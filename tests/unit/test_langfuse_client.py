from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.domain.models import (
    ApplicationExecution,
    CaseEvaluationReport,
    EvaluationResult,
    ExperimentCaseResult,
    ExperimentReport,
)
from app.integrations.langfuse_client import (
    LangfuseExperimentPublisher,
)


class FakeObservation:
    def __init__(
        self,
        name: str,
    ) -> None:
        self.name = name

        self.updates: list[dict[str, Any]] = []

        self.scores: list[dict[str, Any]] = []

        self.trace_scores: list[dict[str, Any]] = []

    def update(
        self,
        **kwargs: Any,
    ) -> None:
        self.updates.append(kwargs)

    def score(
        self,
        **kwargs: Any,
    ) -> None:
        self.scores.append(kwargs)

    def score_trace(
        self,
        **kwargs: Any,
    ) -> None:
        self.trace_scores.append(kwargs)


class FakeLangfuseClient:
    def __init__(self) -> None:
        self.observations: list[FakeObservation] = []

        self.flushed = False

    @contextmanager
    def start_as_current_observation(
        self,
        **kwargs: Any,
    ) -> Iterator[FakeObservation]:
        observation = FakeObservation(name=kwargs["name"])

        self.observations.append(observation)

        yield observation

    def auth_check(self) -> bool:
        return True

    def flush(self) -> None:
        self.flushed = True


class BrokenLangfuseClient:
    def start_as_current_observation(
        self,
        **kwargs: Any,
    ) -> Any:
        raise RuntimeError("Langfuse is unavailable.")

    def auth_check(self) -> bool:
        raise RuntimeError("Langfuse is unavailable.")

    def flush(self) -> None:
        raise RuntimeError("Langfuse is unavailable.")


def create_report() -> ExperimentReport:
    execution = ApplicationExecution(
        case_id="case-1",
        system="demo-system",
        output={"answer": "Paris"},
        success=True,
        latency_ms=100,
        estimated_cost=0.002,
        model="test-model",
        prompt_version="prompt-v1",
        application_version="app-v1",
    )

    evaluation_result = EvaluationResult(
        evaluator="exact_match",
        evaluator_version="1.0.0",
        score=1.0,
        value=True,
        passed=True,
        reason="Values matched.",
    )

    evaluation = CaseEvaluationReport(
        case_id="case-1",
        system="demo-system",
        passed=True,
        aggregate_score=1.0,
        evaluator_count=1,
        passed_count=1,
        failed_count=0,
        results=[evaluation_result],
    )

    case_result = ExperimentCaseResult(
        case_id="case-1",
        passed=True,
        input={"question": ("Capital of France?")},
        expected_output={"answer": "Paris"},
        case_metadata={"category": "geography"},
        execution=execution,
        evaluation=evaluation,
    )

    timestamp = datetime(
        2026,
        9,
        16,
        12,
        0,
        tzinfo=UTC,
    )

    return ExperimentReport(
        experiment_id="exp-langfuse-test",
        name="Langfuse test",
        system="demo-system",
        dataset_id="demo-dataset",
        dataset_version="1.0.0",
        started_at=timestamp,
        completed_at=timestamp,
        passed=True,
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        pass_rate=1.0,
        aggregate_score=1.0,
        metric_scores={"exact_match": 1.0},
        evaluator_versions={"exact_match": "1.0.0"},
        total_latency_ms=100,
        total_tokens=0,
        total_cost_usd=0.002,
        models=["test-model"],
        prompt_versions=["prompt-v1"],
        application_versions=["app-v1"],
        cases=[case_result],
    )


def test_publisher_is_disabled_without_credentials():
    settings = Settings(
        _env_file=None,
        langfuse_public_key=None,
        langfuse_secret_key=None,
    )

    publisher = LangfuseExperimentPublisher.from_settings(settings)

    assert publisher.enabled is False
    assert publisher.check_connection() is False

    assert publisher.publish(create_report()) is False


def test_publisher_sends_trace_cases_and_scores():
    client = FakeLangfuseClient()

    publisher = LangfuseExperimentPublisher(client=client)

    assert publisher.enabled is True
    assert publisher.check_connection() is True

    published = publisher.publish(create_report())

    assert published is True
    assert client.flushed is True
    assert len(client.observations) == 2

    experiment = client.observations[0]
    case = client.observations[1]

    assert experiment.name == ("evaluation-experiment")

    assert case.name == "evaluation-case"

    assert len(experiment.updates) == 1
    assert len(case.updates) == 1

    trace_score_names = {score["name"] for score in experiment.trace_scores}

    assert "experiment_passed" in (trace_score_names)

    assert "aggregate_score" in (trace_score_names)

    assert "pass_rate" in (trace_score_names)

    assert "metric_exact_match" in (trace_score_names)

    case_score_names = {score["name"] for score in case.scores}

    assert case_score_names == {
        "execution_success",
        "case_passed",
        "exact_match",
    }


def test_publisher_does_not_break_on_failure():
    publisher = LangfuseExperimentPublisher(client=BrokenLangfuseClient())

    assert publisher.enabled is True

    assert publisher.check_connection() is False

    published = publisher.publish(create_report())

    assert published is False
