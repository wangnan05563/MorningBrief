# SonarQube Server Detection and Startup Script
# 用途：跨平台 SonarQube 服务检测与启动（Windows/Linux/macOS）
# 使用：
#   .\start-sonarqube.ps1                 # 检测并启动
#   .\start-sonarqube.ps1 -StatusOnly     # 仅检测状态
#   .\start-sonarqube.ps1 -ForceRestart   # 强制重启
# 配置文件：config/core_config.json（v2.0）+ config/project_config.json
# 兼容：旧 config/scan_config.json（如存在则自动 fallback）

[CmdletBinding()]
param(
    [string]$CoreConfigPath = "$PSScriptRoot\..\config\core_config.json",
    [string]$ProjectConfigPath = "$PSScriptRoot\..\config\project_config.json",
    [string]$LegacyConfigPath = "$PSScriptRoot\..\config\scan_config.json",
    [switch]$StatusOnly,
    [switch]$ForceRestart
)

# ========== 加载共享库（依赖：logging, env-resolver, config-loader）==========
$LibPath = Join-Path $PSScriptRoot "lib\lib.ps1"
. $LibPath

$Platform = Get-Platform
Write-Step "平台: OS=$($Platform.OS), Shell=$($Platform.Shell), PS=$($Platform.PSVersion)"

# ========== 跨平台脚本路径选择 ==========
function Get-ServerScript {
    param([object]$ServerConfig, [string]$ScriptType)

    # v2.0 多平台配置
    if ($ServerConfig.start_script -is [PSCustomObject] -or ($ServerConfig.start_script -and $ServerConfig.start_script.PSObject.Properties[$Platform.OS])) {
        $scriptPath = $ServerConfig.start_script.$($Platform.OS)
        if ($ScriptType -eq "stop") {
            $scriptPath = $ServerConfig.stop_script.$($Platform.OS)
        }
    } else {
        # v1.0 字符串路径（默认 Windows）
        $scriptPath = if ($ScriptType -eq "stop") { $ServerConfig.stop_script } else { $ServerConfig.start_script }
        if ($Platform.OS -ne "windows") {
            Write-Warn "检测到旧版配置 + 非 Windows 平台，启动可能失败"
        }
    }
    return $scriptPath
}

# ========== SonarQube 健康检查 ==========
function Test-SonarQubeHealth {
    param(
        [string]$BaseUrl,
        [int]$TimeoutSeconds = 10
    )
    try {
        $response = Invoke-WebRequest -Uri "$BaseUrl/api/system/status" -UseBasicParsing -TimeoutSec $TimeoutSeconds -ErrorAction Stop
        $body = $response.Content | ConvertFrom-Json
        return @{ Healthy = $true; Status = $body.status; Version = $body.version }
    } catch {
        return @{ Healthy = $false; Status = "unreachable"; Version = "" }
    }
}

# ========== 停止 SonarQube ==========
function Stop-SonarQube {
    param([object]$Config, [string]$BaseUrl)

    $port = [int](Resolve-EnvPlaceholder $Config.port)
    if (Test-PortInUse -Port $port) {
        Write-Warn "SonarQube 正在运行于端口 $port"
        Write-Step "正在停止 SonarQube..."

        $javaHome = Resolve-EnvPlaceholder $Config.java_home
        $installPath = Resolve-EnvPlaceholder $Config.install_path
        $stopScriptRel = Get-ServerScript -ServerConfig $Config -ScriptType "stop"

        if ($stopScriptRel) {
            $stopScript = Join-Path $installPath $stopScriptRel
            if (Test-Path $stopScript) {
                $env:JAVA_HOME = $javaHome
                $env:Path = "$javaHome\bin;$env:Path"

                if ($Platform.OS -eq "windows") {
                    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$stopScript`"" -Wait -NoNewWindow
                } else {
                    & $stopScript stop
                }
                Start-Sleep -Seconds 5
            }
        }

        # 二次检测，必要时强制终止
        if (Test-PortInUse -Port $port) {
            Write-Step "强制停止端口 $port 上的残留进程..."
            if ($Platform.OS -eq "windows") {
                Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
                    try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
                }
            } else {
                $pids = (lsof -ti :$port 2>/dev/null) -split "`n"
                foreach ($pid in $pids) { try { kill -9 $pid 2>/dev/null } catch {} }
            }
            Start-Sleep -Seconds 3
        }

        if (-not (Test-PortInUse -Port $port)) {
            Write-Success "SonarQube 已成功停止"
        } else {
            Write-Err "停止 SonarQube 失败"
        }
    } else {
        Write-Success "SonarQube 未在运行"
    }
}

# ========== 主流程 ==========

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SonarQube 服务器检测（$($Platform.OS)）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 加载配置
$cfg = Load-Config -PrimaryPath $CoreConfigPath -LegacyPath $LegacyConfigPath
$ServerConfig = $cfg.Core.sonarqube_server
$port = [int](Resolve-EnvPlaceholder $ServerConfig.port)
$host = Resolve-EnvPlaceholder $ServerConfig.host
$baseUrl = if ($host -match "^https?://") { $host.TrimEnd('/') } else { "http://$host`:$port" }

Write-Host "配置来源: $($cfg.Source)" -ForegroundColor Gray
Write-Host "SonarQube URL: $baseUrl" -ForegroundColor Gray
Write-Host "端口: $port" -ForegroundColor Gray
Write-Host ""

# 仅检测状态模式
if ($StatusOnly) {
    $listening = Test-PortInUse -Port $port
    $health = Test-SonarQubeHealth -BaseUrl $baseUrl

    Write-Host "SonarQube 服务器状态:" -ForegroundColor Yellow
    Write-Host "  平台    : $($Platform.OS)" -ForegroundColor Gray
    Write-Host "  端口 $port : $(if ($listening) { 'LISTENING' } else { 'NOT LISTENING' })" -ForegroundColor $(if ($listening) { 'Green' } else { 'Red' })
    Write-Host "  健康    : $($health.Status)" -ForegroundColor $(if ($health.Healthy) { 'Green' } else { 'Red' })
    if ($health.Version) {
        Write-Host "  版本   : $($health.Version)" -ForegroundColor Gray
    }
    exit $(if ($listening -and $health.Healthy) { 0 } else { 1 })
}

# 强制重启模式
if ($ForceRestart) {
    Stop-SonarQube -Config $ServerConfig -BaseUrl $baseUrl
}

# 检测并启动
if (Test-PortInUse -Port $port) {
    $health = Test-SonarQubeHealth -BaseUrl $baseUrl
    if ($health.Healthy) {
        Write-Success "SonarQube 已在端口 $port 上运行"
        Write-Host "  状态  : $($health.Status)" -ForegroundColor Gray
        Write-Host "  版本 : $($health.Version)" -ForegroundColor Gray
        exit 0
    } else {
        Write-Warn "端口 $port 被占用但健康检查失败，尝试重启..."
        Stop-SonarQube -Config $ServerConfig -BaseUrl $baseUrl
    }
}

# 启动 SonarQube
Write-Step "SonarQube 未运行，正在启动..."

$javaHome = Resolve-EnvPlaceholder $ServerConfig.java_home
$installPath = Resolve-EnvPlaceholder $ServerConfig.install_path
$startScriptRel = Get-ServerScript -ServerConfig $ServerConfig -ScriptType "start"
$startScript = Join-Path $installPath $startScriptRel

if (-not (Test-Path $javaHome)) {
    Write-Err "JAVA_HOME 路径不存在: $javaHome"
    Write-Host "  请设置环境变量 JAVA_HOME_SONAR，或修改 config/core_config.json" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $startScript)) {
    Write-Err "SonarQube 启动脚本不存在: $startScript"
    Write-Host "  请设置环境变量 SONARQUBE_HOME，或修改 config/core_config.json" -ForegroundColor Yellow
    exit 1
}

Write-Step "JAVA_HOME: $javaHome"
Write-Step "SonarQube: $installPath"
Write-Step "平台: $($Platform.OS)"
Write-Step "启动脚本: $startScript"

$env:JAVA_HOME = $javaHome
$env:Path = "$javaHome\bin;$env:Path"

if ($Platform.OS -eq "windows") {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$startScript`"" -WindowStyle Normal
} else {
    # Linux/Mac：使用 nohup 后台启动
    Start-Process -FilePath "/bin/bash" -ArgumentList "-c", "`"$startScript`" > /dev/null 2>&1 &" -WindowStyle Hidden
}

# 等待启动
$timeout = $ServerConfig.startup_timeout_seconds
$interval = $ServerConfig.health_check_interval_seconds
$elapsed = 0

Write-Step "等待 SonarQube 启动（超时: ${timeout}s）..."

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds $interval
    $elapsed += $interval

    if (Test-PortInUse -Port $port) {
        $health = Test-SonarQubeHealth -BaseUrl $baseUrl
        if ($health.Healthy) {
            Write-Host ""
            Write-Success "SonarQube 启动成功！"
            Write-Host "  状态  : $($health.Status)" -ForegroundColor Gray
            Write-Host "  版本 : $($health.Version)" -ForegroundColor Gray
            Write-Host "  URL   : $baseUrl" -ForegroundColor Gray
            exit 0
        }
    }

    $progress = [math]::Round(($elapsed / $timeout) * 100)
    Write-Host -NoNewline "`r  进度: $progress% ($elapsed/${timeout}s)" -ForegroundColor Yellow
}

Write-Host ""
Write-Err "SonarQube 在 ${timeout}s 内未能启动"
Write-Host ""
Write-Host "排查建议:" -ForegroundColor Yellow
Write-Host "  1. 检查 $javaHome/bin/java 是否存在" -ForegroundColor White
Write-Host "  2. 查看 SonarQube 日志: $installPath/logs/sonar.log" -ForegroundColor White
Write-Host "  3. 确认端口 $port 未被其他进程占用" -ForegroundColor White
exit 1
