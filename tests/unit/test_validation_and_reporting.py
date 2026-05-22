from __future__ import annotations

from perf_orchestrator.config import ValidationThresholds
from perf_orchestrator.models.results import TestMetrics
from perf_orchestrator.services.comparator import MetricsComparator
from perf_orchestrator.services.report_builder import ReportBuilder
from perf_orchestrator.services.validator import MetricsValidator
import pytest


def test_metrics_validator_passes_default_thresholds() -> None:
    validator = MetricsValidator(ValidationThresholds())
    metrics = TestMetrics(
        transactions=1000,
        throughput=42.0,
        avg_response_ms=100,
        p95_response_ms=200,
        p99_response_ms=250,
        max_response_ms=400,
        error_rate_pct=0.0,
        duration_minutes=60,
    )

    result = validator.validate(metrics, expected_throughput=40.0)

    assert result.passed is True
    assert result.target_checks["expected_throughput"] is True


def test_metrics_comparator_flags_regression_when_latency_rises() -> None:
    comparator = MetricsComparator()
    baseline = TestMetrics(1000, 100.0, 2, 3, 5, 50, 0.0, 60)
    candidate = TestMetrics(1005, 95.0, 2.5, 4.0, 6.0, 60, 0.0, 60)

    summary = comparator.compare("round-1", baseline, "round-2", candidate)

    classifications = {delta.metric_name: delta.classification for delta in summary.deltas}
    assert classifications["throughput"] == "stable"
    assert classifications["p95_response_ms"] == "regression"
    assert classifications["p99_response_ms"] == "regression"


def test_report_builder_uses_required_single_run_sections() -> None:
    validator = MetricsValidator(ValidationThresholds())
    builder = ReportBuilder()
    metrics = TestMetrics(1200, 55.0, 120, 180, 240, 500, 0.0, 30)
    validation = validator.validate(metrics)

    report = builder.build_single_run_report(
        test_name="load-test",
        environment_label="vm",
        metrics=metrics,
        validation=validation,
    )

    assert set(report) == {
        "Test Summary",
        "Test Execution Summary",
        "Detailed Observations and Analysis",
    }


def test_report_builder_applies_custom_aliases_without_losing_required_sections() -> None:
    validator = MetricsValidator(ValidationThresholds())
    builder = ReportBuilder()
    metrics = TestMetrics(1200, 55.0, 120, 180, 240, 500, 0.0, 30)
    validation = validator.validate(metrics)

    report = builder.build_single_run_report(
        test_name="load-test",
        environment_label="vm",
        metrics=metrics,
        validation=validation,
        custom_format={
            "title": "Custom Report",
            "section_order": [
                "Test Execution Summary",
                "Test Summary",
                "Detailed Observations and Analysis",
            ],
            "section_aliases": {
                "Test Execution Summary": "Execution",
                "Test Summary": "Summary",
            },
        },
    )

    assert list(report.keys())[0] == "Title"
    assert "Execution" in report
    assert "Summary" in report
    assert "Detailed Observations and Analysis" in report


def test_report_builder_rejects_custom_section_order_missing_required_sections() -> None:
    validator = MetricsValidator(ValidationThresholds())
    builder = ReportBuilder()
    metrics = TestMetrics(1200, 55.0, 120, 180, 240, 500, 0.0, 30)
    validation = validator.validate(metrics)

    with pytest.raises(ValueError):
        builder.build_single_run_report(
            test_name="load-test",
            environment_label="vm",
            metrics=metrics,
            validation=validation,
            custom_format={"section_order": ["Test Summary"]},
        )