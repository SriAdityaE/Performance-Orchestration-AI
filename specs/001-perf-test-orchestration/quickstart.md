# Quickstart: Remote Performance Test Orchestration

## Operator Preparation

1. Log in to the VM.
2. Connect the VM to VPN if required.
3. Build the Slack notifier artifact from the repository root.
4. Ensure `PERF_SHARED_ROOT`, `JMETER_HOME`, `NOTIFICATION_CHANNEL`, and `SLACK_WEBHOOK_URL` are set correctly in the environment when you need to override defaults.
5. Start the VM-side runner with the one-line wrapper.
6. Keep VM and local terminals separate; environment variables are session-scoped in PowerShell.

```powershell
npm run build:notifier
```

## Script Shortcuts

The repository includes helper scripts to avoid repeating environment setup each run:

- VM runner script: `Start-VmRunner.ps1`
- Local submit script: `Start-LocalSubmit.ps1`

VM runner (continuous mode):

```powershell
.\Start-VmRunner.ps1
```

Local submit:

```powershell
.\Start-LocalSubmit.ps1
```

## Start the VM-Side Runner

```powershell
python -m perf_orchestrator.runner.main
```

For one-shot processing during manual validation:

```powershell
python -m perf_orchestrator.runner.main --once
```

## Submit a Local Run Request

Prepare a request JSON file with one or two tests, then run:

```powershell
python -m perf_orchestrator.cli.main --request-file .\request.json
```

Important: `--request-file` always requires an explicit file path argument.

Minimal request example:

```json
{
   "tests": [
      {
         "test_name": "baseline",
         "environment_label": "vm",
         "test_plan_path": "L:/MCP/AI/Performance-Orchestration-AI/SDD-project/tests/load_test.jmx",
         "user_count": 100,
         "ramp_up_seconds": 30,
         "duration_minutes": 60,
         "expected_throughput": 200.0,
         "extra_args": {
            "threads": "100"
         }
      }
   ],
   "notification": {
      "channel": "slack"
   }
}
```

## Expected Flow

1. The local CLI validates input and creates a run folder plus request pointer.
2. The VM-side runner detects the queued request.
3. The VM-side runner executes JMeter, captures artifacts, and writes status updates.
4. Validation and, when applicable, comparison are completed.
5. Slack receives these lifecycle events only:
   - test started
   - test ended
   - report preparation in progress
   - final report ready

## Verification

- Confirm a run folder exists under `PERF_SHARED_ROOT\runs\{run_id}`.
- Confirm `status.json` reaches `completed` or `failed`.
- Confirm report files are created under `reports/`.
- Confirm Slack receives the approved lifecycle events and final report.
- Confirm `events.jsonl` includes the same lifecycle sequence that appears in Slack.
- Confirm both local and VM `PERF_SHARED_ROOT` values resolve to the same physical shared storage.
