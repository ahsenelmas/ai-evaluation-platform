from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationResult,
)
from app.evaluators.base import Evaluator


class LatencyEvaluator(Evaluator):
    name = "latency"
    version = "1.0.0"

    def __init__(
        self,
        max_latency_ms: int,
    ) -> None:
        if max_latency_ms <= 0:
            raise ValueError("Maximum latency must be greater than zero.")

        self.max_latency_ms = max_latency_ms

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        del case

        actual_latency_ms = execution.latency_ms

        passed = actual_latency_ms <= self.max_latency_ms

        if passed:
            reason = (
                f"Latency {actual_latency_ms} ms is within "
                f"the {self.max_latency_ms} ms limit."
            )
        else:
            reason = (
                f"Latency {actual_latency_ms} ms exceeds "
                f"the {self.max_latency_ms} ms limit."
            )

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=1.0 if passed else 0.0,
            value=passed,
            passed=passed,
            reason=reason,
            metadata={
                "actual_latency_ms": actual_latency_ms,
                "max_latency_ms": self.max_latency_ms,
                "exceeded_by_ms": max(
                    0,
                    actual_latency_ms - self.max_latency_ms,
                ),
            },
        )
