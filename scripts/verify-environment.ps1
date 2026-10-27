# Inspects and verifies the local Windows development environment for Sahaay
Write-Host "=== Sahaay Environment Diagnostics ===" -ForegroundColor Cyan

# 1. Operating System & Hardware
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor
$gpu = Get-CimInstance Win32_VideoController
Write-Host "OS: $($os.Caption) ($($os.OSArchitecture))"
Write-Host "CPU: $($cpu.Name) ($($cpu.NumberOfCores) Cores / $($cpu.NumberOfLogicalProcessors) Threads)"
Write-Host "RAM: $([math]::Round($os.TotalVisibleMemorySize / 1MB, 2)) GB Total"
foreach ($g in $gpu) {
    Write-Host "GPU: $($g.Name)"
}

Write-Host "`n=== Installed Runtimes & Tooling ===" -ForegroundColor Cyan

# 2. Git
try {
    $gitVer = git --version
    Write-Host "[OK] Git: $gitVer" -ForegroundColor Green
} catch {
    Write-Host "[MISSING] Git is not installed." -ForegroundColor Red
}

# 3. Python
try {
    $pyVer = python --version
    Write-Host "[OK] Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[MISSING] Python is not installed." -ForegroundColor Red
}

# 4. uv package manager
$uvPath = "$env:APPDATA\Python\Python312\Scripts\uv.exe"
if (Test-Path $uvPath) {
    $uvVer = & $uvPath --version
    Write-Host "[OK] uv: $uvVer" -ForegroundColor Green
} else {
    Write-Host "[WARNING] uv is not in AppData path. Running pip fallback." -ForegroundColor Yellow
}

# 5. Node.js & npm
try {
    $nodeVer = node --version
    $npmVer = npm --version
    Write-Host "[OK] Node: $nodeVer (npm: $npmVer)" -ForegroundColor Green
} catch {
    Write-Host "[MISSING] Node.js/npm is not installed." -ForegroundColor Red
}

# 6. .NET SDK
try {
    $dotnetVer = dotnet --version 2>$null
    if ($LASTEXITCODE -eq 0 -and $dotnetVer) {
        Write-Host "[OK] .NET SDK: $dotnetVer" -ForegroundColor Green
    } else {
        Write-Host "[INFO] .NET Runtime installed, but no .NET SDK found (Required for C# companion build)." -ForegroundColor Yellow
    }
} catch {
    Write-Host "[INFO] .NET is not in PATH." -ForegroundColor Yellow
}

# 7. Browsers
$chromeInstalled = Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"
$edgeInstalled = Test-Path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
Write-Host "Google Chrome: $(if ($chromeInstalled) { '[OK] Installed' } else { '[NOT FOUND]' })"
Write-Host "Microsoft Edge: $(if ($edgeInstalled) { '[OK] Installed' } else { '[NOT FOUND]' })"
