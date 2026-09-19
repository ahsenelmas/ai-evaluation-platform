from datetime import UTC, datetime

import pytest

from app.domain.models import ExperimentReport
from app.services.experiment_comparison_service import (
    ExperimentComparisonService,
    IncompatibleExperimentsError,
)


def create_report(
    experiment_id: str,
    *,
    system: str = "ata-rag",
    dataset_id: str = "ata-rag-golden-v1",
    dataset_version: str = "1.1.0",
    passed: bool = True,
    pass_rate: float = 1.0,
    aggregate_score: float = 1.0,
    metric_scores: dict[str, float] | None = None,
    total_latency_ms: int = 3000,
    total_cases: int = 3,
) -> ExperimentReport:
    timestamp = datetime(
        2026,
        9,
        18,
        12,
        0,
        tzinfo=UTC,
    )

    return ExperimentReport(
        experiment_id=experiment_id,
        name=experiment_id,
        system=system,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        started_at=timestamp,
        completed_at=timestamp,
        passed=passed,
        total_cases=total_cases,
        passed_cases=(
            total_cases if passed else total_cases - 1
        ),
        failed_cases=0 if passed else 1,
        pass_rate=pass_rate,
        aggregate_score=aggregate_score,
        metric_scores=metric_scores
        or {
            "exact_match": 1.0,
            "semantic_facts": 1.0,
        },
        total_latency_ms=total_latency_ms,
    )


def test_comparison_reports_no_regression():
    service = ExperimentComparisonService()

    baseline = create_report("exp-baseline")
    candidate = create_report("exp-candidate")

    comparison = service.compare(
        baseline=baseline,
        candidate=candidate,
    )

    assert comparison.regression_detected is False
    assert comparison.regressed_metrics == []
    assert comparison.pass_rate_change == 0.0
    assert comparison.aggregate_score_change == 0.0

    assert all(
        metric.status == "unchanged"
        for metric in comparison.metrics
    )


def test_comparison_detects_metric_regression():
    service = ExperimentComparisonService()

    baseline = create_report("exp-baseline")

    candidate = create_report(
        "exp-candidate",
        passed=False,
        pass_rate=2 / 3,
        aggregate_score=0.9,
        metric_scores={
            "exact_match": 1.0,
            "semantic_facts": 0.5,
        },
    )

    comparison = service.compare(
        baseline=baseline,
        candidate=candidate,
    )

    assert comparison.regression_detected is True
    assert comparison.pass_rate_change < 0
    assert comparison.aggregate_score_change == -0.1

    assert comparison.regressed_metrics == [
        "semantic_facts"
    ]

    semantic_comparison = next(
        metric
        for metric in comparison.metrics
        if metric.metric == "semantic_facts"
    )

    assert semantic_comparison.status == "regressed"
    assert semantic_comparison.absolute_change == -0.5


def test_comparison_detects_latency_regression():
    service = ExperimentComparisonService()

    baseline = create_report(
        "exp-baseline",
        total_latency_ms=3000,
    )

    candidate = create_report(
        "exp-candidate",
        total_latency_ms=3900,
    )

    comparison = service.compare(
        baseline=baseline,
        candidate=candidate,
        max_latency_increase_percent=20.0,
    )

    assert comparison.regression_detected is True
    assert comparison.latency_change_percent == 30.0

    assert any(
        "Average latency increased" in reason
        for reason in comparison.regression_reasons
    )


def test_comparison_marks_missing_metric_as_regression():
    service = ExperimentComparisonService()

    baseline = create_report("exp-baseline")

    candidate = create_report(
        "exp-candidate",
        metric_scores={
            "exact_match": 1.0,
        },
    )

    comparison = service.compare(
        baseline=baseline,
        candidate=candidate,
    )

    assert comparison.regression_detected is True
    assert comparison.regressed_metrics == [
        "semantic_facts"
    ]

    missing_metric = next(
        metric
        for metric in comparison.metrics
        if metric.metric == "semantic_facts"
    )

    assert missing_metric.status == "missing"
    assert missing_metric.regression is True


def test_comparison_rejects_different_systems():
    service = ExperimentComparisonService()

    baseline = create_report(
        "exp-baseline",
        system="ata-rag",
    )

    candidate = create_report(
        "exp-candidate",
        system="internship-coordinator",
    )

    with pytest.raises(
        IncompatibleExperimentsError,
        match="different systems",
    ):
        service.compare(
            baseline=baseline,
            candidate=candidate,
        )


def test_comparison_rejects_different_dataset_versions():
    service = ExperimentComparisonService()
    baseline = create_report("exp-baseline", dataset_version="1.0.0")
    candidate = create_report("exp-candidate", dataset_version="1.1.0")

    with pytest.raises(
        IncompatibleExperimentsError,
        match="different dataset versions",
    ):
        service.compare(baseline=baseline, candidate=candidate)
