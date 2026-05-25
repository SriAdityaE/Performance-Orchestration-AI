param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$RequestFile = "request.json",
    [string]$PerfSharedRoot,
    [string]$JMeterHome,
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel = "slack",
    [string]$SlackWebhookUrl
)

$ErrorActionPreference = "Stop"

if (-not $PerfSharedRoot) {
    $PerfSharedRoot = Join-Path $ProjectRoot "shared-root"
}

if (-not $JMeterHome) {
    if ($env:JMETER_HOME -and (Test-Path $env:JMETER_HOME)) {
        $JMeterHome = $env:JMETER_HOME
    } elseif (Test-Path "L:\apache-jmeter-5.5_New\apache-jmeter-5.5") {
        $JMeterHome = "L:\apache-jmeter-5.5_New\apache-jmeter-5.5"
    } elseif (Test-Path "C:\apache-jmeter-5.5_New\apache-jmeter-5.5") {
        $JMeterHome = "C:\apache-jmeter-5.5_New\apache-jmeter-5.5"
    } else {
        throw "Unable to resolve JMETER_HOME. Pass -JMeterHome or set JMETER_HOME."
    }
}

$submitScript = Join-Path $ProjectRoot "Start-LocalSubmit.ps1"
$runnerScript = Join-Path $ProjectRoot "Start-VmRunner.ps1"

if (-not (Test-Path $submitScript)) {
    throw "Missing submit script: $submitScript"
}
if (-not (Test-Path $runnerScript)) {
    throw "Missing runner script: $runnerScript"
}

function Send-StartupSlackNotification {
    param(
        [string]$WebhookUrl,
        [string]$ProjectRoot,
        [string]$RequestFile,
        [string]$NotificationChannel
    )

    if ($NotificationChannel -notin @("slack", "both")) {
        return
    }

    if (-not $WebhookUrl) {
        Write-Warning "Slack startup notification skipped: SLACK_WEBHOOK_URL is not configured."
        return
    }

    $payload = @{
        text = "RUN-ONETERMINAL STARTED`nProject: $ProjectRoot`nRequest: $RequestFile`nHost: $env:COMPUTERNAME`nTime: $((Get-Date).ToUniversalTime().ToString('o'))"
    } | ConvertTo-Json -Compress

    try {
        Invoke-RestMethod -Uri $WebhookUrl -Method Post -ContentType "application/json" -Body $payload | Out-Null
        Write-Host "Startup Slack notification sent." -ForegroundColor Green
    }
    catch {
        Write-Warning "Startup Slack notification failed: $($_.Exception.Message)"
    }
}

if (-not $SlackWebhookUrl) {
    $SlackWebhookUrl = $env:SLACK_WEBHOOK_URL
}

Send-StartupSlackNotification `
  -WebhookUrl $SlackWebhookUrl `
  -ProjectRoot $ProjectRoot `
  -RequestFile $RequestFile `
  -NotificationChannel $NotificationChannel

function Send-SlackPreflightNotification {
    param(
        [string]$ProjectRoot,
        [string]$NotificationChannel
    )

    if ($NotificationChannel -notin @("slack", "both")) {
        return
    }

    $notifierCli = Join-Path $ProjectRoot "tools\slack-notifier\dist\cli.js"
    if (-not (Test-Path $notifierCli)) {
        throw "Slack notifier script not found: $notifierCli. Build it with npm run build:notifier"
    }

    $payload = @{
        event_type = "test_started"
        run_id = "one-terminal-preflight"
        message = "One-terminal workflow started"
        test_name = "preflight"
        details = @{ phase = "pre_submit" }
        occurred_at = (Get-Date).ToUniversalTime().ToString("o")
    } | ConvertTo-Json -Compress

    $payload | node $notifierCli | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Slack preflight notification failed (exit code $LASTEXITCODE)."
    }
    Write-Host "Slack preflight notification sent." -ForegroundColor Green
}

Send-SlackPreflightNotification -ProjectRoot $ProjectRoot -NotificationChannel $NotificationChannel

Write-Host "[1/4] Submitting run request..." -ForegroundColor Cyan
& $submitScript `
  -ProjectRoot $ProjectRoot `
  -RequestFile $RequestFile `
  -PerfSharedRoot $PerfSharedRoot `
  -JMeterHome $JMeterHome `
  -NotificationChannel $NotificationChannel

if ($LASTEXITCODE -ne 0) {
    throw "Start-LocalSubmit.ps1 failed with exit code $LASTEXITCODE"
}

$latestRun = Get-ChildItem (Join-Path $PerfSharedRoot "runs") -Directory |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $latestRun) {
    throw "No run folder found in $PerfSharedRoot\runs after submit."
}

$runId = $latestRun.Name
$runDir = $latestRun.FullName
Write-Host "[2/4] Submitted run: $runId" -ForegroundColor Green

Write-Host "[3/4] Processing queued run in same terminal..." -ForegroundColor Cyan
& $runnerScript `
  -ProjectRoot $ProjectRoot `
  -PerfSharedRoot $PerfSharedRoot `
  -JMeterHome $JMeterHome `
  -NotificationChannel $NotificationChannel `
  -Once

if ($LASTEXITCODE -ne 0) {
    Write-Warning "VM runner exited with code $LASTEXITCODE"
}

Write-Host "[4/4] Final run status and events" -ForegroundColor Cyan
$statusPath = Join-Path $runDir "status.json"
$eventsPath = Join-Path $runDir "events.jsonl"

if (Test-Path $statusPath) {
    Get-Content $statusPath
} else {
    Write-Warning "status.json not found at $statusPath"
}

if (Test-Path $eventsPath) {
    Write-Host "--- events.jsonl ---" -ForegroundColor Yellow
    Get-Content $eventsPath
} else {
    Write-Warning "events.jsonl not found at $eventsPath"
}
