# Builds the Windows Native Companion (.NET 8 solution)
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path

# Detect dotnet from PATH or user installation
$localDotnet = "$env:LOCALAPPDATA\Microsoft\dotnet"
if (Test-Path "$localDotnet\dotnet.exe") {
    $env:PATH = "$localDotnet;$env:PATH"
    $env:DOTNET_ROOT = $localDotnet
}

Push-Location "$RepoRoot\apps\windows-companion"
try {
    Write-Host "Building Sahaay Native Companion Solution..." -ForegroundColor Cyan
    & "$localDotnet\dotnet.exe" build Sahaay.sln -c Release -p:UseSharedCompilation=false --no-restore
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Building project files directly..." -ForegroundColor Yellow
        & "$localDotnet\dotnet.exe" build Sahaay.Contracts/Sahaay.Contracts.csproj -c Release --no-restore
        & "$localDotnet\dotnet.exe" build Sahaay.Controller/Sahaay.Controller.csproj -c Release --no-restore
        & "$localDotnet\dotnet.exe" build Sahaay.NativeHost/Sahaay.NativeHost.csproj -c Release --no-restore
    }
} finally {
    Pop-Location
}
