param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PerfSharedRoot,
    [string]$JMeterHome = "L:\apache-jmeter-5.5_New\apache-jmeter-5.5",
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel = "slack",
    [string]$SlackWebhookUrl,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

if (-not $PerfSharedRoot) {
    $PerfSharedRoot = Join-Path $ProjectRoot "shared-root"
}

if ($NotificationChannel -eq "slack" -and -not $SlackWebhookUrl -and -not $env:SLACK_WEBHOOK_URL) {
    throw "Slack channel selected but Slack webhook is missing. Pass -SlackWebhookUrl or set SLACK_WEBHOOK_URL."
}

if (-not (Test-Path $JMeterHome)) {
    throw "JMETER_HOME path not found: $JMeterHome"
}

New-Item -ItemType Directory -Path (Join-Path $PerfSharedRoot "requests") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PerfSharedRoot "runs") -Force | Out-Null

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "src"
    $env:PERF_SHARED_ROOT = $PerfSharedRoot
    $env:JMETER_HOME = $JMeterHome
    $env:NOTIFICATION_CHANNEL = $NotificationChannel

    if ($SlackWebhookUrl) {
        $env:SLACK_WEBHOOK_URL = $SlackWebhookUrl
    }

    Write-Host "Starting VM runner"
    Write-Host "PERF_SHARED_ROOT: $env:PERF_SHARED_ROOT"
    Write-Host "JMETER_HOME: $env:JMETER_HOME"

    if ($Once) {
        python -m perf_orchestrator.runner.main --once
    }
    else {
        python -m perf_orchestrator.runner.main
    }
}
finally {
    Pop-Location
}
