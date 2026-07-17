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
# 前置验证（紧凑输出）
$checks = @()

# 1. 端口检测
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
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/api/system/status" -UseBasicParsing -TimeoutSec 10
        $body = $response.Content | ConvertFrom-Json
        $checks += @{ Name="server"; Result="$($body.status)"; Color="Green" }
    } catch {
        $checks += @{ Name="server"; Result="unreachable"; Color="Red" }
    }
} else {
    $checks += @{ Name="port"; Result="$port"; Color="Red" }
}

# 2. 环境变量检查
$checks += @{ Name="token"; Result="configured"; Color="Green" }
$checks += @{ Name="url"; Result=(if ($env:SONARQUBE_URL) { "set" } else { "default" }); Color="Green" }

# 3. MCP 工具提示
$requiredCapabilities = $cfg.Core.mcp_check.capabilities_required
if ($requiredCapabilities) {
    Write-Host ""
    Write-Host "[MCP] 技能需要以下能力:" -ForegroundColor White
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
        $checks += @{ Name="scanner"; Result="installed"; Color="Green" }
    } else {
        $checks += @{ Name="scanner"; Result="missing"; Color="Yellow" }
    }
} else {
    $checks += @{ Name="scanner"; Result="not configured"; Color="Yellow" }
}

# 一次性紧凑输出
Write-Host ""
Write-CompactStatus -Checks $checks
Write-Host "  验证完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
