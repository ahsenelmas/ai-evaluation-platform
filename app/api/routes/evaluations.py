from fastapi import APIRouter, HTTPException, status

from app.api.schemas.evaluations import (
    RunEvaluationRequest,
)
from app.domain.models import CaseEvaluationReport
from app.engine.runner import EvaluationRunner
from app.evaluators.registry import (
    build_default_registry,
)

router = APIRouter(
    prefix="/evaluations",
    tags=["evaluations"],
)


@router.post(
    "/run",
    response_model=CaseEvaluationReport,
)
async def run_evaluation(
    payload: RunEvaluationRequest,
) -> CaseEvaluationReport:
    registry = build_default_registry()

    try:
        evaluators = [
            registry.create(
                evaluator.name,
                evaluator.settings,
            )
            for evaluator in payload.evaluators
        ]

        runner = EvaluationRunner(
            evaluators=evaluators,
        )

        return await runner.run_case(
            case=payload.case,
            execution=payload.execution,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
