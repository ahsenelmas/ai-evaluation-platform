from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)
from app.evaluators.base import Evaluator


def normalize_source_id(source_id: str) -> str:
    value = source_id.strip()

    if not value:
        return value

    parsed = urlsplit(value)

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
    ):
        return value

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]

    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    path = parsed.path.rstrip("/")

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            "",
            "",
        )
    )


def deduplicate_source_ids(
    source_ids: list[str],
) -> list[str]:
    unique_ids: list[str] = []
    normalized_ids: set[str] = set()

    for source_id in source_ids:
        normalized_id = normalize_source_id(source_id)

        if not normalized_id:
            continue

        if normalized_id in normalized_ids:
            continue

        normalized_ids.add(normalized_id)
        unique_ids.append(source_id.strip())

    return unique_ids


class RetrievalEvaluator(Evaluator):
    def __init__(
        self,
        *,
        k: int = 5,
        minimum_score: float = 1.0,
        expected_field: str = "expected_source_ids",
        source_id_field: str = "url",
    ) -> None:
        if k <= 0:
            raise ValueError("Retrieval K must be greater than zero.")

        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError(
                "Minimum score must be between 0 and 1."
            )

        self.k = k
        self.minimum_score = minimum_score
        self.expected_field = expected_field
        self.source_id_field = source_id_field

    def get_expected_ids(
        self,
        case: EvaluationCase,
    ) -> list[str]:
        raw_ids = case.expected_output.get(
            self.expected_field,
            [],
        )

        if not isinstance(raw_ids, list):
            raise ValueError(
                f"'{self.expected_field}' must be a list."
            )

        if not all(
            isinstance(item, str)
            for item in raw_ids
        ):
            raise ValueError(
                "Every expected source ID must be a string."
            )

        return deduplicate_source_ids(raw_ids)

    def get_retrieved_ids(
        self,
        execution: ApplicationExecution,
    ) -> list[str]:
        raw_ids: list[str] = []

        for source in execution.retrieved_context:
            if not isinstance(source, dict):
                continue

            source_id: Any = source.get(
                self.source_id_field
            )

            if not isinstance(source_id, str):
                continue

            if source_id.strip():
                raw_ids.append(source_id)

        return deduplicate_source_ids(raw_ids)[: self.k]


class RetrievalRecallEvaluator(RetrievalEvaluator):
    name = "retrieval_recall"
    version = "1.1.0"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        try:
            expected_ids = self.get_expected_ids(case)
            retrieved_ids = self.get_retrieved_ids(
                execution
            )

        except ValueError as error:
            return EvaluationResult(
                evaluator=self.name,
                evaluator_version=self.version,
                score=0.0,
                passed=False,
                reason=str(error),
                metadata={
                    "k": self.k,
                    "configuration_error": True,
                },
            )

        normalized_expected_ids = [
            normalize_source_id(source_id)
            for source_id in expected_ids
        ]
        normalized_retrieved_ids = [
            normalize_source_id(source_id)
            for source_id in retrieved_ids
        ]

        retrieved_set = set(normalized_retrieved_ids)

        matched_ids = [
            source_id
            for source_id in expected_ids
            if normalize_source_id(source_id)
            in retrieved_set
        ]

        missing_ids = [
            source_id
            for source_id in expected_ids
            if normalize_source_id(source_id)
            not in retrieved_set
        ]

        score = (
            len(matched_ids) / len(expected_ids)
            if expected_ids
            else 1.0
        )

        passed = score >= self.minimum_score

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=round(score, 4),
            value=passed,
            passed=passed,
            reason=(
                f"Retrieved {len(matched_ids)} of "
                f"{len(expected_ids)} expected sources "
                f"within the top {self.k} results."
            ),
            metadata={
                "k": self.k,
                "minimum_score": self.minimum_score,
                "expected_ids": expected_ids,
                "retrieved_ids": retrieved_ids,
                "normalized_expected_ids": (
                    normalized_expected_ids
                ),
                "normalized_retrieved_ids": (
                    normalized_retrieved_ids
                ),
                "matched_ids": matched_ids,
                "missing_ids": missing_ids,
            },
        )


class RetrievalPrecisionEvaluator(RetrievalEvaluator):
    name = "retrieval_precision"
    version = "1.1.0"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        try:
            expected_ids = self.get_expected_ids(case)
            retrieved_ids = self.get_retrieved_ids(
                execution
            )

        except ValueError as error:
            return EvaluationResult(
                evaluator=self.name,
                evaluator_version=self.version,
                score=0.0,
                passed=False,
                reason=str(error),
                metadata={
                    "k": self.k,
                    "configuration_error": True,
                },
            )

        normalized_expected_ids = [
            normalize_source_id(source_id)
            for source_id in expected_ids
        ]
        normalized_retrieved_ids = [
            normalize_source_id(source_id)
            for source_id in retrieved_ids
        ]

        expected_set = set(normalized_expected_ids)

        matched_ids = [
            source_id
            for source_id in retrieved_ids
            if normalize_source_id(source_id)
            in expected_set
        ]

        irrelevant_ids = [
            source_id
            for source_id in retrieved_ids
            if normalize_source_id(source_id)
            not in expected_set
        ]

        if retrieved_ids:
            score = len(matched_ids) / len(
                retrieved_ids
            )
        else:
            score = 1.0 if not expected_ids else 0.0

        passed = score >= self.minimum_score

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=round(score, 4),
            value=passed,
            passed=passed,
            reason=(
                f"{len(matched_ids)} of "
                f"{len(retrieved_ids)} retrieved sources "
                f"were relevant within the top {self.k}."
            ),
            metadata={
                "k": self.k,
                "minimum_score": self.minimum_score,
                "expected_ids": expected_ids,
                "retrieved_ids": retrieved_ids,
                "normalized_expected_ids": (
                    normalized_expected_ids
                ),
                "normalized_retrieved_ids": (
                    normalized_retrieved_ids
                ),
                "matched_ids": matched_ids,
                "irrelevant_ids": irrelevant_ids,
            },
        )
