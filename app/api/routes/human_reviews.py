"""Human assessments attached to a saved experiment and case."""

from functools import lru_cache
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.experiments import get_experiment_repository
from app.api.schemas.human_reviews import CreateHumanReviewRequest
from app.core.config import get_settings
from app.domain.models import HumanReview
from app.repositories.experiment_repository import (
    ExperimentNotFoundError,
    FileExperimentRepository,
)
from app.repositories.human_review_repository import FileHumanReviewRepository

router = APIRouter(
    prefix="/experiments/{experiment_id}/cases/{case_id}/reviews",
    tags=["human reviews"],
)


@lru_cache
def get_human_review_repository() -> FileHumanReviewRepository:
    return FileHumanReviewRepository(get_settings().experiment_storage_root)


def check_case(
    experiment_id: str,
    case_id: str,
    repository: FileExperimentRepository,
) -> None:
    try:
        report = repository.get(experiment_id)
    except ExperimentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if not any(case.case_id == case_id for case in report.cases):
        raise HTTPException(
            status_code=404,
            detail=f"Case '{case_id}' was not found in experiment '{experiment_id}'.",
        )


@router.get("", response_model=list[HumanReview])
def list_human_reviews(
    experiment_id: str,
    case_id: str,
    repository: Annotated[FileExperimentRepository, Depends(get_experiment_repository)],
    reviews: Annotated[FileHumanReviewRepository, Depends(get_human_review_repository)],
) -> list[HumanReview]:
    check_case(experiment_id, case_id, repository)
    return reviews.list_case(experiment_id, case_id)


@router.post("", response_model=HumanReview, status_code=status.HTTP_201_CREATED)
def create_human_review(
    experiment_id: str,
    case_id: str,
    payload: CreateHumanReviewRequest,
    repository: Annotated[FileExperimentRepository, Depends(get_experiment_repository)],
    reviews: Annotated[FileHumanReviewRepository, Depends(get_human_review_repository)],
) -> HumanReview:
    check_case(experiment_id, case_id, repository)
    return reviews.save(
        HumanReview(
            review_id=f"review-{uuid4().hex}",
            experiment_id=experiment_id,
            case_id=case_id,
            **payload.model_dump(),
        )
    )
