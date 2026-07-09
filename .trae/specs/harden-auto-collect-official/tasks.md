# Tasks

## 阶段一：P0 配置同步与文档边界

- [x] Task 1: 补齐 config.example.yaml 的 eval 段
  - [x] SubTask 1.1: 在 `config/config.example.yaml` 末尾追加完整 `eval` 段，字段与 `yaml_config.py:EvalConfig` 对齐（pass_score / auto_buy_score / ai_auto_eval / ai_auto_deep_analyze / auto_collect_official / auto_collect_max_per_run / auto_collect_dedup_window_minutes / auto_collect_fail_pause_threshold / ai_multi_run_suggestion / ai_suggestion_interval + filter_tags / exclude_keywords）
  - [x] SubTask 1.2: 每个字段附中文注释说明用途与取值范围

- [x] Task 2: refresh_item 与 _collect_official_and_evaluate docstring 边界说明
  - [x] SubTask 2.1: 在 `src/xianyu_hunter/web/routes/api_items.py:refresh_item` 端点（约 L82-133）添加 docstring，明确"轻量刷新"语义（仅 detail + upsert_item，不评估/不采集卖家/不提取评价），引导使用 `POST /api/evaluations/{item_id}/collect-official`
  - [x] SubTask 2.2: 在 `src/xianyu_hunter/web/routes/api_evaluations.py:_collect_official_and_evaluate` 函数（约 L1736）扩展 docstring，列出完整流程步骤（detail / seller_profile + reviews 并行 / seller_profile_fallback 降级 / 持久化 / 重新评估 / events 写入）

## 阶段二：P0 单元测试补齐

- [x] Task 3: 新增 tests/test_worker_auto_collect.py
  - [x] SubTask 3.1: 测试四个 AND 条件中任一不满足时不触发采集（4 个独立用例：开关关闭 / 回调未注入 / 超配额 / 未通过 pass_score）
  - [x] SubTask 3.2: 测试全部条件满足时触发采集并自增计数
  - [x] SubTask 3.3: 测试采集函数抛异常时记录 warning 并继续，计数不自增
  - [x] SubTask 3.4: 测试本轮 max_per_run 配额耗尽后停止触发

- [x] Task 4: 新增 tests/test_official_collect_integration.py
  - [x] SubTask 4.1: mock `container.collector.detail/seller_profile`，验证 `_coalesce` 新值为空时保留旧值
  - [x] SubTask 4.2: 验证 ALWAYS_OVERWRITE 白名单字段（task_id/publish_time/view_cnt/want_cnt/region/seller_id/is_sold）即使旧值非空也覆盖
  - [x] SubTask 4.3: 验证采集成功后 `events.payload.data_source='official'` 标记写入

- [x] Task 5: 新增 tests/test_detail_extract_failure.py
  - [x] SubTask 5.1: mock Page，测试标题选择器/og:title/document.title 全部失败时 `detail()` 返回 None
  - [x] SubTask 5.2: 测试价格 ≤ 0 时返回 None（当前 _detail.py 已有此分支，需确认覆盖）
  - [x] SubTask 5.3: 测试 page.goto 响应 HTTP ≥ 400 时返回 None + warning 日志
  - [x] SubTask 5.4: 测试 page.goto 响应 HTTP ≥ 300 重定向时返回 None + warning 含目标 URL

## 阶段三：P1 数据模型与去重退避

- [x] Task 6: items 表新增 data_source 列
  - [x] SubTask 6.1: 在 `src/xianyu_hunter/infra/db_models.py:ItemRow` 新增 `data_source: Mapped[str] = mapped_column(Text, default='search')` 列
  - [x] SubTask 6.2: 在 `db_models.py:init_db` 中添加幂等迁移（_migrate_add_column + UPDATE 回填历史数据为 'search'）
  - [x] SubTask 6.3: 在 `src/xianyu_hunter/infra/repo_items.py` 新增 `update_data_source(item_id, source)` 方法（白名单校验 search/official/live）
  - [x] SubTask 6.4: 新增 `tests/test_items_data_source_migration.py`：7 个测试覆盖列存在性/默认值/更新 official/live/非法值抛错/不存在 item/迁移幂等

- [x] Task 7: EvalConfig 新增去重与退避配置字段
  - [x] SubTask 7.1: 在 `src/xianyu_hunter/infra/yaml_config.py:EvalConfig` 新增 `auto_collect_dedup_window_minutes: int = 30` 和 `auto_collect_fail_pause_threshold: int = 3`
  - [x] SubTask 7.2: 在 `config/config.yaml` 和 `config/config.example.yaml` 同步新增字段及中文注释
  - [x] SubTask 7.3: 在 `frontend/src/api/types.ts:EvalConfig` 类型扩展对应字段

- [x] Task 8: worker.py 自动官方采集去重机制
  - [x] SubTask 8.1: RunStats 新增 `official_collect_skipped_dedup: int = 0` 和 `official_collect_paused: bool = False` 字段
  - [x] SubTask 8.2: 自动采集块前调用 `repo.get_recently_collected_item_ids` 查询最近窗口内已采集 item_id，命中则跳过并自增 skipped_dedup（基于 items.last_seen 字段，非 updated_at——items 表实际只有 last_seen）
  - [x] SubTask 8.3: repo_items.py 新增 `get_recently_collected_item_ids(item_ids, window_minutes)` 方法，分批查询避免 IN 子句上限

- [x] Task 9: worker.py 自动官方采集失败退避机制
  - [x] SubTask 9.1: TaskWorker.__init__ 新增 `self._consecutive_collect_failures: int = 0` 计数器
  - [x] SubTask 9.2: 采集失败时计数器自增；达阈值后设置 `stats.official_collect_paused=True`，通过条件短路让后续商品跳过采集（不 break 整个循环，商品仍走评估/通知流程）
  - [x] SubTask 9.3: 暂停时通过 `self.notifier.send(Event(type=TASK_ERROR, severity="critical"))` 发送告警（notifier 作为 __init__ 可选参数注入，匹配 NotifierHub.send 真实签名）
  - [x] SubTask 9.4: run_once 开始时重置 `_consecutive_collect_failures = 0`
  - [x] SubTask 9.5: 新增 5 个退避测试（计数自增/暂停触发/后续跳过/下轮重置/notifier 调用），共 12 个测试全部通过

- [x] Task 10: _collect_official_and_evaluate 写入 data_source
  - [x] SubTask 10.1: api_evaluations.py L1924 调用 `container.repo.update_data_source(item_id, "official")`（try/except 隔离失败）
  - [x] SubTask 10.2: api_items.py L175 调用 `container.repo.update_data_source(item_id, "live")`（try/except 隔离失败）

## 阶段四：P2 可观测性与任务级覆盖验证

- [x] Task 11: 新增 GET /api/evaluations/auto-collect-stats 端点
  - [x] SubTask 11.0: worker.py 自动采集 except 分支新增 `collect.official.failed` 事件写入（含 error 字段，供统计端点聚合）
  - [x] SubTask 11.1: api_evaluations.py 新增 `/auto-collect-stats` 端点，查询 eval.scored+data_source=official（成功）和 collect.official.failed（失败）两类事件
  - [x] SubTask 11.2: 聚合返回 `{range_hours, total, success, failed, success_rate, top_failures}`，top_failures 从 payload.error 截断 100 字符聚合 Top3
  - [x] SubTask 11.3: 新增 `tests/test_auto_collect_stats_endpoint.py` 7 个测试（空数据/正常/Top3/Top3上限/时间过滤/非法range/排除非official）

- [x] Task 12: 前端 EvalRules.tsx 采集指标可视化
  - [x] SubTask 12.1: evaluation.ts 新增 `autoCollectStats(rangeHours)` 方法
  - [x] SubTask 12.2: EvalRules.tsx 自动官方采集卡片下方新增「最近 24 小时采集统计」面板（共 N 次 / 成功 M 次 / 成功率 Tag），useAutoRefresh 60 秒刷新
  - [x] SubTask 12.3: 失败暂停状态展示（红色 Tag「已暂停（连续失败 N 次）」）+ Top3 失败原因列表
  - [x] 实现决策：用 theme.useToken() 的 token.colorSuccess/Error 替代不存在的 CSS 变量 --xh-success/--xh-error；hooks 区用 config?.eval?.auto_collect_official 可选链（evalConfig 在 early return 之后才解构）

- [x] Task 13: 任务级 auto_collect_official 覆盖逻辑验证（发现功能不存在，已完整实现）
  - [x] SubTask 13.1: domain/task.py 新增 eval_config 字段；db_models.py:TaskRow 新增 eval_config JSON 列 + 增量迁移
  - [x] SubTask 13.2: api_tasks.py:TaskCreate/TaskUpdate 新增 eval_config 字段 + JSON 序列化；startup.py 解析注入 Task 对象
  - [x] SubTask 13.3: worker.py 新增 `_effective_eval_cfg()` 方法用 model_copy 合并任务级覆盖（避免污染全局单例）
  - [x] SubTask 13.4: types.ts 新增 TaskEvalOverride 接口 + Task/TaskCreateBody 扩展 eval_config 字段
  - [x] SubTask 13.5: TaskEditor.tsx 新增任务级 auto_collect_official Switch + auto_collect_max_per_run InputNumber UI，均带"留空则使用全局配置"说明文字
  - [x] SubTask 13.6: 新增 `tests/test_task_level_auto_collect_override.py`：11 个测试（6 单元 + 5 集成）覆盖合并逻辑与 run_once 行为

## 阶段五：集成测试与回归

- [x] Task 14: 运行完整后端测试套件，确认无回归
  - [x] SubTask 14.1: 6 个新增测试文件共 45 个测试全部通过（test_worker_auto_collect 12 / test_official_collect_integration 3 / test_detail_extract_failure 5 / test_items_data_source_migration 7 / test_auto_collect_stats_endpoint 7 / test_task_level_auto_collect_override 11）
  - [x] SubTask 14.2: 6 个回归测试文件共 108 个测试全部通过（test_repository / test_worker_scheduler / test_evaluator / test_list_links_normalize / test_item_sold_status / test_evaluations_sold_filter）
  - [x] SubTask 14.3: 前端 `npx tsc --noEmit` 编译通过（exit code 0，排除预存在的 PriceHistogramCard colorPurple 错误后无其他错误）

- [x] Task 15: 端到端流程验证（静态验证 + 测试套件覆盖，因 with_browser=False 无法真实运行）
  - [x] SubTask 15.1: 配置项就位验证——get_config() 返回 auto_collect_official=False / max_per_run=3 / dedup_window=30 / fail_pause_threshold=3；worker.py L454 自动采集条件块完整
  - [x] SubTask 15.2: 去重机制验证——worker.py L463 调用 repo.get_recently_collected_item_ids，L478 自增 official_collect_skipped_dedup；test_worker_auto_collect 覆盖触发逻辑
  - [x] SubTask 15.3: 退避机制验证——worker.py L493 计数器自增 / L527 设置 official_collect_paused / L508 写入 collect.official.failed 事件 / notifier.send 告警；test_backoff_pauses_after_threshold + test_backoff_notifier_called_on_pause 覆盖
  - [x] SubTask 15.4: 前端可视化验证——evaluation.ts L119 autoCollectStats 方法存在；EvalRules.tsx collectStats/loadCollectStats/useAutoRefresh/已暂停 Tag/top_failures 列表全部就位；TypeScript 编译通过
  - [x] SubTask 15.5: 端点可达性验证——auto_collect_stats 函数可导入，签名 (range_hours=24, container) -> dict[str, Any]；test_auto_collect_stats_endpoint 7 个测试覆盖
  - [x] SubTask 15.6: 迁移幂等性验证——test_migration_idempotent 测试通过；init_db 重复调用无报错（data_source 列 + eval_config 列）

# Task Dependencies

- Task 2 无依赖（独立 docstring 修改）
- Task 3-5 无依赖（独立测试文件，P0 并行）
- Task 6 depends on 无（独立 schema 变更，但需与 Task 7 协调字段命名）
- Task 7 depends on 无（独立配置字段）
- Task 8 depends on Task 6（去重查询需要 items.updated_at，但 updated_at 已存在；Task 6 的 data_source 是独立字段）
- Task 9 depends on Task 7（退避阈值配置字段）
- Task 10 depends on Task 6（update_data_source 方法）
- Task 11 depends on Task 10（统计端点依赖 data_source 标记写入）
- Task 12 depends on Task 11（前端调用新端点）
- Task 13 无依赖（验证现有逻辑，可能产生修复）
- Task 14 depends on Task 1-13（所有改动完成后回归）
- Task 15 depends on Task 14（测试通过后端到端验证）

# Parallelizable Work

- 阶段一 Task 1（配置同步）+ Task 2（docstring）可并行
- 阶段二 Task 3-5（三个测试文件）可并行
- 阶段三 Task 6（schema）+ Task 7（配置）可并行；Task 8/9/10 依赖 6/7
- 阶段四 Task 11/12 串行（前端依赖后端端点）；Task 13 与 Task 11/12 可并行
