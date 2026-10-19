来源：T02504（FR-UX-405 枚举统一字典）。反馈状态的三份本地映射在本单的范围外（后端 `feedback` 的 status 不是模型枚举，纳入口径见下），留本单收口。

## 现状（实测）
`apps/admin-web/src/views/mobile/ManageFeedback.vue`
- `:42-46` tab 列表 `{label:'待处理',value:'pending'} / 处理中 / 已解决`；
- `:53` `const statusLabel = { pending: '待处理', processed: '处理中', resolved: '已解决' }`；
- `:54-55` `statusClass` 内联 `{ pending:'m-badge--warn', processed:'m-badge--info', resolved:'m-badge--on' }`；
- `:57` `nextLabel` 又把「处理中 / 已解决」写了一遍（`:56` `nextMap` 是状态流转，属业务逻辑，保留）。

同一组 4 处文案、3 个取值，改一次要同步 4 个位置；且 PC 端没有对应页面（全仓 `grep '已解决'` 仅此一处命中），移动端是唯一点——这正是「第二份映射」会长出来的形态。后端 `feedback` 的 status 取值来源需在动工时先确认（`backend/app/models` 里没有 feedback 状态枚举，说明它是自由字符串或服务层常量）。

## 建议做法
1. 先在 `enums.js` 新增 `FEEDBACK_STATUS`（label / badge 两字段，与本单字典同形状），并在文件头注明「后端无模型枚举，值集以 `backend/app/**/feedback*` 服务层常量为准」；
2. 把上述 4 处改为 `enumLabel / enumBadge / enumOptions`；
3. 若要进门禁双向比对，需先把后端 feedback 状态提升为 `str, Enum`（与 T02504 派生的「通知投递状态枚举化」同族，可并单做）。

## 验收口径
- `npm run validate:nav` 通过；
- 移动端反馈页 tab、状态徽章、按钮文案与现状逐字一致（本单只统一来源，不改文案）；
- 若未做后端枚举化，`enums.js` 里该域必须在 `BACKEND_ENUM_OF` 显式置 `null`，不要靠「没声明」蒙过门禁。
