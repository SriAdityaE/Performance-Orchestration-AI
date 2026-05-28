param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PerfSharedRoot,
    [int]$KeepLatestRuns = 0,
    [switch]$DeleteInsteadOfArchive
)

$ErrorActionPreference = "Stop"

if (-not $PerfSharedRoot) {
    $PerfSharedRoot = Join-Path $ProjectRoot "shared-root"
}

$requestsDir = Join-Path $PerfSharedRoot "requests"
$runsDir = Join-Path $PerfSharedRoot "runs"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$requestStaleDir = Join-Path $requestsDir "stale"
$runArchiveRoot = Join-Path $runsDir "archive"
$runArchiveDir = Join-Path $runArchiveRoot $timestamp

if (-not (Test-Path $requestsDir)) {
    throw "Requests directory not found: $requestsDir"
}
if (-not (Test-Path $runsDir)) {
    throw "Runs directory not found: $runsDir"
}

Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "PerfSharedRoot: $PerfSharedRoot"
Write-Host "KeepLatestRuns: $KeepLatestRuns"
Write-Host "Mode: $([string]::new($(if ($DeleteInsteadOfArchive) { 'delete' } else { 'archive' })))"
Write-Host ""

# 1) Clear queued request pointers (active queue only)
$queuePointers = Get-ChildItem $requestsDir -File -Filter "*.json" -ErrorAction SilentlyContinue
if ($queuePointers.Count -eq 0) {
    Write-Host "No active request pointers found."
} elseif ($DeleteInsteadOfArchive) {
    $queuePointers | Remove-Item -Force
    Write-Host "Deleted $($queuePointers.Count) active request pointer(s)." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path $requestStaleDir -Force | Out-Null
    $queuePointers | Move-Item -Destination $requestStaleDir -Force
    Write-Host "Archived $($queuePointers.Count) active request pointer(s) to: $requestStaleDir" -ForegroundColor Yellow
}

# 2) Clear previous run directories, optionally keeping latest N
$runDirs = Get-ChildItem $runsDir -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "archive" } |
    Sort-Object LastWriteTime -Descending

$toKeep = @()
if ($KeepLatestRuns -gt 0 -and $runDirs.Count -gt 0) {
    $toKeep = $runDirs | Select-Object -First $KeepLatestRuns
}

$toClear = @($runDirs | Where-Object { $toKeep -notcontains $_ })

if ($toClear.Count -eq 0) {
    Write-Host "No run directories selected for cleanup."
} elseif ($DeleteInsteadOfArchive) {
    $toClear | Remove-Item -Recurse -Force
    Write-Host "Deleted $($toClear.Count) run directorie(s)." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path $runArchiveDir -Force | Out-Null
    $toClear | Move-Item -Destination $runArchiveDir -Force
    Write-Host "Archived $($toClear.Count) run directorie(s) to: $runArchiveDir" -ForegroundColor Yellow
}

if ($toKeep.Count -gt 0) {
    Write-Host "Kept latest run directorie(s):" -ForegroundColor Green
    $toKeep | ForEach-Object { Write-Host " - $($_.Name)" }
}

Write-Host ""
Write-Host "Queue reset complete." -ForegroundColor Green
