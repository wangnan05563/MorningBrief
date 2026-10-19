# T02510 · [PRD] 6.1 小程序底部导航补全 —— 处理结果

需求关联：FR-UX-601 / ACC-UX-601（docs/需求规格说明书-UX优化.md）、评审建议 J1 / J12 / J20 / I27（docs/reviews/T02336-UX建议评审报告.md）

## 根因

三个独立的成因，对应本单描述的三件事：

1. **tab 没有文字**：`apps/miniprogram/app.json` 的 `tabBar.list` 三项只配了 `iconPath` / `selectedIconPath`，没有 `text`。小程序用的是**原生 tabBar**（仓库里没有 `custom-tab-bar/` 目录），而原生 tabBar 的唯一文字通道就是 `text` 字段——不配就没有任何补救口子（图标上加字做不到）。结果三个 tab 是纯图形，用户只能靠猜。
2. **完全没有角标**：H5 移动端壳 `MobileLayout.vue` 的 tab 项只有图标+文字，没有任何计数渲染；小程序侧同样没有任何 `wx.setTabBarBadge` 调用。深层原因是**两端的数据口径不一样**：B 端（H5）后端早有 `/m/dashboard-summary` 聚合接口（`pending_review` / `unread_message`），移动端首页一直在用，只是没提到壳层；C 端（小程序）**后端没有任何未读/待办计数接口**，那部分只能另定口径。
3. **孤儿页与入口不一致**：`pages/queue/queue`（播放队列）全站唯一入口是历史页工具条里一枚**纯图标 chip**；`pages/profile/profile.js` 的 `routeMap` 里还挂着 `favorites` / `recent` / `channels` / `downloads` / `preferred` 五个键——这些页面在 T00726 已并入「我的」页第二层 Tab（走 `goSecondPage`，wxml 里没有对应 `data-key`），是**永远不会命中的死键**。更普遍的问题是 js 里存在一批 `onXxx` 方法在同页 wxml 没有宿主控件（死入口），没有任何机制能发现，改着改着就烂。

共性根因：**「导航一致性」全靠人肉维护，没有任何构建期校验**。所以本单不只是补 4 个字段，而是把口径变成可执行的门禁。

## 影响范围

- 小程序底部导航（三个 tab 的可见性/可寻址性）：`pages/index`、`pages/history`、`pages/profile`；
- 小程序播放队列可见性：`pages/queue`（新增首页入口）+ 历史页 chip；
- 小程序角标：挂在「历史」tab（`HISTORY_TAB_INDEX = 1`），口径 = 本地播放队列待播条数；
- H5 管理端移动端壳：`apps/admin-web/src/layouts/MobileLayout.vue` 的审批 tab（待办数）与消息 tab（未读数）；
- 「我的」页菜单路由：`routeMap` 由 8 键收敛到 5 个真实入口；
- CI：`.github/workflows/ci.yml` 新增一个 job，小程序改动从此有门禁；
- **未动**：后端接口、数据库、调度器；未新增任何轮询或请求频次（NFR-UX-03）。

## 修复（绝对路径+改动点）

### ① tab 补文字（J1）

`D:\code\otherProjects\20_News\apps\miniprogram\app.json`
- `tabBar.list` 三项分别补 `"text": "今日"` / `"历史"` / `"我的"`（+3 行）。

### ② 小程序角标（J1 的第二半，口径为「队列待播数」）

`D:\code\otherProjects\20_News\apps\miniprogram\utils\tab-badge.js`（新增）
- `pendingCountOf(queue, index)` = `queue.length - (index + 1)`，index 为 -1 时整队算待播，下限 0；
- `badgeText(count)`：0 → `''`（调用方撤角标），>99 → `99+`（≤4 字符，符合微信建议）；
- `currentTabIndex()`：读 `getCurrentPages()` 栈顶 route 对照 `TAB_ROUTES`，不在 tab 页返回 -1（`wx.setTabBarBadge` 只在 tab 页可调）；
- `createTabBadge()` 带**去重缓存**：文案与上次相同直接短路，不再打 API；`fail` 回调清缓存，等下一个 tab 页 onShow 重试；取数失败返回 `read-failed` 并跳过，而不是留一个来路不明的数字；
- 计数来源走**依赖注入**（默认延迟 require `services/audio`），纯逻辑可单测，不把 `wx.createInnerAudioContext` 拉进测试环境。

`D:\code\otherProjects\20_News\apps\miniprogram\app.js`
- `onLaunch` 里订阅 `onQueueChange(() => refreshTabBadge())`（页面 onShow 只覆盖「切 tab」，详情页/队列页增删节目后停在非 tab 页时角标不会动）；
- `onShow` 回前台补挂一次（后台连播会吃掉队列）；冷启动页面栈尚空时由 `refresh` 内部判「非 tab 页」自行跳过。

`D:\code\otherProjects\20_News\apps\miniprogram\pages\history\history.js`、`...\pages\profile\profile.js`
- `onShow` 各加一行 `refreshTabBadge()`（历史页是角标挂载位，回到本页立刻校准）。

### ③ H5 移动端 tabBar 待办/未读角标（I27 的 H5 形态）

`D:\code\otherProjects\20_News\apps\admin-web\src\layouts\MobileLayout.vue`
- tab 定义加 `badgeKind`（审批=「待办」、消息=「未读」），`aria-label` 渲染成 `审批（待办 3）`——数字单独念出来没有意义，读屏用户需要知道这是待办数还是未读数；
- 模板把图标包进 `.m-tabbar__icon-wrap`，右上角叠 `.m-tabbar__badge`，带 `data-guide="mobile-tab-badge-<name>"` 供 e2e 定位；
- 计数来源复用 `getDashboardSummary()`（`apps/admin-web/src/api/mobile.js:9`，接口早已存在，只是把数据从移动端首页提到壳层）；
- `countsKnown` 门控：**没拿到过计数就一个角标都不画**；刷新失败时**保留上一次的值**而不是归零——归零会让用户以为「没有待办了」，比不显示更危险；失败只 `console.warn`，不弹 toast；
- `BADGE_FOLD_AT = 99` 折叠；
- `REFRESH_MIN_INTERVAL_MS = 10_000` 节流 + `refreshing` 互斥：刷新点有 4 个（进入 / 切 tab / 回前台 / SSE `workflow.completed`），不打节流会变成「每次点 tab 都打一次聚合接口」，那才真违反 NFR-UX-03；
- 未登录（`!userStore.role`）直接不请求，避免 401 弹提示。

### ④ 孤儿页入口与死键收敛（J12 / J20）

`D:\code\otherProjects\20_News\apps\miniprogram\pages\index\index.wxml`
- 顶栏新增 `bindtap="onOpenQueue"` 的队列入口（+5 行，含注释）——原 `index.js` 的 `onOpenQueue` 无任何 wxml 绑定，队列页全站只有历史页那枚纯图标 chip。

`D:\code\otherProjects\20_News\apps\miniprogram\pages\profile\profile.js`
- `routeMap` 删除 5 个死键（favorites/recent/channels/downloads/preferred），只保留 `queue` / `feedback` / `settings` / `about` / `privacy` 等真实入口；

`D:\code\otherProjects\20_News\apps\miniprogram\pages\profile\profile.wxml`
- 同步第二层 Tab 的实际入口形态（59 行变更），使「有 data-key」与「有路由」两两对齐。

### ⑤ 把口径变成门禁（本单真正的价值所在）

`D:\code\otherProjects\20_News\apps\miniprogram\scripts\validate-tabbar.mjs`（新增，~596 行，零第三方依赖）
- 纯构建期静态校验：括号配对 + 正则 + wxml 标签栈，不引第三方解析器；`collectFacts() → checkFacts() → validate()`，CLI 打印事实行、`跳过：` 说明、`✗` 错误，有错 exit 1；
- 检查项：J1 tab 必须有非空且唯一的 `text`、标题与页面 title 一致、`pagePath` 必须在 `app.json.pages` 注册、图标文件真实存在、tab 数量 2~5；J12 js 里定义的 `onXxx` 必须能在同页 wxml 的 bind/catch 绑定里出现（死入口）、入口不能是纯图标、`routeMap` 的键必须有 `data-key` 宿主且值已注册；J19 合规类入口（privacy/agreement/feedback）不得藏在 `wx:if` / `wx:elif` / `wx:else` 分支里（`wx:for` 豁免）；角标挂载点 `HISTORY_TAB_INDEX` / `TAB_ROUTES` 必须与 `tabBar.list` 顺序一致——**有人往 tabBar 前面插一个 tab，门禁会红，而不是角标静默挂错位置**；
- 豁免机制：被点名的方法上一行写 `/* gate-allow: 原因 */`；
- 已声明的静态局限（不是 bug，写出来免得误信）：动态绑定 `bindtap="{{fn}}"` 里的变量形式方法名、动态属性名、运行时拼出的路由查不了。

配套单测：`D:\code\otherProjects\20_News\apps\miniprogram\tests\validate-tabbar.test.mjs`（新增 34 例，含「真实仓库必须干净」golden 用例）
配套单测：`D:\code\otherProjects\20_News\apps\miniprogram\tests\tab-badge.test.js`（新增 19 例）
H5 e2e：`D:\code\otherProjects\20_News\apps\admin-web\tests\mobile-tabbar-badge.spec.js`（新增 7 例，后端零依赖：`**/admin/api/v1/**` 单路由分发 + SSE 文本体 + `BroadcastChannel('news_sse')` 作为无后端触发器）

`D:\code\otherProjects\20_News\.github\workflows\ci.yml`
- 新增 Job 3 `miniprogram-check`：`node apps/miniprogram/scripts/validate-tabbar.mjs` + `cd apps/miniprogram && node --test tests/*.test.js tests/*.test.mjs`；pyinstaller job 顺延为 Job 4，文件头「三个 job」改为「四个 job」。

### ⑥ 5 处 gate-allow 豁免（诚实留痕，不偷偷变绿）

`...\pages\index\index.js`：`onTogglePlay`(701) / `onSeek`(717) / `onViewScript`(727) / `onCycleRate`(879)
`...\pages\detail\detail.js`：`onPlay`(481)
- 这些是「有代码无宿主控件」的历史残留（首页迷你播放控制条簇 + 首页本地展开文稿链 + `currentRate` 有状态无入口）。**没有直接删**：删除会牵出 `showScript` / `scriptLoaded` / `loadScript` / `RATE_OPTIONS` 整套机制，那是一次独立的 UI 决策，不属于 6.1 的范围。改为逐处写原因 + 建派生单 T02736，注释里明确「勿随手删，删前先确认 UI 不回摆」。

## 验证（实测证据）

命令层全链闭环，全部实跑：

1. 门禁（真实仓库）：`node apps/miniprogram/scripts/validate-tabbar.mjs`
   → `[validate-tabbar] tabBar 3 项（今日/历史/我的） · 注册页 18 个 · 角标挂载 历史 tab[1]` / `[validate-tabbar] 通过`；18 个页面 **0 条误报**（过程中修掉 6 条 routeMap 前导斜杠误报、1 条 `onDownloadCancel` 三元 mustache 绑定误报）。
2. 小程序单测：`cd apps/miniprogram && node --test tests/*.test.js tests/*.test.mjs`
   → `tests 139 / pass 139 / fail 0`（含本单新增 34+19 例）。注：`node --test <目录>` 在本环境会 `MODULE_NOT_FOUND`，必须显式 glob。
3. H5 导航门禁（既有）：`node apps/admin-web/scripts/validate-nav.mjs` → `[validate-nav] 通过`。
4. 前端构建：`cd apps/admin-web && npm run build` → exit 0（7m33s）。
5. H5 角标 UI 实测（Playwright + 系统 Chrome，`PW_CHANNEL=chrome`，viewport 375×667）：
   `npx playwright test tests/mobile-tabbar-badge.spec.js` → **7 passed (2.5m)**。覆盖：审批=3 / 消息=5 且 `aria-label` 为「审批（待办 3）」「消息（未读 5）」；home 不画角标；计数为 0 → 不画且 `aria-label` 退回纯「审批」；137→`99+`、99→`99`；SSE `workflow.completed` 后 3→7 且**只多发 1 次请求**（证节流生效）；计数接口 500 时沿用上次值且无 `.el-message`；375px 无横向滚动、角标不溢出导航条盒子；配色 `rgb(201, 67, 59)` + 白字。
6. **证伪对照**（一次通过的新测试不值得信任，逐条验证「检测器真的能红」）：
   - A 真仓 `app.json` 去掉 `text` → 门禁红 ✓
   - B 把角标挂载索引与 `tabBar.list` 顺序错开 → 门禁红（点名「角标会挂错 tab」）✓
   - C 组件变异两处：`BADGE_FOLD_AT` 99→9、失败分支里把计数清零 → e2e 对应用例 **2 failed** ✓
   - D 移除 `index.wxml` 的 `bindtap="onOpenQueue"` → 门禁红（`onOpenQueue` 成死入口）✓
   - 四处变异后从 `/tmp` 备份逐字节还原（不用 `git checkout`，避免裹挟并发 WIP），复跑全绿 ✓
   - E「合规入口藏进 `wx:if`」未做真仓变异（改动面太大），由门禁单测的 4 个分支用例覆盖——如实标注，不当成已实测。

**验证缺口 / 需人工**：ACC-UX-601 的「真机三 tab 截图」在本环境拿不到（无微信开发者工具/真机通道）。人工抽查清单：
- a) 真机底栏三个 tab 是否分别显示「今日 / 历史 / 我的」，中英文字体下是否截断；
- b) 队列里有 ≥2 条待播时，「历史」tab 右上角红点数字是否等于「当前条之后剩余条数」，播完/清空后是否自动消失；
- c) 小程序从详情页返回首页、以及回前台时角标是否即时校准；
- d) H5 移动端审批/消息角标在真实登录态下的数字与页面内列表是否对得上（e2e 是 mock 数据）；
- e) 读屏（iOS VoiceOver）下 tab 是否念出「审批（待办 3）」而不是「3」。
真机截图类验收已有单 T02522 承载，本单不重复建单。

## 本次回写

- **T02735**【AI回写待审核】小程序「我的」页内嵌面板与整页重复收敛（J20，仅最近/收藏/频道三项）——本单只删了 `routeMap` 死键并补齐真实入口，J20 的完整「重复面板收敛」按 T02336 报告第 157 行的裁决（只收最近/收藏/频道三项）超出 6.1 范围，另单处理；
- **T02736**【AI回写待审核】小程序首页播放控制条/文稿展开残留死方法簇需产品裁决（恢复入口或删除）——对应上面 5 处 `gate-allow`，是产品决策单而非技术清理单；
- 既有单交叉引用：T02522（小程序真机三 tab 截图验收）、T02513（6.2 深链参数与状态保留，下一单）；本单不重复建单。
- 本单代码改动：见「修复」小节全部路径（新增 5 文件 / 修改 11 文件）。

## 下一步建议

1. 审批 T02735 / T02736 两张 AI 回写单：T02736 需先裁决「恢复首页播放控制条入口」还是「删死链」，裁决前请不要靠删代码让门禁变绿 → 已建派生单 T02735、T02736（即本节所列）。
2. 门禁目前只守小程序侧；H5 侧的 `validate-nav.mjs` 尚未纳入 CI（只在本地脚本）→ 已建派生单 T02737。
3. 真机三 tab 截图 + 读屏文案验收本环境无法完成 → 归既有单 T02522（仅观察不建单，避免重复）。
