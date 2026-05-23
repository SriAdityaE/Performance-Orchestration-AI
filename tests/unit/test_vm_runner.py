from __future__ import annotations

import json
from pathlib import Path

from perf_orchestrator.config import load_settings
from perf_orchestrator.models.events import LifecycleEvent
from perf_orchestrator.models.run_request import RunRequest, TestDefinition
from perf_orchestrator.runner.vm_runner import CommandResult, VmRunner
from perf_orchestrator.services.orchestrator import LocalOrchestrator


class RecordingNotifier:
    def __init__(self) -> None:
        self.events: list[LifecycleEvent] = []

    def emit(self, event: LifecycleEvent) -> None:
        self.events.append(event)


class FakeCommandRunner:
    def run(self, run_paths, test, test_index):
        result_file = run_paths.artifacts_dir / f"test_{test_index}.jtl"
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
    orchestrator = LocalOrchestrator(settings=settings, notifier=RecordingNotifier())
    result = orchestrator.start(request)

    notifier = RecordingNotifier()
    runner = VmRunner(settings=settings, notifier=notifier, command_runner=FakeCommandRunner())

    processed_run_id = runner.process_next_run()

    assert processed_run_id == result.run_paths.run_id
    status_payload = json.loads(result.run_paths.status_path.read_text(encoding="utf-8"))
    assert status_payload["state"] == "completed"
    assert Path(status_payload["final_report_path"]).exists()
    assert [event.event_type for event in notifier.events] == [
        "test_started",
        "test_ended",
        "report_preparation_in_progress",
        "final_report_ready",
    ]