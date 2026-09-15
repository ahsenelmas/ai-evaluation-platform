import pytest

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)
from app.evaluators.deterministic.retrieval import (
    RetrievalPrecisionEvaluator,
    RetrievalRecallEvaluator,
)


def create_case() -> EvaluationCase:
    return EvaluationCase(
        id="ata-001",
        system="ata-rag",
        input={
            "question": "What programmes are offered?"
        },
        expected_output={
            "expected_source_ids": [
                "https://ata.test/programmes",
                "https://ata.test/admissions",
            ]
        },
    )


def create_execution() -> ApplicationExecution:
    return ApplicationExecution(
        case_id="ata-001",
        system="ata-rag",
        output={},
        retrieved_context=[
            {
                "url": "https://ata.test/programmes"
            },
            {
                "url": "https://ata.test/tuition"
            },
            {
                "url": "https://ata.test/admissions"
            },
        ],
    )


@pytest.mark.asyncio
async def test_recall_at_k_passes() -> None:
    evaluator = RetrievalRecallEvaluator(
        k=3,
        minimum_score=1.0,
    )

    result = await evaluator.evaluate(
        create_case(),
        create_execution(),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["missing_ids"] == []


@pytest.mark.asyncio
async def test_recall_at_k_detects_missing_source() -> None:
    evaluator = RetrievalRecallEvaluator(
        k=2,
        minimum_score=0.75,
    )

    result = await evaluator.evaluate(
        create_case(),
        create_execution(),
    )

    assert result.passed is False
    assert result.score == 0.5
    assert result.metadata["missing_ids"] == [
        "https://ata.test/admissions"
    ]


@pytest.mark.asyncio
async def test_precision_at_k_calculates_score() -> None:
    evaluator = RetrievalPrecisionEvaluator(
        k=3,
        minimum_score=0.6,
    )

    result = await evaluator.evaluate(
        create_case(),
        create_execution(),
    )

    assert result.passed is True
    assert result.score == 0.6667
    assert result.metadata["irrelevant_ids"] == [
        "https://ata.test/tuition"
    ]


@pytest.mark.asyncio
async def test_precision_fails_when_no_source_is_relevant() -> None:
    execution = ApplicationExecution(
        case_id="ata-001",
        system="ata-rag",
        output={},
        retrieved_context=[
            {
                "url": "https://ata.test/unrelated"
            }
        ],
    )

    evaluator = RetrievalPrecisionEvaluator(
        k=1,
        minimum_score=0.5,
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is False
    assert result.score == 0.0


def test_retrieval_evaluator_rejects_invalid_k() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        RetrievalRecallEvaluator(k=0)
