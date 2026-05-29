from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


MAX_TESTS_PER_REQUEST = 5


class RunRequestError(ValueError):
    """Raised when a submitted run request is invalid."""


@dataclass(frozen=True)
class TestDefinition:
    test_name: str
    environment_label: str
    test_plan_path: Path
    user_count: int | None = None
    ramp_up_seconds: int = 0
    duration_minutes: int = 5
    expected_throughput: float | None = None
    extra_args: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.test_name.strip():
            raise RunRequestError("test_name is required")
        if not self.environment_label.strip():
            raise RunRequestError("environment_label is required")
        if self.user_count is not None and self.user_count <= 0:
            raise RunRequestError("user_count must be greater than zero when provided")
        if self.ramp_up_seconds < 0:
            raise RunRequestError("ramp_up_seconds must be zero or greater")
        if self.duration_minutes <= 0:
            raise RunRequestError("duration_minutes must be greater than zero")
        if self.expected_throughput is not None and self.expected_throughput <= 0:
            raise RunRequestError("expected_throughput must be greater than zero when provided")

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "TestDefinition":
        return cls(
            test_name=str(payload["test_name"]),
            environment_label=str(payload["environment_label"]),
            test_plan_path=Path(str(payload["test_plan_path"])),
            user_count=int(payload["user_count"]) if payload.get("user_count") is not None else None,
            ramp_up_seconds=int(payload["ramp_up_seconds"]) if payload.get("ramp_up_seconds") is not None else 0,
            duration_minutes=int(payload["duration_minutes"]) if payload.get("duration_minutes") is not None else 5,
            expected_throughput=(
                float(payload["expected_throughput"])
                if payload.get("expected_throughput") is not None
                else None
            ),
            extra_args={str(k): str(v) for k, v in dict(payload.get("extra_args", {})).items()},
        )


@dataclass(frozen=True)
class NotificationPreferences:
    channel: str = "slack"
    custom_report_format: dict[str, object] | None = None

    def validate(self) -> None:
        if not self.channel.strip():
            raise RunRequestError("notification channel is required")
        if self.custom_report_format is None:
            return
        if not isinstance(self.custom_report_format, dict):
            raise RunRequestError("custom_report_format must be an object when provided")
        allowed_keys = {"title", "section_order", "section_aliases"}
        unexpected = [key for key in self.custom_report_format.keys() if key not in allowed_keys]
        if unexpected:
            raise RunRequestError(
                f"custom_report_format has unsupported keys: {', '.join(sorted(unexpected))}"
            )

        section_order = self.custom_report_format.get("section_order")
        if section_order is not None:
            if not isinstance(section_order, list) or not all(isinstance(item, str) for item in section_order):
                raise RunRequestError("custom_report_format.section_order must be a list of section names")

        section_aliases = self.custom_report_format.get("section_aliases")
        if section_aliases is not None:
            if not isinstance(section_aliases, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in section_aliases.items()
            ):
                raise RunRequestError(
                    "custom_report_format.section_aliases must be a map of section name to display label"
                )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "NotificationPreferences":
        return cls(
            channel=str(payload.get("channel", "slack")),
            custom_report_format=payload.get("custom_report_format"),
        )


@dataclass(frozen=True)
class RunRequest:
    tests: tuple[TestDefinition, ...]
    notification: NotificationPreferences = NotificationPreferences()

    def validate(self) -> None:
        if not self.tests:
            raise RunRequestError("At least one test is required")
        if len(self.tests) > MAX_TESTS_PER_REQUEST:
            raise RunRequestError(
                f"No more than {MAX_TESTS_PER_REQUEST} tests are supported in a single request"
            )
        for test in self.tests:
            test.validate()
        self.notification.validate()

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "tests": [
                {
                    **asdict(test),
                    "test_plan_path": str(test.test_plan_path),
                }
                for test in self.tests
            ],
            "notification": asdict(self.notification),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RunRequest":
        return cls(
            tests=tuple(TestDefinition.from_dict(item) for item in payload["tests"]),
            notification=NotificationPreferences.from_dict(dict(payload.get("notification", {}))),
        )