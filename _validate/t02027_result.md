# T02027 回传：test_stall_alert 同日去重「失效」根因是用例口径写错，生产去重无缺陷

来源：T01845（T01925 修复验证跑全量回归时顺带发现的既有缺陷，与档位/时长主题无关）。

## 根因

**用例本身写错（本单描述里预留的第 3 种结论成立），不是生产链路查询条件不匹配。**

- 测试助手 `backend/tests/test_stall_alert.py:27` `_utc_naive_of()` 原实现是
  `local_dt.replace(tzinfo=timezone.utc).astimezone(timezone.utc).replace(tzinfo=None)`——
  先剥掉本地语义强标为 UTC、再「换算」到 UTC，是**恒等变换**：本地 17:28 被原样当成 UTC 17:28 落库。
- 生产写入端不是这个口径：`LogService.create_log`（`backend/app/services/notification/log_service.py:96-107`）
  不传 `created_at`，由 `server_default=func.now()`（`backend/app/models/notification_log.py:47-48`）
  即 SQLite `CURRENT_TIMESTAMP` 写 **UTC**；读取端 `_already_alerted_today`
  （`backend/app/services/stall_alert.py:142-154`）按 UTC 解出再 `.astimezone()` 转本地比日期，
  **读写口径本来就是一致的**。
- 于是用例造出了一条生产写不出来的记录：本地钟点 ≥17:00 时，这条「UTC 17:28」解回本地是
  **次日 01:28**，与 `now.date()` 不同日 → 防抖判 False → 真的又发一次 → `status='success'`，
  断言 `'skipped'` 失败。本地 07:30 跑则恰好同日 → 通过。
  即：**时间依赖性假失败**，白天全绿、傍晚起必挂，会掩盖真实回归。
- 排查起点里的「查询条件/参数绑定不匹配」已逐条排除：`ALERT_EVENT_TYPE='system.stall_alert'`
  （`stall_alert.py:34`）写入与查询用的是同一常量，日志里可见实际 SQL
  `... WHERE event_type = ? AND status = 'success' ... ('system.stall_alert',)`
  （`backend/logs/MorningBrief_2026-10-11.log:548`），绑定正常。

## 影响范围

- **生产未发生重复告警**（不是「现行链路仍在重复发送」）：真实库只读盘点
  `system.stall_alert` 7 条记录全为 `failed`、0 条 `success`，不存在同一本地日多条 success。
  历史唯一一条 success（id=31，2026-10-08 23:30 UTC）是老命名 `event_type='stall_alert'`
  留下的，现行常量下查不到，属命名迁移遗留，不影响新写入后的当日去重。
- 受影响的是**测试可信度**：该用例从写下起就只在白天有意义，任何真的防抖回归若在傍晚跑测试
  反而会被这次假失败掩盖（误判为「已知问题」）。
- 排查过程顺带暴露一个**真实的生产缺陷**（与本单主题无关，已另建单，见「本次回写」）：
  停摆告警自上线起 7/7 发送失败，从未送达——wecom 渠道把配置占位符判为「已配置」，
  发送必然抛 `Request URL is missing an 'http://' or 'https://' protocol.`；
  且 per-channel 失败原因不落库，管理端只看到「所有渠道发送失败」。

## 修复

只改测试层，**没有为了让绿灯放宽断言**（`assert result["status"] == "skipped"` 原样保留）：

1. `backend/tests/test_stall_alert.py:27-41`——`_utc_naive_of()` 改真做本地→UTC 换算
   （`local_tz = datetime.now().astimezone().tzinfo`，与 `_already_alerted_today:153` 的
   `.astimezone()` 取同一个系统本地时区，保证互为逆运算），并在 docstring 写清失效机制。
2. `backend/tests/test_stall_alert.py:201-213`——`test_dedup_same_day_local` 的 `now`
   由 `localnow_naive()` 改为钉住正午本地钟点 `datetime(2026, 10, 11, 12, 0)`：
   「1 小时前已告警」跨午夜时本就不属于同一本地日，用真实当前时刻做断言在语义上是错的。
3. `backend/tests/test_stall_alert.py:215-231`——新增 `test_dedup_against_real_write_path`：
   预置行改由 `LogService.create_log(...)` 落库（`created_at` 走 `server_default` 的 UTC），
   不再手造时间戳。这是本单的回归锚点——用例口径与生产写入口径不一致时，这类缺陷会立刻显形。
4. 取证脚本与产物（真实库全程 `mode=ro` 只读，不改配置、不写库）：
   - `_validate/t02027_prod_dedup_audit.py`（按 UTC→本地日聚合 success 条数）
   - `_validate/t02027_audit.txt`、`_validate/t02027_alert_fail.txt`（7 条明细 + 全库
     event_type/status 分布）
   - commit `8f2fea2`（用例口径修正）、`a59e92b`（取证产物）

## 验证

1. 修复前复现：`pytest tests/test_stall_alert.py::test_dedup_same_day_local -q` 于本地 18:28 失败
   （`assert 'success' == 'skipped'`，日志显示 FakeHub 真被调用一次）。
2. 修复后单文件：`cd backend && .venv/Scripts/python.exe -m pytest tests/test_stall_alert.py -q`
   → **15 passed**（13 原有 + 1 改 + 1 新增）。
3. 全量回归：`cd backend && .venv/Scripts/python.exe -m pytest tests -q`
   → **1042 passed, 0 failed**（此前 T01925 回传时记录的是 1040 passed / 1 failed，
   即本单收口的就是这一项）。
4. 守卫用例未改坏：`test_dedup_local_morning_is_utc_previous_day`（本地 07:30 = 前一日 UTC 23:30
   的跨日场景）修复前后均通过。
5. 生产端判定证据：真实库 `system.stall_alert` 7 条全 `failed`、无同日多条 success
   （`_validate/t02027_audit.txt`）；应用日志里防抖 SQL 实际执行并绑定正确
   （`backend/logs/MorningBrief_2026-10-11.log:548`、`:1165`）。
6. 时间依赖性自检：修复后在本地 19:xx（原必挂时段）跑仍全绿；新用例改用真实写入时刻，
   与运行时刻无关。

**未覆盖项（诚实标注）**：本单只解决「用例假失败 + 防抖口径锚定」。真实缺陷「告警从未送达」
不在本单修复范围（需用户先提供真实 webhook，且属生产配置，本环境不代改）→ 已建派生单跟踪。

## 本次回写

- 建派生单 1 张（按「派生单不再派生」规则挂到最初原单 **T01845**；建单前按全量 400 条标题
  （含归档）查重，无同题单）：
  - **T02030**【AI回写待审核】wecom 告警渠道把占位符当已配置：停摆告警 7/7 发送失败、护栏从未真正送达
    （正文含实测证据、`wecom.py:33-35` 根因、四条待办与硬约束：不改 `.env`/生产配置、
    不触发真实通知通道、改重试语义前须先确认 `test_failed_send_logged_but_not_deduped` 契约）。
- 代码与取证产物已提交：`8f2fea2`、`a59e92b`。

## 下一步建议

1. 渠道配置校验与 per-channel 失败原因落库 → **已建派生单 T02030**。
2. 填入真实企微 webhook 后需人工验证一次送达（本环境不代发通知、不改 `.env`）
   → **同样在 T02030 内跟踪**（该单验收标准要求「填合法 URL 后发送成功且可查 per-channel 结果」）。
3. `notification_log` 里老命名遗留行（`event_type='stall_alert'`，id=31）不影响现行防抖，
   仅作为历史数据存在（仅观察不建单）。
