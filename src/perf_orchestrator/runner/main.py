from __future__ import annotations

import argparse
import sys
import time

from perf_orchestrator.config import ConfigError, load_settings
from perf_orchestrator.runner.vm_runner import VmRunner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the VM-side performance test watcher")
    parser.add_argument("--once", action="store_true", help="Process at most one queued run and exit")
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=5.0,
        help="Polling interval used when the runner stays active",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        settings = load_settings()
        runner = VmRunner(settings=settings)
        if args.once:
            processed = runner.process_next_run()
            if processed:
                print(processed)
            return 0

        while True:
            processed = runner.process_next_run()
            if processed:
                print(processed)
            time.sleep(max(args.poll_seconds, 0.5))
    except KeyboardInterrupt:
        return 0
    except (ConfigError, OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())