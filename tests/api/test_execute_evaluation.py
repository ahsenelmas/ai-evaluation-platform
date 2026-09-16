from fastapi.testclient import TestClient

from app.adapters.base import ApplicationAdapter
from app.adapters.registry import AdapterRegistry
from app.api.routes.evaluations import (
    get_adapter_registry,
)
from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)
from app.main import app

client = TestClient(app)


class FakeAtaAdapter(ApplicationAdapter):
    system = "ata-rag"

    async def execute(
        self,
        case: EvaluationCase,
    ) -> ApplicationExecution:
        self.validate_case(case)

        return ApplicationExecution(
            case_id=case.id,
            system=self.system,
            output={
                "answer": ("ATA offers technical and artistic programmes."),
                "language": "en",
                "grounded": True,
                "sources": [{"url": ("https://akademiata.edu.pl/programmes")}],
            },
            success=True,
            latency_ms=350,
            prompt_version="ata-rag-v1",
            application_version="1.0.0",
        )


def override_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(FakeAtaAdapter())
    return registry


def create_payload() -> dict:
    return {
        "case": {
            "id": "ata-001",
            "system": "ata-rag",
            "input": {
                "question": ("What programmes does ATA offer?"),
                "language": "en",
            },
            "expected_output": {"grounded": True},
            "metadata": {"category": "programmes"},
        },
        "evaluators": [
            {"name": "exact_match", "settings": {"field_name": "grounded"}},
            {
                "name": "required_fields",
                "settings": {"required_fields": ["answer", "sources"]},
            },
            {"name": "latency", "settings": {"max_latency_ms": 1000}},
        ],
    }


def test_execute_endpoint_runs_full_flow() -> None:
    app.dependency_overrides[get_adapter_registry] = override_adapter_registry

    try:
        response = client.post(
            "/api/v1/evaluations/execute",
            json=create_payload(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    data = response.json()

    assert data["execution"]["success"] is True
    assert data["evaluation"]["passed"] is True
    assert data["evaluation"]["aggregate_score"] == 1.0
    assert data["evaluation"]["evaluator_count"] == 3


def test_execute_endpoint_rejects_unknown_system() -> None:
    app.dependency_overrides[get_adapter_registry] = override_adapter_registry

    payload = create_payload()
    payload["case"]["system"] = "unknown-system"

    try:
        response = client.post(
            "/api/v1/evaluations/execute",
            json=payload,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "Unknown AI system" in (response.json()["detail"])
