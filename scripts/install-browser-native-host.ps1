<#
.SYNOPSIS
Installs and registers Sahaay Native Messaging Host for Google Chrome and Microsoft Edge (Per-User, No Admin Required).

.DESCRIPTION
Deploys standalone Sahaay.NativeHost executable to %LOCALAPPDATA%\Sahaay\native-host,
generates the native messaging manifest with dual Chrome/Edge scheme support and
unpacked extension auto-detection, and registers it in HKCU for both Chrome and Edge.

.PARAMETER ExtensionId
Target browser extension ID (default: "knldjmfmopnpolahpmmgbagdohdnhkik").
#>

param(
    [string]$ExtensionId = "filgbgddapmjcddcoadfpimdicmkhpolc",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$HostName = "com.sahaay.nativehost"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallDir = Join-Path $env:LOCALAPPDATA "Sahaay\native-host"
$SourceExe = Join-Path $RepoRoot "bin\dist\native-host-standalone\Sahaay.NativeHost.exe"
$TargetExe = Join-Path $InstallDir "Sahaay.NativeHost.exe"
$ManifestPath = Join-Path $InstallDir "com.sahaay.nativehost.json"

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

$ExtensionDir = Join-Path $RepoRoot "apps\browser-extension"
$UnpackedId = if (Test-Path $ExtensionDir) {
    Get-ChromiumExtensionId (Resolve-Path $ExtensionDir).Path
} else {
    $ExtensionId
}

Write-Host "=== Installing Sahaay Native Messaging Host ===" -ForegroundColor Cyan
Write-Host "Target Directory:     $InstallDir"
Write-Host "Configured Ext ID:    $ExtensionId"
Write-Host "Unpacked Repo Ext ID: $UnpackedId"

# 1. Build unless explicitly skipped
if (-not $SkipBuild) {
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

# 3. Generate Native Messaging Manifest with all verified extension origins
$allOrigins = [System.Collections.Generic.HashSet[string]]::new()
$allOrigins.Add("chrome-extension://$ExtensionId/") | Out-Null
$allOrigins.Add("extension://$ExtensionId/") | Out-Null
$allOrigins.Add("chrome-extension://filgbgddapmjcddcoadfpimdicmkhpolc/") | Out-Null
$allOrigins.Add("extension://filgbgddapmjcddcoadfpimdicmkhpolc/") | Out-Null
$allOrigins.Add("chrome-extension://knldjmfmopnpolahpmmgbagdohdnhkik/") | Out-Null
$allOrigins.Add("extension://knldjmfmopnpolahpmmgbagdohdnhkik/") | Out-Null
$allOrigins.Add("chrome-extension://nokchmadkhaghgooijgkgpheoieaibdp/") | Out-Null
$allOrigins.Add("extension://nokchmadkhaghgooijgkgpheoieaibdp/") | Out-Null
if ($UnpackedId) {
    $allOrigins.Add("chrome-extension://$UnpackedId/") | Out-Null
    $allOrigins.Add("extension://$UnpackedId/") | Out-Null
}

$manifest = [ordered]@{
    name = $HostName
    description = "Sahaay Native Messaging Host for Chrome and Edge"
    path = $TargetExe
    type = "stdio"
    allowed_origins = @($allOrigins)
}

$manifestJson = $manifest | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ManifestPath, $manifestJson)
Write-Host "[OK] Manifest generated: $ManifestPath" -ForegroundColor Green

# Also mirror manifest to repository standalone dist directory
$RepoManifest = Join-Path $RepoRoot "bin\dist\native-host-standalone\$HostName.json"
$repoManifestData = [ordered]@{
    name = $HostName
    description = "Sahaay Native Messaging Host for Chrome and Edge"
    path = $SourceExe
    type = "stdio"
    allowed_origins = @($allOrigins)
}
[System.IO.File]::WriteAllText($RepoManifest, ($repoManifestData | ConvertTo-Json -Depth 4))

Write-Host "Allowed Origins:" -ForegroundColor Gray
foreach ($origin in $allOrigins) {
    Write-Host "  - $origin" -ForegroundColor Gray
}

# 4. Register in HKCU (Google Chrome & Microsoft Edge)
$RegTargets = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
)

# Use reg.exe directly with /ve to guarantee default (unnamed) registry value is set
reg.exe add "HKCU\Software\Google\Chrome\NativeMessagingHosts\$HostName" /ve /t REG_SZ /d "$ManifestPath" /f
reg.exe add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\$HostName" /ve /t REG_SZ /d "$ManifestPath" /f

foreach ($regPath in $RegTargets) {
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force | Out-Null
    }
    Set-ItemProperty -Path $regPath -Name "(default)" -Value $ManifestPath -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $regPath -Name "(Default)" -Value $ManifestPath -ErrorAction SilentlyContinue
    Write-Host "[OK] Registered in: $regPath" -ForegroundColor Green
}

# 5. Native binary self-registration & diagnostics
if (Test-Path $TargetExe) {
    & $TargetExe --register "$ExtensionId"
} elseif (Test-Path $SourceExe) {
    & $SourceExe --register "$ExtensionId"
}

Write-Host "`nInstallation & Registration Successfully Completed!" -ForegroundColor Green
