from __future__ import annotations

from dataclasses import dataclass

from perf_orchestrator.models.results import ComparisonDelta, ComparisonSummary, TestMetrics

_METRIC_DISPLAY_NAMES: dict[str, str] = {
    "throughput": "Throughput",
    "avg_response_ms": "Avg Response",
    "p95_response_ms": "P95 Response",
    "p99_response_ms": "P99 Response",
    "error_rate_pct": "Error Rate",
}

# Latency quantization / measurement-noise floor in milliseconds.
# A latency delta whose absolute change is below this floor is treated as
# noise regardless of its percentage value. JMeter reports per-sample times
# rounded to the millisecond, so at single-digit-ms scale a 1 ms tick produces
# misleading 30%+ "regressions" that are not real performance changes.
_LATENCY_NOISE_FLOOR_MS = 5.0

# Default tolerance (percentage) for declaring two runs comparable based on
# sample count. Two runs with sample counts differing by more than this
# percentage represent different load profiles and their deltas should not be
# interpreted as performance changes.
_PROFILE_SAMPLE_TOLERANCE_PCT = 20.0


@dataclass(frozen=True)
class ProfileCompatibility:
    """Result of a load-profile compatibility check between two runs."""

    comparable: bool
    reason: str | None = None


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
            absolute_change_ms = candidate_value - baseline_value
            if abs(absolute_change_ms) < _LATENCY_NOISE_FLOOR_MS:
                classification = "stable"
            elif delta_pct > 10:
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

    def assess_profile_compatibility(
        self,
        baseline_samples: int,
        candidate_samples: int,
        *,
        tolerance_pct: float = _PROFILE_SAMPLE_TOLERANCE_PCT,
    ) -> ProfileCompatibility:
        """Decide whether two runs share a comparable load profile.

        When sample counts differ by more than ``tolerance_pct`` the runs are
        not comparable: any throughput/latency delta is dominated by the
        load-profile change (different thread count, ramp, or duration) rather
        than by a real performance change. Callers should either skip
        comparison or annotate the report with the returned reason.
        """
        if baseline_samples <= 0 or candidate_samples <= 0:
            return ProfileCompatibility(
                comparable=False,
                reason="sample count missing or zero on one side",
            )
        delta_pct = abs(candidate_samples - baseline_samples) / baseline_samples * 100
        if delta_pct > tolerance_pct:
            return ProfileCompatibility(
                comparable=False,
                reason=(
                    f"sample count differs by {delta_pct:.1f}% "
                    f"(baseline={baseline_samples}, candidate={candidate_samples}); "
                    "comparison may reflect load-profile change rather than performance change"
                ),
            )
        return ProfileCompatibility(comparable=True, reason=None)