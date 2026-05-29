from __future__ import annotations

from perf_orchestrator.models.results import ComparisonDelta, ComparisonSummary, TestMetrics

_METRIC_DISPLAY_NAMES: dict[str, str] = {
    "throughput": "Throughput",
    "avg_response_ms": "Avg Response",
    "p95_response_ms": "P95 Response",
    "p99_response_ms": "P99 Response",
    "error_rate_pct": "Error Rate",
}


class MetricsComparator:
    def compare(
        self,
        baseline_label: str,
        baseline: TestMetrics,
        candidate_label: str,
        candidate: TestMetrics,
    ) -> ComparisonSummary:
        deltas = (
            self._delta("throughput", baseline.throughput, candidate.throughput, higher_is_better=True),
            self._delta("avg_response_ms", baseline.avg_response_ms, candidate.avg_response_ms, higher_is_better=False),
            self._delta("p95_response_ms", baseline.p95_response_ms, candidate.p95_response_ms, higher_is_better=False),
            self._delta("p99_response_ms", baseline.p99_response_ms, candidate.p99_response_ms, higher_is_better=False),
            self._delta("error_rate_pct", baseline.error_rate_pct, candidate.error_rate_pct, higher_is_better=False),
        )
        observations = tuple(self._observation(delta) for delta in deltas)
        return ComparisonSummary(
            baseline_label=baseline_label,
            candidate_label=candidate_label,
            deltas=deltas,
            observations=observations,
        )

    def _delta(
        self,
        metric_name: str,
        baseline_value: float,
        candidate_value: float,
        *,
        higher_is_better: bool,
    ) -> ComparisonDelta:
        if baseline_value == 0:
            delta_pct = 0.0
        else:
            delta_pct = ((candidate_value - baseline_value) / baseline_value) * 100

        classification = "inconclusive"
        if metric_name == "throughput":
            if delta_pct < -5:
                classification = "regression"
            elif delta_pct > 5:
                classification = "improvement"
            else:
                classification = "stable"
        elif metric_name in {"avg_response_ms", "p95_response_ms", "p99_response_ms"}:
            if delta_pct > 10:
                classification = "regression"
            elif delta_pct < -10:
                classification = "improvement"
            else:
                classification = "stable"
        elif metric_name == "error_rate_pct":
            absolute_change = candidate_value - baseline_value
            if absolute_change > 0.5:
                classification = "regression"
            elif absolute_change < -0.5:
                classification = "improvement"
            else:
                classification = "stable"
        elif higher_is_better:
            classification = "improvement" if delta_pct > 0 else "regression"
        else:
            classification = "improvement" if delta_pct < 0 else "regression"

        return ComparisonDelta(
            metric_name=metric_name,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            delta_pct=delta_pct,
            classification=classification,
        )

    def _observation(self, delta: ComparisonDelta) -> str:
        display = _METRIC_DISPLAY_NAMES.get(delta.metric_name, delta.metric_name)
        if delta.classification == "stable":
            return f"{display}: remained stable ({delta.delta_pct:.2f}% change)"
        if delta.classification == "improvement":
            return f"{display}: improved by {abs(delta.delta_pct):.2f}%"
        if delta.classification == "regression":
            return f"{display}: regressed by {abs(delta.delta_pct):.2f}%"
        return f"{display}: comparison is inconclusive"