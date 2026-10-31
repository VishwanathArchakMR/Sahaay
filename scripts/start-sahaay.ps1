<#
.SYNOPSIS
Unified launcher for Sahaay AI Desktop Agent.

.DESCRIPTION
Checks runtime prerequisites, builds missing components, ensures browser native
messaging host registration, and starts the supervised application runtime.

.PARAMETER Mode
Execution mode: "Desktop" (default, launches Electron UI), "Headless" (starts backend and controller without GUI), or "Dev" (starts Vite dev server + Electron).

.PARAMETER DiagnosticsOnly
When specified, performs a live diagnostic probe across all components and prints a comprehensive status report without starting long-running processes.

.EXAMPLE
.\scripts\start-sahaay.ps1
Starts Sahaay in standard Desktop mode with runtime supervision.

.EXAMPLE
.\scripts\start-sahaay.ps1 -DiagnosticsOnly
Probes and displays system status across Python, .NET, browser host, and desktop UI.

.EXAMPLE
.\scripts\start-sahaay.ps1 -Mode Headless
Starts the backend and controller services for CLI or headless testing.
#>

[CmdletBinding()]
param(
    [ValidateSet("Desktop", "Headless", "Dev")]
    [string]$Mode = "Desktop",

    [switch]$DiagnosticsOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         Launching Sahaay Windows AI Agent Runtime         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# 1. PREREQUISITE CHECKS WITH ACTIONABLE ERROR GUIDANCE
# -----------------------------------------------------------------------------

# 1a. Python virtual environment
$PythonExe = Join-Path $RepoRoot "core\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[SETUP] Python virtual environment not found at core\.venv." -ForegroundColor Yellow
    Write-Host "Running automated setup: .\scripts\setup.ps1..." -ForegroundColor Yellow
    & "$PSScriptRoot\setup.ps1"
    if (-not (Test-Path $PythonExe)) {
        Write-Host "[ERROR] Python setup failed. Please execute manually:" -ForegroundColor Red
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1" -ForegroundColor Yellow
        exit 1
    }
}

# 1b. Windows Companion Controller binary
$ControllerRelease = Join-Path $RepoRoot "apps\windows-companion\Sahaay.Controller\bin\Release\net10.0-windows\Sahaay.Controller.exe"
$ControllerDebug = Join-Path $RepoRoot "apps\windows-companion\Sahaay.Controller\bin\Debug\net10.0-windows\Sahaay.Controller.exe"
$ControllerExe = if (Test-Path $ControllerRelease) { $ControllerRelease } elseif (Test-Path $ControllerDebug) { $ControllerDebug } else { $null }

if (-not $ControllerExe) {
    Write-Host "[BUILD] Windows companion controller binary not found. Building..." -ForegroundColor Yellow
    & "$PSScriptRoot\build-companion.ps1"
    $ControllerExe = if (Test-Path $ControllerRelease) { $ControllerRelease } elseif (Test-Path $ControllerDebug) { $ControllerDebug } else { $null }
    if (-not $ControllerExe) {
        Write-Host "[ERROR] Controller build failed. Please execute manually:" -ForegroundColor Red
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\build-companion.ps1" -ForegroundColor Yellow
        exit 1
    }
}

# 1c. Browser Native Messaging Host registration (Chrome and Edge)
$ChromeRegPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.sahaay.nativehost"
$EdgeRegPath = "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.sahaay.nativehost"
$ChromeRegistered = Test-Path $ChromeRegPath
$EdgeRegistered = Test-Path $EdgeRegPath

if (-not $ChromeRegistered -and -not $EdgeRegistered) {
    Write-Host "[INSTALL] Browser native messaging host not registered. Installing..." -ForegroundColor Yellow
    & "$PSScriptRoot\install-browser-native-host.ps1"
    $ChromeRegistered = Test-Path $ChromeRegPath
    $EdgeRegistered = Test-Path $EdgeRegPath
    if (-not $ChromeRegistered -and -not $EdgeRegistered) {
        Write-Host "[WARN] Native messaging host registration incomplete. To fix manually run:" -ForegroundColor Yellow
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\install-browser-native-host.ps1" -ForegroundColor Yellow
    }
}

# 1d. Desktop UI Build Artifacts
$DesktopRoot = Join-Path $RepoRoot "apps\desktop"
$DistHtml = Join-Path $DesktopRoot "dist\index.html"
$MainJs = Join-Path $DesktopRoot "out\main\index.js"

if ((-not (Test-Path $DistHtml) -or -not (Test-Path $MainJs)) -and ($Mode -eq "Desktop")) {
    Write-Host "[BUILD] Desktop UI artifacts missing or out-of-date. Compiling renderer and electron main..." -ForegroundColor Yellow
    Push-Location $DesktopRoot
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

# -----------------------------------------------------------------------------
# 2. DIAGNOSTICS-ONLY PROBE MODE
# -----------------------------------------------------------------------------
if ($DiagnosticsOnly) {
    Write-Host "`n=== Sahaay Runtime Diagnostics Probe ===" -ForegroundColor Cyan

    # Backend probe
    $BackendReachable = $false
    try {
        $healthReq = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 2 -ErrorAction Stop
        if ($healthReq.status -eq "healthy") { $BackendReachable = $true }
    } catch {}

    # Controller pipe probe
    $ControllerPipeUp = [System.IO.File]::Exists("\\.\pipe\SahaayControllerPipe")

    # Native host pipe probe
    $NativeHostPipeUp = [System.IO.File]::Exists("\\.\pipe\SahaayBrowserBridgePipe")

    Write-Host ("- Python Environment:        " + $(if (Test-Path $PythonExe) { "[READY] ($PythonExe)" } else { "[MISSING]" }))
    Write-Host ("- FastAPI Core Backend:      " + $(if ($BackendReachable) { "[ONLINE] (http://127.0.0.1:8000/api/v1/health)" } else { "[STOPPED] (Loopback port 8000 inactive)" }))
    Write-Host ("- Windows Controller Binary: " + $(if ($ControllerExe) { "[READY] ($ControllerExe)" } else { "[MISSING]" }))
    Write-Host ("- Windows Controller Pipe:   " + $(if ($ControllerPipeUp) { "[CONNECTED] (\\.\pipe\SahaayControllerPipe)" } else { "[STOPPED] (Daemon not running)" }))
    Write-Host ("- Chrome Native Host Reg:    " + $(if ($ChromeRegistered) { "[REGISTERED] (HKCU)" } else { "[NOT REGISTERED]" }))
    Write-Host ("- Edge Native Host Reg:      " + $(if ($EdgeRegistered) { "[REGISTERED] (HKCU)" } else { "[NOT REGISTERED]" }))
    Write-Host ("- Browser Extension Bridge:  " + $(if ($NativeHostPipeUp) { "[ATTACHED] (Active tab listening)" } else { "[HOST_WAITING] (Waiting for browser connection)" }))
    Write-Host ("- Desktop UI Bundle:         " + $(if (Test-Path $DistHtml) { "[READY] ($DistHtml)" } else { "[NOT BUILT] (Run: npm run build in apps/desktop)" }))
    Write-Host ("- Electron Main Bundle:      " + $(if (Test-Path $MainJs) { "[READY] ($MainJs)" } else { "[NOT BUILT]" }))
    Write-Host "`nDiagnostics probe complete." -ForegroundColor Green
    exit 0
}

# -----------------------------------------------------------------------------
# 3. RUNTIME EXECUTION MODES
# -----------------------------------------------------------------------------
if ($Mode -eq "Headless") {
    Write-Host "`n[START] Starting Sahaay in Headless Service Mode..." -ForegroundColor Green

    # Check if backend already running
    $BackendRunning = $false
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "healthy") { $BackendRunning = $true }
    } catch {}

    if (-not $BackendRunning) {
        Write-Host "Spawning FastAPI backend on 127.0.0.1:8000..." -ForegroundColor Cyan
        $env:PYTHONPATH = Join-Path $RepoRoot "core\src"
        $backendProcess = Start-Process -FilePath $PythonExe `
            -ArgumentList "-m", "uvicorn", "sahaay_core.main:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory (Join-Path $RepoRoot "core") `
            -WindowStyle Hidden `
            -PassThru
        Write-Host "Backend started with PID: $($backendProcess.Id)" -ForegroundColor Green
    } else {
        Write-Host "FastAPI backend already active on 127.0.0.1:8000 (reusing instance)." -ForegroundColor Yellow
    }

    # Check if controller already running
    $PipeRunning = [System.IO.File]::Exists("\\.\pipe\SahaayControllerPipe")
    if (-not $PipeRunning -and $ControllerExe) {
        Write-Host "Spawning interactive Windows Controller in user session..." -ForegroundColor Cyan
        $controllerProcess = Start-Process -FilePath $ControllerExe `
            -WorkingDirectory (Split-Path $ControllerExe) `
            -WindowStyle Hidden `
            -PassThru
        Write-Host "Controller started with PID: $($controllerProcess.Id)" -ForegroundColor Green
    } elseif ($PipeRunning) {
        Write-Host "Windows Controller pipe already listening (reusing instance)." -ForegroundColor Yellow
    }

    # Verify backend readiness
    $retries = 15
    $ready = $false
    while ($retries -gt 0 -and -not $ready) {
        Start-Sleep -Milliseconds 600
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 1 -ErrorAction Stop
            if ($h.status -eq "healthy") { $ready = $true }
        } catch {}
        $retries--
    }

    if ($ready) {
        Write-Host "`n[SUCCESS] Sahaay Headless Runtime is ONLINE and ready!" -ForegroundColor Green
        Write-Host "  API Endpoint:    http://127.0.0.1:8000/api/v1"
        Write-Host "  Health Probe:    http://127.0.0.1:8000/api/v1/health"
        Write-Host "  OpenAPI Docs:    http://127.0.0.1:8000/docs"
        Write-Host "Press Ctrl+C to exit launcher."
    } else {
        Write-Host "`n[WARN] Backend did not respond within expected startup window." -ForegroundColor Yellow
    }
}
elseif ($Mode -eq "Dev") {
    Write-Host "`n[START] Starting Sahaay in Vite Hot-Reload Development Mode..." -ForegroundColor Green
    Push-Location $DesktopRoot
    try {
        $env:VITE_DEV_SERVER_URL = "http://localhost:5173"
        # Start Vite dev server in background and launch electron
        $viteJob = Start-Job -ScriptBlock {
            param($path)
            Set-Location $path
            npm run dev
        } -ArgumentList $DesktopRoot

        Start-Sleep -Seconds 3
        npx electron .
    } finally {
        if ($viteJob) { Stop-Job $viteJob -ErrorAction SilentlyContinue; Remove-Job $viteJob -ErrorAction SilentlyContinue }
        Pop-Location
    }
}
else {
    # Default Desktop mode: Supervised Electron Application
    Write-Host "`n[START] Starting Supervised Sahaay Desktop Application..." -ForegroundColor Green
    # Clear ELECTRON_RUN_AS_NODE if inherited from IDE terminal so Electron runs as GUI app, not Node CLI
    Remove-Item Env:\ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
    Push-Location $DesktopRoot
    try {
        # Ensure electron main is freshly built
        npm run build:electron
        npx electron .
    } finally {
        Pop-Location
    }
}
