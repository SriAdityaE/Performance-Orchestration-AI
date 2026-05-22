from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json


LIFECYCLE_EVENTS = {
    "test_started",
    "test_ended",
    "report_preparation_in_progress",
    "final_report_ready",
}


@dataclass(frozen=True)
class LifecycleEvent:
    event_type: str
    run_id: str
    message: str
    test_name: str | None = None
    details: dict[str, object] = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if self.event_type not in LIFECYCLE_EVENTS:
            raise ValueError(f"Unsupported lifecycle event: {self.event_type}")

    def to_json(self) -> str:
        return json.dumps(
            {
                "event_type": self.event_type,
                "run_id": self.run_id,
                "message": self.message,
                "test_name": self.test_name,
                "details": self.details,
                "occurred_at": self.occurred_at,
            }
        )