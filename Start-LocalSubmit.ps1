param(
    [string]$ProjectRoot,
    [string]$RequestFile,
    [string]$PerfSharedRoot,
    [string]$JMeterHome,
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel
)

$targetScript = Join-Path $PSScriptRoot "scripts\Start-LocalSubmit.ps1"
if (-not (Test-Path $targetScript)) {
    throw "Missing target script: $targetScript"
}

& $targetScript -ProjectRoot $ProjectRoot -RequestFile $RequestFile -PerfSharedRoot $PerfSharedRoot -JMeterHome $JMeterHome -NotificationChannel $NotificationChannel
exit $LASTEXITCODE
