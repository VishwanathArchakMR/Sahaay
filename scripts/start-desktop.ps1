# Starts the Electron Desktop Application in development mode
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Push-Location "$RepoRoot\apps\desktop"
try {
    Write-Host "Launching Sahaay Desktop App..." -ForegroundColor Cyan
    npm run dev
} finally {
    Pop-Location
}
