from collections.abc import Sequence

from app.domain.models import (
    ApplicationExecution,
    CaseEvaluationReport,
    EvaluationCase,
    EvaluationResult,
)
from app.evaluators.base import Evaluator


class EvaluationRunner:
    def __init__(
        self,
        evaluators: Sequence[Evaluator],
    ) -> None:
        if not evaluators:
            raise ValueError("At least one evaluator is required.")

        self.evaluators = list(evaluators)

    async def run_case(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> CaseEvaluationReport:
        if case.id != execution.case_id:
            raise ValueError("Evaluation case ID and execution case ID do not match.")

        if case.system != execution.system:
            raise ValueError(
                "Evaluation case system and execution system do not match."
            )

        results: list[EvaluationResult] = []

        for evaluator in self.evaluators:
            try:
                result = await evaluator.evaluate(
                    case,
                    execution,
                )
            except Exception as error:
                result = EvaluationResult(
                    evaluator=evaluator.name,
                    evaluator_version=evaluator.version,
                    score=0.0,
                    passed=False,
                    reason=(f"Evaluator failed with {type(error).__name__}: {error}"),
                    metadata={
                        "evaluator_error": True,
                        "error_type": type(error).__name__,
                    },
                )

            results.append(result)

        numerical_scores = [
            result.score for result in results if result.score is not None
        ]

        aggregate_score = (
            sum(numerical_scores) / len(numerical_scores) if numerical_scores else 0.0
        )

        passed_count = sum(1 for result in results if result.passed)

        failed_count = len(results) - passed_count

        return CaseEvaluationReport(
            case_id=case.id,
            system=case.system,
            passed=failed_count == 0,
            aggregate_score=round(
                aggregate_score,
                4,
            ),
            evaluator_count=len(results),
            passed_count=passed_count,
            failed_count=failed_count,
            results=results,
        )
