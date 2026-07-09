# Tasks

## 阶段一：后端 — 批量采集调度器

- [x] Task 1: 新增 `BatchRefreshScheduler` 批量刷新调度器
  - [x] SubTask 1.1: 创建 `src/xianyu_hunter/modules/batch_refresh_scheduler.py`，基于 asyncio 后台循环实现定时批量采集
  - [x] SubTask 1.2: 实现批量采集逻辑：查询 `is_sold=0` 的商品列表，逐个调用 `collector.detail()` 刷新，复用 `refresh_item` 端点的合并写库逻辑
  - [x] SubTask 1.3: 实现失败重试和熔断：单个商品失败记录原因并跳过，连续失败超过 `fail_pause_threshold` 暂停当前批次
  - [x] SubTask 1.4: 实现变更日志记录：每次刷新后记录 item_id、变更字段列表、时间戳到内存状态

- [x] Task 2: 新增批量采集配置段
  - [x] SubTask 2.1: 在 `yaml_config.py` 新增 `BatchRefreshConfig` 配置段（interval_minutes、enabled、batch_size、max_items_per_run）
  - [x] SubTask 2.2: 在 `config/config.yaml` 和 `config/config.example.yaml` 添加 `batch_refresh` 配置段

- [x] Task 3: 新增批量采集管理 API 端点
  - [x] SubTask 3.1: 创建 `src/xianyu_hunter/web/routes/api_batch_refresh.py`，提供 `GET /api/batch-refresh/status`、`POST /api/batch-refresh/trigger`、`PATCH /api/batch-refresh/config` 端点
  - [x] SubTask 3.2: 在 `web/app.py` 注册新路由

- [x] Task 4: 启动时注入批量刷新调度器
  - [x] SubTask 4.1: 在 `web/startup.py` 的 startup 钩子中启动 `BatchRefreshScheduler`（仅当 `XH_WITH_SCHEDULER=1` 且 `batch_refresh.enabled=true`）
  - [x] SubTask 4.2: 在 shutdown 钩子中停止调度器

## 阶段二：后端 — 状态筛选

- [x] Task 5: `list_links` 端点新增 `sold_filter` 参数
  - [x] SubTask 5.1: 在 `api_task_links.py` 的 `list_links` 端点新增 `sold_filter: str = "all"` 参数
  - [x] SubTask 5.2: 在 `repo_links.py` 的 `list_and_count_task_links` 方法新增 `sold_filter` 参数，SQL WHERE 条件下推（JOIN items 表按 is_sold 过滤）
  - [x] SubTask 5.3: 确保 `sold_filter=all` 时行为与现有完全一致（无性能回归）

- [x] Task 6: `evaluations` list 端点新增 `sold_filter` 参数
  - [x] SubTask 6.1: 在 `api_evaluations.py` 的 evaluations list 端点新增 `sold_filter: str = "all"` 参数
  - [x] SubTask 6.2: 从 items 表批量查询 is_sold 状态，在 Python 端过滤评估记录

## 阶段三：前端 — 状态筛选与持久化

- [x] Task 7: 商品列表页新增状态筛选
  - [x] SubTask 7.1: 在 `ItemList.tsx` 工具栏新增 antd Select（全部/在售/已售），使用 `usePersistentState('xh.items.soldFilter')` 持久化，默认值 `"onsale"`
  - [x] SubTask 7.2: 调用 `list_links` API 时传递 `sold_filter` 参数
  - [x] SubTask 7.3: 客户端实时搜索模式（live mode）也支持状态筛选

- [x] Task 8: 评估明细页新增状态筛选与 is_sold 渲染
  - [x] SubTask 8.1: 在 `Evaluations/index.tsx` 查询条件区新增状态筛选 Select，使用 `usePersistentState('xh.evals.soldFilter')`
  - [x] SubTask 8.2: 调用 `evaluations` list API 时传递 `sold_filter` 参数
  - [x] SubTask 8.3: 新增 is_sold 列到 `COLUMN_DEFINITIONS`，渲染为 Tag（已售红/在售绿）

- [x] Task 9: 评估明细页筛选条件持久化
  - [x] SubTask 9.1: 将 `Evaluations/index.tsx` 的 itemId/taskId/scoreRange/dateRange/brandFilter 从 `useState` 改为 `usePersistentState`
  - [x] SubTask 9.2: dateRange 需处理 dayjs 对象序列化（转为 ISO 字符串存储，读取时转回 dayjs）

## 阶段四：前端 — 更新时间显示

- [x] Task 10: 商品列表页新增"最后更新时间"列
  - [x] SubTask 10.1: 在 `DEFAULT_FIELD_META` 新增 `updated_at` 字段定义（type: datetime）
  - [x] SubTask 10.2: 后端 `list_links` 端点确保 `task_links.updated_at` 字段返回给前端
  - [x] SubTask 10.3: 前端渲染为相对时间（如"3分钟前"），支持按更新时间排序

## 阶段五：测试与验证

- [x] Task 11: 后端单元测试
  - [x] SubTask 11.1: `tests/test_batch_refresh_scheduler.py` — 测试调度器启动/停止、批量采集逻辑、失败重试、熔断
  - [x] SubTask 11.2: `tests/test_list_links_sold_filter.py` — 测试 `sold_filter` 参数（all/onsale/sold 三种场景）
  - [x] SubTask 11.3: `tests/test_evaluations_sold_filter.py` — 测试评估列表 `sold_filter` 参数

- [x] Task 12: 集成测试与回归
  - [x] SubTask 12.1: 运行完整后端测试套件，确认无回归（111 个测试全部通过）
  - [x] SubTask 12.2: 前端 `tsc --noEmit` 编译通过
  - [x] SubTask 12.3: 验证商品列表页状态筛选端到端流程
  - [x] SubTask 12.4: 验证评估明细页筛选条件持久化端到端流程

# Task Dependencies

- Task 2 depends on Task 1（调度器需要配置参数）
- Task 3 depends on Task 1（API 端点操作调度器实例）
- Task 4 depends on Task 1, Task 2, Task 3
- Task 5 无依赖（后端独立修改）
- Task 6 无依赖（后端独立修改）
- Task 7 depends on Task 5（前端调用后端新参数）
- Task 8 depends on Task 6（前端调用后端新参数）
- Task 9 无依赖（前端独立修改）
- Task 10 无依赖（前后端独立修改）
- Task 11 depends on Task 1, Task 5, Task 6
- Task 12 depends on Task 7, Task 8, Task 9, Task 10, Task 11

# Parallelizable Work

- 阶段一（Task 1-4）和 阶段二（Task 5-6）可并行
- 阶段三 Task 7 依赖 Task 5，Task 8 依赖 Task 6，但 Task 9 和 Task 10 可与 Task 7/8 并行
