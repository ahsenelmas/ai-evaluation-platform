from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.models import ExperimentReport
from app.repositories.experiment_repository import (
    ExperimentNotFoundError,
    FileExperimentRepository,
)


def create_report(
    *,
    experiment_id: str,
    completed_at: datetime,
) -> ExperimentReport:
    return ExperimentReport(
        experiment_id=experiment_id,
        name="Repository test",
        system="demo-system",
        dataset_id="demo-dataset",
        dataset_version="1.0.0",
        started_at=completed_at,
        completed_at=completed_at,
        passed=True,
        total_cases=0,
        passed_cases=0,
        failed_cases=0,
        pass_rate=1.0,
        aggregate_score=1.0,
    )


def test_repository_saves_and_loads_report(
    tmp_path: Path,
):
    repository = FileExperimentRepository(storage_root=tmp_path)

    report = create_report(
        experiment_id="exp-save-test",
        completed_at=datetime(
            2026,
            9,
            16,
            10,
            0,
            tzinfo=UTC,
        ),
    )

    repository.save(report)

    loaded_report = repository.get("exp-save-test")

    assert loaded_report == report
    assert (tmp_path / "exp-save-test.json").exists()


def test_repository_lists_newest_report_first(
    tmp_path: Path,
):
    repository = FileExperimentRepository(storage_root=tmp_path)

    older_report = create_report(
        experiment_id="exp-older",
        completed_at=datetime(
            2026,
            9,
            16,
            10,
            0,
            tzinfo=UTC,
        ),
    )

    newer_report = create_report(
        experiment_id="exp-newer",
        completed_at=datetime(
            2026,
            9,
            16,
            11,
            0,
            tzinfo=UTC,
        ),
    )

    repository.save(older_report)
    repository.save(newer_report)

    reports = repository.list_reports()

    assert [report.experiment_id for report in reports] == [
        "exp-newer",
        "exp-older",
    ]


def test_repository_reports_missing_experiment(
    tmp_path: Path,
):
    repository = FileExperimentRepository(storage_root=tmp_path)

    with pytest.raises(
        ExperimentNotFoundError,
        match="was not found",
    ):
        repository.get("exp-missing")


def test_repository_rejects_path_traversal(
    tmp_path: Path,
):
    repository = FileExperimentRepository(storage_root=tmp_path)

    with pytest.raises(
        ValueError,
        match="invalid path",
    ):
        repository.get("../../outside-directory")
