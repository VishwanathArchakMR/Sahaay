# Runs all automated quality checks and test suites across Sahaay
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PytestExe = "$RepoRoot\core\.venv\Scripts\pytest.exe"
$RuffExe = "$RepoRoot\core\.venv\Scripts\ruff.exe"

Write-Host "=== Running Sahaay Quality Baseline & Test Suite ===" -ForegroundColor Cyan

# 1. Python Linting & Formatting Check
if (Test-Path $RuffExe) {
    Write-Host "`n1. Running Ruff Linter & Formatter..." -ForegroundColor Yellow
    & $RuffExe check "$RepoRoot\core" "$RepoRoot\tests"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Ruff linting failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "[PASS] Ruff linter passed." -ForegroundColor Green
}

# 2. Automated Test Suite (Unit, Privacy, Security, Contracts)
if (Test-Path $PytestExe) {
    Write-Host "`n2. Running Pytest Suite..." -ForegroundColor Yellow
    $env:PYTHONPATH = "$RepoRoot\core\src"
    & $PytestExe "$RepoRoot\tests"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Pytest tests failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "[PASS] All automated Python tests passed." -ForegroundColor Green
}

# 2b. .NET Windows Companion Test Suite
$localDotnet = "$env:LOCALAPPDATA\Microsoft\dotnet"
if (Test-Path "$localDotnet\dotnet.exe") {
    $env:PATH = "$localDotnet;$env:PATH"
    $env:DOTNET_ROOT = $localDotnet
}
if (Get-Command dotnet -ErrorAction SilentlyContinue) {
    Write-Host "`n2b. Running .NET Companion Test Suite..." -ForegroundColor Yellow
    dotnet test "$RepoRoot\apps\windows-companion\Sahaay.sln"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] .NET companion tests failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "[PASS] .NET companion tests passed." -ForegroundColor Green
}

# 3. Browser Extension Typecheck
Write-Host "`n3. Checking Browser Extension..." -ForegroundColor Yellow
Push-Location "$RepoRoot\apps\browser-extension"
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Browser extension typecheck failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "[PASS] Browser extension typecheck passed." -ForegroundColor Green
} finally {
    Pop-Location
}

# 4. Desktop App Typecheck
Write-Host "`n4. Checking Desktop Application..." -ForegroundColor Yellow
Push-Location "$RepoRoot\apps\desktop"
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Desktop typecheck failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "[PASS] Desktop typecheck passed." -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n=== All Quality Checks Passed Cleanly! ===" -ForegroundColor Green
