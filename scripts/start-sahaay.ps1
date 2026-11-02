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

# Configure user-local .NET 10 environment if installed in LOCALAPPDATA
$localDotnet = "$env:LOCALAPPDATA\Microsoft\dotnet"
if (Test-Path "$localDotnet\dotnet.exe") {
    $env:DOTNET_ROOT = $localDotnet
    $env:PATH = "$localDotnet;$env:PATH"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         Launching Sahaay Windows AI Agent Runtime         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Active Named Pipe Ping Handshake
function Test-NamedPipePing([string]$pipeName, [int]$timeoutMs = 400) {
    try {
        $client = [System.IO.Pipes.NamedPipeClientStream]::new(".", $pipeName, [System.IO.Pipes.PipeDirection]::InOut)
        $client.Connect($timeoutMs)
        $writer = [System.IO.StreamWriter]::new($client)
        $writer.AutoFlush = $true
        $reader = [System.IO.StreamReader]::new($client)
        $writer.WriteLine('{"id":"probe","command":"ping","sessionId":"diagnostics-probe"}')
        $resp = $reader.ReadLine()
        $client.Dispose()
        return ($resp -and $resp.Contains('"success":true'))
    } catch {
        return $false
    }
}

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
$ControllerStandalone = Join-Path $RepoRoot "bin\dist\controller-standalone\Sahaay.Controller.exe"
$ControllerRelease = Join-Path $RepoRoot "apps\windows-companion\Sahaay.Controller\bin\Release\net10.0-windows\Sahaay.Controller.exe"
$ControllerDebug = Join-Path $RepoRoot "apps\windows-companion\Sahaay.Controller\bin\Debug\net10.0-windows\Sahaay.Controller.exe"
$ControllerExe = if (Test-Path $ControllerStandalone) { $ControllerStandalone } elseif (Test-Path $ControllerRelease) { $ControllerRelease } elseif (Test-Path $ControllerDebug) { $ControllerDebug } else { $null }

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
$ChromeRegistered = $false
$EdgeRegistered = $false
try {
    $ChromeRegistered = Test-Path $ChromeRegPath -ErrorAction SilentlyContinue
    $EdgeRegistered = Test-Path $EdgeRegPath -ErrorAction SilentlyContinue
} catch {
    $ChromeRegistered = $true
    $EdgeRegistered = $true
}

$NeedsHostInstall = -not $ChromeRegistered -or -not $EdgeRegistered
if (-not $NeedsHostInstall) {
    # Verify that the registered manifest file actually exists
    try {
        $chromeItem = Get-Item -Path $ChromeRegPath -ErrorAction SilentlyContinue
        $regVal = if ($chromeItem) { $chromeItem.GetValue("") } else { $null }
        if (-not $regVal) {
            $regVal = (Get-ItemProperty -Path $ChromeRegPath -ErrorAction SilentlyContinue)."(default)"
        }
        if (-not $regVal) {
            $regVal = (Get-ItemProperty -Path $ChromeRegPath -ErrorAction SilentlyContinue)."(Default)"
        }
        if ($regVal -and (-not (Test-Path $regVal -ErrorAction SilentlyContinue))) {
            $NeedsHostInstall = $true
        }
    } catch {
        # Permission constraint reading registry value; key exists so skip reinstall
        $NeedsHostInstall = $false
    }
}

if ($NeedsHostInstall) {
    Write-Host "[INSTALL] Browser native messaging host not fully registered. Installing and configuring origins..." -ForegroundColor Yellow
    & "$PSScriptRoot\install-browser-native-host.ps1" -SkipBuild
    $ChromeRegistered = Test-Path $ChromeRegPath
    $EdgeRegistered = Test-Path $EdgeRegPath
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

    # Controller pipe probe (Active Handshake)
    $ControllerPipeUp = Test-NamedPipePing -pipeName "SahaayControllerPipe"
    $NativeHostPipeUp = Test-NamedPipePing -pipeName "SahaayBrowserBridgePipe"

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

function Ensure-Port8000Available {
    try {
        $existingConns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($existingConns) {
            $healthOk = $false
            try {
                $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 1 -ErrorAction Stop
                if ($h.status -eq "healthy") { $healthOk = $true }
            } catch {}

            if (-not $healthOk) {
                foreach ($conn in $existingConns) {
                    $procId = $conn.OwningProcess
                    if ($procId -gt 0) {
                        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                        if ($proc -and ($proc.ProcessName -like "*python*" -or $proc.ProcessName -like "*uvicorn*")) {
                            Write-Host "[CLEANUP] Stopping unresponsive Sahaay backend process (PID: $procId)..." -ForegroundColor Yellow
                            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                        } else {
                            Write-Host "[BLOCKED] Port 8000 is occupied by an external process: '$($proc.ProcessName)' (PID: $procId)." -ForegroundColor Red
                            Write-Host "Sahaay will not terminate unrelated processes. Please free port 8000 and restart." -ForegroundColor Yellow
                            exit 1
                        }
                    }
                }
                Start-Sleep -Milliseconds 800
            }
        }
    } catch {}
}

if ($Mode -eq "Headless") {
    Write-Host "`n[START] Starting Sahaay in Headless Service Mode..." -ForegroundColor Green

    Ensure-Port8000Available

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
    $PipeRunning = Test-NamedPipePing -pipeName "SahaayControllerPipe"
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
        try {
            while ($true) {
                Start-Sleep -Seconds 1
                if ($backendProcess -and $backendProcess.HasExited) {
                    Write-Host "[WARN] Backend process terminated unexpectedly." -ForegroundColor Yellow
                    break
                }
            }
        } finally {
            if ($backendProcess -and -not $backendProcess.HasExited) {
                Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
            }
            if ($controllerProcess -and -not $controllerProcess.HasExited) {
                Stop-Process -Id $controllerProcess.Id -Force -ErrorAction SilentlyContinue
            }
        }
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
    # Default Desktop mode: Electron Desktop Application with RuntimeSupervisor as single owner
    Write-Host "`n[START] Launching Sahaay Desktop Application..." -ForegroundColor Green
    Write-Host "Runtime lifecycle managed by Electron RuntimeSupervisor." -ForegroundColor Gray

    # Ensure persistent log directory exists under AppData
    $LogDir = Join-Path $env:LOCALAPPDATA "Sahaay\logs"
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

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
