param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".")).Path,
    [string]$PerfSharedRoot,
    [string]$JMeterHome,
    [ValidateSet("terminal", "slack", "teams", "both")]
    [string]$NotificationChannel = "slack",
    [string]$SlackWebhookUrl,
    [switch]$Once
)

$targetScript = Join-Path $PSScriptRoot "scripts\Start-VmRunner.ps1"
if (-not (Test-Path $targetScript)) {
    throw "Missing target script: $targetScript"
}

function Resolve-JMeterHome {
    param(
        [string]$ProjectRoot
    )

    if ($env:JMETER_HOME -and (Test-Path $env:JMETER_HOME)) {
        return $env:JMETER_HOME
    }

    $candidatePaths = @(
        "L:\apache-jmeter-5.5_New\apache-jmeter-5.5",
        "C:\apache-jmeter-5.5_New\apache-jmeter-5.5",
        (Join-Path $ProjectRoot "apache-jmeter-5.5"),
        $ProjectRoot
    )

    foreach ($candidatePath in $candidatePaths) {
        if ($candidatePath -and (Test-Path $candidatePath)) {
            return $candidatePath
        }
    }

    return $null
}

if (-not $PerfSharedRoot) {
    $PerfSharedRoot = Join-Path $ProjectRoot "shared-root"
}

if (-not $JMeterHome) {
    $JMeterHome = Resolve-JMeterHome -ProjectRoot $ProjectRoot
}

if (-not $JMeterHome) {
    throw "Unable to resolve JMETER_HOME. Pass -JMeterHome or set the JMETER_HOME environment variable."
}

& $targetScript -ProjectRoot $ProjectRoot -PerfSharedRoot $PerfSharedRoot -JMeterHome $JMeterHome -NotificationChannel $NotificationChannel -SlackWebhookUrl $SlackWebhookUrl -Once:$Once
exit $LASTEXITCODE
