from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
import time

from perf_orchestrator.config import Settings
from perf_orchestrator.models.events import LifecycleEvent
from perf_orchestrator.models.run_request import MAX_TESTS_PER_REQUEST, RunRequest, TestDefinition
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


def _format_date_bucket(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _sanitize_path_segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    safe = safe.strip("_")
    return safe or "test"


class JMeterCommandRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        run_paths: RunPaths,
        test: TestDefinition,
        test_index: int,
        *,
        results_dir: Path | None = None,
    ) -> CommandResult:
        output_dir = results_dir or run_paths.artifacts_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        result_file = output_dir / f"test_{test_index}.jtl"
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
        effective_extra_args = {
            # Capture child sampler rows when a transaction controller emits parent samples,
            # so aggregate reporting can include real per-transaction labels.
            "jmeter.save.saveservice.subresults": "true",
            "jmeter.save.saveservice.label": "true",
        }
        effective_extra_args.update(test.extra_args)

        for key, value in effective_extra_args.items():
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
        run_started_at = datetime.now(UTC)
        execution_stamp = run_started_at.strftime("%Y%m%d-%H%M%S")
        date_bucket = _format_date_bucket(run_started_at)
        execution_artifacts_dir = run_paths.artifacts_dir / "jtl" / date_bucket
        execution_reports_dir = run_paths.reports_dir / date_bucket
        execution_artifacts_dir.mkdir(parents=True, exist_ok=True)
        execution_reports_dir.mkdir(parents=True, exist_ok=True)
        external_run_dir: Path | None = None
        if self._settings.test_logs_root:
            first_test_name_slug = _sanitize_path_segment(request.tests[0].test_name) if request.tests else "test"
            run_date_str = run_started_at.strftime("%Y-%m-%d")
            external_run_dir = self._settings.test_logs_root / f"{first_test_name_slug}-{run_date_str}"
            external_run_dir.mkdir(parents=True, exist_ok=True)

        status_payload["state"] = "running"
        status_payload["started_at"] = run_started_at.isoformat()
        status_payload["execution_stamp"] = execution_stamp
        status_payload["execution_date_bucket"] = date_bucket
        status_payload["execution_artifacts_dir"] = str(execution_artifacts_dir)
        status_payload["execution_reports_dir"] = str(execution_reports_dir)
        if external_run_dir:
            status_payload["external_testlogs_dir"] = str(external_run_dir)
        write_status(run_paths, status_payload)
        self._logger.info("Run processing started", extra={"run_id": run_paths.run_id})

        completed_runs: list[tuple[TestDefinition, dict[str, object]]] = []
        tests_payload: list[dict[str, object]] = list(status_payload["tests"])

        for index, test in enumerate(request.tests, start=1):
            test_stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            run_slot = f"round{index}_{test_stamp}"
            test_date = run_started_at.strftime("%Y%m%d")
            test_time = datetime.now(UTC).strftime("%H%M%S")
            test_artifacts_dir = execution_artifacts_dir / run_slot
            test_reports_dir = execution_reports_dir / run_slot
            test_artifacts_dir.mkdir(parents=True, exist_ok=True)
            test_reports_dir.mkdir(parents=True, exist_ok=True)
            external_test_dir: Path | None = None
            report_index = index
            if external_run_dir:
                # Count existing round subdirs so successive single-test runs get round2, round3…
                existing_round_count = sum(
                    1 for d in external_run_dir.iterdir()
                    if d.is_dir() and d.name.startswith("round")
                )
                external_round_num = existing_round_count + 1
                report_index = external_round_num
                testlogs_slot = f"round{external_round_num}_{test_date}_{test_time}"
                external_test_dir = external_run_dir / testlogs_slot
                external_test_dir.mkdir(parents=True, exist_ok=True)
            else:
                testlogs_slot = f"round{index}_{test_date}_{test_time}"

            tests_payload[index - 1]["state"] = "running"
            tests_payload[index - 1]["run_slot"] = run_slot
            tests_payload[index - 1]["run_slot_started_at"] = datetime.now(UTC).isoformat()
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
                    details={"environment": test.environment_label, "index": report_index},
                ),
            )

            try:
                command_result = self._command_runner.run(
                    run_paths,
                    test,
                    index,
                    results_dir=test_artifacts_dir,
                )
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
                if external_test_dir:
                    shutil.copy2(command_result.result_file, external_test_dir / command_result.result_file.name)
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
                "test_plan_path": str(test.test_plan_path),
                "run_slot": run_slot,
            }
            summary_path = test_reports_dir / "summary.json"
            summary_path.write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            if external_test_dir:
                shutil.copy2(summary_path, external_test_dir / "summary.json")
            # Keep canonical summary paths for compatibility with existing tooling.
            (run_paths.reports_dir / f"test_{index}_summary.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            tests_payload[index - 1]["state"] = "completed"
            tests_payload[index - 1]["validation_passed"] = validation.passed
            tests_payload[index - 1]["jtl_path"] = str(command_result.result_file)
            tests_payload[index - 1]["summary_path"] = str(summary_path)
            if external_test_dir:
                tests_payload[index - 1]["external_testlogs_slot"] = str(external_test_dir)
                tests_payload[index - 1]["testlogs_slot_name"] = testlogs_slot
                tests_payload[index - 1]["report_index"] = report_index
            tests_payload[index - 1]["run_slot_completed_at"] = datetime.now(UTC).isoformat()
            tests_payload[index - 1]["test_plan_path"] = str(test.test_plan_path)
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
                    details={"validation_passed": validation.passed, "index": report_index},
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

        report_payload = self._build_report(run_paths, completed_runs, request.notification.custom_report_format)
        report_stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        report_path = execution_reports_dir / f"final_report_{report_stamp}.json"
        report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        (execution_reports_dir / "final_report.json").write_text(
            json.dumps(report_payload, indent=2), encoding="utf-8"
        )
        # Keep canonical final report path for compatibility with existing tooling.
        canonical_report_path = run_paths.reports_dir / "final_report.json"
        shutil.copy2(report_path, canonical_report_path)
        if external_run_dir:
            shutil.copy2(report_path, external_run_dir / report_path.name)
            shutil.copy2(report_path, external_run_dir / "final_report.json")

        status_payload["state"] = "completed"
        status_payload["completed_at"] = datetime.now(UTC).isoformat()
        status_payload["tests"] = tests_payload
        status_payload["final_report_path"] = str(report_path)
        status_payload["final_report_latest_path"] = str(canonical_report_path)
        if external_run_dir:
            status_payload["external_final_report_path"] = str(external_run_dir / report_path.name)
        write_status(run_paths, status_payload)
        self._emit(
            run_paths,
            LifecycleEvent(
                event_type="final_report_ready",
                run_id=run_paths.run_id,
                message="Final report is ready",
                details={
                    "report_path": str(report_path),
                    "report_latest_path": str(canonical_report_path),
                    "report_payload": report_payload,
                    "custom_report_format": request.notification.custom_report_format,
                },
            ),
        )
        self._logger.info("Run processing completed", extra={"run_id": run_paths.run_id})

    def _build_report(
        self,
        run_paths: RunPaths,
        completed_runs: list[tuple[TestDefinition, dict[str, object]]],
        custom_format: dict[str, object] | None,
    ) -> dict[str, object]:
        if len(completed_runs) == 1:
            test, summary = completed_runs[0]
            current_metrics = parse_metrics(summary["metrics"])
            comparison_summary = None
            comparison_history = None
            best_run_recommendation = None
            status_snapshot = read_status(run_paths)
            external_dir_raw = status_snapshot.get("external_testlogs_dir")
            external_run_dir = Path(str(external_dir_raw)) if external_dir_raw else None
            tests_snapshot = status_snapshot.get("tests", [])
            current_external_slot_name = None
            if isinstance(tests_snapshot, list) and tests_snapshot:
                first_test = tests_snapshot[0]
                if isinstance(first_test, dict):
                    slot_name = first_test.get("testlogs_slot_name")
                    current_external_slot_name = str(slot_name) if slot_name else None
            previous_history = self._find_previous_single_run_metrics_history(
                run_paths.run_id,
                test.test_name,
                limit=MAX_TESTS_PER_REQUEST,
                external_run_dir=external_run_dir,
                current_external_slot_name=current_external_slot_name,
            )
            if previous_history:
                comparison_history = tuple(
                    self._comparator.compare(
                        baseline_label=previous_run_id,
                        baseline=previous_metrics,
                        candidate_label=run_paths.run_id,
                        candidate=current_metrics,
                    )
                    for previous_run_id, previous_metrics in previous_history
                )

                previous_run_id, previous_metrics = previous_history[0]
                comparison_summary = self._comparator.compare(
                    baseline_label=previous_run_id,
                    baseline=previous_metrics,
                    candidate_label=run_paths.run_id,
                    candidate=current_metrics,
                )
                improvements = sum(1 for delta in comparison_summary.deltas if delta.classification == "improvement")
                regressions = sum(1 for delta in comparison_summary.deltas if delta.classification == "regression")
                if improvements > regressions:
                    best_run_recommendation = (
                        f"Current run is preferred — "
                        f"{improvements} metric{'s' if improvements != 1 else ''} improved "
                        f"with {regressions} regression{'s' if regressions != 1 else ''} detected. "
                        "Approve current run as the new baseline."
                    )
                elif regressions > improvements:
                    best_run_recommendation = (
                        f"Previous baseline is preferred — "
                        f"{regressions} regression{'s' if regressions != 1 else ''} detected "
                        f"against only {improvements} improvement{'s' if improvements != 1 else ''}. "
                        "Review current run before promoting."
                    )
                else:
                    best_run_recommendation = (
                        "Both runs are statistically equivalent. "
                        "Either can be used as the baseline for future runs."
                    )

            return self._report_builder.build_single_run_report(
                test_name=test.test_name,
                environment_label=test.environment_label,
                test_plan_path=str(test.test_plan_path),
                metrics=current_metrics,
                validation=parse_validation(summary["validation"]),
                comparison_summary=comparison_summary,
                comparison_history=comparison_history,
                best_run_recommendation=best_run_recommendation,
                custom_format=custom_format,
            )

        selected_runs = completed_runs[:MAX_TESTS_PER_REQUEST]
        labeled_runs = [
            (
                f"Run {idx} - {test.test_name}",
                parse_metrics(summary["metrics"]),
            )
            for idx, (test, summary) in enumerate(selected_runs, start=1)
        ]
        first_label, first_metrics = labeled_runs[0]
        last_label, last_metrics = labeled_runs[-1]
        comparison = self._comparator.compare(
            first_label,
            first_metrics,
            last_label,
            last_metrics,
        )
        recommendation = "Investigate before approval" if any(
            delta.classification == "regression" for delta in comparison.deltas
        ) else "Approve for rollout"
        return self._report_builder.build_comparison_report(
            current_rounds=tuple(labeled_runs),
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

    def _find_previous_single_run_metrics_history(
        self,
        current_run_id: str,
        current_test_name: str,
        *,
        limit: int,
        external_run_dir: Path | None = None,
        current_external_slot_name: str | None = None,
    ) -> list[tuple[str, object]]:
        current_test_name_norm = current_test_name.strip().casefold()
        matches: list[tuple[str, object]] = []
        seen_labels: set[str] = set()

        for run_dir in sorted(self._settings.runs_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not run_dir.is_dir() or run_dir.name == current_run_id:
                continue

            status_path = run_dir / "status.json"
            manifest_path = run_dir / "run_request.json"
            if not status_path.exists():
                continue

            summary_path = run_dir / "reports" / "test_1_summary.json"
            if not summary_path.exists():
                fallback_summaries = sorted((run_dir / "reports").glob("*/round*/summary.json"))
                if fallback_summaries:
                    summary_path = fallback_summaries[-1]
            if not summary_path.exists():
                continue

            status_payload = json.loads(status_path.read_text(encoding="utf-8"))
            if status_payload.get("state") != "completed":
                continue

            previous_test_name = ""
            if manifest_path.exists():
                manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                tests_payload = manifest_payload.get("tests", [])
                if tests_payload:
                    previous_test_name = str(tests_payload[0].get("test_name", ""))

            if not previous_test_name:
                status_tests = status_payload.get("tests", [])
                if isinstance(status_tests, list) and status_tests:
                    previous_test_name = str(status_tests[0].get("test_name", ""))

            if previous_test_name.strip().casefold() != current_test_name_norm:
                continue

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            matches.append((run_dir.name, parse_metrics(summary_payload["metrics"])))
            seen_labels.add(run_dir.name)
            if len(matches) >= limit:
                break

        if len(matches) < limit and external_run_dir and external_run_dir.exists():
            round_dirs = sorted(
                (
                    d
                    for d in external_run_dir.iterdir()
                    if d.is_dir() and d.name.startswith("round")
                ),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            for round_dir in round_dirs:
                if current_external_slot_name and round_dir.name == current_external_slot_name:
                    continue
                summary_path = round_dir / "summary.json"
                if not summary_path.exists():
                    continue
                label = round_dir.name
                if label in seen_labels:
                    continue
                summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
                metrics_payload = summary_payload.get("metrics")
                if not isinstance(metrics_payload, dict):
                    continue
                matches.append((label, parse_metrics(metrics_payload)))
                seen_labels.add(label)
                if len(matches) >= limit:
                    break

        return matches

    def _find_previous_single_run_metrics(
        self,
        current_run_id: str,
        current_test_name: str,
    ) -> tuple[str, object] | None:
        history = self._find_previous_single_run_metrics_history(
            current_run_id,
            current_test_name,
            limit=1,
        )
        if not history:
            return None
        return history[0]


def parse_metrics(payload: dict[str, object]):
    from perf_orchestrator.models.results import AggregateRow, TestMetrics

    aggregate_payload = payload.get("aggregate_rows", [])
    aggregate_rows: list[AggregateRow] = []
    if isinstance(aggregate_payload, (list, tuple)):
        for row in aggregate_payload:
            if not isinstance(row, dict):
                continue
            aggregate_rows.append(
                AggregateRow(
                    label=str(row.get("label", "UNNAMED")),
                    samples=int(row.get("samples", 0)),
                    average_ms=float(row.get("average_ms", 0.0)),
                    median_ms=float(row.get("median_ms", 0.0)),
                    p90_ms=float(row.get("p90_ms", 0.0)),
                    p95_ms=float(row.get("p95_ms", 0.0)),
                    p99_ms=float(row.get("p99_ms", 0.0)),
                    min_ms=float(row.get("min_ms", 0.0)),
                    max_ms=float(row.get("max_ms", 0.0)),
                    error_pct=float(row.get("error_pct", 0.0)),
                    throughput_per_sec=float(row.get("throughput_per_sec", 0.0)),
                )
            )

    transaction_names_payload = payload.get("transaction_names", [])
    transaction_names = (
        tuple(str(item) for item in transaction_names_payload)
        if isinstance(transaction_names_payload, (list, tuple))
        else ()
    )

    return TestMetrics(
        transactions=int(payload["transactions"]),
        throughput=float(payload["throughput"]),
        avg_response_ms=float(payload["avg_response_ms"]),
        p95_response_ms=float(payload["p95_response_ms"]),
        p99_response_ms=float(payload["p99_response_ms"]),
        max_response_ms=float(payload["max_response_ms"]),
        error_rate_pct=float(payload["error_rate_pct"]),
        duration_minutes=int(payload["duration_minutes"]),
        aggregate_rows=tuple(aggregate_rows),
        transaction_names=transaction_names,
    )


def parse_validation(payload: dict[str, object]):
    from perf_orchestrator.models.results import ValidationResult

    return ValidationResult(
        passed=bool(payload["passed"]),
        reasons=tuple(str(item) for item in payload.get("reasons", [])),
        threshold_checks={str(k): bool(v) for k, v in dict(payload.get("threshold_checks", {})).items()},
        target_checks={str(k): bool(v) for k, v in dict(payload.get("target_checks", {})).items()},
    )