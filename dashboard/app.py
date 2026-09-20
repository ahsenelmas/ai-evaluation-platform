"""Run with: python -m streamlit run dashboard/app.py --server.port 8501."""

import json
import os
from datetime import datetime
from typing import Any

import streamlit as st
from api_client import APIError, EvaluationAPI

st.set_page_config(
    page_title="AI Evaluation Platform",
    page_icon="🧪",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1250px; padding-top: 2rem;}
    [data-testid="stMetric"] {
        border: 1px solid #dce6e1; border-radius: 12px;
        padding: 14px; background: #f7faf8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def load(call: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return call(*args, **kwargs)
    except APIError as error:
        st.error(str(error))
        return None


def label(report: dict[str, Any]) -> str:
    return (
        f"{report.get('name', 'Unnamed')} · {report['experiment_id']} "
        f"· {report.get('pass_rate', 0):.0%}"
    )


def reports_by_date(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(reports, key=lambda item: item.get("completed_at", ""), reverse=True)


def format_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return value


def metrics(report: dict[str, Any]) -> None:
    columns = st.columns(4)
    columns[0].metric("Pass rate", f"{report.get('pass_rate', 0):.1%}")
    columns[1].metric("Score", f"{report.get('aggregate_score', 0):.3f}")
    columns[2].metric(
        "Passed cases",
        f"{report.get('passed_cases', 0)}/{report.get('total_cases', 0)}",
    )
    columns[3].metric("Total latency", f"{report.get('total_latency_ms', 0):,} ms")


def report_details(report: dict[str, Any], api: EvaluationAPI | None = None) -> None:
    st.subheader(report.get("name", "Experiment"))
    st.caption(
        f"{report['experiment_id']} · {report.get('system', '—')} · "
        f"{report.get('dataset_id', '—')} v{report.get('dataset_version', '—')} · "
        f"{format_date(report.get('completed_at'))}"
    )
    metrics(report)
    st.write("**Status:**", "Passed ✅" if report.get("passed") else "Failed ❌")
    scores = report.get("metric_scores", {})
    if scores:
        st.markdown("#### Evaluator scores")
        st.dataframe(
            [{"Evaluator": name, "Score": score} for name, score in scores.items()],
            hide_index=True,
            use_container_width=True,
        )
    cases = report.get("cases", [])
    if cases:
        st.markdown("#### Cases")
        st.dataframe(
            [
                {
                    "Case": case["case_id"],
                    "Category": case.get("case_metadata", {}).get("category", "—"),
                    "Passed": case.get("passed", False),
                    "Score": case.get("evaluation", {}).get("aggregate_score"),
                    "Latency (ms)": case.get("execution", {}).get("latency_ms", 0),
                }
                for case in cases
            ],
            hide_index=True,
            use_container_width=True,
        )
        failed_only = st.checkbox("Show failed cases only", key="failed_only")
        for case in cases:
            if failed_only and case.get("passed"):
                continue
            with st.expander(
                f"{'✅' if case.get('passed') else '❌'} {case['case_id']} "
                f"· {case.get('case_metadata', {}).get('category', 'case')}"
            ):
                execution = case.get("execution", {})
                if execution.get("error"):
                    st.error(execution["error"])
                st.dataframe(
                    [
                        {
                            "Evaluator": result.get("evaluator"),
                            "Passed": result.get("passed"),
                            "Score": result.get("score"),
                            "Reason": result.get("reason"),
                        }
                        for result in case.get("evaluation", {}).get("results", [])
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
                st.write("**Case input**")
                st.json(case.get("input", {}))
                expected, actual = st.columns(2)
                expected.write("**Expected output**")
                expected.json(case.get("expected_output", {}))
                actual.write("**Actual output**")
                actual.json(execution.get("output", {}))
                with st.expander("Execution and evaluator metadata"):
                    st.json({
                        "execution": execution,
                        "evaluation": case.get("evaluation", {}),
                    })
                if api is not None:
                    human_review_form(api, report["experiment_id"], case)


def human_review_form(
    api: EvaluationAPI, experiment_id: str, case: dict[str, Any]
) -> None:
    case_id = case["case_id"]
    st.markdown("**Human reviews**")
    reviews = load(api.human_reviews, experiment_id, case_id)
    if reviews:
        st.dataframe(
            [
                {
                    "Reviewer": review["reviewer"],
                    "Score": review["score"],
                    "Passed": review["passed"],
                    "Category": review["category"],
                    "Explanation": review["explanation"],
                    "Reviewed": format_date(review.get("created_at")),
                }
                for review in reviews
            ],
            hide_index=True,
            use_container_width=True,
        )
    with st.form(f"review_{experiment_id}_{case_id}"):
        reviewer = st.text_input("Reviewer name")
        category = st.selectbox(
            "Human judgment",
            ["correct", "partially_correct", "incorrect", "uncertain"],
        )
        score = st.slider("Human score", 0.0, 1.0, 0.5, 0.05)
        passed = st.checkbox("Human pass decision")
        explanation = st.text_area("Reason for this judgment")
        submitted = st.form_submit_button("Save human review")
        if submitted:
            if not reviewer.strip() or not explanation.strip():
                st.error("Enter a reviewer name and an explanation.")
            else:
                saved = load(
                    api.add_human_review,
                    experiment_id,
                    case_id,
                    {
                        "reviewer": reviewer.strip(),
                        "score": score,
                        "passed": passed,
                        "category": category,
                        "explanation": explanation.strip(),
                    },
                )
                if saved:
                    st.success("Human review saved. Refresh to see it above.")


def default_evaluators(system: str) -> list[dict[str, Any]]:
    if system == "ata-rag":
        return [
            {"name": "exact_match", "settings": {"field_name": "grounded"}},
            {
                "name": "required_fields",
                "settings": {
                    "required_fields": ["answer", "grounded", "sources"],
                    "allow_empty_fields": ["sources"],
                },
            },
            {"name": "latency", "settings": {"max_latency_ms": 60000}},
            {
                "name": "retrieval_recall",
                "settings": {"k": 5, "minimum_score": 1.0},
            },
            {
                "name": "semantic_facts",
                "settings": {"minimum_score": 1.0, "timeout_seconds": 90},
            },
        ]
    return [
        {"name": "exact_match", "settings": {"field_name": "recommendation"}},
        {
            "name": "required_fields",
            "settings": {
                "required_fields": [
                    "recommendation", "missing_fields", "rule_violations"
                ],
                "allow_empty_fields": ["missing_fields", "rule_violations"],
            },
        },
        {"name": "latency", "settings": {"max_latency_ms": 60000}},
        {"name": "security_flag_match", "settings": {}},
        {"name": "missing_fields_match", "settings": {}},
    ]


def overview(api: EvaluationAPI) -> None:
    st.title("AI Evaluation Platform")
    st.caption("Track evaluation runs and compare changes across your AI systems.")
    health = load(api.health)
    if health is None:
        st.info("Start the FastAPI backend on port 8100 and refresh this page.")
        return
    langfuse = load(api.langfuse_status)
    st.success(f"API online · {health.get('service', 'Evaluation API')}")
    if langfuse:
        st.info(f"Langfuse: {langfuse.get('message', 'Status unavailable')}")
    reports = load(api.experiments)
    if reports is None:
        return
    st.metric("Saved experiments", len(reports))
    if reports:
        st.markdown("### Recent experiments")
        st.dataframe(
            [
                {
                    "Name": report.get("name"),
                    "System": report.get("system"),
                    "Passed": report.get("passed"),
                    "Pass rate": report.get("pass_rate"),
                    "Completed": format_date(report.get("completed_at")),
                    "ID": report.get("experiment_id"),
                }
                for report in reports_by_date(reports)[:15]
            ],
            hide_index=True,
            use_container_width=True,
        )


def datasets_page(api: EvaluationAPI) -> None:
    st.title("Datasets")
    datasets = load(api.datasets)
    if datasets is None:
        return
    if not datasets:
        st.info("No datasets are registered yet.")
        return
    st.dataframe(
        [
            {
                "Dataset": item["id"],
                "System": item["system"],
                "Version": item["version"],
                "Cases": item["case_count"],
                "Released": item.get("released", False),
            }
            for item in datasets
        ],
        hide_index=True,
        use_container_width=True,
    )
    selected = st.selectbox("Inspect dataset", datasets, format_func=lambda d: d["id"])
    data = load(api.dataset, selected["id"])
    if data:
        st.caption(selected.get("description", ""))
        for case in data.get("cases", []):
            with st.expander(case["id"]):
                st.json(
                    {
                        "input": case.get("input"),
                        "expected": case.get("expected_output"),
                    }
                )


def run_page(api: EvaluationAPI) -> None:
    st.title("Run an experiment")
    datasets = load(api.datasets)
    if not datasets:
        return
    selected = st.selectbox("Dataset", datasets, format_func=lambda d: d["id"])
    st.caption(f"System: {selected['system']} · {selected['case_count']} cases")
    name = st.text_input("Experiment name", value=f"{selected['system']} evaluation")
    st.caption(
        "Review the evaluator settings before running against the application."
    )
    evaluators_text = st.text_area(
        "Evaluators (JSON list)",
        value=json.dumps(default_evaluators(selected["system"]), indent=2),
        height=300,
        key=f"evaluators_{selected['id']}",
    )
    if st.button("Run experiment", type="primary"):
        try:
            evaluators = json.loads(evaluators_text)
            if not isinstance(evaluators, list) or not evaluators:
                raise ValueError("Evaluators must be a non-empty JSON list.")
            if not name.strip():
                raise ValueError("Enter an experiment name.")
        except ValueError as error:
            st.error(str(error))
            return
        with st.spinner("Running dataset cases and evaluators…"):
            report = load(
                api.run,
                {
                    "name": name.strip(),
                    "dataset_id": selected["id"],
                    "evaluators": evaluators,
                },
            )
        if report:
            st.success(f"Saved experiment {report['experiment_id']}")
            report_details(report, api)


def history_page(api: EvaluationAPI) -> None:
    st.title("Experiment history")
    reports = load(api.experiments)
    if reports is None:
        return
    if not reports:
        st.info("No saved experiments yet. Use Run an experiment to create one.")
        return
    reports = reports_by_date(reports)
    selected = st.selectbox("Experiment", reports, format_func=label)
    report = load(api.experiment, selected["experiment_id"])
    if report:
        report_details(report, api)


def compare_page(api: EvaluationAPI) -> None:
    st.title("Compare experiments")
    reports = load(api.experiments)
    if reports is None:
        return
    if len(reports) < 2:
        st.info("Run at least two experiments to compare them.")
        return
    reports = reports_by_date(reports)
    baseline = st.selectbox("Baseline", reports, index=1, format_func=label)
    candidates = [
        report for report in reports
        if report["dataset_id"] == baseline["dataset_id"]
        and report["experiment_id"] != baseline["experiment_id"]
    ]
    if not candidates:
        st.info("No other run exists for this dataset. Select a different baseline.")
        return
    candidate = st.selectbox("Candidate", candidates, format_func=label)
    score_tolerance = st.number_input(
        "Score tolerance", min_value=0.0, max_value=1.0, value=0.0, step=0.01
    )
    max_latency = st.number_input(
        "Maximum latency increase (%)", min_value=0.0, value=20.0, step=1.0
    )
    comparison = load(
        api.compare,
        baseline["experiment_id"], candidate["experiment_id"],
        score_tolerance=score_tolerance,
        max_latency_increase_percent=max_latency,
    )
    if not comparison:
        return
    if comparison["regression_detected"]:
        st.error("Regression detected")
    else:
        st.success("No regression detected")
    a, b, c = st.columns(3)
    a.metric("Pass rate", f"{comparison['candidate_pass_rate']:.1%}",
             f"{comparison['pass_rate_change']:+.1%}")
    b.metric("Score", f"{comparison['candidate_aggregate_score']:.3f}",
             f"{comparison['aggregate_score_change']:+.3f}")
    latency_delta = comparison.get("latency_change_percent")
    c.metric("Average latency", f"{comparison['candidate_average_latency_ms']:.0f} ms",
             f"{latency_delta:+.1f}%" if latency_delta is not None else "—",
             delta_color="inverse")
    st.markdown("### Metric comparison")
    st.dataframe(
        [
            {
                "Evaluator": row["metric"], "Baseline": row.get("baseline_score"),
                "Candidate": row.get("candidate_score"),
                "Change": row.get("absolute_change"), "Status": row["status"],
                "Regression": row.get("regression", False),
            }
            for row in comparison.get("metrics", [])
        ],
        hide_index=True,
        use_container_width=True,
    )
    for reason in comparison.get("regression_reasons", []):
        st.warning(reason)


def main() -> None:
    with st.sidebar:
        st.title("🧪 Evaluation")
        base_url = st.text_input(
            "API base URL",
            value=os.getenv("EVALUATION_API_URL", "http://127.0.0.1:8100"),
        )
        page = st.radio(
            "Navigate",
            ["Overview", "Datasets", "Run experiment", "History", "Compare"],
        )
        st.caption("Use Refresh in your browser to load recent runs.")
    api = EvaluationAPI(base_url, timeout=3600.0)
    pages = {
        "Overview": overview,
        "Datasets": datasets_page,
        "Run experiment": run_page,
        "History": history_page,
        "Compare": compare_page,
    }
    pages[page](api)


if __name__ == "__main__":
    main()
