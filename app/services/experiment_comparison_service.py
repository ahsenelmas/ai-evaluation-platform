from app.domain.models import (
    ExperimentComparison,
    ExperimentReport,
    MetricComparison,
)


class IncompatibleExperimentsError(ValueError):
    """Raised when two experiments cannot be compared."""


class ExperimentComparisonService:
    """Compare a candidate experiment with a stored baseline."""

    def compare(
        self,
        baseline: ExperimentReport,
        candidate: ExperimentReport,
        score_tolerance: float = 0.0,
        max_latency_increase_percent: float = 20.0,
    ) -> ExperimentComparison:
        self._validate_thresholds(
            score_tolerance=score_tolerance,
            max_latency_increase_percent=(
                max_latency_increase_percent
            ),
        )

        self._validate_compatibility(
            baseline=baseline,
            candidate=candidate,
        )

        metric_comparisons = self._compare_metrics(
            baseline=baseline,
            candidate=candidate,
            score_tolerance=score_tolerance,
        )

        regressed_metrics = [
            comparison.metric
            for comparison in metric_comparisons
            if comparison.regression
        ]

        improved_metrics = [
            comparison.metric
            for comparison in metric_comparisons
            if comparison.status == "improved"
        ]

        pass_rate_change = self._round(
            candidate.pass_rate - baseline.pass_rate
        )

        aggregate_score_change = self._round(
            candidate.aggregate_score
            - baseline.aggregate_score
        )

        baseline_average_latency = self._average_latency(
            baseline
        )

        candidate_average_latency = self._average_latency(
            candidate
        )

        latency_change_percent = (
            self._percentage_change(
                baseline=baseline_average_latency,
                candidate=candidate_average_latency,
            )
        )

        regression_reasons: list[str] = []

        if pass_rate_change < -score_tolerance:
            regression_reasons.append(
                "Candidate pass rate decreased beyond the "
                "configured score tolerance."
            )

        if aggregate_score_change < -score_tolerance:
            regression_reasons.append(
                "Candidate aggregate score decreased beyond "
                "the configured score tolerance."
            )

        if regressed_metrics:
            regression_reasons.append(
                "Regressed metrics: "
                + ", ".join(regressed_metrics)
                + "."
            )

        if (
            latency_change_percent is not None
            and latency_change_percent
            > max_latency_increase_percent
        ):
            regression_reasons.append(
                "Average latency increased by "
                f"{latency_change_percent:.2f}%, exceeding "
                "the configured limit of "
                f"{max_latency_increase_percent:.2f}%."
            )

        if baseline.passed and not candidate.passed:
            regression_reasons.append(
                "The baseline passed but the candidate failed."
            )

        return ExperimentComparison(
            baseline_experiment_id=(
                baseline.experiment_id
            ),
            candidate_experiment_id=(
                candidate.experiment_id
            ),
            system=baseline.system,
            dataset_id=baseline.dataset_id,
            baseline_dataset_version=(
                baseline.dataset_version
            ),
            candidate_dataset_version=(
                candidate.dataset_version
            ),
            baseline_passed=baseline.passed,
            candidate_passed=candidate.passed,
            baseline_pass_rate=baseline.pass_rate,
            candidate_pass_rate=candidate.pass_rate,
            pass_rate_change=pass_rate_change,
            baseline_aggregate_score=(
                baseline.aggregate_score
            ),
            candidate_aggregate_score=(
                candidate.aggregate_score
            ),
            aggregate_score_change=(
                aggregate_score_change
            ),
            baseline_average_latency_ms=(
                baseline_average_latency
            ),
            candidate_average_latency_ms=(
                candidate_average_latency
            ),
            latency_change_percent=(
                latency_change_percent
            ),
            score_tolerance=score_tolerance,
            max_latency_increase_percent=(
                max_latency_increase_percent
            ),
            metrics=metric_comparisons,
            regressed_metrics=regressed_metrics,
            improved_metrics=improved_metrics,
            regression_reasons=regression_reasons,
            regression_detected=bool(
                regression_reasons
            ),
        )

    def _compare_metrics(
        self,
        baseline: ExperimentReport,
        candidate: ExperimentReport,
        score_tolerance: float,
    ) -> list[MetricComparison]:
        metric_names = sorted(
            set(baseline.metric_scores)
            | set(candidate.metric_scores)
        )

        comparisons: list[MetricComparison] = []

        for metric_name in metric_names:
            baseline_score = baseline.metric_scores.get(
                metric_name
            )

            candidate_score = candidate.metric_scores.get(
                metric_name
            )

            if baseline_score is None:
                comparisons.append(
                    MetricComparison(
                        metric=metric_name,
                        baseline_score=None,
                        candidate_score=candidate_score,
                        status="added",
                    )
                )
                continue

            if candidate_score is None:
                comparisons.append(
                    MetricComparison(
                        metric=metric_name,
                        baseline_score=baseline_score,
                        candidate_score=None,
                        status="missing",
                        regression=True,
                    )
                )
                continue

            absolute_change = self._round(
                candidate_score - baseline_score
            )

            relative_change = self._percentage_change(
                baseline=baseline_score,
                candidate=candidate_score,
            )

            if absolute_change < -score_tolerance:
                comparison_status = "regressed"
                regression = True

            elif absolute_change > score_tolerance:
                comparison_status = "improved"
                regression = False

            else:
                comparison_status = "unchanged"
                regression = False

            comparisons.append(
                MetricComparison(
                    metric=metric_name,
                    baseline_score=baseline_score,
                    candidate_score=candidate_score,
                    absolute_change=absolute_change,
                    relative_change_percent=(
                        relative_change
                    ),
                    status=comparison_status,
                    regression=regression,
                )
            )

        return comparisons

    @staticmethod
    def _validate_compatibility(
        baseline: ExperimentReport,
        candidate: ExperimentReport,
    ) -> None:
        if baseline.system != candidate.system:
            raise IncompatibleExperimentsError(
                "Experiments use different systems: "
                f"'{baseline.system}' and "
                f"'{candidate.system}'."
            )

        if baseline.dataset_id != candidate.dataset_id:
            raise IncompatibleExperimentsError(
                "Experiments use different datasets: "
                f"'{baseline.dataset_id}' and "
                f"'{candidate.dataset_id}'."
            )

        if baseline.dataset_version != candidate.dataset_version:
            raise IncompatibleExperimentsError(
                "Experiments use different dataset versions: "
                f"'{baseline.dataset_version}' and "
                f"'{candidate.dataset_version}'."
            )

    @staticmethod
    def _validate_thresholds(
        score_tolerance: float,
        max_latency_increase_percent: float,
    ) -> None:
        if not 0.0 <= score_tolerance <= 1.0:
            raise ValueError(
                "Score tolerance must be between 0 and 1."
            )

        if max_latency_increase_percent < 0.0:
            raise ValueError(
                "Maximum latency increase percentage "
                "cannot be negative."
            )

    @staticmethod
    def _average_latency(
        report: ExperimentReport,
    ) -> float:
        if report.total_cases == 0:
            return 0.0

        return round(
            report.total_latency_ms / report.total_cases,
            2,
        )

    @staticmethod
    def _percentage_change(
        baseline: float,
        candidate: float,
    ) -> float | None:
        if baseline == 0:
            return None

        return round(
            ((candidate - baseline) / baseline) * 100,
            2,
        )

    @staticmethod
    def _round(
        value: float,
    ) -> float:
        return round(value, 6)
