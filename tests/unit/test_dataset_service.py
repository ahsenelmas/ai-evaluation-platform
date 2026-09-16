import hashlib
import json
from pathlib import Path

import pytest

from app.services.dataset_service import (
    DatasetService,
)


def write_dataset(
    root: Path,
    *,
    cases: list[dict],
    system: str = "ata-rag",
    released: bool = False,
    checksum: str | None = None,
) -> DatasetService:
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataset_path = root / "test.jsonl"

    content = "\n".join(json.dumps(case) for case in cases)

    dataset_path.write_text(
        content,
        encoding="utf-8",
    )

    actual_checksum = hashlib.sha256(dataset_path.read_bytes()).hexdigest()

    manifest = [
        {
            "id": "test-dataset-v1",
            "system": system,
            "version": "1.0.0",
            "file_path": "test.jsonl",
            "description": "Test dataset",
            "released": released,
            "checksum_sha256": (
                checksum
                if checksum is not None
                else (actual_checksum if released else None)
            ),
            "case_count": len(cases),
        }
    ]

    (root / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    return DatasetService(root)


def create_case(
    case_id: str = "case-001",
    system: str = "ata-rag",
) -> dict:
    return {
        "id": case_id,
        "system": system,
        "input": {"question": "Test question"},
        "expected_output": {},
        "metadata": {},
    }


def test_dataset_service_loads_dataset(
    tmp_path: Path,
) -> None:
    service = write_dataset(
        tmp_path,
        cases=[create_case()],
    )

    dataset = service.get_dataset("test-dataset-v1")

    assert dataset.metadata.system == "ata-rag"
    assert len(dataset.cases) == 1
    assert dataset.cases[0].id == "case-001"


def test_dataset_service_rejects_duplicate_cases(
    tmp_path: Path,
) -> None:
    service = write_dataset(
        tmp_path,
        cases=[
            create_case(),
            create_case(),
        ],
    )

    with pytest.raises(
        ValueError,
        match="duplicate case IDs",
    ):
        service.get_dataset("test-dataset-v1")


def test_dataset_service_rejects_wrong_system(
    tmp_path: Path,
) -> None:
    service = write_dataset(
        tmp_path,
        cases=[create_case(system="internship-coordinator")],
        system="ata-rag",
    )

    with pytest.raises(
        ValueError,
        match="another system",
    ):
        service.get_dataset("test-dataset-v1")


def test_released_dataset_detects_changes(
    tmp_path: Path,
) -> None:
    service = write_dataset(
        tmp_path,
        cases=[create_case()],
        released=True,
        checksum="incorrect-checksum",
    )

    with pytest.raises(
        ValueError,
        match="has been modified",
    ):
        service.get_dataset("test-dataset-v1")
