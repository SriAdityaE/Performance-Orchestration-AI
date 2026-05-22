param(
    [string]$ProjectRoot,
    [string]$PerfSharedRoot,
    [string]$JMeterHome,
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel,
    [string]$SlackWebhookUrl,
    [switch]$Once
)

$targetScript = Join-Path $PSScriptRoot "scripts\Start-VmRunner.ps1"
if (-not (Test-Path $targetScript)) {
    throw "Missing target script: $targetScript"
}

& $targetScript -ProjectRoot $ProjectRoot -PerfSharedRoot $PerfSharedRoot -JMeterHome $JMeterHome -NotificationChannel $NotificationChannel -SlackWebhookUrl $SlackWebhookUrl -Once:$Once
exit $LASTEXITCODE
