<#
.SYNOPSIS
    MorningBrief 一键环境配置脚本
.DESCRIPTION
    在新 PC 上自动检测依赖、初始化配置文件与数据目录、安装前端依赖。
    V1.2 单机 exe 部署：覆盖 Node.js / Python / .env 配置 / 数据目录 / admin-web 前端依赖。
    默认仅安装缺失项，可重复执行。
.PARAMETER SkipSystem
    跳过系统级软件（Node.js/Python）检测，仅做项目级初始化。
.PARAMETER SkipFrontend
    跳过前端依赖安装。适用场景：仅调试后端。
.PARAMETER StartService
    全部完成后自动启动服务。
.EXAMPLE
    .\setup-env.ps1
    标准执行：检测并补齐缺失依赖，完成项目初始化。
.EXAMPLE
    .\setup-env.ps1 -SkipSystem
    跳过系统级软件检测，仅做项目内初始化。
.NOTES
    适用：Windows 10/11 x64，PowerShell 5.1+
#>
#Requires -Version 5.0

[CmdletBinding()]
param(
    [switch]$SkipSystem,
    [switch]$SkipFrontend,
    [switch]$StartService
)

# 强制遇错即停：任一步骤失败应立即暴露，避免后续步骤在错误状态下继续
$ErrorActionPreference = "Stop"
$Script:StepPrefix = "[MorningBrief-Setup]"

# ============================================================
# 工具函数
# ============================================================

function Write-Step {
    param([string]$Message)
    Write-Host "$StepPrefix $Message" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$Message)
    Write-Host "$StepPrefix   [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "$StepPrefix   [WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "$StepPrefix   [FAIL] $Message" -ForegroundColor Red
}

function Test-CommandAvailable {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-NodeVersion {
    param([string]$ExePath)
    try {
        $output = & $ExePath --version 2>&1
        if ($output -match 'v?(\d+)\.(\d+)\.(\d+)') {
            return [PSCustomObject]@{
                Major = [int]$Matches[1]
                Minor = [int]$Matches[2]
                Patch = [int]$Matches[3]
            }
        }
    } catch {}
    return $null
}

function Test-VersionSatisfy {
    param($Current, [int]$MinMajor, [int]$MinMinor)
    if ($null -eq $Current) { return $false }
    if ($Current.Major -gt $MinMajor) { return $true }
    if ($Current.Major -lt $MinMajor) { return $false }
    return $Current.Minor -ge $MinMinor
}

function Invoke-Safe {
    param([scriptblock]$Block, [string]$Description)
    try {
        $global:LASTEXITCODE = 0
        & $Block
        if ($LASTEXITCODE -ne 0) { throw "退出码 $LASTEXITCODE" }
    } catch {
        Write-Err "$Description 失败：$_"
        throw
    }
}

# ============================================================
# 路径常量
# ============================================================

$Script:ProjectRoot  = (Resolve-Path "$PSScriptRoot\..").Path
$Script:FrontendDir  = Join-Path $ProjectRoot "apps/admin-web"
$Script:LogsDir      = Join-Path $ProjectRoot "runtime\logs"
$Script:DataDir      = Join-Path $ProjectRoot "runtime\data"
$Script:EnvFile      = Join-Path $ProjectRoot "backend\.env"
$Script:EnvExample   = Join-Path $ProjectRoot "backend\.env.example"
$Script:Requirements = Join-Path $ProjectRoot "backend\requirements.txt"
$Script:ConfigPath   = Join-Path $PSScriptRoot "config.json"

# Node.js 版本门槛：vite 5 需要 Node 18+，推荐 20+
# 默认值，可被 config.json 的 tools.node.min_version 覆盖
$Script:NodeMinMajor = 18
$Script:NodeMinMinor = 0

# 从 config.json 加载 Node.js 配置（search_paths + min_version）
# 失败时静默降级到默认值，不阻断脚本
$Script:NodeSearchPaths = @()
if (Test-Path $ConfigPath) {
    try {
        $cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($cfg.tools.node.search_paths) {
            $Script:NodeSearchPaths = @($cfg.tools.node.search_paths)
        }
        if ($cfg.tools.node.min_version) {
            $mv = $cfg.tools.node.min_version
            if ($mv.Count -ge 2) {
                $Script:NodeMinMajor = [int]$mv[0]
                $Script:NodeMinMinor = [int]$mv[1]
            }
        }
    } catch {
        Write-Host "  [WARN] config.json 解析失败，使用默认配置: $_" -ForegroundColor Yellow
    }
}

# 统一的 Node.js 查找函数：config 路径 → PATH → 常见安装路径
# 返回 node.exe 完整路径，找不到返回 $null
function Find-NodeExe {
    $candidates = @()
    $candidates += $Script:NodeSearchPaths
    $pathNode = (Get-Command node -ErrorAction SilentlyContinue).Source
    if ($pathNode) { $candidates += $pathNode }
    $candidates += @(
        "C:\Program Files\nodejs\node.exe",
        "C:\Program Files (x86)\nodejs\node.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

# ============================================================
# 主流程
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "  MorningBrief 一键环境配置" -ForegroundColor Cyan
Write-Host "  项目目录: $ProjectRoot" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""

# ---------- Step 1: 系统级软件（Node.js 必需；Python / Docker 可选） ----------

if ($SkipSystem) {
    Write-Step "[1/6] 跳过系统级软件检测（-SkipSystem）"
} else {
    Write-Step "[1/6] 检测系统级软件（Node.js / Python）"

    # --- Python ---
    # V1.2 单机 exe 模式：运行时无需 Python（已打包），但开发/调试需要
    if (Test-CommandAvailable 'python') {
        Write-OK "Python 已就绪（开发/调试用，exe 运行时不依赖）"
    } else {
        Write-Warn "未检测到 Python（仅开发调试需要，exe 运行时不依赖）"
    }

    # --- Node.js ---
    # 仅前端 admin-web 构建需要，后端为单机 exe 不依赖 Node.js
    # 查找链：config.json 配置路径 → PATH 中的 node → 常见安装路径
    $nodeExe = Find-NodeExe
    if ($nodeExe) {
        $ver = Get-NodeVersion $nodeExe
        if ($ver -and (Test-VersionSatisfy $ver $NodeMinMajor $NodeMinMinor)) {
            Write-OK "Node.js 已就绪: $nodeExe ($($ver.Major).$($ver.Minor).$($ver.Patch))"
        } else {
            Write-Warn "检测到 Node.js $($ver.Major).$($ver.Minor) ($nodeExe)，但需要 >= $NodeMinMajor.$NodeMinMinor"
            $nodeExe = $null
        }
    }

    if (-not $nodeExe) {
        Write-Warn "未找到 Node.js >= $NodeMinMajor.$NodeMinMinor（前端构建需要，后端不受影响）"
        Write-Host "  可编辑 scripts\config.json 的 tools.node.search_paths 指定 node.exe 路径" -ForegroundColor Gray
        if (Test-CommandAvailable 'winget') {
            Write-Host "  或通过 winget 安装: winget install OpenJS.NodeJS.LTS" -ForegroundColor Gray
        }
    }
}

# ---------- Step 2: .env 配置文件 ----------

Write-Step "[2/6] 初始化 .env 配置文件"

# .env 包含数据库密码、API Key 等敏感信息，从模板复制后用户自行填值
if (Test-Path $EnvFile) {
    Write-OK ".env 已存在，跳过"
} elseif (Test-Path $EnvExample) {
    Copy-Item $EnvExample $EnvFile
    Write-OK ".env 已从模板创建，请编辑填入实际密钥"
    Write-Host "  notepad backend\.env" -ForegroundColor Gray
} else {
    Write-Warn ".env 与 .env.example 均不存在，请手动创建配置"
}

# ---------- Step 3: 运行时数据目录 ----------

Write-Step "[3/6] 创建运行时数据目录"

# 这些目录在 .gitignore 中被忽略，需在初始化时主动创建
# V1.2 起单机 exe 部署，SQLite 数据库与日志存放在 exe 同级目录
$dataDirs = @(
    $LogsDir,
    $DataDir,
    (Join-Path $DataDir "audio_cache")
)
foreach ($d in $dataDirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}
Write-OK "数据目录就绪 (data/audio_cache, logs)"

# ---------- Step 4: 前端构建产物检查 ----------

Write-Step "[4/6] 检查前端构建产物"

# V1.2 起前端由 FastAPI StaticFiles 服务，需 apps/admin-web/dist 存在
$adminDist = Join-Path $ProjectRoot "apps/admin-web\dist"
if (Test-Path (Join-Path $adminDist "index.html")) {
    Write-OK "前端构建产物已就绪（apps/admin-web/dist/）"
} else {
    Write-Warn "前端未构建，请先运行 scripts\build-frontend.ps1"
}

# ---------- Step 5: 前端依赖 ----------

if ($SkipFrontend) {
    Write-Step "[5/6] 跳过前端依赖安装（-SkipFrontend）"
} else {
    Write-Step "[5/6] 安装前端依赖（admin-web）"

    # npm 查找：优先从已检测的 node.exe 同目录推导，避免版本不一致
    $npmCmd = $null
    $foundNode = Find-NodeExe
    if ($foundNode) {
        $npmInSameDir = Join-Path (Split-Path $foundNode -Parent) "npm.cmd"
        if (Test-Path $npmInSameDir) { $npmCmd = $npmInSameDir }
    }
    if (-not $npmCmd -and (Test-CommandAvailable 'npm')) { $npmCmd = 'npm' }

    if (-not $npmCmd) {
        Write-Warn "找不到 npm，跳过前端依赖安装。请安装 Node.js 18+ 后重跑（可加 -SkipSystem）"
        Write-Host "  或编辑 scripts\config.json 的 tools.node.search_paths 指定 node.exe 路径" -ForegroundColor Gray
    } elseif (-not (Test-Path $FrontendDir)) {
        Write-Warn "admin-web 目录不存在，跳过"
    } else {
        Push-Location $FrontendDir
        try {
            # npm ci 比 install 更严格（依赖 lockfile），失败时更能暴露环境问题
            if (Test-Path (Join-Path $FrontendDir "package-lock.json")) {
                Invoke-Safe { & $npmCmd ci --no-fund --no-audit } "npm ci 安装前端依赖"
            } else {
                Invoke-Safe { & $npmCmd install --no-fund --no-audit } "npm install 安装前端依赖"
            }
            Write-OK "前端依赖安装完成"
        } finally {
            Pop-Location
        }
    }
}

# ---------- Step 6: 最终校验 ----------

Write-Step "[6/6] 环境自检"

$checklist = @(
    @{ Name = ".env 配置文件"; Test = { Test-Path $EnvFile } },
    @{ Name = "logs 目录"; Test = { Test-Path $LogsDir } },
    @{ Name = "data/audio_cache 目录"; Test = { Test-Path (Join-Path $DataDir "audio_cache") } }
)
if (-not $SkipFrontend) {
    $checklist += @{ Name = "前端 node_modules"; Test = { Test-Path (Join-Path $FrontendDir "node_modules") } }
}

$allPass = $true
foreach ($item in $checklist) {
    if (& $item.Test) {
        Write-OK "$($item.Name) ✓"
    } else {
        Write-Err "$($item.Name) ✗"
        $allPass = $false
    }
}

Write-Host ""
if ($allPass) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  环境配置完成！" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  部分检查未通过，请按上述提示修复后重跑" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "下一步操作：" -ForegroundColor Cyan
Write-Host "  1. 编辑 backend\.env 填入实际密钥（JWT_SECRET / LLM_API_KEY / COS_* 等，V1.2 无 MYSQL/REDIS 配置）"
Write-Host "  2. 构建前端：双击 scripts\前端构建.bat"
Write-Host "  3. 启动服务：双击 scripts\启动服务.bat"
Write-Host "  4. 访问地址（单机 exe 默认 127.0.0.1:8000）："
Write-Host "     API:       http://127.0.0.1:8000/api/v1/"
Write-Host "     运营后台:   http://127.0.0.1:8000/admin/"
Write-Host "     健康检查:   http://127.0.0.1:8000/api/health"
Write-Host "     API 文档:   http://127.0.0.1:8000/docs"
Write-Host ""

# ---------- 可选：启动服务 ----------

if ($StartService -and $allPass) {
    Write-Step "启动服务（-StartService）"
    & "$PSScriptRoot\start.ps1"
}

Write-Host ""
return 0
