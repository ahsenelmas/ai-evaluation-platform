from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import (
    ApplicationExecution,
    CaseEvaluationReport,
    EvaluationCase,
)


class EvaluatorRequest(BaseModel):
    name: str = Field(
        min_length=1,
        description="Registered evaluator name.",
    )

    settings: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Evaluator-specific configuration."
        ),
    )


class RunEvaluationRequest(BaseModel):
    case: EvaluationCase
    execution: ApplicationExecution

    evaluators: list[EvaluatorRequest] = Field(
        min_length=1,
        description=(
            "Evaluators executed for this case."
        ),
    )


class ExecuteEvaluationRequest(BaseModel):
    case: EvaluationCase

    evaluators: list[EvaluatorRequest] = Field(
        min_length=1,
        description=(
            "Evaluators executed after the "
            "application responds."
        ),
    )


class ExecuteEvaluationResponse(BaseModel):
    execution: ApplicationExecution
    evaluation: CaseEvaluationReport
