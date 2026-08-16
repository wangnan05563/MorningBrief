# 本会话修改代码逻辑走查报告

- **日期**：2026-08-05
- **模式**：增量审查（本会话修改文件，git diff 比对）
- **覆盖范围**：
  - 后端（news-backend-code-review）：`ai_budget.py`、`ai_config_service.py`、`workflow_scheduler.py`、`ffmpeg_wrapper.py`、`concat.py` 及对应测试
  - 前端（news-frontend-code-review）：`admin-web/src/views/about/About.vue`
- **审查结论**：无阻塞级（CRITICAL/必须修复）问题；1 项 HIGH 硬约束命中为**有意的、已文档化的偏离**，附改进建议；其余为良好实践与低优先级提示。

---

## 一、后端走查（news-backend-code-review）

### 1.1 硬约束扫描结果（按 config.yaml hard_constraints）

| 约束名 | 级别 | 命中 | 说明 |
|--------|------|------|------|
| `create_task_no_reference` | CRITICAL | ❌ 未命中 | 本代码用 `loop.create_task(...)`（非 `asyncio.create_task`），且引用通过模块级 `_db_usage_tasks` 集合保留，**满足"防 GC 回收"意图** |
| `datetime_now_no_tzinfo` | HIGH | ✅ 命中 | `ai_config_service.py:1038` `created_at=datetime.now()` —— **有意偏离，见 F-01** |
| `async_def_without_await` | HIGH | ❌ 未命中 | `_persist_usage_to_db` 含 `await svc.record_usage(...)` |
| `sync_io_in_async` / `sync_requests_in_async` | CRITICAL | ❌ 未命中 | 无 `time.sleep` / `requests.*` |
| `exception_log_warning_fstring` | HIGH | ❌ 未命中 | `_persist_usage_to_db` 用 `logger.warning("...", exc_info=True)`，无 f-string 拼 `{e}` |
| `bare_except_pass` | HIGH | ❌ 未命中 | `_persist_usage_to_db` 捕获 `Exception` 并 `exc_info=True` 记录，非裸 except |
| `builtin_exception_shadowing` | HIGH | ❌ 未命中 | `StitchError` 为项目自定义异常（`ffmpeg_wrapper.py:30`）；`RuntimeError` 为正确复用内置类 |
| `timezone_consistency` / `ai_budget_timezone` | CRITICAL | ❌ 未命中 | 未使用 `datetime.now(timezone.utc)`；未向 `ai_budget` 注入 UTC |
| `finally_unconditional_release` | CRITICAL | ❌ 未命中 | 变更代码无锁释放 |

### 1.2 发现项

#### F-01 【HIGH · 硬约束命中 · 有意偏离】`created_at=datetime.now()`（本地 naive 时间）

- **位置**：`backend/app/services/ai_config_service.py:1038`（本次新增）
- **命中规则**：`datetime_now_no_tzinfo`（HIGH，`block_on_violation: true`），规则要求改用 `utcnow_naive()` 统一 naive UTC 存储。
- **为什么是有意偏离（且正确）**：
  - 根因是 `AIUsageLog.created_at` 模型的 `server_default=func.now()` 在 SQLite 下返回 **UTC**，而 `get_usage_summary()` 的"今日"区间用 `datetime.combine(date.today(), time.min)` —— **本地 naive 日期**切分。二者相差约 8 小时，导致"今日"归属偏差。
  - 项目**整体约定用本地日期做"按日"分桶**：`ai_budget._today_key()` 用本地日期；`rewriter/crawler/scheduler` 均按本地日期筛选（`ai_budget_timezone` CRITICAL 规则明确要求 daily reset 用本地时间，UTC 会导致跨日额度累加错误）。
  - 因此此处**显式存储本地 naive 时间**，与查询端的本地日期切分保持内部一致，是修复该 bug 的正确选择。若强行改用 `utcnow_naive()`（UTC），反而会与 `get_usage_summary` 的本地边界重新产生约 8h 偏差。
- **改进建议（二选一，均不阻塞）**：
  1. **推荐**：在 `app/core/timeutil.py` 新增 `localnow_naive()` 助手（与现有 `utcnow_naive()` 对称），此处改为 `created_at=localnow_naive()`。既消除硬约束命中，又让"本地时间"意图显式化、可被复用。
  2. 维持现状，保留现有注释（已说明 UTC vs 本地偏差），作为**已文档化的有意偏离**备案。

#### F-02 【PASS · 修复正确】`_run_step` 捕获 `asyncio.CancelledError`（`workflow_scheduler.py:1114`）

- Python 3.14 中 `CancelledError` 继承自 `BaseException`，`except Exception` 无法捕获。步骤协程被取消（外部取消工作流任务）时会逃逸到任务层，导致 workflow 以**空 error、空 failed_step 静默失败** —— 正是 Aug 5「220 workflow.failed / 0 步骤完成 / 空错误」的根因。
- 新增 `except asyncio.CancelledError`（位于 `except Exception` 之前，顺序正确），记录 `exc_info`、置为可读失败（"步骤 X 被取消"）、`break`（取消不可重试）。**修复正确且必要**。
- 同文件补充 `exc_info=True`（重试日志 + 最终失败日志），显著提升可诊断性。
- **小提示（LOW）**：该 except 分支注释写"可能单步超时 {step_timeout}s"，但 `asyncio.wait_for` 超时实际抛出 `TimeoutError`（被下方 `except Exception` 捕获），此分支主要覆盖**外部取消**任务的情形。注释建议改为"任务被外部取消（wait_for 超时走 TimeoutError 分支）"以避免误导。

#### F-03 【PASS · 修复正确】`run_ffmpeg` 启动异常上抛 `StitchError`（`ffmpeg_wrapper.py:41`）

- 原代码 `await asyncio.create_subprocess_exec(...)` 未捕获，若启动阶段抛异常（句柄耗尽 / 路径异常 / child watcher 未挂载），其 `str()` 可能为空，导致上层只记录到空错误、无法定位 stitch 失败根因（Aug 4 模式）。
- 现包 try/except 并统一转 `StitchError(f"FFmpeg 启动失败({type(exc).__name__}): {exc} | cmd=...")`，`StitchError` 为项目既有异常类。**修复正确**。

#### F-04 【PASS · 修复正确】`concat.py` 频道级参数修复

- `_resolve_channel_bgm`：`gap_sec` 区分"未配置(None)"与"显式配置为 0" —— 原 `or 0.5` 会把合法的 `0.0` 兜底成 `0.5`，导致"段间静音=0 无停顿"在全局配置下失效（`concat.py:90`）。
- `concat()`：`_get_duration_range(channel_id)` → `_get_duration_range(_min_dur)`。原实现把 `channel_id`（小整数）误当作 `min_duration_sec` 传入，导致**频道级最短时长配置完全失效且把频道 ID 大小当成秒数下限**（`concat.py:323`）。
- 验证：`channel_min_duration` 由 `_resolve_channel_bgm` 解析并作为第 5 返回值传出，`concat` 解包为 `_min_dur` 传入，**链路完整无 NameError**。

#### F-05 【PASS · 设计合理】`record_call` fire-and-forget 落库（`ai_budget.py`）

- `_dispatch_db_usage`：仅当 `asyncio.get_running_loop()` 存在才派发，同步/CLI 上下文安全跳过；`_DB_USAGE_DISPATCH_ENABLED = "pytest" not in sys.modules` 在测试环境禁用，避免异步测试污染真实 DB / 产生 pending-task 告警。
- 任务引用通过模块级 `_db_usage_tasks` 集合 + `add_done_callback` 保活，**避免被 GC 静默丢弃**（asyncio 不持有 `create_task` 结果的强引用）。
- `_persist_usage_to_db` 用独立 `AsyncSessionLocal()` 会话调 `record_usage`，写库失败仅 `logger.warning(exc_info=True)` 不向上抛 —— 符合"统计不得拖垮主生成流程"的设计意图。

#### F-06 【LOW · 性能/可观测性提示】每笔 AI 调用开一个独立 DB 会话

- fire-and-forget 每成功调用（TTS 峰值 ~60/min）打开/关闭一个 `AsyncSessionLocal()` 会话。SQLite WAL + `busy_timeout=5000` 可承受，但属短连接密集写入。
- 建议：可作为后续优化（如按秒/batch 合并写库）；当前为统计用途，非阻塞路径，优先级低。
- 另：`_persist_usage_to_db` 吞掉所有异常仅 warning，长期若持续失败不易察觉。建议增加"连续失败计数"或 periodic 汇总日志（非阻塞）。

### 1.3 良好实践

- 注释清晰解释"为什么"（时区偏差、GC 保活、测试环境禁用派发），符合项目"注释解释 why"规范。
- `record_call` 同步签名保持不变，存量同步测试零回归（15→16 项测试通过）。
- 错误日志统一补 `exc_info=True`，保留 traceback。

---

## 二、前端走查（news-frontend-code-review）

### 2.1 范围与字段契约

- 本次前端会话改动仅 `admin-web/src/views/about/About.vue`（关于页版本/发布时间展示修复）。
- **字段契约（维度 8）**：后端返回 `published_at`（snake_case），前端读取 `res.published_at`（snake_case），**前后端一致，无 camelCase 转换**，合规。

### 2.2 发现项

#### FE-01 【PASS】`_formatPublishedAt(iso)` 时区转换正确

- 将 GitHub ISO（UTC，带 `Z`）转为 UTC+8 日期：`new Date(iso)` → `+8h` → 取 `getUTCFullYear/Month/Date`。
- 对非法输入 `Number.isNaN(d.getTime())` 返回 `''`，防御性好。
- **小提示（LOW）**：依赖 GitHub `published_at` 为带 `Z` 的 UTC ISO。若未来某数据源返回**本地 naive 时间**（无 `Z`），`new Date` 会按本地解析，再 `+8h` 会**重复偏移**。建议在注释中明确"假定输入为 UTC ISO（含 Z）"。

#### FE-02 【PASS】`performCheck` 新增分支逻辑正确

- 原 `if (res.latest)`（有新版）→ 展示"有新版本"，副标题显示真实发布日。
- 新增 `else if (res.source === 'remote' && res.published_at)`（已是最新但拿到远端发布时间）：把当前版本"发布于"替换为 release 真实发布日，避免显示过期的 `build_date` 硬编码值。
- 定时器管理与既有 `else` 分支一致：设置前先 `clearTimeout(latestTimer)`，3s 后仅在仍为 `latest` 时回退 `idle`，避免覆盖 `newer/error` 终态，**无定时器堆叠/泄漏**。
- `onUnmounted`（line 390-402）清理 `latestTimer` 与 `mountDelayTimer`，**生命周期配对正确**（维度 9）。

#### FE-03 【LOW · UX 提示】按钮内嵌 span 点击

- `update-sub` span 位于 `el-button` 内，点击该 span 会因事件冒泡触发 `openRelease`。属可接受的预期行为，无需修改。

### 2.3 良好实践

- 纯函数 `_formatPublishedAt` 无副作用、有防御；新增样式 `.update-sub` 仅做视觉弱化，未引入 `console.log`/`debugger`（维度 14 合规）。

---

## 三、测试与验证状态

- 新增/修改测试：`test_ai_budget.py`（+`test_record_call_dispatches_db_usage`）、`test_ai_config_service.py`（+2 项聚合/写库测试）。
- 目标测试 `test_ai_budget.py` + `test_ai_config_service.py`：**16 passed**。
- 全量后端套件：**369 passed，0 failed**。
- `py_compile` 通过（ai_budget.py / ai_config_service.py）。

---

## 四、范围说明（不在本会话改动内）

以下工作树已修改文件**不属于本会话对话的改动**，未纳入本次走查（属其他任务：队列批量删除、音频管理、构建脚本等）。如需对它们做同样的走查，请另行指定：

- 后端：`config.py`、`_build_info.py`、`routers/admin/audio.py`、`routers/admin/queue.py`、`services/queue_service.py`、`middleware/path_prefix.py`
- 前端：`api/audio.js`、`api/queue.js`、`channel/ChannelManagement.vue`、`queue/QueueManagement.vue`、`workflow/WorkflowDetail.vue`、`miniprogram/*`
- 脚本：`build-exe.ps1`、`push_to_github.ps1`、`start.ps1`、`build_info.py`、`VERSION`

---

## 五、结论

本会话修改的代码逻辑**整体健康，无阻塞级缺陷**：

1. AI 用量落库链路（根因修复）设计合理，引用保活与测试环境隔离到位；
2. 频道静音相关三处修复（gap_sec 0 值区分、`_get_duration_range` 参数修正、`CancelledError` 捕获、StitchError 上抛）均正确，直击 Aug 4–5 静默失败根因；
3. 前端 About.vue 版本/发布日展示修复字段契约一致、定时器生命周期正确。

**唯一需决策项（F-01）**：`created_at=datetime.now()` 命中 HIGH 硬约束，但为与项目本地日期分桶约定保持一致的有意偏离。建议按 F-01 建议新增 `localnow_naive()` 助手以消除 lint 命中并使意图显式化（非阻塞）。
