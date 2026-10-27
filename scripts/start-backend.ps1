# Starts the Sahaay Core Backend Orchestrator on 127.0.0.1:8000
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PythonVenv = "$RepoRoot\core\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonVenv)) {
    Write-Host "Virtual environment not found. Please run .\scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Sahaay Core Backend on 127.0.0.1:8000..." -ForegroundColor Cyan
& $PythonVenv -m uvicorn sahaay_core.main:app --host 127.0.0.1 --port 8000
