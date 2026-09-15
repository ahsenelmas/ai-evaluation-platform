import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.models import (
    DatasetManifestEntry,
    EvaluationCase,
    EvaluationDataset,
)


class DatasetService:
    def __init__(
        self,
        dataset_root: str | Path,
    ) -> None:
        self.dataset_root = Path(
            dataset_root
        ).resolve()

        self.manifest_path = (
            self.dataset_root / "manifest.json"
        )

    def list_datasets(
        self,
    ) -> list[DatasetManifestEntry]:
        return self._load_manifest()

    def get_dataset(
        self,
        dataset_id: str,
    ) -> EvaluationDataset:
        entries = self._load_manifest()

        entry = next(
            (
                item
                for item in entries
                if item.id == dataset_id
            ),
            None,
        )

        if entry is None:
            raise ValueError(
                f"Dataset '{dataset_id}' was not found."
            )

        dataset_path = self._resolve_dataset_path(
            entry.file_path
        )

        if not dataset_path.exists():
            raise ValueError(
                f"Dataset file does not exist: "
                f"{entry.file_path}"
            )

        file_bytes = dataset_path.read_bytes()

        actual_checksum = hashlib.sha256(
            file_bytes
        ).hexdigest()

        if entry.released:
            if not entry.checksum_sha256:
                raise ValueError(
                    f"Released dataset '{entry.id}' "
                    "does not have a checksum."
                )

            if (
                actual_checksum
                != entry.checksum_sha256
            ):
                raise ValueError(
                    f"Released dataset '{entry.id}' "
                    "has been modified."
                )

        cases = self._load_jsonl_cases(
            dataset_path
        )

        self._validate_dataset(
            entry=entry,
            cases=cases,
        )

        return EvaluationDataset(
            metadata=entry,
            cases=cases,
        )

    def _load_manifest(
        self,
    ) -> list[DatasetManifestEntry]:
        if not self.manifest_path.exists():
            raise ValueError(
                "Dataset manifest was not found."
            )

        try:
            raw_manifest: Any = json.loads(
                self.manifest_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "Dataset manifest contains "
                "invalid JSON."
            ) from error

        if not isinstance(raw_manifest, list):
            raise ValueError(
                "Dataset manifest must contain "
                "a JSON list."
            )

        try:
            entries = [
                DatasetManifestEntry.model_validate(
                    item
                )
                for item in raw_manifest
            ]
        except ValidationError as error:
            raise ValueError(
                "Dataset manifest validation failed."
            ) from error

        dataset_ids = [
            entry.id
            for entry in entries
        ]

        if len(dataset_ids) != len(
            set(dataset_ids)
        ):
            raise ValueError(
                "Dataset manifest contains "
                "duplicate dataset IDs."
            )

        return entries

    def _resolve_dataset_path(
        self,
        relative_path: str,
    ) -> Path:
        dataset_path = (
            self.dataset_root / relative_path
        ).resolve()

        if not dataset_path.is_relative_to(
            self.dataset_root
        ):
            raise ValueError(
                "Dataset path cannot leave "
                "the dataset directory."
            )

        return dataset_path

    @staticmethod
    def _load_jsonl_cases(
        dataset_path: Path,
    ) -> list[EvaluationCase]:
        cases: list[EvaluationCase] = []

        for line_number, line in enumerate(
            dataset_path.read_text(
                encoding="utf-8"
            ).splitlines(),
            start=1,
        ):
            if not line.strip():
                continue

            try:
                raw_case = json.loads(line)

                case = (
                    EvaluationCase.model_validate(
                        raw_case
                    )
                )

            except (
                json.JSONDecodeError,
                ValidationError,
            ) as error:
                raise ValueError(
                    f"Invalid evaluation case on "
                    f"line {line_number}."
                ) from error

            cases.append(case)

        return cases

    @staticmethod
    def _validate_dataset(
        entry: DatasetManifestEntry,
        cases: list[EvaluationCase],
    ) -> None:
        if len(cases) != entry.case_count:
            raise ValueError(
                f"Dataset '{entry.id}' expected "
                f"{entry.case_count} cases but "
                f"contains {len(cases)}."
            )

        case_ids = [
            case.id
            for case in cases
        ]

        if len(case_ids) != len(
            set(case_ids)
        ):
            raise ValueError(
                f"Dataset '{entry.id}' contains "
                "duplicate case IDs."
            )

        wrong_system_cases = [
            case.id
            for case in cases
            if case.system != entry.system
        ]

        if wrong_system_cases:
            raise ValueError(
                f"Dataset '{entry.id}' contains "
                "cases for another system: "
                + ", ".join(wrong_system_cases)
            )
