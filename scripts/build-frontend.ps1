<#
.SYNOPSIS
    MorningBrief 前端构建脚本（admin-web）
.DESCRIPTION
    构建 apps/admin-web Vue 项目，产物输出到 apps/admin-web/dist/。
    V1.2 起由 FastAPI StaticFiles 服务此目录（单机 exe 模式）。
.PARAMETER SkipInstall
    跳过 npm 依赖安装（仅依赖无变更时用）。
.EXAMPLE
    .\build-frontend.ps1
    标准构建：检查依赖 + vite build
.EXAMPLE
    .\build-frontend.ps1 -SkipInstall
    跳过依赖安装，直接构建（node_modules 已存在且无变更时用）
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Script:StepPrefix = "[MorningBrief-Frontend]"

function Write-Step { param([string]$Message) Write-Host "$StepPrefix $Message" -ForegroundColor Cyan }
function Write-OK    { param([string]$Message) Write-Host "$StepPrefix   [OK] $Message" -ForegroundColor Green }
function Write-Warn  { param([string]$Message) Write-Host "$StepPrefix   [WARN] $Message" -ForegroundColor Yellow }

$Script:ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Script:FrontendDir = Join-Path $ProjectRoot "apps/admin-web"
$Script:DistDir     = Join-Path $FrontendDir "dist"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MorningBrief 前端构建（admin-web）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 检查 Node.js ----------
Write-Step "[1/4] 检查 Node.js 环境"

# Node.js 查找：config.json 配置路径 → PATH 中的 node → 常见安装路径
# 找到 node.exe 后 npm.cmd/npx.cmd 从同目录推导，避免 node 与 npm 版本不一致
$Script:ConfigPath = Join-Path $PSScriptRoot "config.json"
$nodeExe = $null
$npmCmd  = $null

# 1. 从 config.json 读取 search_paths
$configPaths = @()
if (Test-Path $ConfigPath) {
    try {
        $cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($cfg.tools.node.search_paths) { $configPaths = @($cfg.tools.node.search_paths) }
    } catch {
        Write-Host "  [WARN] config.json 解析失败，跳过配置路径: $_" -ForegroundColor Yellow
    }
}

# 2. 汇总查找路径：config 路径优先，PATH 中的 node 次之，常见安装路径兜底
$candidates = @()
$candidates += $configPaths
$pathNode = (Get-Command node -ErrorAction SilentlyContinue).Source
if ($pathNode) { $candidates += $pathNode }
$candidates += @(
    "C:\Program Files\nodejs\node.exe",
    "C:\Program Files (x86)\nodejs\node.exe"
)

# 3. 按顺序探测，找到第一个可用的 node.exe
foreach ($p in $candidates) {
    if ($p -and (Test-Path $p)) {
        $nodeExe = $p
        break
    }
}

if (-not $nodeExe) {
    Write-Host "[ERROR] 未检测到 Node.js，请安装 Node.js 18+ 后重试" -ForegroundColor Red
    Write-Host "  下载地址: https://nodejs.org/" -ForegroundColor Gray
    Write-Host "  或编辑 scripts\config.json 的 tools.node.search_paths 指定 node.exe 路径" -ForegroundColor Gray
    exit 1
}

# 4. npm.cmd/npx.cmd 与 node.exe 同目录（Node.js Windows 安装包的标准布局）
$nodeDir = Split-Path $nodeExe -Parent
$npmPath = Join-Path $nodeDir "npm.cmd"
if (Test-Path $npmPath) {
    $npmCmd = $npmPath
} elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    # 兜底：PATH 中的 npm（可能版本不一致，但优于无）
    $npmCmd = 'npm'
} else {
    Write-Host "[ERROR] 找到 node.exe ($nodeExe) 但同目录无 npm.cmd，请检查 Node.js 安装" -ForegroundColor Red
    exit 1
}

# 5. 版本检测：vite 5 + ??= 运算符需要 Node 18+
$nodeVersion = (& $nodeExe --version 2>$null) -replace '[v\n\r]', ''
if ($nodeVersion) {
    $nodeMajor = [int]($nodeVersion.Split('.')[0])
    if ($nodeMajor -lt 18) {
        Write-Host "[ERROR] Node $nodeVersion 版本过低，vite 5 需要 Node 18+" -ForegroundColor Red
        exit 1
    }
    Write-OK "Node 版本：$nodeVersion ($nodeExe)"
} else {
    Write-Host "[ERROR] 无法获取 Node.js 版本: $nodeExe" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $FrontendDir)) {
    Write-Host "[ERROR] apps/admin-web 目录不存在: $FrontendDir" -ForegroundColor Red
    exit 1
}

# ---------- 安装依赖 ----------
if ($SkipInstall) {
    Write-Step "[2/4] 跳过依赖安装（-SkipInstall）"
} else {
    Write-Step "[2/4] 安装前端依赖"

    Push-Location $FrontendDir
    try {
        # node_modules 增量：比较 package-lock.json 与 .install-stamp 的 mtime
        # 仅在 lock 文件变化时才 npm ci，避免每次重装耗时
        $lockFile  = "package-lock.json"
        $stampFile = "node_modules\.install-stamp"
        $needInstall = $false

        if (-not (Test-Path "node_modules")) {
            $needInstall = $true
            Write-Host "  node_modules 不存在，需要安装" -ForegroundColor DarkGray
        } elseif (-not (Test-Path $stampFile)) {
            $needInstall = $true
            Write-Host "  .install-stamp 不存在，需要重装" -ForegroundColor DarkGray
        } elseif (Test-Path $lockFile) {
            $lockMtime  = (Get-Item $lockFile).LastWriteTime
            $stampMtime = (Get-Item $stampFile).LastWriteTime
            if ($lockMtime -gt $stampMtime) {
                $needInstall = $true
                Write-Host "  package-lock.json 已变更，需要重新安装依赖" -ForegroundColor DarkGray
            } else {
                Write-Host "  node_modules 已是最新（lock 未变），跳过安装" -ForegroundColor DarkGray
            }
        }

        if ($needInstall) {
            Write-Host "  预计耗时：约 1-3 分钟" -ForegroundColor DarkGray
            if (Test-Path $lockFile) {
                & $npmCmd ci --no-fund --no-audit
            } else {
                & $npmCmd install --no-fund --no-audit
            }
            if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm 依赖安装失败" }
            # 写入安装时间戳（用于下次增量判断）
            Set-Content -Path $stampFile -Value (Get-Date -Format "o") -Encoding UTF8
            Write-OK "前端依赖安装完成"
        }
    } finally {
        Pop-Location
    }
}

# ---------- 清理旧产物 ----------
Write-Step "[3/4] 清理旧构建产物"

if (Test-Path $DistDir) {
    Remove-Item -Recurse -Force $DistDir -ErrorAction SilentlyContinue
    Write-OK "旧产物已清理"
} else {
    Write-OK "无旧产物需清理"
}

# ---------- 构建前端 ----------
Write-Step "[4/4] 执行 vite build"

# 绕过 npm run build，直接用 node.exe 执行 vite.js
# npm 在执行 npm run 时可能用旧版 node（npm 内部维护的 node 路径或 script-shell 配置），
# 导致 vite 加载 ESM 模块时报 ??= 语法错误（旧版 Node 不支持 ES2021 语法）
# 直接用已验证版本的 $nodeExe 执行，确保 Node 版本正确
Push-Location $FrontendDir
try {
    $viteJs = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"
    if (-not (Test-Path $viteJs)) { throw "vite.js 不存在: $viteJs（请先运行 npm install）" }
    & $nodeExe $viteJs build
    if ($LASTEXITCODE -ne 0) { throw "vite build 失败" }
} finally {
    Pop-Location
}

# 校验产物
$indexFile = Join-Path $DistDir "index.html"
if (Test-Path $indexFile) {
    Write-OK "构建完成，产物位于 apps/admin-web\dist\"
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  前端构建成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  产物目录: apps/admin-web\dist\"
    Write-Host "  部署方式: FastAPI StaticFiles 服务（单机 exe 模式）"
    Write-Host "  下一步:   运行 scripts\build-exe.ps1 打包 exe"
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "[ERROR] 构建完成但未找到 dist\index.html，请检查 vite 配置" -ForegroundColor Red
    exit 1
}
