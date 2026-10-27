<#
.SYNOPSIS
Registers com.sahaay.nativehost for the current user in Google Chrome and Microsoft Edge.

.DESCRIPTION
Configures the Native Messaging Host manifest with the target extension ID and registers
it in HKCU without requiring administrative privileges.

.PARAMETER ExtensionId
The Extension ID from chrome://extensions or edge://extensions (e.g. "knldjmfmopnpolahpmmgbagdohdnhkik").
#>

param(
    [string]$ExtensionId = "knldjmfmopnpolahpmmgbagdohdnhkik",
    [string]$Configuration = "Debug"
)

$HostName = "com.sahaay.nativehost"
$ScriptDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path "$ScriptDir\..\..\..").Path
$BinDir = "$ScriptDir\bin\$Configuration\net10.0"
$ExePath = "$BinDir\Sahaay.NativeHost.exe"
$ManifestPath = "$ScriptDir\com.sahaay.nativehost.json"

Write-Host "=== Registering Sahaay Native Messaging Host ($HostName) ===" -ForegroundColor Cyan
Write-Host "Target Extension ID: $ExtensionId"

if (-not (Test-Path $ExePath)) {
    Write-Host "[WARNING] NativeHost executable not found at: $ExePath" -ForegroundColor Yellow
    Write-Host "Building project first..." -ForegroundColor Yellow
    dotnet build "$ScriptDir\Sahaay.NativeHost.csproj" -c $Configuration
    if (-not (Test-Path $ExePath)) {
        Write-Error "Failed to locate built executable: $ExePath"
        exit 1
    }
}

$ResolvedExePath = (Resolve-Path $ExePath).Path
$ResolvedManifestPath = (Resolve-Path $ManifestPath).Path

# Generate or update manifest with actual extension ID
$manifest = @{
    name = $HostName
    description = "Sahaay Native Messaging Host for Chrome and Edge"
    path = $ResolvedExePath
    type = "stdio"
    allowed_origins = @(
        "chrome-extension://$ExtensionId/"
    )
}

$manifestJson = $manifest | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ResolvedManifestPath, $manifestJson)
Write-Host "[OK] Updated manifest at: $ResolvedManifestPath" -ForegroundColor Green

# Register in HKCU for Google Chrome & Microsoft Edge
$RegistryTargets = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
)

foreach ($regPath in $RegistryTargets) {
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force | Out-Null
    }
    Set-ItemProperty -Path $regPath -Name "(default)" -Value $ResolvedManifestPath
    Write-Host "[OK] Registered in registry: $regPath -> $ResolvedManifestPath" -ForegroundColor Green
}

Write-Host "`nVerification check:" -ForegroundColor Cyan
foreach ($regPath in $RegistryTargets) {
    $val = (Get-ItemProperty -Path $regPath -Name "(default)" -ErrorAction SilentlyContinue)."(default)"
    Write-Host "  $regPath: $val"
}

Write-Host "`nNative Host registration complete!" -ForegroundColor Green
