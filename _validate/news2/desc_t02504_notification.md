来源：T02504（FR-UX-405 枚举统一字典）。本单只把「后端有 `class X(str, Enum)` 模型枚举」的 11 个域纳入 `src/constants/enums.js` 并接上门禁双向对账，通知投递状态不在其中——它没有模型枚举可对账，本单不动它（避免把无法校验的域塞进「字典=真相」的口径里）。

## 现状（实测）
- 后端 `backend/app/models/notification_log.py:39`：`status` 是 `String` 列，取值写在 comment 里（`success | failed | failed_capped | suppressed`），不是 `class X(str, Enum)` ⇒ 门禁 `checkEnums` 对它无从对账（`readBackendEnums` 只认 Enum 类）。
- 前端 `apps/admin-web/src/views/notification/NotificationConfig.vue:832-835` 一份 `{success:'成功', failed:'失败', failed_capped:'失败达上限', suppressed:'已抑制'}`，同文件 `:342-343` 的筛选 `<el-option>` 又写了一遍「失败达上限 / 已抑制」，另有 `:825-826` 的 tag 颜色分支。同一组值在一个文件里三处表达，改文案要翻三处。

## 建议做法
1. `backend/app/models/notification_log.py` 增加 `class NotificationDeliveryStatus(str, Enum)`，列定义改为引用该枚举（保留 comment 与既有取值，不做数据迁移——值字符串不变）；
2. `enums.js` 新增 `NOTIFICATION_DELIVERY_STATUS`（label / type），并在 `BACKEND_ENUM_OF` 里挂上类名，门禁即自动纳入双向比对；
3. `NotificationConfig.vue` 删掉本地三份表达，改用 `enumLabel / enumTagType / enumOptions`。

## 验收口径
- `npm run validate:nav` 通过，且把字典里 `suppressed` 删掉后必须报错（证明双向对账真的生效）；
- 通知页筛选下拉与状态标签文案不变（现值即真相，不做文案改动）；
- 后端 `pytest -k notification` 通过。
