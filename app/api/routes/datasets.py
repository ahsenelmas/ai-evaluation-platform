from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.core.config import get_settings
from app.domain.models import (
    DatasetManifestEntry,
    EvaluationDataset,
)
from app.services.dataset_service import (
    DatasetNotFoundError,
    DatasetService,
)

router = APIRouter(
    prefix="/datasets",
    tags=["datasets"],
)


def get_dataset_service() -> DatasetService:
    settings = get_settings()

    return DatasetService(dataset_root=settings.dataset_root)


@router.get(
    "",
    response_model=list[DatasetManifestEntry],
)
def list_datasets(
    service: Annotated[
        DatasetService,
        Depends(get_dataset_service),
    ],
) -> list[DatasetManifestEntry]:
    try:
        return service.list_datasets()

    except ValueError as error:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail=str(error),
        ) from error


@router.get(
    "/{dataset_id}",
    response_model=EvaluationDataset,
)
def get_dataset(
    dataset_id: str,
    service: Annotated[
        DatasetService,
        Depends(get_dataset_service),
    ],
) -> EvaluationDataset:
    try:
        return service.get_dataset(dataset_id)

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
