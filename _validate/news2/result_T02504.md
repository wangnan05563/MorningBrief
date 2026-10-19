# T02504 处理结果（FR-UX-405 套餐/类型/状态枚举统一）

## 根因

前端没有「后端枚举 → 中文文案」的单一来源，同一字段在多处各自抄了一份映射，抄的时候还抄错了值，
于是产生三类用户可见问题：

1. **同字段不同页文案不一致**：`WorkflowStatus.queued` 在队列页叫「等待中」、在工作流列表叫「排队中」；
   `success` 分别叫「已完成 / 成功」；素材状态 `pending` 在素材库叫「待消费」、在工作流详情页叫「待处理」，
   `selected` 叫「已选题 / 已选中」。
2. **填了不显示 / 漏英文原值**：映射表里缺成员或写了幽灵值（如移动端队列把 `success` 写成 `finished`），
   命中不到的分支直接落回 `status` 原值，界面显示英文 token；统计卡「已完成」永远显示 `-`。
3. **没有任何机制能发现漂移**：`validate-nav.mjs` 只管路由/图标/依赖，枚举值与后端 `class X(str, Enum)`
   对不上时构建照常通过，错误只能靠人肉点页面发现。

## 影响范围

- 涉及状态/类型文案的全部 PC 视图与移动端视图：工作流列表/详情、队列管理（PC + 移动端）、
  审核列表/详情、素材库、广告位/排期、课程池、频道管理、我的页、Layout、进度指示组件。
- 构建期门禁 `apps/admin-web/scripts/validate-nav.mjs` 与其测试（新增枚举对账能力）。
- 端到端断言：`tests/queue.spec.js` 文案随统一口径改变；新增 `tests/enum-dictionary.spec.js` 锁死三层行为。
- 不改后端：后端枚举定义（`backend/app/models/*.py` 的 `class X(str, Enum)`）是本次的对账基准，未做任何改动。

## 修复（绝对路径+改动点）

### 1. 单一字典（新建）

`D:\code\otherProjects\20_News\apps\admin-web\src\constants\enums.js`

- 11 份字典：`WORKFLOW_STATUS`、`WORKFLOW_STEP_NAME`、`WORKFLOW_STEP_STATUS`、`WORKFLOW_SOURCE`、
  `REVIEW_STATUS`、`MATERIAL_STATUS`、`MATERIAL_MEDIA_TYPE`、`MATERIAL_SOURCE_TYPE`、`AD_POSITION`、
  `CHANNEL_TYPE`、`ADMIN_ROLE`；成员字段 `label`（列表/标签短文案）、`long`（详情长文案）、
  `type`（el-tag）、`badge`（移动端徽标配色）、`el`（el-steps status）。
- `BACKEND_ENUM_OF`：字典键 → 后端 Py 枚举类名，供门禁做值级对账（`CHANNEL_TYPE: null` 显式声明
  「后端不是枚举」，属已知豁免而非漏配）。
- 助手函数：`enumLabel` / `enumOptionLabel` / `enumTagType` / `enumBadge` / `enumStepStatus` / `enumOptions`，
  未命中值统一返回原值而不是空串，保证「漏配可见」而不是「漏配空白」。

### 2. 视图去重复映射（全部改为读字典）

- `...\src\views\workflow\WorkflowList.vue`、`WorkflowDetail.vue`、`...\components\WorkflowProgressIndicator.vue`
- `...\src\views\queue\QueueManagement.vue`、`...\src\views\mobile\ManageQueue.vue`（删除本地 `finished` 幽灵键）
- `...\src\views\review\ReviewList.vue`、`ReviewDetail.vue`
- `...\src\views\material\MaterialLibrary.vue`、`CourseMaterials.vue`、`BookPool.vue`
- `...\src\views\ad\AdPlacements.vue`、`AdSchedule.vue`
- `...\src\views\channel\ChannelManagement.vue`、`...\src\views\Mine.vue`、`...\src\layout\Layout.vue`
- 本单执行中门禁新抓到的一处漏网重复：`...\src\views\workflow\WorkflowDetail.vue` 的
  `materialStatusOptions/Label/Type` 三份本地抄本（「待处理/已选中」）已删除，改为
  `enumOptions(MATERIAL_STATUS)` + `enumLabel` + `enumTagType`，下拉选项也由字典生成。

### 3. 构建期门禁：枚举字典双向对账

`...\apps\admin-web\scripts\validate-nav.mjs`

- `topLevelKeys` 同时识别字符串值与对象值两种映射形态（此前只认字符串值，对象形态的重复表看不见）。
- `collectEnumDuplicates(dicts, srcDir)`（导出，可单测）：扫描 `src` 下 `.vue/.js`（排除字典自身），
  在 `<script>` 段内找「≥2 个字典键 + 全部为字符串/对象值」的本地映射，报为重复；
  其中不在后端枚举取值集合内的键（如 `finished`）报为幽灵值，命中 ≥3 处且无未知项时判定为「写错值」。
  行号按 `<script>` 偏移折算到真实文件行，报错形如 `views/xxx.vue:3`。
- `checkEnums(f)`（导出）：字典 ↔ 后端逐值双向比对（缺值 / 多值 / 后端类不存在）+ 重复与幽灵；
  无字典或读不到后端模型时整项跳过并打印说明，不假装通过。
- 结果经 `navConsistencyGate()` 在 `buildStart` 抛错，`npm run build` / `npm run dev` 均被拦。

### 4. 测试

- `...\apps\admin-web\scripts\validate-nav.test.mjs`：新增 8 条用例（一致不报错、缺值+多值+改名三方向、
  后端读不到只跳过但重复照抓、无字典整项跳过、dup/phantom 经 `checkFacts`、重复表 fixture 命中两处含
  对象形态、不误报单键计数场景、真实仓库对账非空且 `checkEnums` 零错）。
- `...\apps\admin-web\tests\enum-dictionary.spec.js`（新建）：移动端队列徽标/统计卡（中文 + 无英文原值 +
  `success` 计入「成功」卡）、PC 队列抽屉步骤时间线（`爬虫采集/质量审核/语音合成` + `成功/重试中/等待中`）、
  频道 `type_label` 优先于字典。
- `...\apps\admin-web\tests\queue.spec.js`：统计卡断言 等待中→排队中、已完成→成功，注释说明口径来源。

## 验证（实测证据）

全部命令在本机实测，非推断：

1. 门禁静态对账：`node scripts/validate-nav.mjs` → 「… · 枚举字典 11 份」+「[validate-nav] 通过」。
2. 门禁单测：`node --test scripts/validate-nav.test.mjs` → **27/27 pass**（含新增 8 条枚举用例）。
3. 反证（证明门禁不是永远绿）：
   - 临时放一份含重复映射 + 幽灵值的探测 `.vue` → 门禁输出 2 条错误、exit=1；
   - 从字典里删掉 `cancelled` 成员 → 门禁报「缺少后端 WorkflowStatus 的值：cancelled」、exit=1；
   两处探测文件测完即删，未进仓库。
4. 构建：`npm run build` → 「✓ built in 51.91s」（门禁在 buildStart 生效且通过）。
5. 端到端（UI 实测，`PW_CHANNEL=chrome npx playwright test`，dev server :5181 复用）：
   - `tests/enum-dictionary.spec.js` → **3 passed**；
   - 受影响规格集（queue / workflow / review / material / channel / enum-dictionary）→ **59/60**，
     唯一失败 `review.spec.js:128` 图片预览经单文件复跑 → **12 passed**，判定冷编译竞态（属既有 flaky）；
   - 全量套件 158 条 → 3 失败全部集中在 `page-layout-padding.spec.js`，已实测为视口驱动的环境差异
     （1280 下 `pcPadding=16px`，1440/1600 下 `24px`，`global.scss` 媒体查询未改动），与本单无关，
     已在 T02628 覆盖。
6. 后端枚举基准未动，抽样相关测试：`pytest -k "enum or channel_type or material_status"` →
   **6 passed, 1137 deselected**。
7. 提交隔离：本单为独立 commit **7bc90ed**（20 files，842 insertions / 252 deletions）；
   并发会话的 WIP（`api/audio.js`、`CourseMaterials.vue` 的 CSS token hunk、后端 rewriter/style_library、
   reports 删除）未被裹挟——`CourseMaterials.vue` 只取本单 hunk（`git apply --cached`），
   提交后 `git status` 仍保留其余未提交改动。

### 人工抽查清单（文案观感类，verified 不覆盖此项）

- [ ] 队列管理（PC）：统计卡四个标签、表格状态标签、抽屉步骤时间线三处文案是否统一为
      「排队中 / 运行中 / 成功 / 失败」。
- [ ] 移动端队列：徽标配色是否与新字典一致（成功绿、失败红、重试中橙、排队中蓝）。
- [ ] 工作流详情：素材状态下拉与标签是否为「待消费 / 已选题 / 已消费 / 已归档」口径。
- [ ] 频道管理：有 `type_label` 的频道显示人填标签、无标签的走字典，混排是否可接受。
- [ ] 审核列表/详情：通过 / 驳回 / 待审核 三态在列表、详情、统计处是否完全一致。

## 本次回写

- 新建派生单 3 张（均 `【AI回写待审核】` 前缀，父单 T02504，项目 news二期）：
  - T02702：`notification_log.status` 后端仍是裸 String 列（`backend/app/models/notification_log.py:39`
    注释 `success | failed | failed_capped | suppressed`），前端 `NotificationConfig.vue:342-343,825-835`
    各自硬编码，字典无法纳管 —— 描述文件 `_validate/news2/desc_t02504_notification.md`。
  - T02703：反馈状态枚举前端三处重复映射且含后端不存在的值 —— `ManageFeedback.vue:42-57`，
    描述文件 `_validate/news2/desc_t02504_feedback.md`。
  - T02704：`channel_type` 后端为 `String(16)` + comment（`backend/app/models/channel.py:120`）而非枚举，
    `CHANNEL_TYPE` 字典在 `BACKEND_ENUM_OF` 里被显式豁免为 `null`，需后端枚举化后解除豁免 ——
    描述文件 `_validate/news2/desc_t02504_channeltype.md`。
- 门禁文档注释、字典文件头、测试文件头均写明了 FR-UX-405 / T02504 溯源。
- 本结果文档：`D:\code\otherProjects\20_News\_validate\news2\result_T02504.md`。

## 下一步建议

- 「后端裸 String 列 + 前端硬编码」的枚举补齐（已建派生单 T02702、T02703、T02704，见「本次回写」）。
- 小程序端目前未发现自建状态文案映射表，故不建单；若后续小程序引入同一批字段的展示，
  应复用同一份字典源（仅观察，不建单）。
- `page-layout-padding.spec.js` 的视口相关失败与 `review.spec.js` 图片预览冷编译竞态，
  均已在既有单 T02628 覆盖，不重复建单。
