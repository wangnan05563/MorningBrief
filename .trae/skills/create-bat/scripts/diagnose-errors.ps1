<#
.SYNOPSIS
    通用脚本错误诊断器 - create-bat 技能组件
.DESCRIPTION
    根据 config.json 中配置的诊断规则，匹配错误信息并提供修复建议。
    所有诊断规则从配置读取，无硬编码。
.PARAMETER ConfigFile
    配置文件路径
.PARAMETER ErrorOutput
    错误输出文本
.EXAMPLE
    .\diagnose-errors.ps1 -ConfigFile config.json -ErrorOutput "script is not recognized"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$ConfigFile,
    [Parameter(Mandatory=$true, Position=0)]
    [string]$ErrorOutput
)

$ErrorActionPreference = "SilentlyContinue"

# ---- 加载配置 ----
$config = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json

# ---- 匹配诊断规则 ----
$matches = @()
if ($config.diagnoses) {
    foreach ($rule in $config.diagnoses) {
        $pattern = $rule.pattern
        if ($ErrorOutput -match [regex]::Escape($pattern) -or $ErrorOutput -like "*$pattern*") {
            $matches += $rule
        }
    }
}

# ---- 输出结果 ----
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  错误诊断器 (create-bat)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($matches.Count -eq 0) {
    Write-Host "  未匹配到已知诊断规则" -ForegroundColor Yellow
    Write-Host "  可在 config.json 的 diagnoses 数组中添加新规则" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

foreach ($m in $matches) {
    Write-Host "--- 匹配诊断: $($m.name) ---" -ForegroundColor Yellow
    if ($m.category) { Write-Host "  分类:   $($m.category)" -ForegroundColor DarkGray }
    if ($m.fix)     { Write-Host "  修复:   $($m.fix)" -ForegroundColor Green }
    if ($m.steps) {
        Write-Host "  步骤:" -ForegroundColor DarkCyan
        $i = 1
        foreach ($step in $m.steps) {
            Write-Host "    $i. $step" -ForegroundColor DarkGray
            $i++
        }
    }
    Write-Host ""
}

exit 0
