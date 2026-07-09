<#
.SYNOPSIS
    20_News 服务启动脚本（V1.2 单机 exe / 开发模式）
.DESCRIPTION
    智能启动 20_News 后端服务：
    1. 优先启动已构建的 exe（dist\20-news\20-news.exe）
    2. 回退到 venv 开发模式（.venv\Scripts\python.exe backend\launcher.py）
    3. 再回退到系统 python（V1.2 开发模式不强制 venv）
    启动后写入 PID 到 .run\20-news.pid，供 stop.ps1 使用。
.PARAMETER Dev
    强制开发模式（venv 优先，回退系统 python），忽略 exe。
.PARAMETER Exe
    强制 exe 模式（要求 dist\20-news\20-news.exe 存在）。
.EXAMPLE
    .\start.ps1
    自动选择模式（优先 exe → venv → 系统 python）。
.EXAMPLE
    .\start.ps1 -Dev
    强制开发模式。
.NOTES
    适用：Windows 10/11 x64，PowerShell 5.1+
#>
#Requires -Version 5.0

[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Exe
)

$ErrorActionPreference = "Stop"
$Script:StepPrefix = "[20News-Start]"

function Write-Step { param([string]$Message) Write-Host "$StepPrefix $Message" -ForegroundColor Cyan }
function Write-OK    { param([string]$Message) Write-Host "$StepPrefix   [OK] $Message" -ForegroundColor Green }
function Write-Warn  { param([string]$Message) Write-Host "$StepPrefix   [WARN] $Message" -ForegroundColor Yellow }
function Write-Err   { param([string]$Message) Write-Host "$StepPrefix   [FAIL] $Message" -ForegroundColor Red }

# ============================================================
# 路径常量
# ============================================================

$Script:ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Script:ExePath     = Join-Path $ProjectRoot "dist\20-news\20-news.exe"
$Script:VenvPython  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Script:LauncherPy  = Join-Path $ProjectRoot "backend\launcher.py"
# 系统回退：venv 不存在时用系统 python（V1.2 开发模式不强制 venv）
$Script:SystemPython = $null
$sysPyCmd = Get-Command python -ErrorAction SilentlyContinue
if ($sysPyCmd) { $Script:SystemPython = $sysPyCmd.Source }
$Script:RunDir      = Join-Path $ProjectRoot ".run"
$Script:PidFile     = Join-Path $RunDir "20-news.pid"
$Script:LogFile     = Join-Path $ProjectRoot "logs\service-start.log"

# ============================================================
# 模式选择
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "  20_News 服务启动" -ForegroundColor Cyan
Write-Host "  项目目录: $ProjectRoot" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""

# -Dev 与 -Exe 互斥
if ($Dev -and $Exe) {
    Write-Err "-Dev 与 -Exe 不可同时指定"
    exit 1
}

$mode = $null
$exeExists = Test-Path $ExePath
$venvExists = Test-Path $VenvPython
$launcherExists = Test-Path $LauncherPy

if ($Exe) {
    # 强制 exe 模式
    if (-not $exeExists) {
        Write-Err "exe 不存在: $ExePath"
        Write-Host "  请先运行 scripts\构建打包.bat 生成 exe" -ForegroundColor Gray
        exit 1
    }
    $mode = "exe"
} elseif ($Dev) {
    # 强制开发模式：优先 venv，回退系统 python
    if (-not $launcherExists) {
        Write-Err "launcher.py 不存在: $LauncherPy"
        exit 1
    }
    if ($venvExists) {
        $mode = "dev"
    } elseif ($SystemPython) {
        $mode = "dev-sys"
        Write-Warn "未找到 venv，回退到系统 python: $SystemPython"
    } else {
        Write-Err "未找到 venv python 也未找到系统 python"
        Write-Host "  请创建虚拟环境: python -m venv .venv" -ForegroundColor Gray
        Write-Host "  或安装系统 Python 并加入 PATH" -ForegroundColor Gray
        exit 1
    }
} else {
    # 自动选择：优先 exe → venv → 系统 python
    if ($exeExists) {
        $mode = "exe"
    } elseif ($venvExists -and $launcherExists) {
        $mode = "dev"
    } elseif ($SystemPython -and $launcherExists) {
        $mode = "dev-sys"
    } else {
        Write-Err "无可用的启动方式"
        Write-Host "  方式 1（exe 模式）: 运行 scripts\构建打包.bat 生成 exe" -ForegroundColor Gray
        Write-Host "  方式 2（venv 模式）: python -m venv .venv 并安装 backend\requirements.txt" -ForegroundColor Gray
        Write-Host "  方式 3（系统 python）: 安装 Python 3.10+ 并 pip install -r backend\requirements.txt" -ForegroundColor Gray
        exit 1
    }
}

Write-Step "启动模式: $mode"
if ($mode -eq "exe") {
    Write-Host "  EXE: $ExePath" -ForegroundColor DarkGray
} elseif ($mode -eq "dev") {
    Write-Host "  Python: $VenvPython" -ForegroundColor DarkGray
    Write-Host "  入口:   $LauncherPy" -ForegroundColor DarkGray
} elseif ($mode -eq "dev-sys") {
    Write-Host "  Python: $SystemPython (系统)" -ForegroundColor DarkGray
    Write-Host "  入口:   $LauncherPy" -ForegroundColor DarkGray
    Write-Warn "使用系统 Python（非隔离环境），依赖需自行确保已装"
}

# ============================================================
# 检查是否已有实例运行
# ============================================================

Write-Step "[1/3] 检查现有实例"

if (Test-Path $PidFile) {
    $oldPid = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Warn "已有实例运行 (PID=$oldPid)，请先运行 scripts\停止服务.bat"
        exit 1
    } else {
        # PID 文件存在但进程已退出，清理残留
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "  清理过期 PID 文件" -ForegroundColor DarkGray
    }
}

# 按进程名查找（兜底：PID 文件可能丢失）
$existingProcs = @()
if ($mode -eq "exe") {
    $existingProcs = Get-Process -Name "20-news" -ErrorAction SilentlyContinue
} else {
    # dev / dev-sys 均按命令行含 launcher.py 的 python.exe 匹配
    $existingProcs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*launcher.py*" } |
        ForEach-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
}

if ($existingProcs) {
    Write-Warn "已有 $($existingProcs.Count) 个服务进程运行"
    $existingProcs | ForEach-Object { Write-Host "  PID=$($_.Id)" -ForegroundColor DarkGray }
    Write-Host "  请先运行 scripts\停止服务.bat" -ForegroundColor Gray
    exit 1
}

Write-OK "无冲突实例"

# ============================================================
# 准备运行时目录
# ============================================================

Write-Step "[2/3] 准备运行时目录"

# .run 目录存放 PID 文件（不入库）
if (-not (Test-Path $RunDir)) {
    New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
    Write-Host "  创建 $RunDir" -ForegroundColor DarkGray
}

# logs 目录（启动日志输出位置）
$logsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

Write-OK "目录就绪"

# ============================================================
# 启动服务
# ============================================================

Write-Step "[3/3] 启动服务进程"

# 启动为后台进程，stdout/stderr 重定向到日志文件（Start-Process 直接写文件，无需手动管理 Stream）
try {
    if ($mode -eq "exe") {
        $proc = Start-Process -FilePath $ExePath `
            -WorkingDirectory (Split-Path $ExePath) `
            -RedirectStandardOutput $LogFile `
            -RedirectStandardError "$LogFile.err" `
            -WindowStyle Normal `
            -PassThru
    } else {
        # dev / dev-sys 共用：dev 用 venv python，dev-sys 用系统 python
        $pyExe = if ($mode -eq "dev-sys") { $SystemPython } else { $VenvPython }
        $proc = Start-Process -FilePath $pyExe `
            -ArgumentList $LauncherPy `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $LogFile `
            -RedirectStandardError "$LogFile.err" `
            -WindowStyle Normal `
            -PassThru
    }

    # 写入 PID 文件
    Set-Content -Path $PidFile -Value $proc.Id -Encoding UTF8
    Write-OK "服务已启动 (PID=$($proc.Id))"
    Write-Host "  PID 文件: $PidFile" -ForegroundColor DarkGray
    Write-Host "  日志文件: $LogFile" -ForegroundColor DarkGray
} catch {
    Write-Err "启动失败: $_"
    exit 1
}

# ============================================================
# 等待健康检查
# ============================================================

Write-Host ""
Write-Host "  等待服务就绪（最多 30 秒）..." -ForegroundColor Cyan

$host_ = "127.0.0.1"
$port = 8000
# 从 .env 读取端口（如有）
$envFile = Join-Path $ProjectRoot "backend\.env"
if ($mode -eq "exe") { $envFile = Join-Path (Split-Path $ExePath) ".env" }
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -ErrorAction SilentlyContinue
    $portLine = $envContent | Where-Object { $_ -match '^\s*APP_PORT\s*=' }
    if ($portLine -match 'APP_PORT\s*=\s*(\d+)') { $port = [int]$Matches[1] }
    # APP_HOST=0.0.0.0 是服务端绑定地址，客户端健康检查必须用 127.0.0.1
    $hostLine = $envContent | Where-Object { $_ -match '^\s*APP_HOST\s*=' }
    if ($hostLine -match 'APP_HOST\s*=\s*(\S+)') {
        $bindHost = $Matches[1]
        if ($bindHost -ne '0.0.0.0') { $host_ = $bindHost }
    }
}

$healthUrl = "http://${host_}:${port}/api/health"
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    # 检查进程是否意外退出
    if ($proc.HasExited) {
        Write-Err "进程意外退出 (退出码 $($proc.ExitCode))"
        Write-Host "  查看日志: $LogFile" -ForegroundColor Gray
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        exit 1
    }
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline -ForegroundColor DarkGray
    }
}
Write-Host ""

if ($ready) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  服务启动成功！" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  PID:         $($proc.Id)"
    Write-Host "  健康检查:    $healthUrl"
    Write-Host "  API 文档:    http://${host_}:${port}/docs"
    Write-Host "  运营后台:    http://${host_}:${port}/admin/"
    Write-Host "  日志文件:    $LogFile"
    Write-Host ""
    Write-Host "  停止服务:    双击 scripts\停止服务.bat" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Warn "服务已启动但 30 秒内未通过健康检查"
    Write-Host "  可能仍在初始化，或 .env 配置有误" -ForegroundColor Gray
    Write-Host "  手动验证: $healthUrl" -ForegroundColor Gray
    Write-Host "  查看日志: $LogFile" -ForegroundColor Gray
}

Write-Host ""
return 0
