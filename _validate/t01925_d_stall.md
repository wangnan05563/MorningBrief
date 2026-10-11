来源：T01845（T01925 修复验证跑全量回归时顺带发现，与档位/时长主题无关，是独立缺陷单）

【现象】
`cd backend && .venv/Scripts/python.exe -m pytest tests/test_stall_alert.py::test_dedup_same_day_local -q`
稳定失败（单独复跑亦失败）：
```
>       assert result["status"] == "skipped"
E       AssertionError: assert 'success' == 'skipped'
```
同批日志显示告警被真的发出去了：
`[stall_alert] … status=success result={'total': 1, 'success': 1, 'failed': 0, 'suppressed': 0}`

【用例前提】库里预置一条 `NotificationLog(event_type=ALERT_EVENT_TYPE, channel="multi", status="success",
created_at=_utc_naive_of(now-1h))`，即「当日已告警过」，`check_and_alert` 本应走 `_already_alerted_today` 跳过。

【排查起点】
- `backend/app/services/stall_alert.py:140-154` `_already_alerted_today`：先跑查询取 last 时间，
  `if not row: return False`。若查询条件（event_type / status / channel 过滤，或 `{"et": ALERT_EVENT_TYPE}`
  的参数绑定）与用例预置行不匹配，就会返回 None → 判为「当日未告警」→ 重复发送。这是**最可能的失效点**。
- `backend/app/services/stall_alert.py:178-181` 调用点与返回结构（`ok|alerted|skipped|quiet`）。
- 时区口径：`_utc_naive_of` 写入 vs `last_dt.replace(tzinfo=utc).astimezone().date()` 比较，
  注意 `test_dedup_local_morning_is_utc_previous_day`（同文件 :206+）是这条口径的守卫用例，
  当前通过——修的时候不要把它改坏。
- 参考同主题历史单：T01696「工作流中断停滞 34 天…停滞告警误报」（已归档），本单不是它的重复：
  那条修的是误报，本条是**同日去重失效导致重复告警**。

【要做的事】
1. 定位是查询条件不匹配、还是 created_at 读写口径不一致（本地/UTC）导致日期比较跨日。
2. 修复后 `pytest tests/test_stall_alert.py -q` 全绿，并跑一次全量 `pytest tests -q` 确认无回归。
3. 若结论是「用例本身写错」（预置行与生产写入口径不一致），如实说明并修用例，不要为了绿灯放宽断言。

【硬约束】
不改生产配置、不动 `.env`；只跑测试，不触发真实通知通道（用 `fake_hub`）。
