import pytest
from fastapi.testclient import TestClient

from app.adapters.base import ApplicationAdapter
from app.adapters.registry import AdapterRegistry
from app.api.routes.experiments import (
    get_adapter_registry,
    get_dataset_service,
)
from app.domain.models import (
    ApplicationExecution,
    DatasetManifestEntry,
    EvaluationCase,
    EvaluationDataset,
    TokenUsage,
)
from app.main import app
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


def override_dataset_service():
    return FakeDatasetService()


def override_adapter_registry():
    registry = AdapterRegistry()
    registry.register(FakeExperimentAdapter())
    return registry


@pytest.fixture(autouse=True)
def dependency_overrides():
    app.dependency_overrides[get_dataset_service] = override_dataset_service

    app.dependency_overrides[get_adapter_registry] = override_adapter_registry

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


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
    assert body["dataset_id"] == "demo-dataset"
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
