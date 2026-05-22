param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$RequestFile = "request.json",
    [string]$PerfSharedRoot,
    [string]$JMeterHome,
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel = "terminal"
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

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "src"
    $env:PERF_SHARED_ROOT = $PerfSharedRoot
    $env:JMETER_HOME = $JMeterHome
    $env:NOTIFICATION_CHANNEL = $NotificationChannel

    Write-Host "Submitting request from: $resolvedRequestFile"
    Write-Host "PERF_SHARED_ROOT: $env:PERF_SHARED_ROOT"
    python -m perf_orchestrator.cli.main --request-file $resolvedRequestFile
}
finally {
    Pop-Location
}
