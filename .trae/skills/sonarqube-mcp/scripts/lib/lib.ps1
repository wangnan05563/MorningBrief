# SonarQube MCP - 共享脚本库入口
# 用途：通过 . $PSScriptRoot\lib.ps1 一次性加载所有共享函数
# 提供的函数：
#   - Resolve-EnvPlaceholder : 解析 ${ENV:VAR|default} 占位符
#   - Load-SonarConfig       : 加载 v1/v2 配置（含兼容层）
#   - Get-ConfigValue        : 安全获取配置值（带默认值）
#   - Write-Step/Write-Success/Write-Warn/Write-Err : 统一日志
#   - Test-IsConfigLoaded    : 验证配置已加载

[CmdletBinding()]
param()

$LibRoot = $PSScriptRoot

# 按依赖顺序加载（env-resolver 独立，config-loader 依赖 env-resolver，logging 独立，platform 独立）
. (Join-Path $LibRoot "env-resolver.ps1")
. (Join-Path $LibRoot "logging.ps1")
. (Join-Path $LibRoot "config-loader.ps1")
. (Join-Path $LibRoot "..\detect-platform.ps1")
# 注意：dot-source 加载的脚本不支持 Export-ModuleMember（仅 .psm1 模块支持）
# 所有函数在 dot-source 时已自动注入调用方作用域，无需额外导出
