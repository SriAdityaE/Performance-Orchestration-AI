param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$RequestFile = "request.json",
    [string]$PerfSharedRoot,
    [string]$JMeterHome,
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel = "terminal",
    [switch]$SkipQueueCleanup,
    [switch]$Watch,
    [int]$PollSeconds = 3,
    [int]$WatchTimeoutSeconds = 1800
)

$ErrorActionPreference = "Stop"

if (-not $PerfSharedRoot) {
    $PerfSharedRoot = Join-Path $ProjectRoot "shared-root"
}

if (-not $JMeterHome) {
    # Local submit path only validates existence, so project root is a safe default.
    $JMeterHome = $ProjectRoot
}

$resolvedRequestFile = if ([System.IO.Path]::IsPathRooted($RequestFile)) {
    $RequestFile
} else {
    Join-Path $ProjectRoot $RequestFile
}

if (-not (Test-Path $resolvedRequestFile)) {
    throw "Request file not found: $resolvedRequestFile"
}

New-Item -ItemType Directory -Path $PerfSharedRoot -Force | Out-Null

function Reset-RequestQueue {
    param(
        [string]$PerfSharedRoot
    )

    $requestsDir = Join-Path $PerfSharedRoot "requests"
    if (-not (Test-Path $requestsDir)) {
        New-Item -ItemType Directory -Path $requestsDir -Force | Out-Null
        return
    }

    $staleDir = Join-Path $requestsDir "stale"
    New-Item -ItemType Directory -Path $staleDir -Force | Out-Null

    $pointers = Get-ChildItem $requestsDir -File -Filter "*.json" -ErrorAction SilentlyContinue
    if ($pointers.Count -gt 0) {
        $pointers | Move-Item -Destination $staleDir -Force
        Write-Host "Archived $($pointers.Count) existing request pointer(s) to $staleDir" -ForegroundColor Yellow
    }
}

function Watch-RunStatus {
    param(
        [string]$PerfSharedRoot,
        [string]$RunId,
        [int]$PollSeconds,
        [int]$WatchTimeoutSeconds
    )

    $runDir = Join-Path (Join-Path $PerfSharedRoot "runs") $RunId
    $statusPath = Join-Path $runDir "status.json"
    $eventsPath = Join-Path $runDir "events.jsonl"
    $deadline = (Get-Date).AddSeconds([Math]::Max($WatchTimeoutSeconds, 10))
    $lastStatusText = ""
    $lastEventCount = 0

    Write-Host "Watching run status: $RunId"
    Write-Host "Run dir: $runDir"

    while ((Get-Date) -lt $deadline) {
        if (Test-Path $eventsPath) {
            $events = Get-Content $eventsPath -ErrorAction SilentlyContinue
            if ($events) {
                for ($i = $lastEventCount; $i -lt $events.Count; $i++) {
                    Write-Host "EVENT: $($events[$i])" -ForegroundColor Yellow
                }
                $lastEventCount = $events.Count
            }
        }

        if (Test-Path $statusPath) {
            $statusText = Get-Content $statusPath -Raw -ErrorAction SilentlyContinue
            if ($statusText -and $statusText -ne $lastStatusText) {
                $lastStatusText = $statusText
                $status = $statusText | ConvertFrom-Json
                Write-Host ("STATE: {0}" -f $status.state) -ForegroundColor Cyan
                if ($status.tests) {
                    foreach ($test in $status.tests) {
                        Write-Host ("  - Test[{0}] {1}: {2}" -f $test.index, $test.test_name, $test.state)
                    }
                }

                if ($status.state -in @("completed", "failed")) {
                    Write-Host "Run reached terminal state: $($status.state)" -ForegroundColor Green
                    return
                }
            }
        }

        Start-Sleep -Seconds ([Math]::Max($PollSeconds, 1))
    }

    Write-Warning "Watch timeout reached ($WatchTimeoutSeconds sec) before terminal run state."
}

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "src"
    $env:PERF_SHARED_ROOT = $PerfSharedRoot
    $env:JMETER_HOME = $JMeterHome
    $env:NOTIFICATION_CHANNEL = $NotificationChannel

    if (-not $SkipQueueCleanup) {
        Reset-RequestQueue -PerfSharedRoot $PerfSharedRoot
    }

    Write-Host "Submitting request from: $resolvedRequestFile"
    Write-Host "PERF_SHARED_ROOT: $env:PERF_SHARED_ROOT"
    $runId = (python -m perf_orchestrator.cli.main --request-file $resolvedRequestFile).Trim()
    if ($runId) {
        Write-Host $runId
    }

    if ($Watch -and $runId) {
        Watch-RunStatus -PerfSharedRoot $PerfSharedRoot -RunId $runId -PollSeconds $PollSeconds -WatchTimeoutSeconds $WatchTimeoutSeconds
    }
}
finally {
    Pop-Location
}
