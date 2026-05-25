# Script Shortcuts

## VM Runner

Run continuously with defaults:

```powershell
.\Start-VmRunner.ps1
```

Run once:

```powershell
.\Start-VmRunner.ps1 -Once
```

## Local Submit

```powershell
.\Start-LocalSubmit.ps1
```

Show run stats in the same local terminal after submit:

```powershell
.\Start-LocalSubmit.ps1 -Watch
```

Customize polling/timeout:

```powershell
.\Start-LocalSubmit.ps1 -Watch -PollSeconds 2 -WatchTimeoutSeconds 1200
```

## One-Terminal VM Workflow

Submit + process + print final status/events in a single terminal:

```powershell
.\Run-OneTerminal.ps1
```

By default, this command runs in `slack` mode and sends a startup Slack notification before submit/processing.
It then sends normal lifecycle notifications during run processing.
It performs fresh-start queue cleanup by default, creates a runtime request payload, and enforces a known-good test plan path.

Optional process cleanup for stale runner/JMeter processes before run:

```powershell
.\Run-OneTerminal.ps1 -KillPreviousProcesses
```

Skip queue cleanup when you explicitly want to preserve queued pointers:

```powershell
.\Run-OneTerminal.ps1 -SkipQueueCleanup
```

Override test plan path for a different demo script:

```powershell
.\Run-OneTerminal.ps1 -TestPlanPath "L:\Latest_Script_Sqlserver\MyOtherPlan.jmx"
```

For terminal-only lifecycle output (no Slack popups):

```powershell
.\Run-OneTerminal.ps1 -NotificationChannel terminal
```

## Reset Previous Runs (VM)

Archive previous request pointers and old run folders before a fresh demo run:

```powershell
.\Reset-RunQueue.ps1
```

Keep latest 1 run and archive everything else:

```powershell
.\Reset-RunQueue.ps1 -KeepLatestRuns 1
```

Delete mode (destructive):

```powershell
.\Reset-RunQueue.ps1 -DeleteInsteadOfArchive
```

## Notes

- Both sides must point to the same physical shared-root storage.
- The root-level wrappers resolve sensible defaults from the current checkout and environment.
- Override `-JMeterHome`, `-PerfSharedRoot`, or `-NotificationChannel` only when the defaults do not fit the current machine.
- Starting the VM runner does not send Slack by itself; Slack lifecycle messages are emitted only when a queued run is processed.
- If the latest run is already `failed`, submit a fresh run using `.\Start-LocalSubmit.ps1`.
- Local `-Watch` mode requires `PERF_SHARED_ROOT` to point to the same physical storage the VM runner uses.
