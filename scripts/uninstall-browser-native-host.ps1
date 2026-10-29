<#
.SYNOPSIS
Uninstalls and unregisters Sahaay Native Messaging Host from Google Chrome and Microsoft Edge.

.DESCRIPTION
Stops running native host processes, removes the native messaging registry keys for Chrome
and Edge from HKCU, and cleans up manifest files without modifying any other system settings.
#>

$ErrorActionPreference = "SilentlyContinue"
$HostName = "com.sahaay.nativehost"
$InstallDir = Join-Path $env:LOCALAPPDATA "Sahaay\native-host"

Write-Host "=== Uninstalling Sahaay Native Messaging Host ===" -ForegroundColor Cyan

# 0. Terminate running host process if active
Get-Process -Name "Sahaay.NativeHost" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Stopping running process PID $($_.Id)..." -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force
}

# 1. Remove registry keys
$RegTargets = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
)

foreach ($regPath in $RegTargets) {
    if (Test-Path $regPath) {
        Remove-Item -Path $regPath -Recurse -Force
        Write-Host "[OK] Removed registry entry: $regPath" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Registry entry not found: $regPath" -ForegroundColor Gray
    }
}

# 2. Clean up manifest
$ManifestPath = Join-Path $InstallDir "com.sahaay.nativehost.json"
if (Test-Path $ManifestPath) {
    Remove-Item -Path $ManifestPath -Force
    Write-Host "[OK] Removed manifest file: $ManifestPath" -ForegroundColor Green
}

Write-Host "`nUninstallation cleanly completed!" -ForegroundColor Green
