# Performance Orchestration AI

Performance Orchestration AI is a local-to-VM performance testing workflow for running JMeter-based load tests, capturing execution artifacts, validating results, and sending structured lifecycle updates or final summaries to Slack or Teams.

It is designed for teams that want repeatable performance runs, consistent project-side file contracts, and business-readable reporting without hardcoding secrets into the repository.

## What this project does

- Accepts a run request describing one or more JMeter test definitions.
- Stores requests and execution state using a shared-root contract under a common folder.
- Queues work for a VM runner and tracks lifecycle status per run.
- Executes JMeter on the VM, captures logs and JTL results, and parses the output.
- Validates throughput, latency, and error-rate thresholds.
- Builds a final report with aggregate metrics, transaction breakdowns, and comparison views.
- Sends notifications for lifecycle events and the final report to Slack and/or Teams.

## Architecture at a glance

The project is organized into a few key layers:

- Request model and validation: [src/perf_orchestrator/models/run_request.py](src/perf_orchestrator/models/run_request.py)
- Runtime settings/configuration: [src/perf_orchestrator/config.py](src/perf_orchestrator/config.py)
- Local orchestration entrypoint: [src/perf_orchestrator/services/orchestrator.py](src/perf_orchestrator/services/orchestrator.py)
- VM execution and result parsing: [src/perf_orchestrator/runner/vm_runner.py](src/perf_orchestrator/runner/vm_runner.py)
- Reporting and comparisons: [src/perf_orchestrator/services/report_builder.py](src/perf_orchestrator/services/report_builder.py) and [src/perf_orchestrator/services/comparator.py](src/perf_orchestrator/services/comparator.py)
- Notification bridge: [src/perf_orchestrator/services/notifier.py](src/perf_orchestrator/services/notifier.py)

## Main workflow

1. Prepare a request JSON payload.
2. Submit it through the local submit script.
3. The request is written into the shared-root request queue.
4. The VM runner reads the next queued request.
5. JMeter runs against the configured test plan and writes JTL output.
6. The runner parses JTL data, validates metrics, builds comparison summaries, and writes the report.
7. Lifecycle events and the final report are sent to the configured notification channel.

## Repository structure

- [src/perf_orchestrator](src/perf_orchestrator) — main Python implementation
- [tests/unit](tests/unit) — validation and unit tests
- [scripts](scripts) — helper scripts for running the workflow locally or on a VM
- [tools/slack-notifier](tools/slack-notifier) — Node-based notifier used to send final Slack/Teams payloads
- [shared-root](shared-root) — runtime output structure used by the orchestrator
- [specs/001-perf-test-orchestration](specs/001-perf-test-orchestration) — product/spec documentation
- [request.json](request.json) — sample request template
- [.env.example](.env.example) — environment variable template

## Prerequisites

Before running the project, make sure the following are available:

- Python 3.11+
- JMeter installation on the target VM or execution machine
- A shared folder accessible from both the local machine and the VM
- A Slack webhook URL and/or Teams webhook URL if notifications are enabled
- Node.js if the notifier is used in Slack/Teams mode

## Environment setup

1. Copy [.env.example](.env.example) to a local file named .env.
2. Fill in the required values:
   - PERF_SHARED_ROOT
   - JMETER_HOME
   - NOTIFICATION_CHANNEL
   - SLACK_WEBHOOK_URL or TEAMS_WEBHOOK_URL
3. Keep .env out of Git by following the existing .gitignore rules.

Example values are already shown in [.env.example](.env.example). Do not commit real secrets.

## Sample request

A sample request is provided in [request.json](request.json). It includes one or more tests and notification preferences.

Example structure:

```json
{
  "tests": [
    {
      "test_name": "My Load Test",
      "environment_label": "PERF-VM",
      "test_plan_path": "L:/path/to/your/TestPlan.jmx",
      "ramp_up_seconds": 30,
      "duration_minutes": 5,
      "expected_throughput": 200.0
    }
  ],
  "notification": {
    "channel": "slack"
  }
}
```

## Run the project

From the project root, use the PowerShell wrappers in the root folder:

### Local submit

```powershell
.\Start-LocalSubmit.ps1
```

This creates the request and enqueues it for processing.

### VM runner

```powershell
.\Start-VmRunner.ps1
```

This watches the shared-root request queue and runs the queued JMeter workload.

### Single-terminal workflow

```powershell
.\scripts\Run-OneTerminal.ps1
```

This is the easiest demo flow when you want submission, execution, and final lifecycle/status handling in one terminal session.

### Reset queued runs

```powershell
.\scripts\Reset-RunQueue.ps1
```

This is useful when you want to clear old run state before a fresh demo or test cycle.

## Shared-root contract

The system uses a standard shared folder layout for automation and traceability.

Typical structure:

```text
shared-root/
  requests/
    queued-request.json
    stale/
  runs/
    run-YYYYMMDDHHMMSS-abc123/
      run_request.json
      status.json
      logs/
      artifacts/
      reports/
```

This makes it easy for local submission scripts and VM runner scripts to coordinate without relying on a database.

## Reports and comparisons

The project builds reports from JMeter output and can compare results across runs.

This includes:

- throughput
- average response time
- p95 and p99 latency
- error rate
- transaction-level aggregates
- run-to-run comparison summaries
- recommendation text for whether the current run is better or equivalent

The comparison logic includes safeguards so load-profile changes or small measurement noise do not create misleading conclusions.

## Notification behavior

The notifier can emit lifecycle events and final report payloads to:

- Slack
- Teams
- terminal output

The runtime behavior is controlled by the NOTIFICATION_CHANNEL setting and the webhook URL environment variables.

## Validation

The repo includes unit tests for the configuration and orchestration logic.

Run the tests with:

```powershell
python -m pytest -q
```

or a focused subset:

```powershell
python -m pytest tests/unit/test_config.py tests/unit/test_vm_runner.py -q
```

## Important notes

- No real credentials or secrets should be stored in this repository.
- Keep webhook URLs in environment variables or secure secret stores.
- If you are running on a new machine, confirm the shared-root path and JMeter home match the actual environment.
- The project is intentionally structured to be readable and traceable, but it is not a full SaaS platform; it is a workflow automation repo for performance-test orchestration.

## Security and public release checklist

Before making the repo public, confirm the following:

- [.env.example](.env.example) contains only placeholders and no real values.
- Local .env files are never committed; they are ignored by the repo rules.
- Slack and Teams webhook values are supplied through environment variables only.
- Shared run output under [shared-root](shared-root) is not intended for permanent source control and should be treated as runtime data.
- Generated Python caches, build output, and Node dependencies are excluded from the repository.
- Any internal company references, internal URLs, or hostnames are removed before release.
- The README and examples use placeholders instead of real machine paths and secrets.

This repository is safe for public sharing when these rules are respected.

## Related design docs

- [specs/001-perf-test-orchestration/spec.md](specs/001-perf-test-orchestration/spec.md)
- [specs/001-perf-test-orchestration/quickstart.md](specs/001-perf-test-orchestration/quickstart.md)
- [specs/001-perf-test-orchestration/contracts/shared-root-run-contract.md](specs/001-perf-test-orchestration/contracts/shared-root-run-contract.md)

## License

This project is shared for internal collaboration and evaluation. If you want it published with a formal license, add one before making it public to a wider audience.
