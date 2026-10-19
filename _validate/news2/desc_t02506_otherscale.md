来源：T02506（FR-UX-501 指标单位元数据）。本单只把「已经实测出问题」的统计概览/趋势
（overview + trend + dashboard-summary 内嵌）纳入单位元数据表并让 PC、移动端按 meta 渲染；
其余统计接口留在旧形态（各自硬编码 scale），本单不动它们，避免一次改动横跨五个页面 yet 无验证。

## 现状（实测）
- `backend/app/workflow/llm/rewriter.py:459-461`：`trigger_rate / improve_rate / not_improve_rate`
  已在后端 `round(x * 100, 2)`，返回的是 **0~100 百分比**；
- `backend/app/services/auto_review_service.py:725-727`：`success_rate` 是 **0~1 小数**（同名字段反刻度）；
- `backend/app/routers/admin/users.py:107` + `backend/app/models/user.py:24`：`total_listen_duration` 是 **秒**；
- 前端各自补 scale：`apps/admin-web/src/views/stats/LlmMetrics.vue:42` 直接 `{{ r.value }}%`、
  `:108/:115/:122` 只 `.toFixed(2)`（能对上纯粹因为后端恰好已乘 100）；
  `apps/admin-web/src/views/system/AutoReviewConfig.vue:547` 自己 `(rate*100).toFixed(1)+'%'`，
  `:552-553` 自己写秒/分换算；`apps/admin-web/src/views/mobile/ManageUsers.vue:28` 补 `次`/`秒` 后缀。
- 唯一真源 `backend/app/services/stats_metrics.py`（T02506 新建）目前只登记了 5 个概览指标。

## 建议做法
1. 把上述指标登记进 `METRIC_META`（`percent` / `ratio` / `second` 三类 unit 已在字典注释里预留），
   对应接口（`/stats/llm-metrics`、自动审核概览、`/admin/.../users` 列表）返回体加 `meta`；
2. 三个页面改用 `apps/admin-web/src/utils/format.js` 的 `metricLabel / metricValue / metricText`，
   删掉本地 `*100`、`toFixed(2)+'%'`、秒分换算；
3. 后端 `rewriter.py` 的派生率建议改为返回 0~1 ratio 并在 meta 里声明 `factor:100`，
   与 `completion_rate` 统一（这一步会改接口数值口径，需在 PR 里写明调用方影响）。

## 验收口径
- `backend/tests/test_stats_metric_meta.py` 扩展断言：新登记的每个接口响应里
  `meta` 覆盖返回的全部指标；
- PC 与移动端同一指标显示值一致（新增/复用 e2e 用例，参照 `tests/stats.spec.js`
  「移动端首页与 PC 卡片同口径」的写法）；
- 反证：从 `METRIC_META` 删掉一个成员并重跑 `python scripts/gen_stats_metric_meta.py`，
  `pytest tests/test_stats_metric_meta.py` 必须失败（夹具漂移守护已建好，直接复用）；
- `npm run build` + `npx playwright test stats.spec.js <受影响 spec>` 全绿。
