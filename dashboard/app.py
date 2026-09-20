"""Run with: python -m streamlit run dashboard/app.py --server.port 8501."""

import hashlib
import json
import os
from datetime import datetime
from typing import Any

import streamlit as st
from api_client import APIError, EvaluationAPI
from ui_kit import fmt_ms, inject_css, pill, pill_row, short, table, verdict

st.set_page_config(
    page_title="AI Evaluation Platform",
    page_icon="🧪",
    layout="wide",
)
inject_css()

MISSING = "(missing)"
PAGES = {
    "Overview": "🏠",
    "Datasets": "🗂️",
    "Run experiment": "▶️",
    "History": "🕘",
    "Compare": "⚖️",
}
RESULT_LABEL = {"Pass": "✅ Pass", "Fail": "❌ Fail", "Error": "⚠️ Error"}
RESULT_TONE = {"Pass": "ok", "Fail": "warn", "Error": "bad"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
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


def case_category(case: dict[str, Any]) -> str:
    return (case.get("case_metadata") or {}).get("category") or "—"


def case_status(case: dict[str, Any]) -> str:
    """Pass, Fail (an evaluator failed) or Error (the application call failed)."""
    if case.get("passed"):
        return "Pass"
    if (case.get("execution") or {}).get("error"):
        return "Error"
    return "Fail"


def case_counts(report: dict[str, Any]) -> dict[str, int]:
    cases = report.get("cases") or []
    if cases:
        statuses = [case_status(case) for case in cases]
        return {
            "total": len(cases),
            "passed": statuses.count("Pass"),
            "failed": statuses.count("Fail"),
            "errors": statuses.count("Error"),
        }
    total = report.get("total_cases", 0)
    passed = report.get("passed_cases", 0)
    return {"total": total, "passed": passed, "failed": total - passed, "errors": 0}


def field_rows(expected: Any, actual: Any) -> list[dict[str, str]]:
    """Field-by-field comparison of two key-value outputs."""
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return []
    rows = []
    for field in [*expected, *(key for key in actual if key not in expected)]:
        in_expected = field in expected
        want = expected.get(field, MISSING)
        got = actual.get(field, MISSING)
        match = "—" if not in_expected else ("✅" if want == got else "❌")
        rows.append(
            {
                "Field": field,
                "Match": match,
                "Expected": short(want) if in_expected else "—",
                "Actual": short(got),
            }
        )
    return rows


def show_verdict(counts: dict[str, int]) -> None:
    total, passed = counts["total"], counts["passed"]
    attention = counts["failed"] + counts["errors"]
    if not total:
        verdict("No cases in this report", tone="neutral")
    elif not attention:
        verdict(f"All {total} cases passed", tone="ok")
    else:
        parts = []
        if counts["failed"]:
            parts.append(f"{counts['failed']} failed an evaluator check")
        if counts["errors"]:
            parts.append(f"{counts['errors']} hit an execution error")
        verdict(
            f"{attention} of {total} cases need attention",
            [f"{passed} passed · " + " · ".join(parts)],
            tone="bad" if counts["errors"] else "warn",
        )


# --------------------------------------------------------------------------- #
# Report display (used by Run experiment and History)
# --------------------------------------------------------------------------- #
def metrics(report: dict[str, Any]) -> None:
    columns = st.columns(4)
    columns[0].metric("Pass rate", f"{report.get('pass_rate', 0):.1%}")
    columns[1].metric("Score", f"{report.get('aggregate_score', 0):.3f}")
    columns[2].metric(
        "Passed cases",
        f"{report.get('passed_cases', 0)}/{report.get('total_cases', 0)}",
    )
    columns[3].metric("Total latency", fmt_ms(report.get("total_latency_ms", 0)))


def report_details(
    report: dict[str, Any], api: EvaluationAPI | None = None, key: str = "report"
) -> None:
    experiment_id = report["experiment_id"]
    key = f"{key}_{experiment_id}"
    st.subheader(report.get("name", "Experiment"))
    pill_row(
        pill(report.get("system", "—")),
        pill(report.get("dataset_id", "—")),
        pill(f"version {report.get('dataset_version', '—')}"),
        pill(format_date(report.get("completed_at"))),
    )
    st.caption(f"Experiment ID: `{experiment_id}`")
    show_verdict(case_counts(report))
    metrics(report)

    cases_tab, scores_tab = st.tabs(["Cases", "Evaluator scores"])
    with scores_tab:
        scores = report.get("metric_scores", {})
        if scores:
            table(
                [{"Evaluator": name, "Score": score} for name, score in scores.items()],
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score", min_value=0.0, max_value=1.0, format="%.3f"
                    )
                },
            )
        else:
            st.info("This report has no aggregate evaluator scores.")
    with cases_tab:
        cases_view(report, api, key)


def cases_view(
    report: dict[str, Any], api: EvaluationAPI | None, key: str
) -> None:
    cases = report.get("cases", [])
    if not cases:
        st.info("This report has no saved case results.")
        return
    counts = case_counts(report)
    attention = counts["failed"] + counts["errors"]
    options = ["All", "Needs attention", "Execution errors"]
    totals = {
        "All": len(cases),
        "Needs attention": attention,
        "Execution errors": counts["errors"],
    }
    left, right = st.columns([3, 2])
    view = left.radio(
        "Show",
        options,
        index=1 if attention else 0,
        horizontal=True,
        format_func=lambda option: f"{option} ({totals[option]})",
        key=f"{key}_view",
    )
    categories = sorted({case_category(case) for case in cases})
    picked = (
        right.multiselect("Category", categories, key=f"{key}_categories")
        if len(categories) > 1
        else []
    )

    def keep(case: dict[str, Any]) -> bool:
        status = case_status(case)
        if view == "Needs attention" and status == "Pass":
            return False
        if view == "Execution errors" and status != "Error":
            return False
        return not picked or case_category(case) in picked

    shown = [case for case in cases if keep(case)]
    if not shown:
        st.info("No cases match these filters.")
        return
    table(
        [
            {
                "Case": case["case_id"],
                "Category": case_category(case),
                "Result": RESULT_LABEL[case_status(case)],
                "Score": (case.get("evaluation") or {}).get("aggregate_score"),
                "Latency": fmt_ms((case.get("execution") or {}).get("latency_ms")),
            }
            for case in shown
        ],
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0.0, max_value=1.0, format="%.2f"
            )
        },
    )
    st.caption(f"Showing {len(shown)} of {len(cases)} cases.")
    selected = st.selectbox(
        "Inspect a case",
        shown,
        format_func=lambda case: (
            f"{RESULT_LABEL[case_status(case)]} · {case['case_id']} "
            f"· {case_category(case)}"
        ),
        key=f"{key}_case",
    )
    with st.container(border=True):
        case_detail(selected, report["experiment_id"], api)


def case_detail(
    case: dict[str, Any], experiment_id: str, api: EvaluationAPI | None
) -> None:
    execution = case.get("execution") or {}
    evaluation = case.get("evaluation") or {}
    status = case_status(case)
    score = evaluation.get("aggregate_score")
    st.markdown(f"##### {case['case_id']}")
    pill_row(
        pill(status, RESULT_TONE[status]),
        pill(f"Score {score:.2f}" if score is not None else "Score —"),
        pill(fmt_ms(execution.get("latency_ms"))),
        pill(case_category(case)),
    )
    if execution.get("error"):
        st.error(execution["error"])

    results = sorted(evaluation.get("results", []), key=lambda r: bool(r.get("passed")))
    if results:
        st.markdown("**Evaluator results** (failures first)")
        table(
            [
                {
                    "Evaluator": result.get("evaluator"),
                    "Result": "✅ Pass" if result.get("passed") else "❌ Fail",
                    "Score": result.get("score"),
                    "Reason": result.get("reason"),
                }
                for result in results
            ],
            column_config={
                "Score": st.column_config.NumberColumn("Score", format="%.2f"),
                "Reason": st.column_config.TextColumn("Reason", width="large"),
            },
        )

    output_tab, input_tab, raw_tab = st.tabs(["Output", "Input", "Raw data"])
    with output_tab:
        expected = case.get("expected_output", {})
        actual = execution.get("output", {})
        rows = field_rows(expected, actual)
        if rows:
            table(
                rows,
                column_config={
                    "Match": st.column_config.TextColumn("Match", width="small"),
                    "Expected": st.column_config.TextColumn("Expected", width="large"),
                    "Actual": st.column_config.TextColumn("Actual", width="large"),
                },
            )
        with st.expander("Full expected and actual output", expanded=not rows):
            left, right = st.columns(2)
            left.markdown("**Expected output**")
            left.json(expected)
            right.markdown("**Actual output**")
            right.json(actual)
    with input_tab:
        st.json(case.get("input", {}))
    with raw_tab:
        st.json({"execution": execution, "evaluation": evaluation})

    if api is not None:
        with st.expander("Human review"):
            human_review_form(api, experiment_id, case)


def human_review_form(
    api: EvaluationAPI, experiment_id: str, case: dict[str, Any]
) -> None:
    case_id = case["case_id"]
    form_key = f"review_{experiment_id}_{case_id}"
    # Bumping the counter after a save gives the form fresh, empty widgets.
    round_ = st.session_state.get(f"{form_key}_round", 0)
    reviews = load(api.human_reviews, experiment_id, case_id)
    if reviews:
        table(
            [
                {
                    "Reviewer": review["reviewer"],
                    "Judgment": review["category"],
                    "Score": review["score"],
                    "Passed": "✅" if review["passed"] else "❌",
                    "Explanation": review["explanation"],
                    "Reviewed": format_date(review.get("created_at")),
                }
                for review in reviews
            ],
            column_config={
                "Explanation": st.column_config.TextColumn("Explanation", width="large")
            },
        )
    else:
        st.caption("No human reviews saved for this case yet.")
    if st.session_state.pop(f"{form_key}_saved", False):
        st.success("Human review saved.")
    with st.form(f"{form_key}_{round_}"):
        reviewer = st.text_input(
            "Reviewer name", value=st.session_state.get("reviewer_name", "")
        )
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
                    st.session_state["reviewer_name"] = reviewer.strip()
                    st.session_state[f"{form_key}_saved"] = True
                    st.session_state[f"{form_key}_round"] = round_ + 1
                    st.rerun()


# --------------------------------------------------------------------------- #
# Evaluator defaults
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def overview(api: EvaluationAPI) -> None:
    st.title("AI Evaluation Platform")
    st.caption("Track evaluation runs and compare changes across your AI systems.")
    health = load(api.health)
    if health is None:
        st.info(
            "Start the evaluation API with "
            "`python -m uvicorn app.main:app --port 8100`, "
            "then click **Refresh data** in the sidebar."
        )
        return
    langfuse = load(api.langfuse_status)
    datasets = load(api.datasets) or []
    reports = load(api.experiments)
    if reports is None:
        return

    pills = [pill("API online", "ok")]
    if langfuse:
        message = langfuse.get("message", "Status unavailable")
        connected = "connected" in message.lower() and "not" not in message.lower()
        pills.append(
            pill("Langfuse connected", "ok")
            if connected
            else pill(f"Langfuse: {message}", "warn")
        )
    if datasets:
        released = sum(1 for item in datasets if item.get("released"))
        pills.append(
            pill(
                f"{released} of {len(datasets)} datasets released",
                "ok" if released == len(datasets) else "warn",
            )
        )
    pill_row(*pills)

    ordered = reports_by_date(reports)
    columns = st.columns(3)
    columns[0].metric("Saved experiments", len(reports))
    columns[1].metric(
        "Systems evaluated", len({item.get("system") for item in reports})
    )
    if ordered:
        latest = ordered[0]
        previous = next(
            (
                item
                for item in ordered[1:]
                if item.get("dataset_id") == latest.get("dataset_id")
            ),
            None,
        )
        delta = (
            f"{latest.get('pass_rate', 0) - previous.get('pass_rate', 0):+.1%}"
            if previous
            else None
        )
        columns[2].metric(
            "Latest pass rate", f"{latest.get('pass_rate', 0):.1%}", delta
        )
        note = (
            f"Latest run: {latest.get('name', 'Unnamed')}, "
            f"{format_date(latest.get('completed_at'))}."
        )
        if previous:
            note += f" Change is against the previous {latest['dataset_id']} run."
        st.caption(note)

    if not reports:
        st.info("No saved experiments yet. Open **Run experiment** to create one.")
        return
    st.markdown("### Recent experiments")
    table(
        [
            {
                "Name": report.get("name"),
                "System": report.get("system"),
                "Result": (
                    "✅ All passed" if report.get("passed") else "⚠️ Needs review"
                ),
                "Pass rate": (report.get("pass_rate") or 0) * 100,
                "Cases": (
                    f"{report.get('passed_cases', 0)}/{report.get('total_cases', 0)}"
                ),
                "Completed": format_date(report.get("completed_at")),
                "ID": report.get("experiment_id"),
            }
            for report in ordered[:15]
        ],
        column_config={
            "Pass rate": st.column_config.ProgressColumn(
                "Pass rate", min_value=0, max_value=100, format="%.0f%%"
            ),
            "Cases": st.column_config.TextColumn("Cases", width="small"),
        },
    )
    if len(ordered) > 15:
        st.caption(
            f"Showing the 15 most recent of {len(ordered)}. See History for all."
        )


def datasets_page(api: EvaluationAPI) -> None:
    st.title("Datasets")
    datasets = load(api.datasets)
    if datasets is None:
        return
    if not datasets:
        st.info(
            "No datasets are registered yet. Add entries to `datasets/manifest.json`."
        )
        return
    table(
        [
            {
                "Dataset": item["id"],
                "System": item["system"],
                "Version": item["version"],
                "Cases": item["case_count"],
                "Status": "Released" if item.get("released") else "Candidate",
            }
            for item in datasets
        ]
    )
    if any(not item.get("released") for item in datasets):
        st.caption(
            "Candidate datasets are development baselines that still need label "
            "review. They are not released benchmarks."
        )
    selected = st.selectbox("Inspect dataset", datasets, format_func=lambda d: d["id"])
    data = load(api.dataset, selected["id"])
    if not data:
        return
    if selected.get("description"):
        st.caption(selected["description"])
    cases = data.get("cases", [])

    def category(case: dict[str, Any]) -> str:
        meta = case.get("metadata") or case.get("case_metadata") or {}
        return meta.get("category") or case.get("category") or "—"

    categories = sorted({category(case) for case in cases})
    left, right = st.columns([2, 3])
    query = left.text_input("Search case IDs", placeholder="e.g. case-014")
    picked = (
        right.multiselect("Category", categories) if len(categories) > 1 else []
    )
    shown = [
        case
        for case in cases
        if query.strip().lower() in case["id"].lower()
        and (not picked or category(case) in picked)
    ]
    if not shown:
        st.info("No cases match these filters.")
        return
    table(
        [
            {
                "Case": case["id"],
                "Category": category(case),
                "Input": short(case.get("input"), 110),
            }
            for case in shown
        ],
        column_config={"Input": st.column_config.TextColumn("Input", width="large")},
    )
    st.caption(f"Showing {len(shown)} of {len(cases)} cases.")
    case = st.selectbox("Inspect a case", shown, format_func=lambda c: c["id"])
    with st.container(border=True):
        st.markdown(f"##### {case['id']}")
        left, right = st.columns(2)
        left.markdown("**Input**")
        left.json(case.get("input"))
        right.markdown("**Expected output**")
        right.json(case.get("expected_output"))


def run_page(api: EvaluationAPI) -> None:
    st.title("Run an experiment")
    datasets = load(api.datasets)
    if not datasets:
        return
    with st.container(border=True):
        selected = st.selectbox("Dataset", datasets, format_func=lambda d: d["id"])
        pill_row(
            pill(selected["system"]),
            pill(f"{selected['case_count']} cases"),
            pill(
                "Released" if selected.get("released") else "Candidate dataset",
                "ok" if selected.get("released") else "warn",
            ),
        )
        name = st.text_input(
            "Experiment name", value=f"{selected['system']} evaluation"
        )

        defaults = default_evaluators(selected["system"])
        names = [item["name"] for item in defaults]
        chosen = st.multiselect(
            "Evaluators",
            names,
            default=names,
            key=f"chosen_{selected['id']}",
            help="Each evaluator scores every case. Deselect the ones you don't need.",
        )
        evaluators = [
            json.loads(json.dumps(item)) for item in defaults if item["name"] in chosen
        ]
        for item in evaluators:
            if item["name"] == "latency":
                limit = st.number_input(
                    "Latency limit per case (ms)",
                    min_value=1000,
                    value=int(item["settings"]["max_latency_ms"]),
                    step=5000,
                    key=f"latency_{selected['id']}",
                )
                item["settings"]["max_latency_ms"] = int(limit)

        guided = json.dumps(evaluators, indent=2)
        with st.expander("Evaluator settings (JSON)"):
            edit = st.checkbox(
                "Edit JSON directly", key=f"edit_json_{selected['id']}"
            )
            if edit:
                digest = hashlib.md5(guided.encode()).hexdigest()[:8]
                evaluators_text = st.text_area(
                    "Evaluators (JSON list)",
                    value=guided,
                    height=300,
                    key=f"evaluators_{selected['id']}_{digest}",
                )
            else:
                evaluators_text = guided
                st.code(guided, language="json")

    st.caption(
        "Cases run one after another and the report is saved when the run "
        "finishes. If this page disconnects, check History before running again."
    )
    if st.button("Run experiment", type="primary"):
        try:
            parsed = json.loads(evaluators_text)
            if not isinstance(parsed, list) or not parsed:
                raise ValueError("Select at least one evaluator.")
            if not name.strip():
                raise ValueError("Enter an experiment name.")
        except ValueError as error:
            st.error(str(error))
        else:
            with st.status(
                f"Running {selected['case_count']} cases…", expanded=True
            ) as status:
                st.write("Running the application, then scoring each case.")
                report = load(
                    api.run,
                    {
                        "name": name.strip(),
                        "dataset_id": selected["id"],
                        "evaluators": parsed,
                    },
                )
                if report:
                    status.update(
                        label=f"Finished. Saved as {report['experiment_id']}",
                        state="complete",
                        expanded=False,
                    )
                    st.session_state["last_report"] = report
                else:
                    status.update(label="Run failed", state="error")

    # Keep the latest result on screen while the person filters and inspects it.
    report = st.session_state.get("last_report")
    if report:
        st.divider()
        head, clear = st.columns([5, 1])
        head.markdown("### Latest result")
        if clear.button("Clear result"):
            st.session_state.pop("last_report", None)
            st.rerun()
        report_details(report, api, key="run")


def history_page(api: EvaluationAPI) -> None:
    st.title("Experiment history")
    reports = load(api.experiments)
    if reports is None:
        return
    if not reports:
        st.info("No saved experiments yet. Open **Run experiment** to create one.")
        return
    reports = reports_by_date(reports)
    systems = sorted({item.get("system", "—") for item in reports})
    if len(systems) > 1:
        system = st.radio("System", ["All", *systems], horizontal=True)
        if system != "All":
            reports = [item for item in reports if item.get("system") == system]
    selected = st.selectbox("Experiment", reports, format_func=label)
    report = load(api.experiment, selected["experiment_id"])
    if report:
        st.divider()
        report_details(report, api, key="history")


def case_changes(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """Cases whose pass/fail status differs between two runs, regressions first."""
    before = {case["case_id"]: case for case in baseline.get("cases", [])}
    after = {case["case_id"]: case for case in candidate.get("cases", [])}
    rows = []
    for case_id, new in after.items():
        old = before.get(case_id)
        if old is None or bool(old.get("passed")) == bool(new.get("passed")):
            continue
        rows.append(
            {
                "Case": case_id,
                "Category": case_category(new),
                "Change": "🔻 Regressed" if old.get("passed") else "🔺 Fixed",
                "Baseline score": (old.get("evaluation") or {}).get(
                    "aggregate_score"
                ),
                "Candidate score": (new.get("evaluation") or {}).get(
                    "aggregate_score"
                ),
            }
        )
    rows.sort(key=lambda row: (row["Change"] != "🔻 Regressed", row["Case"]))
    return rows, len(set(before) ^ set(after))


def default_pair(
    reports: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """(older, newer): the most recent run and the run before it on that dataset."""
    for index, newer in enumerate(reports):
        for older in reports[index + 1 :]:
            if older.get("dataset_id") == newer.get("dataset_id"):
                return older, newer
    return None


def compare_page(api: EvaluationAPI) -> None:
    st.title("Compare experiments")
    reports = load(api.experiments)
    if reports is None:
        return
    if len(reports) < 2:
        st.info("Run at least two experiments to compare them.")
        return
    reports = reports_by_date(reports)
    pair = default_pair(reports)
    left, right = st.columns(2)
    baseline = left.selectbox(
        "Baseline",
        reports,
        index=reports.index(pair[0]) if pair else 0,
        format_func=label,
    )
    candidates = [
        report for report in reports
        if report["dataset_id"] == baseline["dataset_id"]
        and report["experiment_id"] != baseline["experiment_id"]
    ]
    if not candidates:
        st.info("No other run exists for this dataset. Select a different baseline.")
        return
    candidate = right.selectbox(
        "Candidate",
        candidates,
        index=candidates.index(pair[1]) if pair and pair[1] in candidates else 0,
        format_func=label,
    )
    if candidate.get("completed_at", "") < baseline.get("completed_at", ""):
        st.warning(
            "The candidate is older than the baseline, so changes read backwards."
        )
    with st.expander("Regression thresholds"):
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
    reasons = comparison.get("regression_reasons", [])
    if comparison["regression_detected"]:
        verdict("Regression detected", reasons, tone="bad")
    else:
        verdict("No regression detected", reasons, tone="ok")
    a, b, c = st.columns(3)
    a.metric("Pass rate", f"{comparison['candidate_pass_rate']:.1%}",
             f"{comparison['pass_rate_change']:+.1%}")
    b.metric("Score", f"{comparison['candidate_aggregate_score']:.3f}",
             f"{comparison['aggregate_score_change']:+.3f}")
    latency_delta = comparison.get("latency_change_percent")
    c.metric("Average latency", f"{comparison['candidate_average_latency_ms']:.0f} ms",
             f"{latency_delta:+.1f}%" if latency_delta is not None else "—",
             delta_color="inverse")

    st.markdown("### Cases that changed")
    base_report = load(api.experiment, baseline["experiment_id"])
    cand_report = load(api.experiment, candidate["experiment_id"])
    if base_report and cand_report:
        rows, unmatched = case_changes(base_report, cand_report)
        if rows:
            regressed = sum(1 for row in rows if row["Change"].endswith("Regressed"))
            st.caption(
                f"{regressed} regressed, {len(rows) - regressed} fixed. "
                "Regressions are listed first."
            )
            table(
                rows,
                column_config={
                    "Baseline score": st.column_config.NumberColumn(format="%.2f"),
                    "Candidate score": st.column_config.NumberColumn(format="%.2f"),
                },
            )
        else:
            st.caption("No case changed between passing and failing.")
        if unmatched:
            st.caption(f"{unmatched} cases exist in only one of the two runs.")

    st.markdown("### Metric comparison")
    table(
        [
            {
                "Evaluator": row["metric"],
                "Baseline": row.get("baseline_score"),
                "Candidate": row.get("candidate_score"),
                "Change": row.get("absolute_change"),
                "Status": row["status"],
                "Regression": "⚠️ Regression" if row.get("regression") else "OK",
            }
            for row in comparison.get("metrics", [])
        ],
        column_config={
            "Baseline": st.column_config.NumberColumn(format="%.3f"),
            "Candidate": st.column_config.NumberColumn(format="%.3f"),
            "Change": st.column_config.NumberColumn(format="%+.3f"),
        },
    )


def main() -> None:
    with st.sidebar:
        st.title("🧪 Evaluation")
        page = st.radio(
            "Navigate",
            list(PAGES),
            format_func=lambda name: f"{PAGES[name]}  {name}",
            label_visibility="collapsed",
        )
        st.button("Refresh data")
        with st.expander("Connection"):
            base_url = st.text_input(
                "API base URL",
                value=os.getenv("EVALUATION_API_URL", "http://127.0.0.1:8100"),
            )
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
