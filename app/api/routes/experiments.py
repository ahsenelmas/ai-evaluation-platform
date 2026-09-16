from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.adapters.registry import AdapterRegistry
from app.api.routes.datasets import (
    get_dataset_service,
)
from app.api.routes.evaluations import (
    create_evaluators,
    get_adapter_registry,
)
from app.api.schemas.experiments import (
    RunExperimentRequest,
)
from app.domain.models import ExperimentReport
from app.engine.experiment_runner import (
    ExperimentRunner,
)
from app.services.dataset_service import (
    DatasetNotFoundError,
    DatasetService,
)

router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
)


@router.post(
    "/run",
    response_model=ExperimentReport,
)
async def run_experiment(
    payload: RunExperimentRequest,
    dataset_service: Annotated[
        DatasetService,
        Depends(get_dataset_service),
    ],
    adapter_registry: Annotated[
        AdapterRegistry,
        Depends(get_adapter_registry),
    ],
) -> ExperimentReport:
    try:
        dataset = dataset_service.get_dataset(payload.dataset_id)

        adapter = adapter_registry.get(dataset.metadata.system)

        evaluators = create_evaluators(payload.evaluators)

        runner = ExperimentRunner(
            adapter=adapter,
            evaluators=evaluators,
        )

        return await runner.run(
            name=payload.name,
            dataset=dataset,
        )

    except DatasetNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail=str(error),
        ) from error
