---
name: "news-frontend-code-review"
description: "对 MorningBrief 项目前端代码（admin-web/src/ 下 Vue 3/Element Plus 文件 + miniprogram/ 下微信小程序文件）进行全面评审与逻辑审查，覆盖组件规范、状态管理、API 契约、路由设计、类型安全、性能、可访问性、前后端字段契约、小程序生命周期、音频播放管理等维度。当用户要求'审查/检查/走查/把关/review/评估/看看对不对/规范不规范'前端 Vue/JS 代码、'.vue/.js 文件修改'、'迭代发布前前端走查'，或提到'前端评审/frontend review/Vue 代码审查/小程序代码审查'时调用。仅审查前端文件；纯后端 .py 文件审查请改用 news-backend-code-review。"
whenToUse: "需要审查 MorningBrief 前端代码（admin-web/src/ 下 .vue/.js 文件 + miniprogram/ 下 .js/.wxml/.wxss 文件）是否符合项目规范"
triggers: "前端代码 走查/审查/审核/把关/review/检查/评估 | .vue/.js 文件 修改/变更/迭代 走查 | 迭代发布前 前端 代码 走查 | 这段前端代码 写得对不对/规范不规范 | Vue/小程序 代码 review | 页面/组件/Store/路由 代码 审查"
version: "3.1.0"
updated: "2026-08-05"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 前端代码审查

对 MorningBrief 项目前端代码进行全面评审，覆盖**运营后台（admin-web/，Vue 3 + Element Plus + Vite + Pinia）**与**微信小程序（miniprogram/，原生小程序）**两套前端代码。

## 配置驱动

**核心原则**：所有评审规则、硬约束、项目规范均通过 `config.yaml` 管理，技能本身不含任何业务参数或硬编码值。新增规则只需修改配置文件，无需改动技能本身。

配置文件位置：`.trae/skills/news-frontend-code-review/config.yaml`

首次使用时，从同目录的 `config.example.yaml` 复制并按项目实际情况修改。配置项分为 8 大类：

| 配置类 | 职责 | 关键参数 |
|--------|------|----------|
| `scope` | 评审范围 | include_paths, exclude_paths, file_extensions, max_files_per_run |
| `priority` | 优先级排序 | severity_order, category_order, report_threshold |
| `hard_constraints` | 硬约束规则 | rules（可扩展列表，每条含 name/pattern/message/severity/auto_fix） |
| `checklist` | 评审检查清单 | 15 大类开关 |
| `abstraction_thresholds` | 抽象建议阈值 | inline_style_repeat, text_literal_repeat, function_max_lines 等 |
| `report` | 报告生成 | output_dir, format, include_good_practices, max_suggestions |
| `verify` | 验证配置 | run_tests_after_review, test_command, fail_on_critical |
| `project_conventions` | 项目专属规范参考 | tech_stack, field_contract_frontend, miniprogram_lifecycle 等 |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh .trae/skills/news-frontend-code-review/scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文件 | 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建议 |

---

## Input / Output 契约

### Input
- **必填**：审查范围（文件路径列表 / git diff / 代码片段）
- **可选**：审查模式（quick / incremental / file / full，默认 incremental）

### Output
- **报告文件**：按 `templates/report-template.md` 输出结构化报告到 `config.yaml#report.output_dir`
- **控制台摘要**：违规总数、按严重级别分组、修复建议优先级排序

---

## 审查流程

### 阶段 1：快速自检（阻塞级）

```powershell
pwsh .trae/skills/news-frontend-code-review/scripts/auto-scan.ps1
```

扫描阻塞级问题，发现 CRITICAL 必须修复后再继续。

### 阶段 2：人工评审（按维度）

按 `config.yaml#checklist` 开关逐维度审查：

1. 读取 `config.yaml` 获取启用维度
2. 按维度遍历，每维度记录违规位置 + 修复建议
3. 对照 `field_contract_frontend.known_field_pairs` 核对字段契约
4. 对照 `miniprogram_lifecycle.listener_pairs` 核对生命周期配对
5. 触发 `abstraction_thresholds` 时记录抽象建议

详细审查规则定义在 [references/dimensions.md](references/dimensions.md)。

### 阶段 3：报告生成

按 `templates/report-template.md` 输出报告，包含：

- 基本信息、审查结果摘要
- 硬约束合规性检查结果
- 详细问题列表（按 severity 分组）
- 好的实践（正面反馈）
- 配置变更点

### 阶段 4：修复验证

修复后重新运行阶段 1 + 阶段 2，确认问题已解决。

---

## 失败处理

| 失败场景 | 判断信号 | 处理方式 |
|----------|----------|----------|
| config.yaml 缺失 | 启动时文件不存在 | 回退 config.example.yaml |
| 审查范围无文件 | git diff 为空 | 退出码 0 + 提示"无变更" |
| 维度配置缺失 | config.yaml 对应节点为 null | 跳过该维度 + WARN |
| auto-scan.ps1 不可执行 | PowerShell 执行策略限制 | 提示手动设置 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| report-template.md 缺失 | template 找不到 | 使用内置默认模板输出纯文本报告 |

---

## 核心审查维度

> 完整定义见 [references/dimensions.md](references/dimensions.md)。以下为快速参考表。

### 默认全开维度（1-15）

| 编号 | 维度 | 关键检查点 | 严重级别 |
|------|------|-----------|----------|
| 1 | 目录结构 | 分层清晰；禁止跨层反向依赖；页面文件命名规范 | CRITICAL |
| 2 | 命名规范 | PascalCase/camelCase/UPPER_SNAKE_CASE；事件处理 `on*` 前缀 | HIGH |
| 3 | Vue 3 组件规范 | `<script setup>`；`defineProps`+类型标注；`:key` 唯一标识 | HIGH |
| 4 | Element Plus 规范 | `el-form` 验证；`el-table` 分页；`:loading` 防重复提交 | HIGH |
| 5 | Pinia 状态管理 | `defineStore`；state/getters/actions 分离；异常处理 | HIGH |
| 6 | API 调用规范 | 统一 `api/` 封装；拦截器 JWT + 401 处理；路径严格相等判断 | HIGH |
| 7 | 路由设计 | 懒加载；`beforeEach` 守卫；404 兜底；`meta.requiresAuth` | HIGH |
| 8 | 前后端字段契约 | snake_case 透传；禁止转 camelCase；字段名前后端一致 | CRITICAL |
| 9 | 小程序生命周期 | `onLoad`/`onUnload` 配对；监听器 `off`；`globalData` 显式声明 | CRITICAL |
| 10 | 小程序音频播放 | 全局单例 `player`；`episodeId` 判断；`onCanplay` 自清理 | CRITICAL |
| 11 | 小程序 API 层 | 循环依赖延迟 `require`；BASE_URL 环境切换；token 集中管理 | HIGH |
| 12 | 性能 | 路由懒加载；虚拟滚动；防抖；`setData` 批量更新 | MEDIUM |
| 13 | 可访问性 | 语义化 HTML；`aria-label`；表单 label 关联；颜色对比度 | MEDIUM |
| 14 | 代码质量 | 禁止 `console.log`/`debugger`；注释解释"为什么"；延迟 require | HIGH |
| 15 | 错误处理 | try-catch；空状态 `el-empty`；loading 状态；友好网络提示 | HIGH |

### 补充审查要点（A-M）

| 编号 | 维度 | 关键检查点 | 严重级别 |
|------|------|-----------|----------|
| A | el-table 拖拽排序 | Sortable.js `onEnd` 先恢复 DOM 再改数组；取消 `fixed` 列 | HIGH |
| B | canvas 验证码 | 排除形近字符（`0/O`、`l/I/1`、`5/S`） | HIGH |
| C | el-upload 文件校验 | `before-upload` 类型+大小双重校验；`accept` 属性 | HIGH |
| D | 图表组件注册 | `Chart.register(BarElement/LineElement/Filler)` | HIGH |
| E | 趋势图 Y 轴单位 | 指标切换时 Y 轴单位同步更新；配置驱动 | MEDIUM |
| F | 外部服务降级前端 | audio src 支持绝对/相对路径；降级提示 `el-alert`；错误分类 | HIGH |
| G | 小程序用户态双层同步 | `globalData` 写入后同步 `localStorage`；UI 状态不写持久化 | CRITICAL |
| H | 小程序 4 维静态验证 | `node --check` / 接口 / 契约 / 渲染四维验证 | HIGH |
| I | 字段契约验证清单 | 请求字段/响应字段/兜底链三项核对 | HIGH |
| J | 进度上报容错 | `duration<=0` 不跳过上报；`listened_seconds` 独立累计 | HIGH |
| K | 状态属性一致性 | `status` 属性先检查标志位再查询；`stop()` 设标志位 | HIGH |
| L | 音频队列自动播放 | `onEnded` 触发 `playNext()`；空队列预填 | MEDIUM |
| M | 小程序分包配置 | `pages` 路径不以 `subPackages[].root` 为前缀 | HIGH |

---

## 参考

- [dimensions.md](references/dimensions.md) — 审查维度详细定义（118 项，含判断信号、grep 模式、修复示例）
- [_shared/references/](../_shared/references/) — 跨技能共享主题
- [news-code-dev](../news-code-dev/SKILL.md) — 项目开发技能（编码规范）
- [config.yaml](config.yaml) — 审查配置（规则/硬约束/阈值/字段契约）

---

## V3.0 2026-08-05 会话复盘新增前端审查维度（FE-196~FE-200）

> 来源：打包模式三面板空白、关于页版本失真、HLS 首播冷启动失败、微信剪贴板隐私未声明四类真实问题。对应 news-code-dev 诊断标准 DS-5 / DS-6 / DS-13 / DS-14（详见 news-code-dev `references/diagnostic-standards.md`）。
> 所有规则参数通过 `config.yaml` 对应节点管理；报告中违规条目标注 `[V3.0 新增]`。
> **配置落地**：FE-196~FE-200 的五个 `config.yaml` 节点（`remote_resource_display_check` / `build_metadata_display_check` / `packaging_fallback_ui_check` / `hls_cold_start_retry_check` / `wechat_privacy_scope_check`）已补齐；V3.1 新增 FE-201 节点 `backend_switch_field_passthrough_check`。审查时直接读取对应节点，无硬编码新增。

| 维度 | 审查项 | 严重级别 | 对应 DS | 配置节点 |
|------|--------|----------|---------|----------|
| FE-196 | 远程资源字段契约展示一致性：远程 `path` 返回语义值（如 `"云端(COS)"`）、`size_bytes=0` 前端正确展示（不为空/异常）、删除按钮 `v-if` 排除远程 | HIGH | DS-5 | `remote_resource_display_check` |
| FE-197 | 关于页/版本真实发布日展示：GitHub ISO → UTC+8 转换（`_formatPublishedAt`）；检查更新基于真实 version；非法输入防御 | MEDIUM | DS-6 | `build_metadata_display_check` |
| FE-198 | 打包模式回退 UI 一致性：详情页素材/TTS/成品面板在 COS 回退下可展示；远程 blob 走代理；`activePanels` 懒加载 | HIGH | DS-5 | `packaging_fallback_ui_check` |
| FE-199 | HLS 首播冷启动静默重试与降级：音频 `onError` 首播必须有静默重试分支（`MAX_HLS_RETRY`）；重试耗尽回退 mp3 直链；首播失败不得中断连续 loading | HIGH | DS-13 | `hls_cold_start_retry_check` |
| FE-200 | 微信隐私合规 scope 声明：敏感 API（`setClipboardData` 等）调用前必须 `requirePrivacyAuthorize`；后台声明对应 scope（剪贴板读写共用「剪贴板」scope） | CRITICAL | DS-14 | `wechat_privacy_scope_check` |
| FE-201 | 后端新增开关/枚举字段的前端透传与列表列展示：通用 axios 透传包装不得丢字段；新字段须在列表新增展示列与编辑控件；后端继承语义（NULL/None）与前端"继承/自定义"往返一致 | HIGH | DS-15 | `backend_switch_field_passthrough_check` |

### 审查结果呈现优化（V3.0）

与后端审查保持一致，报告（`templates/report-template.md`）增强：

1. **问题定性分层**：每条问题标注 `真缺陷 / 误报 / 环境制品`（如 safe-delete 拦截前端构建清理属环境制品，非代码失败）。
2. **适用/不适用场景字段**：每条问题补充 `适用场景` 与 `不适用场景`（取自 DS 标准维度 4）。
3. **严重级别判定理由**：阻塞级须写明"为什么阻塞"，而非仅给标签。
4. **与整体工作流一致**：修复建议优先指向 news-code-dev 的 DS 标准与 meta-rules 编号；新增规则须在 `config.yaml` 有对应节点（无硬编码新增）。

## V3.1 2026-08-05 段间静音/bgm_gap_mode 复盘新增前端审查维度（FE-201）

> 来源：段间静音做成可开关 `bgm_gap_mode`(silence/bridge) 后，前端须保证通用 axios 透传不丢新字段，并在列表/编辑表单显式展示与编辑该开关；后端 `NULL`（继承全局）与前端"继承/自定义"往返一致。对应 news-code-dev 诊断标准 DS-15（媒体特性可开关化与真静音实现）。
> 所有规则参数通过 `config.yaml` 对应节点管理；报告中违规条目标注 `[V3.1 新增]`。

| 维度 | 审查项 | 严重级别 | 对应 DS | 配置节点 |
|------|--------|----------|---------|----------|
| FE-201 | 通用 axios 透传包装不得丢弃后端新增字段（snake_case 直传）；后端新增开关/枚举字段须在列表新增展示列 | HIGH | DS-15 | `backend_switch_field_passthrough_check.passthrough_no_drop` |
| FE-201 | 后端新增开关字段须在编辑表单提供控件（如下拉 silence/bridge）；后端 `NULL` 表示"继承全局"，前端须支持"继承/自定义"往返（`inherit` → `null`） | HIGH | DS-15 | `backend_switch_field_passthrough_check.inherit_null_roundtrip` |
