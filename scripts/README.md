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

For terminal-only lifecycle output (no Slack popups):

```powershell
.\Run-OneTerminal.ps1 -NotificationChannel terminal
```

## Notes

- Both sides must point to the same physical shared-root storage.
- The root-level wrappers resolve sensible defaults from the current checkout and environment.
- Override `-JMeterHome`, `-PerfSharedRoot`, or `-NotificationChannel` only when the defaults do not fit the current machine.
- Starting the VM runner does not send Slack by itself; Slack lifecycle messages are emitted only when a queued run is processed.
- If the latest run is already `failed`, submit a fresh run using `.\Start-LocalSubmit.ps1`.
- Local `-Watch` mode requires `PERF_SHARED_ROOT` to point to the same physical storage the VM runner uses.
