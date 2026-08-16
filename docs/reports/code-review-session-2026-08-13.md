# 代码评审报告 · 当前会话修改逻辑（2026-08-13）

评审范围：本会话（含未提交 working tree）中修改的生产代码逻辑，覆盖业务范围扩展 T5/T7、队列批量删除 FK 修复、维护清理级联修复，以及移动端 ReviewList/ManageQueue。

评审依据：news-backend-code-review (v3.4.0) + news-frontend-code-review (v3.4.0)。
定性分层：`真缺陷` / `误报` / `环境制品`。级别：HIGH / MEDIUM / LOW / INFO。

---

## 一、后端（Python / FastAPI / SQLAlchemy）

### [MEDIUM→HIGH · 真缺陷] 1. 批量删除孤儿 Episode 的 PlayLog 未清理，仍可能 FK 失败
- **位置**：`backend/app/services/workflow_service.py` → `batch_delete_workflows`
  - `episode_ids` 收集仅用 `Episode.workflow_id.in_(workflow_ids)`（删除阶段首步）
  - `PlayLog`/`PlayProgress` 按 `episode_id.in_(episode_ids)` 删除
  - `Episode` 删除用 `or_(Episode.workflow_id.in_(workflow_ids), Episode.script_id.in_(script_ids))`
- **问题**：`PlayLog.episode_id` 是**真实外键**（`play_log.py:26-27` `ForeignKey("episode.id")`）。`Episode` 的 OR 分支会删掉「`workflow_id` 不在本批但 `script_id` 属本批」的 Episode（含历史 `workflow_id=NULL` 孤儿）；但这些 Episode 的 id 不在 `episode_ids` 中，其 `PlayLog` 不会被清理 → 删 `Episode` 时触发 `FOREIGN KEY constraint failed`。
- **当前为何没爆**：本会话已回填 42 条 `NULL-workflow` Episode，且脚本跨工作流复用（Episode 属 A 工作流却引用 B 工作流 Script）场景在生产库较少；且回归测试 `test_queue_batch_delete_autoreviewstat.py` 只构造「孤儿 Episode + Script」**未带 PlayLog**，未覆盖此路径。
- **影响**：若存在「script 属本批、自身 workflow 不同且带 PlayLog」的 Episode，或未来再现带 PlayLog 的 `NULL-workflow` 孤儿 Episode，勾选含该工作流的删除仍会 500（前端「数据库错误」）。
- **对应规范**：维度 29-32（批量删除与事务）、R238（异常降级可观测）。
- **修复建议**：将 `episode_ids` 的收集改为与 `Episode` 删除相同的 `or_(workflow_id.in_(workflow_ids), script_id.in_(script_ids))`，使 `PlayLog/PlayProgress` 清理覆盖全部将被删除的 Episode；并在回归测试中补「孤儿 Episode + PlayLog」用例。

### [MEDIUM · 真缺陷 · 注释误导] 2. maintenance_service.py 矛盾注释未清理（aa2380b 已修 bug 有被回退风险）
- **位置**：`backend/app/services/maintenance_service.py:489` 显式 `delete(WorkflowStep)`，其下 `:492` 注释 `# workflow_step 通过 cascade 自动删除，无需手动清理`。
- **问题**：注释与本次修复意图**正好相反**——本修复正是发现 bulk delete 不触发 ORM cascade 才显式删除 `WorkflowStep`。该注释会误导后续维护者「无需手动清理」而删掉 `:489` 行，重新引入 `WorkflowStep` 漏删（aa2380b 抓出的真 bug）。
- **对应规范**：维度 200（别名/重命名/矛盾注释未清理）、R208。
- **修复建议**：删除 `:492` 注释，或改为「Core 级 bulk delete 不触发 ORM cascade，须显式删除 WorkflowStep」。

### [MEDIUM · 真缺陷 · 异常降级缺失] 3. rewriter.py 课程提示词文件缺失无兜底，course 频道触发直接 500
- **位置**：`backend/app/workflow/llm/rewriter.py` `rewrite()` 内（约 1555-1562 行）调用 `_resolve_rewrite_template(...)`、`_load_prompt_file(_COURSE_INTRO_FILE)`、`_load_prompt_file(_COURSE_OUTRO_FILE)` 均**未包裹 try/except**。
- **问题**：`_load_prompt_file` 在文件缺失时抛 `FileNotFoundError`（其 docstring 声称「由调用方兜底」），但 `rewrite()` 未捕获。若 `rewrite_course.txt` / `course_intro.txt` / `course_outro.txt` 任一下发缺失（部署漏发 prompts 目录），course 频道触发改写会直接抛异常 → 工作流 500，而非降级到默认 `rewrite.txt` / 空 intro/outro。
- **对应规范**：维度 239（异常降级收窄与可观测性）、R238。
- **修复建议**：`rewrite()` 内对三处 `_load_prompt_file` 包 `try/except FileNotFoundError` → `logger.warning` 并回退默认模板/空文案，保证课程频道在 prompts 不全时仍可降级运行。

### [MEDIUM · 设计偏离/不对称] 4. style_library.py 频道类型强制覆盖按 ID 定制词库
- **位置**：`backend/app/workflow/llm/style_library.py:413-417` `if channel_type == "course": lib = _COURSE_LIBRARY else: lib = _get_channel_library(channel_id)`。
- **问题**：course 频道一律强制讲师词库，**即使该频道在 `_CHANNEL_STYLE_LIBRARY` 按 ID 配置了专属词库也被忽略**。这与同文件 `rewrite()` 中「`rewrite_template`/`intro_prompt`/`outro_prompt` 频道显式覆盖优先」的约定**不对称**——同一 course 频道能定制文案模板，却无法定制风格口吻。
- **影响**：非崩溃，属功能/设计一致性问题；运营若想为某 course 频道定制口吻无法满足。
- **修复建议**：若需支持按 ID 定制，改为「`channel_type=course` 且该频道无专属词库时再用 `_COURSE_LIBRARY`」；或文档明确「course 一律讲师口吻」以消除歧义。

### [MEDIUM · 事务契约/健壮性 · 未提交改动] 5. workflow_service.py 移除内部 commit，改为调用方 commit（当前 working tree 未提交）
- **位置**：`backend/app/services/workflow_service.py` `batch_delete_workflows` 删除 `await self.db.commit()`（仅保留 `except` 内的 `self.db.rollback()`）。
- **现状核实（已验证，非当前崩溃）**：两个调用方 `routers/admin/queue.py:117` 与 `routers/admin/workflows.py:115` 均在写入 `AuditLog` 后 `db.commit()`，故当前两条 API 路径均正确落库，无静默 no-op。
- **风险**：
  1. **隐式契约**：`batch_delete_workflows` 不再自提交，任何「直接调用 service 且不提交」的新调用方/单测会静默丢失删除（flush 后未 commit → 会话关闭回滚）。
  2. **与 maintenance 不对称**：`maintenance_service._cleanup_workflows` 内部自提交，两条删除路径事务归属相反，偏离「batch_delete 原本自提交、与 maintenance 对称」的原设计。
  3. **回滚范围**：`except` 内 `self.db.rollback()` 回滚整个会话事务；当前调用方都在 service 返回后才写 AuditLog，故安全，但属脆弱顺序耦合（若先写 AuditLog 再调用 service 且 service 抛错，AuditLog 会被一并回滚）。
- **修复建议**：为 method 增加 docstring「调用方须在同一事务内 commit」；或保留内部 commit（路由再 commit 为 no-op，无副作用）；补充「直接调用 service 后须 commit」的单测，防止隐性回归。

### [LOW · 数据一致性] 6. 批量删除未清理 Comment/Favorite（孤儿累积，与 maintenance 不对称）
- **位置**：`workflow_service.py` 删除链未删 `Comment`/`Favorite`（仅 `maintenance_service` 清理）。
- **问题**：`Comment.episode_id`/`Favorite.episode_id` 为普通列（非 FK，已确认），删 Episode 不报 FK，但二者指向已删 Episode → 孤儿数据累积。
- **影响**：非崩溃，数据悬空。
- **修复建议**：`batch_delete_workflows` 同步清理 `Comment`/`Favorite`（与 maintenance 对齐）。

### [LOW · 边界] 7. rewriter.py `_resolve_rewrite_template` 文件名/正文启发式较弱
- **位置**：`rewriter.py` 约 75-90 行，用 `endswith(".txt") and "{" not in value` 区分文件名与模板正文。
- **问题**：若运营把不含 `{` 占位符的合法模板正文（如纯说明）或含 `{` 的异常文件名设为 `rewrite_template`，会被误判。弱启发式，极低概率误用。
- **修复建议**：改用显式前缀（如 `file:`）或 sentinel 区分；或在频道配置层约束取值。

### [LOW · 默认参数陷阱] 8. rewriter.py `_assemble_script(inject_date=True)`
- **位置**：`rewriter.py:1103` 默认 `True`；当前 2 处调用方均显式传入。
- **问题**：未来新增调用方若忘记传 `inject_date=False`，course 稿件会被错误注入「今天是…」时效播报，破坏讲解连贯性。
- **修复建议**：文档注明 course 必须传 `False`，或改为方法内部按 `channel_type` 决定（与 `get_style_hint` 一致）。

---

## 二、前端（Vue 3 / Element Plus）

### [LOW · 状态生命周期] 9. WorkflowList.vue 「跳过爬虫」开关跨触发不复位
- **位置**：`admin-web/src/views/workflow/WorkflowList.vue` `const skipCrawl = ref(false)`；`handleTrigger` 读取后未重置。
- **问题**：用户开启开关触发一次后，开关保持开启；切换频道或 `loadList` 刷新均不复位。若下次对新闻频道误开启，会按提示「可能因无素材失败」（运营自负），但易误触。
- **修复建议**：触发成功后 `skipCrawl.value = false` 复位（或按频道记忆）。

### [LOW · UX/逻辑] 10. ReviewList.vue 失败态「点击标题重试」实际需两次点击
- **位置**：`admin-web/src/views/mobile/ReviewList.vue` `toggleExpand`（210-222）+ `m-detail__err`（`v-else`）。
- **问题**：`toggleExpand` 先 `item.expanded = !item.expanded`（210 行）。加载失败后 `expanded=true`、`detail=null`；再次点标题 → `expanded=false`（收起），`m-detail__err` 随之消失（因在 `v-if="item.expanded"` 块内）；需第三次点击才真正重载。内联「点击标题重试」与「一次点击即收起」行为不符。
- **修复建议**：加载失败时 `toggleExpand` 直接重载而非 toggle（如 `if (item.expanded && item.detail === null) reload()`），或把重试入口绑在 err 块上。

### [LOW · 边界] 11. ReviewList.vue `size:50` 假设后端不截断
- **位置**：`ReviewList.vue:186` `size: 50`（对齐 `BATCH_MAX_SIZE=50`）。
- **问题**：前端「一键全部审批」依赖后端返回全部 50 条待审。若后端对 `size` 有隐性上限（<50）或实际待审 >50，则「全部审批」静默漏批。
- **修复建议**：确认后端 `listReviews` 接受 `size=50` 不截断；或前端分页累加后再批量审批。

### [INFO · 良好实践] 12. 以下改动实现正确，符合规范
- `ReviewList.vue`：驳回理由采集（`ElMessageBox.prompt`，取消即返回不改动）、`audio` 回退 `item.detail.audio_url || item.detail.hls_url`、`v-if/v-else-if/v-else` 加载链结构合法（已核实非缺陷）。
- `ManageQueue.vue`：队列编号复制 `navigator.clipboard` + `execCommand('copy')` 降级 + 失败兜底提示，符合移动端兼容规范（FE-227 / 无安全上下文降级）。
- `workflow.js` `triggerWorkflow(channelId, options)`：payload 条件组装，`skip_crawl`/`episode_date` 仅真值时发送，向后兼容。

---

## 三、结论汇总

| # | 文件 | 类别（用户关注点） | 定性 | 级别 |
|---|------|------------------|------|------|
| 1 | workflow_service.py 批量删除 | 边界条件 / 潜在 FK 异常 | 真缺陷 | MEDIUM→HIGH |
| 2 | maintenance_service.py:492 注释 | 与原有设计意图偏离（误导） | 真缺陷 | MEDIUM |
| 3 | rewriter.py 课程提示词加载 | 异常处理缺失 | 真缺陷 | MEDIUM |
| 4 | style_library.py 类型强制 | 逻辑不一致/设计偏离 | 真缺陷 | MEDIUM |
| 5 | workflow_service.py 未提交 commit 改动 | 事务契约/并发隐患 | 真缺陷（当前无崩溃） | MEDIUM |
| 6 | workflow_service.py 缺 Comment/Favorite | 数据一致性 | 真缺陷 | LOW |
| 7 | rewriter.py 文件名启发式 | 边界条件 | 真缺陷 | LOW |
| 8 | rewriter.py inject_date 默认 | 变量/默认陷阱 | 潜在隐患 | LOW |
| 9 | WorkflowList.vue skipCrawl | 状态生命周期 | 真缺陷 | LOW |
| 10 | ReviewList.vue 重试点击 | 边界/逻辑 | 真缺陷 | LOW |
| 11 | ReviewList.vue size:50 | 边界条件 | 潜在隐患 | LOW |

**建议修复优先级**：#1（对齐 episode_ids 收集，补 PlayLog 回归用例）→ #2（删矛盾注释）→ #3（课程提示词 try/except 兜底）→ #5（明确 commit 契约/补单测）→ #4/#9/#10/#11（设计对称与 UX）。#6/#7/#8 可在后续清理中一并处理。

**未提交改动提示**：`workflow_service.py`（#5 事务改动）、`ReviewList.vue`、`ManageQueue.vue` 当前在 working tree 未提交；建议评审结论落地后再统一提交。
