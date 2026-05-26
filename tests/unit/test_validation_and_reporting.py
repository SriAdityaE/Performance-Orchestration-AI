from __future__ import annotations

from perf_orchestrator.config import ValidationThresholds
from perf_orchestrator.models.results import TestMetrics
from perf_orchestrator.services.jmeter_parser import parse_jmeter_csv
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


def test_parse_jmeter_csv_builds_per_transaction_aggregate_rows(tmp_path) -> None:
    result_file = tmp_path / "result.jtl"
    result_file.write_text(
        "timeStamp,elapsed,label,responseCode,responseMessage,threadName,success\n"
        "1716400000000,10,Txn_A,200,OK,thread-1,true\n"
        "1716400001000,12,Txn_A,200,OK,thread-1,true\n"
        "1716400002000,5,Txn_B,200,OK,thread-1,true\n"
        "1716400003000,50,Txn_C,500,Error,thread-1,false\n",
        encoding="utf-8",
    )

    metrics = parse_jmeter_csv(result_file, planned_duration_minutes=1)

    assert metrics.transaction_names == ("Txn_A", "Txn_B", "Txn_C")
    assert [row.label for row in metrics.aggregate_rows] == ["Txn_A", "Txn_B", "Txn_C", "TOTAL"]
    assert metrics.aggregate_rows[0].samples == 2
    assert metrics.aggregate_rows[3].samples == 4
    assert metrics.aggregate_rows[3].error_pct == 25.0


def test_report_builder_uses_transaction_rows_when_available(tmp_path) -> None:
    validator = MetricsValidator(ValidationThresholds())
    builder = ReportBuilder()
    metrics = TestMetrics(1200, 55.0, 120, 180, 240, 500, 0.0, 30)
    validation = validator.validate(metrics)
    # Build a realistic metrics payload from parser output instead of handcrafting row dataclasses.
    # This keeps test expectations close to actual runtime behavior.
    parsed_file = tmp_path / "result.jtl"
    parsed_file.write_text(
        "timeStamp,elapsed,label,responseCode,responseMessage,threadName,success\n"
        "1716400000000,10,Txn_A,200,OK,thread-1,true\n"
        "1716400001000,12,Txn_B,200,OK,thread-1,true\n",
        encoding="utf-8",
    )
    parsed_metrics = parse_jmeter_csv(parsed_file, planned_duration_minutes=1)

    report = builder.build_single_run_report(
        test_name="load-test",
        environment_label="vm",
        test_plan_path="L:/AI_SPEC/Xinspect_JMeterTest.jmx",
        metrics=parsed_metrics,
        validation=validation,
    )

    summary = report["Test Summary"]
    execution = report["Test Execution Summary"]
    assert summary["transactions_detected"] == 2
    assert summary["transaction_names"] == ["Txn_A", "Txn_B"]
    assert [row["label"] for row in summary["jmeter_aggregate"]] == ["Txn_A", "Txn_B", "TOTAL"]
    assert execution["test_plan_path"].endswith("Xinspect_JMeterTest.jmx")


def test_comparison_report_includes_both_runs_and_observations() -> None:
    comparator = MetricsComparator()
    builder = ReportBuilder()
    run1 = TestMetrics(900, 45.0, 100, 140, 180, 300, 0.0, 20)
    run2 = TestMetrics(920, 50.0, 95, 130, 170, 280, 0.0, 20)

    comparison = comparator.compare("Run1", run1, "Run2", run2)
    report = builder.build_comparison_report(
        current_rounds=(("Run1", run1), ("Run2", run2)),
        comparison=comparison,
        recommendation="Approve for rollout",
    )

    summary = report["Today's Test Results Summary"]
    assert "Run1" in summary
    assert "Run2" in summary
    assert report["Test Execution Summary"]["baseline"] == "Run1"
    assert report["Test Execution Summary"]["candidate"] == "Run2"
    assert len(report["Detailed Observations and Analysis"]) > 0