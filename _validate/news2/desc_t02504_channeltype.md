来源：T02504（FR-UX-405 枚举统一字典）。本单里 `CHANNEL_TYPE` 是唯一一份「前端自己声明、后端没有模型枚举可对账」的字典：`BACKEND_ENUM_OF.CHANNEL_TYPE = null`，门禁只校验「页面不得再抄第二份」，无法校验「值集是否与后端一致」。这是明知有缺口仍接受的取舍——把它记成任务，而不是记成注释。

## 现状（实测）
- `backend/app/models/channel.py:120`：`channel_type = String(16), default="news", comment="频道类型 news/course/audiobook"`——取值只存在于注释里，无枚举、无 `CheckConstraint`；
- 同表另有 `type_label = String(32), nullable=True`，是运营手填的中文展示名，后端已按 `ch.type_label or ch.channel_type` 优先使用（`backend/app/services/review_service.py:89`），`routers/admin/channels.py:356` 也把它回传前端；
- 前端 `apps/admin-web/src/constants/enums.js` 的 `CHANNEL_TYPE` 手写 news/course/audiobook 三项；本单新增的 e2e（`tests/enum-dictionary.spec.js` 第三个用例）刻意断言「字典里没有的值（feature）原样显示」，即后端一旦出现第四种类型，界面立刻漏出英文原值，门禁不会有任何提示。

## 建议做法
1. `channel_type` 提升为 `class ChannelType(str, Enum)`（news/course/audiobook），值字符串保持不变、不做数据迁移；同步 `CheckConstraint` 与迁移脚本；
2. 明确 `type_label` 的定位（人工覆盖名 vs 枚举派生名）并在模型注释里写清「为空时回落枚举」，避免两个字段将来各写一半；
3. `enums.js` 里 `BACKEND_ENUM_OF.CHANNEL_TYPE` 从 `null` 改为 `'ChannelType'`，让门禁接管值集比对；
4. 若第 1 步不做，至少要给后端加一条「写入 channel_type 必须落在白名单内」的接口校验，否则前端字典永远是猜测。

## 验收口径
- 后端 `pytest -k "channel"` 通过（含新增枚举的取值断言）；
- `npm run validate:nav` 通过，且把 `enums.js` 里 `audiobook` 删掉后必须报「缺少后端 ChannelType 的值」——证明字典与模型真的挂上了；
- 频道列表页 `type_label` 优先、为空回落枚举标签的行为不变（已有 e2e 用例覆盖）。
