from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import uuid

from perf_orchestrator.config import Settings
from perf_orchestrator.models.run_request import RunRequest


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    manifest_path: Path
    status_path: Path
    requests_path: Path
    events_log_path: Path
    artifacts_dir: Path
    logs_dir: Path
    reports_dir: Path


def create_run_layout(settings: Settings, request: RunRequest) -> RunPaths:
    request.validate()

    run_id = f"run-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = settings.runs_dir / run_id
    artifacts_dir = run_dir / "artifacts"
    logs_dir = run_dir / "logs"
    reports_dir = run_dir / "reports"
    manifest_path = run_dir / "run_request.json"
    status_path = run_dir / "status.json"
    events_log_path = run_dir / "events.jsonl"
    request_pointer_path = settings.requests_dir / f"{run_id}.json"

    for directory in (
        settings.requests_dir,
        settings.runs_dir,
        run_dir,
        artifacts_dir,
        logs_dir,
        reports_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(json.dumps(request.to_dict(), indent=2), encoding="utf-8")
    status_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "state": "created",
                "created_at": datetime.now(UTC).isoformat(),
                "tests": [
                    {
                        "index": index,
                        "test_name": test.test_name,
                        "environment": test.environment_label,
                        "state": "queued",
                    }
                    for index, test in enumerate(request.tests, start=1)
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    request_pointer_path.write_text(
        json.dumps({"run_id": run_id, "manifest_path": str(manifest_path)}, indent=2),
        encoding="utf-8",
    )

    return RunPaths(
        run_id=run_id,
        run_dir=run_dir,
        manifest_path=manifest_path,
        status_path=status_path,
        requests_path=request_pointer_path,
        events_log_path=events_log_path,
        artifacts_dir=artifacts_dir,
        logs_dir=logs_dir,
        reports_dir=reports_dir,
    )


def load_run_paths(settings: Settings, run_id: str) -> RunPaths:
    run_dir = settings.runs_dir / run_id
    return RunPaths(
        run_id=run_id,
        run_dir=run_dir,
        manifest_path=run_dir / "run_request.json",
        status_path=run_dir / "status.json",
        requests_path=settings.requests_dir / f"{run_id}.json",
        events_log_path=run_dir / "events.jsonl",
        artifacts_dir=run_dir / "artifacts",
        logs_dir=run_dir / "logs",
        reports_dir=run_dir / "reports",
    )


def read_status(run_paths: RunPaths) -> dict[str, object]:
    return json.loads(run_paths.status_path.read_text(encoding="utf-8"))


def write_status(run_paths: RunPaths, payload: dict[str, object]) -> None:
    run_paths.status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")