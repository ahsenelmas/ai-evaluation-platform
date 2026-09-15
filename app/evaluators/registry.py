from collections.abc import Callable
from typing import Any

from app.evaluators.base import Evaluator
from app.evaluators.deterministic.exact_match import (
    ExactMatchEvaluator,
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
            available = ", ".join(
                self.available()
            )

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


def build_default_registry() -> EvaluatorRegistry:
    registry = EvaluatorRegistry()

    registry.register(
        "exact_match",
        create_exact_match_evaluator,
    )

    return registry
