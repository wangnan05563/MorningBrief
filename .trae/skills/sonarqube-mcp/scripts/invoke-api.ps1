# SonarQube API 抽象层
# 用途：统一封装 HTTP API 调用（兼容 MCP 工具不可用场景）
# 入口：. .\scripts\invoke-api.ps1; Invoke-SonarApi -Endpoint ...
# 支持：
#   - Get-SystemStatus
#   - Get-Projects (projectKey)
#   - Search-Issues (params)
#   - Get-QualityGate (projectKey)
#   - Search-SecurityHotspots
#   - Get-Rule (ruleKey)
#   - Get-Measures
#   - Change-IssueStatus
# 通用化设计：
#   - 所有参数从 core_config.json 加载
#   - Token 强制从环境变量读取
#   - 支持分页（自动累积）
#   - 统一错误处理与日志

[CmdletBinding()]
param(
    [string]$CoreConfigPath = "$PSScriptRoot\..\config\core_config.json"
)

# ========== 加载共享库（依赖：env-resolver, config-loader, logging）==========
$LibPath = Join-Path $PSScriptRoot "lib\lib.ps1"
. $LibPath

# ========== 加载配置 ==========
if (-not (Test-Path $CoreConfigPath)) {
    throw "核心配置文件不存在: $CoreConfigPath"
}
$CoreConfig = Get-Content $CoreConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

# ========== 获取 SonarQube 连接信息 ==========
$Script:Host = Resolve-EnvPlaceholder $CoreConfig.sonarqube_server.host
$Script:Port = [int](Resolve-EnvPlaceholder $CoreConfig.sonarqube_server.port)
$Script:Token = [Environment]::GetEnvironmentVariable("SONAR_TOKEN")
$Script:BaseUrl = if ($Script:Host -match "^https?://") {
    "$($Script:Host.TrimEnd('/'))"
} else {
    "http://$($Script:Host):$Script:Port"
}

# 默认 API 调用参数（从配置加载，可被 param 覆盖）
$Script:DefaultTimeoutSec = if ($CoreConfig.api_defaults -and $CoreConfig.api_defaults.timeout_seconds) {
    [int]$CoreConfig.api_defaults.timeout_seconds
} else { 30 }

$Script:DefaultPageSize = if ($CoreConfig.api_defaults -and $CoreConfig.api_defaults.page_size) {
    [int]$CoreConfig.api_defaults.page_size
} else { 500 }

# API 端点路径（从配置加载，支持自定义 SonarQube 部署）
$Script:ApiEndpoints = @{
    system_status      = "/api/system/status"
    projects_search    = "/api/projects/search"
    issues_search      = "/api/issues/search"
    issues_transition  = "/api/issues/do_transition"
    qualitygates_status = "/api/qualitygates/project_status"
    rules_show         = "/api/rules/show"
    measures_component = "/api/measures/component"
}
if ($CoreConfig.api_endpoints) {
    foreach ($prop in $CoreConfig.api_endpoints.PSObject.Properties) {
        $Script:ApiEndpoints[$prop.Name] = $prop.Value
    }
}

# 问题状态变更的可选值（从配置加载）
$Script:IssueStatusValues = if ($CoreConfig.api_defaults -and $CoreConfig.api_defaults.issue_statuses) {
    $CoreConfig.api_defaults.issue_statuses
} else { @("falsepositive", "accept", "reopen", "resolve", "confirm") }

if ([string]::IsNullOrEmpty($Script:Token)) {
    Write-Warn "[Invoke-SonarApi] SONAR_TOKEN 环境变量未设置，API 调用将失败"
}

# ========== 通用 API 调用函数 ==========
function Invoke-SonarApi {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Endpoint,

        [Parameter(Mandatory = $false)]
        [hashtable]$QueryParams = @{},

        [Parameter(Mandatory = $false)]
        [ValidateSet("GET", "POST")]
        [string]$Method = "GET",

        [Parameter(Mandatory = $false)]
        [int]$TimeoutSec = $Script:DefaultTimeoutSec
    )

    $url = "$Script:BaseUrl$Endpoint"
    if ($QueryParams.Count -gt 0) {
        $qs = ($QueryParams.GetEnumerator() | ForEach-Object {
            "$([uri]::EscapeDataString($_.Key))=$([uri]::EscapeDataString($_.Value.ToString()))"
        }) -join "&"
        $url = "$url`?$qs"
    }

    $headers = @{
        "Authorization" = "Bearer $Script:Token"
        "Accept" = "application/json"
    }

    try {
        $response = Invoke-WebRequest -Uri $url -Headers $headers -Method $Method -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return $response.Content | ConvertFrom-Json
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $errorBody = ""
        try { $errorBody = $_.Exception.Response.GetResponseStream() | ForEach-Object { [System.IO.StreamReader]::new($_).ReadToEnd() } } catch {}
        throw "API 调用失败 [$Method $url] (HTTP $statusCode): $errorBody"
    }
}

# ========== 业务封装函数 ==========

function Get-SonarSystemStatus {
    return Invoke-SonarApi -Endpoint $Script:ApiEndpoints.system_status
}

function Get-SonarProjects {
    param([string]$ProjectKey = "")
    $params = @{}
    if ($ProjectKey) { $params["projects"] = $ProjectKey }
    return Invoke-SonarApi -Endpoint $Script:ApiEndpoints.projects_search -QueryParams $params
}

function Search-SonarIssues {
    [CmdletBinding()]
    param(
        [string[]]$Projects = @(),
        [string[]]$Severities = @(),
        [string[]]$Types = @(),
        [string[]]$Statuses = @(),
        [string[]]$Files = @(),
        [string]$RuleKey = "",
        [int]$Page = 1,
        [int]$PageSize = $Script:DefaultPageSize,
        [string[]]$Facets = @()
    )

    $params = @{
        "p" = $Page
        "ps" = $PageSize
    }
    if ($Projects) { $params["componentKeys"] = $Projects -join "," }
    if ($Severities) { $params["severities"] = $Severities -join "," }
    if ($Types) { $params["types"] = $Types -join "," }
    if ($Statuses) { $params["issueStatuses"] = $Statuses -join "," }
    if ($Files) { $params["files"] = $Files -join "," }
    if ($RuleKey) { $params["rules"] = $RuleKey }
    if ($Facets) { $params["facets"] = $Facets -join "," }

    return Invoke-SonarApi -Endpoint $Script:ApiEndpoints.issues_search -QueryParams $params
}

function Search-SonarIssuesAll {
    [CmdletBinding()]
    param(
        [string[]]$Projects = @(),
        [string[]]$Severities = @(),
        [string[]]$Types = @(),
        [string[]]$Statuses = @(),
        [int]$PageSize = $Script:DefaultPageSize
    )

    $allIssues = @()
    $page = 1
    do {
        $result = Search-SonarIssues -Projects $Projects -Severities $Severities -Types $Types -Statuses $Statuses -Page $page -PageSize $PageSize
        $allIssues += $result.issues
        $hasNext = $result.paging.hasNextPage
        $page++
    } while ($hasNext)

    return $allIssues
}

function Get-SonarQualityGate {
    param([Parameter(Mandatory = $true)][string]$ProjectKey)
    return Invoke-SonarApi -Endpoint $Script:ApiEndpoints.qualitygates_status -QueryParams @{ "projectKey" = $ProjectKey }
}

function Get-SonarRule {
    param([Parameter(Mandatory = $true)][string]$RuleKey)
    return Invoke-SonarApi -Endpoint $Script:ApiEndpoints.rules_show -QueryParams @{ "key" = $RuleKey }
}

function Get-SonarMeasures {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectKey,
        [Parameter(Mandatory = $true)][string[]]$MetricKeys
    )
    return Invoke-SonarApi -Endpoint $Script:ApiEndpoints.measures_component -QueryParams @{
        "component" = $ProjectKey
        "metricKeys" = $MetricKeys -join ","
    }
}

function Change-SonarIssueStatus {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$IssueKey,
        [Parameter(Mandatory = $true)][string]$Status,
        [string]$Comment = ""
    )

    # ValidateSet 必须使用字面量，因此改为运行时校验
    # 合法值在 $Script:IssueStatusValues 中定义（可从 core_config.json -> api_defaults.issue_statuses 覆盖）
    if ($Script:IssueStatusValues -notcontains $Status) {
        $valid = $Script:IssueStatusValues -join ", "
        throw "无效的问题状态: '$Status'。合法值: $valid"
    }

    $body = @{
        "issue" = $IssueKey
        "transition" = $Status
    }
    if ($Comment) { $body["comment"] = $Comment }

    return Invoke-SonarApi -Endpoint $Script:ApiEndpoints.issues_transition -Method "POST" -QueryParams $body
}

# ========== 导出 ==========
# 注意：invoke-api.ps1 既可通过 dot-source 加载（普通 .ps1），
# 也可被另一个脚本 import-module（需要 Export-ModuleMember）。
# 为兼容性，dot-source 模式下此语句会被自动忽略（PowerShell 5+ 检测机制）。
if ($MyInvocation.InvocationName -ne "." -and $MyInvocation.MyCommand.Path -like "*.psm1") {
    Export-ModuleMember -Function `
        Invoke-SonarApi, `
        Get-SonarSystemStatus, `
        Get-SonarProjects, `
        Search-SonarIssues, `
        Search-SonarIssuesAll, `
        Get-SonarQualityGate, `
        Get-SonarRule, `
        Get-SonarMeasures, `
        Change-SonarIssueStatus
}
