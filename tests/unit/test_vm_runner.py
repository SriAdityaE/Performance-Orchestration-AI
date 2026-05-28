from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import re

from perf_orchestrator.config import load_settings
from perf_orchestrator.models.events import LifecycleEvent
from perf_orchestrator.models.run_request import RunRequest, TestDefinition
from perf_orchestrator.runner.vm_runner import CommandResult, VmRunner, parse_metrics
from perf_orchestrator.services.orchestrator import LocalOrchestrator


class RecordingNotifier:
    def __init__(self) -> None:
        self.events: list[LifecycleEvent] = []

    def emit(self, event: LifecycleEvent) -> None:
        self.events.append(event)


class FakeCommandRunner:
    def run(self, run_paths, test, test_index, *, results_dir=None):
        output_dir = results_dir or run_paths.artifacts_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        result_file = output_dir / f"test_{test_index}.jtl"
        stdout_path = run_paths.logs_dir / f"test_{test_index}.stdout.log"
        stderr_path = run_paths.logs_dir / f"test_{test_index}.stderr.log"
        result_file.write_text(
            "timeStamp,elapsed,label,responseCode,responseMessage,threadName,success\n"
            "1716400000000,2,tx,200,OK,thread-1,true\n"
            "1716400001000,3,tx,200,OK,thread-1,true\n",
            encoding="utf-8",
        )
        stdout_path.write_text("ok", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return CommandResult(result_file=result_file, stdout_path=stdout_path, stderr_path=stderr_path)


def _make_fake_jmeter_home(base: Path) -> Path:
    jmeter_home = base / "jmeter"
    (jmeter_home / "bin").mkdir(parents=True, exist_ok=True)
    (jmeter_home / "bin" / "jmeter.bat").write_text("@echo off\n", encoding="utf-8")
    return jmeter_home


def test_vm_runner_processes_next_run_and_writes_report(tmp_path: Path) -> None:
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    external_logs_root = tmp_path / "external-testlogs"
    (tmp_path / "plan.jmx").write_text("<jmeterTestPlan/>", encoding="utf-8")
    settings = load_settings(
        {
            "PERF_SHARED_ROOT": str(tmp_path),
            "JMETER_HOME": str(jmeter_home),
            "NOTIFICATION_CHANNEL": "terminal",
            "TEST_LOG_ROOT": str(external_logs_root),
        }
    )
    request = RunRequest(
        tests=(
            TestDefinition(
                test_name="baseline",
                environment_label="vm",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=10,
                ramp_up_seconds=5,
                duration_minutes=1,
            ),
        )
    )
    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())
    result = orchestrator.start(request)

    notifier = RecordingNotifier()
    runner = VmRunner(settings=settings, notifier=notifier, command_runner=FakeCommandRunner())

    processed_run_id = runner.process_next_run()

    assert processed_run_id == result.run_paths.run_id
    status_payload = json.loads(result.run_paths.status_path.read_text(encoding="utf-8"))
    assert status_payload["state"] == "completed"
    assert Path(status_payload["final_report_path"]).exists()
    assert Path(status_payload["final_report_latest_path"]).exists()
    assert "execution_stamp" in status_payload
    assert "execution_date_bucket" in status_payload
    assert re.match(r"^\d{2}-\d{2}\([A-Za-z]{3}-\d{1,2}(st|nd|rd|th)\)$", status_payload["execution_date_bucket"])
    assert "jtl" in status_payload["tests"][0]["jtl_path"]
    jtl_path = Path(status_payload["tests"][0]["jtl_path"])
    assert jtl_path.exists()
    run_slot = status_payload["tests"][0]["run_slot"]
    assert run_slot.startswith("Run1_")
    assert jtl_path.parent.name == run_slot
    assert jtl_path.parent.parent.name == status_payload["execution_date_bucket"]
    assert Path(status_payload["tests"][0]["summary_path"]).exists()
    assert "external_testlogs_dir" in status_payload
    assert Path(status_payload["tests"][0]["external_testlogs_slot"]).exists()
    assert re.match(
        r"^\d{8}_baseline_round1_\d{6}$",
        status_payload["tests"][0]["testlogs_slot_name"],
    )
    assert Path(status_payload["external_final_report_path"]).exists()
    assert [event.event_type for event in notifier.events] == [
        "test_started",
        "test_ended",
        "report_preparation_in_progress",
        "final_report_ready",
    ]


def test_vm_runner_archives_stale_queued_request(tmp_path: Path) -> None:
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    settings = load_settings(
        {
            "PERF_SHARED_ROOT": str(tmp_path),
            "JMETER_HOME": str(jmeter_home),
            "NOTIFICATION_CHANNEL": "terminal",
        }
    )
    request = RunRequest(
        tests=(
            TestDefinition(
                test_name="baseline",
                environment_label="vm",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=10,
                ramp_up_seconds=5,
                duration_minutes=1,
            ),
        )
    )
    result = LocalOrchestrator(settings=settings, notifier=RecordingNotifier()).start(request)

    status_payload = json.loads(result.run_paths.status_path.read_text(encoding="utf-8"))
    status_payload["queued_for_vm_runner_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    result.run_paths.status_path.write_text(json.dumps(status_payload, indent=2), encoding="utf-8")

    runner = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
    processed_run_id = runner.process_next_run()

    assert processed_run_id is None
    updated_status = json.loads(result.run_paths.status_path.read_text(encoding="utf-8"))
    assert updated_status["state"] == "failed"
    assert updated_status["failure_reason"] == "VM runner startup timeout exceeded"
    assert not (settings.requests_dir / f"{result.run_paths.run_id}.json").exists()
    assert (settings.requests_dir / "stale" / f"{result.run_paths.run_id}.json").exists()


def test_vm_runner_two_run_request_generates_comparison_report(tmp_path: Path) -> None:
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    (tmp_path / "plan.jmx").write_text("<jmeterTestPlan/>", encoding="utf-8")
    settings = load_settings(
        {
            "PERF_SHARED_ROOT": str(tmp_path),
            "JMETER_HOME": str(jmeter_home),
            "NOTIFICATION_CHANNEL": "terminal",
        }
    )
    request = RunRequest(
        tests=(
            TestDefinition(
                test_name="Inspect_Load test",
                environment_label="PRD-VM",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=100,
                ramp_up_seconds=30,
                duration_minutes=1,
            ),
            TestDefinition(
                test_name="Inspect_Load test",
                environment_label="PRD-VM",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=120,
                ramp_up_seconds=30,
                duration_minutes=1,
            ),
        )
    )
    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())
    result = orchestrator.start(request)

    notifier = RecordingNotifier()
    runner = VmRunner(settings=settings, notifier=notifier, command_runner=FakeCommandRunner())

    processed_run_id = runner.process_next_run()

    assert processed_run_id == result.run_paths.run_id
    status_payload = json.loads(result.run_paths.status_path.read_text(encoding="utf-8"))
    assert status_payload["state"] == "completed"
    assert len(status_payload["tests"]) == 2
    assert status_payload["tests"][0]["state"] == "completed"
    assert status_payload["tests"][1]["state"] == "completed"

    final_report = json.loads(Path(status_payload["final_report_latest_path"]).read_text(encoding="utf-8"))
    assert "Today's Test Results Summary" in final_report
    assert "Test Execution Summary" in final_report
    assert "Detailed Observations and Analysis" in final_report
    assert "Recommendation or Conclusion" in final_report
    assert len(final_report["Today's Test Results Summary"]) == 2


def test_vm_runner_historical_comparison_triggers_on_second_run(tmp_path: Path) -> None:
    """Simulates Run-OneTerminal.ps1 run sequence: run 1 completes, run 2 finds it and includes
    a Historical Comparison section in the observations — confirming the lookup works."""
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    (tmp_path / "plan.jmx").write_text("<jmeterTestPlan/>", encoding="utf-8")
    settings = load_settings(
        {
            "PERF_SHARED_ROOT": str(tmp_path),
            "JMETER_HOME": str(jmeter_home),
            "NOTIFICATION_CHANNEL": "terminal",
        }
    )

    def _make_request() -> RunRequest:
        return RunRequest(
            tests=(
                TestDefinition(
                    test_name="Inspect_Load test",
                    environment_label="PRD-VM",
                    test_plan_path=tmp_path / "plan.jmx",
                    user_count=100,
                    ramp_up_seconds=30,
                    duration_minutes=5,
                    expected_throughput=200.0,
                ),
            )
        )

    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())

    # --- Run 1 ---
    result1 = orchestrator.start(_make_request())
    runner1 = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
    processed1 = runner1.process_next_run()
    assert processed1 == result1.run_paths.run_id
    status1 = json.loads(result1.run_paths.status_path.read_text(encoding="utf-8"))
    assert status1["state"] == "completed"

    # --- Run 2 (simulates next Run-OneTerminal.ps1 invocation) ---
    result2 = orchestrator.start(_make_request())
    notifier2 = RecordingNotifier()
    runner2 = VmRunner(settings=settings, notifier=notifier2, command_runner=FakeCommandRunner())
    processed2 = runner2.process_next_run()
    assert processed2 == result2.run_paths.run_id

    status2 = json.loads(result2.run_paths.status_path.read_text(encoding="utf-8"))
    assert status2["state"] == "completed"

    # Verify comparison was included in observations
    final_report = json.loads(Path(status2["final_report_latest_path"]).read_text(encoding="utf-8"))
    observations = final_report.get("Detailed Observations and Analysis", [])
    assert any("Historical Comparison" in line for line in observations), (
        "Expected 'Historical Comparison' in observations — cross-run comparison did not trigger"
    )
    assert any("Best Run Recommendation" in line for line in observations), (
        "Expected 'Best Run Recommendation' in observations"
    )

    # The final_report_ready event payload should carry comparison data
    final_event = next(e for e in notifier2.events if e.event_type == "final_report_ready")
    report_payload = final_event.details["report_payload"]
    obs = report_payload.get("Detailed Observations and Analysis", [])
    assert any("Historical Comparison" in str(line) for line in obs)


def test_parse_metrics_preserves_aggregate_rows_and_transaction_names() -> None:
    payload = {
        "transactions": 4,
        "throughput": 2.0,
        "avg_response_ms": 19.25,
        "p95_response_ms": 50.0,
        "p99_response_ms": 50.0,
        "max_response_ms": 50.0,
        "error_rate_pct": 25.0,
        "duration_minutes": 1,
        "aggregate_rows": [
            {
                "label": "Txn_A",
                "samples": 2,
                "average_ms": 11.0,
                "median_ms": 11.0,
                "p90_ms": 12.0,
                "p95_ms": 12.0,
                "p99_ms": 12.0,
                "min_ms": 10.0,
                "max_ms": 12.0,
                "error_pct": 0.0,
                "throughput_per_sec": 1.0,
            },
            {
                "label": "TOTAL",
                "samples": 4,
                "average_ms": 19.25,
                "median_ms": 12.0,
                "p90_ms": 50.0,
                "p95_ms": 50.0,
                "p99_ms": 50.0,
                "min_ms": 5.0,
                "max_ms": 50.0,
                "error_pct": 25.0,
                "throughput_per_sec": 2.0,
            },
        ],
        "transaction_names": ["Txn_A", "Txn_B", "Txn_C"],
    }

    metrics = parse_metrics(payload)

    assert metrics.transaction_names == ("Txn_A", "Txn_B", "Txn_C")
    assert [row.label for row in metrics.aggregate_rows] == ["Txn_A", "TOTAL"]
    assert metrics.aggregate_rows[0].samples == 2


def test_parse_metrics_accepts_tuple_payload_for_aggregate_rows() -> None:
    payload = {
        "transactions": 2,
        "throughput": 1.0,
        "avg_response_ms": 15.0,
        "p95_response_ms": 20.0,
        "p99_response_ms": 20.0,
        "max_response_ms": 20.0,
        "error_rate_pct": 0.0,
        "duration_minutes": 1,
        "aggregate_rows": (
            {
                "label": "Txn_A",
                "samples": 1,
                "average_ms": 10.0,
                "median_ms": 10.0,
                "p90_ms": 10.0,
                "p95_ms": 10.0,
                "p99_ms": 10.0,
                "min_ms": 10.0,
                "max_ms": 10.0,
                "error_pct": 0.0,
                "throughput_per_sec": 0.5,
            },
            {
                "label": "TOTAL",
                "samples": 2,
                "average_ms": 15.0,
                "median_ms": 15.0,
                "p90_ms": 20.0,
                "p95_ms": 20.0,
                "p99_ms": 20.0,
                "min_ms": 10.0,
                "max_ms": 20.0,
                "error_pct": 0.0,
                "throughput_per_sec": 1.0,
            },
        ),
        "transaction_names": ("Txn_A", "Txn_B"),
    }

    metrics = parse_metrics(payload)

    assert metrics.transaction_names == ("Txn_A", "Txn_B")
    assert [row.label for row in metrics.aggregate_rows] == ["Txn_A", "TOTAL"]
    assert metrics.aggregate_rows[1].samples == 2