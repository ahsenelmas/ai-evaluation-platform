import pytest

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)
from app.evaluators.deterministic.required_fields import (
    RequiredFieldsEvaluator,
)


def create_case() -> EvaluationCase:
    return EvaluationCase(
        id="case-001",
        system="test-system",
        input={},
        expected_output={},
    )


@pytest.mark.asyncio
async def test_required_fields_passes() -> None:
    evaluator = RequiredFieldsEvaluator(
        required_fields=[
            "recommendation",
            "extracted_fields.student_name",
        ]
    )

    execution = ApplicationExecution(
        case_id="case-001",
        system="test-system",
        output={
            "recommendation": "APPROVE",
            "extracted_fields": {
                "student_name": "Test Student"
            },
        },
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["missing_fields"] == []
    assert result.metadata["empty_fields"] == []


@pytest.mark.asyncio
async def test_required_fields_detects_missing_field() -> None:
    evaluator = RequiredFieldsEvaluator(
        required_fields=[
            "recommendation",
            "extracted_fields.student_name",
        ]
    )

    execution = ApplicationExecution(
        case_id="case-001",
        system="test-system",
        output={
            "recommendation": "APPROVE",
            "extracted_fields": {},
        },
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is False
    assert result.score == 0.5
    assert result.metadata["missing_fields"] == [
        "extracted_fields.student_name"
    ]
    assert result.metadata["empty_fields"] == []


@pytest.mark.asyncio
async def test_required_fields_rejects_empty_value() -> None:
    evaluator = RequiredFieldsEvaluator(
        required_fields=[
            "answer",
            "sources",
        ]
    )

    execution = ApplicationExecution(
        case_id="case-001",
        system="test-system",
        output={
            "answer": "No relevant information was found.",
            "sources": [],
        },
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is False
    assert result.score == 0.5
    assert result.metadata["missing_fields"] == []
    assert result.metadata["empty_fields"] == ["sources"]


@pytest.mark.asyncio
async def test_required_fields_allows_configured_empty_value() -> None:
    evaluator = RequiredFieldsEvaluator(
        required_fields=[
            "answer",
            "grounded",
            "sources",
        ],
        allow_empty_fields=["sources"],
    )

    execution = ApplicationExecution(
        case_id="case-001",
        system="test-system",
        output={
            "answer": "The question is outside the knowledge base.",
            "grounded": False,
            "sources": [],
        },
    )

    result = await evaluator.evaluate(
        create_case(),
        execution,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["present_fields"] == [
        "answer",
        "grounded",
        "sources",
    ]


def test_required_fields_rejects_unknown_allowed_field() -> None:
    with pytest.raises(
        ValueError,
        match="must also be required fields",
    ):
        RequiredFieldsEvaluator(
            required_fields=["answer"],
            allow_empty_fields=["sources"],
        )


def test_required_fields_rejects_empty_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="At least one required field",
    ):
        RequiredFieldsEvaluator(required_fields=[])
