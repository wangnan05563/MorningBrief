# SonarQube MCP 连接验证脚本（v2.0 通用化）
# 用途：验证 SonarQube 服务状态、环境变量、MCP 工具可用性
# 配置：自动检测 config/core_config.json（v2.0）或 config/scan_config.json（v1.0 兼容）

[CmdletBinding()]
param(
    [string]$CoreConfigPath = "$PSScriptRoot\..\config\core_config.json",
    [string]$ProjectConfigPath = "$PSScriptRoot\..\config\project_config.json",
    [string]$LegacyConfigPath = "$PSScriptRoot\..\config\scan_config.json"
)

# ========== 加载共享库（依赖：env-resolver, config-loader, logging）==========
$LibPath = Join-Path $PSScriptRoot "lib\lib.ps1"
. $LibPath

# ========== 主流程 ==========
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SonarQube 连接验证" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 加载配置（使用共享库 Load-SonarConfig）
$cfg = Load-SonarConfig -CoreConfigPath $CoreConfigPath -ProjectConfigPath $ProjectConfigPath -LegacyConfigPath $LegacyConfigPath

Write-Host "[OK] 配置加载成功 ($($cfg.Source))" -ForegroundColor Green

# 解析关键配置
$serverCfg = $cfg.Core.sonarqube_server
$port = [int](Resolve-EnvPlaceholder $serverCfg.port)
$host = Resolve-EnvPlaceholder $serverCfg.host
$baseUrl = if ($host -match "^https?://") { $host.TrimEnd('/') } else { "http://$host`:$port" }
$projectKey = if ($cfg.Project -and $cfg.Project.project.key) {
    Resolve-EnvPlaceholder $cfg.Project.project.key
} else {
    if ($cfg.Core.project.key) { Resolve-EnvPlaceholder $cfg.Core.project.key } else { "" }
}

Write-Host "  SonarQube URL : $baseUrl" -ForegroundColor Gray
Write-Host "  SonarQube Port: $port" -ForegroundColor Gray
Write-Host "  Project Key   : $projectKey" -ForegroundColor Gray
Write-Host ""

# 1. 端口检测
Write-Host "--- 端口检测 ---" -ForegroundColor Yellow
$portListening = $false
try {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($conn) { $portListening = $true }
    }
} catch {
    $netstatResult = netstat -ano 2>$null | Select-String ":$port\s" | Select-String "LISTENING"
    if ($netstatResult) { $portListening = $true }
}

if ($portListening) {
    Write-Host "[通过] 端口 $port 正在监听" -ForegroundColor Green
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/api/system/status" -UseBasicParsing -TimeoutSec 10
        $body = $response.Content | ConvertFrom-Json
        Write-Host "[通过] 健康检查: status=$($body.status), version=$($body.version)" -ForegroundColor Green
    } catch {
        Write-Host "[警告] 健康检查失败: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[未通过] 端口 $port 未监听" -ForegroundColor Red
    Write-Host "  请执行: .\start-sonarqube.ps1" -ForegroundColor Yellow
}

Write-Host ""

# 2. 环境变量检查
Write-Host "--- 环境变量检查 ---" -ForegroundColor Yellow
$envVars = @(
    @{ Name = "SONAR_TOKEN"; Required = $true },
    @{ Name = "SONARQUBE_URL"; Required = $false },
    @{ Name = "SONAR_PROJECT_KEY"; Required = $false },
    @{ Name = "JAVA_HOME_SONAR"; Required = $false },
    @{ Name = "SONARQUBE_HOME"; Required = $false },
    @{ Name = "SONAR_SCANNER_HOME"; Required = $false }
)

foreach ($var in $envVars) {
    $val = [Environment]::GetEnvironmentVariable($var.Name)
    if ($val) {
        $display = if ($var.Name -eq "SONAR_TOKEN") { "***已配置***" } else { $val }
        Write-Host "  $($var.Name) : $display" -ForegroundColor Green
    } else {
        $color = if ($var.Required) { "Red" } else { "Yellow" }
        $prefix = if ($var.Required) { "[必需]" } else { "[可选]" }
        Write-Host "  $($var.Name) : $prefix 未设置" -ForegroundColor $color
    }
}

Write-Host ""

# 3. MCP 工具提示
Write-Host "--- MCP 工具验证 ---" -ForegroundColor Yellow
$requiredCapabilities = $cfg.Core.mcp_check.capabilities_required
if ($requiredCapabilities) {
    Write-Host "  技能需要以下 MCP 能力:" -ForegroundColor White
    foreach ($cap in $requiredCapabilities) {
        Write-Host "    - $cap" -ForegroundColor White
    }
}
Write-Host ""
Write-Host "  需在 Agent 中执行以下调用验证:" -ForegroundColor White
Write-Host "    1. Get-SonarProjects" -ForegroundColor White
Write-Host "    2. Get-SonarQualityGate -ProjectKey '$projectKey'" -ForegroundColor White
Write-Host ""
Write-Host "  若 MCP 不可用，使用降级方案:" -ForegroundColor White
Write-Host "    .\run-sonar-scanner.ps1" -ForegroundColor White
Write-Host ""

# 4. 降级扫描器检查
Write-Host "--- 降级扫描器检查 ---" -ForegroundColor Yellow
$scannerHome = Resolve-EnvPlaceholder $cfg.Core.sonar_scanner.scanner_home
if ($scannerHome) {
    $scannerBinRel = $cfg.Core.sonar_scanner.scanner_bin
    if ($scannerBinRel -is [PSCustomObject] -or $scannerBinRel -is [System.Collections.IDictionary]) {
        $scannerBin = $scannerBinRel.windows
    } else {
        $scannerBin = $scannerBinRel
    }
    $scannerFullPath = Join-Path $scannerHome $scannerBin
    if (Test-Path $scannerFullPath) {
        Write-Host "[通过] sonar-scanner 已安装: $scannerFullPath" -ForegroundColor Green
    } else {
        Write-Host "[提示] sonar-scanner 未找到: $scannerFullPath" -ForegroundColor Yellow
    }
} else {
    Write-Host "[提示] SONAR_SCANNER_HOME 未设置" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  验证完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
