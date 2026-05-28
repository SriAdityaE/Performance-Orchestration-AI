# Shared-Root Run Contract

## Request Pointer

Location: `PERF_SHARED_ROOT/requests/{run_id}.json`

```json
{
  "run_id": "run-20260522120000-ab12cd34",
  "manifest_path": "C:/.../runs/run-20260522120000-ab12cd34/run_request.json"
}
```

## Run Manifest

Location: `PERF_SHARED_ROOT/runs/{run_id}/run_request.json`

Contains:

- `tests`: one or two test definitions
- `notification`: channel and optional custom report format

Each test definition includes:

- `test_name`
- `environment_label`
- `test_plan_path`
- `user_count`
- `ramp_up_seconds`
- `duration_minutes`
- `expected_throughput`
- `extra_args`

## Status File

Location: `PERF_SHARED_ROOT/runs/{run_id}/status.json`

Required top-level fields:

- `run_id`
- `state`
- `created_at`
- `queued_for_vm_runner_at`
- `started_at`
- `completed_at`
- `tests`
- `failure_classification`
- `failure_reason`
- `final_report_path`

## Processing Rules

1. Local orchestrator creates the run folder, manifest, status file, and request pointer.
2. VM-side runner polls `requests/` for new request pointers.
3. VM-side runner processes only runs whose status is `queued_for_vm_runner`.
4. VM-side runner writes test-level state updates to `status.json`.
5. JTL files are written under `artifacts/jtl/{date_bucket}/Run{index}_{run_stamp}/test_{index}.jtl`.
6. `date_bucket` format is `DD-MM(MMM-Do)` (example: `25-05(May-25th)`).
7. Per-test summary backups are written under `reports/{date_bucket}/Run{index}_{run_stamp}/summary.json`.
8. Final report backup is written to `reports/{date_bucket}/final_report_{report_stamp}.json` before `final_report_ready` is emitted.
9. A latest compatibility copy is also written to `reports/final_report.json`.
10. `final_report_ready` event details include `report_path`, `report_latest_path`, `report_payload`, and `custom_report_format`.
11. Local and VM `PERF_SHARED_ROOT` values may differ as paths, but they must map to the same physical shared storage.
12. Local submit wrapper archives existing queued request pointers by default before enqueueing a new run; this can be bypassed with `-SkipQueueCleanup` when FIFO queue processing is required.
13. VM runner mirrors JTL and report backup files to `TEST_LOG_ROOT` when that path is available (default target: `L:\testlogs`) using per-test folders named `{YYYYMMDD}_{test_name}_round{index}_{HHMMSS}` under the run/date bucket path.
14. For single-run reports, `report_payload["Test Summary"]` includes transaction-level fields derived from parsed JTL labels:
  - `transactions_detected`
  - `transaction_names`
  - `jmeter_aggregate` rows with one entry per discovered label plus `TOTAL`
   - parent transaction-controller labels must be suppressed from the visible transaction list when child transaction labels are present in the parsed JTL
15. For single-run reports, `report_payload["Test Execution Summary"]["test_plan_path"]` records the executed JMX path used by the VM-side runner.
16. For single-run final notifications, the Slack payload must include a readable JMeter aggregate section (transaction label rows plus `TOTAL`), must show a distinct target-miss state when expected throughput is not met but base thresholds pass, and must be posted as Slack blocks (not JSON-as-text).
17. Final Slack report blocks (single-run and two-run) MUST open with an email-ready subject line and introduction paragraph (test name, date, and content description), followed by all metrics and observations, and close with a brief signature line. No separate Senior Architect review narrative block appears in the output.
18. Two-run comparative summaries must preserve both runs even when test names are identical by using round-qualified labels (for example, `Run 1 - <test_name>` and `Run 2 - <test_name>`).

## Operational Notes

- Operator shortcuts are provided by `Start-VmRunner.ps1` and `Start-LocalSubmit.ps1` at the repository root, with implementations in `scripts/`.
- A single-terminal VM shortcut is provided by `scripts/Run-OneTerminal.ps1` for submit + process + status output in one terminal session.
- The root-level wrappers resolve sensible defaults for the current checkout so operators can avoid repeating long parameter lists.
- `--request-file` must always include an explicit JSON file path when using the Python CLI directly.
- PowerShell environment variables are scoped to the current terminal session.
- Runner startup by itself does not emit lifecycle notifications; lifecycle notifications begin only after a queued run enters processing.
- Runs in `failed` state are not reprocessed and require a fresh submit.
- Local watch mode (`Start-LocalSubmit.ps1 -Watch`) requires local access to the same physical shared-root used by VM.
- Before committing or pushing script changes, operators must run local script parse checks and targeted unit tests and confirm success.

## Failure Classification Rules

- `execution`: JMeter command startup/execution failure or VM runner startup timeout exceeded.
- `parsing`: Result parsing timeout or malformed/unreadable result file.
- `validation`: Run completed but threshold checks failed for a test.
- `notification`: Slack delivery failure in notifier bridge after retry policy is exhausted.
