# T02507（FR-UX-502）完播率刻度统一：卡片 / 趋势 / 移动端三处同刻度

- 任务：`[PRD] 5.2 completion_rate刻度统一` — completion_rate 统一 0~1 或百分比；卡片/趋势/移动端三处不得混用；趋势图 Y 轴标注单位与最大值
- 关联需求：FR-UX-502（刻度一致性），承接 FR-UX-501 / T02506（单位元数据下发）
- 项目：news二期 ｜ commit：`63ffe0a`（代码+测试）、文档随后
- 结论：**已落地并验证**（命令层全链闭环 + UI 实测截图），verified=true；观感部分留人工抽查清单

## 根因

T02506 把「单位与换算」做成后端唯一真源（`stats_metrics.METRIC_META`）并随接口下发，卡片与移动端首页改成了按 meta 渲染，但**趋势图没有一起改**——它仍把后端下发的原始 ratio 直接喂给 Chart.js：

1. `StatsOverview.vue` 里 `data: trend.value.values`，完播率区间值是 0~1，纵轴于是画成 0.00/0.25/0.50/0.75，而同一天的卡片写「完播率(%) 65.0」。同一指标两处差 100 倍，正是 PRD 说的「三处不得混用」。
2. 纵轴既没有单位标题，也没有任何「最大值」线索（`scales.y` 只有 `beginAtZero`），不满足「趋势图 Y 轴标注单位与最大值」。
3. `trendOptions` 是**静态对象**：vue-chartjs 5.3.4 只在 options 引用变化时 `setOptions`（`node_modules/vue-chartjs/dist/index.js:164-181`），静态对象切指标后轴配置会停在上一份数据上——这会让「修完仍然混用」以另一种形态回来。
4. `trendMeta` 原先按「当前选中的 metric」取，而切换指标到响应到达之间图上画的还是上一份数据，存在「曲线是 DAU、轴写完播率(%)」的中间态。

## 影响范围

- 仅 PC 统计页趋势图（`/stats`）：`StatsOverview.vue` 的曲线数据、纵轴、tooltip、图上方新增摘要行。
- 公共格式化 `src/utils/format.js`：新增 `metricNumber`（换算唯一出口），`metricValue` 改为复用它，`metricText` 的 `%` 改为紧跟数字（`65.0%`）。卡片与移动端首页的显示结果不变（数值/单位与 T02506 一致）。
- 后端**未改**：接口继续按原始单位下发（`avg(completed)` 是 0~1 ratio），换算只在展示端发生一次。
- 趋势接口只有 `StatsOverview.vue` 一个消费方（`grep stats/trend src/` 除 `api/stats.js` 的死封装外无引用），不存在其他页面残留旧刻度。
- 移动端首页没有趋势图（只有卡片），第三条「移动端」由 T02506 的 meta 卡片满足；小程序端格式化在 T02710。

## 修复（绝对路径 + 改动点）

`D:\code\otherProjects\20_News\apps\admin-web\src\utils\format.js`
- 拆出 `metricNumber(raw, meta)`：返回换算后的**数值**（按 `precision` 定点），不可换算返回 `null`（不猜单位、不补 0）。
- `metricValue` 改为在 `metricNumber` 之上做千分位/定点呈现；`metricText` 对 `%` 不加空格。

`D:\code\otherProjects\20_News\apps\admin-web\src\views\stats\StatsOverview.vue`
- 新增 `trendPoints`（`values.map(v => metricNumber(v, trendMeta))`）作为**曲线、峰值、轴上限共用的唯一取数出口**。
- `trendMeta` 改按响应自带的 `trend.metric` 取（回退到当前选中项），消除切换中的中间态。
- 新增 `axisTitle = metricLabel(trendMeta)`、`axisUnit`、`peak`（换算后最大值及其日期）、`trendAriaLabel`。
- `trendData.datasets[0].data` 由 `trend.value.values` 改为 `trendPoints.value`。
- `trendOptions` 由静态对象改为 `computed`：`scales.y.title`（单位）、`ticks.callback`（百分比带 `%`、计数带千分位）、`tooltip.callbacks.label`、`suggestedMax: peak?.value ?? 0`（峰值不裁顶，且恒有定义，避免上一指标的残留值）、`animation: false`（切指标即时出图 + 让像素断言可确定）。
- 模板：图上方新增摘要行 `data-guide="stats-trend-summary"`（`纵轴 完播率(%)` + `峰值 65.0%（2026-07-02）`，缺数据时显式「峰值 暂无数据」），画布容器带 `role="img"` + `aria-label`（读屏用户拿不到 canvas，这是他们的「纵轴 + 峰值」）。
- 样式：`.trend-canvas` 改 flex 列，摘要行占固定高度、`.trend-plot` 吃剩余高度（`min-height:0` 保证 Chart.js 有确定尺寸）。

`D:\code\otherProjects\20_News\backend\tests\test_stats_scale_parity.py`（新增，6 条用例）
- 逐日断言 `get_overview(d)` 与 `get_trend` 在 `dau/play_count/completion_rate/avg_listen_duration` 上同值（三处同刻度的数据层前提）。
- 断言趋势完播率仍以 0~1 ratio 下发、meta 为 `{unit:ratio, display:{unit:'%',factor:100}}` 且与 `METRIC_META` 同一份对象（后端提前乘 100 会被抓到）。
- 断言 `m/dashboard-summary.today` 与 PC 概览逐字段相同、`meta` 同一份。

`D:\code\otherProjects\20_News\apps\admin-web\tests\unit\format.test.mjs`（新增，node:test 9 条）
- 钉住「换算只乘一次」：`0.65 → 65`、`512 秒 → 8.5`、计数不换算、缺 meta → `null`；并显式记录 `65 → 6500`（接口若提前百分化会被二次放大到离谱）。
- 元数据读 `tests/helpers/stats-metric-meta.json`（由 `scripts/gen_stats_metric_meta.py` 从后端表生成），不手写副本。
- 运行：`cd apps/admin-web && node --test tests/unit/format.test.mjs`（Node 24 在本机不接受目录形式 `node --test tests/unit`，会被当模块加载）。

`D:\code\otherProjects\20_News\apps\admin-web\tests\helpers\mock.js`
- 新增 `statsTrendCompletionResponse`：`values` 是 0~1 原始 ratio（0.5/0.65/0.42），峰值 0.65 与概览卡片的 `completion_rate: 0.65` 是同一个数。

`D:\code\otherProjects\20_News\apps\admin-web\tests\stats.spec.js`
- 新增 3 条：`趋势图与卡片同刻度（完播率）`（轴文案 + 峰值 `65.0%（2026-07-02）` + 卡片 `65.0` + aria + 不出现 `0.65`）、`趋势曲线按换算后的刻度绘制`（画布像素）、`趋势缺 meta 时不猜刻度`（常驻反证）。
- 像素断言思路：Chart.js 网格线 alpha≈0.1、面积填充≈0.18，主线/数据点是实色，按 `alpha>120` 过滤后只剩曲线，比较其在画布高度中的上下沿占比。

`D:\code\otherProjects\20_News\apps\admin-web\playwright.config.js`
- `testIgnore: '**/unit/**'`：`tests/unit/*.test.mjs` 是 node:test 用例，不能被 playwright 当 e2e 收集。

## 验证（实测证据）

命令层（全部实跑）：
1. `npm run validate:nav` → 「枚举字典 11 份 … 通过」。
2. `node --test tests/unit/format.test.mjs` → **9 passed**（3 suites）。
3. `backend/.venv/Scripts/python.exe -m pytest tests/test_stats_scale_parity.py tests/test_stats_metric_meta.py tests/test_stats_trend_null_gap.py -q` → **15 passed**。
4. **后端全量** `pytest -q` → **1155 passed, 0 failed, 0 skipped**，548.19s（日志 `_validate/news2/_pytest_full_t02507.log`；由独立子代理执行，未改任何源码）。
5. `npm run build` → ✓ built in 40.07s；`dist/assets/StatsOverview-DDMw7OKs.js` 内可 grep 到 `纵轴` / `峰值 ${...text}` / `峰值 暂无数据`，说明新摘要确实进了产物。
6. `PW_CHANNEL=chrome npx playwright test tests/stats.spec.js` → **7 passed**（含新增 3 条）。
7. **全量 e2e** → **160 passed, 3 failed (5.9m)**，日志 `_validate/news2/_pw_t02507_full.log`。3 条失败全部是 `page-layout-padding.spec.js:43`「三个素材页内容卡片不贴边（左侧仅 16px）」——与本单无关的既有失败，已由 **T02628** 跟踪（`git status` 显示 `CourseMaterials.vue` 是并发会话的未提交 WIP，正是这几个页面）。
8. UI 实测截图（夹具数据、1440 宽）：`_validate/news2/_shot_stats_desktop.png` 显示纵轴刻度 `0%…70%`、竖排轴标题「完播率(%)」、摘要「纵轴 完播率(%) 峰值 65.0%（2026-07-02）」、卡片「完播率(%) 65.0」——三处同一个数；窄屏截图 `_shot_stats_narrow.png` 落到移动端首页（路由按视口切换），顺带确认 T02506 的失败形态：接口未 mock 时四张卡片显示 `-` 而不是猜出来的秒值。
   - 截图里的 `Request failed with status code 500` 是 vite 代理在后端未启动（`curl :8000` 连接失败）时对未 mock 请求回的错误，不是应用缺陷。

反证（证明用例不是空跑，逐条注入后重跑并还原）：
- **C2**（把 `data` 改回 `trend.value.values`，即修复前形态）→ `趋势曲线按换算后的刻度绘制` **失败**：`expect(band.topFrac).toBeLessThan(0.5)`，曲线贴底。这是「曲线刻度」这个 canvas 死角被真实覆盖的证据。
- **C4**（`trendPoints` 不做换算）→ `趋势缺 meta 时不猜刻度` **失败**（`峰值 -（2026-07-01）` ≠ `峰值 暂无数据`）。
- **C3**（轴单位写死 `'完播率(%)'`）→ `趋势缺 meta 时不猜刻度` **失败**（`纵轴 完播率(%)` ≠ `纵轴 -`）：轴单位确实来自 meta。
- **C1**（换算之后再乘一次 `factor`）→ **前端全部通过**（二次换算只让曲线相对自身缩放，轴自动跟着放大，DOM 与像素都读不出来）。这是本单确认存在、且无法用 UI 断言关闭的盲区 → 判据已补进 **T02709**（`.factor` 只允许出现在 `src/utils/format.js`，视图读取即门禁红灯）。
- 反证结束后 `git diff` 与还原校验：`restored: True`，注入代码未进 commit。

真数据核对（read-only 打开 `backend/data/news.db`）：
- 最近 5 个有数据的日期每天仅 1~2 条播放、1 个用户，`avg(completed)` 只会是 0.0 或 1.0（`_validate/news2/_realdata_t02507.json`）。所以 ACC-UX-501 #2 用真数据是「退化成立」——0/1 乘不乘 100 都长得像。同值性由后端 SQL 等价（本单 6 条用例）保证，量级换算由夹具 + 像素反证保证；真数据这一环另立 **T02715** 补样本。

人工抽查清单（观感部分，verified 不覆盖主观审美）：
1. 打开 `/stats`，切「完播率」：纵轴是否显示 `%` 后缀、轴标题是否与卡片名称一致、摘要行是否读出「纵轴 … 峰值 …」。
2. 切「DAU / 播放量」：轴标题应变成 `DAU(人)` / `播放量(次)`，刻度是千分位整数而不是 `1,500人` 这种逐项后缀。
3. 悬停曲线：tooltip 是否 `完播率: 65%`（不是 0.65）。
4. 30 天区间 + 空档日：曲线是否断点（不贴 0），摘要是否仍报峰值而不是「峰值 0%」。
5. 竖排轴标题与刻度文字在窄容器（约 1024 宽）下是否互相挤压——截图里两者相邻但未重叠。
6. 关掉动画后切指标的即时感是否可接受（本单为像素断言确定性主动关闭入场动画）。

## 本次回写

- 新建派生单 **T02715**（`【AI回写待审核】为统计验收补多用户样本，让完播率脱离 0/1 退化值`，`derivedFrom=T02507`）：真数据验收缺口，含造数建议与验收口径。
- 追加 **T02709**（门禁「单位字面量硬编码」检查，派生自 T02506）描述一节：把 C1 盲区与 `.factor` 单点判据、反证写法写进去（原文逐字保留，复核 `original preserved: True`，长度 1594 → 2189）。
- 不新建重复单：移动端首页缺失败态 → 已在 **T02626**（把失败态+重试铺到剩余页面）范围内；小程序端格式化 → 已在 **T02710**；三个素材页内边距既有失败 → 已在 **T02628**；`api/stats.js` 死封装 → 已在 **T02711**。
- 留档：`_validate/news2/` 下 `_pytest_full_t02507.log`、`_pw_t02507_full.log`、`_build_t02507.log`、`_control_C1/C2/C3/C4.txt`、`_realdata_t02507.json`、两张截图（`_` 前缀为本地产物，不入库）。

## 下一步建议

1. 落地 T02709 的 `.factor` 单点门禁，堵住「页面里再乘一次」这个 UI 断言抓不到的盲区（已建派生单 T02709，本单补充判据）。
2. 按 T02715 补多用户统计样本，把 ACC-UX-501 #2 从「夹具成立」推到「真数据成立」（已建派生单 T02715）。
3. T02710（小程序端格式化）接入同一份 meta 时，注意小程序没有 `metricNumber` 这个出口——若各自实现换算，等于把 C1 盲区搬到另一个端（仅观察不建单，执行时按 T02710 自身验收口径处理）。
4. 若后续要求 tooltip 也带 `%` 之外的单位后缀（当前计数类只写数字，单位在轴标题），属文案取向选择，需要产品确认（仅观察不建单）。
