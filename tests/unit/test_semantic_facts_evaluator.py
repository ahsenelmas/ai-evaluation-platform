import json

import httpx
import pytest

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)
from app.evaluators.llm_judges.semantic_facts import (
    SemanticFactsEvaluator,
    parse_json_response,
)


def create_case() -> EvaluationCase:
    return EvaluationCase(
        id="semantic-001",
        system="ata-rag",
        input={
            "question": "What programmes does ATA offer?"
        },
        expected_output={
            "expected_answer_facts": [
                "ATA offers Architecture.",
                "ATA offers Design.",
            ]
        },
    )


def create_execution() -> ApplicationExecution:
    return ApplicationExecution(
        case_id="semantic-001",
        system="ata-rag",
        output={
            "answer": (
                "ATA offers Architecture and several "
                "other programmes."
            )
        },
    )


def create_evaluator(
    transport: httpx.AsyncBaseTransport,
    minimum_score: float = 1.0,
) -> SemanticFactsEvaluator:
    return SemanticFactsEvaluator(
        base_url="https://judge.test/v1",
        api_key="test-key",
        model="test-model",
        minimum_score=minimum_score,
        transport=transport,
    )


def test_parse_json_response_removes_code_fence() -> None:
    parsed = parse_json_response(
        '```json\n{"fact_results": []}\n```'
    )

    assert parsed == {"fact_results": []}


@pytest.mark.asyncio
async def test_semantic_facts_calculates_score() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.headers["authorization"] == (
            "Bearer test-key"
        )

        request_body = json.loads(
            request.content.decode("utf-8")
        )

        assert request_body["model"] == "test-model"

        response_content = {
            "fact_results": [
                {
                    "supported": True,
                    "reason": "Architecture is mentioned.",
                },
                {
                    "supported": False,
                    "reason": "Design is not mentioned.",
                },
            ],
            "reason": "The answer contains one of two facts.",
        }

        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                response_content
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 20,
                    "total_tokens": 60,
                },
            },
        )

    evaluator = create_evaluator(
        httpx.MockTransport(handler)
    )

    result = await evaluator.evaluate(
        create_case(),
        create_execution(),
    )

    assert result.passed is False
    assert result.score == 0.5
    assert result.metadata["matched_facts"] == [
        "ATA offers Architecture."
    ]
    assert result.metadata["missing_facts"] == [
        "ATA offers Design."
    ]
    assert result.metadata["judge_token_usage"] == {
        "input_tokens": 40,
        "output_tokens": 20,
        "total_tokens": 60,
    }


@pytest.mark.asyncio
async def test_semantic_facts_passes_at_threshold() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        del request

        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "fact_results": [
                                        {
                                            "supported": True,
                                            "reason": "Matched.",
                                        },
                                        {
                                            "supported": False,
                                            "reason": "Missing.",
                                        },
                                    ],
                                    "reason": "Partial match.",
                                }
                            )
                        }
                    }
                ]
            },
        )

    evaluator = create_evaluator(
        httpx.MockTransport(handler),
        minimum_score=0.5,
    )

    result = await evaluator.evaluate(
        create_case(),
        create_execution(),
    )

    assert result.passed is True
    assert result.score == 0.5


@pytest.mark.asyncio
async def test_semantic_facts_handles_invalid_response() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        del request

        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "not-json"
                        }
                    }
                ]
            },
        )

    evaluator = create_evaluator(
        httpx.MockTransport(handler)
    )

    result = await evaluator.evaluate(
        create_case(),
        create_execution(),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.metadata["judge_error"] is True
    assert "valid JSON" in result.reason


@pytest.mark.asyncio
async def test_semantic_facts_rejects_missing_answer() -> None:
    evaluator = create_evaluator(
        httpx.MockTransport(
            lambda request: httpx.Response(
                status_code=500
            )
        )
    )

    execution = ApplicationExecution(
        case_id="semantic-001",
        system="ata-rag",
        output={},
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "valid 'answer'" in result.reason


@pytest.mark.asyncio
async def test_semantic_facts_passes_without_expected_facts() -> None:
    evaluator = create_evaluator(
        httpx.MockTransport(
            lambda request: httpx.Response(
                status_code=500
            )
        )
    )

    case = EvaluationCase(
        id="semantic-empty",
        system="ata-rag",
        input={},
        expected_output={
            "expected_answer_facts": []
        },
    )

    result = await evaluator.evaluate(
        case,
        create_execution(),
    )

    assert result.passed is True
    assert result.score == 1.0
