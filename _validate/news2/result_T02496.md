## 根因

三类同族缺陷，根因是「用数据的缺失来表达请求的失败」：

1. **列表页失败被渲染成空态**。QueueManagement / ChannelManagement / WorkflowList / DatabaseAdmin / StatsOverview 的加载函数要么只有 `try/finally`（无 catch，异常直接冒到拦截器弹一条 toast 后消失），要么在 catch 里把 `list/tasks/rows` 置空。界面于是显示「暂无频道 / 暂无队列任务 / 请从左侧选择一张表」——用户无法区分「库里真的没有」和「接口挂了没取到」。toast 会自灭，页面上又没有第二个重试入口，用户只能整页刷新。
2. **趋势图把空档期画成 0 折线**。后端 `StatsService.get_trend` 对区间内没有记录的日期 `values.append(0)`；前端 `hasTrend` 只判 `trend.dates.length > 0`，而 dates 恒等于区间天数（7/30/90），永远为真。结果：一个没有任何播放的时段被画成一条贴着 0 轴的折线，读起来是「播放量归零」，实际是「根本没数据」——这正是 FR-UX-302「不画 0 折线」点名的误读。
3. **小程序详情页错误态只能重回上一页**。`pages/detail/detail.js` 失败时 `setData({ error })`，WXML 只有一句错误文案，没有重试按钮；`loadDetail` 成功后也不清 `error`。

## 影响范围

- **改动的页面（Web PC）**：队列管理 C1、频道管理 C5、工作流列表 E1、数据管理 M54（表清单/schema/行数据三级）、统计概览（概览卡 + 趋势卡两处）。
- **改动的页面（Web 移动端）**：`views/mobile/ManageQueue.vue`（ACC-UX-301 第 3 条：移动端同样要把失败与空分开）。
- **改动的页面（小程序）**：`pages/detail/detail.js|wxml`（J32）。
- **公共层**：新增 `useLoadState`（三态封装）与 `ListLoadError`（列表级失败横幅）；`useConfigLoad` 改为委托 `useLoadState`，四个配置页（COS/内网穿透/通知/AI）的行为与文案不变（`isReady/isError/errorMessage/retrying` 字段名保持一致，已跑 config-load-error-guard 回归）。
- **后端**：`get_trend` 返回值语义变更（缺数据日期 `null` 而非 `0`）。全仓 grep 确认唯一消费者是 `StatsOverview.vue`，无其他代码对 `values` 求和/求均值，不存在 null 参与算术的隐患。
- **未覆盖（如实说明）**：另有 13 个页面仍是「失败即空态」——ReviewList、ReviewDetail、WorkflowDetail、MaterialLibrary、BookPoolPanel、CosFiles、BookFinder、AdMaterials、AdPlacements、ChannelHealth、LlmMetrics、RssHealth、AutoReviewConfig。FR-UX-302 只点名了队列/频道/工作流等主列表页，本单按点名范围交付，其余建派生单推进（见「下一步建议」）。

## 修复（绝对路径与改动点）

- `D:\code\otherProjects\20_News\apps\admin-web\src\composables\useLoadState.js`（新增）：`useLoadState(loader, { failMessage, emptyMessage })` → `{ state, errorMessage, isLoading, isError, isReady, retrying, load, retry }`。loader 返回 `null/undefined` 也记为 error（「接口通了但没给数据」不能当成就绪）。`retry()` 不复位 loading，否则错误横幅连同重试按钮会在重试期间消失。
- `D:\code\otherProjects\20_News\apps\admin-web\src\composables\useConfigLoad.js`：整体委托 `useLoadState`，只保留配置页专用的 `failMessage='配置加载失败'` / `emptyMessage='配置接口未返回数据'`，删掉重复的三态实现。
- `D:\code\otherProjects\20_News\apps\admin-web\src\components\ListLoadError.vue`（新增）：`el-alert` + 「加载失败：{message}」+ 重试按钮；`stale` 为真时文案改为「下方为上次成功加载的数据，可能已过期」，为假时明确「这与『暂无数据』不同：请求未成功，数据并未加载」。显隐由使用方的 `v-if` 决定，组件内部不再叠 `visible` 门控（初版照抄 ConfigLoadError 带了 `visible` 默认 false，而 6 个使用方都只写外层 `v-if`，导致横幅一个都渲染不出来——6 条 e2e 全挂在 `element(s) not found`，是这次实测才暴露的）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\queue\QueueManagement.vue`：横幅插在 `<el-table>` 前；catch 改为设 `listError` 且**不再清空 `tasks/total`**；`#empty` 加 `v-if="!listError"`；新增 `retryLoadTasks()`。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\channel\ChannelManagement.vue`：同上（此前只有 `try/finally`，失败时列表静默为空）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\workflow\WorkflowList.vue`：同上 + 在「重置」前补独立「刷新」入口（`IconButton :icon="Refresh"`，desc「重新拉取工作流列表」）；`loadList(silent)` 失败保留旧行且不重复弹 toast。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\maintenance\DatabaseAdmin.vue`：`tablesError/schemaError/rowsError` 三态 + `loadFailed/loadErrorMessage` 聚合；横幅插在 `<el-main class="content-area">` 内 `<template v-if="selectedTable">` 之前；`<el-empty description="请从左侧选择一张表">` 加 `v-else-if="!loadFailed"`；**失败时禁用新增/批量删除/导入/行编辑/行删除**——列信息没取到时弹编辑表单等于用空对象覆盖该行；`loadRows` 失败不再清空 rows；schema 返回空列也判为失败；新增 `reloadAll()`。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\stats\StatsOverview.vue`：概览与趋势各一条横幅 + 各自 retry；`hasTrend` 改为看实际数据点 `values.some(v => v !== null && v !== undefined)`，全 null 时显示「暂无趋势数据」而非 0 折线；`loadTrend` 失败保留上一次曲线。
- `D:\code\otherProjects\20_News\backend\app\services\stats_service.py:66-115`：缺数据日期 `values.append(db_map.get(...))` → `null`；当天有记录但聚合为 NULL（如 duration 全空）同样给 `null`；docstring 与注释同步改口径。
- `D:\code\otherProjects\20_News\apps\miniprogram\pages\detail\detail.js`：`data` 增 `episodeId`，`onLoad` 记录；`loadDetail` 成功时 `error: ''`；新增 `onRetryLoad()`（无 id 直接返回，重置 loading + error 后重跑 `loadDetail`）。
- `D:\code\otherProjects\20_News\apps\miniprogram\pages\detail\detail.wxml`：错误态内加「重试」按钮（`wx:if="{{episodeId}}"`），复用 `app.wxss` 既有的 `.load-retry-wrap/.load-retry-btn`（T00599 已有该模式，不新造样式）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\mobile\ManageQueue.vue`：`loading / loadError / 空` 三分支互斥，失败分支给「加载失败：{原因}」+ 重试按钮（禁用至请求结束）。
- 提交：`cceb533`（path-limited，14 个文件；工作区里其他会话的 `api/audio.js`、`CourseMaterials.vue`、`rewriter.py`、`package.json`、`VERSION` 等 WIP 未裹挟）。

## 验证（实测证据）

- **新增 e2e（8 条全绿）**：`apps/admin-web/tests/list-error-state.spec.js` —— `PW_CHANNEL=chrome npx playwright test tests/list-error-state.spec.js` → **8 passed (23.1s)**。用例覆盖：PC 队列页失败显示横幅且表格保留旧行、点重试后横幅消失且恢复数据、移动端队列页失败+重试、频道管理失败非空态、工作流列表失败+「刷新」入口存在、数据管理表清单失败而非「请从左侧选择一张表」、趋势 values 全 null 时不渲染 canvas 而显示「暂无趋势数据」、趋势接口失败显示横幅+重试成功。失败注入用 `page.route` 首次 `route.abort()`、后续 `fulfill`。
- **回归（45 条全绿，0 失败）**：`queue.spec.js + channels.spec.js + workflow.spec.js + stats.spec.js + config-load-error-guard.spec.js + list-error-state.spec.js` → **45 passed (1.1m)**。其中 config-load-error-guard 证明 `useConfigLoad` 委托 `useLoadState` 后四个配置页的「失败禁存 + 重试 + 草稿不恢复」无回退；stats.spec.js 证明 `hasTrend` 改动没打破既有趋势断言。
- **后端 pytest**：新增 `backend/tests/test_stats_trend_null_gap.py` → **3 passed**（空档日为 null 而非 0 / 全区间无记录时 values 全 null / 有记录但 avg 为 NULL 时该日为 null）。相关子集 `-k "stat or trend or overview"` → **35 passed**。全量 `pytest tests -q` → **1141 passed, 190 warnings in 150.65s**，零失败。
- **前端构建**：`npm run build` → **✓ built in 16.52s**（无错误告警）。
- **小程序**：`node --check pages/detail/detail.js` 通过。**真机/微信开发者工具未跑**——本环境无微信模拟器，重试按钮的实际点击与 WXML 渲染未经实测，故本单 verified 置 false，需人工按下列步骤抽查：
  1. 微信开发者工具打开 `apps/miniprogram`，把 `loadDetail` 请求的域名临时改成不可达地址（或用工具的「网络状况 → 离线」）；
  2. 进入任一节目详情页 → 应显示错误文案 + 「重试」按钮（按钮样式与列表现有重试一致）；
  3. 恢复网络 → 点「重试」→ 应回到正常播放界面，且错误文案消失（不是残留）；
  4. 用「缺少 id 参数」路径复查：从错误入口进入（无 id）时**不应**出现重试按钮（`wx:if="{{episodeId}}"` 生效）；
  5. 弱网下重复点重试，确认 loading 态与按钮不会互相卡死。

## 本次回写

- 建派生单 **T02626**：把错误态+重试模式铺到剩余 13 个「失败即空态」页面（审核列表/详情优先）。
- 建派生单 **T02627**（`【缺环境】` 前缀）：小程序详情页重试按钮需微信开发者工具/真机实测，本环境无法运行。
- 其余观察不建单：`get_trend` 的 `values` 唯一消费者是 `StatsOverview.vue`（已 grep 确认，无第三方求和逻辑），null 语义变更无需下游适配（仅观察不建单）。

## 下一步建议

- 剩余 13 个页面的同族缺陷应尽快收口，尤其审核列表/审核详情是运营每天用的页面，失败显示「暂无待审」会导致漏审被误读为「今天没内容」——**已建派生单 T02626**。
- 小程序真机复验需在有微信开发者工具的环境执行——**已建派生单 T02627（缺环境）**。
- `ListLoadError` 的 `stale` 语义目前各页面各自 `:stale="list.length > 0"` 手传；若后续把三态统一到 `useLoadState`（列表页现在还是各自 ref），可让 composable 直接产出 stale——属重构机会，纳入 T02626 的实施要点，不单独建单。
