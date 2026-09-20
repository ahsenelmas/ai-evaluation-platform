import json
import sys
from collections import defaultdict
from pathlib import Path

from build_internship_dataset import build_evaluation_case, load_json

source = Path(sys.argv[1])

targets = {
    "malicious": 6,
    "broken": 6,
    "handwritten": 5,
    "missing_crucial_information": 6,
    "requires_clarification": 10,
    "school_requirement_rejection": 6,
    "valid": 11,
}

by_category = defaultdict(list)

for folder in source.iterdir():
    expected_path = folder / "expected_result.json"

    if folder.is_dir() and expected_path.is_file():
        expected = load_json(expected_path)
        by_category[expected["primary_category"]].append(folder.name)

selected_ids = []

for category, count in targets.items():
    available = sorted(by_category[category])

    if len(available) < count:
        raise ValueError(
            f"{category}: need {count}, found {len(available)}"
        )

    selected_ids.extend(available[:count])

# APP-063 has contradictory supervisor evidence in its PDF.
selected_ids = [
    "APP-067" if case_id == "APP-063" else case_id
    for case_id in selected_ids
]

if len(selected_ids) != 50 or len(set(selected_ids)) != 50:
    raise ValueError("Expected 50 distinct cases")

output = Path("data/internship-candidate-50.jsonl")
output.parent.mkdir(parents=True, exist_ok=True)

with output.open("w", encoding="utf-8", newline="\n") as file:
    for case_id in selected_ids:
        case = build_evaluation_case(source, case_id)

        # Convert source-form names to Coordinator output field names.
        if case_id == "APP-033":
            case["expected_output"]["missing_fields"] = [
                "supervisor_email"
            ]
        elif case_id == "APP-035":
            case["expected_output"]["missing_fields"] = [
                "internship_end_date"
            ]

        file.write(json.dumps(case, ensure_ascii=False) + "\n")

print(f"Created {output} with {len(selected_ids)} draft cases")

for category, count in targets.items():
    print(f"{category}: {count}")
