# Unregisters com.sahaay.nativehost from current user registry
$HostName = "com.sahaay.nativehost"

$RegistryTargets = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
)

Write-Host "Unregistering $HostName..." -ForegroundColor Cyan

foreach ($regPath in $RegistryTargets) {
    if (Test-Path $regPath) {
        Remove-Item -Path $regPath -Force -Recurse
        Write-Host "[OK] Removed: $regPath" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Not registered at: $regPath"
    }
}

Write-Host "Unregistration complete." -ForegroundColor Green
