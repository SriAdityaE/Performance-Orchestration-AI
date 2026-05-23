from __future__ import annotations

from pathlib import Path

import pytest

from perf_orchestrator.config import ConfigError, load_settings


def _make_fake_jmeter_home(base: Path) -> Path:
    jmeter_home = base / "jmeter"
    (jmeter_home / "bin").mkdir(parents=True, exist_ok=True)
    (jmeter_home / "bin" / "jmeter.bat").write_text("@echo off\n", encoding="utf-8")
    return jmeter_home


def test_load_settings_requires_slack_webhook_for_slack_channel(tmp_path: Path) -> None:
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    env = {
        "PERF_SHARED_ROOT": str(tmp_path),
        "JMETER_HOME": str(jmeter_home),
        "NOTIFICATION_CHANNEL": "slack",
    }

    with pytest.raises(ConfigError):
        load_settings(env)


def test_load_settings_accepts_terminal_channel_without_webhook(tmp_path: Path) -> None:
    jmeter_home = _make_fake_jmeter_home(tmp_path)
    env = {
        "PERF_SHARED_ROOT": str(tmp_path),
        "JMETER_HOME": str(jmeter_home),
        "NOTIFICATION_CHANNEL": "terminal",
    }

    settings = load_settings(env)

    assert settings.notification_channel == "terminal"
    assert settings.requests_dir == tmp_path / "requests"
    assert settings.runs_dir == tmp_path / "runs"