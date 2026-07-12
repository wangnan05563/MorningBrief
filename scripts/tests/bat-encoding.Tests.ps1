$ErrorActionPreference = "Stop"

$scriptsDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$gbk = [System.Text.Encoding]::GetEncoding(
    936,
    [System.Text.EncoderExceptionFallback]::new(),
    [System.Text.DecoderExceptionFallback]::new()
)
$batchPath = Get-ChildItem $scriptsDir -Filter "*.bat" | Where-Object {
    $candidateBytes = [System.IO.File]::ReadAllBytes($_.FullName)
    $gbk.GetString($candidateBytes) -match 'start\.ps1'
} | Select-Object -First 1 -ExpandProperty FullName
if (-not $batchPath) {
    throw "Could not locate the startup batch file"
}
$bytes = [System.IO.File]::ReadAllBytes($batchPath)

$hasUtf8Bom = $bytes.Length -ge 3 -and
    $bytes[0] -eq 0xEF -and
    $bytes[1] -eq 0xBB -and
    $bytes[2] -eq 0xBF
if ($hasUtf8Bom) {
    throw "Batch file must not contain a UTF-8 BOM"
}

$isolatedLf = 0
for ($index = 0; $index -lt $bytes.Length; $index++) {
    if ($bytes[$index] -eq 0x0A -and ($index -eq 0 -or $bytes[$index - 1] -ne 0x0D)) {
        $isolatedLf++
    }
}
if ($isolatedLf -ne 0) {
    throw "Batch file contains $isolatedLf isolated LF line endings; CRLF is required"
}

$text = $gbk.GetString($bytes)
if (-not $text.StartsWith("@echo off`r`nchcp 936")) {
    throw "Batch file must be GBK-compatible and start with the expected code page"
}
if (@($bytes | Where-Object { $_ -gt 0x7F }).Count -ne 0) {
    throw "Startup batch entry must remain ASCII-only for cmd.exe compatibility"
}
if ($text -notmatch '(?s)pause >nul\r\nexit /b 0') {
    throw "Startup batch must wait for a key press before closing after success"
}

$smokeDir = Join-Path $env:TEMP ("20-news-bat-smoke-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $smokeDir | Out-Null
    $smokeBatch = Join-Path $smokeDir "start-service.bat"
    Copy-Item $batchPath $smokeBatch
    [System.IO.File]::WriteAllText(
        (Join-Path $smokeDir "start.ps1"),
        "exit 0`r`n",
        [System.Text.Encoding]::ASCII
    )

    $smokeCommand = "(echo.) | call `"$smokeBatch`""
    $output = & cmd.exe /d /c $smokeCommand 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "cmd.exe smoke test failed with exit code $LASTEXITCODE`n$output"
    }
    if ($output -match "not recognized|(?m)^'.*'") {
        throw "cmd.exe split a batch line into an invalid command`n$output"
    }
} finally {
    if (Test-Path $smokeDir) {
        Remove-Item -LiteralPath $smokeDir -Recurse -Force
    }
}

Write-Host "[PASS] startup batch encoding and line endings" -ForegroundColor Green
