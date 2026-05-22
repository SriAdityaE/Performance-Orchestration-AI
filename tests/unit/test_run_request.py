from __future__ import annotations

from pathlib import Path

import pytest

from perf_orchestrator.models.run_request import (
    NotificationPreferences,
    RunRequest,
    RunRequestError,
    TestDefinition,
)


def test_run_request_rejects_more_than_two_tests(tmp_path: Path) -> None:
    test = TestDefinition(
        test_name="smoke",
        environment_label="vm",
        test_plan_path=tmp_path / "plan.jmx",
        user_count=10,
        ramp_up_seconds=5,
        duration_minutes=30,
    )

    request = RunRequest(tests=(test, test, test))

    with pytest.raises(RunRequestError):
        request.validate()


def test_run_request_serializes_minimum_fields(tmp_path: Path) -> None:
    test = TestDefinition(
        test_name="baseline",
        environment_label="vm",
        test_plan_path=tmp_path / "plan.jmx",
        user_count=10,
        ramp_up_seconds=5,
        duration_minutes=30,
        expected_throughput=100.0,
    )

    payload = RunRequest(tests=(test,)).to_dict()

    assert payload["tests"][0]["test_name"] == "baseline"
    assert payload["tests"][0]["expected_throughput"] == 100.0


def test_run_request_rejects_invalid_custom_report_format(tmp_path: Path) -> None:
    test = TestDefinition(
        test_name="baseline",
        environment_label="vm",
        test_plan_path=tmp_path / "plan.jmx",
        user_count=10,
        ramp_up_seconds=5,
        duration_minutes=30,
    )
    request = RunRequest(
        tests=(test,),
        notification=NotificationPreferences(
            channel="slack",
            custom_report_format={"unsupported": "x"},
        ),
    )

    with pytest.raises(RunRequestError):
        request.validate()