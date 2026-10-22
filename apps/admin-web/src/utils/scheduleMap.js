/**
 * 排期日历的数据整形（D24 / FR-UX-202）。
 *
 * 原来这段逻辑长在 `AdSchedule.vue` 的 `fetchSchedule()` 里，形态是
 * `map[dateKey][position] = { material_name, enabled }`——同一个广告位同一天
 * 有第二条投放时，后写直接覆盖前写，被盖掉的那条在日历上**彻底消失**：
 * 既没有「+1 条冲突」角标，也没有 tooltip，运营读到的是「这个位子只有一支」。
 *
 * 抽成纯函数是为了能被直接单测（视图里的循环 + 日期边界不适合靠字符串断言）。
 */

const ONE_DAY_MS = 24 * 60 * 60 * 1000

/**
 * @param {Array<{material_name: string, position: string, start_date: string, end_date: string, enabled: number, status: string}>} placements
 * @returns {Record<string, Record<string, {material_name: string, enabled: number, status: string, conflicts: Array}>>}
 */
export function buildScheduleMap(placements = []) {
  // 第一步：按 (日期, 广告位) 收集**全部**投放，不在这里挑一条
  const buckets = {}
  for (const p of placements) {
    const start = new Date(p.start_date)
    const end = new Date(p.end_date)
    // 日期缺失/非法时 Invalid Date 让 `d <= end` 直接为假，这条投放自然不产生任何格子，
    // 不需要额外分支（曾加过一道 NaN continue，变异探针实测删掉它行为完全一致，属冗余防御）。
    // 用显式重新赋值推进 d：SonarQube S2189 不认 d.setDate() 这类原地调用
    for (let d = new Date(start); d <= end; d = new Date(d.getTime() + ONE_DAY_MS)) {
      const dateKey = d.toISOString().slice(0, 10)
      const list = (buckets[dateKey] ||= {})
      const byPos = (list[p.position] ||= [])
      // status 由服务端派生（T02602），随格子带到视图，前端不再按 enabled 猜
      byPos.push({ material_name: p.material_name, enabled: p.enabled, status: p.status })
    }
  }

  // 第二步：归一化成视图需要的形状——主显一条 + 其余进 conflicts
  const map = {}
  for (const [dateKey, byPos] of Object.entries(buckets)) {
    map[dateKey] = {}
    for (const [pos, list] of Object.entries(byPos)) {
      map[dateKey][pos] = pickPrimary(list)
    }
  }
  return map
}

/**
 * 主显优先给**今天真正在播**的投放（status=active），其次给启用中的，
 * 停用的那条不该把启用的挤进折叠列表，否则「日历显示已停用」会和投放规则页
 * 对不上（T02491 / D14 的同一口径）。待投放/已过期都还没在播，排在停用之前
 * 只因开关仍是启用态（T02602）。
 */
export function pickPrimary(list) {
  const rank = (x) => (x.status === 'active' ? 0 : x.enabled !== 0 ? 1 : 2)
  let primaryIndex = 0
  for (let i = 1; i < list.length; i += 1) {
    if (rank(list[i]) < rank(list[primaryIndex])) primaryIndex = i
  }
  const primary = list[primaryIndex]
  return {
    material_name: primary.material_name,
    enabled: primary.enabled,
    status: primary.status,
    conflicts: list.filter((_, i) => i !== primaryIndex),
  }
}
