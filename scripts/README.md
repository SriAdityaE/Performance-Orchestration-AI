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

## Notes

- Both sides must point to the same physical shared-root storage.
- The root-level wrappers resolve sensible defaults from the current checkout and environment.
- Override `-JMeterHome`, `-PerfSharedRoot`, or `-NotificationChannel` only when the defaults do not fit the current machine.
- Starting the VM runner does not send Slack by itself; Slack lifecycle messages are emitted only when a queued run is processed.
- If the latest run is already `failed`, submit a fresh run using `.\Start-LocalSubmit.ps1`.
