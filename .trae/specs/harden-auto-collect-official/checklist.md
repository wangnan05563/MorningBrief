# Checklist

## 阶段一：P0 配置同步与文档边界

- [ ] `config.example.yaml` 包含完整 `eval` 段，字段与 `yaml_config.py:EvalConfig` 对齐
- [ ] `eval` 段每个字段附中文注释说明用途与取值范围
- [ ] `api_items.py:refresh_item` 端点 docstring 明确"轻量刷新"语义，引导使用 `/collect-official`
- [ ] `api_evaluations.py:_collect_official_and_evaluate` 函数 docstring 列出完整流程步骤

## 阶段二：P0 单元测试补齐

- [ ] `test_worker_auto_collect.py` 覆盖四个 AND 条件中任一不满足时不触发采集（4 个独立用例）
- [ ] `test_worker_auto_collect.py` 覆盖全部条件满足时触发采集并自增计数
- [ ] `test_worker_auto_collect.py` 覆盖采集函数抛异常时记录 warning 并继续，计数不自增
- [ ] `test_worker_auto_collect.py` 覆盖本轮 max_per_run 配额耗尽后停止触发
- [ ] `test_official_collect_integration.py` 验证 `_coalesce` 新值为空时保留旧值
- [ ] `test_official_collect_integration.py` 验证 ALWAYS_OVERWRITE 白名单字段强制覆盖
- [ ] `test_official_collect_integration.py` 验证采集成功后 `events.payload.data_source='official'` 标记写入
- [ ] `test_detail_extract_failure.py` 覆盖标题为空时返回 None
- [ ] `test_detail_extract_failure.py` 覆盖价格 ≤ 0 时返回 None
- [ ] `test_detail_extract_failure.py` 覆盖 HTTP 4xx/5xx 时返回 None + warning
- [ ] `test_detail_extract_failure.py` 覆盖 HTTP 3xx 重定向时返回 None + warning 含目标 URL

## 阶段三：P1 数据模型与去重退避

- [ ] `db_models.py:ItemRow` 新增 `data_source` 列定义（Text，默认 'search'）
- [ ] `repository.py` schema 初始化包含幂等迁移（先 PRAGMA table_info 检查再 ALTER）
- [ ] `repo_items.py` 新增 `update_data_source(item_id, source)` 方法
- [ ] `test_items_data_source_migration.py` 验证列存在性 + 历史数据回填 + update_data_source 方法
- [ ] `yaml_config.py:EvalConfig` 新增 `auto_collect_dedup_window_minutes`（默认 30）和 `auto_collect_fail_pause_threshold`（默认 3）
- [ ] `config.yaml` 和 `config.example.yaml` 同步新增字段及中文注释
- [ ] `frontend/src/api/types.ts:EvalConfig` 类型扩展对应字段
- [ ] `worker.py:RunStats` 新增 `official_collect_skipped_dedup` 和 `official_collect_paused` 字段
- [ ] `worker.py` 自动采集块前去重检查（距 updated_at < 30 分钟跳过）
- [ ] `repo_items.py` 新增 `get_recently_collected_item_ids` 批量查询方法
- [ ] `worker.py` 引入 `consecutive_collect_failures` 计数器
- [ ] 连续失败 ≥ 阈值时设置 `official_collect_paused=True` 并 break 剩余采集
- [ ] 暂停时通过 `container.notifier.notify()` 发送告警
- [ ] 新一轮 `run_once` 开始时重置计数器与暂停状态
- [ ] `test_worker_auto_collect.py` 扩展覆盖退避机制（计数 / 暂停 / 通知 / 下轮重置）
- [ ] `api_evaluations.py:_collect_official_and_evaluate` 调用 `repo.update_data_source(item_id, 'official')`
- [ ] `api_items.py:refresh_item` 调用 `repo.update_data_source(item_id, 'live')`

## 阶段四：P2 可观测性与任务级覆盖验证

- [ ] `api_evaluations.py` 新增 `GET /auto-collect-stats` 端点
- [ ] 端点返回 `{total, success, failed, success_rate, top_failures}` 结构
- [ ] `test_auto_collect_stats_endpoint.py` 覆盖空数据 / 正常数据 / 失败聚合三种场景
- [ ] `frontend/src/api/evaluation.ts` 新增 `getAutoCollectStats()` 方法
- [ ] `EvalRules.tsx` 自动官方采集卡片下方新增指标展示（共 N 次 / 成功 M 次 / 成功率 X%）
- [ ] 指标卡片使用 `useAutoRefresh` 60 秒自动刷新
- [ ] 失败暂停状态展示（红色 Tag + Top3 失败原因列表）
- [ ] 阅读现有 `api_tasks.py` 与 `startup.py` 任务级配置合并代码并确认覆盖逻辑
- [ ] 如有缺陷修复合并逻辑；如已正确新增 `test_task_level_auto_collect_override.py` 回归测试
- [ ] `TaskEditor.tsx` 任务级配置 UI 添加"留空则使用全局配置"说明

## 阶段五：集成测试与回归

- [ ] 所有新增测试文件运行通过（test_worker_auto_collect / test_official_collect_integration / test_detail_extract_failure / test_items_data_source_migration / test_auto_collect_stats_endpoint / test_task_level_auto_collect_override）
- [ ] 相关回归测试运行通过（test_repository / test_worker_scheduler / test_evaluator / test_list_links_normalize / test_item_sold_status / test_evaluations_sold_filter）
- [ ] 前端 `npx tsc --noEmit` 编译通过（排除与本 spec 无关的预存在错误）
- [ ] 端到端验证：开启 `auto_collect_official=true` 后任务运行时自动触发采集
- [ ] 端到端验证：30 分钟内重复运行同一任务时去重机制生效
- [ ] 端到端验证：连续 3 次失败后暂停 + notifier 告警发送
- [ ] 端到端验证：前端 EvalRules 页面采集指标正确显示
