import pytest

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)
from app.engine.runner import EvaluationRunner
from app.evaluators.base import Evaluator
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
            "status": "RECOMMENDATION_READY",
        },
    )


def create_execution(
    recommendation: str = "APPROVE",
) -> ApplicationExecution:
    return ApplicationExecution(
        case_id="internship-001",
        system="internship-coordinator",
        output={
            "recommendation": recommendation,
            "status": "RECOMMENDATION_READY",
        },
    )


@pytest.mark.asyncio
async def test_runner_passes_when_all_evaluators_pass() -> None:
    runner = EvaluationRunner(
        evaluators=[
            ExactMatchEvaluator("recommendation"),
            ExactMatchEvaluator("status"),
        ]
    )

    report = await runner.run_case(
        create_case(),
        create_execution(),
    )

    assert report.passed is True
    assert report.aggregate_score == 1.0
    assert report.evaluator_count == 2
    assert report.passed_count == 2
    assert report.failed_count == 0


@pytest.mark.asyncio
async def test_runner_calculates_score_when_one_evaluator_fails() -> None:
    runner = EvaluationRunner(
        evaluators=[
            ExactMatchEvaluator("recommendation"),
            ExactMatchEvaluator("status"),
        ]
    )

    report = await runner.run_case(
        create_case(),
        create_execution(
            recommendation="REQUEST_CLARIFICATION",
        ),
    )

    assert report.passed is False
    assert report.aggregate_score == 0.5
    assert report.passed_count == 1
    assert report.failed_count == 1


def test_runner_rejects_empty_evaluator_list() -> None:
    with pytest.raises(
        ValueError,
        match="At least one evaluator",
    ):
        EvaluationRunner(evaluators=[])


@pytest.mark.asyncio
async def test_runner_rejects_mismatched_case_id() -> None:
    runner = EvaluationRunner(
        evaluators=[
            ExactMatchEvaluator("recommendation"),
        ]
    )

    execution = create_execution()
    execution.case_id = "different-case"

    with pytest.raises(
        ValueError,
        match="case ID",
    ):
        await runner.run_case(
            create_case(),
            execution,
        )


class BrokenEvaluator(Evaluator):
    name = "broken_evaluator"
    version = "1.0.0"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        raise RuntimeError("Simulated evaluator failure")


@pytest.mark.asyncio
async def test_runner_captures_evaluator_errors() -> None:
    runner = EvaluationRunner(
        evaluators=[
            BrokenEvaluator(),
        ]
    )

    report = await runner.run_case(
        create_case(),
        create_execution(),
    )

    assert report.passed is False
    assert report.aggregate_score == 0.0
    assert report.failed_count == 1
    assert report.results[0].metadata["evaluator_error"] is True
    assert "Simulated evaluator failure" in report.results[0].reason
