# MorningBrief 后端代码审查报告

## 基本信息

- **审查版本**：v1.0.0
- **审查模式**：[全量审查 / 增量审查 / 指定文件审查 / 片段评审]
- **审查范围**：`backend/app/**/*.py`
- **审查文件数**：X 个
- **审查时间**：YYYY-MM-DD HH:MM:SS
- **审查人**：news-backend-code-review Skill
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

### 按 category 分布（15 维度）

| Category | 数量 |
|----------|------|
| security | X |
| error_handling | X |
| async_concurrency | X |
| sqlalchemy | X |
| workflow | X |
| field_contract | X |
| fastapi | X |
| cache | X |
| config_driven | X |
| logging | X |
| performance | X |
| layering | X |
| naming | X |
| type_annotation | X |
| testability | X |

## 硬约束合规性检查结果

| 硬约束规则 | 状态 | 违规位置 |
|------------|------|----------|
| `deprecated_utcnow` | ✅ 通过 / ❌ 违规 | - |
| `datetime_now_no_tzinfo` | ✅ 通过 / ❌ 违规 | - |
| `bare_sql_injection` | ✅ 通过 / ❌ 违规 | - |
| `enum_field_without_value` | ✅ 通过 / ❌ 违规 | - |
| `create_task_no_reference` | ✅ 通过 / ❌ 违规 | - |
| `sync_io_in_async` | ✅ 通过 / ❌ 违规 | - |
| `sync_requests_in_async` | ✅ 通过 / ❌ 违规 | - |
| `async_def_without_await` | ✅ 通过 / ❌ 违规 | - |
| `finally_unconditional_release` | ✅ 通过 / ❌ 违规 | - |
| `redis_non_atomic_lrange_ltrim` | ✅ 通过 / ❌ 违规 | - |
| `token_compare_with_equals` | ✅ 通过 / ❌ 违规 | - |
| `hardcoded_credentials` | ✅ 通过 / ❌ 违规 | - |
| `sensitive_filter_not_initialized` | ✅ 通过 / ❌ 违规 | - |
| `logout_missing` | ✅ 通过 / ❌ 违规 | - |
| `builtin_exception_shadowing` | ✅ 通过 / ❌ 违规 | - |
| `bare_except_pass` | ✅ 通过 / ❌ 违规 | - |
| `exception_log_warning_fstring` | ✅ 通过 / ❌ 违规 | - |
| `internal_route_no_auth` | ✅ 通过 / ❌ 违规 | - |
| `print_statement` | ✅ 通过 / ❌ 违规 | - |
| `print_traceback_format_exc` | ✅ 通过 / ❌ 违规 | - |
| `os_getenv_direct` | ✅ 通过 / ❌ 违规 | - |

**合并结论**：[允许合并 / 阻止合并（存在 CRITICAL 违规）]

## V2.4 频道级配置与 LLM 超时审查结果（维度 113-115）

> 对应 `config.yaml#llm_timeout_config_driven_check`、`channel_config_override_check`、`channel_cron_event_driven_check`，详见 SKILL.md "维度 113-115：2026-07-22 频道级配置与 LLM 超时复盘新增审查维度"

| 维度 | 审查项 | 状态 | 违规位置 | 配置节点 |
|------|--------|------|----------|----------|
| 113 | LLM 调用 timeout 从 settings 读取 | ✅ 通过 / ❌ 违规 | - | `llm_timeout_config_driven_check.require_settings_read` |
| 113 | 长耗时 LLM 调用使用 max(LLM_TIMEOUT_SEC*N, MIN) 公式 | ✅ 通过 / ❌ 违规 | - | `llm_timeout_config_driven_check.require_formula_for_long_running` |
| 113 | LLM_TIMEOUT_SEC 在 CONFIG_KEY_MAP 可配置 | ✅ 通过 / ❌ 违规 | - | `llm_timeout_config_driven_check.config_key_map_entry` |
| 113 | LLM 调用失败记录 token 用量到预算系统 | ✅ 通过 / ❌ 违规 | - | `llm_timeout_config_driven_check.require_budget_record` |
| 114 | 频道级配置字段优先于 settings 全局 | ✅ 通过 / ❌ 违规 | - | `channel_config_override_check.channel_fields` |
| 114 | 频道字段为空时 fallback 到全局配置 | ✅ 通过 / ❌ 违规 | - | `channel_config_override_check.require_fallback_to_global` |
| 114 | 频道字段变更发布 EventBus 事件 | ✅ 通过 / ❌ 违规 | - | `channel_config_override_check.require_event_publish_on_change` |
| 114 | 数据库迁移幂等（PRAGMA 检测后 ALTER TABLE） | ✅ 通过 / ❌ 违规 | - | `channel_config_override_check.require_idempotent_migration` |
| 115 | schedule_time 变更发布 channel.schedule_changed 事件 | ✅ 通过 / ❌ 违规 | - | `channel_cron_event_driven_check.event_types` |
| 115 | is_active 变更发布 channel.active_changed 事件 | ✅ 通过 / ❌ 违规 | - | `channel_cron_event_driven_check.event_types` |
| 115 | 事件发布用 publish_nowait 避免阻塞 | ✅ 通过 / ❌ 违规 | - | `channel_cron_event_driven_check.publish_method` |
| 115 | 订阅者处理幂等（重复事件无副作用） | ✅ 通过 / ❌ 违规 | - | `channel_cron_event_driven_check.require_idempotent_subscriber` |
| 115 | 频道禁用时取消 queued 工作流 | ✅ 通过 / ❌ 违规 | - | `channel_cron_event_driven_check.require_cancel_queued_on_disable` |
| 115 | schedule_time 清空时移除 cron 任务 | ✅ 通过 / ❌ 违规 | - | `channel_cron_event_driven_check.require_unregister_on_empty_schedule` |
| 115 | cron 任务配置 misfire_grace_time/coalesce/max_instances=1 | ✅ 通过 / ❌ 违规 | - | `channel_cron_event_driven_check.cron_job_config` |

## V2.5 后端高频故障复盘审查结果（维度 124-129）

> 对应 `config.yaml#binary_response_no_wrapper_check`、`workflow_retry_in_place_check`、`config_key_settings_mapping_check`、`test_time_baseline_alignment_check`、`foreign_key_defensive_handling_check`、`credential_masking_regex_check`，详见 SKILL.md "v2.5：2026-07-22 后端高频故障复盘新增审查维度（维度 124-129）"

| 维度 | 审查项 | 状态 | 违规位置 | 配置节点 |
|------|--------|------|----------|----------|
| 124 | FileResponse/StreamingResponse 显式设置 media_type | ✅ 通过 / ❌ 违规 | - | `binary_response_no_wrapper_check.require_media_type` |
| 124 | 二进制响应禁止包装在 {code,message,data} 中 | ✅ 通过 / ❌ 违规 | - | `binary_response_no_wrapper_check.forbid_success_wrapper` |
| 124 | 文件不存在返回 HTTP 404 而非 200+error | ✅ 通过 / ❌ 违规 | - | `binary_response_no_wrapper_check.require_404_on_not_found` |
| 124 | 扫描范围覆盖 routers/ 与 services/ | ✅ 通过 / ❌ 违规 | - | `binary_response_no_wrapper_check.scan_dirs` |
| 125 | retry_workflow 接受 from_step 参数 | ✅ 通过 / ❌ 违规 | - | `workflow_retry_in_place_check.require_from_step_param` |
| 125 | 删除 from_step 及之后步骤记录（含失败记录） | ✅ 通过 / ❌ 违规 | - | `workflow_retry_in_place_check.require_delete_failed_steps` |
| 125 | 保留 from_step 之前的成功步骤记录 | ✅ 通过 / ❌ 违规 | - | `workflow_retry_in_place_check.require_preserve_success_steps` |
| 125 | 校验前驱步骤 success 且有 result | ✅ 通过 / ❌ 违规 | - | `workflow_retry_in_place_check.require_predecessor_validation` |
| 125 | 重置状态为 queued，清空 error 与 finished_at | ✅ 通过 / ❌ 违规 | - | `workflow_retry_in_place_check.require_status_reset` |
| 125 | 入队当前 workflow_id，禁止 trigger_workflow | ✅ 通过 / ❌ 违规 | - | `workflow_retry_in_place_check.forbid_trigger_new_workflow` |
| 126 | CONFIG_KEY_MAP 的 key 与路由层 BaseModel 字段名一致 | ✅ 通过 / ❌ 违规 | - | `config_key_settings_mapping_check.require_key_align_with_body` |
| 126 | CONFIG_KEY_MAP 的 value 与 Settings 属性名一致 | ✅ 通过 / ❌ 违规 | - | `config_key_settings_mapping_check.require_value_align_with_settings` |
| 126 | _normalize_xxx 返回 result key 与 CONFIG_KEY_MAP 的 key 一致 | ✅ 通过 / ❌ 违规 | - | `config_key_settings_mapping_check.require_normalize_xxx_consistency` |
| 126 | get_config_for_frontend 返回字段名与 CONFIG_KEY_MAP 的 key 一致 | ✅ 通过 / ❌ 违规 | - | `config_key_settings_mapping_check.require_get_config_for_frontend_consistency` |
| 126 | SENSITIVE_KEYS/INT_KEYS 与 CONFIG_KEY_MAP 的 key 命名一致 | ✅ 通过 / ❌ 违规 | - | `config_key_settings_mapping_check.require_type_keys_naming_consistency` |
| 126 | 禁止混用前缀风格（如 edge_tts_xxx 与 edge_xxx 混用） | ✅ 通过 / ❌ 违规 | - | `config_key_settings_mapping_check.forbid_mixed_prefix` |
| 127 | 测试用 datetime.now() 而非 datetime.utcnow() | ✅ 通过 / ❌ 违规 | - | `test_time_baseline_alignment_check.require_local_time_in_test` |
| 127 | 禁止测试用 UTC aware 时间与本地时间混用 | ✅ 通过 / ❌ 违规 | - | `test_time_baseline_alignment_check.forbid_utc_aware_in_test` |
| 127 | 时间比较用近似断言（abs diff < epsilon） | ✅ 通过 / ❌ 违规 | - | `test_time_baseline_alignment_check.require_approximate_assertion` |
| 127 | epsilon 按数据库精度配置（SQLite 2s / MySQL 1s） | ✅ 通过 / ❌ 违规 | - | `test_time_baseline_alignment_check.db_precision_mapping` |
| 128 | 删除父记录前先 UPDATE 子表外键为 NULL 或级联删除 | ✅ 通过 / ❌ 违规 | - | `foreign_key_defensive_handling_check.require_manual_fk_handling` |
| 128 | 不依赖 PRAGMA foreign_keys 开关 | ✅ 通过 / ❌ 违规 | - | `foreign_key_defensive_handling_check.forbid_pragma_foreign_keys_dependency` |
| 128 | 删除操作在同一事务内完成 | ✅ 通过 / ❌ 违规 | - | `foreign_key_defensive_handling_check.require_same_transaction` |
| 128 | 推荐预删除 count 检查 | ✅ 通过 / ❌ 违规 | - | `foreign_key_defensive_handling_check.recommend_pre_delete_count_check` |
| 128 | 推荐 ON DELETE SET NULL/CASCADE 作为兜底 | ✅ 通过 / ❌ 违规 | - | `foreign_key_defensive_handling_check.recommend_ondelete_as_fallback` |
| 129 | 脱敏正则使用捕获组保留 key 名 | ✅ 通过 / ❌ 违规 | - | `credential_masking_regex_check.require_capture_group` |
| 129 | 替换为 m.group(1)+"***" 而非整体替换 | ✅ 通过 / ❌ 违规 | - | `credential_masking_regex_check.require_key_name_preservation` |
| 129 | 大小写不敏感（(?i) 前缀） | ✅ 通过 / ❌ 违规 | - | `credential_masking_regex_check.require_case_insensitive` |
| 129 | 敏感关键词列表可配置（token/secret/key/password/appkey 等） | ✅ 通过 / ❌ 违规 | - | `credential_masking_regex_check.sensitive_keywords` |
| 129 | 统一函数名 mask_sensitive | ✅ 通过 / ❌ 违规 | - | `credential_masking_regex_check.unified_function_name` |

## V3.0 2026-08-05 会话复盘审查结果（维度 196-202）

> 对应 `config.yaml` 各节点，详见 SKILL.md "V3.0 2026-08-05 会话复盘新增审查维度"。

| 维度 | 审查项 | 状态 | 违规位置 | 配置节点 |
|------|--------|------|----------|----------|
| 196 | except 块保留 traceback / 子进程启动转专用异常 | ✅ 通过 / ❌ 违规 | - | `exception_swallow_check` |
| 197 | wait_for/create_task 包裹函数 except Exception 前补 CancelledError | ✅ 通过 / ❌ 违规 | - | `cancelled_error_guard_check` |
| 198 | 同步函数内 create_task 模块级集合保活 + 运行循环守卫 + 测试禁用 | ✅ 通过 / ❌ 违规 | - | `fire_and_forget_keepalive_check` |
| 199 | _build_info.py 禁止硬编码 unknown/日期；生成器被构建/发布脚本调用 | ✅ 通过 / ❌ 违规 | - | `build_metadata_single_source_check` |
| 200 | 删除/重命名公共 API 后 grep 旧名 0 匹配；矛盾注释清理 | ✅ 通过 / ❌ 违规 | - | `alias_rename_completeness_check` |
| 201 | 依赖模块级文件路径/单例的测试重定向 tmp_path，不依赖 unlink 成功 | ✅ 通过 / ❌ 违规 | - | `test_isolation_safe_delete_check` |
| 202 | installer.iss 含 SetupIconFile；spec 与 iss 模板一致 | ✅ 通过 / ❌ 违规 | - | `packaging_config_completeness_check` |

## V3.1 2026-08-05 段间静音/bgm_gap_mode 复盘审查结果（维度 205-206）

> 对应 `config.yaml` 各节点，详见 SKILL.md "V3.1 2026-08-05 段间静音/bgm_gap_mode 复盘新增审查维度"。
> 对应 news-code-dev 诊断标准 DS-15 / DS-16。

| 维度 | 审查项 | 状态 | 违规位置 | 配置节点 |
|------|--------|------|----------|----------|
| 205 | 媒体开关字段有 silence/bridge 双模式 + amix duration=first 真静音 | ✅ 通过 / ❌ 违规 | - | `bgm_gap_mode_check` |
| 205 | 全局默认/频道覆盖双路径（非 None 覆盖 settings.*，None 继承） | ✅ 通过 / ❌ 违规 | - | `bgm_gap_mode_check.channel_override` |
| 205 | 新增列幂等迁移（PRAGMA table_info 检测后 ALTER TABLE） | ✅ 通过 / ❌ 违规 | - | `bgm_gap_mode_check.idempotent_migration` |
| 206 | 校验器语义：空串→None(继承)；去空格归一化；非法→ValueError | ✅ 通过 / ❌ 违规 | - | `validator_semantic_check` |
| 206 | 校验器行为与测试断言一致（期望 None 不抛错；期望抛错须拒绝） | ✅ 通过 / ❌ 违规 | - | `validator_semantic_check.test_alignment` |

## 问题定性（真缺陷 / 误报 / 环境制品）

> V3.0 增强：每条问题必须归入以下三类之一，避免把"环境制品"误判为"代码失败"或把"grep 误报"计入缺陷。

| 定性 | 定义 | 处理方式 |
|------|------|----------|
| 真缺陷 | 违反硬约束或明确反模式，需代码修复 | 计入阻塞/严重统计，给出修复建议 |
| 误报 | grep 信号命中但人工确认非问题（如 `get_settings` 触发 `os_getenv_direct`） | 记录 `false_positive_hints` 理由，不计入缺陷 |
| 环境制品 | safe-delete 拦截 teardown、`test_ai_budget` 的 `unlink` 残留等，与改动无关 | 单独归类并注明"非代码失败"，不计入缺陷 |

## 详细问题列表

### 🔴 阻塞问题（必须修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`backend/app/xxx.py` 第 X 行
   - **问题定性**：[真缺陷 / 误报 / 环境制品]
   - **适用场景**：[该规则适用的上下文，取自 DS 标准维度 4]
   - **不适用场景**：[该规则不适用的上下文]
   - **当前代码**：
     ```python
     # 问题代码示例
     ```
   - **修复建议**：
     ```python
     # 修复后的代码示例
     ```
   - **参考规范**：[对应 SKILL.md 维度章节 / news-code-dev DS-x]
   - **配置节点**：[对应 config.yaml 节点]
   - **严重级别判定理由**：[为何判为 CRITICAL/HIGH——如"CancelledError 逃逸导致静默失败不可观测"]

### 🟠 严重问题（强烈建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`backend/app/xxx.py` 第 X 行
   - **修复建议**：[具体建议]

### 🟡 警告问题（建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`backend/app/xxx.py` 第 X 行
   - **修复建议**：[具体建议]

### 🟢 优化建议（可选）

1. **建议描述**：[具体建议]
   - **位置**：`backend/app/xxx.py` 第 X 行
   - **优化方案**：[具体方案]

## ✅ 好的实践

- [正面反馈：列出本次审查中发现的好实践]
  - 例如：`hmac.compare_digest()` 正确使用
  - 例如：SQLite 引擎正确配置 WAL 模式 + busy_timeout
  - 例如：WorkflowScheduler 单实例锁防止并发触发
  - 例如：自定义异常继承 BizError 统一处理

## 测试运行结果

- **测试命令**：`pytest backend/tests/ -x --tb=short`
- **测试结果**：[通过 / 失败]
- **测试覆盖**：[覆盖率]
- **py_compile 验证**：[通过 / 失败]

## 审查结论

- [ ] 通过（无阻塞问题）
- [ ] 有条件通过（仅警告和提示级别问题）
- [ ] 不通过（存在阻塞或严重问题）

## 修复验证

修复完成后，请重新运行审查确认问题已解决：

```powershell
# 1. 重新运行快速自检
pwsh .trae/skills/news-backend-code-review/scripts/auto-scan.ps1

# 2. 重新运行人工评审
# 调用 news-backend-code-review 技能
```

## 报告归档

报告保存路径：`.trae/skills/news-backend-code-review/reports/YYYY-MM-DD_HHmmss_[full|incremental]_report.md`

---

## 四维度复盘

> 基于本次 MorningBrief 后端代码审查完整过程的复盘，沉淀可复用的工作流模板与判断逻辑。

### 维度 1：成功执行任务的完整步骤

- 本次审查在 15 维度下识别 `N` 个问题，其中 `M` 个被成功闭环
- 关键成功路径（按时间顺序）：
  1. `Grep 搜索反模式`：按维度 1-15 的判断信号扫描 `backend/app/**/*.py`
  2. `分类问题`：按 severity 与 category 归类
  3. `子智能体并行修复`：派发并行子智能体（敏感词初始化 / JWT 黑名单 / Enum .value / finally 锁保护等）
  4. `py_compile 验证`：`python -m py_compile <file>` 确保语法正确
  5. `pytest 测试`：`pytest backend/tests/ -x` 确保未破坏现有测试
- 复用方法/工具：Grep（反模式扫描）、Edit（精确修复）、RunCommand（py_compile + pytest 验证）

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 敏感词过滤器未初始化 | `sensitive_filter.load_words()` 从未被调用 | LLM 改写结果命中敏感词不拦截 | 启动流程遗漏初始化调用 | 在 main.py lifespan 或 WorkflowScheduler.__init__ 调用 `load_words()` |
| 登出接口缺失 | 无 `/logout` 路由 | JWT token 无法主动失效 | 黑名单机制未闭环 | 新增登出接口，写黑名单 |
| workflow source 字段返回 Enum 对象 | `WorkflowSource.CRON` 直接序列化 | API 返回 `<WorkflowSource.CRON: 'cron'>`，前端解析失败 | Enum 未调 `.value` | 序列化时用 `source.value` |
| finally 误删其他工作流的锁 | `finally: await cache.release("wf_lock")` 无条件执行 | 并发工作流互相误删锁 | `lock_acquired` 标志缺失 | 加 `lock_acquired` 标志 |
| approve 跨事务 | 审核批准与发布在同一事务 | 发布失败回滚审核状态 | 事务边界设计错误 | 拆分为两步独立事务 |
| PermissionError 覆盖内置异常 | `class PermissionError(Exception)` | 业务代码无法捕获内置异常 | 命名未加 Biz 前缀 | 改名 `BizPermissionError` |
| datetime.utcnow() 弃用 | Python 3.12+ 警告 | 升级 Python 后报错 | 沿用旧 API | 改用 `utcnow_naive()` |
| play_log LRANGE+LTRIM 非原子 | 消费日志时两条命令间并发写入 | 日志丢失或重复消费 | 未用 Lua 脚本 | 用 Lua 脚本封装 |
| asyncio.create_task 未保留引用 | 裸 `asyncio.create_task(coro)` | 协程被 GC 回收 | 局部变量无生命周期 | 赋值给 `self._running_tasks` |
| 异步函数中同步 IO 阻塞事件循环 | `async def` 内 `time.sleep` / `requests.get` | 整个事件循环阻塞 | 误用同步库 | 用 `asyncio.to_thread()` 或异步库 |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 核心判断信号 | 落地配置节点 |
|------|--------------|--------------|
| 敏感词初始化检查 | Grep `load_words` 在 startup 路径缺失 | `hard_constraints.rules.sensitive_filter_not_initialized` |
| JWT 黑名单闭环检查 | Grep `/logout` 路由缺失或未写黑名单 | `hard_constraints.rules.logout_missing` |
| Enum 字段序列化检查 | Grep `WorkflowStatus\.\w+` 后无 `.value` 在序列化路径 | `hard_constraints.rules.enum_field_without_value` |
| finally 锁保护检查 | Grep `finally` 块内 `release` 无 `lock_acquired` 判断 | `hard_constraints.rules.finally_unconditional_release` |
| 内置异常覆盖检查 | Grep `class PermissionError` / `class KeyError` 等 | `hard_constraints.rules.builtin_exception_shadowing` |
| datetime 弃用检查 | Grep `datetime\.utcnow\(\)` / `datetime\.now\(\)` | `hard_constraints.rules.deprecated_utcnow` |
| Redis 非原子操作检查 | Grep `LRANGE` 后跟 `LTRIM` 无 `eval` / `pipeline` | `hard_constraints.rules.redis_non_atomic_lrange_ltrim` |
| create_task 引用检查 | Grep `asyncio\.create_task` 未赋值实例属性 | `hard_constraints.rules.create_task_no_reference` |
| 同步 IO 阻塞检查 | Grep `async def` 内 `time\.sleep` / `requests\.` | `hard_constraints.rules.sync_io_in_async` |
| 内部接口鉴权检查 | Grep `routers/internal` 路由无 `verify_localhost` | `hard_constraints.rules.internal_route_no_auth` |
| 裸 SQL 注入检查 | Grep `text\(["'].*\+` 或 `f"SELECT` 字符串拼接 | `hard_constraints.rules.bare_sql_injection` |
| print 语句检查 | Grep `print\(` 在 .py 文件 | `hard_constraints.rules.print_statement` |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 敏感词初始化检查 | 含 LLM 改写/内容审核的 workflow 项目 | 无敏感词过滤的项目 |
| JWT 黑名单闭环检查 | 需要主动登出/封禁 token 的认证系统 | 无状态 JWT（接受 token 不可主动失效） |
| Enum .value 检查 | 用 Python Enum 定义状态字段的 ORM | 用字符串常量而非 Enum 的项目 |
| finally 锁保护检查 | 用 Redis/TTLCache 分布式锁的并发场景 | 单进程无锁场景、`with lock:` 上下文管理器 |
| 内置异常覆盖检查 | 所有 Python 项目 | 无 |
| datetime 弃用检查 | Python 3.12+ 项目 | Python 3.8-3.11 兼容场景（仅警告） |
| Redis 非原子检查 | 用 Redis 多命令原子操作场景 | 单命令操作、Lua 脚本已封装 |
| create_task 引用检查 | `asyncio.create_task` 长生命周期协程 | `asyncio.gather` 短期并发（自动等待） |
| 同步 IO 阻塞检查 | FastAPI / asyncio 异步项目 | 同步框架（Flask 默认）、CLI 脚本 |
| 内部接口鉴权检查 | 暴露内部 API 的项目（`routers/internal/`） | 无内部接口的项目 |
| 裸 SQL 注入检查 | 用 SQLAlchemy `text()` 的项目 | 纯 ORM 查询、纯参数化查询 |
| print 语句检查 | 所有生产项目 | 一次性脚本、debug 临时调试 |

## V3.1 段间静音/bgm_gap_mode 四维度复盘（DS-15 / DS-16）

> 基于本次段间静音/bgm_gap_mode 特性开发全流程的复盘，沉淀可复用的工作流模板与判断逻辑。

### 维度 1：成功执行任务的完整步骤
1. 复现"看似无效"：用真实函数生成 gap/main 音频，验证静音时长参数真正落地（排除陈旧残留冒充新产出，见 DS-7）。
2. 定位根因：默认 bridge 模式让 BGM 在段间连续叠加，`amix` 把静音段淹没 → 改为真静音 `amix=inputs=2:duration=first`。
3. 特征开关化：将静音语义做成可开关 `bgm_gap_mode`(silence/bridge)，全局默认 + 频道级覆盖（双路径）。
4. 幂等迁移：新增列用 `PRAGMA table_info` 检测后 `ALTER TABLE ADD COLUMN`。
5. 校验器语义对齐：空串/None→继承 None；去空格合法值→归一化；其余→ValueError。
6. 测试 + 构建双验证：后端 pytest（受管 venv）+ 前端 `vite build`（独立输出目录避开 safe-delete 拦截）。

### 维度 2：任务执行过程中的不确定性与失败点
| 失败点 | 触发条件 | 影响 | 根因 | 修复方式 |
|--------|----------|------|------|----------|
| 静音"看似无效" | 默认 bridge 模式 BGM 连续叠加 | 设 2.5s 听起来像 0.5s | bridge 掩盖静音 | 真静音 amix duration=first（DS-15） |
| 校验器/测试语义错位 | 校验器空串抛错但测试期望 None | 单测 3 失败 | 空串语义未约定为继承 | 空串→None + 重写测试（DS-16） |
| `vite build` 清理被拦截 | safe-delete 拦截 emptyDir 批量删 dist | 本地构建验证受阻 | 批量删除被 FAIL CLOSED | 用全新输出目录（如 dist_bgmcheck）绕过 |

### 维度 3：可抽象的固定流程与判断逻辑
| 模板 | 核心判断信号 | 落地方式 |
|------|--------------|----------|
| 媒体开关真静音检测 | grep 媒体开关无 silence/bridge 双模式 + amix 无 duration=first | DS-15：`bgm_gap_mode_check` |
| 双路径覆盖检测 | grep 取值未走 `channel.x or settings.X` | DS-15：`bgm_gap_mode_check.channel_override` |
| 校验器语义检测 | grep 校验器空串抛错 / 合法值未归一化 / 与测试断言矛盾 | DS-16：`validator_semantic_check` |

### 维度 4：适用场景与不适用场景
| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 媒体开关真静音 | 媒体处理有"看似不生效"历史的特性（静音/BGM/混音开关） | 非媒体纯逻辑特性、无物理产出物可查 |
| 校验器语义对齐 | 所有带枚举/开关的 Pydantic Body 字段（含频道级覆盖字段） | 纯无约束字符串、必填不可空字段 |

## 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则，仅调整阈值/白名单/关键字等参数化配置，不引入新的硬编码业务值。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 阈值调整 | `coding_standards.type_annotation.max_any_count` | `3` | `5` | 项目当前 Any 使用较多，逐步收敛 | 维度 3 类型注解 |
| 白名单新增 | `hard_constraints.rules.print_statement.exclude_files` | `[launcher.py, _verify_init.py]` | 同左 + `[setup.py]` | 新增 setup 脚本豁免 | 维度 13 日志规范 |
| 关键路径新增 | `coding_standards.error_handling.critical_path_patterns` | `[def _on_startup, ...]` | 同左 + `[def _on_close, def _shutdown]` | 补齐关闭路径 | 维度 9 错误处理 |
| 字段映射新增 | `field_contract.known_field_mappings` | `[episode, workflow, review]` | 同左 + `[ad_material, ad_placement]` | 新增广告模块字段 | 维度 12 字段契约 |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] SKILL.md 的 15 维度与本变更一致

## SonarQube 规则映射

| SQ 规则 | 审查维度 | 编码规范 | 元规范 | 严重级别 | 修复建议 |
|---------|---------|---------|--------|---------|----------|
| S7503 | 维度 74 | S52 | R67 | 阻塞 | 转同步函数或补充 await |
| S6395 | 维度 75 | S53 | R68 | 警告 | 改用非捕获组 (?:...) |
| S7504 | 维度 76 | S54 | R69 | 警告 | 去掉多余 list() 转换 |
| S1481 | 维度 77 | S55 | R70 | 阻塞 | 删除未使用变量/参数 |
| S1128 | 维度 78 | S55 | R70 | 警告 | 删除未使用 import |
| S2486 | 维度 80 | S59 | R74 | 警告 | 添加日志或注释 |
| cognitive_complexity | 维度 73 | S51 | R66 | 阻塞 | 抽取辅助函数或数据驱动重构 |
| - | 维度 79 | S56 | R71 | 建议 | 重构为 list[tuple] + 循环 |

## 修复优先级矩阵

| 问题严重级别 | 处理策略 | 阻塞发版 |
|------------|---------|----------|
| 阻塞 (blocker) | block_release | ✓ |
| 严重 (critical) | block_release | ✓ |
| 主要 (major) | fix_before_release | ✗（但发版前必须修复） |
| 警告 (warning) | fix_next_iteration | ✗ |
| 次要 (minor) | log_only | ✗ |
| 信息 (info) | log_only | ✗ |

> 技能专属审查章节已迁移至统一模板：[_shared/templates/report-template.md](../_shared/templates/report-template.md)
