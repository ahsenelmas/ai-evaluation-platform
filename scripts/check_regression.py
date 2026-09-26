"""Compare two saved experiment reports and fail CI on a regression."""

import argparse
import json
import os
from pathlib import Path

from pydantic import ValidationError

from app.domain.models import ExperimentComparison, ExperimentReport
from app.services.experiment_comparison_service import (
    ExperimentComparisonService,
)


def load_report(path: Path) -> ExperimentReport:
    """Load and validate an experiment report from a JSON file."""
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    return ExperimentReport.model_validate(payload)


def compare_reports(
    baseline_path: Path,
    candidate_path: Path,
    *,
    score_tolerance: float = 0.0,
    max_latency_increase_percent: float = 20.0,
) -> ExperimentComparison:
    """Compare two validated experiment reports."""
    baseline = load_report(baseline_path)
    candidate = load_report(candidate_path)

    return ExperimentComparisonService().compare(
        baseline=baseline,
        candidate=candidate,
        score_tolerance=score_tolerance,
        max_latency_increase_percent=max_latency_increase_percent,
    )


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.1f}%"


def _console_report(comparison: ExperimentComparison) -> str:
    status = "FAIL" if comparison.regression_detected else "PASS"
    lines = [
        "AI EVALUATION REGRESSION GATE",
        f"Baseline:  {comparison.baseline_experiment_id}",
        f"Candidate: {comparison.candidate_experiment_id}",
        "",
        (
            "Pass rate: "
            f"{comparison.baseline_pass_rate:.1%} -> "
            f"{comparison.candidate_pass_rate:.1%} "
            f"({comparison.pass_rate_change:+.1%})"
        ),
        (
            "Score:     "
            f"{comparison.baseline_aggregate_score:.3f} -> "
            f"{comparison.candidate_aggregate_score:.3f} "
            f"({comparison.aggregate_score_change:+.3f})"
        ),
        (
            "Latency:   "
            f"{comparison.baseline_average_latency_ms:.1f} ms -> "
            f"{comparison.candidate_average_latency_ms:.1f} ms "
            f"({_format_percent(comparison.latency_change_percent)})"
        ),
        "",
    ]

    if comparison.regression_reasons:
        lines.append("Regression reasons:")
        lines.extend(f"- {reason}" for reason in comparison.regression_reasons)
        lines.append("")

    lines.append(f"RESULT: {status}")
    return "\n".join(lines)


def _markdown_report(comparison: ExperimentComparison) -> str:
    status = "FAIL" if comparison.regression_detected else "PASS"
    rows = [
        "## AI evaluation regression gate",
        "",
        f"**Result: {status}**",
        "",
        "| Metric | Baseline | Candidate | Change |",
        "| --- | ---: | ---: | ---: |",
        (
            "| Pass rate | "
            f"{comparison.baseline_pass_rate:.1%} | "
            f"{comparison.candidate_pass_rate:.1%} | "
            f"{comparison.pass_rate_change:+.1%} |"
        ),
        (
            "| Aggregate score | "
            f"{comparison.baseline_aggregate_score:.3f} | "
            f"{comparison.candidate_aggregate_score:.3f} | "
            f"{comparison.aggregate_score_change:+.3f} |"
        ),
        (
            "| Average latency | "
            f"{comparison.baseline_average_latency_ms:.1f} ms | "
            f"{comparison.candidate_average_latency_ms:.1f} ms | "
            f"{_format_percent(comparison.latency_change_percent)} |"
        ),
    ]

    if comparison.regression_reasons:
        rows.extend(["", "### Regression reasons", ""])
        rows.extend(f"- {reason}" for reason in comparison.regression_reasons)

    return "\n".join(rows) + "\n"


def _write_github_summary(comparison: ExperimentComparison) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with Path(summary_path).open("a", encoding="utf-8") as file:
        file.write(_markdown_report(comparison))


def run_gate(
    baseline_path: Path,
    candidate_path: Path,
    *,
    score_tolerance: float = 0.0,
    max_latency_increase_percent: float = 20.0,
) -> int:
    """Run the regression gate and return a process exit code."""
    try:
        comparison = compare_reports(
            baseline_path,
            candidate_path,
            score_tolerance=score_tolerance,
            max_latency_increase_percent=max_latency_increase_percent,
        )
    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as error:
        print(f"REGRESSION GATE ERROR: {error}")
        return 2

    print(_console_report(comparison))
    _write_github_summary(comparison)
    return 1 if comparison.regression_detected else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail when a candidate experiment regresses from a baseline.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to the baseline ExperimentReport JSON file.",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Path to the candidate ExperimentReport JSON file.",
    )
    parser.add_argument(
        "--score-tolerance",
        type=float,
        default=0.0,
        help="Allowed score and metric decrease before failing (default: 0).",
    )
    parser.add_argument(
        "--max-latency-increase-percent",
        type=float,
        default=20.0,
        help="Allowed average latency increase before failing (default: 20).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return run_gate(
        args.baseline,
        args.candidate,
        score_tolerance=args.score_tolerance,
        max_latency_increase_percent=args.max_latency_increase_percent,
    )


if __name__ == "__main__":
    raise SystemExit(main())
