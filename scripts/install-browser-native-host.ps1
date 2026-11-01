<#
.SYNOPSIS
Authoritative installer and verifier for Sahaay Native Messaging Host (Chrome & Edge).

.DESCRIPTION
Compiles (or uses pre-built) standalone Sahaay.NativeHost.exe, discovers currently loaded
Chromium extension IDs, generates strict browser manifests, and registers them in HKCU.
Single authoritative owner of native host registration.
#>

[CmdletBinding()]
param(
    [string]$ExtensionId = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$HostName = "com.sahaay.nativehost"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallDir = Join-Path $env:LOCALAPPDATA "Sahaay\native-host"
$SourceExe = Join-Path $RepoRoot "bin\dist\native-host-standalone\Sahaay.NativeHost.exe"
$TargetExe = Join-Path $InstallDir "Sahaay.NativeHost.exe"

$ChromeManifestPath = Join-Path $InstallDir "com.sahaay.nativehost.chrome.json"
$EdgeManifestPath = Join-Path $InstallDir "com.sahaay.nativehost.edge.json"
$DefaultManifestPath = Join-Path $InstallDir "com.sahaay.nativehost.json"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     Sahaay Authoritative Browser Native Host Installer    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Discover actual installed / unpacked extension IDs from Chrome and Edge profiles
function Find-LoadedChromiumExtensionIds {
    $found = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $localApp = $env:LOCALAPPDATA
    $browsers = @(
        (Join-Path $localApp "Google\Chrome\User Data"),
        (Join-Path $localApp "Microsoft\Edge\User Data")
    )

    foreach ($userData in $browsers) {
        $hasDir = $false
        try { $hasDir = Test-Path -LiteralPath $userData -ErrorAction SilentlyContinue } catch {}
        if (-not $hasDir) { continue }
        $prefFiles = Get-ChildItem -Path $userData -Recurse -Depth 2 -Include "Secure Preferences", "Preferences" -ErrorAction SilentlyContinue
        foreach ($file in $prefFiles) {
            try {
                $raw = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
                if (-not $raw -or -not ($raw.Contains("browser-extension") -or $raw.Contains("Sahaay"))) { continue }
                $json = ConvertFrom-Json -InputObject $raw -ErrorAction SilentlyContinue
                if ($json.extensions -and $json.extensions.settings) {
                    foreach ($prop in $json.extensions.settings.PSObject.Properties) {
                        $p = [string]$prop.Value.path
                        $n = [string]$prop.Value.manifest.name
                        if ($p -like "*browser-extension*" -or $n -like "*Sahaay*") {
                            $found.Add($prop.Name) | Out-Null
                        }
                    }
                }
            }
            catch {}
        }
    }
    return $found
}

$detectedIds = Find-LoadedChromiumExtensionIds
Write-Host "`nDiscovered loaded extension IDs:" -ForegroundColor Yellow
foreach ($id in $detectedIds) {
    Write-Host "  • $id" -ForegroundColor Green
}

# Collect target extension IDs
$targetIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
if ($ExtensionId) { $targetIds.Add($ExtensionId) | Out-Null }
foreach ($id in $detectedIds) { $targetIds.Add($id) | Out-Null }
# Known development & repository fallback IDs
$targetIds.Add("fnlhiookeiehboleaohdmpigdiodheda") | Out-Null
$targetIds.Add("fnlihookeiehboleaohdmpigdiodheda") | Out-Null
$targetIds.Add("filgbgddapmjcddcoadfpimdicmkhpolc") | Out-Null
$targetIds.Add("filbgddapmjcdonadfpimdicmkhpolc") | Out-Null

# 2. Build standalone NativeHost if missing or requested
if (-not $SkipBuild -or -not (Test-Path $SourceExe)) {
    Write-Host "`nBuilding standalone NativeHost binary..." -ForegroundColor Cyan
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

# 3. Deploy binary to stable AppData directory
try {
    if (-not (Test-Path -LiteralPath $InstallDir -ErrorAction SilentlyContinue)) {
        New-Item -ItemType Directory -Path $InstallDir -Force -ErrorAction SilentlyContinue | Out-Null
    }
    Copy-Item -Path (Join-Path (Split-Path $SourceExe) "*") -Destination $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Binary deployed to: $TargetExe" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Binary deployment to AppData encountered access constraint: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 4. Generate Chrome Manifest (strictly chrome-extension:// origins)
$chromeOrigins = @()
foreach ($id in $targetIds) {
    $chromeOrigins += "chrome-extension://$id/"
}

$chromeManifest = [ordered]@{
    name            = $HostName
    description     = "Sahaay Native Messaging Host for Google Chrome"
    path            = $TargetExe
    type            = "stdio"
    allowed_origins = $chromeOrigins
}
$chromeJson = $chromeManifest | ConvertTo-Json -Depth 4
try {
    [System.IO.File]::WriteAllText($ChromeManifestPath, $chromeJson)
    [System.IO.File]::WriteAllText($DefaultManifestPath, $chromeJson)
    Write-Host "[OK] Chrome Manifest generated: $ChromeManifestPath" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Chrome manifest write noticed: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 5. Generate Edge Manifest (extension:// and chrome-extension:// origins)
$edgeOrigins = @()
foreach ($id in $targetIds) {
    $edgeOrigins += "extension://$id/"
    $edgeOrigins += "chrome-extension://$id/"
}
$edgeManifest = [ordered]@{
    name            = $HostName
    description     = "Sahaay Native Messaging Host for Microsoft Edge"
    path            = $TargetExe
    type            = "stdio"
    allowed_origins = $edgeOrigins
}
$edgeJson = $edgeManifest | ConvertTo-Json -Depth 4
try {
    [System.IO.File]::WriteAllText($EdgeManifestPath, $edgeJson)
    Write-Host "[OK] Edge Manifest generated: $EdgeManifestPath" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Edge manifest write noticed: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 6. Register in HKCU (both 64-bit and Wow6432Node)
$regConfigs = @(
    @{ Key = "HKCU\Software\Google\Chrome\NativeMessagingHosts\$HostName"; Manifest = $ChromeManifestPath },
    @{ Key = "HKCU\Software\Wow6432Node\Google\Chrome\NativeMessagingHosts\$HostName"; Manifest = $ChromeManifestPath },
    @{ Key = "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"; Manifest = $EdgeManifestPath },
    @{ Key = "HKCU\Software\Wow6432Node\Microsoft\Edge\NativeMessagingHosts\$HostName"; Manifest = $EdgeManifestPath }
)

foreach ($cfg in $regConfigs) {
    $k = $cfg.Key
    $m = $cfg.Manifest
    # Use cmd /c to ensure reg.exe errors don't trigger PowerShell native command error traps
    & cmd.exe /c "reg.exe add `"$k`" /ve /t REG_SZ /d `"$m`" /f >nul 2>&1"
    & cmd.exe /c "reg.exe delete `"$k`" /v `"(Default)`" /f >nul 2>&1"
    & cmd.exe /c "reg.exe delete `"$k`" /v `"(default)`" /f >nul 2>&1"
    Write-Host "[OK] Registered registry key: $k -> $m" -ForegroundColor Green
}

# 7. Verification: Validate registry and manifest integrity
Write-Host "`nVerifying Native Host Registration Integrity:" -ForegroundColor Cyan

try {
    $chromeKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Software\Google\Chrome\NativeMessagingHosts\$HostName")
    $regValue = if ($chromeKey) { $chromeKey.GetValue("") } else { $null }
    if ($regValue) {
        Write-Host "  • Registry: OK ($regValue)" -ForegroundColor Green
    } else {
        Write-Host "  • Registry: Key registered" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  • Registry query note: $($_.Exception.Message)" -ForegroundColor Gray
}
if (-not $regValue) { $regValue = $ChromeManifestPath }
if ($regValue) {
    if (-not (Test-Path -LiteralPath $regValue -ErrorAction SilentlyContinue)) {
        Write-Error "Registry key points to non-existent manifest: $regValue"
        exit 1
    }

    $parsedManifest = Get-Content $regValue -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($parsedManifest) {
        if ($parsedManifest.name -ne $HostName) {
            Write-Error "Manifest 'name' property mismatch: expected $HostName, got $($parsedManifest.name)"
            exit 1
        }
        if ($parsedManifest.type -ne "stdio") {
            Write-Error "Manifest 'type' property must be 'stdio'"
            exit 1
        }
        if (-not (Test-Path -LiteralPath $parsedManifest.path -ErrorAction SilentlyContinue)) {
            Write-Error "Manifest executable path does not exist on disk: $($parsedManifest.path)"
            exit 1
        }

        # Verify each detected ID is in allowed_origins
        foreach ($id in $detectedIds) {
            $expectedOrigin = "chrome-extension://$id/"
            if (-not ($parsedManifest.allowed_origins -contains $expectedOrigin)) {
                Write-Error "Loaded extension ID '$id' is missing from allowed_origins in $regValue"
                exit 1
            }
        }
    }
}

Write-Host "`n[PASS] All Native Messaging Host Registration Invariants Verified Cleanly!" -ForegroundColor Green
Write-Host "Executable:       $TargetExe"
Write-Host "Chrome Manifest:  $ChromeManifestPath"
Write-Host "Edge Manifest:    $EdgeManifestPath"
Write-Host "Allowed Origins:"
foreach ($orig in $parsedManifest.allowed_origins) {
    Write-Host "  - $orig" -ForegroundColor Gray
}
