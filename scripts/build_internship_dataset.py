import argparse
import json
from pathlib import Path
from typing import Any

CASE_IDS = [
    "APP-001",
    "APP-002",
    "APP-011",
    "APP-012",
    "APP-021",
    "APP-022",
    "APP-031",
    "APP-032",
    "APP-041",
    "APP-042",
    "APP-061",
    "APP-062",
    "APP-071",
    "APP-072",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a JSON object in {path}."
        )

    return data


def build_evaluation_case(
    source_root: Path,
    case_id: str,
) -> dict[str, Any]:
    case_directory = source_root / case_id

    email_path = case_directory / "email.json"
    expected_path = case_directory / "expected_result.json"
    attachment_path = (
        case_directory
        / f"{case_id}_application.pdf"
    )

    required_paths = [
        email_path,
        expected_path,
        attachment_path,
    ]

    missing_paths = [
        path
        for path in required_paths
        if not path.exists()
    ]

    if missing_paths:
        missing = ", ".join(
            str(path)
            for path in missing_paths
        )

        raise FileNotFoundError(
            f"Missing files for {case_id}: {missing}"
        )

    email = load_json(email_path)
    expected = load_json(expected_path)

    return {
        "id": f"internship-{case_id.lower()}",
        "system": "internship-coordinator",
        "input": {
            "email_sender": email.get("from", ""),
            "email_subject": email.get(
                "subject",
                "",
            ),
            "email_body": email.get("body", ""),
            "attachment_paths": [
                f"{case_id}/{case_id}_application.pdf"
            ],
        },
        "expected_output": {
            "recommendation": expected.get(
                "expected_decision"
            ),
            "missing_fields": expected.get(
                "expected_missing_fields",
                [],
            ),
            "security_flag": expected.get(
                "expected_security_flag",
                False,
            ),
        },
        "metadata": {
            "source_case_id": case_id,
            "category": expected.get(
                "primary_category"
            ),
            "secondary_tags": expected.get(
                "secondary_tags",
                [],
            ),
            "broken_type": expected.get(
                "broken_type"
            ),
            "clarification_type": expected.get(
                "clarification_type"
            ),
            "rejection_type": expected.get(
                "rejection_type"
            ),
            "handwriting_quality": expected.get(
                "handwriting_quality"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Internship Coordinator "
            "golden evaluation dataset."
        )
    )

    parser.add_argument(
        "--source-root",
        required=True,
        type=Path,
        help=(
            "Path to the Coordinator's "
            "generated_test_dataset directory."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "datasets/internship/"
            "internship-coordinator-golden-v1.jsonl"
        ),
        help="Output JSONL file.",
    )

    arguments = parser.parse_args()

    source_root = (
        arguments.source_root
        .expanduser()
        .resolve()
    )

    if not source_root.exists():
        raise FileNotFoundError(
            f"Source directory was not found: "
            f"{source_root}"
        )

    if not source_root.is_dir():
        raise NotADirectoryError(
            f"Source path is not a directory: "
            f"{source_root}"
        )

    output_path: Path = arguments.output

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cases = [
        build_evaluation_case(
            source_root,
            case_id,
        )
        for case_id in CASE_IDS
    ]

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        for case in cases:
            serialized_case = json.dumps(
                case,
                ensure_ascii=False,
                separators=(",", ":"),
            )

            file.write(serialized_case + "\n")

    print(
        f"Created {output_path} "
        f"with {len(cases)} cases."
    )


if __name__ == "__main__":
    main()
