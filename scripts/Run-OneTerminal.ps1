param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$RequestFile = "request.json",
    [string]$PerfSharedRoot,
    [string]$JMeterHome,
    [string]$TestPlanPath = "L:\Latest_Script_Sqlserver\Xinsepect_RDS_SQL_BabelfishTestplan_Latest_07_21.jmx",
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel = "slack",
    [string]$SlackWebhookUrl,
    [switch]$KillPreviousProcesses,
    [switch]$SkipQueueCleanup
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

if (-not (Test-Path $TestPlanPath)) {
    throw "Configured TestPlanPath not found: $TestPlanPath"
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

function Stop-PreviousProcesses {
    Write-Host "Stopping previous runner/JMeter processes..." -ForegroundColor Yellow

    $runnerProcs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match "perf_orchestrator\.runner\.main" }
    foreach ($proc in $runnerProcs) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped runner process PID=$($proc.ProcessId)"
    }

    $jmeterJavaProcs = Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
        Where-Object { $_.CommandLine -match "ApacheJMeter|jmeter" }
    foreach ($proc in $jmeterJavaProcs) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped JMeter java process PID=$($proc.ProcessId)"
    }
}

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
        Write-Host "Archived $($pointers.Count) request pointer(s) to $staleDir" -ForegroundColor Yellow
    } else {
        Write-Host "No active request pointers to archive."
    }
}

function Build-RunRequestFile {
    param(
        [string]$RequestFile,
        [string]$ProjectRoot,
        [string]$TestPlanPath,
        [string]$NotificationChannel,
        [string]$PerfSharedRoot
    )

    $resolvedRequestFile = if ([System.IO.Path]::IsPathRooted($RequestFile)) {
        $RequestFile
    } else {
        Join-Path $ProjectRoot $RequestFile
    }

    if (-not (Test-Path $resolvedRequestFile)) {
        throw "Request file not found: $resolvedRequestFile"
    }

    $payload = Get-Content $resolvedRequestFile -Raw | ConvertFrom-Json
    foreach ($test in $payload.tests) {
        $test.test_plan_path = ($TestPlanPath -replace "\\", "/")
    }
    $payload.notification.channel = $NotificationChannel

    $runtimeDir = Join-Path $PerfSharedRoot "runtime"
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    $runtimeRequestFile = Join-Path $runtimeDir ("request-runtime-" + (Get-Date -Format "yyyyMMddHHmmss") + ".json")
    $payload | ConvertTo-Json -Depth 20 | Set-Content $runtimeRequestFile

    return $runtimeRequestFile
}

if (-not $SlackWebhookUrl) {
    $SlackWebhookUrl = $env:SLACK_WEBHOOK_URL
}

if ($KillPreviousProcesses) {
        Stop-PreviousProcesses
}

if (-not $SkipQueueCleanup) {
        Reset-RequestQueue -PerfSharedRoot $PerfSharedRoot
}

$runtimeRequestFile = Build-RunRequestFile `
    -RequestFile $RequestFile `
    -ProjectRoot $ProjectRoot `
    -TestPlanPath $TestPlanPath `
    -NotificationChannel $NotificationChannel `
    -PerfSharedRoot $PerfSharedRoot

Send-StartupSlackNotification `
  -WebhookUrl $SlackWebhookUrl `
  -ProjectRoot $ProjectRoot `
    -RequestFile $runtimeRequestFile `
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
    -RequestFile $runtimeRequestFile `
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
