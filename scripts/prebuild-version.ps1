<#
.SYNOPSIS
    构建前版本号预生成（写入 package.json 与 backend/VERSION）。
.DESCRIPTION
    按「当天日期 + 递增序号」生成 patch 号，保证每次构建的版本号唯一。

    规则：
      - 版本格式：<MAJOR>.<MINOR>.<YYYYMMDD>.<NNN>
        示例：1.0.20260831.001 （8月31日的第1次构建）
      - MAJOR.MINOR：从 package.json 读取（产品主版本，不会因构建自动递增）
      - YYYYMMDD：本地日期（UTC+8，与项目所有日期逻辑一致）
      - NNN：当日构建序号，3位零填充。从 package.json / backend/VERSION 读取
             已有版本号，若日期段=今天则 +1；首次或跨日则重置为 001
      - 每次构建都递增，即使构建失败也写入（避免同日两次构建覆盖相同版本）
    输出：
      - 写回 repo 根 package.json 的 version 字段（用户要求）
      - 同步写 backend/VERSION（build-exe.ps1 / _build_info.py / installer.iss
        实际读取的是这个文件，必须同步才能让 exe 关于页 / 安装包文件名显示新版本）
.PARAMETER SkipBump
    仅显示当前版本，不递增（调试 / 预览用）。
.EXAMPLE
    .\prebuild-version.ps1
    标准执行：计算下一个构建版本，写入 package.json + backend/VERSION。
.NOTES
    为什么版本号生成放在单独 .ps1 而不是 build-exe.ps1 内？
    - 用户明确要求「在构建打包.bat 打包前」执行，意味着版本写入早于任何构建步骤；
      即使后续 PyInstaller / Inno 失败，本次构建已消耗一个唯一 patch 号，不会与
      下次成功构建重复占用同一版本号（否则 Inno Setup 同名缓存 / 安装包升级检测
      会出问题）。
    - 独立 .ps1 便于单独运行与调试。
#>
[CmdletBinding()]
param(
    [switch]$SkipBump
)

$ErrorActionPreference = "Stop"
$Script:StepPrefix = "[MorningBrief-Version]"

function Write-Step { param([string]$Msg) Write-Host "$StepPrefix $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "$StepPrefix   [OK] $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "$StepPrefix   [WARN] $Msg" -ForegroundColor Yellow }

$repoRoot    = (Resolve-Path "$PSScriptRoot\..").Path
$pkgJsonPath = Join-Path $repoRoot "package.json"
$verFilePath = Join-Path $repoRoot "backend\VERSION"

# ============================================================
# 1. 读取当前版本：优先 package.json，缺失时降级 backend/VERSION，全新环境 1.0.0
# ============================================================
Write-Step "[1/3] 读取当前版本"

$major = 1
$minor = 0
$prevDate = $null   # 上一次构建的日期段（Int 20260831）
$prevSeq  = 0       # 上一次构建的序号（Int）

if (Test-Path $pkgJsonPath) {
    try {
        $pkg = Get-Content $pkgJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
        if ($pkg.version) {
            $v = [string]$pkg.version
            Write-Host "  package.json version=$v" -ForegroundColor DarkGray
            if ($v -match '^(\d+)\.(\d+)(?:\.(\d{8}))?(?:\.(\d+))?$') {
                $major    = [int]$Matches[1]
                $minor    = [int]$Matches[2]
                if ($Matches[3]) { $prevDate = [int]$Matches[3] }
                if ($Matches[4]) { $prevSeq  = [int]$Matches[4] }
            } else {
                Write-Warn "package.json version 格式非 MAJOR.MINOR[.YYYYMMDD[.NNN]]，忽略使用默认 1.0"
            }
        }
    } catch {
        Write-Warn "package.json 解析失败: $_"
    }
}

# 若 package.json 没解析出日期段，再尝试 backend/VERSION 兜底
if (-not $prevDate -and (Test-Path $verFilePath)) {
    $v2 = (Get-Content $verFilePath -Encoding UTF8 |
        Where-Object { $_.Trim() -and -not $_.Trim().StartsWith('#') } |
        Select-Object -First 1)
    if ($v2 -and $v2 -match '^(\d+)\.(\d+)(?:\.(\d{8}))?(?:\.(\d+))?$') {
        if (-not $Matches[3]) {
            # VERSION 只有 MAJOR.MINOR 或 MAJOR.MINOR.PATCH（非 8 位日期），保留当前 major.minor
        } else {
            $major    = [int]$Matches[1]
            $minor    = [int]$Matches[2]
            $prevDate = [int]$Matches[3]
            $prevSeq  = if ($Matches[4]) { [int]$Matches[4] } else { 0 }
        }
        Write-Host "  backend/VERSION fallback=$v2" -ForegroundColor DarkGray
    }
}

Write-Host ("  解析结果: MAJOR={0} MINOR={1} PREV_DATE={2} PREV_SEQ={3}" -f $major, $minor, $prevDate, $prevSeq)

# ============================================================
# 2. 计算新版本号（本地日期 UTC+8，与项目其余日期逻辑一致）
# ============================================================
Write-Step "[2/3] 计算新构建版本号"

# 本地日期（UTC+8 香港时区）：与 ai_budget / crawler / TTLCache counter 使用的日期口径一致
$today = [DateTimeOffset]::Now
$todayInt = [int]$today.ToString('yyyyMMdd')

if ($SkipBump) {
    Write-Host "  (-SkipBump) 不递增，基于现有值显示" -ForegroundColor DarkGray
    if ($prevDate -eq $todayInt -and $prevSeq -gt 0) {
        $newSeq = $prevSeq
    } elseif ($prevDate -eq $todayInt) {
        $newSeq = 1
    } else {
        $newSeq = 1
    }
    $newDate = if ($prevDate) { $prevDate } else { $todayInt }
} else {
    if ($prevDate -eq $todayInt) {
        # 同日：序号 +1（即使上次构建失败也递增，避免同日重号）
        $newSeq  = $prevSeq + 1
    } else {
        # 新的一天：从 001 开始
        $newSeq  = 1
    }
    $newDate = $todayInt
}

$newVersion = "{0}.{1}.{2}.{3:D3}" -f $major, $minor, $newDate, $newSeq
Write-OK ("新版本: {0}" -f $newVersion)

# ============================================================
# 3. 写回 package.json + backend/VERSION
# ============================================================
Write-Step "[3/3] 写回文件"

# ---- package.json ----
# 保留 package.json 已有其他字段（name / scripts / private / description 等），仅替换 version
if (Test-Path $pkgJsonPath) {
    try {
        $pkg = Get-Content $pkgJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
        $pkg | Add-Member -NotePropertyName version -NotePropertyValue $newVersion -Force
        # 缩进 4 空格，与 package.json 常规格式一致；UTF-8 no BOM
        $jsonStr = ($pkg | ConvertTo-Json)
        [System.IO.File]::WriteAllText($pkgJsonPath, $jsonStr + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
        Write-OK ("package.json version -> {0}" -f $newVersion)
    } catch {
        throw "写回 package.json 失败: $_"
    }
} else {
    throw ("package.json 不存在: {0}" -f $pkgJsonPath)
}

# ---- backend/VERSION ----
# 格式：仅一行版本号（UTF-8 no BOM），build-exe.ps1 / installer.iss / _build_info.py 直接读取
$verDir = Split-Path $verFilePath -Parent
if (-not (Test-Path $verDir)) { New-Item -ItemType Directory -Force $verDir | Out-Null }
[System.IO.File]::WriteAllText($verFilePath, ($newVersion + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
Write-OK ("backend/VERSION -> {0}" -f $newVersion)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host ("  构建版本: {0}" -f $newVersion) -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 导出环境变量（供下游 build-exe.ps1 / ISCC 通过 $env:MORNINGBRIEF_VERSION 读取
# 作冗余备份，但实际两个文件已写入，所以仅为调试输出）
$env:MORNINGBRIEF_VERSION = $newVersion