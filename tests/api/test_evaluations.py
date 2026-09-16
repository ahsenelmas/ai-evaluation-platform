from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_payload(
    actual_recommendation: str = "APPROVE",
) -> dict:
    return {
        "case": {
            "id": "internship-001",
            "system": "internship-coordinator",
            "input": {"documents": ["application.pdf"]},
            "expected_output": {"recommendation": "APPROVE"},
            "metadata": {"category": "valid-application"},
        },
        "execution": {
            "case_id": "internship-001",
            "system": "internship-coordinator",
            "output": {"recommendation": actual_recommendation},
        },
        "evaluators": [
            {"name": "exact_match", "settings": {"field_name": "recommendation"}}
        ],
    }


def test_run_evaluation_returns_pass() -> None:
    response = client.post(
        "/api/v1/evaluations/run",
        json=create_payload(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["passed"] is True
    assert data["aggregate_score"] == 1.0
    assert data["evaluator_count"] == 1


def test_run_evaluation_returns_failure() -> None:
    response = client.post(
        "/api/v1/evaluations/run",
        json=create_payload(
            actual_recommendation=("REQUEST_CLARIFICATION"),
        ),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["passed"] is False
    assert data["aggregate_score"] == 0.0
    assert data["failed_count"] == 1


def test_unknown_evaluator_returns_422() -> None:
    payload = create_payload()

    payload["evaluators"][0]["name"] = "unknown_evaluator"

    response = client.post(
        "/api/v1/evaluations/run",
        json=payload,
    )

    assert response.status_code == 422
    assert "Unknown evaluator" in response.json()["detail"]
