/**
 * D24 / FR-UX-202：排期日历重叠投放的整形逻辑。
 *
 * 红基线（修复前的行为，用同样输入可复现）：视图里是
 * `map[dateKey][p.position] = { material_name, enabled }`，同一个位子同一天有第二条
 * 投放时后写覆盖前写，被盖掉的那条**既不在主显也不在任何折叠列表里**——
 * 日历读起来是「这个位子只有 1 支广告」，实际有 2 支在争同一个曝光位。
 * 因此这里的核心断言是「两条都在，一条主显 + 一条进 conflicts」，
 * 而不是只断言「不崩」。
 */
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { buildScheduleMap, pickPrimary } from '../../src/utils/scheduleMap.js'

function placement(material_name, position, start_date, end_date, enabled = 1, status = enabled === 0 ? 'disabled' : 'active') {
  return { material_name, position, start_date, end_date, enabled, status }
}

test('同位同日重叠：两条投放都要留下，不能后写覆盖前写', () => {
  const map = buildScheduleMap([
    placement('早班广告A', 'head', '2026-03-05', '2026-03-07'),
    placement('晚班广告B', 'head', '2026-03-06', '2026-03-08'),
  ])
  const overlapped = map['2026-03-06'].head
  assert.equal(overlapped.conflicts.length, 1, '重叠的第二条必须进折叠列表')
  const names = [overlapped.material_name, ...overlapped.conflicts.map((c) => c.material_name)].sort()
  assert.deepEqual(names, ['早班广告A', '晚班广告B'])
})

test('重叠只影响相交的那几天：区间外仍是单条', () => {
  const map = buildScheduleMap([
    placement('早班广告A', 'head', '2026-03-05', '2026-03-07'),
    placement('晚班广告B', 'head', '2026-03-06', '2026-03-08'),
  ])
  assert.equal(map['2026-03-05'].head.conflicts.length, 0)
  assert.equal(map['2026-03-05'].head.material_name, '早班广告A')
  assert.equal(map['2026-03-08'].head.conflicts.length, 0)
  assert.equal(map['2026-03-08'].head.material_name, '晚班广告B')
})

test('主显优先给启用中的投放：停用那条不该挤掉启用的', () => {
  // 输入顺序刻意把停用的放前面——覆盖式写法会让日历显示「已停用」，
  // 与投放规则页对不上（T02491 / D14 的同一口径）。
  const map = buildScheduleMap([
    placement('过期广告D', 'tail', '2026-03-05', '2026-03-05', 0),
    placement('在投广告E', 'tail', '2026-03-05', '2026-03-05', 1),
  ])
  assert.equal(map['2026-03-05'].tail.material_name, '在投广告E')
  assert.equal(map['2026-03-05'].tail.enabled, 1)
  assert.deepEqual(map['2026-03-05'].tail.conflicts, [{ material_name: '过期广告D', enabled: 0, status: 'disabled' }])
})

test('主显优先给今天真正在播的（status=active），待投放/已过期让位', () => {
  // 三条开关都开着，但只有 status=active 的那条此刻真的会播（T02602）
  const map = buildScheduleMap([
    placement('待投放H', 'head', '2026-03-05', '2026-03-05', 1, 'pending'),
    placement('已过期I', 'head', '2026-03-05', '2026-03-05', 1, 'expired'),
    placement('生效中J', 'head', '2026-03-05', '2026-03-05', 1, 'active'),
  ])
  const slot = map['2026-03-05'].head
  assert.equal(slot.material_name, '生效中J')
  assert.equal(slot.status, 'active')
  assert.equal(slot.conflicts.length, 2)
  assert.deepEqual(
    slot.conflicts.map((c) => c.status).sort(),
    ['expired', 'pending']
  )
})

test('全部停用：仍保留主显与折叠，冲突数不丢', () => {
  const map = buildScheduleMap([
    placement('停用F', 'mid', '2026-03-05', '2026-03-05', 0),
    placement('停用G', 'mid', '2026-03-05', '2026-03-05', 0),
  ])
  const slot = map['2026-03-05'].mid
  assert.equal(slot.enabled, 0)
  assert.equal(slot.conflicts.length, 1)
})

test('三条重叠：折叠列表完整，主显只占一条', () => {
  const map = buildScheduleMap([
    placement('X1', 'head', '2026-03-05', '2026-03-05'),
    placement('X2', 'head', '2026-03-05', '2026-03-05'),
    placement('X3', 'head', '2026-03-05', '2026-03-05'),
  ])
  const slot = map['2026-03-05'].head
  assert.equal(slot.conflicts.length, 2)
  const names = [slot.material_name, ...slot.conflicts.map((c) => c.material_name)].sort()
  assert.deepEqual(names, ['X1', 'X2', 'X3'])
})

test('不同广告位互不干扰：head 的重叠不会算到 mid 头上', () => {
  const map = buildScheduleMap([
    placement('H1', 'head', '2026-03-05', '2026-03-05'),
    placement('H2', 'head', '2026-03-05', '2026-03-05'),
    placement('M1', 'mid', '2026-03-05', '2026-03-05'),
  ])
  assert.equal(map['2026-03-05'].head.conflicts.length, 1)
  assert.equal(map['2026-03-05'].mid.conflicts.length, 0)
  assert.equal(map['2026-03-05'].mid.material_name, 'M1')
})

test('跨天区间逐日展开，且日期键为 YYYY-MM-DD', () => {
  const map = buildScheduleMap([placement('P', 'tail', '2026-03-01', '2026-03-03')])
  assert.deepEqual(Object.keys(map).sort(), ['2026-03-01', '2026-03-02', '2026-03-03'])
})

test('跨月区间逐日展开，日期键保持 YYYY-MM-DD', () => {
  // 键被写成月份（slice 到 7 位）时这条会红——那会让整月共用一格，日历只剩1号有内容
  const map = buildScheduleMap([placement('P', 'tail', '2026-02-27', '2026-03-02')])
  assert.deepEqual(Object.keys(map).sort(),
    ['2026-02-27', '2026-02-28', '2026-03-01', '2026-03-02'])
  assert.equal(map['2026-03-01'].tail.material_name, 'P')
})

test('日期缺失或非法：这条投放不产生任何格子，也不抛错', () => {
  // Invalid Date 使 `d <= end` 恒为假，坏数据不会污染整张日历；
  // 这里钉的是可观测行为，不是某一行防御代码（NaN 分支实测为冗余，已删）。
  const map = buildScheduleMap([
    placement('坏数据', 'head', null, undefined),
    placement('正常', 'head', '2026-03-05', '2026-03-05'),
  ])
  assert.equal(map['2026-03-05'].head.material_name, '正常')
  assert.equal(Object.keys(map).length, 1)
})

test('空输入返回空 map（fetchSchedule 传 undefined 时不该崩）', () => {
  assert.deepEqual(buildScheduleMap(), {})
  assert.deepEqual(buildScheduleMap([]), {})
})

test('pickPrimary 单条投放：conflicts 是空数组而不是 undefined', () => {
  // 视图用 `slotConflicts(...).length` 判断角标，undefined 会直接抛
  const slot = pickPrimary([{ material_name: '唯一', enabled: 1 }])
  assert.deepEqual(slot.conflicts, [])
  assert.equal(slot.material_name, '唯一')
})

test('视图不再自带覆盖式整形：改为引用 scheduleMap，避免逻辑分叉', () => {
  const view = readFileSync(new URL('../../src/views/ad/AdSchedule.vue', import.meta.url), 'utf8')
  assert.match(view, /import \{ buildScheduleMap \} from '\.\.\/\.\.\/utils\/scheduleMap'/)
  assert.doesNotMatch(
    view,
    /map\[dateKey\]\[p\.position\]\s*=/,
    '视图里残留覆盖式赋值——同一位子的第二条投放会被静默吃掉（D24 原缺陷）'
  )
})

test('D24 在 PRD 里有归属条目与验收条款（可追溯性）', () => {
  // 审计时发现 D24 与 C56 原本连 FR 覆盖行都没有：修了代码但需求侧无从核对，
  // 等于下一期没人知道这两条已被处理。
  const prd = readFileSync(new URL('../../../../docs/需求规格说明书-UX优化.md', import.meta.url), 'utf8')
  const fr202 = prd.split('\n').find((l) => l.startsWith('| FR-UX-202 '))
  assert.ok(fr202, 'PRD 中应存在 FR-UX-202 需求行')
  assert.match(fr202, /D24/, 'D24 需挂在 FR-UX-202 覆盖条目下')
  assert.match(prd, /\| M2 \| 19 \|[^|\n]*D24/, 'M2 里程碑覆盖条目需包含 D24')

  const acc = prd.split('ACC-UX-201')[1].split('\n###')[0]
  assert.match(acc, /条重叠/, 'ACC-UX-201 需有重叠投放的验收条款')
  assert.match(acc, /主显优先/, '验收需锁定「启用中的投放占主显」这一口径')
})
