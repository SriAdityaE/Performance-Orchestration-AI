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
5. Final report is written to `reports/final_report.json` before `final_report_ready` is emitted.
6. `final_report_ready` event details include `report_path`, `report_payload`, and `custom_report_format`.

## Failure Classification Rules

- `execution`: JMeter command startup/execution failure or VM runner startup timeout exceeded.
- `parsing`: Result parsing timeout or malformed/unreadable result file.
- `validation`: Run completed but threshold checks failed for a test.
- `notification`: Slack delivery failure in notifier bridge after retry policy is exhausted.
