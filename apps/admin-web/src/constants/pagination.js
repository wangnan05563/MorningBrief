/**
 * 列表分页尺寸的单一口径（T02517 / FR-UX-703 + NFR-UX-03）
 *
 * 为什么存在：分页尺寸选择此前在每个页面各写一份 `[10, 20, 50]` / `[20, 50, 100, 200]`，
 * 结果 NFR-UX-03 的「列表分页尺寸上限 100」根本没人守住——`DatabaseAdmin.vue` 就写得出 200。
 * 更糟的是有几页连 `sizes` 都没进 `layout`（`ReviewList.vue`、`WorkflowDetail.vue`），
 * 写了 `:page-sizes` 也不会渲染选择器，看起来「有配置」其实是假的。
 *
 * 这里把「可选尺寸」与「上限」收成一处，配套 `tests/unit/list-capabilities.test.mjs`
 * 做仓库级不变量断言（每个 el-pagination 必须能选尺寸、尺寸不得超过上限），
 * 新增页面时不必再靠人记得抄一份。
 *
 * 上限 100 的依据：后端 `list_reviews`（`size: Query(20, ge=1, le=100)`）与
 * `m/inbox`（`page_size: Query(20, ge=1, le=100)`）都按 100 收口，前端给到 200
 * 只会被后端静默钳回 100，界面与实际能力不一致。
 */

/** NFR-UX-03：列表分页尺寸上限 */
export const MAX_PAGE_SIZE = 100

/** 主列表页（全屏表格）：允许 10 起步，审核列表每天几百条时需要 50/100 减少翻页 */
export const PAGE_SIZE_OPTIONS = [10, 20, 50, MAX_PAGE_SIZE]

/** 详情面板 / 大表内嵌分页：起步 20（面板高度有限，10 行会让「翻页找东西」更累） */
export const PANEL_PAGE_SIZE_OPTIONS = [20, 50, MAX_PAGE_SIZE]

/**
 * 钳制分页尺寸到允许值（T02517）。
 *
 * 用于「地址栏带来的 size 不在选项里」这类场景：`?size=7` 若原样发给后端，
 * 表格渲染 7 行而选择器里根本没有 7 这个选项，界面与数据不一致；
 * 静默回落到默认值又不如实。这里按「就近取允许值」处理，调用方仍应把钳制结果写回 URL。
 *
 * @param {number} value 待钳制的尺寸
 * @param {number[]} options 允许的尺寸列表
 * @param {number} fallback 列表为空/值不可用时的兜底
 */
export function clampPageSize(value, options = PAGE_SIZE_OPTIONS, fallback = options[0]) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return fallback
  const allowed = (options && options.length ? options : [fallback]).filter(
    (s) => Number.isFinite(s) && s > 0 && s <= MAX_PAGE_SIZE,
  )
  if (!allowed.length) return fallback
  if (n > MAX_PAGE_SIZE) return Math.max(...allowed)
  if (allowed.includes(n)) return n
  // 不在选项里：取最接近的一个（同样大小时取较小的那个，宁可少渲染也别超上限）
  return allowed.reduce(
    (best, s) =>
      Math.abs(s - n) < Math.abs(best - n) || (Math.abs(s - n) === Math.abs(best - n) && s < best)
        ? s
        : best,
    allowed[0],
  )
}
