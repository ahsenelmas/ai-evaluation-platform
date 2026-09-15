from typing import Any

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)
from app.evaluators.base import Evaluator


def get_nested_value(
    data: dict[str, Any],
    field_path: str,
) -> tuple[bool, Any]:
    current: Any = data

    for part in field_path.split("."):
        if not isinstance(current, dict):
            return False, None

        if part not in current:
            return False, None

        current = current[part]

    return True, current


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0

    return False


class RequiredFieldsEvaluator(Evaluator):
    name = "required_fields"
    version = "1.0.0"

    def __init__(
        self,
        required_fields: list[str],
    ) -> None:
        cleaned_fields = [
            field.strip()
            for field in required_fields
            if field.strip()
        ]

        if not cleaned_fields:
            raise ValueError(
                "At least one required field must be provided."
            )

        self.required_fields = list(
            dict.fromkeys(cleaned_fields)
        )

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        del case

        missing_fields: list[str] = []
        present_fields: list[str] = []

        for field_path in self.required_fields:
            found, value = get_nested_value(
                execution.output,
                field_path,
            )

            if not found or is_empty_value(value):
                missing_fields.append(field_path)
            else:
                present_fields.append(field_path)

        score = len(present_fields) / len(
            self.required_fields
        )

        passed = not missing_fields

        if passed:
            reason = "All required output fields are present."
        else:
            reason = (
                "Missing or empty required fields: "
                + ", ".join(missing_fields)
            )

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=round(score, 4),
            value=passed,
            passed=passed,
            reason=reason,
            metadata={
                "required_fields": self.required_fields,
                "present_fields": present_fields,
                "missing_fields": missing_fields,
            },
        )
