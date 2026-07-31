<#
.SYNOPSIS
    auto-scan 公共逻辑模块

.DESCRIPTION
    设计目标（为什么单独抽取）：
    - frontend 与 backend 的 auto-scan.ps1 重复度 80%+，维护成本高
    - 提取公共逻辑到模块，各技能脚本瘦身为薄壳（Import-Module + 调用）
    - 统一报告格式、错误处理、路径定位逻辑

.NOTES
    各技能 auto-scan.ps1 预期行数：
    - frontend: 242 → ~60 行
    - backend: 448 → ~80 行
#>

function Get-ProjectRoot {
    <#
    .SYNOPSIS
        上溯 N 层定位项目根目录（寻找 .git 或 backend/app 目录）
    .PARAMETER MaxLevels
        最大上溯层数，默认 5
    #>
    param([int]$MaxLevels = 5)
    $dir = Get-Location
    for ($i = 0; $i -lt $MaxLevels; $i++) {
        if ((Test-Path (Join-Path $dir ".git")) -or (Test-Path (Join-Path $dir "backend\app"))) {
            return $dir
        }
        $dir = Split-Path $dir -Parent
        if (-not $dir) { break }
    }
    throw "无法定位项目根目录（已上溯 $MaxLevels 层）"
}

function Invoke-GrepCheck {
    <#
    .SYNOPSIS
        通用 grep 检查（Pattern/Path/RuleName/Severity → Issue 对象）
    .PARAMETER Pattern
        正则表达式模式
    .PARAMETER Path
        搜索路径（支持通配符）
    .PARAMETER RuleName
        规则名称，用于报告标识
    .PARAMETER Severity
        严重级别，默认 "HIGH"
    #>
    param(
        [string]$Pattern,
        [string]$Path,
        [string]$RuleName,
        [string]$Severity = "HIGH"
    )
    # 为什么用 Select-String 而非 grep.exe——跨平台兼容，免外部依赖
    $matches = Select-String -Path $Path -Pattern $Pattern -AllMatches -ErrorAction SilentlyContinue
    if ($matches) {
        $uniqueFiles = $matches | Select-Object -ExpandProperty Path | Select-Object -Unique
        return @{
            RuleName  = $RuleName
            Severity  = $Severity
            Files     = @($uniqueFiles)
            MatchCount = $matches.Count
        }
    }
    return $null
}

function Write-ScanReport {
    <#
    .SYNOPSIS
        统一报告格式输出
    .PARAMETER Issues
        由 Invoke-GrepCheck 返回的 Issue 对象数组
    .PARAMETER OutputPath
        输出 Markdown 文件路径
    #>
    param(
        [array]$Issues,
        [string]$OutputPath
    )
    # 为什么用简单 Markdown 而非 JSON——人类可读优先，工具解析可通过子函数扩展
    $lines = @(
        "# 扫描报告",
        "",
        "| 规则 | 严重度 | 文件数 | 匹配数 |",
        "|------|--------|--------|--------|"
    )
    foreach ($issue in $Issues) {
        $fileCount = if ($issue.Files) { $issue.Files.Count } else { 0 }
        $lines += "| $($issue.RuleName) | $($issue.Severity) | $fileCount | $($issue.MatchCount) |"
    }
    $lines -join "`n" | Out-File -FilePath $OutputPath -Encoding UTF8
}

Export-ModuleMember -Function Get-ProjectRoot, Invoke-GrepCheck, Write-ScanReport