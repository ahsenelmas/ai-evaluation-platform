"""Build 100 ATA-RAG candidate prompts from 20 existing seed questions."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "ATA-RAG" / "evaluation" / "ata_rag_evaluation.json"
OUTPUT = ROOT / "datasets" / "ata_rag" / "ata-rag-candidate-100-v1.jsonl"
MANIFEST = ROOT / "datasets" / "manifest.json"
DATASET_ID = "ata-rag-candidate-100-v1"

PREFIXES = {
    "en": (
        "",
        "Please answer this question: ",
        "Could you explain: ",
        "Please give a clear answer to: ",
        "Based on ATA information, answer: ",
    ),
    "pl": (
        "",
        "Proszę odpowiedzieć na pytanie: ",
        "Czy możesz wyjaśnić: ",
        "Proszę jasno odpowiedzieć: ",
        "Na podstawie informacji ATA odpowiedz: ",
    ),
}


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Seed file not found: {SOURCE}")

    seeds = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(seeds, list) or len(seeds) != 20:
        raise SystemExit("Expected exactly 20 existing ATA-RAG seed cases.")

    cases = []
    questions = set()
    seed_ids = set()

    for seed in seeds:
        seed_id = seed["id"]
        language = seed["language"].lower()
        question = seed["question"].strip()

        if seed_id in seed_ids or language not in PREFIXES or not question:
            raise SystemExit(f"Invalid or duplicate seed: {seed_id}")
        seed_ids.add(seed_id)

        terms = seed.get("expected_terms", [])
        source_fragments = seed.get("expected_source_contains", [])
        if not isinstance(terms, list) or not isinstance(source_fragments, list):
            raise SystemExit(f"Invalid expected labels for {seed_id}")

        # Convert the existing calculator URL fragment to its full URL.
        source_urls = []
        for fragment in source_fragments:
            if fragment != "kalkulator-czesnego":
                raise SystemExit(
                    f"Review the source URL for {seed_id}: {fragment}"
                )
            source_urls.append(
                "https://akademiata.pl/kalkulator-czesnego/"
            )

        for variant, prefix in enumerate(PREFIXES[language], start=1):
            prompt = prefix + question
            if prompt.casefold() in questions:
                raise SystemExit(f"Duplicate question: {prompt}")
            questions.add(prompt.casefold())

            cases.append({
                "id": f"ata-100-{len(cases) + 1:03d}",
                "system": "ata-rag",
                "input": {
                    "question": prompt,
                    "language": language,
                    "retrieval_limit": 5,
                },
                "expected_output": {
                    "grounded": seed["expected_grounded"],
                    "expected_source_ids": source_urls,
                    "expected_answer_facts": [
                        f"The answer includes {term}."
                        for term in terms
                    ] if seed["expected_grounded"] else [],
                },
                "metadata": {
                    "category": seed["category"],
                    "seed_id": seed_id,
                    "variant": variant,
                    "label_origin": (
                        "ATA-RAG/evaluation/ata_rag_evaluation.json"
                    ),
                    "forbidden_terms_for_manual_review": seed.get(
                        "forbidden_terms", []
                    ),
                },
            })

    if len(cases) != 100:
        raise SystemExit("Expected exactly 100 cases.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "".join(
            json.dumps(case, ensure_ascii=False) + "\n"
            for case in cases
        ),
        encoding="utf-8",
        newline="\n",
    )

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = {
        "id": DATASET_ID,
        "system": "ata-rag",
        "version": "0.1.0",
        "file_path": "ata_rag/ata-rag-candidate-100-v1.jsonl",
        "description": (
            "100 prompt variants from 20 ATA-RAG seed cases; "
            "review pending."
        ),
        "released": False,
        "checksum_sha256": None,
        "case_count": 100,
    }

    matching = [item for item in manifest if item["id"] == DATASET_ID]
    if matching and matching[0] != entry:
        raise SystemExit(
            "Existing candidate manifest entry differs; review it."
        )
    if not matching:
        manifest.append(entry)
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    print(
        f"Created {OUTPUT} with {len(cases)} cases "
        "from 20 seed questions."
    )
    print(f"Registered {DATASET_ID} as an unreleased candidate.")


if __name__ == "__main__":
    main()
