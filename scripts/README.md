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
