import logging
from contextlib import AbstractContextManager
from typing import Any, Protocol

from langfuse import Langfuse

from app.core.config import Settings
from app.domain.models import (
    ExperimentCaseResult,
    ExperimentReport,
)

logger = logging.getLogger(__name__)


class LangfuseObservationProtocol(Protocol):
    def update(
        self,
        **kwargs: Any,
    ) -> Any:
        """Update an observation."""

    def score(
        self,
        **kwargs: Any,
    ) -> Any:
        """Add a score to an observation."""

    def score_trace(
        self,
        **kwargs: Any,
    ) -> Any:
        """Add a score to the complete trace."""


class LangfuseClientProtocol(Protocol):
    def start_as_current_observation(
        self,
        **kwargs: Any,
    ) -> AbstractContextManager[LangfuseObservationProtocol]:  # type: ignore
        """Start a Langfuse observation."""

    def flush(self) -> None:
        """Send pending Langfuse events."""


class LangfuseExperimentPublisher:
    """Publish completed experiments to Langfuse."""

    def __init__(
        self,
        client: LangfuseClientProtocol | None,
    ) -> None:
        self.client = client

    @property
    def enabled(self) -> bool:
        return self.client is not None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
    ) -> "LangfuseExperimentPublisher":
        public_key = settings.langfuse_public_key
        secret_key = settings.langfuse_secret_key

        if not public_key or not secret_key:
            if public_key or secret_key:
                logger.warning(
                    "Langfuse integration is disabled "
                    "because only one credential was "
                    "configured."
                )

            return cls(client=None)

        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=settings.langfuse_host,
        )

        return cls(client=client)  # type: ignore

    def publish(
        self,
        report: ExperimentReport,
    ) -> bool:
        if self.client is None:
            return False

        try:
            self._publish_report(report)
            self.client.flush()
            return True

        except Exception:
            logger.exception(
                "Failed to publish experiment %s to Langfuse.",
                report.experiment_id,
            )
            return False

    def _publish_report(
        self,
        report: ExperimentReport,
    ) -> None:
        if self.client is None:
            return

        with self.client.start_as_current_observation(
            as_type="span",
            name="evaluation-experiment",
            input={
                "experiment_id": (report.experiment_id),
                "name": report.name,
                "system": report.system,
                "dataset_id": report.dataset_id,
                "dataset_version": (report.dataset_version),
            },
            metadata={
                "experiment_id": (report.experiment_id),
                "system": report.system,
                "dataset_id": report.dataset_id,
                "dataset_version": (report.dataset_version),
                "models": report.models,
                "prompt_versions": (report.prompt_versions),
                "application_versions": (report.application_versions),
                "evaluator_versions": (report.evaluator_versions),
            },
        ) as experiment_span:
            experiment_span.update(
                output={
                    "passed": report.passed,
                    "total_cases": (report.total_cases),
                    "passed_cases": (report.passed_cases),
                    "failed_cases": (report.failed_cases),
                    "pass_rate": report.pass_rate,
                    "aggregate_score": (report.aggregate_score),
                    "total_latency_ms": (report.total_latency_ms),
                    "total_tokens": (report.total_tokens),
                    "total_cost_usd": (report.total_cost_usd),
                }
            )

            experiment_span.score_trace(
                name="experiment_passed",
                value=(1.0 if report.passed else 0.0),
                data_type="BOOLEAN",
            )

            experiment_span.score_trace(
                name="aggregate_score",
                value=float(report.aggregate_score),
                data_type="NUMERIC",
            )

            experiment_span.score_trace(
                name="pass_rate",
                value=float(report.pass_rate),
                data_type="NUMERIC",
            )

            for (
                metric_name,
                metric_score,
            ) in report.metric_scores.items():
                experiment_span.score_trace(
                    name=f"metric_{metric_name}",
                    value=float(metric_score),
                    data_type="NUMERIC",
                )

            for case_result in report.cases:
                self._publish_case(case_result)

    def _publish_case(
        self,
        case_result: ExperimentCaseResult,
    ) -> None:
        if self.client is None:
            return

        execution = case_result.execution

        with self.client.start_as_current_observation(
            as_type="span",
            name="evaluation-case",
            input={
                "case_id": case_result.case_id,
                "input": case_result.input,
                "expected_output": (case_result.expected_output),
            },
            metadata={
                "case_id": case_result.case_id,
                "case_metadata": (case_result.case_metadata),
                "system": execution.system,
                "success": execution.success,
                "error": execution.error,
                "latency_ms": (execution.latency_ms),
                "input_tokens": (execution.token_usage.input_tokens),
                "output_tokens": (execution.token_usage.output_tokens),
                "total_tokens": (execution.token_usage.total_tokens),
                "estimated_cost": (execution.estimated_cost),
                "model": execution.model,
                "prompt_version": (execution.prompt_version),
                "application_version": (execution.application_version),
            },
        ) as case_span:
            case_span.update(
                output={
                    "actual_output": execution.output,
                    "retrieved_context": (execution.retrieved_context),
                    "passed": case_result.passed,
                    "aggregate_score": (case_result.evaluation.aggregate_score),
                }
            )

            case_span.score(
                name="execution_success",
                value=(1.0 if execution.success else 0.0),
                data_type="BOOLEAN",
                comment=execution.error,
            )

            case_span.score(
                name="case_passed",
                value=(1.0 if case_result.passed else 0.0),
                data_type="BOOLEAN",
            )

            for result in case_result.evaluation.results:
                if result.score is None:
                    continue

                case_span.score(
                    name=result.evaluator,
                    value=float(result.score),
                    data_type="NUMERIC",
                    comment=result.reason,
                    metadata={
                        "evaluator_version": (result.evaluator_version),
                        "passed": result.passed,
                        **result.metadata,
                    },
                )
