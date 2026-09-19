import json

import httpx
import pytest

from dashboard.api_client import APIError, EvaluationAPI


def test_comparison_uses_get_and_correct_query_parameters() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/experiments/compare"
        assert request.url.params["baseline_id"] == "exp-old"
        assert request.url.params["candidate_id"] == "exp-new"
        assert request.url.params["score_tolerance"] == "0.02"
        return httpx.Response(200, json={"regression_detected": False})

    api = EvaluationAPI(
        "http://127.0.0.1:8100/",
        transport=httpx.MockTransport(respond),
    )

    result = api.compare("exp-old", "exp-new", score_tolerance=0.02)

    assert result["regression_detected"] is False


def test_run_uses_post_with_request_payload() -> None:
    payload = {
        "name": "baseline",
        "dataset_id": "ata-rag-golden-v1",
        "evaluators": [{"name": "exact_match", "settings": {"field_name": "grounded"}}],
    }

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/experiments/run"
        assert json.loads(request.read()) == payload
        return httpx.Response(200, json={"experiment_id": "exp-1"})

    api = EvaluationAPI("http://127.0.0.1:8100", transport=httpx.MockTransport(respond))
    assert api.run(payload)["experiment_id"] == "exp-1"


def test_api_error_includes_server_detail() -> None:
    api = EvaluationAPI(
        "http://127.0.0.1:8100",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(422, json={"detail": "Unknown evaluator"})
        ),
    )
    with pytest.raises(APIError, match="Unknown evaluator"):
        api.run({"name": "invalid"})
