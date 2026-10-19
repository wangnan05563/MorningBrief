# T02506 处理结果（FR-UX-501 指标单位元数据）

## 根因

统计数值与其单位从来没有绑定关系：后端按「原始单位」返回（`avg_listen_duration` 是秒、
`completion_rate` 是 0~1 小数），单位靠页面自己写在标签里、换算靠页面自己乘。
每个页面各抄一遍，抄漏一次就错一次，而且没有任何地方能发现：

- `apps/admin-web/src/views/stats/StatsOverview.vue:100` 标签写「平均收听(分钟)」，
  取值 `overview.avg_listen_duration` 原样显示——后端给的是秒（`backend/app/services/stats_service.py:42`
  `func.avg(PlayLog.duration)`，`backend/app/models/play_log.py:32` duration 存秒），
  于是 512 秒直接显示成「512 分钟」；
- 同一字段在移动端首页标「(分)」同样不换算（`apps/admin-web/src/views/mobile/Home.vue:54`）；
- 完播率 PC 乘 100（`StatsOverview.vue:161-164` `formatRate`），移动端不乘
  （`Home.vue:52` `completion_rate + '%'`）→ 同一时刻两端显示 `65.0%` 与 `0.65%`；
- 更糟的是 e2e 夹具把 bug 固化成了契约：`apps/admin-web/tests/helpers/mock.js:286`
  把 `avg_listen_duration` 写成 `8.5`（分钟口径），`tests/stats.spec.js:43` 断言原样显示，
  所以 CI 永远绿，而生产接口给的是秒；
- 后端没有任何 schema/OpenAPI 响应模型可挂单位（全仓 `response_model=` 零命中，
  响应统一是 `backend/app/core/response.py:23-25` 的 `{code,message,data}` 裸 dict），
  单位知识只存在于 SQLAlchemy 列注释和中文 docstring 里。

## 影响范围

- 接口返回体：`/admin/api/v1/stats/overview`、`/admin/api/v1/stats/trend` 新增 `meta`
  （trend 另加 `metric`）；`/admin/api/v1/m/dashboard-summary` 的 `today` 因为内嵌同一份
  overview 而自动带上 meta。
- 展示端：PC 统计页 5 张卡片、移动端首页 4 张卡片、趋势曲线名称。
- 测试：`tests/stats.spec.js`（新增移动端同口径用例 + meta 缺失反证用例）、
  `tests/helpers/mock.js` 统计夹具改为秒口径、`backend/tests/test_stats_metric_meta.py`（新建）。
- 未覆盖（如实说明）：`/stats/llm-metrics`、自动审核指标、用户累计收听时长三个接口仍是旧形态
  （已建派生单 T02708）；小程序端时长格式化散落 10 处（派生单 T02710）；
  趋势图 Y 轴 0~1 与 % 的刻度问题属 FR-UX-502 / T02507，本单只把 meta 备好不下结论。

## 修复（绝对路径+改动点）

1. 新建唯一真源 `D:\code\otherProjects\20_News\backend\app\services\stats_metrics.py`
   —— `METRIC_META`（dau/play_count/completion_rate/avg_listen_duration/ad_impression，
   每项 `label` + 原始 `unit` + `display{unit,factor,precision}`）、`OVERVIEW_METRICS` 顺序、
   `meta_for()`；未登记指标不返回（页面显示 `-` 而不是猜单位）。
2. `...\backend\app\services\stats_service.py`
   - 导入 `OVERVIEW_METRICS, meta_for`；
   - `get_overview()` 返回体新增 `"meta": meta_for(*OVERVIEW_METRICS)`；
   - `get_trend()` 返回体新增 `"metric": metric` 与 `"meta": meta_for(metric)`；
   - 数值本身一律不动：仍返回原始单位（秒 / 0~1），换算只在展示端做一次。
3. `...\apps\admin-web\src\utils\format.js` 新增 `metricLabel / metricValue / metricText`
   —— `metricValue` 按 `meta.display.factor` 与 `precision` 换算，0 位小数走千分位、
   带小数走定点；meta 或缺失或值非有限数一律返回 `-`。
4. `...\apps\admin-web\src\views\stats\StatsOverview.vue`
   - 删除本地 `formatNum` / `formatRate` 与 5 行硬编码卡片配置，卡片改为
     「响应键序 + `meta` 名称/单位/换算」；
   - 删除 `metricLabelMap`（`{dau:'DAU',completion_rate:'完播率(%)'}` 的第二份抄本），
     趋势曲线名称改取 `trend.meta[metric].label`（局部变量名 `chartLabel`，避免与导入的
     `metricLabel` 重名）；
   - 卡片键序取自响应本身而非 `Object.entries(meta)`：后端漏发 meta 时仍渲染 5 张 `-` 卡，
     不会整块空白。
5. `...\apps\admin-web\src\views\mobile\Home.vue`
   - 删除本地 `fmt()` 与 4 行硬编码卡片（含 `completion_rate + '%'` 这个不乘 100 的分支），
     改为按 `CARD_KEYS`（页面版式：首页只放 4 张）从 `metrics.meta` 取名与换算。
6. 夹具与防漂移
   - `...\scripts\gen_stats_metric_meta.py`（新建）：从 `METRIC_META` 生成
     `...\apps\admin-web\tests\helpers\stats-metric-meta.json`；
   - `...\apps\admin-web\tests\helpers\statsMeta.js`（新建）：e2e 读取该 JSON；
   - `...\apps\admin-web\tests\helpers\mock.js`：统计夹具引入 `meta`，
     `avg_listen_duration` 由 `8.5`（错）改为 `512`（秒，512/60=8.5 分钟），trend 夹具补
     `metric`/`meta`；
   - `...\backend\tests\test_stats_metric_meta.py::test_frontend_e2e_fixture_matches_backend_table`：
     夹具 JSON 与后端表逐字比对，改了表忘记重跑生成脚本即失败。

## 验证（实测证据）

1. 后端新增用例：`backend/.venv/Scripts/python.exe -m pytest tests/test_stats_metric_meta.py -q`
   → **6 passed**。含接口冒烟两条（TestClient 真走路由）：
   `/stats/overview` 响应 `data.meta` 键序等于 `OVERVIEW_METRICS`、`avg_listen_duration.unit == second`；
   `/m/dashboard-summary` 的 `today.meta` 同源。
2. 既有口径未回归：`pytest tests/test_stats_metric_meta.py tests/test_stats_trend_null_gap.py -q` → **7 passed**
   （T02496 的「缺数据日为 null」语义未受 meta 影响）；
   `pytest tests -k "stats or metric or mobile" -q` → **12 passed, 1135 deselected**。
3. ACC-UX-501 第 1 条「显示值与 play_log.duration 秒值换算一致（抽查 3 天）」——
   对真实库副本（`backend/data/news.db` 拷到 `_validate/news2/` 只读，用完即删）按 meta 口径逐日核算：
   `2026-08-15` 原始 539.5 秒 → 显示 9.0 分钟；`2026-07-30` 620 秒 → 10.3 分钟；
   `2026-07-27` 482 秒 → 8.0 分钟（precision=1，与 `metricValue` 行为一致）。
4. 前端 UI 实测（`PW_CHANNEL=chrome npx playwright test stats.spec.js`）→ **5 passed**：
   - 卡片文案 `完播率(%)` / `平均收听(分钟)` 来自 meta；`512` 秒渲染为 `8.5`，
     且断言 `.metric-value` 中 `512` 出现次数为 0（防「标签分钟、值秒」复发）；
   - 新增「移动端首页与 PC 卡片同口径」：同一份 overview+meta 喂给 `/m/home`，
     `.m-card__label` 第 3/4 张为 `完播率(%)` / `平均收听(分钟)`，
     `.m-card__value` 为 `65.0` / `8.5`，并断言 `0.65` 与 `512` 均不出现
     （这条用例在改前必红——改前移动端显示 `0.65%` 和 `512`）；
   - `tests/list-error-state.spec.js` 一并复跑 → 合计 **12 passed**（趋势 null 档与错误态未受影响）。
5. 反证（证明守护不是永远绿）：
   - 手工把夹具 `avg_listen_duration.display.factor` 从 `1/60` 改成 `1` →
     `pytest::test_frontend_e2e_fixture_matches_backend_table` **FAILED**
     （报错文案直接给出「请重跑 scripts/gen_stats_metric_meta.py」），
     `stats.spec.js` 两条单位用例同时 **failed**（页面显示 512 而非 8.5）；恢复后复跑全绿；
   - 把 overview mock 的 `meta` 删掉 → 卡片显示 5 个 `-`，`512` 仍不出现
     （已固化为常驻用例 `meta 缺失时显示 - 而不是原始秒值`）。
6. 构建：`npm run build` → 「✓ built in 40.46s」；
   门禁 `node scripts/validate-nav.mjs` → 「枚举字典 11 份 · [validate-nav] 通过」，
   `node --test scripts/validate-nav.test.mjs` → **27/27 pass**。
7. 全量 e2e：160 条 → **157 passed / 3 failed**，3 条失败全部是
   `page-layout-padding.spec.js:43`（1280 视口下内边距 16px 与 MIN_GAP 不符），
   与上一单同一环境性失败，已在 T02628 覆盖，本单未触碰布局代码。
8. 提交：独立 commit **ca6367d**
   「feat(stats): 指标单位元数据随接口下发，PC/移动端按 meta 格式化（T02506 / FR-UX-501）」
   （11 files，403 insertions / 45 deletions）；并发会话的未提交改动
   （`api/audio.js`、`CourseMaterials.vue`、`backend/VERSION`、`_build_info.py`、
   `rewriter.py`、`style_library.py`、`test_rewriter_audiobook_quality.py`、jmeter 产物、
   `reports/` 删除）未被裹挟——提交只列本单 11 个路径，提交后 `git status` 仍保留它们。

## 本次回写

- 新建派生单 4 张（`【AI回写待审核】` 前缀，父单 T02506，项目 news二期）：
  - **T02708**：其余统计接口纳入单位元数据表——`rewriter.py:459-461` 返回 0~100 百分比、
    `auto_review_service.py:725-727` 的 `success_rate` 是 0~1 小数（同名 rate 反刻度），
    `users.py:107` 累计收听是秒；前端 `LlmMetrics.vue:42/108/115/122`、
    `AutoReviewConfig.vue:547/552-553`、`ManageUsers.vue:28` 各自硬编码 scale。
    描述：`_validate/news2/desc_t02506_otherscale.md`
  - **T02709**：门禁新增「单位字面量硬编码」检查（延续 T02504 枚举门禁思路），
    防止下一个页面重新写死 `(分钟)` / `*100`。描述：`_validate/news2/desc_t02506_gate.md`
  - **T02710**：小程序时长格式化收敛（`audio-player.js:156-157`、`episode-card.wxml:30-31`、
    `course.js:402-403`、`detail.js:996-1020` 等 10 处内联 `/60`、`%60`）。
    描述：`_validate/news2/desc_t02506_miniprogram.md`
  - **T02711**：`api/stats.js:18` 的 `getToday()` 指向不存在的 `/stats/today`
    （`routers/admin/stats.py` 实测只有 overview/trend/channel-health/rss-health/llm-metrics）。
    描述：`_validate/news2/desc_t02506_deadtoday.md`
- 本结果文档：`D:\code\otherProjects\20_News\_validate\news2\result_T02506.md`；
  全量 e2e 日志：`_validate/news2/_pw_t02506_full.log`。

## 下一步建议

- 单位元数据覆盖其余统计接口：已建派生单 **T02708**。
- 用构建期门禁锁死「视图里不得再出现硬编码单位/换算」：已建派生单 **T02709**。
- 小程序端时长格式化与单位口径对齐：已建派生单 **T02710**。
- 清理指向不存在端点的 `getToday`，并把统计路径收敛到 api 层：已建派生单 **T02711**。
- 趋势图 Y 轴刻度与 `completion_rate` 三处统一属 FR-UX-502 / **T02507**（本单已把 meta 随
  trend 下发，T02507 只需接 `metricValue`，不再需要新建契约）；不另建单，按待办顺序接着做。
