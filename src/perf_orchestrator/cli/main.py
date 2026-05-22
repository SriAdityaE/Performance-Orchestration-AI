from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from perf_orchestrator.config import ConfigError, load_settings
from perf_orchestrator.models.run_request import RunRequest
from perf_orchestrator.services.orchestrator import LocalOrchestrator


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start a local performance orchestration request")
    parser.add_argument("--request-file", type=Path, required=True, help="Path to a JSON run request")
    return parser


def _load_request(path: Path) -> RunRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RunRequest.from_dict(payload)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        settings = load_settings()
        request = _load_request(args.request_file)
        result = LocalOrchestrator(settings=settings).start(request)
    except (ConfigError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(result.run_paths.run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())