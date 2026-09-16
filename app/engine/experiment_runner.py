from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from app.adapters.base import ApplicationAdapter
from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    EvaluationDataset,
    ExperimentCaseResult,
    ExperimentReport,
)
from app.engine.runner import EvaluationRunner
from app.evaluators.base import Evaluator


class ExperimentRunner:
    """Execute and evaluate every case in a dataset."""

    def __init__(
        self,
        adapter: ApplicationAdapter,
        evaluators: Sequence[Evaluator],
    ) -> None:
        evaluator_list = list(evaluators)

        self.adapter = adapter
        self.evaluators = evaluator_list
        self.evaluation_runner = EvaluationRunner(evaluator_list)

    async def run(
        self,
        name: str,
        dataset: EvaluationDataset,
    ) -> ExperimentReport:
        if not name.strip():
            raise ValueError("Experiment name cannot be empty.")

        if not dataset.cases:
            raise ValueError("Experiment dataset cannot be empty.")

        if dataset.metadata.system != self.adapter.system:
            raise ValueError(
                f"Adapter '{self.adapter.system}' cannot "
                f"run dataset for system "
                f"'{dataset.metadata.system}'."
            )

        started_at = datetime.now(UTC)

        case_results: list[ExperimentCaseResult] = []

        metric_buckets: dict[
            str,
            list[float],
        ] = {
            "execution_success": [],
        }

        case_scores: list[float] = []

        total_latency_ms = 0
        total_tokens = 0
        total_cost_usd = 0.0

        application_versions: set[str] = set()
        prompt_versions: set[str] = set()
        models: set[str] = set()

        for case in dataset.cases:
            execution = await self._execute_case(case)

            evaluation = await self.evaluation_runner.run_case(
                case=case,
                execution=execution,
            )

            case_passed = execution.success and evaluation.passed

            case_results.append(
                ExperimentCaseResult(
                    case_id=case.id,
                    passed=case_passed,
                    execution=execution,
                    evaluation=evaluation,
                )
            )

            metric_buckets["execution_success"].append(
                1.0 if execution.success else 0.0
            )

            for result in evaluation.results:
                if result.score is None:
                    continue

                metric_buckets.setdefault(
                    result.evaluator,
                    [],
                ).append(result.score)

            case_scores.append(evaluation.aggregate_score if execution.success else 0.0)

            total_latency_ms += execution.latency_ms
            total_tokens += execution.token_usage.total_tokens
            total_cost_usd += execution.estimated_cost

            if execution.application_version:
                application_versions.add(execution.application_version)

            if execution.prompt_version:
                prompt_versions.add(execution.prompt_version)

            if execution.model:
                models.add(execution.model)

        passed_cases = sum(1 for result in case_results if result.passed)

        total_cases = len(case_results)
        failed_cases = total_cases - passed_cases

        pass_rate = passed_cases / total_cases
        aggregate_score = sum(case_scores) / total_cases

        metric_scores = {
            metric_name: round(
                sum(scores) / len(scores),
                4,
            )
            for metric_name, scores in metric_buckets.items()
            if scores
        }

        evaluator_versions = {
            "execution_success": "1.0.0",
            **{evaluator.name: evaluator.version for evaluator in self.evaluators},
        }

        completed_at = datetime.now(UTC)

        return ExperimentReport(
            experiment_id=(f"exp-{uuid4().hex[:12]}"),
            name=name.strip(),
            system=dataset.metadata.system,
            dataset_id=dataset.metadata.id,
            dataset_version=(dataset.metadata.version),
            started_at=started_at,
            completed_at=completed_at,
            passed=failed_cases == 0,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=round(pass_rate, 4),
            aggregate_score=round(
                aggregate_score,
                4,
            ),
            metric_scores=metric_scores,
            evaluator_versions=(evaluator_versions),
            total_latency_ms=total_latency_ms,
            total_tokens=total_tokens,
            total_cost_usd=round(
                total_cost_usd,
                6,
            ),
            application_versions=sorted(application_versions),
            prompt_versions=sorted(prompt_versions),
            models=sorted(models),
            cases=case_results,
        )

    async def _execute_case(
        self,
        case: EvaluationCase,
    ) -> ApplicationExecution:
        try:
            self.adapter.validate_case(case)
            return await self.adapter.execute(case)

        except Exception as error:
            return ApplicationExecution(
                case_id=case.id,
                system=case.system,
                success=False,
                error=(f"{type(error).__name__}: {error}"),
                metadata={
                    "experiment_runner_error": True,
                    "error_type": (type(error).__name__),
                },
            )
