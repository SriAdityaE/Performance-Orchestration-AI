from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict

from perf_orchestrator.models.results import AggregateRow, ComparisonSummary, TestMetrics, ValidationResult


def _run_id_to_date_label(run_id: str) -> str:
    """Convert run-YYYYMMDDHHMMSS-hash to '2026-05-28 16:12', or return the raw ID on failure."""
    try:
        parts = run_id.split("-")
        if len(parts) >= 3 and len(parts[1]) == 14 and parts[1].isdigit():
            ts = parts[1]
            return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}"
    except Exception:
        pass
    return run_id


_COMPARISON_METRIC_FORMAT: dict[str, tuple[str, str]] = {
    "throughput": ("Throughput", " req/s"),
    "avg_response_ms": ("Avg Response Time", " ms"),
    "p95_response_ms": ("P95 Response Time", " ms"),
    "p99_response_ms": ("P99 Response Time", " ms"),
    "error_rate_pct": ("Error Rate", "%"),
}


class ReportBuilder:
    def build_single_run_report(
        self,
        *,
        test_name: str,
        environment_label: str,
        test_plan_path: str | None = None,
        metrics: TestMetrics,
        validation: ValidationResult,
        comparison_summary: ComparisonSummary | None = None,
        comparison_history: tuple[ComparisonSummary, ...] | None = None,
        best_run_recommendation: str | None = None,
        profile_compatibility_warning: str | None = None,
        custom_format: dict[str, object] | None = None,
    ) -> dict[str, object]:
        test_observations = self._build_test_observations(
            test_name=test_name,
            environment_label=environment_label,
            metrics=metrics,
            validation=validation,
            comparison_summary=comparison_summary,
            best_run_recommendation=best_run_recommendation,
            profile_compatibility_warning=profile_compatibility_warning,
        )
        transaction_names, aggregate_rows = self._build_single_run_aggregate_view(test_name, metrics)

        base = {
            "Test Summary": {
                "test_name": test_name,
                "environment": environment_label,
                "transactions_detected": len(transaction_names),
                "transaction_names": transaction_names,
                "transactions": metrics.transactions,
                "throughput": metrics.throughput,
                "jmeter_aggregate": [asdict(row) for row in aggregate_rows]
                if aggregate_rows
                else [
                    {
                        "label": test_name,
                        "samples": metrics.transactions,
                        "average_ms": metrics.avg_response_ms,
                        "median_ms": metrics.avg_response_ms,
                        "p90_ms": metrics.p95_response_ms,
                        "p95_ms": metrics.p95_response_ms,
                        "p99_ms": metrics.p99_response_ms,
                        "min_ms": metrics.avg_response_ms,
                        "max_ms": metrics.max_response_ms,
                        "error_pct": metrics.error_rate_pct,
                        "throughput_per_sec": metrics.throughput,
                    }
                ],
                "response_times": {
                    "avg_ms": metrics.avg_response_ms,
                    "p95_ms": metrics.p95_response_ms,
                    "p99_ms": metrics.p99_response_ms,
                    "max_ms": metrics.max_response_ms,
                },
                "error_rate_pct": metrics.error_rate_pct,
            },
            "Test Execution Summary": {
                "test_plan_path": test_plan_path,
                "duration_minutes": metrics.duration_minutes,
                "validation_passed": validation.passed,
                "threshold_checks": validation.threshold_checks,
                "target_checks": validation.target_checks,
                **(
                    {
                        "historical_comparison": {
                            "baseline": comparison_summary.baseline_label,
                            "candidate": comparison_summary.candidate_label,
                            "deltas": [
                                {
                                    "metric": delta.metric_name,
                                    "baseline": delta.baseline_value,
                                    "candidate": delta.candidate_value,
                                    "delta_pct": delta.delta_pct,
                                    "classification": delta.classification,
                                }
                                for delta in comparison_summary.deltas
                            ],
                            "recommendation": best_run_recommendation,
                        }
                    }
                    if comparison_summary
                    else {}
                ),
                **(
                    {
                        "historical_comparisons": [
                            {
                                "baseline": summary.baseline_label,
                                "candidate": summary.candidate_label,
                                "deltas": [
                                    {
                                        "metric": delta.metric_name,
                                        "baseline": delta.baseline_value,
                                        "candidate": delta.candidate_value,
                                        "delta_pct": delta.delta_pct,
                                        "classification": delta.classification,
                                    }
                                    for delta in summary.deltas
                                ],
                            }
                            for summary in comparison_history
                        ]
                    }
                    if comparison_history
                    else {}
                ),
            },
            "Detailed Observations and Analysis": test_observations,
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

    def _build_single_run_aggregate_view(
        self,
        test_name: str,
        metrics: TestMetrics,
    ) -> tuple[list[str], list[AggregateRow]]:
        rows = list(metrics.aggregate_rows)
        if not rows:
            return list(metrics.transaction_names), []

        non_total = [row for row in rows if row.label != "TOTAL"]
        total_rows = [row for row in rows if row.label == "TOTAL"]

        # When JMeter emits both parent transaction controller sample and child sampler rows,
        # suppress the parent row from presentation so transaction-level insights stay visible.
        if len(non_total) > 1:
            filtered = [row for row in non_total if row.label.strip() != test_name.strip()]
            if filtered:
                non_total = filtered

        transaction_names = [row.label for row in non_total]
        return transaction_names, [*non_total, *total_rows]

    def build_comparison_report(
        self,
        *,
        current_rounds: tuple[tuple[str, TestMetrics], ...],
        comparison: ComparisonSummary,
        recommendation: str,
        extra_observations: tuple[str, ...] | None = None,
        custom_format: dict[str, object] | None = None,
    ) -> dict[str, object]:
        merged_observations: list[str] = []
        if extra_observations:
            merged_observations.extend(str(item) for item in extra_observations)
        merged_observations.extend(comparison.observations)
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
                "observations": merged_observations,
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

    def _build_test_observations(
        self,
        *,
        test_name: str,
        environment_label: str,
        metrics: TestMetrics,
        validation: ValidationResult,
        comparison_summary: ComparisonSummary | None,
        best_run_recommendation: str | None,
        profile_compatibility_warning: str | None = None,
    ) -> list[str]:
        summary = (
            f"Executive Summary: Run '{test_name}' on {environment_label} processed "
            f"{metrics.transactions} transactions with throughput {metrics.throughput:.2f}/s."
        )
        latency = (
            f"Latency Profile: avg={metrics.avg_response_ms:.2f} ms, "
            f"p95={metrics.p95_response_ms:.2f} ms, p99={metrics.p99_response_ms:.2f} ms, "
            f"max={metrics.max_response_ms:.2f} ms."
        )
        reliability = f"Reliability: error rate is {metrics.error_rate_pct:.2f}%."
        tail_risk = (
            f"Tail Latency Risk: p99={metrics.p99_response_ms:.2f} ms and max={metrics.max_response_ms:.2f} ms "
            "indicate outlier response-time exposure under this workload."
        )
        max_impact = (
            "Peak Response Impact: elevated max response time can cause intermittent user delays "
            "even when average latency appears healthy."
        )

        reasons = list(validation.reasons) or ["No threshold violations were reported."]
        reason_lines = [f"Test Observation: {reason}" for reason in reasons]

        comparison_lines: list[str] = []
        if comparison_summary:
            baseline_date = _run_id_to_date_label(comparison_summary.baseline_label)
            candidate_date = _run_id_to_date_label(comparison_summary.candidate_label)
            comparison_lines.append(
                f"Run Comparison — Previous run ({baseline_date}) vs. Current run ({candidate_date}):"
            )
            if profile_compatibility_warning:
                comparison_lines.append(
                    f"⚠ Profile advisory: {profile_compatibility_warning}"
                )
            for delta in comparison_summary.deltas:
                label, unit = _COMPARISON_METRIC_FORMAT.get(
                    delta.metric_name, (delta.metric_name, "")
                )
                baseline_fmt = f"{delta.baseline_value:.2f}{unit}"
                candidate_fmt = f"{delta.candidate_value:.2f}{unit}"
                if delta.classification == "stable":
                    change_desc = "stable"
                elif delta.classification == "improvement":
                    change_desc = f"improved {abs(delta.delta_pct):.0f}%"
                elif delta.classification == "regression":
                    change_desc = f"regressed {abs(delta.delta_pct):.0f}%"
                else:
                    change_desc = "inconclusive"
                comparison_lines.append(
                    f"{label}: {baseline_fmt} \u2192 {candidate_fmt}  ({change_desc})"
                )
        return [
            summary,
            latency,
            reliability,
            tail_risk,
            max_impact,
            *reason_lines,
            *comparison_lines,
        ]