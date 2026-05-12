$ErrorActionPreference = "Stop"

$scriptPath = Split-Path -Parent $PSCommandPath
$projectRoot = (Resolve-Path (Join-Path $scriptPath "..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

Set-Location $projectRoot

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment is missing. Run tools\repair-dev-env.ps1 first."
}

& $venvPython -m pytest @args
if ($LASTEXITCODE -ne 0) {
    throw "pytest failed with exit code $LASTEXITCODE."
}
