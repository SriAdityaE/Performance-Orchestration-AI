from __future__ import annotations

from perf_orchestrator.config import ValidationThresholds
from perf_orchestrator.models.results import TestMetrics, ValidationResult


class MetricsValidator:
    def __init__(self, thresholds: ValidationThresholds) -> None:
        self._thresholds = thresholds

    def validate(
        self,
        metrics: TestMetrics,
        expected_throughput: float | None = None,
    ) -> ValidationResult:
        threshold_checks = {
            "error_rate": metrics.error_rate_pct <= self._thresholds.max_error_rate_pct,
            "p95": metrics.p95_response_ms <= self._thresholds.max_p95_ms,
            "p99": metrics.p99_response_ms <= self._thresholds.max_p99_ms,
            "throughput": metrics.throughput >= self._thresholds.min_throughput,
        }
        reasons = []
        if not threshold_checks["error_rate"]:
            reasons.append(
                f"Error rate {metrics.error_rate_pct:.2f}% exceeds {self._thresholds.max_error_rate_pct:.2f}%"
            )
        if not threshold_checks["p95"]:
            reasons.append(
                f"P95 {metrics.p95_response_ms:.2f} ms exceeds {self._thresholds.max_p95_ms} ms"
            )
        if not threshold_checks["p99"]:
            reasons.append(
                f"P99 {metrics.p99_response_ms:.2f} ms exceeds {self._thresholds.max_p99_ms} ms"
            )
        if not threshold_checks["throughput"]:
            reasons.append("Throughput must remain above zero")

        target_checks: dict[str, bool] = {}
        if expected_throughput is not None:
            met_target = metrics.throughput >= expected_throughput
            target_checks["expected_throughput"] = met_target
            if not met_target:
                reasons.append(
                    f"Throughput {metrics.throughput:.2f} req/sec missed target {expected_throughput:.2f} req/sec"
                )

        return ValidationResult(
            passed=not reasons,
            reasons=tuple(reasons),
            threshold_checks=threshold_checks,
            target_checks=target_checks,
        )