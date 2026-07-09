# 强化自动官方采集 Spec

## Why

`auto_collect_official` 功能已在 `worker.py:398-414` + `api_evaluations.py:1736-1945` 完整实现并接入主流程，但存在三类质量缺口：
1. **配置同步缺口**：`config.example.yaml` 缺失整个 `eval` 段，新部署者看不到 `auto_collect_official` 配置项
2. **测试零覆盖**：`tests/` 中该功能无任何单元测试，四个 AND 触发条件、旧值保留策略、提取失败分支均无回归保护
3. **可观测性弱**：`data_source` 仅写在 `events.payload` JSON 中无法高效筛选；无去重机制可能重复采集；连续失败无退避；前端无采集指标可视化

本 spec 聚焦质量补齐 + 韧性增强 + 可观测性，不重新实现功能。

## What Changes

### P0 质量补齐
- 补齐 `config.example.yaml` 的 `eval` 段，与 `yaml_config.py:EvalConfig` 对齐
- 新增 `tests/test_worker_auto_collect.py`：覆盖 worker 触发的四个 AND 条件 + 计数自增
- 新增 `tests/test_official_collect_integration.py`：mock collector，验证 `_collect_official_and_evaluate` 的 `_coalesce` 旧值保留策略 + `data_source=official` 标记
- 新增 `tests/test_detail_extract_failure.py`：回归 `_detail.py` 提取失败（标题空/价格 ≤0/重定向/首页标题）显式返回 None 的所有分支
- 在 `api_items.py:refresh_item` 与 `api_evaluations.py:_collect_official_and_evaluate` 的 docstring 中明确语义边界（前者轻量刷新，后者完整官方采集+评估）

### P1 韧性增强
- **BREAKING**：`items` 表新增 `data_source TEXT` 列（取值 `search` / `official` / `live`），默认 `search`；提供迁移脚本回填历史数据
- `worker.py` 自动官方采集前检查 `items.updated_at`，30 分钟内已采集过的商品跳过
- `worker.py` 引入"连续 N 次失败后暂停自动采集"退避机制（默认 N=3，可通过配置 `auto_collect_fail_pause_threshold` 调整）
- 失败暂停时通过 `notifier` 发送告警
- `EvalConfig` 新增 `auto_collect_dedup_window_minutes: int = 30` 和 `auto_collect_fail_pause_threshold: int = 3`

### P2 可观测性
- 前端 `EvalRules.tsx` 新增"最近 24 小时自动采集"指标卡片（采集次数 / 成功率 / 失败原因 Top3），数据来自 `events` 表
- 后端新增 `GET /api/evaluations/auto-collect-stats` 端点，返回最近 24 小时统计
- 验证任务级 `auto_collect_official` 覆盖逻辑：确认 `api_tasks.py` 创建任务时任务级配置与全局配置的合并优先级正确

## Impact

### Affected specs
- `batch-refresh-and-sold-filter`（本 spec 的 `data_source` 列与 items 表关联，可能影响 list_links 端点）

### Affected code
**配置层**：
- `src/xianyu_hunter/infra/yaml_config.py`（EvalConfig 新增 2 字段）
- `config/config.example.yaml`（补齐 eval 段）
- `config/config.yaml`（同步新增字段）

**核心逻辑**：
- `src/xianyu_hunter/modules/worker.py`（去重检查 + 退避机制 + 统计字段扩展）
- `src/xianyu_hunter/web/routes/api_evaluations.py`（`_collect_official_and_evaluate` 写入 `items.data_source`）
- `src/xianyu_hunter/web/routes/api_items.py`（refresh_item docstring 边界说明）
- `src/xianyu_hunter/infra/repo_items.py`（新增 `update_data_source` 方法 + 去重查询方法）
- `src/xianyu_hunter/infra/db_models.py`（ItemRow 新增 `data_source` 列）
- `src/xianyu_hunter/infra/repository.py`（schema 迁移，CREATE COLUMN IF NOT EXISTS）

**API 层**：
- `src/xianyu_hunter/web/routes/api_evaluations.py` 新增 `GET /auto-collect-stats` 端点
- `src/xianyu_hunter/web/routes/api_tasks.py` 验证任务级覆盖合并逻辑

**前端**：
- `frontend/src/pages/Config/EvalRules.tsx`（新增指标卡片 + 失败暂停状态展示）
- `frontend/src/api/evaluation.ts`（新增 `getAutoCollectStats` 方法）
- `frontend/src/api/types.ts`（EvalConfig 类型扩展 2 字段）

**测试**：
- `tests/test_worker_auto_collect.py`（新增）
- `tests/test_official_collect_integration.py`（新增）
- `tests/test_detail_extract_failure.py`（新增）
- `tests/test_items_data_source_migration.py`（新增）
- `tests/test_task_level_auto_collect_override.py`（新增）

## ADDED Requirements

### Requirement: 配置示例同步
The system SHALL 在 `config.example.yaml` 中提供完整的 `eval` 配置段，包含 `pass_score` / `auto_buy_score` / `ai_auto_eval` / `ai_auto_deep_analyze` / `auto_collect_official` / `auto_collect_max_per_run` / `auto_collect_dedup_window_minutes` / `auto_collect_fail_pause_threshold` / `ai_multi_run_suggestion` / `ai_suggestion_interval` 全部字段及中文注释，与 `yaml_config.py:EvalConfig` 字段对齐。

#### Scenario: 新部署者拷贝 example 后可看到所有 eval 配置
- **WHEN** 用户从 `config.example.yaml` 拷贝配置
- **THEN** 文件包含完整 `eval` 段，所有字段有默认值与中文注释

### Requirement: 自动官方采集中断单元测试覆盖
The system SHALL 通过 `tests/test_worker_auto_collect.py` 覆盖 `worker.py:398-414` 自动官方采集触发逻辑的全部边界条件。

#### Scenario: 四个 AND 条件中任一不满足时不触发采集
- **WHEN** `eval_cfg.auto_collect_official` 为 False / `official_collect_fn` 为 None / `stats.official_collected >= max_per_run` / 商品未通过 pass_score
- **THEN** `official_collect_fn` 不被调用，`stats.official_collected` 不自增

#### Scenario: 全部条件满足时触发采集并自增计数
- **WHEN** 四个 AND 条件全部满足
- **THEN** `official_collect_fn(detail.id, task.id)` 被调用一次，`stats.official_collected` 自增 1

#### Scenario: 采集函数抛异常时记录 warning 并继续
- **WHEN** `official_collect_fn` 抛出异常
- **THEN** 异常被捕获，`logger.warning` 记录原因，循环继续处理下一个商品，`stats.official_collected` 不自增

### Requirement: 官方采集旧值保留策略单元测试
The system SHALL 通过 `tests/test_official_collect_integration.py` 验证 `_collect_official_and_evaluate` 的 `_coalesce` 旧值保留策略与 `data_source=official` 标记。

#### Scenario: 新值为空时保留旧值
- **WHEN** collector 返回的 detail 中某字段为空，而 DB 中 items 表已有旧值
- **THEN** 旧值被保留，不被空值覆盖

#### Scenario: ALWAYS_OVERWRITE 白名单字段强制覆盖
- **WHEN** collector 返回的 detail 中 `task_id` / `publish_time` / `view_cnt` / `want_cnt` / `region` / `seller_id` / `is_sold` 字段有新值
- **THEN** 即使旧值非空也被覆盖

#### Scenario: 采集成功后写入 data_source=official
- **WHEN** `_collect_official_and_evaluate` 成功完成
- **THEN** `items.data_source` 字段被更新为 `'official'`，`events.payload.data_source` 也标记为 `'official'`

### Requirement: detail 提取失败分支回归测试
The system SHALL 通过 `tests/test_detail_extract_failure.py` 覆盖 `_detail.py` 提取失败时显式返回 None 的所有分支。

#### Scenario: 标题为空时返回 None
- **WHEN** 详情页标题选择器、og:title、document.title 全部失败
- **THEN** `detail()` 返回 None（不返回半残数据）

#### Scenario: 价格 ≤ 0 时返回 None
- **WHEN** 详情页价格提取结果 ≤ 0
- **THEN** `detail()` 返回 None

#### Scenario: HTTP 4xx/5xx 时返回 None
- **WHEN** `page.goto` 响应状态码 ≥ 400
- **THEN** `detail()` 返回 None，并记录 warning

#### Scenario: HTTP 3xx 重定向时返回 None
- **WHEN** `page.goto` 响应状态码 ≥ 300
- **THEN** `detail()` 返回 None，并记录 warning 含重定向目标 URL

### Requirement: items 表 data_source 字段
The system SHALL 在 `items` 表新增 `data_source TEXT` 列，取值 `search` / `official` / `live`，默认 `search`。

#### Scenario: 历史数据迁移
- **WHEN** 数据库升级时发现 `items` 表无 `data_source` 列
- **THEN** 自动添加该列，默认值 `'search'`，所有历史行被回填为 `'search'`

#### Scenario: list_links 端点支持按 data_source 过滤
- **WHEN** 前端调用 `list_links` 时传 `data_source=official`
- **THEN** 仅返回 `items.data_source='official'` 的商品行

### Requirement: 自动官方采集去重
The system SHALL 在 `worker.py` 触发自动官方采集前检查 `items.updated_at`，若商品在 `auto_collect_dedup_window_minutes`（默认 30 分钟）内已被采集过，则跳过。

#### Scenario: 30 分钟内已采集过的商品被跳过
- **WHEN** `items.updated_at` 距当前时间 < 30 分钟
- **THEN** 该商品不被重复采集，`stats.official_collected` 不自增，日志记录"跳过（去重窗口内）"

#### Scenario: 超过 30 分钟的商品正常采集
- **WHEN** `items.updated_at` 距当前时间 ≥ 30 分钟，或 `updated_at` 为 NULL
- **THEN** 该商品正常进入采集流程

### Requirement: 自动官方采集失败退避
The system SHALL 在 `worker.py` 引入"连续 N 次失败后暂停自动采集"退避机制，N 由 `auto_collect_fail_pause_threshold`（默认 3）控制。

#### Scenario: 连续失败达到阈值时暂停本轮自动采集
- **WHEN** 自动官方采集连续失败次数 ≥ `auto_collect_fail_pause_threshold`
- **THEN** 本轮剩余商品不再触发自动采集，`stats.official_collect_paused=True`，日志记录暂停原因

#### Scenario: 暂停时通过 notifier 发送告警
- **WHEN** 自动采集被暂停
- **THEN** 通过 `notifier` 发送告警，包含任务名、失败次数、最后失败原因

#### Scenario: 下轮任务重置失败计数
- **WHEN** 新一轮 `run_once` 开始
- **THEN** 连续失败计数重置为 0，暂停状态清除

### Requirement: 自动采集统计端点
The system SHALL 提供 `GET /api/evaluations/auto-collect-stats` 端点，返回最近 24 小时自动官方采集统计。

#### Scenario: 返回统计数据
- **WHEN** 调用 `GET /api/evaluations/auto-collect-stats`
- **THEN** 返回 JSON：`{total: int, success: int, failed: int, success_rate: float, top_failures: [{reason: str, count: int}]}`

### Requirement: 前端采集指标可视化
The system SHALL 在 `EvalRules.tsx` 自动官方采集卡片下方新增"最近 24 小时采集"指标展示。

#### Scenario: 显示采集次数与成功率
- **WHEN** 用户进入 `EvalRules` 页面
- **THEN** 看到"最近 24 小时：共 N 次 / 成功 M 次 / 成功率 X%"，每 60 秒自动刷新

#### Scenario: 失败暂停状态展示
- **WHEN** 自动采集处于失败暂停状态
- **THEN** 卡片显示红色 Tag"已暂停（连续失败 N 次）"，并展示 Top3 失败原因

### Requirement: 任务级 auto_collect_official 覆盖验证
The system SHALL 验证任务级 `auto_collect_official` 配置覆盖全局配置的合并逻辑正确。

#### Scenario: 任务级开关关闭时全局开关不生效
- **WHEN** 全局 `auto_collect_official=true`，任务级 `auto_collect_official=false`
- **THEN** 该任务不触发自动官方采集

#### Scenario: 任务级 max_per_run 覆盖全局
- **WHEN** 全局 `auto_collect_max_per_run=3`，任务级 `auto_collect_max_per_run=10`
- **THEN** 该任务单轮最多采集 10 个商品

## MODIFIED Requirements

### Requirement: refresh_item 端点语义边界文档
`api_items.py:refresh_item` 端点 SHALL 在 docstring 中明确标注：该端点仅采集 `collector.detail()` 并 `upsert_item`，**不**触发重新评估、**不**采集卖家主页、**不**提取评价，是"轻量刷新"。完整官方采集应使用 `POST /api/evaluations/{item_id}/collect-official`。

#### Scenario: 维护者通过 docstring 区分两个端点
- **WHEN** 维护者阅读 `refresh_item` 源码
- **THEN** docstring 明确说明语义边界，引导维护者使用正确端点

### Requirement: _collect_official_and_evaluate 函数文档
`api_evaluations.py:_collect_official_and_evaluate` SHALL 在 docstring 中明确标注：该函数执行完整官方采集流程（detail + seller_profile + reviews + 重新评估 + events 写入），是"完整官方采集"。

#### Scenario: 维护者通过 docstring 理解完整流程
- **WHEN** 维护者阅读该函数源码
- **THEN** docstring 列出全部步骤（采集 detail / 并行 seller_profile + reviews / 降级 seller_profile_fallback / 持久化 / 重新评估 / events 写入）

## REMOVED Requirements

无移除项。本 spec 不删除任何现有功能。
