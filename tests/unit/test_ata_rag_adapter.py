import httpx
import pytest

from app.adapters.ata_rag import AtaRagAdapter
from app.domain.models import EvaluationCase


def create_case() -> EvaluationCase:
    return EvaluationCase(
        id="ata-001",
        system="ata-rag",
        input={
            "question": ("What programmes does ATA offer?"),
            "language": "en",
            "retrieval_limit": 5,
        },
        expected_output={},
    )


@pytest.mark.asyncio
async def test_ata_adapter_returns_execution() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == "/api/chat"

        return httpx.Response(
            status_code=200,
            json={
                "message_id": ("58d8efbf-81fc-44fe-aa2f-2c45ddcb63cb"),
                "session_id": ("839fe284-888f-432f-8318-93ee6f4db194"),
                "answer": ("ATA offers several technical and artistic programmes."),
                "language": "en",
                "grounded": True,
                "sources": [
                    {
                        "title": "Study Programmes",
                        "section": "Programmes",
                        "url": ("https://akademiata.edu.pl/programmes"),
                        "similarity": 0.85,
                        "final_score": 0.91,
                    }
                ],
                "token_usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                },
                "estimated_cost": 0.001,
                "model": "test-model",
                "prompt_version": "ata-rag-v1",
                "application_version": "1.0.0",
            },
        )

    adapter = AtaRagAdapter(
        base_url="http://ata-rag.test",
        transport=httpx.MockTransport(handler),
    )

    execution = await adapter.execute(create_case())

    assert execution.success is True
    assert execution.output["grounded"] is True
    assert len(execution.retrieved_context) == 1
    assert execution.token_usage.total_tokens == 120
    assert execution.model == "test-model"


@pytest.mark.asyncio
async def test_ata_adapter_handles_http_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=503,
            json={"detail": "Service unavailable"},
        )

    adapter = AtaRagAdapter(
        base_url="http://ata-rag.test",
        transport=httpx.MockTransport(handler),
    )

    execution = await adapter.execute(create_case())

    assert execution.success is False
    assert execution.error is not None
    assert "503" in execution.error


@pytest.mark.asyncio
async def test_ata_adapter_rejects_missing_question() -> None:
    case = EvaluationCase(
        id="ata-002",
        system="ata-rag",
        input={},
        expected_output={},
    )

    adapter = AtaRagAdapter(
        base_url="http://ata-rag.test",
    )

    execution = await adapter.execute(case)

    assert execution.success is False
    assert execution.error is not None
    assert "question" in execution.error


@pytest.mark.asyncio
async def test_ata_adapter_rejects_wrong_system() -> None:
    case = EvaluationCase(
        id="wrong-001",
        system="internship-coordinator",
        input={},
        expected_output={},
    )

    adapter = AtaRagAdapter(
        base_url="http://ata-rag.test",
    )

    with pytest.raises(
        ValueError,
        match="cannot execute",
    ):
        await adapter.execute(case)
