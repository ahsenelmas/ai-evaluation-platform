from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.domain.models import ExperimentReport


class ExperimentNotFoundError(ValueError):
    """Raised when a stored experiment does not exist."""


class FileExperimentRepository:
    """Store experiment reports as versioned JSON files."""

    def __init__(
        self,
        storage_root: str | Path,
    ) -> None:
        self.storage_root = Path(storage_root).resolve()

        self.storage_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(
        self,
        report: ExperimentReport,
    ) -> ExperimentReport:
        experiment_path = self._experiment_path(report.experiment_id)

        temporary_path = self.storage_root / (
            f".{report.experiment_id}.{uuid4().hex}.tmp"
        )

        try:
            temporary_path.write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )

            temporary_path.replace(experiment_path)

        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        return report

    def get(
        self,
        experiment_id: str,
    ) -> ExperimentReport:
        experiment_path = self._experiment_path(experiment_id)

        if not experiment_path.exists():
            raise ExperimentNotFoundError(
                f"Experiment '{experiment_id}' was not found."
            )

        return self._load_report(experiment_path)

    def list_reports(
        self,
    ) -> list[ExperimentReport]:
        reports = [self._load_report(path) for path in self.storage_root.glob("*.json")]

        return sorted(
            reports,
            key=lambda report: report.completed_at,
            reverse=True,
        )

    def _experiment_path(
        self,
        experiment_id: str,
    ) -> Path:
        normalized_id = experiment_id.strip()

        if not normalized_id:
            raise ValueError("Experiment ID cannot be empty.")

        experiment_path = (self.storage_root / f"{normalized_id}.json").resolve()

        if not experiment_path.is_relative_to(self.storage_root):
            raise ValueError("Experiment ID contains an invalid path.")

        return experiment_path

    @staticmethod
    def _load_report(
        experiment_path: Path,
    ) -> ExperimentReport:
        try:
            return ExperimentReport.model_validate_json(
                experiment_path.read_text(encoding="utf-8")
            )

        except (
            OSError,
            ValidationError,
        ) as error:
            raise ValueError(
                f"Stored experiment report is invalid: {experiment_path.name}"
            ) from error
