from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys
import time

from perf_orchestrator.models.events import LifecycleEvent


class NotificationError(RuntimeError):
    """Raised when notification delivery fails."""


class NotifierBridge:
    def __init__(self, repo_root: Path, *, slack_delivery_retries: int = 3) -> None:
        self._repo_root = repo_root
        self._slack_delivery_retries = max(slack_delivery_retries, 1)
        self._logger = logging.getLogger(__name__)

    @property
    def script_path(self) -> Path:
        return self._repo_root / "tools" / "slack-notifier" / "dist" / "cli.js"

    def emit(self, event: LifecycleEvent) -> None:
        command = ["node", str(self.script_path)]
        if not self.script_path.exists():
            raise NotificationError(
                f"Notifier script not found: {self.script_path}. Build it with 'npm run build:notifier'."
            )

        last_error = "notification delivery failed"
        for attempt in range(1, self._slack_delivery_retries + 1):
            completed = subprocess.run(
                command,
                input=event.to_json(),
                text=True,
                capture_output=True,
                cwd=self._repo_root,
                check=False,
            )
            if completed.returncode == 0:
                if attempt > 1:
                    self._logger.warning("Slack notification succeeded after retry", extra={"attempt": attempt})
                return

            last_error = completed.stderr.strip() or completed.stdout.strip() or last_error
            self._logger.warning(
                "Slack notification attempt failed",
                extra={"attempt": attempt, "error": last_error, "event_type": event.event_type},
            )
            if attempt < self._slack_delivery_retries:
                time.sleep(min(attempt, 3))

        raise NotificationError(last_error)


class TerminalNotifier:
    _logger = logging.getLogger(__name__)

    def emit(self, event: LifecycleEvent) -> None:
        self._logger.info("Lifecycle event emitted to terminal", extra={"event_type": event.event_type})
        print(event.to_json(), file=sys.stdout)