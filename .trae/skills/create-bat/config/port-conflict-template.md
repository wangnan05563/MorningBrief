### 端口冲突诊断脚本模板（UTF-8 BOM + CRLF）

用于诊断端口冲突，从 config.json 读取端口配置和冲突处理策略：

```powershell
#Requires -Version 5.1
# 端口冲突诊断脚本
# 用法: powershell -File diagnose-port-conflict.ps1 -ConfigPath config.json

param(
    [string]$ConfigPath = "$PSScriptRoot\config.json"
)

# 加载配置
if (-not (Test-Path $ConfigPath)) { throw "配置文件不存在: $ConfigPath" }
$Config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

$port = $Config.service.port
$projectRoot = $Config.project.root
$conflictConfig = $Config.port_conflict
$waitSeconds = if ($conflictConfig.port_release_wait_seconds) { $conflictConfig.port_release_wait_seconds } else { 5 }

Write-Host "诊断端口 $port 冲突..." -ForegroundColor Cyan

# 查找所有监听目标端口的进程
$netstatOutput = netstat -aon | findstr ":$port.*LISTENING"
if (-not $netstatOutput) {
    Write-Host "[OK] 端口 $port 未被占用" -ForegroundColor Green
    exit 0
}

# 提取所有 PID（去重）
$pids = @()
foreach ($line in $netstatOutput) {
    $parts = $line -split '\s+'
    $pid = $parts[$parts.Length - 1]
    if ($pid -match '^\d+$' -and $pids -notcontains $pid) {
        $pids += $pid
    }
}

Write-Host "发现 $($pids.Count) 个进程监听端口 $port :" -ForegroundColor Yellow

# 对每个 PID 查询进程信息
foreach ($pid in $pids) {
    # 优先用 Get-CimInstance（wmic 在某些 Windows 版本输出为空）
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$pid" -ErrorAction SilentlyContinue
    if ($process) {
        $cmdLine = $process.CommandLine
        $name = $process.Name
    } else {
        # fallback: 用 tasklist 获取进程名
        $taskOutput = tasklist /FI "PID eq $pid" /FO CSV /NH 2>$null
        $name = ($taskOutput -split ',')[0] -trim('"')
        $cmdLine = "<无法获取命令行>"
    }

    # 判断归属
    $isSameProject = $false
    if ($cmdLine -and $projectRoot) {
        $normalizedRoot = $projectRoot -replace '\\', '\\'
        if ($cmdLine -match $normalizedRoot) { $isSameProject = $true }
    }

    $category = if ($isSameProject) { "同项目" } else { "其他项目" }
    Write-Host "  PID $pid ($name) [$category]" -ForegroundColor $(if ($isSameProject) {'Yellow'} else {'Red'})
    Write-Host "    命令行: $cmdLine" -ForegroundColor Gray

    # 按策略处理
    if ($isSameProject -and $conflictConfig.kill_same_project) {
        Write-Host "    → 杀掉同项目旧进程..." -ForegroundColor Yellow
        taskkill /F /T /PID $pid 2>$null
    } elseif (-not $isSameProject -and $conflictConfig.kill_other_project) {
        Write-Host "    → 杀掉其他项目进程..." -ForegroundColor Yellow
        taskkill /F /T /PID $pid 2>$null
    } else {
        Write-Host "    → 需用户确认处理方式" -ForegroundColor Yellow
    }
}

# 等待端口释放
Write-Host "`n等待端口释放（最多 $waitSeconds 秒）..." -ForegroundColor Cyan
for ($i = 0; $i -lt $waitSeconds; $i++) {
    Start-Sleep -Seconds 1
    $stillUsed = netstat -aon | findstr ":$port.*LISTENING"
    if (-not $stillUsed) {
        Write-Host "[OK] 端口 $port 已释放" -ForegroundColor Green
        exit 0
    }
}

# 端口仍被占用
Write-Host "[WARN] 端口 $port 仍被占用:" -ForegroundColor Red
$remaining = netstat -aon | findstr ":$port.*LISTENING"
$remaining | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host "`n建议:" -ForegroundColor Yellow
Write-Host "  1. 手动杀掉剩余进程"
Write-Host "  2. 或修改 config.json 的 service.port 为其他端口"
exit 1
```

---
