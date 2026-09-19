from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.experiments import get_experiment_repository
from app.api.routes.human_reviews import get_human_review_repository
from app.domain.models import (
    ApplicationExecution,
    CaseEvaluationReport,
    ExperimentCaseResult,
    ExperimentReport,
)
from app.main import app
from app.repositories.experiment_repository import FileExperimentRepository
from app.repositories.human_review_repository import FileHumanReviewRepository


@pytest.fixture
def repositories(tmp_path: Path):
    experiments = FileExperimentRepository(tmp_path / "experiments")
    reviews = FileHumanReviewRepository(tmp_path / "experiments")
    now = datetime.now(UTC)
    report = ExperimentReport(
        experiment_id="exp-one",
        name="Human review test",
        system="demo",
        dataset_id="demo-v1",
        dataset_version="1.0.0",
        started_at=now,
        completed_at=now,
        passed=True,
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        pass_rate=1.0,
        aggregate_score=1.0,
        cases=[
            ExperimentCaseResult(
                case_id="case-one",
                passed=True,
                execution=ApplicationExecution(case_id="case-one", system="demo"),
                evaluation=CaseEvaluationReport(
                    case_id="case-one",
                    system="demo",
                    passed=True,
                    aggregate_score=1.0,
                    evaluator_count=0,
                    passed_count=0,
                    failed_count=0,
                ),
            )
        ],
    )
    experiments.save(report)
    app.dependency_overrides[get_experiment_repository] = lambda: experiments
    app.dependency_overrides[get_human_review_repository] = lambda: reviews
    yield experiments, reviews
    app.dependency_overrides.clear()


def test_reviews_are_saved_separately_and_remain_accessible(repositories):
    experiments, reviews = repositories
    path = "/api/v1/experiments/exp-one/cases/case-one/reviews"
    payload = {
        "reviewer": "  Ahsen  ",
        "score": 0.75,
        "passed": True,
        "category": "partially_correct",
        "explanation": "  The answer omits one detail.  ",
    }

    with TestClient(app) as client:
        first = client.post(path, json=payload)
        second = client.post(path, json={**payload, "score": 0.5, "passed": False})
        listed = client.get(path)

    assert first.status_code == 201
    assert second.status_code == 201
    assert listed.status_code == 200
    assert first.json()["review_id"] != second.json()["review_id"]
    assert first.json()["reviewer"] == "Ahsen"
    assert first.json()["explanation"] == "The answer omits one detail."
    assert [item["score"] for item in listed.json()] == [0.75, 0.5]
    reopened = FileHumanReviewRepository(reviews.storage_root.parent)
    assert len(reopened.list_case("exp-one", "case-one")) == 2
    assert experiments.get("exp-one").aggregate_score == 1.0


def test_reviews_reject_missing_cases_and_invalid_judgments(repositories):
    path = "/api/v1/experiments/exp-one/cases/case-one/reviews"
    payload = {
        "reviewer": "Ahsen",
        "score": 0.5,
        "passed": False,
        "category": "uncertain",
        "explanation": "Needs manual review.",
    }
    with TestClient(app) as client:
        missing_experiment = "/api/v1/experiments/missing/cases/case-one/reviews"
        assert client.get(missing_experiment).status_code == 404
        missing_case = client.post(path.replace("case-one", "missing"), json=payload)
        assert missing_case.status_code == 404
        assert client.post(path, json={**payload, "score": 1.5}).status_code == 422
        blank_reason = client.post(path, json={**payload, "explanation": "   "})
        assert blank_reason.status_code == 422
