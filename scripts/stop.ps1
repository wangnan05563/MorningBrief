<#
.SYNOPSIS
    MorningBrief 服务停止脚本（V1.2 单机 exe / 开发模式）
.DESCRIPTION
    停止 MorningBrief 后端服务进程：
    1. 优先读取 .run\MorningBrief.pid 停止指定进程
    2. 兜底按进程名查找（MorningBrief.exe 或运行 launcher.py 的 python.exe）
    3. 清理 PID 文件
.PARAMETER Force
    强制终止（Kill），不等进程优雅退出。
.EXAMPLE
    .\stop.ps1
    停止服务。
.EXAMPLE
    .\stop.ps1 -Force
    强制终止服务进程。
.NOTES
    适用：Windows 10/11 x64，PowerShell 5.1+
#>
#Requires -Version 5.0

[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Script:StepPrefix = "[MorningBrief-Stop]"

function Write-Step { param([string]$Message) Write-Host "$StepPrefix $Message" -ForegroundColor Cyan }
function Write-OK    { param([string]$Message) Write-Host "$StepPrefix   [OK] $Message" -ForegroundColor Green }
function Write-Warn  { param([string]$Message) Write-Host "$StepPrefix   [WARN] $Message" -ForegroundColor Yellow }
function Write-Err   { param([string]$Message) Write-Host "$StepPrefix   [FAIL] $Message" -ForegroundColor Red }

# ============================================================
# 路径常量
# ============================================================

$Script:ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Script:RunDir      = Join-Path $ProjectRoot ".run"
$Script:PidFile     = Join-Path $RunDir "MorningBrief.pid"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "  MorningBrief 服务停止" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""

# ============================================================
# 收集目标进程
# ============================================================

Write-Step "[1/2] 查找服务进程"

$targetProcs = @()

# 方式 1：从 PID 文件读取
if (Test-Path $PidFile) {
    $pidValue = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pidValue) {
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($proc) {
            $targetProcs += $proc
            Write-Host "  从 PID 文件找到进程: PID=$($proc.Id)" -ForegroundColor DarkGray
        } else {
            Write-Host "  PID 文件指向的进程已不存在（PID=$pidValue）" -ForegroundColor DarkGray
        }
    }
    # 无论进程是否存在，PID 文件稍后统一清理
}

# 方式 2：按进程名兜底查找（PID 文件丢失或进程重启时）
if ($targetProcs.Count -eq 0) {
    # exe 模式进程
    $exeProcs = Get-Process -Name "MorningBrief" -ErrorAction SilentlyContinue
    if ($exeProcs) {
        $targetProcs += $exeProcs
        Write-Host "  按 exe 进程名找到: $($exeProcs.Count) 个" -ForegroundColor DarkGray
    }

    # 开发模式进程（命令行含 launcher.py 的 python.exe）
    # 用 CIM 查询命令行，避免误杀其他 python 进程
    $devProcs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*launcher.py*" }
    foreach ($p in $devProcs) {
        $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
        if ($proc -and ($targetProcs.Id -notcontains $proc.Id)) {
            $targetProcs += $proc
            Write-Host "  按开发模式进程找到: PID=$($proc.Id)" -ForegroundColor DarkGray
        }
    }
}

if ($targetProcs.Count -eq 0) {
    Write-Warn "未找到运行中的 MorningBrief 服务进程"
    # 清理可能残留的 PID 文件
    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "  已清理残留 PID 文件" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  无需停止（无运行中实例）" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
}

Write-OK "找到 $($targetProcs.Count) 个进程"
$targetProcs | ForEach-Object {
    Write-Host "  PID=$($_.Id)  $($_.ProcessName)" -ForegroundColor DarkGray
}

# ============================================================
# 停止进程
# ============================================================

Write-Step "[2/2] 停止进程"

$stoppedCount = 0
$failedCount = 0

foreach ($proc in $targetProcs) {
    try {
        if ($Force) {
            # -Force：直接 Kill（不等优雅退出）
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Write-OK "强制终止 PID=$($proc.Id) ($($proc.ProcessName))"
        } else {
            # 默认：先 CloseMainWindow（允许 uvicorn 优雅退出保存状态），3 秒后仍存活则 Kill
            $null = $proc.CloseMainWindow()
            $proc.WaitForExit(3000) | Out-Null
            if (-not $proc.HasExited) {
                Stop-Process -Id $proc.Id -Force -ErrorAction Stop
                Write-OK "优雅退出超时，强制终止 PID=$($proc.Id)"
            } else {
                Write-OK "优雅退出 PID=$($proc.Id) ($($proc.ProcessName))"
            }
        }
        $stoppedCount++
    } catch {
        Write-Err "停止 PID=$($proc.Id) 失败: $_"
        $failedCount++
    }
}

# 清理 PID 文件
if (Test-Path $PidFile) {
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "  已清理 PID 文件" -ForegroundColor DarkGray
}

Write-Host ""
if ($failedCount -eq 0) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  服务已停止（$stoppedCount 个进程）" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  部分进程停止失败（成功 $stoppedCount / 失败 $failedCount）" -ForegroundColor Yellow
    Write-Host "  可尝试: 停止服务.bat -Force" -ForegroundColor Gray
    Write-Host "============================================================" -ForegroundColor Yellow
}

Write-Host ""
return 0
