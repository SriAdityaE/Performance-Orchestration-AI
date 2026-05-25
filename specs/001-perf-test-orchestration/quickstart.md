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
- One-terminal VM workflow: `scripts/Run-OneTerminal.ps1`

VM runner (continuous mode):

```powershell
.\Start-VmRunner.ps1
```

Local submit:

```powershell
.\Start-LocalSubmit.ps1
```

Local submit with status watch (when local can access the same shared-root):

```powershell
.\Start-LocalSubmit.ps1 -Watch -PollSeconds 3 -WatchTimeoutSeconds 1800
```

## Recommended Runtime Workflow

Use this sequence for consistent Slack lifecycle delivery:

1. Open VM Window 1 and start the continuous runner.
2. Open VM Window 2 and submit a fresh request.
3. Monitor the latest run status and `events.jsonl` until `completed` or `failed`.
4. If a previous run is already `failed`, submit a new request because failed runs are not reprocessed.

VM Window 1:

```powershell
.\Start-VmRunner.ps1
```

VM Window 2:

```powershell
.\Start-LocalSubmit.ps1
$latest = Get-ChildItem .\shared-root\runs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content "$($latest.FullName)\status.json"
if (Test-Path "$($latest.FullName)\events.jsonl") { Get-Content "$($latest.FullName)\events.jsonl" -Wait }
```

Single-terminal VM workflow:

```powershell
Set-Location .\scripts
.\Run-OneTerminal.ps1 -NotificationChannel terminal
```

Default one-command demo workflow (recommended):

```powershell
Set-Location .\scripts
.\Run-OneTerminal.ps1
```

`Run-OneTerminal.ps1` now performs all of the following automatically:

- resolves project, shared-root, and JMeter paths
- sets/overrides test plan path in runtime request payload
- archives active queued request pointers before submit (fresh-start behavior)
- optionally kills existing runner/JMeter processes when requested
- sends startup Slack notification in `slack`/`both` mode
- submits and processes one run, then prints final status/events

For demo/default Slack behavior with startup notification and lifecycle notifications:

```powershell
Set-Location .\scripts
.\Run-OneTerminal.ps1
```

Manual Slack connectivity check:

```powershell
$payload = @{
   event_type = "test_started"
   run_id = "manual-slack-check"
   message = "manual slack check"
   test_name = "connectivity"
   details = @{ environment = "vm"; index = 1 }
   occurred_at = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Compress
$payload | node .\tools\slack-notifier\dist\cli.js
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
         "test_plan_path": "L:/Latest_Script_Sqlserver/Xinsepect_RDS_SQL_BabelfishTestplan_Latest_07_21.jmx",
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
- Confirm a fresh run is queued after runner restart; runner startup alone does not emit lifecycle events.
- Confirm local `-Watch` mode is only used when local can read the same shared-root as VM.

## Local Verification Gate (Before Push)

Before committing or pushing any script changes, run local verification and keep the successful output in terminal history.

```powershell
Set-Location "C:\Users\erraguntlaaditya\OneDrive - Nagarro\Documents\Practice\MCPServer\Performance-Orchestration-AI\SDD-project"
foreach ($file in @('scripts\\Run-OneTerminal.ps1','Start-LocalSubmit.ps1','scripts\\Start-LocalSubmit.ps1','Start-VmRunner.ps1','scripts\\Start-VmRunner.ps1')) { [void][scriptblock]::Create((Get-Content $file -Raw)); Write-Host "OK $file" }
python -m pytest tests/unit/test_config.py tests/unit/test_vm_runner.py -q
```

Only push to git after the commands above succeed.
