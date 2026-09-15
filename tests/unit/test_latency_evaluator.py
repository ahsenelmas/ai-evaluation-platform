import pytest

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)
from app.evaluators.deterministic.latency import (
    LatencyEvaluator,
)


def create_case() -> EvaluationCase:
    return EvaluationCase(
        id="case-001",
        system="test-system",
        input={},
        expected_output={},
    )


@pytest.mark.asyncio
async def test_latency_passes_under_limit() -> None:
    evaluator = LatencyEvaluator(
        max_latency_ms=1000
    )

    execution = ApplicationExecution(
        case_id="case-001",
        system="test-system",
        output={},
        latency_ms=750,
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is True
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_latency_fails_over_limit() -> None:
    evaluator = LatencyEvaluator(
        max_latency_ms=1000
    )

    execution = ApplicationExecution(
        case_id="case-001",
        system="test-system",
        output={},
        latency_ms=1250,
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.metadata["exceeded_by_ms"] == 250


def test_latency_rejects_invalid_limit() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        LatencyEvaluator(
            max_latency_ms=0
        )
