from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


ALLOWED_NOTIFICATION_CHANNELS = {"terminal", "teams", "slack", "both"}


@dataclass(frozen=True)
class TimeoutPolicy:
    prereq_seconds: int = 300
    vm_runner_start_seconds: int = 600
    parse_seconds: int = 300
    completion_buffer_seconds: int = 900


@dataclass(frozen=True)
class RetryPolicy:
    vm_runner_start_retries: int = 1
    slack_delivery_retries: int = 3


@dataclass(frozen=True)
class ValidationThresholds:
    max_error_rate_pct: float = 1.0
    max_p95_ms: int = 2000
    max_p99_ms: int = 3000
    min_throughput: float = 0.000001


@dataclass(frozen=True)
class Settings:
    perf_shared_root: Path
    notification_channel: str
    jmeter_home: Path
    slack_webhook_url: str | None
    teams_webhook_url: str | None
    retry_policy: RetryPolicy = RetryPolicy()
    timeout_policy: TimeoutPolicy = TimeoutPolicy()
    thresholds: ValidationThresholds = ValidationThresholds()

    @property
    def requests_dir(self) -> Path:
        return self.perf_shared_root / "requests"

    @property
    def runs_dir(self) -> Path:
        return self.perf_shared_root / "runs"


def _require_path(name: str, raw_value: str | None) -> Path:
    if not raw_value or not raw_value.strip():
        raise ConfigError(f"Missing required environment variable: {name}")

    path = Path(raw_value).expanduser()
    if not path.exists():
        raise ConfigError(f"Configured path for {name} does not exist: {path}")
    return path


def load_settings(env: dict[str, str] | None = None) -> Settings:
    source = env if env is not None else os.environ

    notification_channel = source.get("NOTIFICATION_CHANNEL", "slack").strip().lower()
    if notification_channel not in ALLOWED_NOTIFICATION_CHANNELS:
        raise ConfigError(
            "NOTIFICATION_CHANNEL must be one of: "
            + ", ".join(sorted(ALLOWED_NOTIFICATION_CHANNELS))
        )

    perf_shared_root = _require_path("PERF_SHARED_ROOT", source.get("PERF_SHARED_ROOT"))
    jmeter_home = _require_path("JMETER_HOME", source.get("JMETER_HOME"))
    slack_webhook_url = source.get("SLACK_WEBHOOK_URL") or None
    teams_webhook_url = source.get("TEAMS_WEBHOOK_URL") or None

    if notification_channel in {"slack", "both"} and not slack_webhook_url:
        raise ConfigError("SLACK_WEBHOOK_URL is required when Slack notifications are enabled")

    return Settings(
        perf_shared_root=perf_shared_root,
        notification_channel=notification_channel,
        jmeter_home=jmeter_home,
        slack_webhook_url=slack_webhook_url,
        teams_webhook_url=teams_webhook_url,
    )