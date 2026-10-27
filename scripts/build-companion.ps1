# Builds the Windows Native Companion (.NET 8 solution)
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path

# Detect dotnet from PATH or user installation
$localDotnet = "$env:LOCALAPPDATA\Microsoft\dotnet"
if (Test-Path "$localDotnet\dotnet.exe") {
    $env:PATH = "$localDotnet;$env:PATH"
    $env:DOTNET_ROOT = $localDotnet
}

try {
    $dotnetVer = dotnet --version 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($dotnetVer)) {
        Write-Host "[BLOCKED] No .NET SDK found. Please install the .NET 10.0 SDK to build the native companion." -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "[BLOCKED] .NET CLI not found in PATH or LOCALAPPDATA." -ForegroundColor Yellow
    exit 1
}

Push-Location "$RepoRoot\apps\windows-companion"
try {
    Write-Host "Building Sahaay Native Companion Solution..." -ForegroundColor Cyan
    dotnet build Sahaay.sln -c Release
} finally {
    Pop-Location
}
