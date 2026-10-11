来源：T01845（T02027 排查同日去重时顺带发现，与档位/时长主题无关，是独立缺陷单）

【现象（实测数据，非推测）】
真实库 `backend/data/news.db` 只读盘点（脚本 `_validate/t02027_prod_dedup_audit.py`，输出
`_validate/t02027_audit.txt` / `_validate/t02027_alert_fail.txt`）：

- `notification_log` 里 `event_type='system.stall_alert'` 共 **7 条，status 全部 failed**，
  error 全部是「所有渠道发送失败」（id 335~341，2026-10-09 五条 / 2026-10-11 两条）。
- **一条 success 都没有** → 自 T01696 护栏上线起，停摆告警从未真正送达过任何人。
- 同库其他事件类型是能送达的（`workflow.failed` success 148、`workflow.pending_review` success 123、
  `workflow.published` success 23）→ 不是整条通知链路坏，是**停摆告警这一路的渠道判定坏了**。
- 真因在应用日志里（`backend/logs/MorningBrief_2026-10-11.log:586`，15:18:39 那次）：
  ```
  [stall_alert] ... status=failed result={'total': 1, 'success': 0, 'failed': 1, ...
    'results': [NotifyResult(channel='wecom', success=False,
               error="网络错误: Request URL is missing an 'http://' or 'https://' protocol.")]}
  ```
  同批日志 :515/:517 显示 dingtalk、email 是「未配置凭证，跳过」（正常），只有 wecom 被「已加载」。

【根因】
`backend/app/services/notifier/channels/wecom.py:33-35`：

```python
def is_configured(self) -> bool:
    # 占位符值视为未配置（避免误判空字符串为已配置）
    return bool(self._webhook) and "example.com" not in self._webhook
```

当前配置值 `Settings.ALERT_WECOM_WEBHOOK` 是**模板占位文本**（17 字符、以 `<` 开头、不含 `key=`，
实测既不 `startswith('http://')` 也不 `startswith('https://')`；代码默认值是空串
`backend/app/config.py:338`，`.env.example:145` 也是空 → 该占位文本来自本机 `backend/.env`，
属用户生产配置，本单不擅自改动）。`is_configured()` 只排除 `example.com` 一种形态，
占位文本非空 → 判「已配置」→ `hub._init_channels()`（`app/services/notifier/hub.py:52-63`）把
wecom 收进渠道表 → `send()` 走到 httpx 才因缺 scheme 抛错 → 每次必失败。

连带两个放大问题：
1. 失败原因只在 loguru 日志里。`LogService.create_log`（`app/services/notification/log_service.py:82-108`）
   只存聚合 status/error 字符串「所有渠道发送失败」，`hub.send()` 返回的 per-channel `results`
   （含真正的 httpx 报错）**没有落库** → 管理端「通知记录」看不到真因，只能看出「失败了」。
2. 防抖只认 success（`app/services/stall_alert.py:142-154` 查询条件 `status = 'success'`），
   这是有意语义（`tests/test_stall_alert.py::test_failed_send_logged_but_not_deduped` 钉住），
   但**没有同日重试上限** → 持续失败时每次启动检查/定时检查都会再试一次并再落一条 failed
   （10-09 一天 5 条）。若哪天渠道突然修好，同日仍会先轰炸一次再由 success 收口。

【要做的事】
1. `wecom.is_configured()`（以及同目录其他渠道同理，先 grep 枚举完整清单再改）加**形态校验**：
   必须以 `http://`/`https://` 开头且能解析出 host，并识别常见占位模式（`<...>`、`请填写`、
   `your-`、`changeme` 等）→ 判为未配置，日志明确写「渠道未配置凭证，跳过」而不是「已加载」。
   目标：配置没填对时，`hub.send()` 走 `total == 0` 分支返回「未配置任何通知渠道」，
   让「没配」这件事在日志和库里都是显式的，而不是伪装成一次网络错误。
2. `stall_alert.check_and_alert` 落库时把 `result["results"]` 的 per-channel error 一并写进
   `payload`（现有 payload 字段已存 report summary，`app/services/stall_alert.py:220-226`），
   使管理端通知记录详情能直接看到「wecom: Request URL is missing protocol」这类真因。
3. 给「同一本地日连续失败」加上限（如 ≥3 条 failed 后当日不再重试，改为落一条
   `suppressed`/`failed_capped` 记录），避免持续失败刷日志；**注意**：这条改动与既有测试
   `test_failed_send_logged_but_not_deduped` 的语义直接相关，先确认新的期望行为再改断言，
   不要为了让测试变绿而放宽断言（T02027 的教训）。
4. 配置动作交回用户：本环境不修改 `backend/.env`。修复完成后需要用户在管理端通知设置里
   填入真实企微机器人 webhook，再跑一次「测试通知」验证送达（届时本单才能标 verified）。

【硬约束】
- 不改 `.env`、不改用户生产配置（要改配置先列约束并等确认）；渠道配置改动走管理端接口，不直写库。
- 不触发真实通知通道：单测一律用 `fake_hub` / monkeypatch；本单验证只允许落到日志与库记录。
- 不动真实用户（dev 库 user id 1、2）数据；直连真实库只做 `mode=ro` 只读查询。
- 不新增外部依赖。

【验收标准】
占位符 webhook 情况下：`hub` 不再加载 wecom、`notification_log` 出现「未配置任何通知渠道」这类
显式记录；填了合法 URL 情况下发送成功且 per-channel 结果可查；`cd backend && pytest tests -q` 全绿
（当前基线 1042 passed）。
