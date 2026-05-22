from __future__ import annotations

from pathlib import Path

import pytest

from perf_orchestrator.config import ConfigError, load_settings


def test_load_settings_requires_slack_webhook_for_slack_channel(tmp_path: Path) -> None:
    env = {
        "PERF_SHARED_ROOT": str(tmp_path),
        "JMETER_HOME": str(tmp_path),
        "NOTIFICATION_CHANNEL": "slack",
    }

    with pytest.raises(ConfigError):
        load_settings(env)


def test_load_settings_accepts_terminal_channel_without_webhook(tmp_path: Path) -> None:
    env = {
        "PERF_SHARED_ROOT": str(tmp_path),
        "JMETER_HOME": str(tmp_path),
        "NOTIFICATION_CHANNEL": "terminal",
    }

    settings = load_settings(env)

    assert settings.notification_channel == "terminal"
    assert settings.requests_dir == tmp_path / "requests"
    assert settings.runs_dir == tmp_path / "runs"