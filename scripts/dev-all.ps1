# Alias script forwarding to the unified launcher in Dev mode
[CmdletBinding()]
param(
    [switch]$DiagnosticsOnly
)

$PSScriptRootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($DiagnosticsOnly) {
    & "$PSScriptRootPath\start-sahaay.ps1" -DiagnosticsOnly
} else {
    & "$PSScriptRootPath\start-sahaay.ps1" -Mode Dev
}

