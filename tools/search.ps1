param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Pattern
)

$ErrorActionPreference = "Stop"

$scriptPath = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptPath "..")).Path

Set-Location $projectRoot

git grep -n -- $Pattern
if ($LASTEXITCODE -eq 1) {
    exit 0
}
if ($LASTEXITCODE -ne 0) {
    throw "git grep failed with exit code $LASTEXITCODE."
}
