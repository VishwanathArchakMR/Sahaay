# Registers com.sahaay.nativehost for current user in Chrome and Edge
param(
    [string]$ManifestPath = "$PSScriptRoot\com.sahaay.nativehost.json"
)

$FullManifestPath = (Resolve-Path $ManifestPath).Path
$HostName = "com.sahaay.nativehost"

$RegistryPaths = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
)

foreach ($regPath in $RegistryPaths) {
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force | Out-Null
    }
    Set-ItemProperty -Path $regPath -Name "(default)" -Value $FullManifestPath
    Write-Host "Registered $HostName at $regPath -> $FullManifestPath"
}
