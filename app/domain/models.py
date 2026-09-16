from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvaluationCase(BaseModel):
    id: str = Field(
        min_length=1,
        description="Stable ID of the evaluation case.",
    )

    system: str = Field(
        min_length=1,
        description="Registered AI system identifier.",
    )

    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Input supplied to the AI application.",
    )

    expected_output: dict[str, Any] = Field(
        default_factory=dict,
        description="Expected answer, decision, fields or sources.",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Category, difficulty and other case information.",
    )


class TokenUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ApplicationExecution(BaseModel):
    case_id: str
    system: str

    output: dict[str, Any] = Field(default_factory=dict)
    retrieved_context: list[dict[str, Any]] = Field(default_factory=list)

    success: bool = True
    error: str | None = None

    latency_ms: int = Field(default=0, ge=0)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: float = Field(default=0.0, ge=0)

    model: str | None = None
    prompt_version: str | None = None
    application_version: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    evaluator: str
    evaluator_version: str = "1.0.0"

    score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    value: bool | str | None = None
    passed: bool
    reason: str

    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseEvaluationReport(BaseModel):
    case_id: str
    system: str

    passed: bool
    aggregate_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    evaluator_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)

    results: list[EvaluationResult] = Field(
        default_factory=list,
    )


class DatasetManifestEntry(BaseModel):
    id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    version: str = Field(min_length=1)
    file_path: str = Field(min_length=1)

    description: str = ""
    released: bool = False
    checksum_sha256: str | None = None
    case_count: int = Field(ge=0)


class EvaluationDataset(BaseModel):
    metadata: DatasetManifestEntry
    cases: list[EvaluationCase]


class ExperimentCaseResult(BaseModel):
    """Execution and evaluation results for one dataset case."""

    case_id: str
    passed: bool

    input: dict[str, Any] = Field(default_factory=dict)

    expected_output: dict[str, Any] = Field(default_factory=dict)

    case_metadata: dict[str, Any] = Field(default_factory=dict)

    execution: ApplicationExecution
    evaluation: CaseEvaluationReport


class ExperimentReport(BaseModel):
    """Aggregated result of evaluating an application against a dataset."""

    experiment_id: str
    name: str
    system: str

    dataset_id: str
    dataset_version: str

    started_at: datetime
    completed_at: datetime

    passed: bool
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    aggregate_score: float

    metric_scores: dict[str, float] = Field(default_factory=dict)
    evaluator_versions: dict[str, str] = Field(default_factory=dict)

    total_latency_ms: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    application_versions: list[str] = Field(default_factory=list)
    prompt_versions: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)

    cases: list[ExperimentCaseResult] = Field(default_factory=list)
