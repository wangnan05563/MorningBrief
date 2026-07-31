# 4 个 news-* 技能 Token 优化实施计划

## Context（背景与目标）

**问题**：4 个技能 SKILL.md 严重膨胀，全部违反"≤500 行"规范，合计 16644 行（超标 8-32 倍）。膨胀主因是历史复盘内容（四维度复盘/v2.x 复盘/配置节点速查）污染了能力指令文件，每次技能触发都加载大量过程记录，造成 token 浪费。

| 技能 | 当前行数 | 规范上限 | 超标倍数 |
|------|---------|---------|---------|
| news-auto-testing | 5649 | 500 | 11.3x |
| news-backend-code-review | 5004 | 500 | 10.0x |
| news-frontend-code-review | 4051 | 500 | 8.1x |
| news-code-dev | 1940 | 500 | 3.9x |

**目标**：4 个 SKILL.md 均 ≤500 行，预加载 token 减少 ~88%，建立 token 监控机制守门，不影响功能完整性。

**用户决策**：
- 实施范围：全部 5 阶段（审计基线 → SKILL.md 瘦身 → config 精简 → 跨技能去重 → 脚本模板复用）
- 复盘处置：**直接删除过时复盘**（不归档），但保留已提炼为维度/规则/配置节点的指令性内容

---

## 一、优化后的 SKILL.md 标准结构（≤500 行）

所有 4 个技能统一采用以下结构（基于 [news-code-dev/SKILL.md](file:///d:/code/otherProjects/20_News/.trae/skills/news-code-dev/SKILL.md) L52-113 的良好模式）：

```markdown
---
name: "<skill-name>"                    # 动名词，小写+连字符
description: "<职责>。当用户<场景>时调用。"  # ≤200字，含触发关键词
whenToUse: "<正向场景>"                  # 必填（news-auto-testing 当前缺失，需补）
triggers: "<关键词1> | <关键词2>"        # 必填，管道分隔
version: "<semver>"
updated: "YYYY-MM-DD"
config: "<相对路径>"
---

# <技能标题>

## 项目背景速查          ← 1 个表格（产品/技术栈/核心链路）
## 文档结构              ← 目录树注释 + 资产索引表（指南/规则/参考各一张表）
## Input / Output 契约   ← 新增：结构化签名（必填/可选参数 + 输出格式 + 退出码）
## 执行步骤              ← 指令式编号步骤（禁用"复盘"字样）
## 失败处理              ← 新增：失败场景 | 判断信号 | 处理方式 表格
## 核心规则速查          ← 精简表（编号 | 规范 | grep 信号 | 优先级）+ references 引用
## 参考                  ← 指向 references/ 与 _shared/references/
```

**行数预算**：frontmatter 12 + 背景 15 + 文档结构 60 + I/O 契约 25 + 执行步骤 80 + 失败处理 30 + 速查表 200 + 参考 10 = **≤432 行**（留 68 行缓冲）

---

## 二、"过时复盘"判定与删除规则

按用户决策"直接删除过时复盘"，执行以下拆分规则：

| 段落内容类型 | 判定 | 处置 |
|-------------|------|------|
| 四维度复盘（成功步骤/不确定性/可抽象流程/适用场景） | 过时过程记录 | **直接删除** |
| "v2.x：YYYY-MM-DD ...复盘"整章 | 过时过程记录 | **直接删除** |
| "测试流程优化总结（vN 更新）" | 过时过程记录 | **直接删除** |
| "配置节点速查"表 | 冗余（config.yaml 已有） | **直接删除** |
| "补充章节：基于...复盘的优化"中的指令性内容 | 仍有效指令 | **保留**，迁移到 references/ |
| "维度 N" / "阶段 N" 的定义与判断信号 | 仍有效指令 | **保留**，迁移到 references/dimensions.md 或 stages.md |
| "vN 新增修复策略"表 | 仍有效指令 | **保留**，合并到 config.yaml#fix_strategies |
| "vN 新增测试用例优先级" | 仍有效配置 | **保留**，合并到 config.yaml#test_priority |

**关键原则**：删除的是"过程叙述"，保留的是"可执行指令"。已被提炼为维度/规则的指令不丢失。

---

## 三、实施步骤（5 阶段）

### 阶段 1：建立审计基线（无破坏性，纯新增）

**目标**：开发 token-audit 脚本 + 建立预算基线，不改动任何现有技能。

**新增文件**：
1. `.trae/skills/_shared/scripts/token-audit.ps1` — token 审计脚本（设计见下文第四节）
2. `.trae/skills/_shared/scripts/auto-scan-core.psm1` — 占位文件（阶段 5 填充）
3. 4 个 `.token-budget.json`（每技能目录一个，结构见下文第五节）：
   - `news-code-dev/.token-budget.json`
   - `news-frontend-code-review/.token-budget.json`
   - `news-backend-code-review/.token-budget.json`
   - `news-auto-testing/.token-budget.json`

**验收**：运行 `token-audit.ps1` 生成 baseline 报告，输出 4 技能当前行数/token 估算 + 超预算告警 + 复盘段统计。

### 阶段 2：4 个 SKILL.md 瘦身（核心阶段）

按"指令留下、复盘删除、配置速查删除"三原则重构。**顺序**：news-code-dev（验证流程）→ frontend → backend → testing（最复杂）。

**阶段 2.1 — news-code-dev**（参考文件：[SKILL.md](file:///d:/code/otherProjects/20_News/.trae/skills/news-code-dev/SKILL.md)）：
- 删除 L303-1940 的所有"维度 1-19 复盘"章节（约 1200 行过程叙述）
- 在文档结构图 L64 后补 `lessons-learned.md` 索引行（修复当前孤儿状态）
- 重写 SKILL.md 主体：保留 L1-302 核心指令，新增 Input/Output 契约 + 失败处理章节
- 验证：行数 ≤500，token-audit 通过

**阶段 2.2 — news-frontend-code-review**：
- 新建 `references/` + `references/dimensions.md` + `assets/` 目录
- 删除 12 个"配置节点速查"段（L1702/1912/2025/2403/2705/2868/2994/3160/3261/3464/3714/4001）
- 删除所有"四维度复盘"重复段 + 10+ 个"v2.x 复盘"段
- 维度 1-118 详解迁移到 `references/dimensions.md`
- SKILL.md 保留：frontmatter（补 Input/Output + 失败处理）+ 15 维度速查表（精简）+ 文档结构图
- 目标：4051 行 → ≤500 行

**阶段 2.3 — news-backend-code-review**：
- 同上目录结构
- 删除 11 个"配置节点速查"段（L701/1947/2167/2318/3217/3547/3599/3739/3901/4398/4411）
- 删除 6 个"v2.x 复盘"段（L483/3561/3913/4788/4953 等）
- 维度 1-149 详解迁移到 `references/dimensions.md`，按核心(1-90)/扩展(91-149)分层
- 修复维度编号不连续问题（如维度 133-135 在 106-112 之前）
- 目标：5004 行 → ≤500 行

**阶段 2.4 — news-auto-testing**：
- 同上目录结构
- 补全 frontmatter 的 `whenToUse/triggers` 字段（当前完全缺失）
- 删除 14 个"配置节点速查"段 + 15 个"测试流程优化总结（vN 更新）"段
- 删除 15 个"补充章节：基于...复盘的优化（v2-v15）"中的过程叙述，保留阶段定义迁移到 `references/stages.md`
- 75 阶段详解迁移到 `references/stages.md`
- 目标：5649 行 → ≤500 行

**阶段 2 验收**：4 个 SKILL.md 均 ≤500 行；token-audit 无 ERROR；关键 grep 信号全保留（diff 验证未丢失指令）。

### 阶段 3：config.yaml 精简

**操作**：
1. 合并 testing 的 15 个分散 `fix_strategies`/`test_priority` 段为统一节点
2. 按核心/扩展拆分维度：`core_dimensions`（1-90，默认全开）+ `extended_dimensions`（91+，按需开）
3. 移除 config.yaml 中的示例代码注释到 `references/examples/`
4. 运行 `auto-scan.ps1` 验证硬约束规则未被破坏

**目标行数**：
- news-frontend-code-review: 1817 → ≤800
- news-backend-code-review: 2370 → ≤900
- news-auto-testing: 3596 → ≤1200

### 阶段 4：跨技能去重（_shared 目录）

**新增目录**：`.trae/skills/_shared/references/`

**共享文件**（出现在 ≥2 个技能的主题才提共享）：
- `sonarqube-closure.md` — SonarQube 闭环（backend 维度 73-90 + testing 阶段 20-31 共用）
- `tts-multi-provider.md` — TTS 多 Provider（code-dev + backend 106-112 + frontend 共用）
- `miniprogram-playback.md` — 小程序播放（frontend + backend 81-83 + testing v6 共用）
- `channel-data-isolation.md` — 频道级隔离（backend + testing 共用）
- `timezone-consistency.md` — 时区一致性（4 技能共用）
- `cross-project-migration.md` — 跨项目迁移 7 步法（3 技能共用）
- `nosonar-positioning.md` — NOSONAR 注释位置（3 技能共用）

**操作**：
1. 从各技能 `references/dimensions.md` 提取对应主题段到共享文件
2. 各技能 `references/dimensions.md` 删除已共享段落，改为"详见 [_shared/references/xxx](../_shared/references/xxx)"
3. 各技能 SKILL.md "## 参考"章节补共享文件索引

**链式引用防护**（强制）：
- _shared 文件禁止反向引用技能专属文件
- _shared 文件禁止互相引用（_shared 内部扁平）
- token-audit.ps1 增加 `--detect-chain` 模式守门

### 阶段 5：脚本与模板复用

**操作**：
1. 填充 `_shared/scripts/auto-scan-core.psm1` 公共函数：`Get-ProjectRoot`/`Invoke-GrepCheck`/`Write-ScanReport`/`Read-HardConstraints`
2. 改写 [frontend auto-scan.ps1](file:///d:/code/otherProjects/20_News/.trae/skills/news-frontend-code-review/scripts/auto-scan.ps1)（242行）和 [backend auto-scan.ps1](file:///d:/code/otherProjects/20_News/.trae/skills/news-backend-code-review/scripts/auto-scan.ps1)（448行）为薄壳：`Import-Module` + 调用公共函数
3. 合并两个 `report-template.md` 到 `_shared/templates/report-template.md`，各技能保留"技能专属章节"片段

**预期**：frontend auto-scan 242→60 行，backend 448→80 行。

---

## 四、token-audit.ps1 设计

**位置**：`.trae/skills/_shared/scripts/token-audit.ps1`

**参数（全参数化，无硬编码）**：
```powershell
param(
    [string]$SkillsRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string[]]$SkillNames = @(),                  # 空则扫描全部
    [int]$SkillMdLineThreshold = 500,
    [int]$ConfigLineThreshold = 0,                # 0 表示读 .token-budget.json
    [string]$OutputDir = "audit-reports",
    [switch]$CompareBudget,                       # 对比 .token-budget.json
    [switch]$DetectOrphans,                       # 检测孤儿 references
    [switch]$DetectRetrospectives,                # 检测未删除复盘段
    [switch]$DetectChain                          # 检测 _shared 链式引用
)
```

**核心逻辑**：
1. 扫描每个技能的 SKILL.md / config.yaml / references，统计行数、字符数、估算 token（chars/2.2 经验值）
2. 正则匹配复盘类章节：`^(##|###)\s.*(复盘|retrospect|四维度|补充章节.*v\d|配置节点速查|测试流程优化总结)`
3. 检测孤儿 references（文件存在但 SKILL.md 未引用）
4. 对比 `.token-budget.json` 预算，输出超预算告警
5. 输出 JSON（机器可读）+ Markdown（人类可读，含告警表）

**退出码**：0=全通过 / 1=有 WARN / 2=有 ERROR

**编码约束**（按 project_memory.md）：UTF-8 with BOM + CRLF，首行 `chcp 65001 > $null` + `[Console]::OutputEncoding` 设置。

---

## 五、.token-budget.json 设计

**位置**：每技能目录一个 `<skill>/.token-budget.json`

**结构**：
```json
{
  "skill": "news-backend-code-review",
  "version": "1.0.0",
  "updated": "2026-07-31",
  "budgets": {
    "skill_md_lines": 500,
    "skill_md_est_tokens": 12000,
    "config_lines": 900,
    "references_total_lines": 3000,
    "total_est_tokens": 58000
  },
  "policy": {
    "skill_md_over_budget": "ERROR",
    "config_over_budget": "WARN",
    "retrospective_in_skill_md": "ERROR",
    "config_lookup_in_skill_md": "ERROR",
    "orphan_reference": "WARN"
  }
}
```

**CI 集成**：`token-audit.ps1 -CompareBudget` 可挂到 pre-commit 或 PR 检查。

---

## 六、验证方案

### 6.1 功能完整性验证（关键 grep 信号未丢失）

对每个技能，优化前后提取所有 grep 判断信号（如 `datetime.now`、`LIMIT`、`hmac.compare_digest`），在优化后 SKILL.md + references 中逐一验证仍存在。

```powershell
# 提取 baseline 信号
token-audit.ps1 -VerifyKeywords -OutputDir before
# 优化后验证
token-audit.ps1 -VerifyKeywords -OutputDir after
# 对比缺失项
Compare-Object before/keywords.json after/keywords.json
```

### 6.2 token 减少验证

```powershell
# 优化前
token-audit.ps1 -OutputDir before
# 优化后
token-audit.ps1 -OutputDir after -CompareBudget
```

**目标指标**：
- SKILL.md 总行数：16644 → ≤2000（4×500），减少 88%
- SKILL.md 总 token：~580K → ~70K，减少 88%
- config.yaml 总行数：8363 → ≤3900，减少 53%

### 6.3 回归测试用例

| 用例 | 验证方法 | 预期 |
|------|----------|------|
| 维度不丢失 | 问"审查维度 106 是什么" | 模型 Read references/dimensions.md 找到 |
| 共享文件可被多技能引用 | backend 和 frontend 都问"SonarQube 闭环" | 都 Read _shared/references/sonarqube-closure.md |
| 配置驱动未破坏 | 改 config.yaml 阈值 | 技能行为变化（无硬编码） |
| 预算守门 | SKILL.md 超 500 行提交 | token-audit 退出码 2 |
| 链式引用防护 | _shared 文件引用技能专属 | token-audit --detect-chain 告警 |

---

## 七、风险评估与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 删除复盘后历史经验丢失 | 中 | 关键经验已提炼为维度/规则/grep 信号保留在速查表 + references/dimensions.md；news-code-dev 有 lessons-learned.md 作为经验库 |
| config 精简导致漏审 | 中 | extended_dimensions 默认值显式声明；SKILL.md 触发条件明确"涉及 TTS/时区时自动激活" |
| 跨技能共享引入链式引用 | 低 | token-audit --detect-chain 守门；_shared 文件禁止反向引用 |
| 阶段 2 顺序风险 | 低 | 严格按 code-dev → frontend → backend → testing，每技能完成后跑 token-audit 才进入下一个 |

---

## 八、关键文件清单

**待修改（阶段 2）**：
- [news-code-dev/SKILL.md](file:///d:/code/otherProjects/20_News/.trae/skills/news-code-dev/SKILL.md) — L303-1940 复盘删除
- [news-frontend-code-review/SKILL.md](file:///d:/code/otherProjects/20_News/.trae/skills/news-frontend-code-review/SKILL.md) — 4051→500
- [news-backend-code-review/SKILL.md](file:///d:/code/otherProjects/20_News/.trae/skills/news-backend-code-review/SKILL.md) — 5004→500
- [news-auto-testing/SKILL.md](file:///d:/code/otherProjects/20_News/.trae/skills/news-auto-testing/SKILL.md) — 5649→500

**待修改（阶段 3）**：
- 3 个 config.yaml 精简

**待修改（阶段 5）**：
- [frontend auto-scan.ps1](file:///d:/code/otherProjects/20_News/.trae/skills/news-frontend-code-review/scripts/auto-scan.ps1) + [backend auto-scan.ps1](file:///d:/code/otherProjects/20_News/.trae/skills/news-backend-code-review/scripts/auto-scan.ps1) 改为薄壳
- 2 个 report-template.md 合并

**新增文件**：
- `_shared/scripts/token-audit.ps1`（阶段 1）
- `_shared/scripts/auto-scan-core.psm1`（阶段 5）
- `_shared/references/*.md`（7 个共享文件，阶段 4）
- `_shared/templates/report-template.md`（阶段 5）
- 4 个 `.token-budget.json`（阶段 1）
- 各技能 `references/dimensions.md` 或 `stages.md`（阶段 2）

---

## 九、反模式自检

- [x] SKILL.md ≤500 行（4 个技能全部达标）
- [x] 一层引用深度（SKILL.md → references，禁止 A→B→C）
- [x] 无链式引用（_shared 内部扁平，不反向引用）
- [x] 职责单一（每个技能一个核心动作）
- [x] 触发条件明确（正向 whenToUse + 负向边界）
- [x] Input/Output 结构化（新增契约章节）
- [x] 失败处理完备（新增失败处理章节）
- [x] 无硬编码（token-audit 全参数化，预算走 .token-budget.json）
- [x] 渐进式披露（SKILL.md 精简速查 + references 详解）
