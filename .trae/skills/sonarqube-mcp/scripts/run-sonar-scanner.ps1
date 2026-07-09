# SonarQube Scanner 降级扫描脚本（v2.0 通用化）
# 用途：MCP 不可用时使用 sonar-scanner 命令行工具
# 配置：自动检测 config/core_config.json（v2.0）或 config/scan_config.json（v1.0 兼容）
# 跨平台：Windows/Linux/macOS

[CmdletBinding()]
param(
    [string]$ProjectKey = "",
    [string]$ProjectName = "",
    [string]$Sources = "",
    [int]$WaitTimeout = 0,
    [string]$CoreConfigPath = "$PSScriptRoot\..\config\core_config.json",
    [string]$ProjectConfigPath = "$PSScriptRoot\..\config\project_config.json",
    [string]$LegacyConfigPath = "$PSScriptRoot\..\config\scan_config.json"
)

# ========== 加载共享库（依赖：env-resolver, config-loader, logging, platform）==========
$LibPath = Join-Path $PSScriptRoot "lib\lib.ps1"
. $LibPath

$Platform = Get-Platform

# ========== 加载配置 ==========
$cfg = Load-SonarConfig -CoreConfigPath $CoreConfigPath -ProjectConfigPath $ProjectConfigPath -LegacyConfigPath $LegacyConfigPath
$CoreCfg = $cfg.Core
$ProjectCfg = $cfg.Project

# ========== 解析配置 ==========
$ScannerHome = Resolve-EnvPlaceholder $CoreCfg.sonar_scanner.scanner_home
$ScannerBinRel = $CoreCfg.sonar_scanner.scanner_bin
if ($ScannerBinRel -is [PSCustomObject] -or $ScannerBinRel -is [System.Collections.IDictionary]) {
    $ScannerBinRel = $ScannerBinRel.$($Platform.OS)
}
$ScannerBin = Join-Path $ScannerHome $ScannerBinRel

$Host = Resolve-EnvPlaceholder $CoreCfg.sonarqube_server.host
$Port = [int](Resolve-EnvPlaceholder $CoreCfg.sonarqube_server.port)
$BaseUrl = if ($Host -match "^https?://") { $Host.TrimEnd('/') } else { "http://$Host`:$Port" }

# 参数回退
if (-not $ProjectKey) {
    $ProjectKey = if ($ProjectCfg -and $ProjectCfg.project.key) {
        Resolve-EnvPlaceholder $ProjectCfg.project.key
    } elseif ($CoreCfg.sonar_scanner.default_project_key) {
        $CoreCfg.sonar_scanner.default_project_key
    } elseif ($CoreCfg.project.key) {
        $CoreCfg.project.key
    } else { "" }
}

if (-not $ProjectName) {
    $ProjectName = if ($ProjectCfg -and $ProjectCfg.project.name) { $ProjectCfg.project.name } else { "Default Project" }
}

if (-not $Sources) {
    $Sources = $CoreCfg.sonar_scanner.default_sources
    if (-not $Sources) { $Sources = "." }
}

if ($WaitTimeout -eq 0) {
    $WaitTimeout = $CoreCfg.sonar_scanner.wait_timeout_seconds
    if (-not $WaitTimeout) { $WaitTimeout = 300 }
}

# ========== Token 验证 ==========
$SonarToken = [Environment]::GetEnvironmentVariable("SONAR_TOKEN")
if ([string]::IsNullOrEmpty($SonarToken)) {
    Write-Error "SONAR_TOKEN 环境变量未设置"
    Write-Host "请在 SonarQube Web 界面生成 Token 并设置环境变量:" -ForegroundColor Yellow
    Write-Host "  1. 打开 $BaseUrl" -ForegroundColor White
    Write-Host "  2. 登录后点击右上角头像 -> My Account -> Security" -ForegroundColor White
    Write-Host "  3. 生成 Global Analysis Token" -ForegroundColor White
    Write-Host "  4. 设置环境变量: `$env:SONAR_TOKEN = 'squ_xxxxxxxx'" -ForegroundColor White
    exit 1
}

# ========== 验证服务状态 ==========
Write-Host "验证 SonarQube 服务状态..." -ForegroundColor Cyan
try {
    $Response = Invoke-WebRequest -Uri "$BaseUrl/api/system/status" -UseBasicParsing -TimeoutSec 10
    $Status = ($Response.Content | ConvertFrom-Json).status
    if ($Status -ne "UP") {
        Write-Error "SonarQube 服务状态异常: $Status"
        exit 1
    }
    Write-Host "[OK] SonarQube 服务状态: $Status" -ForegroundColor Green
} catch {
    Write-Error "无法连接 SonarQube 服务: $BaseUrl"
    Write-Host "请先执行: .\start-sonarqube.ps1" -ForegroundColor Yellow
    exit 1
}

# ========== 验证扫描器 ==========
if (-not (Test-Path $ScannerBin)) {
    Write-Error "sonar-scanner 工具不存在: $ScannerBin"
    Write-Host "请安装 sonar-scanner 并设置环境变量 SONAR_SCANNER_HOME" -ForegroundColor Yellow
    exit 1
}

# ========== 生成 sonar-project.properties ==========
$SkillRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Join-Path $SkillRoot "..\..\.."
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$PropertiesFile = Join-Path $ProjectRoot "sonar-project.properties"

# 收集排除项（兼容 v1 和 v2）
$Excludes = @()
if ($ProjectCfg -and $ProjectCfg.modules) {
    foreach ($module in $ProjectCfg.modules.PSObject.Properties.Value) {
        if ($module.exclude) {
            foreach ($ex in $module.exclude) {
                $Excludes += "**/$ex/**"
            }
        }
    }
}
if ($CoreCfg.filters -and $CoreCfg.filters.ignore_paths) {
    foreach ($path in $CoreCfg.filters.ignore_paths) {
        $Excludes += $path
    }
}
$Excludes = $Excludes | Select-Object -Unique
$ExcludesStr = $Excludes -join ","

$Languages = if ($CoreCfg.scan.languages) { $CoreCfg.scan.languages -join "," } else { "python,typescript" }

$PropertiesContent = @"
# SonarQube 项目配置 - 自动生成（v2.0 通用化）
sonar.projectKey=$ProjectKey
sonar.projectName=$ProjectName
sonar.sources=$Sources
sonar.host.url=$BaseUrl
sonar.token=$SonarToken
sonar.exclusions=$ExcludesStr
sonar.languages=$Languages
sonar.sourceEncoding=UTF-8
"@

Set-Content -Path $PropertiesFile -Value $PropertiesContent -Encoding UTF8
Write-Host "[OK] 生成扫描配置: $PropertiesFile" -ForegroundColor Green

# ========== 执行扫描 ==========
Write-Host "执行 SonarQube 扫描..." -ForegroundColor Cyan
Write-Host "  平台 : $($Platform.OS)" -ForegroundColor Gray
Write-Host "  项目 : $ProjectKey" -ForegroundColor Gray
Write-Host "  源码 : $Sources" -ForegroundColor Gray
Write-Host "  服务 : $BaseUrl" -ForegroundColor Gray
Write-Host "  工具 : $ScannerBin" -ForegroundColor Gray

Push-Location $ProjectRoot
try {
    $Process = Start-Process -FilePath $ScannerBin -Wait -NoNewWindow -PassThru
    if ($Process.ExitCode -ne 0) {
        Write-Error "扫描执行失败，退出码: $($Process.ExitCode)"
        Pop-Location
        exit 1
    }
} catch {
    Write-Error "扫描执行异常: $_"
    Pop-Location
    exit 1
}
Pop-Location

# ========== 验证结果 ==========
Write-Host "验证扫描结果..." -ForegroundColor Cyan
$ProjectsUrl = "$BaseUrl/api/projects/search?projects=$ProjectKey"
try {
    $Response = Invoke-WebRequest -Uri $ProjectsUrl -Headers @{Authorization="Bearer $SonarToken"} -UseBasicParsing -TimeoutSec 10
    $Projects = ($Response.Content | ConvertFrom-Json).projects
    if ($Projects.Count -eq 0) {
        Write-Error "扫描结果未上传到 SonarQube"
        exit 1
    }
    Write-Host "[OK] 扫描成功完成！" -ForegroundColor Green
} catch {
    Write-Error "无法验证扫描结果: $_"
    exit 1
}

# ========== 质量门禁 ==========
Write-Host "获取质量门禁状态..." -ForegroundColor Cyan
$QualityGateUrl = "$BaseUrl/api/qualitygates/project_status?projectKey=$ProjectKey"
try {
    $Response = Invoke-WebRequest -Uri $QualityGateUrl -Headers @{Authorization="Bearer $SonarToken"} -UseBasicParsing -TimeoutSec 10
    $GateStatus = ($Response.Content | ConvertFrom-Json).projectStatus.status
    Write-Host "[OK] 质量门禁状态: $GateStatus" -ForegroundColor Green
} catch {
    Write-Warning "无法获取质量门禁状态: $_"
}

# ========== MCP 配置建议 ==========
Write-Host ""
Write-Host "### MCP 配置建议" -ForegroundColor Yellow
Write-Host "当前使用 sonar-scanner 命令行工具作为降级方案。" -ForegroundColor White
Write-Host "建议配置 SonarQube MCP 以获得更好的集成体验。" -ForegroundColor White

exit 0
