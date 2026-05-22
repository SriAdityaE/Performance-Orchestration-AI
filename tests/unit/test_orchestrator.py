from __future__ import annotations

import json
from pathlib import Path

from perf_orchestrator.config import load_settings
from perf_orchestrator.models.run_request import RunRequest, TestDefinition
from perf_orchestrator.services.orchestrator import LocalOrchestrator


class RecordingNotifier:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: LifecycleEvent) -> None:
        self.events.append(event)


def test_orchestrator_creates_run_layout_and_queues_vm_work(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "PERF_SHARED_ROOT": str(tmp_path),
            "JMETER_HOME": str(tmp_path),
            "NOTIFICATION_CHANNEL": "terminal",
        }
    )
    notifier = RecordingNotifier()
    orchestrator = LocalOrchestrator(settings=settings, notifier=notifier)
    request = RunRequest(
        tests=(
            TestDefinition(
                test_name="single-run",
                environment_label="vm",
                test_plan_path=tmp_path / "plan.jmx",
                user_count=25,
                ramp_up_seconds=10,
                duration_minutes=60,
            ),
        )
    )

    result = orchestrator.start(request)

    assert result.run_paths.run_dir.exists()
    assert result.run_paths.manifest_path.exists()
    status_payload = json.loads(result.run_paths.status_path.read_text(encoding="utf-8"))
    assert status_payload["state"] == "queued_for_vm_runner"
    assert status_payload["tests"][0]["state"] == "queued"
    assert notifier.events == []