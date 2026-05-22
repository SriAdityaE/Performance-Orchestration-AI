from __future__ import annotations

from collections import OrderedDict

from perf_orchestrator.models.results import ComparisonSummary, TestMetrics, ValidationResult


class ReportBuilder:
    def build_single_run_report(
        self,
        *,
        test_name: str,
        environment_label: str,
        metrics: TestMetrics,
        validation: ValidationResult,
        custom_format: dict[str, object] | None = None,
    ) -> dict[str, object]:
        base = {
            "Test Summary": {
                "test_name": test_name,
                "environment": environment_label,
                "transactions": metrics.transactions,
                "throughput": metrics.throughput,
                "response_times": {
                    "avg_ms": metrics.avg_response_ms,
                    "p95_ms": metrics.p95_response_ms,
                    "p99_ms": metrics.p99_response_ms,
                    "max_ms": metrics.max_response_ms,
                },
                "error_rate_pct": metrics.error_rate_pct,
            },
            "Test Execution Summary": {
                "duration_minutes": metrics.duration_minutes,
                "validation_passed": validation.passed,
                "threshold_checks": validation.threshold_checks,
                "target_checks": validation.target_checks,
            },
            "Detailed Observations and Analysis": list(validation.reasons) or ["All validation thresholds passed"],
        }
        return self._apply_custom_format(
            base,
            custom_format,
            required_sections={
                "Test Summary",
                "Test Execution Summary",
                "Detailed Observations and Analysis",
            },
        )

    def build_comparison_report(
        self,
        *,
        current_rounds: tuple[tuple[str, TestMetrics], tuple[str, TestMetrics]],
        comparison: ComparisonSummary,
        recommendation: str,
        custom_format: dict[str, object] | None = None,
    ) -> dict[str, object]:
        base = {
            "Today's Test Results Summary": {
                name: {
                    "transactions": metrics.transactions,
                    "throughput": metrics.throughput,
                    "avg_ms": metrics.avg_response_ms,
                    "p95_ms": metrics.p95_response_ms,
                    "p99_ms": metrics.p99_response_ms,
                    "max_ms": metrics.max_response_ms,
                    "error_rate_pct": metrics.error_rate_pct,
                }
                for name, metrics in current_rounds
            },
            "Test Execution Summary": {
                "baseline": comparison.baseline_label,
                "candidate": comparison.candidate_label,
                "observations": list(comparison.observations),
            },
            "Detailed Observations and Analysis": [
                {
                    "metric": delta.metric_name,
                    "baseline": delta.baseline_value,
                    "candidate": delta.candidate_value,
                    "delta_pct": delta.delta_pct,
                    "classification": delta.classification,
                }
                for delta in comparison.deltas
            ],
            "Recommendation or Conclusion": recommendation,
        }
        return self._apply_custom_format(
            base,
            custom_format,
            required_sections={
                "Today's Test Results Summary",
                "Test Execution Summary",
                "Detailed Observations and Analysis",
                "Recommendation or Conclusion",
            },
        )

    def _apply_custom_format(
        self,
        payload: dict[str, object],
        custom_format: dict[str, object] | None,
        *,
        required_sections: set[str],
    ) -> dict[str, object]:
        if not custom_format:
            return payload

        section_order_raw = custom_format.get("section_order")
        section_aliases = custom_format.get("section_aliases", {})
        title = custom_format.get("title")

        if section_order_raw is None:
            section_order = list(payload.keys())
        else:
            section_order = [str(item) for item in section_order_raw]
            missing_required = [section for section in required_sections if section not in section_order]
            if missing_required:
                raise ValueError(
                    "custom section_order must include required sections: "
                    + ", ".join(sorted(missing_required))
                )

        ordered: OrderedDict[str, object] = OrderedDict()
        if title:
            ordered["Title"] = str(title)

        used = set()
        for section in section_order:
            if section in payload:
                alias = str(section_aliases.get(section, section))
                ordered[alias] = payload[section]
                used.add(section)

        for section, value in payload.items():
            if section not in used:
                alias = str(section_aliases.get(section, section))
                ordered[alias] = value

        return dict(ordered)