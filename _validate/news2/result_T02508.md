# T02508 [PRD] 5.3 累计指标口径标注 —— 处理结论

对应需求：FR-UX-503 口径与时间窗标注（docs/需求规格说明书-UX优化.md:153），
验收条款 ACC-UX-501 #3「LLM 指标页明确显示『累计自 x 时间，重启清零』」（:158），
评审原始条目 D68（_validate/ux_t02323/T02323_ux_review.md:1015）。

## 根因

三类"时间窗 / 累计口径"信息只活在代码注释里，页面上一个都读不到：

1. **进程内累计没有起点**。`backend/app/workflow/llm/rewriter.py:426` 的
   `_WORD_COUNT_RETRY_STATS` 与 `backend/app/services/rss_source_service.py:157` 的
   `_SOURCE_STATUS` 都是模块级字典，注释写着"自进程启动累计，重启清零"，但
   `/stats/llm-metrics`、`/stats/rss-health` 两个端点的响应里没有任何时间字段
   （`grep process_start|uptime|started_at|app.state` 全库零命中，项目从来没有
   进程启动时刻这个概念）。前端 `LlmMetrics.vue` 想标也标不出来。
   后果就是 D68 描述的场景：运营发布重启后进页面看到 0%，读成"问题已修复"。
2. **两个互不相干的窗口没有任何一句话说明**。`StatsOverview.vue` 里
   `selectedDate` 只进 `loadOverview`（`params.date`），`range` 只进 `loadTrend`
   （`params.range`），而 `stats_service.get_trend` 把区间锚在 `date.today()` 往前推
   ——切日期时趋势图一动不动是**正确行为**，但页面上看不出来，实测被当成"数据坏了"。
3. **不给刻度又不说"仅趋势"**。`ChannelHealth.vue` 的 mini 折线
   `scales: {x:{display:false}, y:{display:false}}`，tooltip 也没有 callback，
   悬停只显示裸数字；"那条线翘起来"到底是 1 条还是 100 条无从判断。

## 影响范围

- 后端：`/admin/api/v1/stats/llm-metrics`、`/admin/api/v1/stats/rss-health`（含
  `refresh=true` 分支）响应各**新增** 2 个字段 `started_at` / `pid`。纯增字段，
  老前端忽略即可，无破坏性；不改任何计数逻辑、不改巡检行为、不动数据库。
- 前端：4 个页面（LLM 重试指标、RSS 源状态、数据统计、频道健康度）新增口径文案，
  RSS 页顺带把 `loadData`/`refresh` 两份重复落数逻辑合并成 `applyData`。
- 新增 1 个后端模块（`app/core/runtime.py`）+ 1 个前端 util（`src/utils/scope.js`）。
- 明确**不在本单**做的（避免与已有单撞车）：
  - 用户累计收听 / 自动审核率的单位与起点标注 → 已归 **T02708**；
  - 主题归类修正 → **T02545**；
  - 漏斗文字与底色同色的对比度缺陷 → 本单截图时新发现，另建派生单（见「本次回写」）。

## 修复（绝对路径 + 改动点）

后端

- `D:\code\otherProjects\20_News\backend\app\core\runtime.py`（新建）：
  模块 import 时取 `PROCESS_STARTED_AT = localnow_naive()`（本地 naive，与全项目
  时间口径一致）与 `PROCESS_PID = os.getpid()`；`runtime_fields()` 回传
  `{started_at, pid}`。选择在 import 时取值而不是在 lifespan 里赋值：单测/脚本
  直接调 service 时同样有值，且本模块首次 import 发生在应用启动阶段，与 lifespan
  启动时间一致到秒级。
- `D:\code\otherProjects\20_News\backend\app\routers\admin\stats.py`：
  `get_llm_metrics` / `get_rss_health` 两个端点改为
  `success(data={**data, **runtime_fields()})`，docstring 写明"为什么必须带起点"。
  口径属于"这次响应该怎么解读"，是接口层职责，因此没有塞进
  `get_word_count_retry_stats()`（并有测试锁住这一点，防止两处各写一份起点）。

前端

- `D:\code\otherProjects\20_News\apps\admin-web\src\utils\scope.js`（新建）：
  `parseStartedAt` / `cumulativeScopeText` / `uptimeText` 三个纯函数，两个页面共用一份
  文案规则。核心红线：**后端没给 started_at 时不拿当前时间冒充起点**，退化为
  「（后端未返回累计起点时间）」。
- `...\src\views\stats\LlmMetrics.vue`：新增 `data-guide="llm-metrics-scope"` 口径条
  （放在空态之外——零调用时"0%"最容易被误读成"已修复"），文案
  「本页全部计数与派生率累计自 2026-07-18 09:30:00（PID 4321），服务重启后清零 已运行 93 天 15 小时」；
  `metrics` 默认值补 `started_at/pid: null`，`loadData` 成功时冻结 `fetchedAt`。
- `...\src\views\stats\RssHealth.vue`：同样新增 `data-guide="rss-health-scope"` 口径条
  （主语换成「各源巡检状态与连续失败次数」）；抽出 `applyData(data)` 供
  `loadData` 与 `refresh` 共用，避免以后加字段只改一条路径。
- `...\src\views\stats\StatsOverview.vue`：日期选择器下方新增
  `data-guide="stats-scope-note"` 两句话——「上方日期只影响下面这组当日卡片」
  「趋势图固定按近 N 天从今天往前取（实际区间），不随所选日期改变」；
  图上方摘要行补 `区间 {{ trendWindow }}`，`trendWindow` 直接读响应 `dates` 首尾，
  不在本地按"今天"倒推；`trendAriaLabel` 同步带上区间。
- `...\src\views\stats\ChannelHealth.vue`：折线标题下补
  `data-guide="channel-health-trend-caption"`「仅趋势 · 未标刻度（悬停看条数）」；
  tooltip 加 `callbacks.label → "${y} 条"`；顶栏按 radio 旁显示「统计区间 起 ~ 止」
  （同样取后端下发的 daily_trend 日期，不本地倒推）。

测试

- `D:\code\otherProjects\20_News\backend\tests\test_stats_scope_annotation.py`（新建 4 例）
- `D:\code\otherProjects\20_News\backend\tests\test_llm_metrics_smoke.py`（字段集合从 7 项
  改为 9 项，并断言 `started_at` 可 `fromisoformat` 解析、不带 `+00:00`、`pid == os.getpid()`）
- `D:\code\otherProjects\20_News\apps\admin-web\tests\unit\scope.test.mjs`（新建 8 例）
- `D:\code\otherProjects\20_News\apps\admin-web\tests\helpers\mock.js`（两个 fixture 补口径
  字段，新增 `llmMetricsLegacyResponse` 老后端 fixture）
- `tests/llm-metrics.spec.js`（+3 例）、`tests/rss-health.spec.js`（+1 例）、
  `tests/channel-health.spec.js`（+1 例）、`tests/stats.spec.js`（+1 例，含真实交互）

## 验证（实测证据）

命令层

- `cd apps/admin-web && node --test tests/unit/scope.test.mjs` → **8 passed / 0 failed**
- `cd backend && .venv/Scripts/python.exe -m pytest tests/test_llm_metrics_smoke.py
  tests/test_stats_scope_annotation.py -q` → **5 passed**（含"service 层不得被顺手写入口径字段"
  这条纯度断言）
- `cd apps/admin-web && npm run validate:nav` → 路由 45 条 · 引导 27 页 · aria-label 117 个 →
  **通过**（新增的 3 个 `data-guide` 锚点未破坏引导契约）
- `cd apps/admin-web && npm run build` → **✓ built in 2m 48s**，无告警新增
- 定向 e2e：`PW_CHANNEL=chrome npx playwright test tests/{llm-metrics,rss-health,channel-health}.spec.js`
  → **16 passed**；`tests/stats.spec.js` → **9 passed**
- 全量 e2e：见文末「全量回归」行

反证控制实验（`_validate/news2/_controls_t02508.py`，改坏 → 跑对应用例 → 期望红 → 还原）

| 编号 | 破坏动作 | 用例 | 结果 |
| --- | --- | --- | --- |
| C1 | 删掉 LLM 页口径条的 `data-guide` 锚点 | llm-metrics.spec.js:94 | 1 failed ✅ 按预期红 |
| C2 | 后端没给起点时前端拿 `dayjs()` 冒充 | llm-metrics.spec.js:105 | 1 failed ✅ 按预期红 |
| C3 | 让日期选择器同时驱动趋势请求 | stats.spec.js:223 | 1 failed ✅ 按预期红 |
| C4 | 删掉频道健康度「仅趋势」说明 | channel-health.spec.js:77 | 1 failed ✅ 按预期红 |

四个文件均已逐字节还原并二次校验（脚本 `finally` 里 assert 内容一致）。

界面实测（Playwright + 系统 Chrome，mock 后端响应，截图为证）

- `_shot_llm-metrics_desktop.png`：口径条显示在刷新按钮下方、说明卡上方，
  含起点时间、PID、"服务重启后清零"、"已运行 93 天 15 小时"四要素。
- `_shot_rss-health_desktop.png`：口径条在汇总卡与筛选区之间；「最近巡检」原有时间仍在。
- `_shot_stats_overview_desktop.png`：两句话写明卡片/趋势两个窗口，图上方出现
  「区间 2026-07-01 ~ 2026-07-03」。
- `_shot_channel-health_desktop.png`：顶栏「统计区间 2026-07-15 ~ 2026-07-21」，
  三张卡片折线下方都有「仅趋势 · 未标刻度（悬停看条数）」。
- 另有 4 张 900px 宽（tablet）截图确认文案换行不破版。
  注：420px 下 PC 路由会整体切到移动端布局（既有设计），因此窄屏留痕改用 900px。

真机联测（真实后端进程 + 真实浏览器，非 mock）

原本这段计划留作人工抽查，实测发现本环境可以安全做：`APP_ROLE=api`（T01660 路线 A，
`app/config.py:567-584`）会让 lifespan 跳过 APScheduler / 迁移 / 隧道自启，
因此不会真实抓 RSS、不会调用付费 LLM；数据库用生产库副本
（`backend/.tmp/t02508-live/data/news.db`，跑完删除），生产库全程未被打开
（收尾断言 size=30539776B、mtime 未变）。

- 接口层（`_validate/news2/_live_backend.py` 起服务 + `_live_restart.py` 取证）：
  `/admin/api/v1/stats/llm-metrics` 与 `/admin/api/v1/stats/rss-health` 均 HTTP 200 code=0，
  两个接口回报的 `started_at`/`pid` 完全一致。
- 外部佐证：接口回报 `pid=30996` == `netstat` 中 :8000 的 LISTENING 归属 == `tasklist` 里的
  python.exe；`wmic` 回报该进程 OS 创建时刻 `20261020013640`，接口 `started_at=2026-10-20T01:37:06`
  （晚 26s，即 import 期取值；早于端口就绪），且无 `+00:00` 后缀 → 与项目本地朴素时间约定一致。
- 重启对照：同一份代码再起一个进程 → `started_at=2026-10-20T01:47:46 / pid=17572`，
  起点随进程刷新、计数从 0 起（`total_calls=0`、`rss total=0 sources=0`），
  与页面「服务重启后清零」文案语义一致。
- 页面层（一次性 spec `tests/_tmp_live_t02508.spec.js`，跑完已删）：走真实登录表单 →
  打开两页，断言口径条文本包含**接口回报的同一日期与同一 PID**外加「服务重启后清零」，
  实测文本：
  「本页全部计数与派生率累计自 2026-10-20 01:37:06（PID 30996），服务重启后清零 已运行 8 分钟」
  「各源巡检状态与连续失败次数累计自 2026-10-20 01:37:06（PID 30996），服务重启后清零 已运行 8 分钟」
  → **2 passed**。留痕 `_shot_live_llm_metrics.png`、`_shot_live_rss_health.png`
  （后者正是 `暂无 RSS 源` 空态，口径条仍然渲染 → 证明它不在数据 `v-if` 块内）。

验证缺口（诚实说明）

1. **计数「非零 → 归零」的对比未做实测**：要拿到非零的 LLM 重试计数只能真实调用付费 LLM，
   本环境不宜。已做的是「新进程计数从 0 起」+ 代码级证据（`_SOURCE_STATUS` 是模块级字典，
   `app/services/rss_source_service.py:157`；LLM 计数同理留在进程内）。
2. 累计起点取的是 `core/runtime.py` 首次 import 时刻，实测比 OS 进程创建晚 11~26s、
   比端口就绪早，不是严格同一时刻；多 worker 时每个 worker 各报自己的 PID 与起点
   （这正是 `pid` 字段的用途）。
3. 真机联测跑在 `APP_ROLE=api` 的临时实例上；该角色只关掉副作用，不影响这两个只读接口，
   但「已运行」时长在真实 all 角色实例上才会随巡检周期继续增长。
4. 文案观感（措辞、换行、与相邻说明卡的视觉权重）属 GUI 主观项，人工抽查清单见文末。

人工抽查清单（6 步）

1. 用日常方式起后端（all 角色），打开「数据统计 → LLM 重试指标」，确认口径条里的时间
   等于本次后端启动时刻、PID 等于任务管理器里那个 python 进程号。
2. 重启后端，确认时间刷新、PID 变化、计数归零，且口径条「已运行」从很小值重新开始。
3. 打开「RSS 源状态」，等一轮巡检后确认连续失败次数与口径条同时存在，且空态下口径条不消失。
4. 打开「数据统计」总览页，切换日期与「近 N 天」，确认卡片与趋势图各自只受对应控件影响，
   口径条两句话与实际请求一致。
5. 打开「频道健康度」，确认顶栏统计区间取自接口返回的日期（不是本地倒推），悬停能看到条数。
6. 换主题（马卡龙/深色）与 900px 窄窗口各看一遍，确认口径条不破版、不与相邻卡片视觉打架。

## 本次回写

- 新建派生单 **T02728**（本单截图时发现的独立缺陷，与本单需求无关）：
  「LLM 重试漏斗三段文字压在主色实底上对比度不足，末段与底色同色完全不可读」——
  默认马卡龙主题下 `--on-primary` 与 `--color-primary-dark` 同为 `#2D6B5F`，
  末段文字对比度 1.0:1（首段 ≈3.4:1、中段硬编码 `#E09020` ≈2.4:1，均未达 WCAG AA 4.5:1），
  根因是 commit 35e5998 全站主题化时两个 token 撞色。建单前已按标题/关键词
  （对比度 / 漏斗 / WCAG / 真机）查重，库内无同源单。
- 追加到已有单 **T02708**（其余统计接口纳入单位元数据表）描述新增节
  「## 补充（T02508 回写：口径『起点』也要一并登记）」：用户累计收听
  （`views/mobile/ManageUsers.vue:28` 的 `total_listen_count/total_listen_duration`）
  是 DB 全生命周期累计，口径起点=该用户注册时间、不随重启清零，纳入 meta 时一并标注；
  本单不重复改该页面。原文逐字保留（`update_task` 是整文替换，已先 `get` 再合并并复核）。
- 本单为 PRD 拆解单，无前置补丁需要合并。

## 下一步建议

1. 漏斗对比度缺陷 → 已建派生单 **T02728**（含"把三段条 computed 颜色读出来算对比度、
   低于 4.5 直接红"的门禁建议）。
2. T02708 补录用户累计收听口径起点一行 → 已直接追加到该单描述（见上），无需再建单。
3. 真机联测（口径条时间/PID 与真实进程一致、重启后刷新）→ **本单内已实测完成**
   （见「真机联测」节），不再派单；剩余的只有主观观感，走文末人工抽查清单。
4. `app/core/ai_budget.py:70-80` 的预算计数目前同样是"进程内累计"但无任何界面消费，
   等它有了页面再一并带上 `runtime_fields()` ——（仅观察不建单：现在建单只会变成空跑）。

## 全量回归

`cd apps/admin-web && PW_CHANNEL=chrome npx playwright test` →
**3 failed / 166 passed（9.7m）**。3 条失败全部是
`tests/page-layout-padding.spec.js:43 › 桌面页面内边距 › 素材库管理 / 素材录入 / 讲书稿素材池：内容卡片不贴边`，
属 T02628 已登记的既有问题（`CourseMaterials.vue` 是另一会话未提交的 WIP），
与本单改动的 4 个统计页无交集；本单新增/改动的 4 个 spec 在全量里同样全绿。


