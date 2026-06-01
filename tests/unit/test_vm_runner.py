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
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", status_payload["execution_date_bucket"])
    assert "jtl" in status_payload["tests"][0]["jtl_path"]
    jtl_path = Path(status_payload["tests"][0]["jtl_path"])
    assert jtl_path.exists()
    run_slot = status_payload["tests"][0]["run_slot"]
    assert run_slot.startswith("round1_")
    assert jtl_path.parent.name == run_slot
    assert jtl_path.parent.parent.name == status_payload["execution_date_bucket"]
    assert Path(status_payload["tests"][0]["summary_path"]).exists()
    assert "external_testlogs_dir" in status_payload
    assert Path(status_payload["tests"][0]["external_testlogs_slot"]).exists()
    assert re.match(
        r"^round1_\d{8}_\d{6}$",
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


def test_vm_runner_five_run_request_generates_first_to_last_comparison(tmp_path: Path) -> None:
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    (tmp_path / "plan.jmx").write_text("<jmeterTestPlan/>", encoding="utf-8")
    settings = load_settings(
        {
            "PERF_SHARED_ROOT": str(tmp_path),
            "JMETER_HOME": str(jmeter_home),
            "NOTIFICATION_CHANNEL": "terminal",
        }
    )

    def _test_def() -> TestDefinition:
        return TestDefinition(
            test_name="Inspect_Load test",
            environment_label="PRD-VM",
            test_plan_path=tmp_path / "plan.jmx",
            user_count=100,
            ramp_up_seconds=30,
            duration_minutes=1,
        )

    request = RunRequest(tests=(_test_def(), _test_def(), _test_def(), _test_def(), _test_def()))
    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())
    result = orchestrator.start(request)

    runner = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
    processed_run_id = runner.process_next_run()

    assert processed_run_id == result.run_paths.run_id
    status_payload = json.loads(result.run_paths.status_path.read_text(encoding="utf-8"))
    assert status_payload["state"] == "completed"

    final_report = json.loads(Path(status_payload["final_report_latest_path"]).read_text(encoding="utf-8"))
    summary = final_report["Today's Test Results Summary"]
    assert len(summary) == 5
    assert "Run 1 - Inspect_Load test" in summary
    assert "Run 5 - Inspect_Load test" in summary
    assert final_report["Test Execution Summary"]["baseline"] == "Run 1 - Inspect_Load test"
    assert final_report["Test Execution Summary"]["candidate"] == "Run 5 - Inspect_Load test"


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
    assert any("Run Comparison" in line for line in observations), (
        "Expected 'Run Comparison' heading in observations — cross-run comparison did not trigger"
    )
    assert any("Verdict" in line for line in observations), (
        "Expected 'Verdict' in observations"
    )

    # The final_report_ready event payload should carry comparison data
    final_event = next(e for e in notifier2.events if e.event_type == "final_report_ready")
    report_payload = final_event.details["report_payload"]
    obs = report_payload.get("Detailed Observations and Analysis", [])
    assert any("Run Comparison" in str(line) for line in obs)

    execution_summary = report_payload.get("Test Execution Summary", {})
    historical_comparison = execution_summary.get("historical_comparison")
    assert isinstance(historical_comparison, dict)
    assert historical_comparison.get("baseline") == result1.run_paths.run_id
    assert historical_comparison.get("candidate") == result2.run_paths.run_id
    assert isinstance(historical_comparison.get("deltas"), list)
    assert len(historical_comparison.get("deltas")) > 0


def test_vm_runner_historical_comparison_fallbacks_without_manifest(tmp_path: Path) -> None:
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    (tmp_path / "plan.jmx").write_text("<jmeterTestPlan/>", encoding="utf-8")
    settings = load_settings(
        {
            "PERF_SHARED_ROOT": str(tmp_path),
            "JMETER_HOME": str(jmeter_home),
            "NOTIFICATION_CHANNEL": "terminal",
        }
    )

    request_1 = RunRequest(
        tests=(
            TestDefinition(
                test_name="Inspect_Load test",
                environment_label="PRD-VM",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=100,
                ramp_up_seconds=30,
                duration_minutes=5,
            ),
        )
    )
    request_2 = RunRequest(
        tests=(
            TestDefinition(
                test_name=" inspect_load TEST ",
                environment_label="PRD-VM",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=100,
                ramp_up_seconds=30,
                duration_minutes=5,
            ),
        )
    )

    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())

    result1 = orchestrator.start(request_1)
    runner1 = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
    processed1 = runner1.process_next_run()
    assert processed1 == result1.run_paths.run_id

    # Force fallback path by removing prior manifest and canonical summary.
    (result1.run_paths.run_dir / "run_request.json").unlink()
    (result1.run_paths.reports_dir / "test_1_summary.json").unlink()

    result2 = orchestrator.start(request_2)
    runner2 = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
    processed2 = runner2.process_next_run()
    assert processed2 == result2.run_paths.run_id

    status2 = json.loads(result2.run_paths.status_path.read_text(encoding="utf-8"))
    final_report = json.loads(Path(status2["final_report_latest_path"]).read_text(encoding="utf-8"))
    observations = final_report.get("Detailed Observations and Analysis", [])
    assert any("Run Comparison" in line for line in observations)


def test_vm_runner_historical_comparison_fallbacks_to_external_testlogs(tmp_path: Path) -> None:
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
                test_name="My Load Test",
                environment_label="PERF-VM",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=100,
                ramp_up_seconds=30,
                duration_minutes=5,
            ),
        )
    )

    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())

    # Run 1 writes external round summary.
    result1 = orchestrator.start(request)
    runner1 = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
    processed1 = runner1.process_next_run()
    assert processed1 == result1.run_paths.run_id

    # Simulate missing previous shared-root run folder; external testlogs still exist.
    run1_dir = settings.runs_dir / result1.run_paths.run_id
    assert run1_dir.exists()
    import shutil
    shutil.rmtree(run1_dir)

    # Run 2 should still produce comparison using external testlogs fallback.
    result2 = orchestrator.start(request)
    runner2 = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
    processed2 = runner2.process_next_run()
    assert processed2 == result2.run_paths.run_id

    status2 = json.loads(result2.run_paths.status_path.read_text(encoding="utf-8"))
    report2 = json.loads(Path(status2["final_report_latest_path"]).read_text(encoding="utf-8"))

    execution_summary = report2.get("Test Execution Summary", {})
    historical_list = execution_summary.get("historical_comparisons")
    assert isinstance(historical_list, list)
    assert len(historical_list) >= 1
    assert any(str(item.get("baseline", "")).startswith("round") for item in historical_list)


def test_vm_runner_historical_comparison_caps_at_five_previous_runs(tmp_path: Path) -> None:
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
                duration_minutes=5,
                expected_throughput=200.0,
            ),
        )
    )

    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())
    run_ids: list[str] = []

    for _ in range(7):
        result = orchestrator.start(request)
        run_ids.append(result.run_paths.run_id)
        runner = VmRunner(settings=settings, notifier=RecordingNotifier(), command_runner=FakeCommandRunner())
        processed = runner.process_next_run()
        assert processed == result.run_paths.run_id

    latest_run_id = run_ids[-1]
    latest_status = json.loads((settings.runs_dir / latest_run_id / "status.json").read_text(encoding="utf-8"))
    final_report = json.loads(Path(latest_status["final_report_latest_path"]).read_text(encoding="utf-8"))

    execution_summary = final_report.get("Test Execution Summary", {})
    historical_list = execution_summary.get("historical_comparisons")
    assert isinstance(historical_list, list)
    assert len(historical_list) == 5

    # The immediate previous run should be first; oldest run should be outside the capped list.
    assert historical_list[0]["baseline"] == run_ids[-2]
    baselines = [item.get("baseline") for item in historical_list]
    assert run_ids[0] not in baselines
    assert run_ids[1] in baselines


def test_vm_runner_uses_external_round_number_for_event_index(tmp_path: Path) -> None:
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
                test_name="Inspect_Load test",
                environment_label="PRD-VM",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=100,
                ramp_up_seconds=30,
                duration_minutes=5,
            ),
        )
    )

    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())

    # Run 1
    result1 = orchestrator.start(request)
    notifier1 = RecordingNotifier()
    runner1 = VmRunner(settings=settings, notifier=notifier1, command_runner=FakeCommandRunner())
    assert runner1.process_next_run() == result1.run_paths.run_id
    started1 = next(event for event in notifier1.events if event.event_type == "test_started")
    ended1 = next(event for event in notifier1.events if event.event_type == "test_ended")
    assert started1.details["index"] == 1
    assert ended1.details["index"] == 1

    # Run 2 should increment using external round folder scan.
    result2 = orchestrator.start(request)
    notifier2 = RecordingNotifier()
    runner2 = VmRunner(settings=settings, notifier=notifier2, command_runner=FakeCommandRunner())
    assert runner2.process_next_run() == result2.run_paths.run_id
    started2 = next(event for event in notifier2.events if event.event_type == "test_started")
    ended2 = next(event for event in notifier2.events if event.event_type == "test_ended")
    assert started2.details["index"] == 2
    assert ended2.details["index"] == 2


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