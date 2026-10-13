## 根因

T02030 把「占位符凭证」在 Hub 一侧拦住了，但「渠道配没配好」这件事在代码里仍有**三份各自为政的判定**，且管理端看不到逐渠道真因：

1. `NotifierHub._init_channels()`：`Settings` + `is_configured()`（T02030 已修，是唯一正确的一份）。
2. `NotificationSender`（管理端「测试通知」与工作流事件）：从 `ai_config` 读凭证后只做**裸 truthiness** 判断（`if dt_webhook:`），占位符字符串非空即被当成已配置渠道 → 发送时死在 httpx 里，伪装成网络错误；`send_test` 在这种情况下甚至**不落任何日志**，管理端无从查起。
3. `mobile_service._dispatch_admin_alert()`：又抄了一遍裸 truthiness（第三份）。

前端侧：`notification_log` 只存聚合 `status/error`（如「所有渠道发送失败」），`payload.channels` 里已有的逐渠道结果（T02030 起写入）没有任何展示入口；`failed_capped` 状态也不在下拉与标签口径内，列表按它筛选不到。

## 影响范围

- `backend/app/services/notification/sender.py`：管理端「测试通知」按钮、工作流事件通知（待审核/失败/发布成功）的渠道收集与无渠道时的落库文案；「重发」新日志的逐渠道明细与失败文案。
- `backend/app/services/mobile_service.py`：移动端运营告警 IM 下发（钉钉/企微）。
- `backend/app/models/notification_log.py`：状态口径文档（`failed_capped` 此前未记录，实际自 T02030 起已在写）。
- `apps/admin-web` 通知管理页「发送日志」标签：新增展开明细、补齐筛选与状态标签。
- 不改数据库结构、不加外部依赖、不影响已发送成功的通知内容。

## 修复（绝对路径与改动点）

- `D:\code\otherProjects\20_News\backend\app\services\notifier\factory.py`（**新增**）
  - `build_configured_channels(config_svc, *, names=ALL_CHANNELS)`：一次性读 8 个 `notify_*` 键 → 构造钉钉/企微/邮件 notifier → 逐个用 `is_configured()` 形态校验把关；未通过的收集为 `{"channel", "reason"}`（原因取 `configuration_error()`）并记 info 日志。返回 `(channels, skipped)`。
  - `format_skipped(skipped)`：跳过原因拼成一句人话。
  - 三处调用点共用同一套判定与同一份文案，口径与 Hub 对齐。
- `D:\code\otherProjects\20_News\backend\app\services\notification\sender.py`
  - 渠道收集改为 `build_configured_channels(config_svc)`（删掉本地 60 行裸 truthiness 实现与 `_format_skipped` 包装）。
  - `send_workflow_event` 无渠道分支：错误文案带上逐渠道原因 → `未配置任何通知渠道（dingtalk: …; email: …）`；`payload` 补 `channels:[{channel,success:false,error:原因}]`；返回值增加 `skipped`。
  - `send_test` 无渠道分支：**新增落一条 failed 日志**（此前直接 return，管理端留不下痕迹），payload 带 `channels` + `hub` 全 0；返回增加 `skipped`。
  - `send_test` 正常分支：payload 由 `{type:"test"}` 扩为带 `channels`（逐渠道结果）+ `hub`（total/success/failed/suppressed）。
  - `resend_log`：新日志的 `payload` 用**本次重发**的 `channels`/`hub` 覆盖（原样沿用旧 payload 会让管理端展开行显示上一次尝试的原因）；无可用渠道/免打扰静默时 hub 不返回逐渠道结果，补明确原因，修掉「发送失败但 message 显示『重发成功』」的误报。
- `D:\code\otherProjects\20_News\backend\app\services\mobile_service.py`
  - `_dispatch_admin_alert` 改用 `build_configured_channels(config_svc, names=("dingtalk", "wecom"))`，保持原「不含邮件渠道」行为；占位符凭证不再被下发。
- `D:\code\otherProjects\20_News\backend\app\models\notification_log.py`
  - 模块/类 docstring 与 `status` 列 comment 补 `failed_capped`（四态），与实际写入一致。
- `D:\code\otherProjects\20_News\backend\tests\test_notification_sender.py`（+4 用例）
  - `test_collect_channels_uses_is_configured`：合法企微 URL 收集，`<请填写钉钉机器人地址>` 被跳过且原因含「占位符」，email 也在 skipped。
  - `test_send_test_placeholder_webhook_not_sent_and_logged`：`DingTalkNotifier.send` **未被调用**、message 含「占位符」、`skipped[0].channel=="dingtalk"`、落库 `payload.channels[0].error` 含占位符且 `payload.hub` 全 0。
  - `test_mobile_admin_alert_shares_channel_criteria`：移动端告警同口径 → `{"dispatched":0,"note":"no_im_channel_configured"}` 且不发送。
  - `test_resend_log_no_channel_reports_reason_and_fresh_detail`：重发时 patch hub 返回零渠道 → `status=failed`、message 为「未配置任何通知渠道…」，且新日志 `payload.channels==[]`、`payload.hub` 全 0（不再继承旧记录的 channels）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\notification\NotificationConfig.vue`
  - 新增 `parseLogDetail(payload)`：安全解析 payload，产出 `_channels/_hub/_summary/_detailError`（非法 JSON 显式提示而不是静默空表）。
  - 日志表首列新增 `type="expand"` 展开明细：渠道统计行（共/成功/失败/静默）+ 逐渠道子表（渠道 / 成功失败 tag / 详情 tooltip）；旧格式或聚合写入的行回退为「该记录没有逐渠道明细…」说明；`summary` 以 `<pre>` 展示。
  - 筛选下拉补「停摆告警 system.stall_alert」「测试通知 test」「失败达上限 failed_capped」；`getStatusLabel/getStatusTagType/getEventTagType` 同步中文标签与颜色。
  - 样式：`.log-detail` 区块（缩进、说明文本、summary 预格式）。

## 验证（实测证据）

- 后端全量回归：`cd backend && .venv/Scripts/python.exe -m pytest tests -q` → **1066 passed**（T02030 基线 1062 + 本单新增 4 用例），exit 0，日志 `_validate/t02138_pytest_full3.txt`；重构中途两次全量同样全绿（`t02138_pytest_full.txt` 1064、`t02138_pytest_full2.txt` 1065）。
- 定向：`pytest tests/test_notification_sender.py tests/test_notification_api.py tests/test_notifier.py tests/test_stall_alert.py -q` → 80 passed；加 resend 用例后 `test_notification_sender.py + test_notification_api.py` → 31 passed（sender 单跑 17 passed）。
- 前端构建：`cd apps/admin-web && npm run build` → exit 0，`✓ built`，产物含 `NotificationConfig-zG7YpV65.js`（`_validate/t02138_admin_build.txt`）。
- 后端接口实跑（隔离实例 :8010，库=news.db 副本）：`GET /admin/api/v1/notification/logs` 原样透出 `payload.channels`/`payload.hub`；`?status=failed_capped` 返回 2 行、`?event_type=system.stall_alert` 返回 11 行（`_validate/t02138_api_logs.json`）。
- **UI 实测通过**（Playwright + 系统 Chrome，脚本 `_validate/t02138_ui_check.mjs`，输出 `_validate/t02138_ui_out.txt`，截图 `_validate/t02138_ui_*.png`）：
  - 事件下拉 = `["待审核","工作流失败","发布成功","停摆告警","测试通知"]`，状态下拉 = `["成功","失败","失败达上限","已抑制"]`；
  - 筛「事件=停摆告警」11 行，叠加「状态=失败达上限」得 2 行，两行都渲染中文标签「失败达上限」（含真实库那条 343）；
  - ID 344 展开：`渠道统计：共 2 · 成功 0 · 失败 2 · 静默 0` + 逐渠道两行——`dingtalk 失败 钉钉 webhook 仍是配置占位符：<请填写钉钉机器人地址>`、`wecom 失败 请求失败: HTTPSConnectionPool(...)`；
  - ID 346（test/成功）展开：`email 成功` 一行 + 统计行；
  - ID 345（failed_capped 聚合写入）与 ID 342（真实旧格式行）展开走回退文案并保留 summary，不报错；
  - 表格文本无 `undefined/NaN/[object Object]`，前端 console error 数 = 0。
- 安全边界：整轮验证**未触发任何真实通知**（副本库含用户真实钉钉 webhook/secret，故只走单测 mock 与只读日志渲染，未调用 `/notification/test`）；真实库 `backend/data/news.db` 全程未被写入；测试用副本库与 WAL 文件（含明文凭证）验证完已删除，仓库内截图与日志不含明文密钥。

## 本次回写

- 本单为 T01845「可选的后续加固」派生单（T02138），回传正文按 mtask 规则自动并入原单 T01845，不重复手动 merge。
- 证据文件（`_validate/t02138_*`）随本单 commit 入库；`_validate/t02138_smoke/`（含凭证的库副本）不入库、已删除。

## 下一步建议

（仅观察，不建单）管理端展开明细目前按日志已存字段渲染；若后续要让「旧记录」也补齐逐渠道原因，需回填历史 `notification_log.payload`，属数据迁移类工作，按项目「历史行不回填」的既有设计保持现状。
