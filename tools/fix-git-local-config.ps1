$ErrorActionPreference = "Stop"

$scriptPath = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptPath "..")).Path

Set-Location $projectRoot

$excludeFile = Join-Path $projectRoot ".git\info\exclude"
if (-not (Test-Path -LiteralPath $excludeFile)) {
    throw "Missing local exclude file: $excludeFile"
}

git config --local core.excludesfile ".git/info/exclude"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to set local core.excludesfile."
}

git status --short --branch
if ($LASTEXITCODE -ne 0) {
    throw "git status failed."
}
