from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)
from app.evaluators.base import Evaluator


class SecurityFlagMatchEvaluator(Evaluator):
    """Compare a Coordinator security finding to its labeled boolean."""

    name = "security_flag_match"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        expected = case.expected_output.get("security_flag")
        actual = execution.output.get("security_flag")
        valid = isinstance(expected, bool) and isinstance(actual, bool)
        passed = valid and expected == actual

        if not valid:
            reason = "Both expected and actual security_flag must be booleans."
        elif passed:
            reason = "Security flag matches the expected value."
        else:
            reason = f"Security flag differs: expected {expected}, received {actual}."

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=1.0 if passed else 0.0,
            value=passed,
            passed=passed,
            reason=reason,
            metadata={"expected": expected, "actual": actual},
        )


class MissingFieldsMatchEvaluator(Evaluator):
    """Compare missing field names regardless of their order."""

    name = "missing_fields_match"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        expected = case.expected_output.get("missing_fields")
        actual = execution.output.get("missing_fields")
        valid = all(
            isinstance(fields, list)
            and all(isinstance(field, str) and field for field in fields)
            for fields in (expected, actual)
        )

        if valid:
            expected_sorted = sorted(expected)
            actual_sorted = sorted(actual)
            passed = expected_sorted == actual_sorted
            missing = sorted(set(expected) - set(actual))
            unexpected = sorted(set(actual) - set(expected))
            reason = (
                "Missing field names match the expected labels."
                if passed
                else (
                    f"Missing field names differ: expected {expected_sorted}, "
                    f"received {actual_sorted}."
                )
            )
        else:
            passed = False
            missing = []
            unexpected = []
            reason = (
                "Both expected and actual missing_fields must be lists of field names."
            )

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=1.0 if passed else 0.0,
            value=passed,
            passed=passed,
            reason=reason,
            metadata={
                "expected": expected,
                "actual": actual,
                "absent": missing,
                "unexpected": unexpected,
            },
        )
