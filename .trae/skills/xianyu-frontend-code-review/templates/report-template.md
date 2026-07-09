# 闲鱼猎人前端代码审查报告

## 基本信息

- **审查版本**：v2.0.0
- **审查模式**：[全量审查 / 增量审查 / 指定文件审查 / 片段评审]
- **审查范围**：`frontend/src/**/*.{tsx,ts,js}`
- **审查文件数**：X 个
- **审查时间**：YYYY-MM-DD HH:MM:SS
- **审查人**：xianyu-frontend-code-review Skill
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

### 按 category 分布（18 维度）

| Category | 数量 |
|----------|------|
| directory_structure | X |
| naming | X |
| react_component | X |
| typescript_strict | X |
| antd_theme | X |
| zustand | X |
| api_call | X |
| routing_lazy | X |
| sheet_workspace | X |
| hooks_design | X |
| type_safety | X |
| sonarqube | X |
| pwa | X |
| three_mappings | X |
| sse_reconnect | X |
| performance | X |
| accessibility | X |
| project_specific | X |

## 硬约束合规性检查结果

| 硬约束规则 | 状态 | 违规位置 |
|------------|------|----------|
| `fetch_credentials_include` | ✅ 通过 / ❌ 违规 | - |
| `axios_with_credentials` | ✅ 通过 / ❌ 违规 | - |
| `no_token_in_localstorage` | ✅ 通过 / ❌ 违规 | - |
| `no_dangerously_set_inner_html` | ✅ 通过 / ❌ 违规 | - |
| `no_any_type` | ✅ 通过 / ❌ 违规 | - |
| `no_bare_async_catch` | ✅ 通过 / ❌ 违规 | - |
| `icon_button_needs_aria_label` | ✅ 通过 / ❌ 违规 | - |
| `no_enum_use_union` | ✅ 通过 / ❌ 违规 | - |
| `no_index_as_key` | ✅ 通过 / ❌ 违规 | - |
| `no_json_parse_stringify_deep_copy` | ✅ 通过 / ❌ 违规 | - |
| `no_arrow_function_component` | ✅ 通过 / ❌ 违规 | - |
| `zustand_persist_partialize` | ✅ 通过 / ❌ 违规 | - |

**合并结论**：[允许合并 / 阻止合并（存在 CRITICAL 违规）]

## 抽象建议触发情况

基于 `abstraction_thresholds` 阈值检查：

| 抽象维度 | 阈值 | 触发位置 | 建议方案 |
|----------|------|----------|----------|
| 内联样式重复 | ≥3 处 | - | 抽取样式常量或共享组件 |
| 文案字面量重复 | ≥2 处 | - | 抽取共享文案常量 |
| 函数行数 | >50 行 | - | 拆分为子函数 |
| 组件行数 | >300 行 | - | 拆分子组件 |
| 嵌套深度 | >4 层 | - | 提取模块级函数（S2004） |
| 认知复杂度 | >15 | - | 拆分函数（S3776） |

## 详细问题列表

### 🔴 阻塞问题（必须修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```tsx
     // 问题代码示例
     ```
   - **修复建议**：
     ```tsx
     // 修复后的代码示例
     ```
   - **参考规范**：[对应 SKILL.md 维度章节]

### 🟠 严重问题（强烈建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **修复建议**：[具体建议]

### 🟡 警告问题（建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **修复建议**：[具体建议]

### 🟢 优化建议（可选）

1. **建议描述**：[具体建议]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **优化方案**：[具体方案]

## ✅ 好的实践

- [正面反馈：列出本次审查中发现的好实践]
  - 例如：axios.create 正确配置 `withCredentials: true`
  - 例如：ConfigProvider 正确放置在 BrowserRouter 外层
  - 例如：使用字符串字面量联合替代 enum
  - 例如：useRef 持有最新闭包避免 setInterval 陷阱
  - 例如：抽取纯函数便于单元测试（如 resolveActionDisplay）

## 测试运行结果

- **测试命令**：`npm --prefix frontend test ; npm --prefix frontend run typecheck`
- **测试结果**：[通过 / 失败]
- **类型检查**：[通过 / 失败]

## 审查结论

- [ ] 通过（无阻塞问题）
- [ ] 有条件通过（仅警告和提示级别问题）
- [ ] 不通过（存在阻塞或严重问题）

## 修复验证

修复完成后，请重新运行审查确认问题已解决：

```powershell
# 1. 重新运行快速自检
pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1

# 2. 重新运行人工评审
# 调用 xianyu-frontend-code-review 技能
```

## 报告归档

报告保存路径：`.trae/skills/xianyu-frontend-code-review/reports/YYYY-MM-DD_HHmmss_[full|incremental]_report.md`

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
| 批处理熔断后无 `save_progress()` | `consecutive failure >= 3` 后 `break` | 剩余商品永久 skipped | 熔断分支未持久化 cursor | 熔断时调用 `_save_progress()` |
| Proxy/Observer 被 GC 回收 | `const x = new Proxy()` 局部变量 | DOM 变化不再触发回调 | 局部变量无生命周期 | 赋值给实例属性 `this._proxy` |
| 前端 TTL 缓存兜底跨进程状态 | `setTimeout(refresh, 30000)` | 状态刷新延迟 30s | 跨进程状态未 SSE 推送 | `single_source_of_truth` + `refetch()` |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 对应工作流元规范 | 核心判断信号 | 落地配置节点 |
|------|------------------|--------------|--------------|
| 错误处理决策树 | meta-rule #21 | `grep "except" <file>` 关键路径缺 `logger.exception()` | `workflow_meta_rules_frontend.error_handling_decision_tree` |
| 批处理熔断模板 | meta-rule #22 | `grep "consecutive failure" <file>` 无 `save_progress()` | `workflow_meta_rules_frontend.batch_circuit_breaker_frontend.failure_threshold` |
| 资源生命周期 | meta-rule #23 | `grep "new (Proxy\|MutationObserver\|IntersectionObserver\|ResizeObserver)"` 局部变量 | `workflow_meta_rules_frontend.resource_lifecycle_frontend.required_holder_patterns` |
| 跨组件状态同步 | meta-rule #24 | `grep "usePersistentState" <file>` 但后端有 `GET /api/xxx` | `workflow_meta_rules_frontend.state_sync_workflow_frontend.single_source_of_truth` |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 错误处理决策树 | 启动钩子 / 迁移 / 初始化 / API 路由 try-catch / 前端 `.catch` | 性能 hot path（结构化异常）/ 测试代码（`pytest.raises`） |
| 批处理熔断模板 | 批量采集 / 批量导入 / 长任务 / 断点续传 / 用户主动取消 | 实时单次请求 / 幂等小批量（≤3 个）/ 性能 hot path |
| 资源生命周期 | Playwright/Selenium / SSE/EventSource / WebSocket / Proxy/Observer / 长生命周期 Timer | 短生命周期局部计算 / 一次性 useEffect / 测试 mock 资源 |
| 跨组件状态同步 | 复杂前端应用（多组件共享同一份数据）/ 多 Tab / 多路由 / 配置变更实时生效 | 简单组件树（1-2 层 props drilling）/ SSR / 纯 UI 偏好（主题色/视图模式） |

## 🆕 v4.28.0 工作流元规范触发

> 本次审查触发的元规范编号（与 xianyu-hunter-dev/references/meta-rules.md #21-24 对应）。每条触发需指明：触发规则名、对应 config.yaml 配置节点、违规位置、修复方式。

| 触发编号 | 元规范名称 | 触发规则 | 配置节点 | 违规位置 | 修复方式 |
|----------|------------|----------|----------|----------|----------|
| #21 | 错误处理决策树 | F-REVIEW-WF-ERROR-HANDLING | `workflow_meta_rules_frontend.error_handling_decision_tree.forbidden_catch_patterns` | `frontend/src/xxx/yyy.tsx:L123` | 改用 switch on `err.error_code` |
| #22 | 批处理熔断模板 | F-REVIEW-WF-BATCH-CIRCUIT-BREAKER | `workflow_meta_rules_frontend.batch_circuit_breaker_frontend.failure_threshold` | `frontend/src/xxx/zzz.ts:L456` | 熔断时调用 `saveProgress()` |
| #23 | 资源生命周期 | F-REVIEW-WF-RESOURCE-LIFECYCLE | `workflow_meta_rules_frontend.resource_lifecycle_frontend.forbid_local_var_creation` | `frontend/src/aaa.tsx:L78` | 改为 `this._observer = new ...` |
| #24 | 跨组件状态同步 | F-REVIEW-WF-STATE-SYNC | `workflow_meta_rules_frontend.state_sync_workflow_frontend.forbid_persistent_state_for` | `frontend/src/bbb.tsx:L234` | 改为 `useXxxStore().setXxx()` + `refetch()` |

## 🆕 v4.28.0 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则，仅调整阈值/白名单/关键字等参数化配置，不引入新的硬编码业务值。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 阈值调整 | `error_handling_decision_tree.max_retry_count` | `3` | `5` | 现有 3 次重试不足以应对网络抖动 | 错误处理决策树（meta-rule #21） |
| 白名单新增 | `batch_circuit_breaker_frontend.required_state_display` | `[running, paused]` | `[running, paused, failed, stopped, completed]` | 状态机需覆盖全部 5 个状态 | 批处理熔断（meta-rule #22） |
| 模式新增 | `resource_lifecycle_frontend.forbid_local_var_creation` | `[Proxy, MutationObserver]` | `[Proxy, MutationObserver, IntersectionObserver, ResizeObserver, EventSource, WebSocket]` | 补齐其他可注册资源 | 资源生命周期（meta-rule #23） |
| 黑名单新增 | `state_sync_workflow_frontend.forbid_persistent_state_for` | `[task_status, cookie_status]` | `[task_status, cookie_status, scheduler_status, model_config]` | 补齐其他跨进程字段 | 跨组件状态同步（meta-rule #24） |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] SKILL.md 附录 C 的 26 维度与本变更一致
- [ ] references/version-changelog.md 已追加 v4.28.0 变更说明

## 🆕 v4.30 跨边界访问契约

> 跨边界访问必须明确契约，不能依赖隐式约定。与 xianyu-hunter-dev/references/coding-standards.md §2.11-2.14 配套。

### 跨边界契约检查（前端侧）

| 边界类型 | 契约内容 | 配置节点 | 检查工具 |
|----------|----------|----------|----------|
| DB → 前端 | 后端 ISO datetime 字符串渲染必须 `new Date(isoStr).toLocaleString()` | `cross_boundary_contract_frontend.datetime_render_contract.backend_datetime_field_suffixes` | F-REVIEW-DATETIME-RENDER-CONTRACT |
| 前端 → 后端 | 传递时间用 `Date.toISOString()` 保留时区 | `cross_boundary_contract_frontend.datetime_render_contract.required_isoformat_patterns` | F-REVIEW-DATETIME-RENDER-CONTRACT |
| 跨组件 store | 禁止直接访问 `useXxxStore(s => s._private)` | `cross_boundary_contract_frontend.private_hook_encapsulation.forbid_private_prefix_access` | F-REVIEW-PRIVATE-HOOK-ENCAPSULATION |
| 父 → 子 ref | 父组件通过 ref 访问子组件 `_` 内部 state 禁止 | `cross_boundary_contract_frontend.private_hook_encapsulation.require_imperative_handle` | F-REVIEW-PRIVATE-HOOK-ENCAPSULATION |
| 命名一致性 | Zustand store 字段 camelCase（与前端规范） | `cross_boundary_contract_frontend.naming_consistency.store_field_case` | F-REVIEW-NAMING-CONSISTENCY-FRONTEND |

## 🆕 v4.41.0 编码规范防御性复盘

> 基于 `xianyu-hunter-dev` v4.38.0 meta-rules #57-63 前端落地，新增 4 项 F-REVIEW 检查点（F-REVIEW-148~151），自动化扫描从 121 项扩展到 125 项。与 `xianyu-hunter-dev` step 189-195 对应。

### F-REVIEW-148~151 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| F-REVIEW-148 | ASYNC-AWAIT-SYNC-CHECK-FRONTEND | 10 Hooks 设计模式 | CRITICAL | `meta_rules_57_63_frontend.frontend_async_await_check` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-149 | HTTP-ERROR-LOCALIZATION | 7 API 契约 | WARNING | `meta_rules_57_63_frontend.frontend_http_error_localization` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-150 | ERROR-CHAIN-TRANSPARENT | 7 API 契约 / 4 业务逻辑 | WARNING | `meta_rules_57_63_frontend.frontend_error_chain_transparent` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-151 | EXTERNAL-RESOURCE-CLEANUP-FRONTEND | 10 Hooks 设计模式 / 6 Zustand 状态管理 | CRITICAL | `meta_rules_57_63_frontend.frontend_external_resource_cleanup` | X | ✅ 通过 / ❌ 违规 |

### F-REVIEW-148 ASYNC-AWAIT-SYNC-CHECK-FRONTEND 违规详情

> React `useEffect` 内 async 函数必须用 IIFE 包裹 + cancelled 标志，禁止 `useEffect(async () => {})` 直接传入。

1. **问题描述**：[useEffect 直接接收 async 函数 / cleanup 返回 Promise 而非函数 / 缺少 cancelled 标志]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 问题代码示例
     useEffect(async () => {
       const data = await fetchData();
       setData(data);
     }, []);
     ```
   - **修复建议**：
     ```typescript
     // ✅ 用 IIFE 包裹，cleanup 返回函数
     useEffect(() => {
       let cancelled = false;
       (async () => {
         const data = await fetchData();
         if (!cancelled) setData(data);
       })();
       return () => { cancelled = true; };
     }, []);
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_async_await_check`（severity: CRITICAL, forbidden_patterns: ["useEffect(async", "useEffect.*async.*=>"]）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #57 + step 189

### F-REVIEW-149 HTTP-ERROR-LOCALIZATION 违规详情

> 已知状态码优先用前端中文 `statusMessages[status]`，后端 `detail` 仅作 fallback。

1. **问题描述**：[优先用后端英文 detail / 已知状态码无前端中文消息映射 / 状态码映射表散落在组件内]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 优先用后端英文 detail，对中文用户不友好
     catch (err) {
       const status = err?.response?.status;
       const detail = err?.response?.data?.detail;
       message.error(detail || statusMessages[status]);
     }
     ```
   - **修复建议**：
     ```typescript
     // ✅ 已知状态码优先用前端中文消息，后端 detail 仅作 fallback
     const COLLECT_OFFICIAL_ERROR_MESSAGES: Record<number, string> = {
       503: '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动',
       403: '闲鱼登录已过期，请重新登录闲鱼',
       440: '闲鱼登录已过期，请重新登录闲鱼',
       441: '触发闲鱼反爬限制，请稍后重试或手动完成验证',
       410: '商品详情页加载失败或已下架，请稍后重试',
       502: '浏览器连接异常，请重启服务后重试',
     };
     catch (err) {
       const status = err?.response?.status;
       if (status != null && statusMessages[status]) {
         message.error(statusMessages[status]);
       } else {
         message.error(detail || fallbackMessage);
       }
     }
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_http_error_localization`（severity: WARNING, prefer_frontend_message: true, fallback_to_detail: true）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #59 + step 191

### F-REVIEW-150 ERROR-CHAIN-TRANSPARENT 违规详情

> 错误链路需透明展示 reason/failure_reason；用户可见错误必须含可操作建议。

1. **问题描述**：[仅展示模糊错误无 reason / 错误消息无可操作建议 / 多阶段降级链未合并展示 / 缺少 retryable 标志]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 仅展示模糊错误，无 reason 无建议
     message.error('采集失败');
     ```
   - **修复建议**：
     ```typescript
     // ✅ 含 reason 与可操作建议
     message.error({
       content: `采集失败：${reason}。建议：${actionHint}`,
       duration: 8,
     });
     // 或结构化展示
     const errorDisplay = {
       title: '官方采集失败',
       reason: failure_reason,
       suggestion: getSuggestionByReason(failure_reason),
       retryable: isRetryable(failure_reason),
     };
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_error_chain_transparent`（severity: WARNING, require_reason: true, require_suggestion: true, require_retryable_flag: true, multi_stage_merge: true）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #61 + step 193

### F-REVIEW-151 EXTERNAL-RESOURCE-CLEANUP-FRONTEND 违规详情

> `useEffect` 内创建的 WebSocket/EventSource/setInterval/setTimeout/addEventListener/AbortController 必须在 cleanup 中释放。

1. **问题描述**：[useEffect 创建资源但无 cleanup return / cleanup 未调用对应释放方法 / 事件监听器未 removeEventListener / WebSocket 未 close]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ useEffect 创建订阅但无 cleanup
     useEffect(() => {
       const ws = new WebSocket('ws://localhost:8080');
       ws.onmessage = (e) => setMessage(e.data);
       // 缺少 return () => ws.close();
     }, []);
     ```
   - **修复建议**：
     ```typescript
     // ✅ 创建与 cleanup 配对
     useEffect(() => {
       const controller = new AbortController();
       const ws = new WebSocket('ws://localhost:8080');
       ws.onmessage = (e) => setMessage(e.data);
       return () => {
         controller.abort();
         ws.close();
       };
     }, []);
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_external_resource_cleanup`（severity: CRITICAL, resource_types: ["WebSocket", "EventSource", "setInterval", "setTimeout", "addEventListener", "AbortController"], require_cleanup_return: true, pair_required: true）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #62 + step 194

### v4.43.0 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 状态码映射新增 | `meta_rules_57_63_frontend.frontend_http_error_localization.status_message_examples` | `[503, 403, 440, 441, 410, 502]` | `[503, 403, 440, 441, 410, 502, <新状态码>]` | 业务域扩展新增状态码 | F-REVIEW-149（meta-rule #59） |
| 资源类型新增 | `meta_rules_57_63_frontend.frontend_external_resource_cleanup.resource_types` | `[WebSocket, EventSource, setInterval, setTimeout, addEventListener, AbortController]` | `[...现有, <新资源类型>]` | 新增长生命周期资源 | F-REVIEW-151（meta-rule #62） |
| 检测模式新增 | `meta_rules_57_63_frontend.frontend_external_resource_cleanup.detection_patterns` | `[WebSocket, setInterval, addEventListener]` | `[...现有, <新资源 pattern]` | 补齐其他资源的 cleanup 检测 | F-REVIEW-151（meta-rule #62） |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] SKILL.md 维度 34 章节与本变更一致
- [ ] references/version-changelog.md 已追加 v4.41.0 变更说明

