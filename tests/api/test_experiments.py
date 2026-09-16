from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters.base import ApplicationAdapter
from app.adapters.registry import AdapterRegistry
from app.api.routes.experiments import (
    get_adapter_registry,
    get_dataset_service,
    get_experiment_repository,
    get_langfuse_publisher,
)
from app.domain.models import (
    ApplicationExecution,
    DatasetManifestEntry,
    EvaluationCase,
    EvaluationDataset,
    ExperimentReport,
    TokenUsage,
)
from app.main import app
from app.repositories.experiment_repository import (
    FileExperimentRepository,
)
from app.services.dataset_service import (
    DatasetNotFoundError,
)


class FakeExperimentAdapter(ApplicationAdapter):
    system = "demo-system"

    async def execute(
        self,
        case: EvaluationCase,
    ) -> ApplicationExecution:
        return ApplicationExecution(
            case_id=case.id,
            system=case.system,
            output={
                "answer": case.input["answer"],
            },
            success=True,
            latency_ms=20,
            token_usage=TokenUsage(
                input_tokens=4,
                output_tokens=2,
                total_tokens=6,
            ),
            estimated_cost=0.002,
            model="fake-model",
            prompt_version="prompt-v1",
            application_version="app-v1",
        )


class FakeLangfusePublisher:
    def __init__(self) -> None:
        self.published_reports: list[ExperimentReport] = []

    def publish(
        self,
        report: ExperimentReport,
    ) -> bool:
        self.published_reports.append(report)
        return True


class FakeDatasetService:
    def get_dataset(
        self,
        dataset_id: str,
    ) -> EvaluationDataset:
        if dataset_id == "missing-dataset":
            raise DatasetNotFoundError("Dataset 'missing-dataset' was not found.")

        cases = [
            EvaluationCase(
                id="case-1",
                system="demo-system",
                input={"answer": "Paris"},
                expected_output={"answer": "Paris"},
            ),
            EvaluationCase(
                id="case-2",
                system="demo-system",
                input={"answer": "Berlin"},
                expected_output={"answer": "Berlin"},
            ),
        ]

        return EvaluationDataset(
            metadata=DatasetManifestEntry(
                id="demo-dataset",
                system="demo-system",
                version="1.0.0",
                file_path="unused.jsonl",
                case_count=len(cases),
            ),
            cases=cases,
        )


def override_dataset_service() -> FakeDatasetService:
    return FakeDatasetService()


def override_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()

    registry.register(FakeExperimentAdapter())

    return registry


client = TestClient(app)


@pytest.fixture(autouse=True)
def dependency_overrides(
    tmp_path: Path,
):
    repository = FileExperimentRepository(storage_root=tmp_path)

    publisher = FakeLangfusePublisher()

    app.dependency_overrides[get_dataset_service] = override_dataset_service

    app.dependency_overrides[get_adapter_registry] = override_adapter_registry

    app.dependency_overrides[get_experiment_repository] = lambda: repository

    app.dependency_overrides[get_langfuse_publisher] = lambda: publisher

    yield publisher

    app.dependency_overrides.clear()


def test_run_experiment_returns_report():
    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "API experiment",
            "dataset_id": "demo-dataset",
            "evaluators": [
                {
                    "name": "exact_match",
                    "settings": {"field_name": "answer"},
                }
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "API experiment"
    assert body["system"] == "demo-system"
    assert body["dataset_id"] == ("demo-dataset")
    assert body["dataset_version"] == "1.0.0"

    assert body["passed"] is True
    assert body["total_cases"] == 2
    assert body["passed_cases"] == 2
    assert body["failed_cases"] == 0
    assert body["pass_rate"] == 1.0
    assert body["aggregate_score"] == 1.0

    assert body["metric_scores"] == {
        "execution_success": 1.0,
        "exact_match": 1.0,
    }

    assert body["total_latency_ms"] == 40
    assert body["total_tokens"] == 12
    assert body["total_cost_usd"] == 0.004
    assert len(body["cases"]) == 2

    first_case = body["cases"][0]

    assert first_case["input"] == {"answer": "Paris"}
    assert first_case["expected_output"] == {"answer": "Paris"}


def test_run_experiment_returns_404_for_missing_dataset():
    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "Missing dataset",
            "dataset_id": "missing-dataset",
            "evaluators": [
                {
                    "name": "exact_match",
                    "settings": {"field_name": "answer"},
                }
            ],
        },
    )

    assert response.status_code == 404

    assert response.json()["detail"] == ("Dataset 'missing-dataset' was not found.")


def test_run_experiment_rejects_unknown_evaluator():
    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "Invalid evaluator",
            "dataset_id": "demo-dataset",
            "evaluators": [
                {
                    "name": "unknown-evaluator",
                    "settings": {},
                }
            ],
        },
    )

    assert response.status_code == 422

    assert "Unknown evaluator" in (response.json()["detail"])


def run_test_experiment():
    return client.post(
        "/api/v1/experiments/run",
        json={
            "name": "Stored experiment",
            "dataset_id": "demo-dataset",
            "evaluators": [
                {
                    "name": "exact_match",
                    "settings": {"field_name": "answer"},
                }
            ],
        },
    )


def test_list_experiments_returns_saved_reports():
    run_response = run_test_experiment()

    assert run_response.status_code == 200

    response = client.get("/api/v1/experiments")

    assert response.status_code == 200

    reports = response.json()

    assert len(reports) == 1
    assert reports[0]["name"] == ("Stored experiment")
    assert reports[0]["passed"] is True


def test_get_experiment_returns_saved_report():
    run_response = run_test_experiment()

    assert run_response.status_code == 200

    experiment_id = run_response.json()["experiment_id"]

    response = client.get(f"/api/v1/experiments/{experiment_id}")

    assert response.status_code == 200
    assert response.json()["experiment_id"] == experiment_id
    assert response.json()["total_cases"] == 2


def test_get_experiment_returns_404_when_missing():
    response = client.get("/api/v1/experiments/exp-missing")

    assert response.status_code == 404

    assert response.json()["detail"] == ("Experiment 'exp-missing' was not found.")


def test_run_experiment_publishes_to_langfuse(
    dependency_overrides,
):
    publisher = dependency_overrides

    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "Langfuse API test",
            "dataset_id": "demo-dataset",
            "evaluators": [
                {
                    "name": "exact_match",
                    "settings": {"field_name": "answer"},
                }
            ],
        },
    )

    assert response.status_code == 200

    assert len(publisher.published_reports) == 1

    published_report = publisher.published_reports[0]

    assert published_report.experiment_id == (response.json()["experiment_id"])

    assert published_report.name == ("Langfuse API test")
