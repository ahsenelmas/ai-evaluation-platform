from abc import ABC, abstractmethod

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)


class Evaluator(ABC):
    name: str
    version: str = "1.0.0"

    @abstractmethod
    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        """Evaluate one application execution."""
        raise NotImplementedError
