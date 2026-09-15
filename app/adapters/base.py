from abc import ABC, abstractmethod

from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)


class ApplicationAdapter(ABC):
    system: str

    @abstractmethod
    async def execute(
        self,
        case: EvaluationCase,
    ) -> ApplicationExecution:
        """Execute one evaluation case against an AI system."""
        raise NotImplementedError

    def validate_case(
        self,
        case: EvaluationCase,
    ) -> None:
        if case.system != self.system:
            raise ValueError(
                f"Adapter '{self.system}' cannot execute "
                f"a case for system '{case.system}'."
            )
