# Builds the Manifest V3 Browser Extension
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Push-Location "$RepoRoot\apps\browser-extension"
try {
    Write-Host "Building Sahaay Browser Extension..." -ForegroundColor Cyan
    npm run build
    Write-Host "[OK] Browser extension built in apps\browser-extension\dist" -ForegroundColor Green
} finally {
    Pop-Location
}
