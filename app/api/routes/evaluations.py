from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.adapters.registry import (
    AdapterRegistry,
    build_default_adapter_registry,
)
from app.api.schemas.evaluations import (
    EvaluatorRequest,
    ExecuteEvaluationRequest,
    ExecuteEvaluationResponse,
    RunEvaluationRequest,
)
from app.domain.models import CaseEvaluationReport
from app.engine.runner import EvaluationRunner
from app.evaluators.base import Evaluator
from app.evaluators.registry import (
    build_default_registry,
)

router = APIRouter(
    prefix="/evaluations",
    tags=["evaluations"],
)


def get_adapter_registry() -> AdapterRegistry:
    return build_default_adapter_registry()


def create_evaluators(
    requests: list[EvaluatorRequest],
) -> list[Evaluator]:
    registry = build_default_registry()

    return [
        registry.create(
            request.name,
            request.settings,
        )
        for request in requests
    ]


@router.post(
    "/run",
    response_model=CaseEvaluationReport,
)
async def run_evaluation(
    payload: RunEvaluationRequest,
) -> CaseEvaluationReport:
    try:
        evaluators = create_evaluators(
            payload.evaluators
        )

        runner = EvaluationRunner(
            evaluators=evaluators,
        )

        return await runner.run_case(
            case=payload.case,
            execution=payload.execution,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(error),
        ) from error


@router.post(
    "/execute",
    response_model=ExecuteEvaluationResponse,
)
async def execute_and_evaluate(
    payload: ExecuteEvaluationRequest,
    adapter_registry: Annotated[
        AdapterRegistry,
        Depends(get_adapter_registry),
    ],
) -> ExecuteEvaluationResponse:
    try:
        adapter = adapter_registry.get(
            payload.case.system
        )

        execution = await adapter.execute(
            payload.case
        )

        evaluators = create_evaluators(
            payload.evaluators
        )

        runner = EvaluationRunner(
            evaluators=evaluators,
        )

        evaluation = await runner.run_case(
            case=payload.case,
            execution=execution,
        )

        return ExecuteEvaluationResponse(
            execution=execution,
            evaluation=evaluation,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(error),
        ) from error
