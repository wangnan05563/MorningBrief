## 根因

`WeComNotifier.is_configured()` 只做了一种占位形态排除（`"example.com" not in webhook`），
本机 `backend/.env` 里 `ALERT_WECOM_WEBHOOK` 是**模板占位文本**（长度 17、首字符 `<`，实测既不
以 `http://` 也不以 `https://` 开头）。非空 → 判「已配置」→ `NotifierHub._init_channels()` 把
wecom 收进渠道表 → 每次 `send()` 走到 httpx 才抛「Request URL is missing an 'http://' or
'https://' protocol」。

结果：`hub.send()` 返回 `{total:1, success:0, failed:1}` → `stall_alert` 落库的聚合 status 只有
「所有渠道发送失败」，真因只在 loguru 日志里 → 管理端看不出区别；又因为防抖只认 `success`，
持续失败每天每次检查都再刷一条 failed（真实库实测：10-09 五条、10-11 此前两条）。

同目录渠道枚举完整清单（grep `is_configured`，非 pyc）：
- `channels/wecom.py:33`、`channels/dingtalk.py:43` — 同一条弱判定（都修）
- `channels/email.py:46` — `all([host, user, password, to])`，无占位/形态校验（一并加）
- `base.py:56` 接口声明、`hub.py:57` 唯一调用方；`registry.create` 仅 hub 使用（管理端
  「测试通知」走 `sender._collect_configured_channels`，同样吃 `is_configured`，因此修复对两条
  路径同时生效）

## 影响范围

- 停摆告警护栏（T01696）自上线起从未真正送达：真实库 `system.stall_alert` 7/7 failed（本单修复
  前基线）。其他事件类型（`workflow.failed` success 148 / `pending_review` 123 / `published` 23）
  不受影响——坏的只有「靠占位符渠道撑起来的」这一路。
- 管理端「通知记录」详情页此前无法看出失败真因。
- 不涉及库结构变更、不触发真实通知通道、未修改 `backend/.env` 与用户生产配置。

## 修复（文件绝对路径 + 改动点）

1. `D:\code\otherProjects\20_News\backend\app\services\notifier\base.py`
   - 新增凭证形态校验工具：`placeholder_error()`（空值/`<`/`>`/`请填写`/`请输入`/`填入`/
     `placeholder`/`changeme`/`your-`/`your_`/`todo`）、`webhook_error()`（必须 http(s) + 可解析
     host + 非 `example.com` 示例域）、`host_field_error()`、`email_field_error()`。
   - `INotifier` 新增**非抽象**默认方法 `configuration_error() -> str`（已配置返回空串），
     供 Hub 区分「没填」与「填了但形态不对」；桩实现（测试 `_DummyNotifier`）自动继承。
2. `D:\code\otherProjects\20_News\backend\app\services\notifier\channels\wecom.py:33`
   `is_configured()` 改为 `not webhook_error(self._webhook)`；实现 `configuration_error()`；
   直接调用 `send()` 时失败原因也带上校验结论（不再只写「Webhook 未配置」）。
3. `D:\code\otherProjects\20_News\backend\app\services\notifier\channels\dingtalk.py:43` 同上。
4. `D:\code\otherProjects\20_News\backend\app\services\notifier\channels\email.py:46`
   新增逐字段 `_field_errors()`（host 不带协议前缀/无空白、user 与 to 必须像邮箱、password
   非占位），`is_configured()` = 无错误；`configuration_error()` 输出 `字段: 原因` 列表。
5. `D:\code\otherProjects\20_News\backend\app\services\notifier\hub.py:54-73`
   跳过渠道时按原因分级：有形态问题 → `logger.warning("通知渠道未配置凭证，跳过: {name}（原因）")`，
   否则 `info`；`send()` 的零渠道出口措辞改为「未配置任何通知渠道」。
6. `D:\code\otherProjects\20_News\backend\app\services\stall_alert.py`
   - 新增 `_build_payload(report, channel_results, hub_totals)`：把 `hub.send()` 返回的
     per-channel `{channel, success, error}` 与 `{total,success,failed,suppressed}` 一并写入
     `notification_log.payload`；`total==0` 时补一条 `{"channel": "-", "error": <显式文案>}`。
   - 聚合 `error` 文案改为显式：「未配置任何通知渠道（全部渠道凭证缺失或形态非法，请在管理端
     通知设置填写真实 webhook）」（旧「所有渠道发送失败」口径在有渠道但全失败时保留）。
   - 新增 `_same_day_send_failures()`（UTC naive → 本地日期归一，取近 72h 候选再逐行换算，
     避免时区错位）+ 上限逻辑：同一本地日 `failed` 达 `STALL_ALERT_FAIL_CAP_PER_DAY`（默认 3）
     → 落**一条** `failed_capped` 且**不再调用渠道**；当日已有 `failed_capped` → 直接 `skipped`。
   - 抽出 `_as_local_dt()` 供成功防抖与失败计数共用（防抖只认 success 的原语义未改）。
7. `D:\code\otherProjects\20_News\backend\app\config.py:454` 新增 `STALL_ALERT_FAIL_CAP_PER_DAY: int = 3`。
8. 测试：`backend/tests/test_notifier.py`（+8 用例：wecom 形态参数化 6 例、合法 URL 无原因、
   dingtalk 占位、email 逐字段、hub 混合配置只加载合法渠道、hub 占位符下 total==0）；
   `backend/tests/test_stall_alert.py`（+4 用例：per-channel 真因进 payload、零渠道显式记录、
   同日失败上限与后续 skipped、前一日 failed 不吃今日额度）。

## 验证（实测证据）

1. **全量测试**：`cd backend && .venv/Scripts/python.exe -m pytest tests -q` →
   **1062 passed**（正文写的基线 1042 是旧值；本单开工时实际基线 1047，新增 15 条用例自洽）。
   输出留档 `_validate/t02030_pytest_full.txt`。
2. **真实配置只读探针**（不发送、不写库）：`_validate/t02030_hub_probe.py` →
   `_validate/t02030_hub_probe.txt`：
   - wecom 原值长度 17 / 首字符 `<` → `is_configured=False`，
     `configuration_error='ALERT_WECOM_WEBHOOK 不可用: 疑似模板占位符（含「<」）'`
   - `NotifierHub._init_channels()` 日志：三条「通知渠道未配置凭证，跳过: xxx（原因）」，
     `→ 已加载渠道: []`（修复前这里是一行「通知渠道已加载: wecom」）
3. **副本库实跑**（真实 `.env` 配置 + 新代码；SQLite backup API 复制到
   `_validate/t02030_copydb/news.db` 后清掉副本当日记录，跑完即删副本）
   → `_validate/t02030_copydb_run.txt`：连续 5 次 `check_and_alert()`
   `failed(total=0) → failed → failed → failed_capped(failed_today=3) → skipped`，
   落库明细为 `error=未配置任何通知渠道（…）` +
   `payload.channels=[{'channel':'-', 'success':False, 'error':…}]` +
   `payload.hub={'total':0,…}`，第 4 条 `failed_capped` 文案含「上限」。
   即验收标准里的「配置没填对时走 `total==0` 分支、库里有显式记录」已在真实配置下复现。
4. **生产库未被本单写入**：只读复查 `backend/data/news.db` →
   `stall_alert` 行数仍为 9、`MAX(id)=343`（`_validate/t02030_prod_rows.txt`）。
   顺带说明：id=343 这条 `failed_capped` 是**用户本机后端热重载我的改动后自己写进去的**
   （2026-10-11 本地 20:05），恰好是上限逻辑的真机首证；本单脚本对真实库只做 `mode=ro` 查询。
5. **既有语义未被放宽**：`test_failed_send_logged_but_not_deduped`（failed 不参与成功防抖、
   次日仍会重试）断言原样保留且通过——上限设为「3 次之内仍照常重试」，第 3 条之后才收敛，
   不是把失败当成功吞掉。为钉住这条边界，新增 `test_same_day_failure_cap_stops_retrying`
   显式断言「上限前会调用渠道、上限后不再调用且只多一条 failed_capped」。

## 本次回写

- 只回传本单 result 一次（派生单自动并入原单 T01845，不再手动 merge）。
- 不新增派生子任务（本单是 T01845 的派生单，按规则不再派生；剩余动作归入下面「下一步建议」并
  由原单承接）。
- 状态标注 done、**verified=false**：验收标准的「填了合法 URL 情况下发送成功」必须等用户在
  管理端填入真实企微 webhook 并跑「测试通知」才能判定，本环境不代填、不改 `.env`。
- 取证脚本与输出：`_validate/t02030_hub_probe.{py,txt}`、`_validate/t02030_copydb_run.{py,txt}`、
  `_validate/t02030_prod_rows.txt`、`_validate/t02030_pytest_full.txt`。
- commit：`fc6065d`（9 文件，470 插入 / 29 删除）。

## 下一步建议

1. **用户动作（本单 verified 的唯一前置）**：管理端 → 通知设置 → 填入真实企微机器人 webhook
   （`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=…`）→ 保存（会 `hub.reload()`）→
   点「测试通知」。收到即把本单标 verified；若仍报「未配置任何通知渠道」，`configuration_error`
   会直接说明是形态问题还是空值。（仅观察不建单——配置权在用户手上）
2. 停摆告警下一次自然触发点在**明日**（今日已被 `failed_capped` 收敛）：届时渠道若已配好，
   库里应出现 `status=success` 且 `payload.channels` 带 `wecom: success=True`。（仅观察不建单）
3. 可选的后续加固（本轮未做，避免超出本单范围）：`notification_log` 目前只有聚合 status，
   管理端列表可按需把 `payload.channels` 渲染成一行一渠道的明细表；`sender._collect_configured_channels`
   与 Hub 的判定文案可再统一。（仅观察不建单——属体验优化，不是缺陷）
