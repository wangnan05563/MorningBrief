<#
.SYNOPSIS
    Token 审计脚本：扫描 skills 目录下所有技能的 token 使用情况，识别膨胀点。

.DESCRIPTION
    设计目标（为什么这么做）：
    - 守门 SKILL.md ≤500 行规范，防止复盘内容污染能力指令文件
    - 量化 token 消耗，为优化决策提供数据支撑
    - 自动化检测孤儿 references、未删除复盘段、链式引用等问题
    - 全参数化，无硬编码，适配不同项目结构

.PARAMETER SkillsRoot
    skills 根目录路径。默认为脚本所在 _shared 的上级目录。

.PARAMETER SkillNames
    指定扫描的技能名列表。空则扫描 SkillsRoot 下所有 news-* 子目录。

.PARAMETER SkillMdLineThreshold
    SKILL.md 行数告警阈值，默认 500（按 Skill 架构规范）。

.PARAMETER OutputDir
    报告输出目录（相对 SkillsRoot），默认 audit-reports。

.PARAMETER CompareBudget
    对比每技能的 .token-budget.json 预算声明，输出超预算告警。

.PARAMETER DetectOrphans
    检测孤儿 references 文件（存在但 SKILL.md 未引用）。

.PARAMETER DetectRetrospectives
    检测 SKILL.md 中未删除的复盘类章节。

.PARAMETER DetectChain
    检测 _shared/references/ 中的链式引用（禁止反向引用技能专属、禁止互相引用）。

.EXAMPLE
    pwsh token-audit.ps1 -CompareBudget -DetectOrphans -DetectRetrospectives
    全面审计并输出报告。

.EXAMPLE
    pwsh token-audit.ps1 -SkillNames news-code-dev -CompareBudget
    仅审计单个技能。

.NOTES
    退出码：0=全通过 / 1=有 WARN / 2=有 ERROR
    编码：UTF-8 with BOM + CRLF（按 project_memory.md 约束）
#>

param(
    [string]$SkillsRoot = (Resolve-Path (Join-Path (Join-Path $PSScriptRoot "..") "..")).Path,
    [string[]]$SkillNames = @(),
    [int]$SkillMdLineThreshold = 500,
    [string]$OutputDir = "audit-reports",
    [switch]$CompareBudget,
    [switch]$DetectOrphans,
    [switch]$DetectRetrospectives,
    [switch]$DetectChain
)

# 控制台编码设置：为什么用 chcp + Console 双设置——避免中文输出乱码
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

# Token 估算系数：中英混合内容经验值（chars / 2.2）
# 为什么用 2.2：中文 1 字符约 1-2 token，英文 4 char/token，混合取中间偏保守值
$script:TokenRatio = 2.2

# 复盘类章节识别正则：为什么包含这些关键词——覆盖所有已知反模式标题
$script:RetrospectivePattern = '^(#{2,3})\s.*(复盘|retrospect|四维度|补充章节.*v\d|配置节点速查|测试流程优化总结|v\d\.\d.*复盘)'

# ===== 工具函数 =====

function Get-EstTokens {
    # 估算 token 数：字符数 / 经验系数
    param([string]$Text)
    if (-not $Text) { return 0 }
    return [int]([math]::Ceiling($Text.Length / $script:TokenRatio))
}

function Get-FileStats {
    # 统计单文件行数、字符数、估算 token
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return @{ Lines = 0; Chars = 0; EstTokens = 0; Exists = $false }
    }
    $content = Get-Content -Path $Path -Raw -Encoding UTF8
    if ($null -eq $content) { $content = "" }
    $lines = (Get-Content -Path $Path -Encoding UTF8 | Measure-Object -Line).Lines
    return @{
        Lines     = $lines
        Chars     = $content.Length
        EstTokens = Get-EstTokens -Text $content
        Exists    = $true
    }
}

function Find-RetrospectiveSections {
    # 在 SKILL.md 中识别复盘类章节，返回章节列表（标题、行号）
    param([string]$SkillMdPath)
    if (-not (Test-Path $SkillMdPath)) { return @() }
    $lines = Get-Content -Path $SkillMdPath -Encoding UTF8
    $sections = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $script:RetrospectivePattern) {
            $sections += @{
                Line    = $i + 1
                Title   = $lines[$i].Trim()
                Level   = $Matches[1]
            }
        }
    }
    return $sections
}

function Find-OrphanReferences {
    # 检测 references/ 下存在但 SKILL.md 未引用的文件
    param([string]$SkillDir, [string]$SkillMdContent)
    $refDir = Join-Path $SkillDir "references"
    if (-not (Test-Path $refDir)) { return @() }
    $orphans = @()
    Get-ChildItem -Path $refDir -Recurse -File -Filter "*.md" | ForEach-Object {
        # 为什么用文件名匹配而非完整路径——SKILL.md 引用方式可能是相对路径或文件名
        $fileName = $_.Name
        $relPath = $_.FullName.Substring($SkillDir.Length + 1) -replace "\\", "/"
        if ($SkillMdContent -notmatch [regex]::Escape($fileName) -and $SkillMdContent -notmatch [regex]::Escape($relPath)) {
            $orphans += $relPath
        }
    }
    return $orphans
}

function Read-Budget {
    # 读取技能的 .token-budget.json
    param([string]$SkillDir)
    $budgetPath = Join-Path $SkillDir ".token-budget.json"
    if (-not (Test-Path $budgetPath)) { return $null }
    try {
        $raw = Get-Content -Path $budgetPath -Raw -Encoding UTF8
        return $raw | ConvertFrom-Json
    } catch {
        Write-Warning "预算文件解析失败: $budgetPath - $_"
        return $null
    }
}

function Find-ChainReferences {
    # 检测 _shared/references/ 中的链式引用
    # 为什么禁止链式——避免 A→_shared→B 导致 token 爆炸和循环依赖
    # 为什么排除 README.md——索引文件天然需要链接其他文件
    # 为什么排除来源/归属行——"来源：xxx" 与 "../news-" 是文档归因而非依赖链
    param([string]$SharedRefDir)
    if (-not (Test-Path $SharedRefDir)) { return @() }
    $violations = @()
    Get-ChildItem -Path $SharedRefDir -Recurse -File -Filter "*.md" | ForEach-Object {
        $content = Get-Content -Path $_.FullName -Raw -Encoding UTF8
        $fileName = $_.Name
        # 检测反向引用技能专属（../news-），排除来源/归属行
        $lines = $content -split "`n"
        foreach ($line in $lines) {
            if ($line -match '\.\./news-' -and $line -notmatch '^[>\s]*(来源|原技能|关联|相关规范|参考)') {
                $violations += @{
                    File   = $fileName
                    Type   = "反向引用技能专属"
                    Detail = "检测到非来源行的 ../news- 路径引用: $($line.Trim().Substring(0, [Math]::Min(60, $line.Trim().Length)))"
                }
                break
            }
        }
        # 检测 _shared 内部互相引用（排除自身和 README.md 索引文件）
        if ($fileName -ne "README.md") {
            Get-ChildItem -Path $SharedRefDir -File -Filter "*.md" | ForEach-Object {
                $other = $_.Name
                if ($other -ne $fileName -and $other -ne "README.md" -and $content -match [regex]::Escape($other)) {
                    $violations += @{
                        File   = $fileName
                        Type   = "_shared 内部互相引用"
                        Detail = "引用了 $other"
                    }
                }
            }
        }
    }
    return $violations
}

# ===== 主扫描逻辑 =====

$scanDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$scanDateStamp = Get-Date -Format "yyyy-MM-dd"

# 确定扫描目标
if ($SkillNames.Count -eq 0) {
    $targetSkills = Get-ChildItem -Path $SkillsRoot -Directory |
        Where-Object { $_.Name -match "^news-" } |
        Select-Object -ExpandProperty Name
} else {
    $targetSkills = $SkillNames
}

if ($targetSkills.Count -eq 0) {
    Write-Host "未找到任何 news-* 技能目录于: $SkillsRoot" -ForegroundColor Yellow
    exit 1
}

$results = @()
$violations = @()

foreach ($skillName in $targetSkills) {
    $skillDir = Join-Path $SkillsRoot $skillName
    if (-not (Test-Path (Join-Path $skillDir "SKILL.md"))) {
        Write-Warning "跳过 $skillName：无 SKILL.md"
        continue
    }

    # 扫描 SKILL.md
    $skillMdPath = Join-Path $skillDir "SKILL.md"
    $skillMdStats = Get-FileStats -Path $skillMdPath
    $skillMdContent = if ($skillMdStats.Exists) { Get-Content -Path $skillMdPath -Raw -Encoding UTF8 } else { "" }

    # 扫描 config 文件（yaml 或 json）
    $configPath = $null
    $configStats = @{ Lines = 0; Chars = 0; EstTokens = 0; Exists = $false }
    foreach ($cfgName in @("config.yaml", "config\project-config.json", "config.json")) {
        $candidate = Join-Path $skillDir $cfgName
        if (Test-Path $candidate) {
            $configPath = $candidate
            $configStats = Get-FileStats -Path $candidate
            break
        }
    }

    # 扫描 references 目录总行数
    $refDir = Join-Path $skillDir "references"
    $refTotalLines = 0
    $refTotalTokens = 0
    $refFileCount = 0
    if (Test-Path $refDir) {
        Get-ChildItem -Path $refDir -Recurse -File -Filter "*.md" | ForEach-Object {
            $st = Get-FileStats -Path $_.FullName
            $refTotalLines += $st.Lines
            $refTotalTokens += $st.EstTokens
            $refFileCount++
        }
    }

    # 扫描 assets 目录总行数
    $assetsDir = Join-Path $skillDir "assets"
    $assetsTotalLines = 0
    $assetsTotalTokens = 0
    if (Test-Path $assetsDir) {
        Get-ChildItem -Path $assetsDir -Recurse -File | Where-Object { $_.Extension -in @(".md", ".py", ".vue", ".ts") } | ForEach-Object {
            $st = Get-FileStats -Path $_.FullName
            $assetsTotalLines += $st.Lines
            $assetsTotalTokens += $st.EstTokens
        }
    }

    # 检测复盘类章节
    $retroSections = @()
    if ($DetectRetrospectives) {
        $retroSections = Find-RetrospectiveSections -SkillMdPath $skillMdPath
    }

    # 检测孤儿 references
    $orphans = @()
    if ($DetectOrphans) {
        $orphans = Find-OrphanReferences -SkillDir $skillDir -SkillMdContent $skillMdContent
    }

    # 预算对比
    $budget = $null
    $budgetViolations = @()
    if ($CompareBudget) {
        $budget = Read-Budget -SkillDir $skillDir
        if ($null -ne $budget) {
            if ($skillMdStats.Lines -gt $budget.budgets.skill_md_lines) {
                $budgetViolations += @{
                    Type     = "skill_md_over_budget"
                    Severity = $budget.policy.skill_md_over_budget
                    Detail   = "SKILL.md $($skillMdStats.Lines) 行 > 预算 $($budget.budgets.skill_md_lines) 行"
                }
            }
            if ($configStats.Exists -and $configStats.Lines -gt $budget.budgets.config_lines) {
                $budgetViolations += @{
                    Type     = "config_over_budget"
                    Severity = $budget.policy.config_over_budget
                    Detail   = "config $($configStats.Lines) 行 > 预算 $($budget.budgets.config_lines) 行"
                }
            }
        }
    }

    # SKILL.md 超阈值告警（无预算文件时用默认阈值）
    if ($skillMdStats.Lines -gt $SkillMdLineThreshold) {
        $violations += @{
            Skill    = $skillName
            Type     = "skill_md_over_threshold"
            Severity = "ERROR"
            Detail   = "SKILL.md $($skillMdStats.Lines) 行 > 阈值 $SkillMdLineThreshold 行"
        }
    }

    # 复盘章节告警
    if ($retroSections.Count -gt 0) {
        $violations += @{
            Skill    = $skillName
            Type     = "retrospective_in_skill_md"
            Severity = "ERROR"
            Detail   = "发现 $($retroSections.Count) 个复盘类章节未删除"
        }
    }

    # 孤儿告警
    if ($orphans.Count -gt 0) {
        $violations += @{
            Skill    = $skillName
            Type     = "orphan_reference"
            Severity = "WARN"
            Detail   = "孤儿 references: $($orphans -join ', ')"
        }
    }

    # 预算违规告警
    foreach ($bv in $budgetViolations) {
        $violations += @{
            Skill    = $skillName
            Type     = $bv.Type
            Severity = $bv.Severity
            Detail   = $bv.Detail
        }
    }

    $totalEstTokens = $skillMdStats.EstTokens + $configStats.EstTokens + $refTotalTokens + $assetsTotalTokens

    $results += [ordered]@{
        name                  = $skillName
        skill_md              = [ordered]@{
            lines      = $skillMdStats.Lines
            chars      = $skillMdStats.Chars
            est_tokens = $skillMdStats.EstTokens
            over_threshold = $skillMdStats.Lines -gt $SkillMdLineThreshold
        }
        config                = [ordered]@{
            path       = if ($configPath) { $configPath.Substring($skillDir.Length + 1) -replace "\\", "/" } else { $null }
            lines      = $configStats.Lines
            est_tokens = $configStats.EstTokens
        }
        references            = [ordered]@{
            file_count = $refFileCount
            total_lines = $refTotalLines
            est_tokens = $refTotalTokens
        }
        assets                = [ordered]@{
            total_lines = $assetsTotalLines
            est_tokens  = $assetsTotalTokens
        }
        retrospective_sections = if ($DetectRetrospectives) {
            $retroSections | ForEach-Object { @{ line = $_.Line; title = $_.Title } }
        } else { $null }
        orphan_references     = if ($DetectOrphans) { $orphans } else { $null }
        budget                = if ($null -ne $budget) {
            [ordered]@{
                skill_md_lines = $budget.budgets.skill_md_lines
                config_lines   = $budget.budgets.config_lines
            }
        } else { $null }
        total_est_tokens      = $totalEstTokens
    }
}

# 链式引用检测
$chainViolations = @()
if ($DetectChain) {
    $sharedRefDir = Join-Path $SkillsRoot "_shared\references"
    $chainViolations = Find-ChainReferences -SharedRefDir $sharedRefDir
    foreach ($cv in $chainViolations) {
        $violations += @{
            Skill    = "_shared"
            Type     = "chain_reference"
            Severity = "ERROR"
            Detail   = "$($cv.File): $($cv.Type) - $($cv.Detail)"
        }
    }
}

# ===== 输出阶段 =====

$outputPath = Join-Path $SkillsRoot $OutputDir
if (-not (Test-Path $outputPath)) {
    New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
}

# JSON 报告（机器可读）
$jsonReport = [ordered]@{
    scan_date   = $scanDate
    skills_root = $SkillsRoot
    threshold   = @{ skill_md_lines = $SkillMdLineThreshold }
    skills      = $results
    violations  = $violations
    summary     = [ordered]@{
        skill_count          = $results.Count
        total_skill_md_lines = ($results | ForEach-Object { $_.skill_md.lines } | Measure-Object -Sum).Sum
        total_skill_md_tokens = ($results | ForEach-Object { $_.skill_md.est_tokens } | Measure-Object -Sum).Sum
        total_est_tokens     = ($results | ForEach-Object { $_.total_est_tokens } | Measure-Object -Sum).Sum
        violation_count      = $violations.Count
        error_count          = ($violations | Where-Object { $_.Severity -eq "ERROR" }).Count
        warn_count           = ($violations | Where-Object { $_.Severity -eq "WARN" }).Count
    }
}

$jsonFile = Join-Path $outputPath "audit-$scanDateStamp.json"
$jsonReport | ConvertTo-Json -Depth 10 | Out-File -FilePath $jsonFile -Encoding UTF8

# Markdown 报告（人类可读）
$md = @()
$md += "# Token 审计报告"
$md += ""
$md += "**扫描时间**: $scanDate  "
$md += "**Skills 根目录**: ``$SkillsRoot``  "
$md += "**SKILL.md 行数阈值**: $SkillMdLineThreshold"
$md += ""
$md += "## 总览"
$md += ""
$md += "| 指标 | 值 |"
$md += "|------|-----|"
$md += "| 技能数 | $($jsonReport.summary.skill_count) |"
$md += "| SKILL.md 总行数 | $($jsonReport.summary.total_skill_md_lines) |"
$md += "| SKILL.md 总 token（估算） | $($jsonReport.summary.total_skill_md_tokens) |"
$md += "| 全资产总 token（估算） | $($jsonReport.summary.total_est_tokens) |"
$md += "| 违规数 | $($jsonReport.summary.violation_count)（ERROR $($jsonReport.summary.error_count) / WARN $($jsonReport.summary.warn_count)） |"
$md += ""
$md += "## 技能明细"
$md += ""
$md += "| 技能 | SKILL.md 行数 | SKILL.md token | config 行数 | references 行数 | 总 token | 预算（SKILL/config） |"
$md += "|------|--------------|----------------|------------|-----------------|----------|---------------------|"
foreach ($r in $results) {
    $overFlag = if ($r.skill_md.over_threshold) { " ⚠️" } else { "" }
    $budgetStr = if ($r.budget) { "$($r.budget.skill_md_lines) / $($r.budget.config_lines)" } else { "未声明" }
    $md += "| $($r.name) | $($r.skill_md.lines)$overFlag | $($r.skill_md.est_tokens) | $($r.config.lines) | $($r.references.total_lines) | $($r.total_est_tokens) | $budgetStr |"
}
$md += ""

if ($violations.Count -gt 0) {
    $md += "## 违规告警"
    $md += ""
    $md += "| 技能 | 类型 | 严重度 | 详情 |"
    $md += "|------|------|--------|------|"
    foreach ($v in $violations) {
        $sevIcon = if ($v.Severity -eq "ERROR") { "🔴" } else { "🟡" }
        $md += "| $($v.Skill) | $($v.Type) | $sevIcon $($v.Severity) | $($v.Detail) |"
    }
    $md += ""
}

if ($DetectRetrospectives) {
    $md += "## 复盘类章节明细"
    $md += ""
    foreach ($r in $results) {
        if ($r.retrospective_sections -and $r.retrospective_sections.Count -gt 0) {
            $md += "### $($r.name)（$($r.retrospective_sections.Count) 个）"
            $md += ""
            $md += "| 行号 | 标题 |"
            $md += "|------|------|"
            foreach ($s in $r.retrospective_sections) {
                $md += "| $($s.line) | $($s.title) |"
            }
            $md += ""
        }
    }
}

$md += "## 优化建议"
$md += ""
$md += "1. **SKILL.md 超 500 行**的技能：删除复盘类章节（四维度复盘/v2.x 复盘/配置节点速查），迁移维度详解到 references/dimensions.md"
$md += "2. **复盘类章节未删除**：按计划阶段 2 执行删除（保留指令性内容迁移到 references/）"
$md += "3. **孤儿 references**：在 SKILL.md 文档结构图补索引行，或删除无用文件"
$md += "4. **config 超预算**：合并分散段、按核心/扩展分层、移除示例注释"
$md += ""

$mdFile = Join-Path $outputPath "audit-$scanDateStamp.md"
$md -join "`n" | Out-File -FilePath $mdFile -Encoding UTF8

# 控制台摘要输出
Write-Host ""
Write-Host "========== Token 审计完成 ==========" -ForegroundColor Cyan
Write-Host "扫描时间: $scanDate"
Write-Host "技能数: $($jsonReport.summary.skill_count)"
Write-Host "SKILL.md 总行数: $($jsonReport.summary.total_skill_md_lines)"
Write-Host "SKILL.md 总 token（估算）: $($jsonReport.summary.total_skill_md_tokens)"
Write-Host "全资产总 token（估算）: $($jsonReport.summary.total_est_tokens)"
Write-Host "违规数: $($jsonReport.summary.violation_count)（ERROR $($jsonReport.summary.error_count) / WARN $($jsonReport.summary.warn_count)）"
Write-Host ""
Write-Host "报告文件:" -ForegroundColor Green
Write-Host "  JSON: $jsonFile"
Write-Host "  MD:   $mdFile"
Write-Host ""

if ($jsonReport.summary.error_count -gt 0) {
    Write-Host "存在 ERROR 级违规，请处理后再提交" -ForegroundColor Red
    exit 2
} elseif ($jsonReport.summary.warn_count -gt 0) {
    Write-Host "存在 WARN 级告警" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "全部通过 ✓" -ForegroundColor Green
    exit 0
}
