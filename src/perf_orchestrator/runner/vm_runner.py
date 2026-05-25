from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import subprocess
import time

from perf_orchestrator.config import Settings
from perf_orchestrator.models.events import LifecycleEvent
from perf_orchestrator.models.run_request import RunRequest, TestDefinition
from perf_orchestrator.services.comparator import MetricsComparator
from perf_orchestrator.services.jmeter_parser import parse_jmeter_csv
from perf_orchestrator.services.notifier import NotificationError, NotifierBridge, TerminalNotifier
from perf_orchestrator.services.report_builder import ReportBuilder
from perf_orchestrator.services.run_layout import RunPaths, load_run_paths, read_status, write_status
from perf_orchestrator.services.validator import MetricsValidator


@dataclass(frozen=True)
class CommandResult:
    result_file: Path
    stdout_path: Path
    stderr_path: Path


def _read_log_tail(path: Path, max_lines: int = 20) -> str:
    if not path.exists():
        return "<missing log file>"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not content:
        return "<empty log file>"
    return "\n".join(content[-max_lines:])


class JMeterCommandRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, run_paths: RunPaths, test: TestDefinition, test_index: int) -> CommandResult:
        result_file = run_paths.artifacts_dir / f"test_{test_index}.jtl"
        stdout_path = run_paths.logs_dir / f"test_{test_index}.stdout.log"
        stderr_path = run_paths.logs_dir / f"test_{test_index}.stderr.log"
        command = [
            str(self._settings.jmeter_home / "bin" / "jmeter.bat"),
            "-n",
            "-t",
            str(test.test_plan_path),
            "-l",
            str(result_file),
        ]
        for key, value in test.extra_args.items():
            command.append(f"-J{key}={value}")

        max_attempts = 1 + self._settings.retry_policy.vm_runner_start_retries
        timeout_seconds = (test.duration_minutes * 60) + self._settings.timeout_policy.completion_buffer_seconds
        last_error = "JMeter execution failed"
        for attempt in range(1, max_attempts + 1):
            # Create logs immediately so operators can see activity while the test is running.
            stdout_path.write_text(
                f"Attempt {attempt}/{max_attempts}\nCommand: {' '.join(command)}\n\n",
                encoding="utf-8",
            )
            stderr_path.write_text("", encoding="utf-8")

            with stdout_path.open("a", encoding="utf-8") as stdout_handle, stderr_path.open(
                "a", encoding="utf-8"
            ) as stderr_handle:
                process = subprocess.Popen(
                    command,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    text=True,
                )
                try:
                    return_code = process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    last_error = (
                        f"JMeter execution timed out for {test.test_name} after {timeout_seconds} seconds"
                    )
                    stderr_handle.write(last_error + "\n")
                    if attempt < max_attempts:
                        time.sleep(min(attempt, 3))
                    continue
                except KeyboardInterrupt:
                    # Ensure the JMeter subprocess is not orphaned when the operator interrupts the runner.
                    process.kill()
                    process.wait()
                    stderr_handle.write("Runner interrupted by operator (Ctrl+C).\n")
                    raise

            if return_code == 0:
                return CommandResult(result_file=result_file, stdout_path=stdout_path, stderr_path=stderr_path)

            last_error = f"JMeter execution failed for {test.test_name} with exit code {return_code}"
            if attempt < max_attempts:
                time.sleep(min(attempt, 3))

        raise RuntimeError(last_error)


class VmRunner:
    def __init__(
        self,
        settings: Settings,
        *,
        notifier: TerminalNotifier | NotifierBridge | None = None,
        command_runner: JMeterCommandRunner | None = None,
    ) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)
        self._notifier = notifier or self._build_notifier(settings)
        self._command_runner = command_runner or JMeterCommandRunner(settings)
        self._validator = MetricsValidator(settings.thresholds)
        self._comparator = MetricsComparator()
        self._report_builder = ReportBuilder()

    def _build_notifier(self, settings: Settings) -> TerminalNotifier | NotifierBridge:
        if settings.notification_channel == "terminal":
            return TerminalNotifier()
        repo_root = Path(__file__).resolve().parents[3]
        return NotifierBridge(
            repo_root,
            slack_delivery_retries=settings.retry_policy.slack_delivery_retries,
        )

    def process_next_run(self) -> str | None:
        for pointer_file in sorted(self._settings.requests_dir.glob("*.json")):
            pointer_payload = json.loads(pointer_file.read_text(encoding="utf-8"))
            run_paths = load_run_paths(self._settings, str(pointer_payload["run_id"]))
            status_payload = read_status(run_paths)
            if status_payload.get("state") != "queued_for_vm_runner":
                self._archive_request_pointer(pointer_file)
                continue
            if self._is_queue_timeout_exceeded(status_payload):
                status_payload["state"] = "failed"
                status_payload["failure_classification"] = "execution"
                status_payload["failure_reason"] = "VM runner startup timeout exceeded"
                write_status(run_paths, status_payload)
                self._logger.error("VM runner startup timeout exceeded", extra={"run_id": run_paths.run_id})
                self._archive_request_pointer(pointer_file)
                continue
            request = RunRequest.from_dict(json.loads(run_paths.manifest_path.read_text(encoding="utf-8")))
            try:
                self._process_run(run_paths, request, status_payload)
            except BaseException as exc:
                self._logger.exception("Run processing failed", extra={"run_id": run_paths.run_id})
                status_payload = read_status(run_paths)
                if status_payload.get("state") != "failed":
                    status_payload["state"] = "failed"
                    if isinstance(exc, NotificationError):
                        status_payload["failure_classification"] = "notification"
                    elif isinstance(exc, TimeoutError):
                        status_payload["failure_classification"] = "parsing"
                    else:
                        status_payload["failure_classification"] = "execution"
                    status_payload["failure_reason"] = str(exc)
                    write_status(run_paths, status_payload)
                if isinstance(exc, KeyboardInterrupt):
                    raise
            self._archive_request_pointer(pointer_file)
            return run_paths.run_id
        return None

    def _archive_request_pointer(self, pointer_file: Path) -> None:
        stale_dir = self._settings.requests_dir / "stale"
        stale_dir.mkdir(parents=True, exist_ok=True)
        target = stale_dir / pointer_file.name
        if target.exists():
            target.unlink()
        pointer_file.replace(target)

    def _is_queue_timeout_exceeded(self, status_payload: dict[str, object]) -> bool:
        queued_at = status_payload.get("queued_for_vm_runner_at")
        if not queued_at:
            return False
        queued_at_dt = datetime.fromisoformat(str(queued_at))
        age = (datetime.now(UTC) - queued_at_dt).total_seconds()
        return age > self._settings.timeout_policy.vm_runner_start_seconds

    def _process_run(
        self,
        run_paths: RunPaths,
        request: RunRequest,
        status_payload: dict[str, object],
    ) -> None:
        status_payload["state"] = "running"
        status_payload["started_at"] = datetime.now(UTC).isoformat()
        write_status(run_paths, status_payload)
        self._logger.info("Run processing started", extra={"run_id": run_paths.run_id})

        completed_runs: list[tuple[TestDefinition, dict[str, object]]] = []
        tests_payload: list[dict[str, object]] = list(status_payload["tests"])

        for index, test in enumerate(request.tests, start=1):
            tests_payload[index - 1]["state"] = "running"
            write_status(run_paths, {**status_payload, "tests": tests_payload})

            if not test.test_plan_path.exists():
                raise RuntimeError(f"JMeter test plan not found: {test.test_plan_path}")

            self._emit(
                run_paths,
                LifecycleEvent(
                    event_type="test_started",
                    run_id=run_paths.run_id,
                    test_name=test.test_name,
                    message=f"{test.test_name} - JMETER started",
                    details={"environment": test.environment_label, "index": index},
                ),
            )

            try:
                command_result = self._command_runner.run(run_paths, test, index)
                if not command_result.result_file.exists():
                    stdout_tail = _read_log_tail(command_result.stdout_path)
                    stderr_tail = _read_log_tail(command_result.stderr_path)
                    raise RuntimeError(
                        "JMeter finished without creating result file: "
                        f"{command_result.result_file}\n"
                        f"stdout tail:\n{stdout_tail}\n"
                        f"stderr tail:\n{stderr_tail}"
                    )
                parse_start = time.monotonic()
                metrics = parse_jmeter_csv(command_result.result_file, test.duration_minutes)
                parse_elapsed = time.monotonic() - parse_start
                if parse_elapsed > self._settings.timeout_policy.parse_seconds:
                    raise TimeoutError("JMeter parse timeout exceeded")
                validation = self._validator.validate(metrics, test.expected_throughput)
            except TimeoutError as exc:
                tests_payload[index - 1]["state"] = "failed"
                tests_payload[index - 1]["failure_classification"] = "parsing"
                tests_payload[index - 1]["failure_reason"] = str(exc)
                status_payload["state"] = "failed"
                status_payload["failure_classification"] = "parsing"
                status_payload["failure_reason"] = str(exc)
                write_status(run_paths, {**status_payload, "tests": tests_payload})
                raise
            except Exception as exc:
                tests_payload[index - 1]["state"] = "failed"
                tests_payload[index - 1]["failure_classification"] = "execution"
                tests_payload[index - 1]["failure_reason"] = str(exc)
                status_payload["state"] = "failed"
                status_payload["failure_classification"] = "execution"
                status_payload["failure_reason"] = str(exc)
                write_status(run_paths, {**status_payload, "tests": tests_payload})
                raise

            summary = {
                "metrics": asdict(metrics),
                "validation": {
                    "passed": validation.passed,
                    "reasons": list(validation.reasons),
                    "threshold_checks": validation.threshold_checks,
                    "target_checks": validation.target_checks,
                },
                "result_file": str(command_result.result_file),
            }
            (run_paths.reports_dir / f"test_{index}_summary.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            tests_payload[index - 1]["state"] = "completed"
            tests_payload[index - 1]["validation_passed"] = validation.passed
            if not validation.passed:
                tests_payload[index - 1]["failure_classification"] = "validation"
            write_status(run_paths, {**status_payload, "tests": tests_payload})
            self._emit(
                run_paths,
                LifecycleEvent(
                    event_type="test_ended",
                    run_id=run_paths.run_id,
                    test_name=test.test_name,
                    message=f"{test.test_name} ended",
                    details={"validation_passed": validation.passed, "index": index},
                ),
            )
            completed_runs.append((test, summary))

        self._emit(
            run_paths,
            LifecycleEvent(
                event_type="report_preparation_in_progress",
                run_id=run_paths.run_id,
                message="Report preparation is in progress",
            ),
        )

        report_payload = self._build_report(completed_runs, request.notification.custom_report_format)
        report_path = run_paths.reports_dir / "final_report.json"
        report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

        status_payload["state"] = "completed"
        status_payload["completed_at"] = datetime.now(UTC).isoformat()
        status_payload["tests"] = tests_payload
        status_payload["final_report_path"] = str(report_path)
        write_status(run_paths, status_payload)
        self._emit(
            run_paths,
            LifecycleEvent(
                event_type="final_report_ready",
                run_id=run_paths.run_id,
                message="Final report is ready",
                details={
                    "report_path": str(report_path),
                    "report_payload": report_payload,
                    "custom_report_format": request.notification.custom_report_format,
                },
            ),
        )
        self._logger.info("Run processing completed", extra={"run_id": run_paths.run_id})

    def _build_report(
        self,
        completed_runs: list[tuple[TestDefinition, dict[str, object]]],
        custom_format: dict[str, object] | None,
    ) -> dict[str, object]:
        if len(completed_runs) == 1:
            test, summary = completed_runs[0]
            return self._report_builder.build_single_run_report(
                test_name=test.test_name,
                environment_label=test.environment_label,
                metrics=parse_metrics(summary["metrics"]),
                validation=parse_validation(summary["validation"]),
                custom_format=custom_format,
            )

        first_test, first_summary = completed_runs[0]
        second_test, second_summary = completed_runs[1]
        comparison = self._comparator.compare(
            first_test.test_name,
            parse_metrics(first_summary["metrics"]),
            second_test.test_name,
            parse_metrics(second_summary["metrics"]),
        )
        recommendation = "Investigate before approval" if any(
            delta.classification == "regression" for delta in comparison.deltas
        ) else "Approve for rollout"
        return self._report_builder.build_comparison_report(
            current_rounds=(
                (first_test.test_name, parse_metrics(first_summary["metrics"])),
                (second_test.test_name, parse_metrics(second_summary["metrics"])),
            ),
            comparison=comparison,
            recommendation=recommendation,
            custom_format=custom_format,
        )

    def _emit(self, run_paths: RunPaths, event: LifecycleEvent) -> None:
        with run_paths.events_log_path.open("a", encoding="utf-8") as handle:
            handle.write(event.to_json() + "\n")
        try:
            self._notifier.emit(event)
        except NotificationError:
            status_payload = read_status(run_paths)
            status_payload["state"] = "failed"
            status_payload["failure_classification"] = "notification"
            status_payload["failure_reason"] = f"Notification failed for event {event.event_type}"
            write_status(run_paths, status_payload)
            raise


def parse_metrics(payload: dict[str, object]):
    from perf_orchestrator.models.results import TestMetrics

    return TestMetrics(
        transactions=int(payload["transactions"]),
        throughput=float(payload["throughput"]),
        avg_response_ms=float(payload["avg_response_ms"]),
        p95_response_ms=float(payload["p95_response_ms"]),
        p99_response_ms=float(payload["p99_response_ms"]),
        max_response_ms=float(payload["max_response_ms"]),
        error_rate_pct=float(payload["error_rate_pct"]),
        duration_minutes=int(payload["duration_minutes"]),
    )


def parse_validation(payload: dict[str, object]):
    from perf_orchestrator.models.results import ValidationResult

    return ValidationResult(
        passed=bool(payload["passed"]),
        reasons=tuple(str(item) for item in payload.get("reasons", [])),
        threshold_checks={str(k): bool(v) for k, v in dict(payload.get("threshold_checks", {})).items()},
        target_checks={str(k): bool(v) for k, v in dict(payload.get("target_checks", {})).items()},
    )