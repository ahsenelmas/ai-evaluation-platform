"""Append-only human evaluations of saved experiment cases."""

from pathlib import Path
from uuid import uuid4

from app.domain.models import HumanReview


class FileHumanReviewRepository:
    def __init__(self, storage_root: str | Path) -> None:
        self.storage_root = Path(storage_root).resolve() / "human_reviews"
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def save(self, review: HumanReview) -> HumanReview:
        path = self.storage_root / f"{review.review_id}.json"
        if path.exists():
            raise ValueError(f"Review '{review.review_id}' already exists.")
        temporary = self.storage_root / f".{review.review_id}.{uuid4().hex}.tmp"
        try:
            temporary.write_text(review.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return review

    def list_case(self, experiment_id: str, case_id: str) -> list[HumanReview]:
        reviews = (
            HumanReview.model_validate_json(path.read_text(encoding="utf-8"))
            for path in self.storage_root.glob("*.json")
        )
        return sorted(
            (
                review
                for review in reviews
                if review.experiment_id == experiment_id and review.case_id == case_id
            ),
            key=lambda review: review.created_at,
        )
