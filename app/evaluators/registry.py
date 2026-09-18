from collections.abc import Callable
from typing import Any

from app.core.config import get_settings
from app.evaluators.base import Evaluator
from app.evaluators.deterministic.exact_match import (
    ExactMatchEvaluator,
)
from app.evaluators.deterministic.latency import (
    LatencyEvaluator,
)
from app.evaluators.deterministic.required_fields import (
    RequiredFieldsEvaluator,
)
from app.evaluators.deterministic.retrieval import (
    RetrievalPrecisionEvaluator,
    RetrievalRecallEvaluator,
)
from app.evaluators.llm_judges.semantic_facts import (
    SemanticFactsEvaluator,
)

EvaluatorFactory = Callable[
    [dict[str, Any]],
    Evaluator,
]


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._factories: dict[
            str,
            EvaluatorFactory,
        ] = {}

    def register(
        self,
        name: str,
        factory: EvaluatorFactory,
    ) -> None:
        normalized_name = name.strip().lower()

        if not normalized_name:
            raise ValueError(
                "Evaluator name cannot be empty."
            )

        if normalized_name in self._factories:
            raise ValueError(
                f"Evaluator '{normalized_name}' "
                "is already registered."
            )

        self._factories[normalized_name] = factory

    def create(
        self,
        name: str,
        settings: dict[str, Any],
    ) -> Evaluator:
        normalized_name = name.strip().lower()

        factory = self._factories.get(
            normalized_name
        )

        if factory is None:
            available = ", ".join(self.available())

            raise ValueError(
                f"Unknown evaluator '{name}'. "
                f"Available evaluators: {available}"
            )

        return factory(settings)

    def available(self) -> list[str]:
        return sorted(self._factories)


def create_exact_match_evaluator(
    settings: dict[str, Any],
) -> Evaluator:
    field_name = settings.get("field_name")

    if not isinstance(field_name, str):
        raise ValueError(
            "The exact_match evaluator requires "
            "a string 'field_name' setting."
        )

    field_name = field_name.strip()

    if not field_name:
        raise ValueError(
            "The exact_match evaluator requires "
            "a non-empty 'field_name' setting."
        )

    return ExactMatchEvaluator(
        field_name=field_name,
    )


def create_required_fields_evaluator(
    settings: dict[str, Any],
) -> Evaluator:
    required_fields = settings.get(
        "required_fields"
    )
    allow_empty_fields = settings.get(
        "allow_empty_fields",
        [],
    )

    if not isinstance(required_fields, list):
        raise ValueError(
            "The required_fields evaluator requires "
            "a 'required_fields' list."
        )

    if not all(
        isinstance(field, str)
        for field in required_fields
    ):
        raise ValueError(
            "Every required field must be a string."
        )

    if not isinstance(allow_empty_fields, list):
        raise ValueError(
            "'allow_empty_fields' must be a list."
        )

    if not all(
        isinstance(field, str)
        for field in allow_empty_fields
    ):
        raise ValueError(
            "Every field allowed to be empty "
            "must be a string."
        )

    return RequiredFieldsEvaluator(
        required_fields=required_fields,
        allow_empty_fields=allow_empty_fields,
    )


def create_latency_evaluator(
    settings: dict[str, Any],
) -> Evaluator:
    max_latency_ms = settings.get(
        "max_latency_ms"
    )

    if (
        not isinstance(max_latency_ms, int)
        or isinstance(max_latency_ms, bool)
    ):
        raise ValueError(
            "The latency evaluator requires "
            "an integer 'max_latency_ms' setting."
        )

    return LatencyEvaluator(
        max_latency_ms=max_latency_ms,
    )


def parse_retrieval_settings(
    settings: dict[str, Any],
) -> tuple[int, float, str, str]:
    k = settings.get("k", 5)

    minimum_score = settings.get(
        "minimum_score",
        1.0,
    )

    expected_field = settings.get(
        "expected_field",
        "expected_source_ids",
    )

    source_id_field = settings.get(
        "source_id_field",
        "url",
    )

    if (
        not isinstance(k, int)
        or isinstance(k, bool)
        or k <= 0
    ):
        raise ValueError(
            "Retrieval evaluator requires "
            "a positive integer 'k'."
        )

    if (
        not isinstance(
            minimum_score,
            (int, float),
        )
        or isinstance(minimum_score, bool)
        or not 0.0
        <= float(minimum_score)
        <= 1.0
    ):
        raise ValueError(
            "'minimum_score' must be between 0 and 1."
        )

    if (
        not isinstance(expected_field, str)
        or not expected_field.strip()
    ):
        raise ValueError(
            "'expected_field' must be "
            "a non-empty string."
        )

    if (
        not isinstance(source_id_field, str)
        or not source_id_field.strip()
    ):
        raise ValueError(
            "'source_id_field' must be "
            "a non-empty string."
        )

    return (
        k,
        float(minimum_score),
        expected_field.strip(),
        source_id_field.strip(),
    )


def create_retrieval_recall_evaluator(
    settings: dict[str, Any],
) -> Evaluator:
    (
        k,
        minimum_score,
        expected_field,
        source_id_field,
    ) = parse_retrieval_settings(settings)

    return RetrievalRecallEvaluator(
        k=k,
        minimum_score=minimum_score,
        expected_field=expected_field,
        source_id_field=source_id_field,
    )


def create_retrieval_precision_evaluator(
    settings: dict[str, Any],
) -> Evaluator:
    (
        k,
        minimum_score,
        expected_field,
        source_id_field,
    ) = parse_retrieval_settings(settings)

    return RetrievalPrecisionEvaluator(
        k=k,
        minimum_score=minimum_score,
        expected_field=expected_field,
        source_id_field=source_id_field,
    )


def create_semantic_facts_evaluator(
    settings: dict[str, Any],
) -> Evaluator:
    minimum_score = settings.get(
        "minimum_score",
        1.0,
    )

    expected_field = settings.get(
        "expected_field",
        "expected_answer_facts",
    )

    answer_field = settings.get(
        "answer_field",
        "answer",
    )

    timeout_seconds = settings.get(
        "timeout_seconds",
        60.0,
    )

    if (
        not isinstance(
            minimum_score,
            (int, float),
        )
        or isinstance(minimum_score, bool)
        or not 0.0
        <= float(minimum_score)
        <= 1.0
    ):
        raise ValueError(
            "'minimum_score' must be between 0 and 1."
        )

    if (
        not isinstance(expected_field, str)
        or not expected_field.strip()
    ):
        raise ValueError(
            "'expected_field' must be "
            "a non-empty string."
        )

    if (
        not isinstance(answer_field, str)
        or not answer_field.strip()
    ):
        raise ValueError(
            "'answer_field' must be "
            "a non-empty string."
        )

    if (
        not isinstance(
            timeout_seconds,
            (int, float),
        )
        or isinstance(timeout_seconds, bool)
        or float(timeout_seconds) <= 0
    ):
        raise ValueError(
            "'timeout_seconds' must be "
            "greater than zero."
        )

    app_settings = get_settings()

    base_url = app_settings.evaluator_llm_base_url
    api_key = app_settings.evaluator_llm_api_key
    model = app_settings.evaluator_llm_model

    missing_configuration: list[str] = []

    if not base_url:
        missing_configuration.append(
            "EVALUATOR_LLM_BASE_URL"
        )

    if not api_key:
        missing_configuration.append(
            "EVALUATOR_LLM_API_KEY"
        )

    if not model:
        missing_configuration.append(
            "EVALUATOR_LLM_MODEL"
        )

    if missing_configuration:
        raise ValueError(
            "Semantic judge is not configured. Missing: "
            + ", ".join(missing_configuration)
        )

    # These assertions also narrow the types for
    # static type checkers such as Pylance.
    assert base_url is not None
    assert api_key is not None
    assert model is not None

    return SemanticFactsEvaluator(
        base_url=base_url,
        api_key=api_key,
        model=model,
        minimum_score=float(minimum_score),
        expected_field=expected_field.strip(),
        answer_field=answer_field.strip(),
        timeout_seconds=float(timeout_seconds),
    )


def build_default_registry() -> EvaluatorRegistry:
    registry = EvaluatorRegistry()

    registry.register(
        "exact_match",
        create_exact_match_evaluator,
    )

    registry.register(
        "required_fields",
        create_required_fields_evaluator,
    )

    registry.register(
        "latency",
        create_latency_evaluator,
    )

    registry.register(
        "retrieval_recall",
        create_retrieval_recall_evaluator,
    )

    registry.register(
        "retrieval_precision",
        create_retrieval_precision_evaluator,
    )

    registry.register(
        "semantic_facts",
        create_semantic_facts_evaluator,
    )

    return registry
