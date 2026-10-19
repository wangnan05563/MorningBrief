来源：T02506（FR-UX-501 指标单位元数据）。排查统计接口时顺手发现的死调用，
与本单口径改造无关，但会让下一个改统计的人以为「有 /stats/today 这个端点」。

## 现状（实测）
- `apps/admin-web/src/api/stats.js:18`：`export const getToday = () => api.get('/stats/today')`；
- 后端统计路由 `backend/app/routers/admin/stats.py` 只有
  `/overview`（:19）、`/trend`（:30）、`/channel-health`（:46）、`/rss-health`（:62）、
  `/llm-metrics`（:81），**没有 `/today`**——该调用发出即 404；
- 全仓 grep：`getToday` 无任何调用方（`api/stats.js` 的 `getOverview/getTrend` 同样没有被视图使用，
  统计页是在组件里直接 `api.get('/stats/overview')` 调的，见
  `apps/admin-web/src/views/stats/StatsOverview.vue:164`（overview）与 `:177`（trend）。

## 建议做法（二选一，倾向前者）
1. 删除 `getToday`，并把 `api/stats.js` 收敛为「统计接口唯一入口」：
   `StatsOverview.vue` 与 `views/mobile/Home.vue` 改用 `getOverview/getTrend/getDashboardSummary`，
   组件里不再出现裸路径字符串——否则「路径写错」这类问题永远只能靠人肉发现；
2. 或者真需要「今日快捷概览」，就在 `backend/app/routers/admin/stats.py` 补 `/today`
   （内部 `date.today()` 复用 `StatsService.get_overview`，返回体同样带 `meta`），
   并补 `backend/tests/test_stats_metric_meta.py` 风格的端点断言。

## 验收口径
- 选 1：`grep -rn "'/stats/" apps/admin-web/src/views` 为 0 命中（路径只存在于 api 层），
  `npm run build` + `npx playwright test stats.spec.js` 全绿；
- 选 2：新增端点测试断言 `meta` 覆盖全部返回指标，且 `stats.spec.js` 有一条用例真跑该端点。
