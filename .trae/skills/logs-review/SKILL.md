---
name: Logs Review
description: 对后台服务运行时日志进行增量分析，识别 WARNING/ERROR 背后的真问题与噪声，按问题类型匹配修复策略，并行实施修复后验证闭环。所有业务参数通过 `config.yaml` 管理，技能本身不含任何硬编码值。se when cleaning up project workspaces, removing garbage files, organizing scattered scripts, or establishing file classification standards. Triggers on requests like "clean up the workspace", "organize the project structure", "centralize scripts into scripts/ directory", "remove junk files", or "建立文件分类标准". Config-driven, parameterized, no hardcoded paths.
---


## 何时使用

**触发关键词**：`日志分析`、`日志优化`、`warning 排查`、`日志噪声`、`增量日志`、`log review`、`日志治理`、`WARNING 修复`、`ERROR 排查`

**不适用场景**：一次性脚本/批处理任务、紧急热修复（除非启用 ast_mode）、日志格式完全非结构化、完全无测试覆盖（除非 erify.run_tests=false）、实时日志流（ELK/Kafka）、微服务多日志源（当前仅支持单文件）。

## 前置要求

1. **日志文件**：可访问的后台服务日志文件（current_log）
2. **基线快照**：可选的基线日志文件（baseline_log），首次运行可为空（全量模式）
3. **配置文件**：`.trae/skills/logs-review/config.yaml`（首次使用从 config.example.yaml 复制）
4. **测试命令**：可选的测试命令（verify.test_command），用于验证闭环


## 启动协议（分阶加载，按需消耗 token）

**核心原则**：根据场景复杂度分 3 个加载层级，简单场景只需读取 ~500 tokens，完整配置加载 ~2,700 tokens。

| 层级 | 加载内容 | 适用场景 | 预估 token |
|------|----------|----------|-----------|
| **L1 基础** | 仅读取 config.yaml 中的 logs.current_log、ilter.severities | 快速查看日志中的 WARNING/ERROR | ~500 |
| **L2 完整** | L1 + 读取 config.example.yaml 全部配置说明 | 首次配置或需调整高级参数 | ~2,700 |
| **L3 专家** | L2 + 读取 CONFIG_REFERENCE.md 详细约束 | 自定义副作用模式、并行策略等 | ~3,100 |

**自动选择逻辑**：
- 用户未指定层级时：根据日志文件大小自动选择（<1MB → L1，1-10MB → L2，>10MB 或含基线 → L3）
- 用户可通过 `config.yaml` 中 `mode` 字段显式指定：`auto`（默认）/ `l1` / `l2` / `l3`
- 显式指定优先于自动选择

**配置加载优先级**：环境变量 > config.yaml > config.example.yaml 默认值 > 技能内置默认值。

## 配置驱动


配置文件位置：.trae/skills/logs-review/config.yaml。首次使用时，从同目录的 config.example.yaml 复制并按项目实际情况修改。

**config.yaml 采用差异化配置**：仅保留与默认值不同的项，未列出的项自动使用 config.example.yaml 默认值。

**配置总览**：12 大类配置项详见 [config.example.yaml](config.example.yaml)，完整字段说明与约束条件见 [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)。

**环境变量覆盖规则**：所有配置项均可通过环境变量覆盖，规则：`LOGS_REVIEW_<SECTION>_<KEY>`（全大写，下划线分隔）。嵌套字段用双下划线：`LOGS_REVIEW_PARALLEL__SERIAL_THRESHOLD`。列表项用索引：`LOGS_REVIEW_FILTER__SEVERITIES__0=ERROR`。布尔值用 `1`/`0` 或 `true`/`false`。

## 工作流（6 阶段闭环）

### 交互确认点（仅 1 处）

**整个流程中仅 Phase 3 方案设计完成后需用户确认一次**，其余阶段自动执行：

- Phase 0/1/2：自动执行，输出简短摘要
- **Phase 3：输出方案清单，等待用户确认**（唯一确认点）
- Phase 4/5：确认后自动执行到底

### Phase 0: 前置检查（Pre-flight）

1. 读取 `config.yaml` 配置（缺失则使用 `config.example.yaml` 默认值并输出警告）
2. 验证 `logs.current_log` 文件存在
3. 若 `logs.baseline_log` 非空：验证基线文件存在（增量模式）
4. 若 `logs.baseline_log` 为空：切换为全量模式（首次运行）
5. 若 `verify.run_tests=true`：验证 `verify.test_command` 可执行
6. 若 `fast_mode.enabled=true`：标记跳过 `fast_mode.skip_phases` 中的阶段
7. 基线快照管理（按 `baseline.update_policy`）：
   - `manual`：不做处理，由用户维护
   - `post_release`：检测到发布标记后自动复制 current_log 为 baseline
   - `periodic`：检查 `baseline.snapshot_dir` 下快照是否超过 `update_interval_hours`，超时则更新
8. 任一失败则终止并输出诊断信息

**判断逻辑**：基线日志缺失不终止（降级为全量模式），但当前日志缺失必须终止。配置文件缺失不终止（使用默认值降级运行）。

### Phase 1: 增量提取（Extract）

**增量模式（有 baseline_log）**：
1. 读取 current_log 与 baseline_log（编码失败时按 `logs.encoding_fallback` 列表尝试）
2. 按行 diff，提取仅在 current_log 中出现的 WARNING/ERROR/CRITICAL 条目
3. 保留行号、时间戳、severity、模块名、message

**全量模式（无 baseline_log）**：
1. 读取 current_log 全部内容（编码失败时按 `logs.encoding_fallback` 列表尝试）
2. 提取所有匹配 `filter.severities` 的条目

**severity 识别**：
- `log_format=structured`：从 JSON 字段 `logs.severity_field` 读取
- `log_format=plaintext/mixed`：按 `logs.severity_pattern` 正则匹配（必须含命名分组 timestamp/severity/module/message）

**通用后处理**：
3. 应用 `filter.ignore_patterns`（正则）过滤忽略的 message
4. 应用 `filter.ignore_modules` 过滤忽略的模块
5. 若 `filter.deduplicate=true`：按 message 模板去重
   - 先按 `filter.dedup_normalize_patterns` 将动态字段（task_id、时间戳、hex 串）替换为 `{*}` 占位符
   - 再按规范化后的模板聚合，记录出现次数与首次/末次时间

### Phase 2: 分类归因（Classify）

按四维分类：**(模块, severity, 频率, 类型)**

**fast_mode 跳过**：若 `fast_mode.enabled=true` 且 `classify` 在 `skip_phases` 中，则仅按 severity 排序，跳过类型识别。

**4 大问题类型识别**：

| 类型 | 识别特征 | 典型示例 |
|------|----------|----------|
| `warning_noise` | 重复出现的相同 WARNING，无副作用 | business_kpi 告警频繁、重试提示刷屏 |
| `state_check` | 状态不一致导致的 ERROR | Cookie 过期未检查、session 失效未冷却 |
| `retry_failure` | 外部依赖偶发失败 | 网络超时、API 限流、get_cookies 失败 |
| `performance` | 慢查询、批处理缺失、重复计算 | list_links enrich 耗时、逐条 embedding |

**副作用识别**（区分噪声与真问题的关键）：
1. 按 `side_effect.harmful_patterns` 匹配 message → 有副作用，type 取 pattern 的 `type_hint`
2. 按 `side_effect.harmless_patterns` 匹配 → 无副作用，type 取 `type_hint`（通常为 warning_noise）
3. 按 `side_effect.performance_patterns` 匹配且数值超 `threshold_ms` → 性能问题
4. 未命中任何模式 → 按 4 大类型的识别特征启发式判断
5. 若 `classify.auto_downgrade_high_freq_noise=true`：高频 + 未命中 harmful → 自动降级为 warning_noise

**频率统计**：在 `classify.time_window_minutes` 时间窗口内统计出现次数，超过 `classify.frequency_threshold` 视为高频问题。

**优先级分配**：命中 harmful → `high`；命中 performance 且超阈值 → `medium`；命中 harmless → `low`；未命中 → 按 `side_effect.default_priority_by_severity` 映射。

**输出**：分类后的问题清单（JSON 格式）
```json
[{
  "issue_id": "log-001",
  "module": "scheduler",
  "file": "src/<package>/modules/scheduler.py",
  "line": 183,
  "severity": "WARNING",
  "type": "state_check",
  "priority": "high",
  "side_effect": "harmful",
  "message": "Cookie expired, task paused",
  "frequency": 12,
  "first_seen": "2026-07-03 10:00:00",
  "last_seen": "2026-07-03 10:30:00"
}]
```

### Phase 3: 方案设计（Plan）— **唯一用户确认点**

1. 按问题类型匹配 `strategies` 中的策略：
   - `warning_noise` → `merge_logs` / `reduce_frequency` / `skip`
   - `state_check` → `add_precondition` / `add_cooldown` / `skip`
   - `retry_failure` → `add_retry` / `add_backoff` / `skip`
   - `performance` → `add_timing` / `batch_process` / `add_cache` / `skip`
   - `custom` → 自定义策略（从 config 读取 prompt）

2. 生成修复方案清单（JSON 格式）：
```json
[{
  "issue_id": "log-001",
  "file": "src/<package>/modules/scheduler.py",
  "line": 183,
  "type": "state_check",
  "strategy": "add_precondition",
  "prompt": "在任务恢复前增加 Cookie 层状态检查，Cookie 失效时跳过恢复并记录日志",
  "priority": "high"
}]
```

3. 按文件路径分组（同目录的文件分到同组，便于上下文复用）
4. 按 priority 截取 `parallel.max_fix_per_run` 个最高优先级问题
5. **输出方案清单，等待用户确认后进入 Phase 4**

### Phase 4: 并行实施（Fix）

**fast_mode 处理**：若 `fast_mode.enabled=true` 且 `fast_mode.disable_parallel=true`，强制主代理串行。

**并行判断逻辑**（按优先级）：
1. 问题总数 <= `parallel.serial_threshold` → 主代理串行（避免子代理启动开销）
2. 问题总数 > `parallel.serial_threshold` 且文件组数 > 1 且 `parallel.enabled=true` 且 `parallel.agents>1` → 启用并行子代理
3. 否则 → 主代理串行处理
4. `parallel.same_file_serial=true` 时：同一文件内多个问题串行处理（避免 Edit 冲突）
5. 跨模块依赖组（`parallel.dependency_groups`）：同组内的文件必须串行处理

**启用并行时**：
1. 用 `Task` 工具启动 `parallel.agents` 个子代理
2. 每个子代理分配 `parallel.files_per_agent` 个文件
3. 同一 dependency_group 的文件分到同一子代理
4. 子代理任务模板见下方

**子代理任务模板**：

```
修复以下日志问题（issues JSON）：
<issues JSON>

参数注入规则：仅注入与本问题 type_hint 匹配的 business_params（按 _scope 筛选）。
例如：type_hint=state_check 的子代理仅接收 _scope 包含 state_check 的参数。
未标注 _scope 的参数视为全局参数，所有子代理均接收。

要求：Read 上下文（重点看 issue.line 附近）→ 分析根因 → Edit 修复 → 返回 JSON
返回格式：{"fixed":[{"issue_id":"..."}],"skipped":[{"issue_id":"..."}]}

原则：
- 只修改必要部分，不顺便修改旁边的代码
- 注释解释"为什么"而非"做什么"
- 业务参数从 config 读取，不硬编码
```

### Phase 5: 验证报告（Verify & Report）

**验证**：
1. 若 `verify.recheck_logs=true`：
   - 修复文件数 = 0：跳过日志重采集，仅运行测试
   - 修复文件数 > 0：等待 `verify.cooldown_seconds`（让服务产生新日志），重新采集日志，对比修复前后的 WARNING/ERROR 数量
2. 若 `verify.run_tests=true`：运行 `verify.test_command`（超时 `verify.test_timeout_seconds` 秒则报告但不终止）
3. 若 `verify.isolate_preexisting_failures=true`：对比修复前后测试结果，只关注新增失败，预存失败不阻塞合并
4. 若 `verify.check_test_side_effects=true`：
   - 扫描测试输出，匹配 `verify.test_side_effect_patterns`
   - 命中则报告"修复可能引入测试副作用"，建议检查：
     - 同步/异步方法签名一致性（await 同步方法会抛 TypeError）
     - Mock 类型与生产代码匹配（AsyncMock vs MagicMock）
     - 新增校验逻辑的测试环境副作用（如 Cookie 校验在测试环境误判失效）
5. 若 `verify.fail_on_new_warnings=true` 且发现新 WARNING：输出新问题清单，建议回滚或继续修复
6. 硬约束合规性检查：遍历 `hard_constraints.rules`，对每条规则按 `hard_constraints.scan_scope` 决定扫描范围：
   - `modified_only`（默认）：仅扫描 Phase 4 修改过的文件（节省 token）
   - `full`：扫描整个代码库
7. 若 `verify.trigger_code_review=true`：建议用户触发后端/前端代码评审技能进行修复后评审

**报告生成**：
生成 Markdown 报告到 `report.output_dir`，应用 `report.redact_patterns` 脱敏规则后输出。

按 `report.detail_level` 控制详细程度：
- `summary`：仅输出修复清单 + 验证结果 + 硬约束合规性（适合常规迭代）
- `detailed`（默认）：完整 7 节报告（日志摘要、修复清单、未修复项、硬约束合规性、验证结果、凭据安全检查、基线快照状态）

报告文件名格式：`logs-review-report-YYYYMMDD-HHmmss.md`

**结构化输出模板**（按 `report.detail_level` 控制）：

- `summary`：
  ```
  ## Logs Review Summary
  - Issues found: N (high: n1, medium: n2, low: n3)
  - Fixed: N | Skipped: N
  - Tests: PASS/FAIL (N passed, N failed)
  - New warnings after fix: Y/N
  - Hard constraints: PASS/FAIL (N violations)
  ```

- `detailed`（默认）：在 summary 基础上追加 7 节完整内容（日志摘要、修复清单、未修复项、硬约束合规性、验证结果、凭据安全检查、基线快照状态）

**输出压缩规则**：
- 分类报告使用表格格式，不使用段落叙述
- 验证报告中日志差异仅展示**新增/消失条目**，不展示全量日志
- 测试结果仅报告**失败用例**和**变化统计**，不罗列全部通过用例

## 核心判断逻辑

### 1. 噪声 vs 真问题判断
- **噪声特征**：频率超 `classify.frequency_threshold` 且无副作用（不影响业务流程）
  → 策略：`merge_logs`（合并重复日志）/ `reduce_frequency`（降低告警频率）
- **真问题特征**：状态一致性缺失、数据丢失风险、业务流程中断
  → 策略：`add_precondition`（增加前置检查）/ `add_cooldown`（增加冷却）
- **偶发失败特征**：外部依赖超时、API 限流，非业务逻辑错误
  → 策略：`add_retry`（增加重试）/ `add_backoff`（退避重试）

### 2. 副作用识别判断
通过 `side_effect` 配置的 message 模式匹配判断日志是否有实际业务副作用：
- 命中 `harmful_patterns`（如 "expired + pause"）→ 有副作用，优先级 high，type 取 `type_hint`
- 命中 `harmless_patterns`（如 "deprecated + continue"）→ 无副作用，优先级 low，type 为 warning_noise
- 命中 `performance_patterns` 且数值超 `threshold_ms` → 性能问题，优先级 medium
- 未命中任何模式 → 按 severity 映射（`default_priority_by_severity`）
- `classify.auto_downgrade_high_freq_noise=true` 时：高频 + 未命中 harmful → 自动降级为 warning_noise

### 3. 优化深度判断
- **仅日志层**（不影响业务）：合并/降级，最小改动
- **业务逻辑层**（影响流程）：增加状态检查/冷却，需测试覆盖
- **性能层**（影响吞吐）：计时/批处理/缓存，需性能基准对比

### 4. 并行拆分判断
- 问题总数 <= `parallel.serial_threshold` → 主代理串行（避免子代理启动开销）
- 不同文件且无依赖且问题数 > `serial_threshold` → 可并行
- 同文件多问题：串行（避免 Edit 冲突），由 `parallel.same_file_serial` 控制
- 跨模块依赖组（`parallel.dependency_groups` 声明的文件组）：同组串行
- `fast_mode.disable_parallel=true` 时：强制串行

### 5. 修复策略匹配判断

### 5.5 子代理参数作用域筛选
**目的**：避免向子代理注入无关的 business_params，降低 prompt token 消耗。

**规则**：
1. 每个 business_params 项可附加 `_scope` 字段，标注适用的问题类型（数组）
2. 子代理仅接收与其负责问题的 `type_hint` 匹配的参数字段
3. 未标注 `_scope` 的参数视为全局参数，所有子代理均接收
4. 示例：
   ```yaml
   business_params:
     session_cooldown_seconds: 300
       _scope: ["state_check"]       # 仅状态检查类问题需要
     fetch_max_retries: 1
       _scope: ["retry_failure"]      # 仅重试类问题需要
     embedding_batch_size: 32
       _scope: ["performance"]        # 仅性能类问题需要
     log_prefix: "hunter"            # 无 _scope → 全局参数，所有子代理接收
   ```
按问题类型从 `strategies` 配置中查找策略。策略为 `skip` 时不修复，仅记录到报告。`custom` 策略从 config 读取 `prompt` 字段作为子代理指令。

### 6. 验证闭环判断
- 修复文件数 = 0：跳过日志重采集，仅运行测试
- 修复文件数 > 0：必须重新采集日志
- 重新采集后发现新 WARNING：必须处理（修复或回滚）
- 测试失败：若 `isolate_preexisting_failures=true`，区分新增失败与预存失败
- 预存失败：记录但不阻塞，输出到报告供后续处理
- 测试副作用命中：报告但不终止，建议用户检查同步/异步签名、Mock 类型、校验副作用



### 核心判断逻辑流程图

#### 1. 噪声 vs 真问题
```
频率 > frequency_threshold ─┬─ 命中 harmless_patterns → 噪声（降级）
                             ├─ 命中 harmful_patterns → 真问题（保持 high）
                             └─ 未命中 → 按 auto_downgrade_high_freq_noise 决定
```

#### 2. 副作用识别
```
日志 message ──→ 匹配 harmful_patterns ──→ 真问题（优先级 high）
            ├──→ 匹配 harmless_patterns ──→ 噪声（优先级 low）
            ├──→ 匹配 performance_patterns ──→ 性能问题（优先级 medium）
            └──→ 未匹配 ──→ default_priority_by_severity[severity]
```

#### 3. 并行拆分
```
问题总数 ≤ serial_threshold ──→ 主代理串行
问题总数 > serial_threshold ──→ 按文件分组
    ├── 不同文件 + 无依赖 ──→ 并行（最多 agents 个子代理）
    ├── 同文件 ──→ 串行
    └── 同 dependency_group ──→ 串行
```

#### 4. 修复策略匹配
```
问题类型 ──→ strategies[type] ──→ skip（仅记录）
                          ├──→ merge_logs / reduce_frequency（噪声类）
                          ├──→ add_precondition / add_cooldown（状态类）
                          ├──→ add_retry / add_backoff（重试类）
                          ├──→ add_timer / add_batch / add_cache（性能类）
                          └──→ custom（从 config.strategies[type].prompt 读取指令）
```

#### 5. 验证闭环
```
修复完成 ──→ 文件数=0 ──→ 仅运行测试
          ├──→ 文件数>0 ──→ 重新采集日志
          │              ├──→ 有新 WARNING ──→ 修复或回滚
          │              └──→ 无新 WARNING ──→ 通过
          └──→ 测试失败
                     ├──→ isolate_preexisting_failures=true ──→ 区分新增/预存
                     └──→ block_on_violation=true ──→ 硬约束违规则阻断
```
## 失败恢复机制（通用原则）

**核心原则**：仅关键节点（当前日志缺失、硬约束违规则阻断）终止流程，其余情况降级或报告。

| 场景 | 行为 |
|------|------|
| 当前日志文件不存在 | 终止，输出配置指南 |
| 基线日志缺失 | 降级为全量模式，不终止 |
| 配置文件缺失 | 使用默认值降级运行，输出警告 |
| 子代理超时 | 终止超时子代理，主代理接管剩余任务 |
| Edit 冲突 | 子代理串行处理同一文件内的多个问题 |
| 验证失败 | 输出 diff 供用户决策，不自动回滚 |
| 测试预存失败 | 隔离记录，不阻塞本次优化合并 |
| 测试命令执行失败 | 报告但不终止，建议检查 `verify.test_command` |
| 日志编码错误 | 按 `encoding_fallback` 尝试，全部失败则终止 |
| 子代理返回格式错误 | 主代理解析失败结果，记录原始返回并跳过 |
## 安全注意事项

1. **凭据**：日志文件可能包含敏感信息（token、用户 ID），报告生成时需脱敏
2. **硬编码检测**：硬约束规则 `no_hardcoded_credentials` 会扫描代码库（按 `hard_constraints.scan_scope` 决定范围）
3. **报告脱敏**：按 `report.redact_patterns` 配置的正则规则脱敏，默认覆盖 token/password/secret/api_key/send_key/bearer/长 hex 串
4. **凭据吊销**：若在日志中发现泄露凭据，技能会建议立即吊销并提示操作步骤
5. **脱敏规则可扩展**：项目特有的敏感字段格式可通过 `report.redact_patterns` 添加自定义规则

## 与现有工具的关系

- **sonarqube-mcp**：静态扫描修复；本技能为运行时日志修复。两者正交可组合。
- **代码评审技能**：`verify.trigger_code_review=true` 时修复完成后建议触发评审。
- **Task 工具**：启动并行修复子代理。
## 适用场景与限制

### 适用场景
- 后台服务的 WARNING/ERROR 日志增量分析
- 识别高频噪声日志并降噪
- 定位状态一致性、重试耗尽、性能瓶颈等真问题
- 并行修复后验证闭环（日志重采集 + 测试）
- 单文件日志分析（同一服务实例的输出）

### 不适用场景
- 实时日志流（ELK/Kibana/Grafana Loki）
- 微服务多日志源跨文件关联分析
- 日志格式完全非结构化（无时间戳、无级别标识）
- 前端浏览器控制台日志
- 需要修改数据库 schema 或基础设施配置的变更
