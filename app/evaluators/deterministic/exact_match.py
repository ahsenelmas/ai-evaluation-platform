from typing import Any

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)
from app.evaluators.base import Evaluator


class ExactMatchEvaluator(Evaluator):
    name = "exact_match"
    version = "1.0.0"

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        expected: Any = case.expected_output.get(self.field_name)
        actual: Any = execution.output.get(self.field_name)

        if self.field_name not in case.expected_output:
            return EvaluationResult(
                evaluator=self.name,
                evaluator_version=self.version,
                score=0.0,
                passed=False,
                reason=(
                    f"Expected field '{self.field_name}' "
                    "is missing from the evaluation case."
                ),
                metadata={
                    "field_name": self.field_name,
                    "expected": None,
                    "actual": actual,
                },
            )

        passed = actual == expected

        if passed:
            reason = f"Field '{self.field_name}' exactly matches the expected value."
        else:
            reason = (
                f"Field '{self.field_name}' does not match. "
                f"Expected {expected!r}, received {actual!r}."
            )

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=1.0 if passed else 0.0,
            value=passed,
            passed=passed,
            reason=reason,
            metadata={
                "field_name": self.field_name,
                "expected": expected,
                "actual": actual,
            },
        )
