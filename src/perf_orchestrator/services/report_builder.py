from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict

from perf_orchestrator.models.results import ComparisonSummary, TestMetrics, ValidationResult


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
        best_run_recommendation: str | None = None,
        custom_format: dict[str, object] | None = None,
    ) -> dict[str, object]:
        test_observations = self._build_test_observations(
            test_name=test_name,
            environment_label=environment_label,
            metrics=metrics,
            validation=validation,
            comparison_summary=comparison_summary,
            best_run_recommendation=best_run_recommendation,
        )

        base = {
            "Test Summary": {
                "test_name": test_name,
                "environment": environment_label,
                "transactions_detected": len(metrics.transaction_names),
                "transaction_names": list(metrics.transaction_names),
                "transactions": metrics.transactions,
                "throughput": metrics.throughput,
                "jmeter_aggregate": [asdict(row) for row in metrics.aggregate_rows]
                if metrics.aggregate_rows
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

    def _build_test_observations(
        self,
        *,
        test_name: str,
        environment_label: str,
        metrics: TestMetrics,
        validation: ValidationResult,
        comparison_summary: ComparisonSummary | None,
        best_run_recommendation: str | None,
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

        if validation.passed:
            decision = (
                "Stakeholder Decision: Validation passed. Recommendation is to proceed to next stage "
                "while continuing normal trend monitoring."
            )
        else:
            decision = (
                "Stakeholder Decision: Validation failed. Recommendation is to hold release for this scope "
                "until regressions are triaged and corrected."
            )

        reasons = list(validation.reasons) or ["No threshold violations were reported."]
        reason_lines = [f"Test Observation: {reason}" for reason in reasons]

        comparison_lines: list[str] = []
        if comparison_summary:
            comparison_lines.append(
                f"Historical Comparison: Baseline run '{comparison_summary.baseline_label}' vs current run '{comparison_summary.candidate_label}'."
            )
            comparison_lines.extend(
                f"Test Observation: {observation}" for observation in comparison_summary.observations
            )
        if best_run_recommendation:
            comparison_lines.append(f"Best Run Recommendation: {best_run_recommendation}")

        prompt_line = (
            "Analysis Prompt Used: You are a senior performance architect. Analyze the run metrics, "
            "identify business impact, and provide production-readiness guidance without requiring manual rewriting."
        )

        return [
            summary,
            latency,
            reliability,
            tail_risk,
            max_impact,
            *reason_lines,
            *comparison_lines,
            decision,
            prompt_line,
        ]