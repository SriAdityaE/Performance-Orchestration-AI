# Data Model: Remote Performance Test Orchestration

## Entities

### Run Request

- Represents one orchestration request containing one or two tests.
- Key fields:
  - `tests`
  - `notification`

### Test Definition

- Represents one queued performance test.
- Key fields:
  - `test_name`
  - `environment_label`
  - `test_plan_path`
  - `user_count`
  - `ramp_up_seconds`
  - `duration_minutes`
  - `expected_throughput`
  - `extra_args`

### Orchestration Run

- Represents the tracked lifecycle of a single submitted request.
- Key fields:
  - `run_id`
  - `state`
  - `created_at`
  - `started_at`
  - `completed_at`
  - `failure_classification`
  - `failure_reason`
  - `final_report_path`

### Test Status Entry

- Represents one test within the orchestration run.
- Key fields:
  - `index`
  - `test_name`
  - `environment`
  - `state`
  - `validation_passed`
  - `failure_classification`
  - `failure_reason`

### Validation Result

- Captures pass/fail outcome, threshold checks, target checks, and reasons.

### Comparison Summary

- Captures baseline-versus-candidate delta calculations and narrative observations for two-test runs.

## Shared-Root Layout

```text
PERF_SHARED_ROOT/
├── requests/
│   └── {run_id}.json
└── runs/
    └── {run_id}/
        ├── run_request.json
        ├── status.json
        ├── events.jsonl
        ├── artifacts/
        │   └── test_{n}.jtl
        ├── logs/
        │   ├── test_{n}.stdout.log
        │   └── test_{n}.stderr.log
        └── reports/
            ├── test_{n}_summary.json
            └── final_report.json
```

## State Model

### Run States

- `created`
- `queued_for_vm_runner`
- `running`
- `completed`
- `failed`

### Test States

- `queued`
- `running`
- `completed`
- `failed`

## Lifecycle Events

Only these lifecycle events are emitted before the final report:

- `test_started`
- `test_ended`
- `report_preparation_in_progress`
- `final_report_ready`
