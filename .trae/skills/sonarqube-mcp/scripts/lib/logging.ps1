# 统一日志输出
# 用途：所有 SonarQube MCP 脚本使用统一的日志格式
# 格式：[LEVEL] message
# 颜色：INFO=青色，OK=绿色，WARN=黄色，ERROR=红色

function Write-Step {
    param([Parameter(Mandatory = $true, Position = 0)][string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([Parameter(Mandatory = $true, Position = 0)][string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([Parameter(Mandatory = $true, Position = 0)][string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([Parameter(Mandatory = $true, Position = 0)][string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# 状态标记（用于状态报告）
function Write-Status {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value,
        [ValidateSet("ok", "warn", "err", "info")]
        [string]$Level = "info"
    )
    $color = switch ($Level) {
        "ok" { "Green" }
        "warn" { "Yellow" }
        "err" { "Red" }
        default { "White" }
    }
    $prefix = switch ($Level) {
        "ok" { "[通过]" }
        "warn" { "[警告]" }
        "err" { "[未通过]" }
        default { "[信息]" }
    }
    Write-Host "  $prefix $Name : $Value" -ForegroundColor $color
}
