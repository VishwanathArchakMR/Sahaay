<#
.SYNOPSIS
Registers com.sahaay.nativehost for the current user in Google Chrome and Microsoft Edge.

.DESCRIPTION
Configures the Native Messaging Host manifest with dual Chrome and Edge allowed origins
and registers it in HKCU without requiring administrative privileges.

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

# Calculate unpacked extension ID derived from repository path
function Get-ChromiumExtensionId([string]$folderPath) {
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($folderPath)
    $hash = $sha256.ComputeHash($bytes)
    $chars = [char[]]::new(32)
    for ($i = 0; $i -lt 16; $i++) {
        $b = $hash[$i]
        $chars[$i * 2] = [char]([byte][char]'a' + ($b -shr 4))
        $chars[$i * 2 + 1] = [char]([byte][char]'a' + ($b -band 0x0F))
    }
    return [string]::new($chars)
}

$ExtensionDir = Join-Path $ProjectRoot "apps\browser-extension"
$UnpackedId = if (Test-Path $ExtensionDir) {
    Get-ChromiumExtensionId (Resolve-Path $ExtensionDir).Path
} else {
    $ExtensionId
}

$allowedOrigins = [System.Collections.Generic.List[string]]::new()
$allowedOrigins.Add("chrome-extension://$ExtensionId/")
$allowedOrigins.Add("extension://$ExtensionId/")

if ($UnpackedId -ne $ExtensionId) {
    $allowedOrigins.Add("chrome-extension://$UnpackedId/")
    $allowedOrigins.Add("extension://$UnpackedId/")
}

# Generate or update manifest with actual extension ID
$manifest = [ordered]@{
    name = $HostName
    description = "Sahaay Native Messaging Host for Chrome and Edge"
    path = $ResolvedExePath
    type = "stdio"
    allowed_origins = $allowedOrigins.ToArray()
}

$manifestJson = $manifest | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ResolvedManifestPath, $manifestJson)
Write-Host "[OK] Manifest generated at: $ResolvedManifestPath" -ForegroundColor Green

# Register for Chrome
$ChromeRegPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName"
if (-not (Test-Path $ChromeRegPath)) {
    New-Item -Path $ChromeRegPath -Force | Out-Null
}
Set-ItemProperty -Path $ChromeRegPath -Name "(default)" -Value $ResolvedManifestPath
Write-Host "[OK] Registered for Google Chrome ($ChromeRegPath)" -ForegroundColor Green

# Register for Edge
$EdgeRegPath = "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
if (-not (Test-Path $EdgeRegPath)) {
    New-Item -Path $EdgeRegPath -Force | Out-Null
}
Set-ItemProperty -Path $EdgeRegPath -Name "(default)" -Value $ResolvedManifestPath
Write-Host "[OK] Registered for Microsoft Edge ($EdgeRegPath)" -ForegroundColor Green

Write-Host "`nRegistration complete! Restart Chrome/Edge to load host." -ForegroundColor Green
