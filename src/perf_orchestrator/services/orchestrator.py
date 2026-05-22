from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from perf_orchestrator.config import Settings
from perf_orchestrator.models.run_request import RunRequest
from perf_orchestrator.services.notifier import NotifierBridge, TerminalNotifier
from perf_orchestrator.services.run_layout import RunPaths, create_run_layout, read_status, write_status


@dataclass
class OrchestrationResult:
    run_paths: RunPaths


class LocalOrchestrator:
    def __init__(self, settings: Settings, notifier: TerminalNotifier | None = None) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)
        self._notifier = notifier or self._build_notifier(settings)

    def _build_notifier(self, settings: Settings) -> TerminalNotifier | NotifierBridge:
        if settings.notification_channel == "terminal":
            return TerminalNotifier()
        repo_root = Path(__file__).resolve().parents[3]
        return NotifierBridge(
            repo_root,
            slack_delivery_retries=settings.retry_policy.slack_delivery_retries,
        )

    def start(self, request: RunRequest) -> OrchestrationResult:
        self._logger.info("Starting local orchestration request")
        run_paths = create_run_layout(self._settings, request)
        self._write_status(run_paths, "queued_for_vm_runner")
        self._logger.info("Run queued for VM runner", extra={"run_id": run_paths.run_id})
        return OrchestrationResult(run_paths=run_paths)

    def _write_status(self, run_paths: RunPaths, state: str) -> None:
        payload = read_status(run_paths)
        payload["state"] = state
        if state == "queued_for_vm_runner":
            from datetime import UTC, datetime

            payload["queued_for_vm_runner_at"] = datetime.now(UTC).isoformat()
        write_status(run_paths, payload)