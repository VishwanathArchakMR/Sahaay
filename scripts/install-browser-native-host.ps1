<#
.SYNOPSIS
Installs and registers Sahaay Native Messaging Host for Google Chrome and Microsoft Edge (Per-User, No Admin Required).

.DESCRIPTION
Deploys standalone Sahaay.NativeHost executable to %LOCALAPPDATA%\Sahaay\native-host,
generates the native messaging manifest, and registers it in HKCU for Chrome and Edge.

.PARAMETER ExtensionId
Target browser extension ID (default: "knldjmfmopnpolahpmmgbagdohdnhkik").
#>

param(
    [string]$ExtensionId = "knldjmfmopnpolahpmmgbagdohdnhkik",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$HostName = "com.sahaay.nativehost"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallDir = Join-Path $env:LOCALAPPDATA "Sahaay\native-host"
$SourceExe = Join-Path $RepoRoot "bin\dist\native-host-standalone\Sahaay.NativeHost.exe"
$TargetExe = Join-Path $InstallDir "Sahaay.NativeHost.exe"
$ManifestPath = Join-Path $InstallDir "com.sahaay.nativehost.json"

Write-Host "=== Installing Sahaay Native Messaging Host ===" -ForegroundColor Cyan
Write-Host "Target Directory: $InstallDir"
Write-Host "Extension ID:     $ExtensionId"

# 1. Build if not already built or requested
if (-not (Test-Path $SourceExe) -and -not $SkipBuild) {
    Write-Host "`nBuilding standalone NativeHost..." -ForegroundColor Yellow
    $localDotnet = Join-Path $env:LOCALAPPDATA "Microsoft\dotnet\dotnet.exe"
    $dotnetCmd = if (Test-Path $localDotnet) { $localDotnet } else { "dotnet" }
    
    $publishOut = Join-Path $RepoRoot "bin\dist\native-host-standalone"
    & $dotnetCmd publish "$RepoRoot\apps\windows-companion\Sahaay.NativeHost\Sahaay.NativeHost.csproj" `
        -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o $publishOut
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to publish NativeHost standalone binary."
        exit 1
    }
}

if (-not (Test-Path $SourceExe)) {
    Write-Error "Source binary not found at: $SourceExe"
    exit 1
}

# 2. Deploy binary to stable AppData directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

Copy-Item -Path (Join-Path (Split-Path $SourceExe) "*") -Destination $InstallDir -Recurse -Force
Write-Host "[OK] Binary deployed to: $TargetExe" -ForegroundColor Green

# 3. Generate Native Messaging Manifest
$manifest = @{
    name = $HostName
    description = "Sahaay Native Messaging Host for Chrome and Edge"
    path = $TargetExe
    type = "stdio"
    allowed_origins = @(
        "chrome-extension://$ExtensionId/"
    )
}

$manifestJson = $manifest | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ManifestPath, $manifestJson)
Write-Host "[OK] Manifest generated: $ManifestPath" -ForegroundColor Green

# 4. Register in HKCU (Google Chrome & Microsoft Edge)
$RegTargets = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
)

foreach ($regPath in $RegTargets) {
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force | Out-Null
    }
    Set-ItemProperty -Path $regPath -Name "(default)" -Value $ManifestPath
    Write-Host "[OK] Registered in: $regPath" -ForegroundColor Green
}

# 5. Run self-diagnostics
Write-Host "`nRunning NativeHost Diagnostics Verification:" -ForegroundColor Cyan
if (Test-Path $TargetExe) {
    & $TargetExe --test
}

Write-Host "`nInstallation & Registration Successfully Completed!" -ForegroundColor Green
