<#
.SYNOPSIS
    通用脚本编码验证器 - create-bat 技能组件
.DESCRIPTION
    验证 .bat / .ps1 文件的编码、BOM、行尾是否符合配置要求。
    所有参数从 config.json 读取，无硬编码。
.PARAMETER ConfigFile
    配置文件路径
.PARAMETER Files
    待验证的文件列表
.EXAMPLE
    .\verify-encoding.ps1 -ConfigFile config.json -Files scripts\启动服务.bat,scripts\start.ps1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$ConfigFile,
    [Parameter(Mandatory=$true)]
    [string[]]$Files
)

$ErrorActionPreference = "Stop"

# ---- 加载配置 ----
$config = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
$enc = $config.encoding

# ---- 验证函数 ----
function Test-FileEncoding {
    param([string]$FilePath, [object]$EncodingConfig)

    $result = [PSCustomObject]@{
        file       = $FilePath
        exists     = Test-Path $FilePath
        size       = 0
        has_bom    = $false
        bom_bytes  = @()
        has_lf_only = $false
        bat_issues = @()
        ps1_issues = @()
    }

    if (-not $result.exists) {
        $result.bat_issues += "文件不存在"
        return $result
    }

    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    $result.size = $bytes.Length

    # BOM 检测
    if ($bytes.Length -ge 3) {
        $result.bom_bytes = $bytes[0..2]
        $result.has_bom = ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    }
    if ($bytes.Length -ge 2) {
        $result.has_bom = $result.has_bom -or ($bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF)
    }

    # CRLF 检测
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($bytes[$i] -eq 0x0A -and ($i -eq 0 -or $bytes[$i-1] -ne 0x0D)) {
            $result.has_lf_only = $true
            break
        }
    }

    # 根据文件扩展名应用规则
    $ext = [System.IO.Path]::GetExtension($FilePath).ToLower()

    if ($ext -eq '.bat') {
        # .bat 规则：禁止 BOM，推荐 GBK，必须 CRLF
        if ($result.has_bom) {
            $result.bat_issues += "FAIL: .bat 文件禁止 BOM"
        }
        if ($result.has_lf_only) {
            $result.bat_issues += "WARN: 发现孤立 LF，应为 CRLF"
        }
    }
    elseif ($ext -eq '.ps1') {
        # .ps1 规则：推荐 UTF-8 BOM，必须 CRLF
        if ($EncodingConfig.ps1_encoding -eq "UTF-8_BOM" -and -not $result.has_bom) {
            $result.ps1_issues += "WARN: 配置要求 UTF-8_BOM 但文件无 BOM"
        }
        if ($result.has_lf_only) {
            $result.ps1_issues += "WARN: 发现孤立 LF，应为 CRLF"
        }
    }

    return $result
}

# ---- 新增：构建脚本 call 检查 ----
function Test-BuildCallPattern {
    param([string]$FilePath, [bool]$CallRequired)

    if (-not $CallRequired) { return @() }

    $issues = @()
    $text = Get-Content $FilePath -Raw -Encoding Default

    # 查找所有 npm/pnpm/node/vite/tsc/vue-tsc 等构建命令调用
    $buildPatterns = @(
        '%PKG_CMD%',
        'npm ',
        'pnpm ',
        'npx ',
        'node ',
        'vite',
        'tsc',
        'vue-tsc',
        'webpack',
        'esbuild'
    )

    foreach ($pattern in $buildPatterns) {
        $lines = $text -split "`r?`n"
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $line = $lines[$i].Trim()
            if ($line -match [regex]::Escape($pattern) -and $line -notmatch '^REM' -and $line -notmatch '^echo') {
                if ($line -notmatch '^call\b') {
                    $issues += "WARN: 第$($i+1)行包含构建命令 '$pattern' 但缺少 call 前缀。这可能导致控制流丢失。"
                }
            }
        }
    }

    return $issues
}

# ---- 执行验证 ----
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  脚本编码验证器 (create-bat)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$all_ok = $true
foreach ($f in $Files) {
    $resolved = Resolve-Path $f -ErrorAction SilentlyContinue
    $path = if ($resolved) { $resolved.Path } else { $f }

    Write-Host "检查: $path" -ForegroundColor DarkGray
    $report = Test-FileEncoding $path $enc

    if ($report.bat_issues.Count -gt 0 -or $report.ps1_issues.Count -gt 0) {
        Write-Host "  [FAIL]" -ForegroundColor Red -NoNewline
        Write-Host " $($report.size) bytes" -ForegroundColor DarkGray
        foreach ($issue in $report.bat_issues) { Write-Host "    BAT: $issue" -ForegroundColor Red }
        foreach ($issue in $report.ps1_issues) { Write-Host "    PS1: $issue" -ForegroundColor Red }
        $all_ok = $false
    } else {
        Write-Host "  [OK]   $($report.size) bytes, BOM=$($report.has_bom), LF-only=$($report.has_lf_only)" -ForegroundColor Green
    }

    # 对 .bat 文件执行 call 检查
    if ($path -match '\.bat$') {
        $callRequired = $false
        if ($config.entries) {
            foreach ($entry in $config.entries) {
                if ($entry.bat_file -and ($path -like "*$($entry.bat_file)*")) {
                    $callRequired = if ($entry.call_required -ne $null) { $entry.call_required } else { $false }
                    break
                }
            }
        }
        $callIssues = Test-BuildCallPattern $path $callRequired
        if ($callIssues.Count -gt 0) {
            Write-Host "  [CALL CHECK]" -ForegroundColor Yellow -NoNewline
            Write-Host " call_required=$callRequired" -ForegroundColor DarkGray
            foreach ($ci in $callIssues) {
                Write-Host "    CALL: $ci" -ForegroundColor Yellow
                $all_ok = $false
            }
        }
    }
}

Write-Host ""
if ($all_ok) {
    Write-Host "  验证通过 OK" -ForegroundColor Green
} else {
    Write-Host "  验证未通过 FAIL 请修复上述问题" -ForegroundColor Red
}
Write-Host ""

exit $(if ($all_ok) { 0 } else { 1 })