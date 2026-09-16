from functools import lru_cache
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
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
from app.core.config import get_settings
from app.domain.models import ExperimentReport
from app.engine.experiment_runner import (
    ExperimentRunner,
)
from app.integrations.langfuse_client import (
    LangfuseExperimentPublisher,
)
from app.repositories.experiment_repository import (
    ExperimentNotFoundError,
    FileExperimentRepository,
)
from app.services.dataset_service import (
    DatasetNotFoundError,
    DatasetService,
)

router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
)


@lru_cache
def get_experiment_repository() -> FileExperimentRepository:
    settings = get_settings()

    return FileExperimentRepository(storage_root=(settings.experiment_storage_root))


@lru_cache
def get_langfuse_publisher() -> LangfuseExperimentPublisher:
    return LangfuseExperimentPublisher.from_settings(get_settings())


@router.get(
    "",
    response_model=list[ExperimentReport],
)
def list_experiments(
    repository: Annotated[
        FileExperimentRepository,
        Depends(get_experiment_repository),
    ],
) -> list[ExperimentReport]:
    try:
        return repository.list_reports()

    except ValueError as error:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail=str(error),
        ) from error


@router.get(
    "/{experiment_id}",
    response_model=ExperimentReport,
)
def get_experiment(
    experiment_id: str,
    repository: Annotated[
        FileExperimentRepository,
        Depends(get_experiment_repository),
    ],
) -> ExperimentReport:
    try:
        return repository.get(experiment_id)

    except ExperimentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail=str(error),
        ) from error


@router.post(
    "/run",
    response_model=ExperimentReport,
)
async def run_experiment(
    payload: RunExperimentRequest,
    background_tasks: BackgroundTasks,
    dataset_service: Annotated[
        DatasetService,
        Depends(get_dataset_service),
    ],
    adapter_registry: Annotated[
        AdapterRegistry,
        Depends(get_adapter_registry),
    ],
    repository: Annotated[
        FileExperimentRepository,
        Depends(get_experiment_repository),
    ],
    langfuse_publisher: Annotated[
        LangfuseExperimentPublisher,
        Depends(get_langfuse_publisher),
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

        report = await runner.run(
            name=payload.name,
            dataset=dataset,
        )

        saved_report = repository.save(report)

        background_tasks.add_task(
            langfuse_publisher.publish,
            saved_report,
        )

        return saved_report

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
