# Performance Orchestration AI

This project orchestrates performance-test execution on VM, captures artifacts and lifecycle status, and sends stakeholder-facing notifications/reports to Slack.

## What It Does

- Accepts run requests (single-run or two-run comparison).
- Queues requests in a shared-root contract (`requests/` and `runs/`).
- Executes JMeter on VM.
- Stores status, events, logs, artifacts, and reports per run.
- Sends lifecycle notifications and final report to Slack.

## Core Flow

1. Submit request.
2. VM runner picks queued request.
3. JMeter executes and writes `.jtl` results.
4. Metrics are parsed and validated.
5. Final report is generated.
6. Slack receives lifecycle notifications and final report.

## Key Paths

- Request template: `request.json`
- Shared root (default): `<project-root>\shared-root`
- Queued pointers: `shared-root\requests\*.json`
- Run folders: `shared-root\runs\<run_id>\`
- Per-run logs: `shared-root\runs\<run_id>\logs\`
- JMeter script (default): `L:\AI_SPEC\Xinspect_JMeterTest.jmx`
- JTL artifacts (date bucket + backup slots): `shared-root\runs\<run_id>\artifacts\jtl\<DD-MM(MMM-Do)>\Run<index>_<YYYYMMDD-HHMMSS>\test_<index>.jtl`
- Per-test summary backups: `shared-root\runs\<run_id>\reports\<DD-MM(MMM-Do)>\Run<index>_<YYYYMMDD-HHMMSS>\summary.json`
- Final report (timestamped backup): `shared-root\runs\<run_id>\reports\<DD-MM(MMM-Do)>\final_report_<YYYYMMDD-HHMMSS>.json`
- Final report (latest compatibility copy): `shared-root\runs\<run_id>\reports\final_report.json`
- External mirror backups (default, round-based naming): `L:\testlogs\<run_id>\<DD-MM(MMM-Do)>\<YYYYMMDD>_<test_name>_round<index>_<HHMMSS>\...`
- Events log: `shared-root\runs\<run_id>\events.jsonl`

## Run Scripts

### Simplest Demo Command (VM)

Run from `scripts` folder:

```powershell
.\Run-OneTerminal.ps1
```

This command handles submit + process + final status/events in one terminal.
By default, it uses Slack channel and sends one startup notification plus standard lifecycle notifications.
It also archives previously queued request pointers before submit so the latest request is executed.

### Useful One-Terminal Options

```powershell
.\Run-OneTerminal.ps1 -NotificationChannel terminal
.\Run-OneTerminal.ps1 -KillPreviousProcesses
.\Run-OneTerminal.ps1 -SkipQueueCleanup
.\.\Run-OneTerminal.ps1 -TestPlanPath "L:\AI_SPEC\Xinspect_JMeterTest.jmx"
```

### Wrapper Scripts

- Local submit wrapper: `Start-LocalSubmit.ps1`
- VM runner wrapper: `Start-VmRunner.ps1`

Implementation scripts live under `scripts/`:

- `scripts/Start-LocalSubmit.ps1`
- `scripts/Start-VmRunner.ps1`
- `scripts/Run-OneTerminal.ps1`
- `scripts/Reset-RunQueue.ps1`

## Local vs VM

- Local terminal is used for request preparation/submission and optional watch mode.
- VM terminal executes JMeter and produces runtime lifecycle/report outputs.
- For reliable demos, use VM one-terminal flow (`scripts/Run-OneTerminal.ps1`).

## Reporting Style

Final report is designed for business-ready sharing with:

- Test summary
- Aggregate-style metric visibility
- Transaction-level aggregate rows derived from JMeter `label` values (plus `TOTAL`)
- Transactions detected count and transaction name list
- Executed test plan path for traceability (`test_plan_path`)
- Test observations
- Prior-run comparison (when available) — see **Cross-Run Comparison** below
- Verdict on best run and readiness

Default report generation does not hardcode a single aggregate label (for example, `ALL`).
It preserves discovered transaction labels from the parsed JTL/CSV output.

### Cross-Run Comparison (Senior Architect Format)

When two or more runs exist for the same test, the report automatically includes a structured comparison block in the Slack notification:

```
Run Comparison — Previous run (2026-05-29 14:01) vs. Current run (2026-05-29 14:05):
Throughput:         13.28 req/s → 13.26 req/s  (stable)
Avg Response Time:  2.75 ms → 1.94 ms  (improved 29%)
P95 Response Time:  5.00 ms → 3.00 ms  (improved 40%)
P99 Response Time:  8.00 ms → 7.00 ms  (improved 13%)
Error Rate:         0.00% → 0.00%  (stable)
Verdict: Current run is preferred — 3 metrics improved with 0 regressions detected. Approve current run as the new baseline.
```

- **Both run timestamps** appear in the heading so stakeholders know the exact window being compared.
- **FROM → TO** values are shown for every metric (Throughput, Avg Response Time, P95, P99, Error Rate) — not just percentage changes.
- **Verdict** gives an explicit action recommendation: approve, review, or treat as equivalent.

## Verification Before Push

Run local script parse checks and targeted tests before pushing script changes:

```powershell
# Run from your repository root
Set-Location "<your-repo-root>"
foreach ($file in @('scripts\\Run-OneTerminal.ps1','Start-LocalSubmit.ps1','scripts\\Start-LocalSubmit.ps1','Start-VmRunner.ps1','scripts\\Start-VmRunner.ps1')) { [void][scriptblock]::Create((Get-Content $file -Raw)); Write-Host "OK $file" }
python -m pytest tests/unit/test_config.py tests/unit/test_vm_runner.py -q
```

## Related Specs

- `specs/001-perf-test-orchestration/spec.md`
- `specs/001-perf-test-orchestration/quickstart.md`
- `specs/001-perf-test-orchestration/contracts/shared-root-run-contract.md`
