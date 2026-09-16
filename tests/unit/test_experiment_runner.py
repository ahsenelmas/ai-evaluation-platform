import pytest

from app.adapters.base import ApplicationAdapter
from app.domain.models import (
    ApplicationExecution,
    DatasetManifestEntry,
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    TokenUsage,
)
from app.engine.experiment_runner import (
    ExperimentRunner,
)


class FakeAdapter(ApplicationAdapter):
    def __init__(
        self,
        system: str = "demo-system",
    ) -> None:
        self.system = system

    async def execute(
        self,
        case: EvaluationCase,
    ) -> ApplicationExecution:
        if case.id == "case-2":
            raise RuntimeError("Application is unavailable.")

        return ApplicationExecution(
            case_id=case.id,
            system=case.system,
            output={
                "answer": case.input["answer"],
            },
            success=True,
            latency_ms=12,
            token_usage=TokenUsage(
                input_tokens=2,
                output_tokens=1,
                total_tokens=3,
            ),
            estimated_cost=0.01,
            model="fake-model",
            prompt_version="prompt-v1",
            application_version="app-v1",
        )


class ExpectedAnswerEvaluator:
    name = "expected_answer"
    version = "1.0.0"

    async def evaluate(
        self,
        case: EvaluationCase,
        execution: ApplicationExecution,
    ) -> EvaluationResult:
        actual = execution.output.get("answer")
        expected = case.expected_output.get("answer")

        passed = actual == expected

        return EvaluationResult(
            evaluator=self.name,
            evaluator_version=self.version,
            score=1.0 if passed else 0.0,
            value=passed,
            passed=passed,
            reason=("Answer matched." if passed else "Answer did not match."),
        )


def create_dataset(
    *,
    include_failing_case: bool = False,
    system: str = "demo-system",
) -> EvaluationDataset:
    cases = [
        EvaluationCase(
            id="case-1",
            system=system,
            input={"answer": "Paris"},
            expected_output={"answer": "Paris"},
        )
    ]

    if include_failing_case:
        cases.append(
            EvaluationCase(
                id="case-2",
                system=system,
                input={"answer": "Berlin"},
                expected_output={"answer": "Berlin"},
            )
        )

    return EvaluationDataset(
        metadata=DatasetManifestEntry(
            id="demo-dataset",
            system=system,
            version="1.0.0",
            file_path="unused.jsonl",
            case_count=len(cases),
        ),
        cases=cases,
    )


@pytest.mark.asyncio
async def test_experiment_aggregates_results():
    runner = ExperimentRunner(
        adapter=FakeAdapter(),
        evaluators=[ExpectedAnswerEvaluator()],  # type: ignore
    )

    report = await runner.run(
        name="Successful experiment",
        dataset=create_dataset(),
    )

    assert report.passed is True
    assert report.total_cases == 1
    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert report.pass_rate == 1.0
    assert report.aggregate_score == 1.0

    assert report.metric_scores == {
        "execution_success": 1.0,
        "expected_answer": 1.0,
    }

    assert report.total_latency_ms == 12
    assert report.total_tokens == 3
    assert report.total_cost_usd == 0.01

    assert report.models == ["fake-model"]
    assert report.prompt_versions == ["prompt-v1"]
    assert report.application_versions == ["app-v1"]


@pytest.mark.asyncio
async def test_experiment_captures_execution_failure():
    runner = ExperimentRunner(
        adapter=FakeAdapter(),
        evaluators=[ExpectedAnswerEvaluator()],  # type: ignore
    )

    report = await runner.run(
        name="Partially failing experiment",
        dataset=create_dataset(include_failing_case=True),
    )

    assert report.passed is False
    assert report.total_cases == 2
    assert report.passed_cases == 1
    assert report.failed_cases == 1
    assert report.pass_rate == 0.5
    assert report.aggregate_score == 0.5

    assert report.metric_scores["execution_success"] == 0.5

    failed_case = report.cases[1]

    assert failed_case.passed is False
    assert failed_case.execution.success is False
    assert "RuntimeError" in failed_case.execution.error  # type: ignore


@pytest.mark.asyncio
async def test_experiment_rejects_wrong_adapter():
    runner = ExperimentRunner(
        adapter=FakeAdapter(system="another-system"),
        evaluators=[ExpectedAnswerEvaluator()],  # type: ignore
    )

    with pytest.raises(
        ValueError,
        match="cannot run dataset",
    ):
        await runner.run(
            name="Wrong adapter experiment",
            dataset=create_dataset(),
        )
