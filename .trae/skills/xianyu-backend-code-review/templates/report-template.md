# 闲鱼猎人后端代码审查报告

## 基本信息

- **审查版本**：v2.0.0
- **审查模式**：[全量审查 / 增量审查 / 指定文件审查 / 片段评审]
- **审查范围**：`src/xianyu_hunter/**/*.py`
- **审查文件数**：X 个
- **审查时间**：YYYY-MM-DD HH:MM:SS
- **审查人**：xianyu-backend-code-review Skill
- **上次审查**：[有/无]

## 相对于上次审查的变化

| 状态 | 数量 | 说明 |
|------|------|------|
| 🆕 新增 | X | 本次新发现的问题 |
| ✅ 已修复 | X | 上次存在的问题已修复 |
| ⚠️ 仍存在 | X | 上次存在的问题仍未修复 |

## 审查结果摘要

- 🔴 阻塞问题：X 个（必须修复）
- 🟠 严重问题：X 个（强烈建议修复）
- 🟡 警告问题：X 个（建议修复）
- 🟢 优化建议：X 个（可选）

### 按 severity 分布

| Severity | 数量 |
|----------|------|
| CRITICAL | X |
| HIGH | X |
| MEDIUM | X |
| LOW | X |
| INFO | X |

### 按 category 分布（29 维度）

| Category | 数量 |
|----------|------|
| security | X |
| sqlite_optimization | X |
| sqlalchemy | X |
| async_scheduler | X |
| ... | X |

## 硬约束合规性检查结果

| 硬约束规则 | 状态 | 违规位置 |
|------------|------|----------|
| `hmac_compare_digest_for_token` | ✅ 通过 / ❌ 违规 | - |
| `no_hardcoded_credentials` | ✅ 通过 / ❌ 违规 | - |
| `no_credentials_in_config_yaml` | ✅ 通过 / ❌ 违规 | - |
| `bare_except_pass` | ✅ 通过 / ❌ 违规 | - |
| `no_devnull_redirect_for_webview2` | ✅ 通过 / ❌ 违规 | - |
| `create_no_window_flag` | ✅ 通过 / ❌ 违规 | - |
| `deprecated_utcnow` | ✅ 通过 / ❌ 违规 | - |
| `staticpool_usage` | ✅ 通过 / ❌ 违规 | - |
| `missing_module_level_imports` | ✅ 通过 / ❌ 违规 | - |
| `pydantic_v1_dict_method` | ✅ 通过 / ❌ 违规 | - |
| `missing_hf_endpoint` | ✅ 通过 / ❌ 违规 | - |

**合并结论**：[允许合并 / 阻止合并（存在 CRITICAL 违规）]

## 详细问题列表

### 🔴 阻塞问题（必须修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`src/xianyu_hunter/web/routes/api_xxx.py` 第 X 行
   - **当前代码**：
     ```python
     # 问题代码示例
     ```
   - **修复建议**：
     ```python
     # 修复后的代码示例
     ```
   - **参考规范**：[对应 SKILL.md 维度章节]

### 🟠 严重问题（强烈建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
   - **修复建议**：[具体建议]

### 🟡 警告问题（建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
   - **修复建议**：[具体建议]

### 🟢 优化建议（可选）

1. **建议描述**：[具体建议]
   - **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
   - **优化方案**：[具体方案]

## ✅ 好的实践

- [正面反馈：列出本次审查中发现的好实践]
  - 例如：`hmac.compare_digest()` 正确使用
  - 例如：SQLite 引擎正确配置 `NullPool` + WAL
  - 例如：ChatbotOrchestrator 设计无请求级状态

## 测试运行结果

- **测试命令**：`pytest tests/ -x`
- **测试结果**：[通过 / 失败]
- **测试覆盖**：[覆盖率]

## 审查结论

- [ ] 通过（无阻塞问题）
- [ ] 有条件通过（仅警告和提示级别问题）
- [ ] 不通过（存在阻塞或严重问题）

## 修复验证

修复完成后，请重新运行审查确认问题已解决：

```powershell
# 1. 重新运行快速自检
pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1

# 2. 重新运行人工评审
# 调用 xianyu-backend-code-review 技能
```

## 报告归档

报告保存路径：`.trae/skills/xianyu-backend-code-review/reports/YYYY-MM-DD_HHmmss_[full|incremental]_report.md`

---

## 🆕 v4.28.0 四维度复盘

> 基于 [`docs/standards/四维度复盘方法论与历史教训集成.md`](../../../../docs/standards/四维度复盘方法论与历史教训集成.md) 的四维度框架，对本次审查的发现进行结构化复盘，沉淀可复用的工作流模板。

### 维度 1：成功执行任务的完整步骤

- 本次审查在 `XXX` 类目下识别出 `N` 个问题，其中 `M` 个被成功闭环
- 关键成功路径（按时间顺序）：
  1. `step 1`: ...
  2. `step 2`: ...
- 复用已有方法/工具：xxx

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 关键路径异常被吞 | 外层 except 用 `logger.warning(f"...{e}")` | 启动失败无法定位 | 异常堆栈丢失 | 改用 `logger.exception()` |
| 多迁移块被外层 try 包裹 | `run_migrations` 一个 try 包裹 C-01~C-05 | 后续迁移块被跳过 | 外层吞异常 | 每个迁移块独立 try/except |
| 批处理熔断后无 `save_progress()` | `consecutive failure >= 3` 后 `break` | 剩余商品永久 skipped | 熔断分支未持久化 cursor | 熔断时调用 `_save_progress()` |
| asyncio.create_task 无引用 | `asyncio.create_task(coro)` 裸调用 | 协程被 GC 回收 | 局部变量无生命周期 | 改 `self._task = asyncio.create_task(coro)` |
| aware/naive datetime 相减 | `_utcnow() - row.created_at` | 抛 `TypeError` | SQLite 默认 naive + 应用层 aware | `.replace(tzinfo=None)` 对齐 |
| 跨模块访问 _Session 私有属性 | `repo._session()` | `AttributeError` | 类内为 `_session` 私有 | 改 `repo.get_session()` 公共方法 |
| 30 秒 TTL 缓存兜底跨进程 | `cache_ttl_seconds=30` | 状态显示延迟 30s | 跨进程未 SSE 推送 | 改 `invalidate_cache()` + SSE |
| 布尔字段初始值被误读 | `last_session_invalid=False` | 状态闪烁 | False ≠ 未检测 | 加 `_last_m5tk_refresh > 0` 标记 |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 对应工作流元规范 | 核心判断信号 | 落地配置节点 |
|------|------------------|--------------|--------------|
| 错误处理决策树 | meta-rule #21 | `grep "except" <file>` 关键路径缺 `logger.exception()` | `workflow_meta_rules_backend.error_handling_decision_tree.critical_path_patterns` |
| 批处理熔断模板 | meta-rule #22 | `grep "consecutive failure" <file>` 无 `save_progress()` | `workflow_meta_rules_backend.batch_circuit_breaker_backend.required_persist_keys` |
| 资源生命周期 | meta-rule #23 | `grep "asyncio.create_task"` 未赋值实例属性 | `workflow_meta_rules_backend.resource_lifecycle_backend.required_task_holders` |
| 跨进程状态同步 | meta-rule #24 | `grep "cache_ttl_seconds" <file>` 跨进程状态 | `workflow_meta_rules_backend.state_sync_workflow_backend.single_source_of_truth_sources` |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 错误处理决策树 | `_on_startup` / `run_migrations` / `_init_*` / API 路由 try-except | 性能 hot path / 测试代码（`pytest.raises`） |
| 批处理熔断模板 | `BatchRefreshScheduler` / `AutoLoginScheduler` / 长任务 / 断点续传 | 实时单次请求 / 幂等小批量（≤3 个）/ 用户主动取消（走 stopped 分支） |
| 资源生命周期 | Playwright Page/Browser / httpx/aiohttp ClientSession / asyncio.Task / asyncio.Lock / SQLAlchemy Session | 短生命周期对象 / 测试 mock / `with` 语句（自动管理） |
| 跨进程状态同步 | `CookieRotator` / `Scheduler._job_states` / `TaskRow.status` 等跨进程读写 | 同进程单例状态 / 一次性函数返回值 |

## 🆕 v4.28.0 工作流元规范触发

> 本次审查触发的元规范编号（与 xianyu-hunter-dev/references/meta-rules.md #21-24 对应）。每条触发需指明：触发规则名、对应 config.yaml 配置节点、违规位置、修复方式。

| 触发编号 | 元规范名称 | 触发规则 | 配置节点 | 违规位置 | 修复方式 |
|----------|------------|----------|----------|----------|----------|
| #21 | 错误处理决策树 | B-REVIEW-WF-ERROR-HANDLING | `workflow_meta_rules_backend.error_handling_decision_tree.forbidden_critical_path_patterns` | `src/xianyu_hunter/web/startup.py:L45` | 改用 `logger.exception()` 输出 traceback |
| #22 | 批处理熔断模板 | B-REVIEW-WF-BATCH-CIRCUIT-BREAKER | `workflow_meta_rules_backend.batch_circuit_breaker_backend.detect_patterns` | `src/xianyu_hunter/collector/batch_refresh_scheduler.py:L95` | 熔断时调用 `_save_progress()` |
| #23 | 资源生命周期 | B-REVIEW-WF-RESOURCE-LIFECYCLE | `workflow_meta_rules_backend.resource_lifecycle_backend.required_task_holders` | `src/xianyu_hunter/xxx.py:L123` | 改 `self._task = asyncio.create_task(coro)` |
| #24 | 跨进程状态同步 | B-REVIEW-WF-STATE-SYNC | `workflow_meta_rules_backend.state_sync_workflow_backend.forbidden_ttl_patterns` | `src/xianyu_hunter/cookie/store.py:L67` | 显式 `invalidate_cache()` + SSE 推送 |

## 🆕 v4.28.0 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则，仅调整阈值/白名单/关键字等参数化配置，不引入新的硬编码业务值。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 阈值调整 | `workflow_meta_rules_backend.batch_circuit_breaker_backend.failure_threshold` | `3` | `5` | 现有 3 次不足以应对浏览器冷启动 | 批处理熔断（meta-rule #22） |
| 白名单新增 | `workflow_meta_rules_backend.error_handling_decision_tree.critical_path_patterns` | `[startup_, migrate_, init_, _on_startup$, run_migrations$]` | 同左 + `[setup_, bootstrap_]` | 补齐其他关键路径前缀 | 错误处理决策树（meta-rule #21） |
| 必填字段新增 | `workflow_meta_rules_backend.batch_circuit_breaker_backend.required_persist_keys` | `[batch_id, cursor, completed_ids, remaining_ids]` | 同左 + `[paused_at, pause_reason, total_count, last_error]` | 续传调试需要时间戳与原因 | 批处理熔断（meta-rule #22） |
| 资源类型新增 | `workflow_meta_rules_backend.resource_lifecycle_backend.required_holder_patterns` | `[Page, ClientSession, AsyncClient, Task, Lock, Session]` | 同左 + `[Browser, Context, Engine, Connection]` | 补齐其他可注册资源 | 资源生命周期（meta-rule #23） |
| 模式新增 | `workflow_meta_rules_backend.state_sync_workflow_backend.forbidden_ttl_patterns` | `[cache_ttl_seconds=30/60]` | 同左 + `[cache_ttl_seconds=120, last_update.*<.*seconds]` | 扩展检测粒度 | 跨进程状态同步（meta-rule #24） |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] SKILL.md 附录 C 的 30 维度与本变更一致
- [ ] references/version-changelog.md 已追加 v4.28.0 变更说明

## 🆕 v4.30 跨边界访问契约

> 跨边界访问必须明确契约，不能依赖隐式约定。与 xianyu-hunter-dev/references/coding-standards.md §2.11-2.14 配套。

### 跨边界契约检查（后端侧）

| 边界类型 | 契约内容 | 配置节点 | 检查工具 |
|----------|----------|----------|----------|
| DB → 应用 | 应用层 `aware datetime` 与 DB 读回 `naive datetime` 运算前必须 `.replace(tzinfo=None)` | `cross_boundary_contract.datetime_tz_consistency.project_tz_strategy` | B-REVIEW-DATETIME-TZ-CONSISTENCY |
| 类 → 外部模块 | 禁止跨模块访问 `repo._session` 私有属性 | `cross_boundary_contract.private_attr_encapsulation.external_object_prefixes` | B-REVIEW-PRIVATE-ATTR-ENCAPSULATION |
| 命名一致性 | 实例属性 snake_case（`self._session`），禁止 `self._Session` 大小写变体 | `cross_boundary_contract.naming_consistency.instance_attr_case` | B-REVIEW-NAMING-CONSISTENCY |
| 跨进程序列化 | `datetime.isoformat()` 必须保留 tzinfo，禁止 `datetime.now().isoformat()` | `cross_boundary_contract.datetime_tz_consistency.recommended_isoformat_patterns` | B-REVIEW-DATETIME-TZ-CONSISTENCY |

## 🆕 v4.38.0 编码规范防御性复盘报告条目（B-REVIEW-182~188）

> 本节为 v4.38.0 新增 7 项 B-REVIEW 检查点（meta-rules #57-63 后端落地）的报告条目模板。每条违规按以下格式记录，参数在 `config.yaml#meta_rules_57_63` 节点管理。

### B-REVIEW-182 ASYNC-AWAIT-STATIC-CHECK 异步方法静态校验

```
### 🔴 [CRITICAL] B-REVIEW-182：async def 方法体内缺少 await 表达式

- **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
- **当前代码**：
  ```python
  async def _finalize_run(self, stats: RunStats, new_items: list[ItemSummary] | None) -> None:
      # 全同步操作，无 await
      self._save_stats(stats)
      self._notify_done(new_items)
  ```
- **问题**：`async def` 方法体内不含 `await` 表达式，Python 3.14 优化后返回 None，调用点 `await self._finalize_run(...)` 触发 `TypeError: object NoneType can't be used in 'await' expression`
- **修复建议**：将 `async def` 改为同步 `def`，调用点同步移除 `await`
- **配置节点**：`meta_rules_57_63.async_await_check`
- **规范引用**：meta-rule #57 / xianyu-hunter-dev v4.38.0 step 189
- **适用**：Python 3.11+ 异步代码，尤其是被 `await` 调用的方法
- **不适用**：`@abstractmethod` 接口定义、`__aenter__`/`__aexit__` 上下文管理器、async generator
```

### B-REVIEW-183 RESOURCE-POOL-BENCHMARK 资源池性能基准

```
### 🟡 [WARNING] B-REVIEW-183：资源池配置缺少性能基准 docstring

- **位置**：`src/xianyu_hunter/db/db_models.py` 第 X 行
- **当前代码**：
  ```python
  engine = create_engine(
      f"sqlite:///{db_path}",
      poolclass=NullPool,  # 无 docstring 说明，每次连接执行 PRAGMA ~100ms
  )
  ```
- **问题**：`poolclass=NullPool` 选择缺少 docstring 说明性能基准数据，NullPool 每次新建连接执行 5 条 PRAGMA ~100ms，慢查询日志显示系统层开销 > 50ms
- **修复建议**：改为 `QueuePool` 复用连接，docstring 记录对比数据（NullPool 231ms → QueuePool 11.9ms，19x 提升）
- **配置节点**：`meta_rules_57_63.resource_pool_benchmark`
- **规范引用**：meta-rule #58 / xianyu-hunter-dev v4.38.0 step 190
- **适用**：所有资源池选择（NullPool/QueuePool/StaticPool）
- **不适用**：测试环境（用 StaticPool 保证隔离）、单次请求资源
```

### B-REVIEW-184 HTTP-STATUS-CODE-MAPPING HTTP 状态码语义映射

```
### 🔴 [CRITICAL] B-REVIEW-184：多原因 None 一律映射同一状态码

- **位置**：`src/xianyu_hunter/services/collection_service.py` 第 X 行
- **当前代码**：
  ```python
  if detail is None:
      raise CollectionError(410, f"Failed to collect item {item_id}: detail page unavailable or item removed")
  # 但 detail() 返回 None 有 10+ 原因（cookie 失效/反爬/页面关闭/真正下架）
  ```
- **问题**：底层 `detail()` 返回 None 有 10+ 原因，但上游一律映射为 410，前端无法区分"cookie 过期需重新登录"与"商品真正下架"
- **修复建议**：建立 `_DETAIL_FAILURE_STATUS_MAP: dict[str, int]` 映射表，底层设置 `last_detail_failure_reason`，上游按映射查找状态码
- **配置节点**：`meta_rules_57_63.http_status_code_mapping`
- **规范引用**：meta-rule #59 / xianyu-hunter-dev v4.38.0 step 191
- **适用**：所有 HTTP 错误响应；多原因返回 None/错误的底层模块
- **不适用**：唯一原因的错误码（如 404 仅表示资源不存在）
```

### B-REVIEW-185 CSS-SELECTOR-FALLBACK CSS 选择器降级链

```
### 🔴 [CRITICAL] B-REVIEW-185：第三方网站 DOM 选择器缺少降级链

- **位置**：`src/xianyu_hunter/collector/_detail.py` 第 X 行
- **当前代码**：
  ```javascript
  let tabs = document.querySelectorAll('[class*="tabItem"]');  // 单一选择器，闲鱼改版 className 后失效
  ```
- **问题**：第三方网站 DOM 选择器单一，闲鱼改版 className 后 `on_sale=0 sold=0` 误报
- **修复建议**：添加 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描）
- **配置节点**：`meta_rules_57_63.css_selector_fallback`
- **规范引用**：meta-rule #60 / xianyu-hunter-dev v4.38.0 step 192
- **适用**：第三方网站 DOM 解析（闲鱼/淘宝/第三方 API 返回 HTML）
- **不适用**：自有代码 DOM、ID 选择器、data-* 属性选择器、后端 API JSON 解析
```

### B-REVIEW-186 EXCEPTION-LOG-SEMANTIC 异常日志语义完整性

```
### 🔴 [CRITICAL] B-REVIEW-186：except 块内使用 logger.warning 丢失 traceback

- **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
- **当前代码**：
  ```python
  except Exception as e:
      logger.warning(f"操作失败: {e}")  # 丢失 traceback，定位问题困难
  ```
- **问题**：except 块内使用 `logger.warning(f'...{e}')` 丢失 traceback，关键路径定位问题耗时 30+ 分钟才能复现
- **修复建议**：改用 `logger.exception("操作失败")` 自动保留完整 traceback
- **配置节点**：`meta_rules_57_63.exception_log_semantic`
- **规范引用**：meta-rule #61 / xianyu-hunter-dev v4.38.0 step 193
- **适用**：所有异常处理代码，尤其是关键路径（启动/迁移/初始化）
- **不适用**：纯性能日志（无异常场景）、DEBUG 级别日志、非 except 块的 warning
```

### B-REVIEW-187 EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期

```
### 🔴 [CRITICAL] B-REVIEW-187：外部传入资源未配对 register/unregister

- **位置**：`src/xianyu_hunter/services/collection_service.py` 第 X 行
- **当前代码**：
  ```python
  async def collect(self, item_id: str, reuse_page: Page | None = None):
      # 外部传入 page 但未注册，被采集器误关
      page = reuse_page or await self.container.browser.new_page()
      await self._collect_with_page(page)
  ```
- **问题**：外部传入的 Page 未注册，并发采集时 page 被主流程关闭
- **修复建议**：配对调用 `register_external_page`/`unregister_external_page`，在 `finally` 块 unregister 避免泄漏
- **配置节点**：`meta_rules_57_63.external_resource_lifecycle`
- **规范引用**：meta-rule #62 / xianyu-hunter-dev v4.38.0 step 194
- **适用**：外部资源传入、并发采集场景、Playwright Page 共享
- **不适用**：内部创建的资源（自己管理生命周期）、单线程使用、一次性资源
```

### B-REVIEW-188 DB-WRITE-IDENTITY-TRACE 数据库写入身份追踪

```
### 🔴 [CRITICAL] B-REVIEW-188：数据库写入函数缺 user_id 参数 / converter 处理 Match 错误

- **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
- **当前代码（反模式1）**：
  ```python
  def upsert_eval_event(event: EventRow):
      # 缺 user_id，跨用户数据可能被误删
      session.add(event)
  ```
- **当前代码（反模式2）**：
  ```python
  _SELLER_LABEL_PATTERNS = (
      ("sold_count", re.compile(r"卖出(\d+)件"), int),  # int(m) 报错：int() argument must be a string, not 're.Match'
  )
  ```
- **问题**：数据库写入函数缺 `user_id` 参数导致跨用户数据删除；converter 用 `int` 直接转型 `re.Match` 对象报错
- **修复建议**：(1) 添加 `user_id: str` 参数并赋值到 `event.created_by`；(2) converter 改为 `lambda m: int(m.group(1))`
- **配置节点**：`meta_rules_57_63.db_write_identity_trace`
- **规范引用**：meta-rule #63 / xianyu-hunter-dev v4.38.0 step 195
- **适用**：所有数据库写入函数、正则 converter 函数、跨用户系统
- **不适用**：系统级写入（日志表/统计表）、单一调用点的函数、纯查询函数
```

## 🆕 v4.38.0 配置节点缺失检查（meta_rules_57_63）

> 若 `config.yaml` 中缺少 `meta_rules_57_63` 节点或其子节点，配置驱动检查将无法生效。审查报告必须列出缺失的配置节点。

| 缺失节点 | 影响范围 | 修复建议 |
|----------|----------|----------|
| `meta_rules_57_63.async_await_check` | B-REVIEW-182 无法判定白名单装饰器与 async generator 豁免 | 从 `config.example.yaml` 复制完整节点 |
| `meta_rules_57_63.resource_pool_benchmark` | B-REVIEW-183 无法判定开销阈值与资源池类型 | 同上 |
| `meta_rules_57_63.http_status_code_mapping` | B-REVIEW-184 无法判定 reason 字段名与默认状态码 | 同上 |
| `meta_rules_57_63.css_selector_fallback` | B-REVIEW-185 无法判定降级级数与 dump 触发条件 | 同上 |
| `meta_rules_57_63.exception_log_semantic` | B-REVIEW-186 无法判定禁用模式与关键路径函数 | 同上 |
| `meta_rules_57_63.external_resource_lifecycle` | B-REVIEW-187 无法判定资源类型与配对函数 | 同上 |
| `meta_rules_57_63.db_write_identity_trace` | B-REVIEW-188 无法判定函数模式与豁免清单 | 同上 |
