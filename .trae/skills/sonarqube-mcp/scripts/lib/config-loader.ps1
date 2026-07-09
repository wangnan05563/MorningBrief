# SonarQube MCP 配置加载器
# 用途：统一加载 core_config.json (v2) 和 project_config.json
#       自动降级兼容旧版 scan_config.json (v1)
# 返回：hashtable { Core, Project, Source }

# 默认配置路径（可通过 param 覆盖）
$Script:DefaultCoreConfigPath = "$PSScriptRoot\..\..\config\core_config.json"
$Script:DefaultProjectConfigPath = "$PSScriptRoot\..\..\config\project_config.json"
$Script:DefaultLegacyConfigPath = "$PSScriptRoot\..\..\config\scan_config.json"

function Load-SonarConfig {
    [CmdletBinding()]
    param(
        [string]$CoreConfigPath = $Script:DefaultCoreConfigPath,
        [string]$ProjectConfigPath = $Script:DefaultProjectConfigPath,
        [string]$LegacyConfigPath = $Script:DefaultLegacyConfigPath
    )

    # 优先 v2 配置（core + project 分层）
    if (Test-Path $CoreConfigPath) {
        $core = Get-Content $CoreConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $project = $null
        if (Test-Path $ProjectConfigPath) {
            $project = Get-Content $ProjectConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } else {
            Write-Warn "未找到项目配置: $ProjectConfigPath（将仅使用 core_config.json 通用配置）"
        }
        return @{
            Core    = $core
            Project = $project
            Source  = "v2 (core+project)"
        }
    }

    # 降级到 v1（scan_config.json 兼容）
    if (Test-Path $LegacyConfigPath) {
        Write-Warn "检测到旧版配置 scan_config.json，建议升级到分层配置（core_config.json + project_config.json）"
        $legacy = Get-Content $LegacyConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        return @{
            Core    = $legacy
            Project = $null
            Source  = "v1 (legacy)"
        }
    }

    throw "未找到任何配置文件。请创建 $CoreConfigPath 或使用旧版 $LegacyConfigPath"
}

# 安全获取配置值（支持嵌套路径，如 "sonarqube_server.host"）
function Get-ConfigValue {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Config,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $false)][object]$Default = $null
    )

    if (-not $Config) { return $Default }

    $parts = $Path -split '\.'
    $current = $Config
    foreach ($part in $parts) {
        if ($null -eq $current) { return $Default }
        if ($current -is [PSCustomObject] -or $current -is [hashtable]) {
            if ($current.PSObject.Properties[$part]) {
                $current = $current.PSObject.Properties[$part].Value
            } else {
                return $Default
            }
        } else {
            return $Default
        }
    }

    if ($null -eq $current) { return $Default }
    return $current
}

# 验证配置已加载（用于子函数前置检查）
function Test-IsConfigLoaded {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Config
    )
    return ($null -ne $Config) -and ($Config.PSObject.Properties.Count -gt 0)
}
