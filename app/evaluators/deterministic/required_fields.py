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
    version = "1.1.0"

    def __init__(
        self,
        required_fields: list[str],
        allow_empty_fields: list[str] | None = None,
    ) -> None:
        cleaned_fields = [
            field.strip()
            for field in required_fields
            if isinstance(field, str) and field.strip()
        ]

        if not cleaned_fields:
            raise ValueError("At least one required field must be provided.")

        self.required_fields = list(dict.fromkeys(cleaned_fields))

        cleaned_allowed_fields = [
            field.strip()
            for field in (allow_empty_fields or [])
            if isinstance(field, str) and field.strip()
        ]

        self.allow_empty_fields = list(
            dict.fromkeys(cleaned_allowed_fields)
        )

        unknown_fields = sorted(
            set(self.allow_empty_fields) - set(self.required_fields)
        )

        if unknown_fields:
            raise ValueError(
                "Fields allowed to be empty must also be required fields: "
                + ", ".join(unknown_fields)
            )

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        del case

        missing_fields: list[str] = []
        empty_fields: list[str] = []
        present_fields: list[str] = []

        for field_path in self.required_fields:
            found, value = get_nested_value(
                execution.output,
                field_path,
            )

            if not found:
                missing_fields.append(field_path)
                continue

            if (
                is_empty_value(value)
                and field_path not in self.allow_empty_fields
            ):
                empty_fields.append(field_path)
                continue

            present_fields.append(field_path)

        failed_fields = missing_fields + empty_fields
        score = len(present_fields) / len(self.required_fields)
        passed = not failed_fields

        if passed:
            reason = "All required output fields are present."
        else:
            problems: list[str] = []

            if missing_fields:
                problems.append(
                    "missing fields: " + ", ".join(missing_fields)
                )

            if empty_fields:
                problems.append(
                    "empty fields: " + ", ".join(empty_fields)
                )

            reason = "Required-field validation failed; " + "; ".join(
                problems
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
                "allow_empty_fields": self.allow_empty_fields,
                "present_fields": present_fields,
                "missing_fields": missing_fields,
                "empty_fields": empty_fields,
            },
        )
