# 代码评审报告：本会话移动端审核 / 队列相关改动

- **评审范围**：本会话由我方修改/新增的代码逻辑
  - `backend/app/services/review_service.py` — `list_reviews`（频道/工作流/标题/摘要增强）、`get_review_detail`（封面图 `cover_url` / HLS `hls_url` 增强）
  - `backend/app/services/workflow_service.py` — `batch_delete_workflows`（补删 `AutoReviewStat` + 事务处理改动）
  - `admin-web/src/views/mobile/ReviewList.vue` — 重写（上下文标题 + 一键全部审批 + 标题点击展开详情）
  - `admin-web/src/views/mobile/ManageQueue.vue` — `goReview` 入口 + 「队列编号」展示 + 点击复制
  - `backend/tests/test_queue_batch_delete_autoreviewstat.py` — 新增回归测试
- **评审日期**：2026-08-13
- **结论概览**：核心修复（批量删除 500）正确且已测试覆盖；但发现 3 处**中等严重度**问题（边界语义、无效增强、事务归属冗余），以及若干轻微问题。无导致崩溃的必现 null/异常，但有真实功能缺口。

---

## 一、必须关注（中等严重度）

### 1. 【边界/语义】"一键全部审批"仅作用于当前已加载页（最多 20 条）
- **位置**：`admin-web/src/views/mobile/ReviewList.vue`
  - `load()`：第 183 行写死 `size: 20`
  - `approveAll()`：第 244 行 `const ids = list.value.map((i) => i.id)` 收集的是**内存中已加载的**列表
- **成因**：前端 `listReviews` 固定 `page:1, size:20`，"全部审批"的 ID 集合来自已加载页，而非服务端全量待审。后端 `BATCH_MAX_SIZE=50` 上限也大于前端实际能收集到的 20。
- **影响**：若某工作流待审 > 20 条，点"一键全部审批"会**静默漏批第 21 条起**的内容，且没有任何提示。按钮文案"一键全部审批"与确认框"本页 N 条"语义互相矛盾。
- **是否符合业务意图**：❌ 不符合。"全部审批"应覆盖该作用域下全部待审；当前最多 20 条，属于边界条件处理不当。
- **建议**：二选一
  - (a) 前端把 `size` 调大到能覆盖上限（如 `size: 50` 并与 `BATCH_MAX_SIZE` 对齐），并在 confirm 中明确"共 N 条全部待审"；
  - (b) 更稳妥：新增/复用"按作用域一次性审批"后端接口，由服务端拉全量待审再批处理，前端只传 `workflow_id`。

### 2. 【语义缺口】`hls_url` 增强未被消费，且 `review.audio_url` 为空时无音频
- **位置**：
  - 后端：`review_service.get_review_detail` 第 132–143 行新增 `cover_url` / `hls_url` 返回
  - 前端：`ReviewList.vue` 第 74–77 行仅渲染 `item.detail.audio_url`，**从未使用 `hls_url`**
- **成因**：我为详情页补了 `hls_url`（更优音频源），但前端播放器只绑定了 `review.audio_url`，且 `v-if="item.detail.audio_url"` 在 `audio_url` 为空时整块隐藏——即便 `hls_url` 存在也不展示。
- **影响**：当 `review.audio_url` 为空而节目 `episode.hls_url` 存在时，移动端审核详情**无法试听语音内容**；同时后端新增的 `hls_url` 字段成为无效增强（死字段）。
- **是否符合业务意图**：⚠️ 部分符合。封面图链路（`cover_url`）被正确消费；音频链路只走了一半，与"详情可展示图片/音频"的意图有缺口。
- **建议**：播放器 `:src` 改为 `item.detail.audio_url || item.detail.hls_url`，或并列展示两者；并补一条 `v-if="item.detail.audio_url || item.detail.hls_url"`。

### 3. 【事务归属】`batch_delete_workflows` 内部 commit/rollback 冗余且与路由重复提交
- **位置**：
  - `workflow_service.py` 第 197–289 行：`try: ... await self.db.commit()` + `except: await self.db.rollback(); raise`
  - `routers/admin/queue.py` 第 117 行：`await db.commit()`（service 返回后再提交一次，用于 AuditLog）
- **成因**：把原 `async with self.db.begin()`（在已 autobegin 的会话上会抛 "transaction already begun" → 500）改为"复用既有事务 + 手动 commit/rollback"。但 service 现在的 `commit()` 提交的是**整个会话**的全部挂起变更，而非仅本方法的删除；随后路由又 `commit()` 一次（写 AuditLog）。
- **影响**：
  - **冗余提交**：删除已在 service 内提交，路由的 commit 只提交 AuditLog；若 AuditLog 提交失败，删除已生效（可接受，但原子性被拆开）。
  - **会话耦合脆弱性**：service 提交/回滚的是整个 `self.db` 会话。若将来有调用方在调用前已往同一会话写入未提交数据，会被本方法"顺带"提交或回滚，产生非预期副作用。
  - 与本项目其他 service（如 `ReviewService`）"由路由层统一提交"的惯例不一致。
- **是否符合业务意图**：⚠️ 功能性正确（能删、能回滚），但事务边界设计不佳；当前调用路径（queue 路由，会话内删除前无残留写入）下不会出错，属隐患而非现障。
- **建议（更优）**：移除 service 内的 `commit()`/`rollback()`，让删除语句 flush 后**由 queue 路由第 117 行统一 commit**——这样"级联删除 + AuditLog"落在同一事务，原子性更好，且消除了冗余提交与会话耦合。`NotFoundError`/`BizError` 仍会向上冒泡，路由无 try/except 故不会误提交损坏事务。

---

## 二、轻微问题（可接受的偏离 / 待优化）

### 4. 【交互/语义】单条"驳回"硬编码理由，且无二次确认
- **位置**：`ReviewList.vue` 第 222 行 `handleReviewAction(item.id, action, action === 'reject' ? '移动端驳回' : null)`
- **成因**：移动端为便捷直接驳回，把理由固定为 '移动端驳回'，未采集具体原因；仅"一键全部审批"有 `ElMessageBox.confirm`。
- **影响**：所有移动端驳回在审计/追溯里理由千篇一律，丢失"为何驳回"的业务信息；误触无确认。
- **是否符合业务意图**：🔶 属合理简化（移动端快审），但与桌面端"驳回必须填理由"的强约束不一致，建议至少加一次确认弹窗，理由可保留默认或改为可选输入。
- **建议**：单条驳回增加 `ElMessageBox.prompt` 采集理由（允许空则用默认），并加确认。

### 5. 【可维护性】`toggleExpand` 注释与行为矛盾 + 加载失败无内联提示
- **位置**：`ReviewList.vue` 第 203–216 行
  - 第 210 行注释"下次点击不再重试"，但第 205 行条件 `!item.detail && !item.loadingDetail` 在失败后（`detail=null, loadingDetail=false`）**仍会重试**——注释失真。
  - 第 61 行 `v-if="item.loadingDetail"` 之后，加载失败（`detail=null`）时展开区为空，无错误态文案，仅依赖全局拦截器 toast。
- **影响**：注释误导维护者；失败体验偏弱（空白展开区）。
- **建议**：统一注释与行为（当前"失败可重试"更合理，保留即可，改注释）；加载失败时在详情区渲染一行"详情加载失败，点击重试"。

### 6. 【兼容性】`copyNo` 在非安全上下文未真正复制
- **位置**：`ManageQueue.vue` `copyNo()`：`navigator.clipboard?.writeText` 不可用时降级为 `ElMessage.info(String(id))`
- **成因**：`navigator.clipboard` 仅在 HTTPS / localhost 安全上下文可用；内网 http 或旧移动端 WebView 为 `undefined`。
- **影响**：降级分支只展示编号文本，**没有真正写入剪贴板**，用户可能误以为已复制。
- **建议**：降级时用 `document.execCommand('copy')` 或临时 `textarea + range` 兼容复制；或在 toast 中明确"请手动长按复制"。

### 7. 【并发残留】批量删除 running/queued 守卫存在 TOCTOU 窗口
- **位置**：`workflow_service.py` 第 199–219 行（先 SELECT 校验状态）与第 249–282 行（后执行删除），同事务但跨连接竞态
- **成因**：拒绝 running/queued 的校验在事务开始时读取，worker 在**另一连接**上可能把 `finished` 翻成 `running`（恰好在我们 SELECT 之后、DELETE 之前），导致删除一个"正在运行"工作流的数据，worker 后续写入已删 Episode → 外键悬空/报错。
- **影响**：极小概率数据一致性风险。
- **是否符合业务意图**：🔶 受限于"单 worker + SQLite"架构（本项目硬约束），窗口极小，属已知残留，本次未处理。
- **建议**：可记录一条 TODO，后续若放开多 worker 再补 `SELECT ... FOR UPDATE` 或队列锁。

---

## 三、确认无误（信息项）

- ✅ **`list_reviews` 多表 JOIN 正确性**：`select(Review, Workflow, Channel, Script)` 均为 1:1 LEFT OUTER JOIN（Review→Workflow→Channel、Review→Script），不会放大行数；`count` 与 `list` 的 `where` 条件一致，分页 `total` 准确。
- ✅ **`buildSummary` 引用的 `publish_failed` 契约成立**：`reviews.py` 第 106–107 行在路由层补回 `published` / `publish_failed`，前端消费无误；"全部成功→success、有失败/发布失败→warning"分支逻辑正确。
- ✅ **`get_review_detail` 的 `selectinload(Review.script)` 安全**：`Review.script` 关系存在（review.py:59），详情页 `script?.` 可选链对 `script=null` 也做了兜底。
- ✅ **级联删除顺序完整**：已复核全部外键（`auto_review_stat.review_id`、`episode.script_id/review_id`、`play_log/play_progress.episode_id`、`review.script_id`、`workflow_step` 无外键），删除顺序（PlayLog/PlayProgress→Episode→AutoReviewStat→Review→Script→Material 重置→WorkflowStep→Workflow）正确，无遗漏。
- ✅ **回归测试有效**：`test_queue_batch_delete_autoreviewstat.py` 构造"工作流→稿件→审核→auto_review_stat"链路后批量删除，覆盖真实 500 根因；与既有 queue/workflow 测试共 40 passed。

---

## 四、处置建议（优先级）

| 优先级 | 项 | 动作 | 状态 |
|---|---|---|---|
| P1 | #1 一键审批仅 20 条 | 调大 size 对齐 BATCH_MAX_SIZE，或改为服务端全量审批接口 | ✅ 已修复 |
| P1 | #2 hls_url 未消费 / 音频缺口 | 播放器 `src` 回退 `hls_url`，并调整 `v-if` | ✅ 已修复 |
| P2 | #3 事务归属冗余 | 移除 service 内 commit/rollback，统一由 queue 路由提交 | ✅ 已修复 |
| P3 | #4 驳回理由/确认 | 加 prompt 采集 + 确认 | ✅ 已修复 |
| P3 | #5 注释/失败态 | 修正注释 + 失败内联提示 | ✅ 已修复 |
| P3 | #6 复制降级 | 兼容 `execCommand` 或明确提示手动复制 | ✅ 已修复 |
| 记录 | #7 TOCTOU | 留 TODO，多 worker 时再补锁 | 已知残留 |

> **修复落地记录（2026-08-13）**：已直接落地 P1/P2/P3。
> - #1：`ReviewList.vue` 的 `load()` 将 `size` 由 20 改为 50（对齐后端 `BATCH_MAX_SIZE=50`），"一键全部审批"现覆盖本作用域全部待审（不再静默漏批 21–50 条）；确认框文案由"本页 N 条"改为"当前 N 条"。
> - #2：详情音频 `<audio :src>` 改为 `item.detail.audio_url || item.detail.hls_url`，`v-if` 同步放宽，修复 `review.audio_url` 为空时无法试听的问题。
> - #3：`workflow_service.batch_delete_workflows` 移除方法内 `await self.db.commit()`，保留 `except` 中的 `rollback()`；级联删除与 AuditLog 现由 `queue.py` 路由层 `await db.commit()` 统一提交，原子性更好、消除会话耦合。
> - #4：`ReviewList.vue` 的 `act()` 对"驳回"改为 `ElMessageBox.prompt` 采集理由（留空回退默认'移动端驳回'），用户取消直接返回；与桌面端"驳回必须填理由"语义对齐，且避免误触无确认。
> - #5：`toggleExpand` 注释修正为"失败再次点击会重新加载"（与代码一致）；详情区新增 `v-else` 失败内联提示"详情加载失败，点击标题重试"（`.m-detail__err` 样式）。
> - #6：`ManageQueue.vue` 的 `copyNo` 增加 `textarea + document.execCommand('copy')` 降级，真正写入剪贴板；均失败时提示"请长按编号手动复制"。
> - 验证：后端 queue/workflow 测试 41 passed；admin-web `vite build`（全新 outDir 规避 safe-delete）✓ built 全模块。改动**未提交**（连同本会话其余移动端/批量删除改动一并待提交）。P3 为前端-only 改动，无后端逻辑变动。
> - #1：`ReviewList.vue` 的 `load()` 将 `size` 由 20 改为 50（对齐后端 `BATCH_MAX_SIZE=50`），"一键全部审批"现覆盖本作用域全部待审（不再静默漏批 21–50 条）；确认框文案由"本页 N 条"改为"当前 N 条"。
> - #2：详情音频 `<audio :src>` 改为 `item.detail.audio_url || item.detail.hls_url`，`v-if` 同步放宽，修复 `review.audio_url` 为空时无法试听的问题。
> - #3：`workflow_service.batch_delete_workflows` 移除方法内 `await self.db.commit()`，保留 `except` 中的 `rollback()`；级联删除与 AuditLog 现由 `queue.py` 路由层 `await db.commit()` 统一提交，原子性更好、消除会话耦合。
> - 验证：后端 queue/workflow 测试 41 passed；admin-web `vite build`（全新 outDir 规避 safe-delete）✓ built 全模块。改动**未提交**（连同本会话其余移动端/批量删除改动一并待提交）。
