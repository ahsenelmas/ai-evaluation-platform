from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.experiments import (
    get_experiment_repository,
)
from app.domain.models import ExperimentReport
from app.main import app
from app.repositories.experiment_repository import (
    FileExperimentRepository,
)

client = TestClient(app)


def create_report(
    experiment_id: str,
    *,
    system: str = "ata-rag",
    dataset_id: str = "ata-rag-golden-v1",
    passed: bool = True,
    pass_rate: float = 1.0,
    aggregate_score: float = 1.0,
    semantic_score: float = 1.0,
    total_latency_ms: int = 3000,
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
        dataset_version="1.1.0",
        started_at=timestamp,
        completed_at=timestamp,
        passed=passed,
        total_cases=3,
        passed_cases=3 if passed else 0,
        failed_cases=0 if passed else 3,
        pass_rate=pass_rate,
        aggregate_score=aggregate_score,
        metric_scores={
            "exact_match": 1.0,
            "semantic_facts": semantic_score,
        },
        total_latency_ms=total_latency_ms,
    )


@pytest.fixture
def comparison_repository(
    tmp_path: Path,
):
    repository = FileExperimentRepository(
        storage_root=tmp_path,
    )

    app.dependency_overrides[
        get_experiment_repository
    ] = lambda: repository

    yield repository

    app.dependency_overrides.clear()


def test_compare_endpoint_returns_no_regression(
    comparison_repository: FileExperimentRepository,
):
    comparison_repository.save(
        create_report("exp-baseline")
    )

    comparison_repository.save(
        create_report("exp-candidate")
    )

    response = client.get(
        "/api/v1/experiments/compare",
        params={
            "baseline_id": "exp-baseline",
            "candidate_id": "exp-candidate",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["regression_detected"] is False
    assert body["pass_rate_change"] == 0.0
    assert body["aggregate_score_change"] == 0.0
    assert body["regressed_metrics"] == []


def test_compare_endpoint_detects_regression(
    comparison_repository: FileExperimentRepository,
):
    comparison_repository.save(
        create_report("exp-baseline")
    )

    comparison_repository.save(
        create_report(
            "exp-candidate",
            passed=False,
            pass_rate=0.0,
            aggregate_score=0.5,
            semantic_score=0.0,
        )
    )

    response = client.get(
        "/api/v1/experiments/compare",
        params={
            "baseline_id": "exp-baseline",
            "candidate_id": "exp-candidate",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["regression_detected"] is True
    assert body["pass_rate_change"] == -1.0
    assert body["aggregate_score_change"] == -0.5

    assert body["regressed_metrics"] == [
        "semantic_facts"
    ]


def test_compare_endpoint_returns_404_for_missing_report(
    comparison_repository: FileExperimentRepository,
):
    comparison_repository.save(
        create_report("exp-baseline")
    )

    response = client.get(
        "/api/v1/experiments/compare",
        params={
            "baseline_id": "exp-baseline",
            "candidate_id": "exp-missing",
        },
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Experiment 'exp-missing' was not found."
    )


def test_compare_endpoint_rejects_different_systems(
    comparison_repository: FileExperimentRepository,
):
    comparison_repository.save(
        create_report(
            "exp-baseline",
            system="ata-rag",
        )
    )

    comparison_repository.save(
        create_report(
            "exp-candidate",
            system="internship-coordinator",
        )
    )

    response = client.get(
        "/api/v1/experiments/compare",
        params={
            "baseline_id": "exp-baseline",
            "candidate_id": "exp-candidate",
        },
    )

    assert response.status_code == 422
    assert "different systems" in response.json()["detail"]
