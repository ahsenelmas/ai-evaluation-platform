from typing import Any

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)
from app.evaluators.base import Evaluator


class RetrievalEvaluator(Evaluator):
    def __init__(
        self,
        *,
        k: int = 5,
        minimum_score: float = 0.0,
        expected_field: str = (
            "expected_source_ids"
        ),
        source_id_field: str = "url",
    ) -> None:
        if k <= 0:
            raise ValueError(
                "Retrieval K must be greater than zero."
            )

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

        return list(
            dict.fromkeys(
                item.strip()
                for item in raw_ids
                if item.strip()
            )
        )

    def get_retrieved_ids(
        self,
        execution: ApplicationExecution,
    ) -> list[str]:
        retrieved_ids: list[str] = []

        for source in execution.retrieved_context:
            if not isinstance(source, dict):
                continue

            source_id: Any = source.get(
                self.source_id_field
            )

            if not isinstance(source_id, str):
                continue

            source_id = source_id.strip()

            if (
                source_id
                and source_id not in retrieved_ids
            ):
                retrieved_ids.append(source_id)

        return retrieved_ids[: self.k]


class RetrievalRecallEvaluator(
    RetrievalEvaluator
):
    name = "retrieval_recall"
    version = "1.0.0"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        try:
            expected_ids = self.get_expected_ids(
                case
            )

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

        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)

        matched_ids = sorted(
            expected_set & retrieved_set
        )

        missing_ids = sorted(
            expected_set - retrieved_set
        )

        score = (
            len(matched_ids) / len(expected_set)
            if expected_set
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
                f"{len(expected_set)} expected sources "
                f"within the top {self.k} results."
            ),
            metadata={
                "k": self.k,
                "minimum_score": self.minimum_score,
                "expected_ids": expected_ids,
                "retrieved_ids": retrieved_ids,
                "matched_ids": matched_ids,
                "missing_ids": missing_ids,
            },
        )


class RetrievalPrecisionEvaluator(
    RetrievalEvaluator
):
    name = "retrieval_precision"
    version = "1.0.0"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        try:
            expected_ids = self.get_expected_ids(
                case
            )

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

        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)

        matched_ids = sorted(
            expected_set & retrieved_set
        )

        irrelevant_ids = sorted(
            retrieved_set - expected_set
        )

        if retrieved_ids:
            score = (
                len(matched_ids)
                / len(retrieved_ids)
            )
        else:
            score = (
                1.0
                if not expected_ids
                else 0.0
            )

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
                "matched_ids": matched_ids,
                "irrelevant_ids": irrelevant_ids,
            },
        )
