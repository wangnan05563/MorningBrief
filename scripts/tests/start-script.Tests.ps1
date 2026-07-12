$ErrorActionPreference = "Stop"

$startScript = Join-Path $PSScriptRoot "..\start.ps1"
$content = Get-Content $startScript -Raw

function Assert-Matches {
    param(
        [string]$Pattern,
        [string]$Message
    )

    if ($content -notmatch $Pattern) {
        throw $Message
    }
}

Assert-Matches '(?s)\$portLine\s*=.*?APP_PORT.*?\$portProcs\s*=' `
    "start.ps1 must read APP_PORT before checking existing listeners"

Assert-Matches 'Get-NetTCPConnection -LocalPort \$port -State Listen' `
    "listener checks must use the configured port instead of hard-coded 8000"

Assert-Matches '(?s)\$remainingListeners\s*=\s*Get-NetTCPConnection -LocalPort \$port.*?if \(\$remainingListeners\).*?exit 1' `
    "start.ps1 must abort when the port remains occupied after cleanup"

Assert-Matches '\$commandLine\s*=\s*"\$cmdStr 2>&1 & pause"' `
    "start.ps1 must stream service logs to the visible cmd window"

Assert-Matches '-WindowStyle Normal' `
    "start.ps1 must open a visible service log window"

Write-Host "[PASS] start.ps1 port conflict guards" -ForegroundColor Green
