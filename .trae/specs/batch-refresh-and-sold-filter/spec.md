# 批量采集与已售商品过滤优化 Spec

## Why

当前商品列表存在两个核心问题：
1. **老数据未更新**：商品信息采集依赖用户手动点击标题链接触发，无定时批量刷新机制，导致价格、已售状态等字段过时
2. **已售商品仍展示**：虽然 `mark_sold` 已正确写入 items 表，但 `list_links` 端点的 `_enrich_with_item_data` 已修复补全 is_sold，前端缺少按状态筛选的能力，用户无法快速过滤已售商品

本方案在现有调度器和防爬体系基础上，新增定时批量采集任务、状态筛选功能，并标准化 is_sold 字段类型。

## What Changes

### 后端
- 新增 `BatchRefreshScheduler` 批量刷新调度器，定时采集"在售"商品详情，复用现有 `collector.detail()` + `refresh_item` 逻辑
- 新增 `GET/POST /api/batch-refresh` 端点，支持查询任务状态、手动触发、配置执行频率
- `list_links` 端点新增 `sold_filter` 参数（`all`/`onsale`/`sold`），SQL 下推过滤
- `evaluations` list 端点新增 `sold_filter` 参数，Python 端过滤
- 统一 is_sold 类型：`_enrich_with_item_data` 输出 `bool`，`mark_sold` 输出 `bool`，items 表保持 `int` 存储但读取时转 `bool`

### 前端
- 商品列表页（ItemList.tsx）新增状态筛选 Select（全部/在售/已售），默认"在售"，使用 `usePersistentState` 持久化
- 评估明细页（Evaluations/index.tsx）新增状态筛选 Select，并补全 is_sold 列渲染
- 评估明细页 5 个筛选条件（itemId/taskId/scoreRange/dateRange/brandFilter）改用 `usePersistentState` 持久化
- 商品列表页新增"最后更新时间"列（读取 `task_links.updated_at`）

### 不做的事情（避免过度设计）
- **不重新开发防爬机制**：项目已有完善的防爬体系（anti_detect/freq_disguise/fingerprint/awsc_spoof/cookie_rotator 等 10 个模块），批量采集复用现有 `collector.detail()` 即可享受全部防爬能力
- **不新增数据归档机制**：已售商品通过 `sold_filter` 过滤展示即可，不需要软删除/归档
- **不新增 IP 轮换/UA 随机化**：现有 `proxy_pool.py` 和 `fingerprint.py` 已实现，批量采集自动复用
- **不新增用户反馈入口**：超出当前需求范围，后续迭代再考虑

## Impact

- Affected code:
  - `src/xianyu_hunter/modules/batch_refresh_scheduler.py`（新增）
  - `src/xianyu_hunter/web/routes/api_batch_refresh.py`（新增）
  - `src/xianyu_hunter/web/routes/api_task_links.py`（修改：list_links 新增 sold_filter）
  - `src/xianyu_hunter/web/routes/api_evaluations.py`（修改：evaluations list 新增 sold_filter）
  - `src/xianyu_hunter/web/routes/api_items.py`（修改：refresh_item 记录变更日志）
  - `src/xianyu_hunter/web/startup.py`（修改：启动批量刷新调度器）
  - `src/xianyu_hunter/infra/yaml_config.py`（修改：新增 batch_refresh 配置段）
  - `frontend/src/pages/Items/ItemList.tsx`（修改：新增状态筛选 + 更新时间列）
  - `frontend/src/pages/Evaluations/index.tsx`（修改：新增状态筛选 + is_sold 列 + 筛选持久化）
  - `frontend/src/api/types.ts`（修改：新增 BatchRefreshStatus 类型）
  - `config/config.yaml`（修改：新增 batch_refresh 配置）

## ADDED Requirements

### Requirement: 定时批量采集调度器
系统 SHALL 提供 `BatchRefreshScheduler`，定时批量刷新"在售"商品的详情数据。

#### Scenario: 定时触发批量采集
- **WHEN** 到达配置的执行时间（默认每 30 分钟）
- **THEN** 系统查询所有 `is_sold=0` 的商品，按 `antidetect.qps` 限速逐个调用 `collector.detail()` 刷新
- **AND** 每次刷新后更新 items 表 + task_links.display
- **AND** 记录刷新日志（item_id、变更字段、时间戳）

#### Scenario: 失败重试
- **WHEN** 单个商品采集失败
- **THEN** 记录失败原因，跳过该商品继续处理下一个
- **AND** 连续失败超过 `fail_pause_threshold` 时暂停当前批次

#### Scenario: 手动触发
- **WHEN** 用户通过 `POST /api/batch-refresh/trigger` 手动触发
- **THEN** 立即执行一次批量采集，返回任务 ID供轮询状态

### Requirement: 批量采集管理端点
系统 SHALL 提供 REST 端点管理批量采集任务。

#### Scenario: 查询状态
- **WHEN** GET `/api/batch-refresh/status`
- **THEN** 返回当前任务状态（idle/running）、上次执行时间、上次结果统计（成功/失败/跳过数）

#### Scenario: 配置执行频率
- **WHEN** PATCH `/api/batch-refresh/config` with `{"interval_minutes": 60}`
- **THEN** 更新定时采集间隔，下次执行按新间隔调度

### Requirement: 状态筛选功能
商品列表和评估明细页 SHALL 支持按销售状态筛选。

#### Scenario: 商品列表按状态筛选
- **WHEN** 用户在商品列表页选择"已售"筛选
- **THEN** 后端 `list_links` 端点通过 `sold_filter=sold` 参数 SQL 下推过滤
- **AND** 仅返回 `is_sold=True` 的商品

#### Scenario: 默认筛选为在售
- **WHEN** 用户首次打开商品列表页
- **THEN** 默认筛选为"在售"，仅展示 `is_sold=False` 的商品
- **AND** 用户可切换为"全部"查看含已售的所有商品

#### Scenario: 筛选条件记忆
- **WHEN** 用户切换筛选后刷新页面
- **THEN** 筛选状态从 localStorage 恢复，保持上次选择

### Requirement: 数据更新时间显示
商品列表 SHALL 显示每条商品的最后更新时间。

#### Scenario: 显示更新时间
- **WHEN** 商品列表渲染时
- **THEN** 显示 `task_links.updated_at` 字段为相对时间（如"3分钟前"）
- **AND** 支持按更新时间排序

## MODIFIED Requirements

### Requirement: list_links 端点筛选
`list_links` 端点 SHALL 新增 `sold_filter` 参数。

#### Scenario: sold_filter=all
- **WHEN** `sold_filter=all`
- **THEN** 返回所有商品（含已售和未售），与现有行为一致

#### Scenario: sold_filter=onsale
- **WHEN** `sold_filter=onsale`
- **THEN** 仅返回 `is_sold=0` 的商品（SQL WHERE is_sold=0）

#### Scenario: sold_filter=sold
- **WHEN** `sold_filter=sold`
- **THEN** 仅返回 `is_sold=1` 的商品（SQL WHERE is_sold=1）

### Requirement: evaluations list 端点筛选
`evaluations` list 端点 SHALL 新增 `sold_filter` 参数。

#### Scenario: 评估列表按状态过滤
- **WHEN** `sold_filter=onsale`
- **THEN** 从 items 表批量查询 is_sold 状态，过滤掉已售商品的评估记录

### Requirement: 评估明细页筛选条件持久化
评估明细页的 5 个核心筛选条件 SHALL 使用 `usePersistentState` 持久化。

#### Scenario: 刷新页面恢复筛选
- **WHEN** 用户设置筛选条件后刷新页面
- **THEN** itemId/taskId/scoreRange/dateRange/brandFilter 从 localStorage 恢复
