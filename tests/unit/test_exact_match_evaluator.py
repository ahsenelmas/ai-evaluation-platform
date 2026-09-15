import pytest

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)
from app.evaluators.deterministic.exact_match import (
    ExactMatchEvaluator,
)


def create_case() -> EvaluationCase:
    return EvaluationCase(
        id="internship-001",
        system="internship-coordinator",
        input={
            "documents": ["application.pdf"],
        },
        expected_output={
            "recommendation": "APPROVE",
        },
        metadata={
            "category": "valid-application",
        },
    )


@pytest.mark.asyncio
async def test_exact_match_passes_for_equal_values() -> None:
    evaluator = ExactMatchEvaluator(
        field_name="recommendation",
    )

    execution = ApplicationExecution(
        case_id="internship-001",
        system="internship-coordinator",
        output={
            "recommendation": "APPROVE",
        },
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.value is True


@pytest.mark.asyncio
async def test_exact_match_fails_for_different_values() -> None:
    evaluator = ExactMatchEvaluator(
        field_name="recommendation",
    )

    execution = ApplicationExecution(
        case_id="internship-001",
        system="internship-coordinator",
        output={
            "recommendation": "REQUEST_CLARIFICATION",
        },
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.value is False


@pytest.mark.asyncio
async def test_exact_match_reports_missing_expected_field() -> None:
    evaluator = ExactMatchEvaluator(
        field_name="decision",
    )

    execution = ApplicationExecution(
        case_id="internship-001",
        system="internship-coordinator",
        output={},
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "missing" in result.reason.lower()
