# 环境变量占位符解析
# 用途：将字符串中的 ${ENV:VAR_NAME|default} 占位符替换为环境变量值
# 语法：
#   ${ENV:VAR}            - 必需，缺失返回原字符串
#   ${ENV:VAR|default}    - 可选，缺失使用默认值
# 示例：
#   Resolve-EnvPlaceholder "${ENV:SONARQUBE_URL|http://localhost:9000}"
#   → "http://localhost:9000"（当 SONARQUBE_URL 未设置时）

function Resolve-EnvPlaceholder {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, Position = 0)]
        [AllowEmptyString()]
        [string]$Value
    )

    if ([string]::IsNullOrEmpty($Value)) { return $Value }

    # 防止无限循环（虽然不会发生，但稳妥起见）
    $maxIterations = 10
    $iteration = 0

    while ($Value -match '\$\{ENV:([A-Z_]+)(?:\|([^}]*))?\}') {
        $iteration++
        if ($iteration -gt $maxIterations) { break }

        $envVar = $Matches[1]
        $defaultVal = $Matches[2]
        $envValue = [Environment]::GetEnvironmentVariable($envVar)

        # 有默认值且环境变量未设置 → 使用默认值
        if (-not $envValue) { $envValue = $defaultVal }

        if ($envValue) {
            $Value = $Value -replace [regex]::Escape($Matches[0]), $envValue
        } else {
            # 既无环境变量也无默认值 → 保留原占位符（避免数据丢失）
            break
        }
    }

    return $Value
}
