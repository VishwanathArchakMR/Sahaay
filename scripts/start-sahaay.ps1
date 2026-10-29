<#
.SYNOPSIS
Unified launcher for Sahaay AI Desktop Agent.

.DESCRIPTION
Checks runtime prerequisites, builds any missing components, ensures browser native
messaging host registration, and starts the supervised application runtime.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         Launching Sahaay Windows AI Agent Runtime         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python virtual environment
$PythonExe = Join-Path $RepoRoot "core\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[SETUP] Python virtual environment not found. Setting up..." -ForegroundColor Yellow
    & "$PSScriptRoot\setup.ps1"
}

# 2. Check Windows Companion Controller binary
$ControllerRelease = Join-Path $RepoRoot "apps\windows-companion\Sahaay.Controller\bin\Release\net10.0-windows\Sahaay.Controller.exe"
$ControllerDebug = Join-Path $RepoRoot "apps\windows-companion\Sahaay.Controller\bin\Debug\net10.0-windows\Sahaay.Controller.exe"
if (-not (Test-Path $ControllerRelease) -and -not (Test-Path $ControllerDebug)) {
    Write-Host "[BUILD] Windows companion controller not yet built. Building..." -ForegroundColor Yellow
    & "$PSScriptRoot\build-companion.ps1"
}

# 3. Check Native Messaging Host registration
$HostRegPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.sahaay.nativehost"
if (-not (Test-Path $HostRegPath)) {
    Write-Host "[INSTALL] Browser native messaging host not registered. Installing..." -ForegroundColor Yellow
    & "$PSScriptRoot\install-browser-native-host.ps1"
}

# 4. Start Supervised Desktop Application
Write-Host "`nStarting Supervised Sahaay Desktop..." -ForegroundColor Green
Push-Location (Join-Path $RepoRoot "apps\desktop")
try {
    npm run dev
} finally {
    Pop-Location
}
