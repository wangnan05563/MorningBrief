# Checklist

## 阶段一：批量采集调度器

- [x] `BatchRefreshScheduler` 类已创建，支持启动/停止/手动触发
- [x] 批量采集逻辑复用 `collector.detail()` + `refresh_item` 合并写库逻辑
- [x] 单个商品采集失败时跳过并记录原因，不中断整个批次
- [x] 连续失败超过 `fail_pause_threshold` 时暂停当前批次
- [x] 变更日志记录 item_id、变更字段列表、时间戳
- [x] `BatchRefreshConfig` 配置段已添加到 `yaml_config.py`
- [x] `config.yaml` 和 `config.example.yaml` 已添加 `batch_refresh` 配置段
- [x] `GET /api/batch-refresh/status` 返回任务状态（idle/running）、上次执行时间、结果统计
- [x] `POST /api/batch-refresh/trigger` 可手动触发并返回任务 ID
- [x] `PATCH /api/batch-refresh/config` 可更新执行频率
- [x] `web/startup.py` 在 `XH_WITH_SCHEDULER=1` 时启动调度器
- [x] `web/app.py` 已注册 `api_batch_refresh` 路由

## 阶段二：状态筛选

- [x] `list_links` 端点新增 `sold_filter` 参数（默认 `all`）
- [x] `sold_filter=onsale` 时 SQL WHERE is_sold=0 下推过滤
- [x] `sold_filter=sold` 时 SQL WHERE is_sold=1 下推过滤
- [x] `sold_filter=all` 时行为与现有完全一致（无性能回归）
- [x] `evaluations` list 端点新增 `sold_filter` 参数
- [x] 评估列表按 is_sold 状态过滤已售商品

## 阶段三：前端状态筛选与持久化

- [x] 商品列表页工具栏新增状态筛选 Select（全部/在售/已售）
- [x] 状态筛选使用 `usePersistentState('xh.items.soldFilter')` 持久化
- [x] 默认筛选为"在售"（`sold_filter=onsale`）
- [x] 商品列表页调用 API 时传递 `sold_filter` 参数
- [x] 实时搜索模式也支持状态筛选
- [x] 评估明细页查询条件区新增状态筛选 Select
- [x] 评估明细页状态筛选使用 `usePersistentState('xh.evals.soldFilter')` 持久化
- [x] 评估明细页调用 API 时传递 `sold_filter` 参数
- [x] 评估明细页新增 is_sold 列到 `COLUMN_DEFINITIONS`
- [x] 评估明细页 is_sold 列渲染为 Tag（已售红/在售绿）
- [x] 评估明细页 itemId/taskId/scoreRange/dateRange/brandFilter 改用 `usePersistentState`
- [x] dateRange 的 dayjs 对象序列化/反序列化正确

## 阶段四：更新时间显示

- [x] `DEFAULT_FIELD_META` 新增 `updated_at` 字段定义
- [x] 后端 `list_links` 端点返回 `task_links.updated_at` 字段
- [x] 前端渲染为相对时间（如"3分钟前"）
- [x] 支持按更新时间排序

## 阶段五：测试验证

- [x] `test_batch_refresh_scheduler.py` 测试调度器启动/停止/批量采集/失败重试/熔断
- [x] `test_list_links_sold_filter.py` 测试三种 sold_filter 场景
- [x] `test_evaluations_sold_filter.py` 测试评估列表状态过滤
- [x] 完整后端测试套件无回归（111 个测试全部通过）
- [x] 前端 `tsc --noEmit` 编译通过（排除 PriceHistogramCard.tsx 的预存在 colorPurple 错误，该错误与本 spec 改动无关）
- [x] 商品列表页状态筛选端到端验证通过
- [x] 评估明细页筛选条件持久化端到端验证通过
