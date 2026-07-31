# JMeter Performance Test Runner
# Usage:
#   .\run_jmeter.ps1 local   # Run local baseline test
#   .\run_jmeter.ps1 prod    # Run production baseline test
#
# Design notes:
# - Use Start-Process + ArgumentList array to avoid PowerShell splitting
#   dotted values like 127.0.0.1 into separate args (happens with & invocation)
# - Clean previous results before each run (JMeter -e -o requires empty/non-existent dir)
# - Inject runtime variables via -J parameters

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("local", "prod")]
    [string]$Env
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$jmeter = "D:\code\Jmeter\apache-jmeter-5.6.3\bin\jmeter.bat"
$jmx = Join-Path $scriptDir "morningbrief_test_plan.jmx"
$props = Join-Path $scriptDir "jmeter.properties"
$tokenFile = Join-Path $scriptDir "test_token.txt"

if (-not (Test-Path $tokenFile)) {
    Write-Error "Token file not found: $tokenFile. Run setup.py first."
    exit 1
}
$token = (Get-Content $tokenFile -Raw).Trim()

# Select target configuration by Env
switch ($Env) {
    "local" {
        $outDir = Join-Path $scriptDir "results_local"
        $targetHost = "127.0.0.1"
        $targetPort = "8000"
        $targetProtocol = "http"
        $pathPrefix = ""
    }
    "prod" {
        $outDir = Join-Path $scriptDir "results_prod"
        $targetHost = "desktop-g10o4nl.tailbca47.ts.net"
        $targetPort = "443"
        $targetProtocol = "https"
        $pathPrefix = "/news"
    }
}

# Clean previous results (JMeter -e -o requires empty or non-existent dir)
$htmlDir = Join-Path $outDir "html"
$jtlFile = Join-Path $outDir "result.jtl"
if (Test-Path $htmlDir) { Remove-Item $htmlDir -Recurse -Force }
if (Test-Path $jtlFile) { Remove-Item $jtlFile -Force }

if (-not (Test-Path $outDir)) {
    New-Item -Path $outDir -ItemType Directory -Force | Out-Null
}

$targetUrl = "${targetProtocol}://${targetHost}:${targetPort}${pathPrefix}"
Write-Host "=========================================="
Write-Host "  JMeter Baseline Test - $Env"
Write-Host "=========================================="
Write-Host "  Target: $targetUrl"
Write-Host "  Load: 10 threads, Ramp-up 5s, Duration 60s"
Write-Host "  Throughput cap: 100/min (under 120/min rate limit)"
Write-Host "  Output: $outDir"
Write-Host "=========================================="
Write-Host ""

# Start-Process with ArgumentList array avoids PowerShell arg parsing issues
$argList = @(
    "-n",
    "-t", $jmx,
    "-l", $jtlFile,
    "-e", "-o", $htmlDir,
    "-p", $props,
    "-Jhost=$targetHost",
    "-Jport=$targetPort",
    "-Jprotocol=$targetProtocol",
    "-Jpath_prefix=$pathPrefix",
    "-Jepisode_id=57",
    "-Jauth_token=$token",
    "-Jthreads=10",
    "-Jramp_up=5",
    "-Jduration=60",
    "-Jthroughput=100.0"
)

$proc = Start-Process -FilePath $jmeter -ArgumentList $argList -NoNewWindow -Wait -PassThru

Write-Host ""
Write-Host "=========================================="
if ($proc.ExitCode -eq 0) {
    Write-Host "  Test completed successfully!"
    Write-Host "  JTL: $jtlFile"
    Write-Host "  HTML: $htmlDir\index.html"
} else {
    Write-Host "  Test FAILED! ExitCode: $($proc.ExitCode)"
}
Write-Host "=========================================="
