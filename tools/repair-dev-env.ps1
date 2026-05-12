param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-ProjectRoot {
    $scriptPath = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptPath "..")).Path
}

function Assert-ChildPath {
    param(
        [string]$Parent,
        [string]$Child
    )

    $resolvedParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    $resolvedChild = [System.IO.Path]::GetFullPath($Child).TrimEnd('\')
    if (-not $resolvedChild.StartsWith($resolvedParent + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside project root: $resolvedChild"
    }
}

function Find-Python {
    $candidates = @()

    foreach ($command in @("python", "py", "python3")) {
        $found = Get-Command $command -ErrorAction SilentlyContinue
        if ($found) {
            $candidates += $found.Source
        }
    }

    $pathCandidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
    )
    $candidates += $pathCandidates

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        try {
            $version = & $candidate --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$version" -match "Python 3\.") {
                return $candidate
            }
        }
        catch {
            continue
        }
    }

    throw "No runnable Python 3 interpreter was found."
}

$projectRoot = Resolve-ProjectRoot
Set-Location $projectRoot

Write-Step "Project"
Write-Host "Root: $projectRoot"

Write-Step "Python discovery"
$python = Find-Python
$pythonVersion = & $python --version
Write-Host "Python: $python"
Write-Host "Version: $pythonVersion"

$venvPath = Join-Path $projectRoot ".venv"
Assert-ChildPath -Parent $projectRoot -Child $venvPath

Write-Step "Rebuild virtual environment"
if (Test-Path -LiteralPath $venvPath) {
    Write-Host "Removing damaged .venv: $venvPath"
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

& $python -m venv $venvPath
if ($LASTEXITCODE -ne 0) {
    throw "python -m venv failed."
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

Write-Step "Verify venv"
& $venvPython --version
if ($LASTEXITCODE -ne 0) {
    throw "venv python --version failed."
}
& $venvPython -c "import sys, pathlib; print(sys.executable); print(pathlib.Path.cwd())"
if ($LASTEXITCODE -ne 0) {
    throw "venv python smoke test failed."
}

if (-not $SkipInstall) {
    Write-Step "Install project dependencies"
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed."
    }
    & $venvPip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed."
    }
}

Write-Step "Toolchain verification"
& $venvPython -m pip --version
if ($LASTEXITCODE -ne 0) {
    throw "pip verification failed."
}
if (-not $SkipInstall) {
    & $venvPython -m pytest --version
    if ($LASTEXITCODE -ne 0) {
        throw "pytest verification failed."
    }
}
else {
    Write-Host "Skipped pytest verification because -SkipInstall was used."
}

Write-Step "Git verification"
git status --short --branch

Write-Step "Done"
Write-Host "Use this interpreter from Codex/PowerShell:"
Write-Host "$venvPython"
