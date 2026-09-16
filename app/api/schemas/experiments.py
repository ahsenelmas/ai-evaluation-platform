from pydantic import BaseModel, Field

from app.api.schemas.evaluations import (
    EvaluatorRequest,
)


class RunExperimentRequest(BaseModel):
    name: str = Field(
        min_length=1,
        description="Human-readable experiment name.",
    )

    dataset_id: str = Field(
        min_length=1,
        description="Versioned dataset identifier.",
    )

    evaluators: list[EvaluatorRequest] = Field(
        min_length=1,
        description=("Evaluators executed for every dataset case."),
    )
