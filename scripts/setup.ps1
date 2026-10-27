# Sets up Sahaay Monorepo (Python virtualenv, Node dependencies, and extension build)
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Write-Host "Setting up Sahaay Monorepo at: $RepoRoot" -ForegroundColor Cyan

# 1. Setup Python backend
Write-Host "`n1. Setting up Python backend (core/)..." -ForegroundColor Yellow
$uvPath = "$env:APPDATA\Python\Python312\Scripts\uv.exe"
Push-Location "$RepoRoot\core"
try {
    if (Test-Path $uvPath) {
        Write-Host "Using uv at: $uvPath"
        & $uvPath venv .venv
        & $uvPath pip install -e ".[dev]" --python .\.venv\Scripts\python.exe
    } else {
        Write-Host "Creating standard venv..."
        python -m venv .venv
        .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
    }
    Write-Host "[OK] Backend dependencies installed." -ForegroundColor Green
} finally {
    Pop-Location
}

# 2. Setup Browser Extension
Write-Host "`n2. Setting up Browser Extension (apps/browser-extension)..." -ForegroundColor Yellow
Push-Location "$RepoRoot\apps\browser-extension"
try {
    npm install
    npm run build
    Write-Host "[OK] Browser extension compiled." -ForegroundColor Green
} finally {
    Pop-Location
}

# 3. Setup Desktop App
Write-Host "`n3. Setting up Desktop App (apps/desktop)..." -ForegroundColor Yellow
Push-Location "$RepoRoot\apps\desktop"
try {
    npm install
    npm run build
    Write-Host "[OK] Desktop application compiled." -ForegroundColor Green
} finally {
    Pop-Location
}

# 4. Setup Windows Companion
Write-Host "`n4. Setting up Windows Native Companion (apps/windows-companion)..." -ForegroundColor Yellow
try {
    & "$PSScriptRoot\build-companion.ps1"
    Write-Host "[OK] Windows companion solution compiled." -ForegroundColor Green
} catch {
    Write-Host "[WARN] Windows companion build skipped or encountered issue: $_" -ForegroundColor Yellow
}

Write-Host "`n=== Sahaay Setup Completed Successfully ===" -ForegroundColor Green
