/**
 * M3「反馈通道与失败可见性」单元测试（T02534 / T02535）
 *
 * 分两类，界线要说清：
 * 1) **行为断言**（强）：cosPath / calculatorSync 两个纯模块。它们是「静默破坏」的判定核心
 *    （H8 的畸形 destKey、M2 的静默夹取），可以直接构造输入断言输出，变异探针杀得动。
 * 2) **委托断言**（弱，但比没有强）：各页面必须把失败态交给统一件、而不是自己写死兜底值。
 *    M2 的教训是文本门抓不住标识符级破坏，所以这里只用来钉住「不许退回旧写法」，
 *    真实渲染行为由 tests/*.spec.js（真实 Chrome）负责。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { buildDestKey, normalizeSegment, validateSegment } from '../../src/utils/cosPath.js'
import {
  DURATION_RANGE,
  RATE_PERCENT_RANGE,
  buildSyncNotices,
  parseDuration,
  parseRate,
} from '../../src/utils/calculatorSync.js'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const SRC = '../../src/'

/** 取 FR 行的「覆盖条目」列（第 4 个单元格），切成条目集合 */
function frCoverage(row) {
  const cell = row.split('|')[4] || ''
  return new Set(cell.split(/[,、]/).map((s) => s.trim()).filter(Boolean))
}

// ---------------------------------------------------------------- H8 / cosPath

test('H8：后端 folders 的尾斜杠不会长成双斜杠 destKey', () => {
  // 原始缺陷现场：名字是 "sub1/"，旧代码补一个 '/' → "prefix/sub1//"
  assert.equal(buildDestKey('news/folder/', 'sub1/', true), 'news/folder/sub1/')
  // 用户「不改动直接点确定」必须得到与原来**相同**的键——这样短路返回才拦得住
  assert.equal(buildDestKey('news/folder/', 'sub1', true), buildDestKey('news/folder/', 'sub1/', true))
})

test('H8：文件（非目录）不补尾斜杠，首斜杠同样剥掉', () => {
  assert.equal(buildDestKey('news/a/', '/b.txt', false), 'news/a/b.txt')
  assert.equal(buildDestKey('', 'a.txt', false), 'a.txt')
})

test('H8：段内带斜杠被 validateSegment 拒掉（同级重命名的边界）', () => {
  assert.deepEqual(validateSegment('a/b'), { ok: false, reason: '名称不能包含 /（此处只做同级重命名）' })
  assert.deepEqual(validateSegment('   '), { ok: false, reason: '新名称不能为空' })
  assert.equal(validateSegment(' sub1/ ').ok, true)
  assert.equal(validateSegment(' sub1/ ').segment, 'sub1')
})

test('H8：normalizeSegment 只处理首尾，不动中间', () => {
  assert.equal(normalizeSegment('//x//'), 'x')
  assert.equal(normalizeSegment('a/b/'), 'a/b')
  assert.equal(normalizeSegment(undefined), '')
})

// ------------------------------------------------------------- M2 / calculatorSync

test('M2：计算器页的越界时长会被夹取，且夹取值可断言', () => {
  assert.deepEqual(
    { ...parseDuration('1800') },
    { requested: 1800, value: DURATION_RANGE.max, clamped: true, range: DURATION_RANGE },
  )
  assert.equal(parseDuration('60').value, DURATION_RANGE.min)
  assert.equal(parseDuration('60').clamped, true)
  assert.equal(parseDuration('600').clamped, false, '范围内不该被判定为夹取')
  assert.equal(parseDuration('abc'), null)
})

test('M2：倍率换算成 edge_rate，越界值同样夹取而不是原样写入表单', () => {
  assert.equal(parseRate('1.5').edge_rate, '+50%')
  assert.equal(parseRate('1').edge_rate, '')
  assert.equal(parseRate('0.8').edge_rate, '-20%')
  // 2.5x → +150%，超出滑杆 +100% 上限：旧代码把 "+150%" 原样塞进表单却报「已同步」
  const r = parseRate('2.5')
  assert.equal(r.percent, 150)
  assert.equal(r.edge_rate, '+100%')
  assert.equal(r.clamped, true)
  assert.equal(parseRate('0.2').edge_rate, '-50%')
  assert.equal(parseRate(''), null)
})

test('M2：被夹取时必须说出来，文案含「请求值 → 实际落值 → 范围」三段', () => {
  const notices = buildSyncNotices(parseDuration('1800'), parseRate('2.5'))
  assert.equal(notices.length, 2)
  assert.match(notices[0], /1800s[\s\S]*180–1200s[\s\S]*1200s/)
  assert.match(notices[1], /2\.5x[\s\S]*\+150%[\s\S]*-50%~\+100%[\s\S]*\+100%/)
  // 范围内则一条都不许有——「都正常还报警」会把用户训练成忽略警告
  assert.deepEqual(buildSyncNotices(parseDuration('600'), parseRate('1.2')), [])
  assert.deepEqual(buildSyncNotices(null, null), [])
})

test('M2：两页区间常量以 AIConfig 滑杆为准，且由测试盯住漂移', () => {
  const vue = read(`${SRC}views/ai/AIConfig.vue`)
  assert.match(vue, /:min="180" :max="1200"/, 'AIConfig 时长滑杆范围变了：DURATION_RANGE 要同步')
  assert.match(vue, /:min="-50" :max="100"/, '语速滑杆范围变了：RATE_PERCENT_RANGE 要同步')
  assert.equal(DURATION_RANGE.min, 180)
  assert.equal(RATE_PERCENT_RANGE.max, 100)
})

test('M2：AIConfig 把夹取判定委托给纯模块，而不是留一份会漂移的内联副本', () => {
  const vue = read(`${SRC}views/ai/AIConfig.vue`)
  assert.match(vue, /from '\.\.\/\.\.\/utils\/calculatorSync'/)
  assert.doesNotMatch(
    vue,
    /Math\.max\(180,\s*Math\.min\(1200/,
    '内联 clamp 又回来了：区间会和 utils/calculatorSync 漂移',
  )
  assert.doesNotMatch(
    vue,
    /if \(applied\.length > 0\) \{\s*ElMessage\.info\(`已从参数计算器同步/,
    '同步提示退回无条件 info：夹取又不说了',
  )
})

// ------------------------------------------------- D25 / I15 / M71 / C73 委托门

test('H8：CosFiles 的重命名必须走 cosPath，而不是把尾斜杠无条件补回去', () => {
  const vue = read(`${SRC}views/cos/CosFiles.vue`)
  assert.match(vue, /from '\.\.\/\.\.\/utils\/cosPath'/, '委托断了：畸形 destKey 会重新在页面里长出来')
  assert.match(vue, /const destKey = buildDestKey\(/)
  assert.match(vue, /validateSegment\(renameNewName\.value\)/, '未校验就提交：a/b 会被当成合法名称')
  // 旧写法 `newName + '/'` 是本缺陷的成因；两处（校验、拼接）都得撤掉
  assert.doesNotMatch(vue, /renameNewName\.value \+ '\/'/, '无条件补尾斜杠的旧写法又回来了')
  assert.doesNotMatch(vue, /const destKey = \$\{currentPrefix\.value\}\$\{renameNewName\.value\}/)
  // 行名要显示成 "sub1" 而不是 "sub1/"，否则用户永远要在弹窗里手删尾斜杠
  assert.match(vue, /replace\(\/\\\/\+\$\/, ''\)/, '后端 folders 自带的尾斜杠未从显示名里剥掉')
})

test('D25：排期日历失败时清掉上月数据并交给页内错误态', () => {
  const vue = read(`${SRC}views/ad/AdSchedule.vue`)
  assert.match(vue, /catch \(e\) \{[\s\S]*?scheduleMap\.value = \{\}/)
  assert.match(vue, /<ListLoadError[\s\S]*?v-if="loadError"/)
  // 关键：日历本体在失败时不得继续渲染「—」（「—」在本页的意思就是该日无排期）
  assert.match(vue, /<el-calendar v-if="!loadError"/)
  assert.match(vue, /from '\.\.\/\.\.\/utils\/scheduleMap'/, 'D24 的重叠整形不能被顺手删掉')
})

test('I15：移动端首页不得再用 0 兜住接口失败', () => {
  const vue = read(`${SRC}views/mobile/Home.vue`)
  assert.doesNotMatch(
    vue,
    /getDashboardSummary\(\)\.catch\(\(\) => \(\{/,
    '旧的兜底回来了：接口失败会被铺成「DAU -、待审 0、未读 0」的正常空态',
  )
  assert.match(vue, /loadError\.value = e\?\.message/)
  assert.match(vue, /<section v-if="!loadError" class="m-section">/)
})

test('M71：维护页状态失败要走页内错误态，旧值靠 stale 说明过期', () => {
  const vue = read(`${SRC}views/maintenance/Maintenance.vue`)
  assert.doesNotMatch(vue, /console\.error\('加载存储状态失败'/)
  assert.match(vue, /statusError\.value = error\?\.message/)
  assert.match(vue, /<ListLoadError[\s\S]*?:stale="!!status"/)
  // 首次失败时三卡必须撤下：`?? 0` 会把「不知道」写成「0 条日志、无需清理」，
  // 只加一条错误横幅而留着断言，等于没修 M71
  assert.match(vue, /<div v-if="status" class="status-section"/)
})

test('C73：讲书稿面板切频道先清残留，失败聚合进一条错误态', () => {
  const vue = read(`${SRC}views/channel/BookPoolPanel.vue`)
  assert.match(vue, /resetPoolView\(\)\s*\n\s*const errors = \[\]/)
  assert.match(vue, /poolError\.value = errors\.length/)
  assert.match(vue, /await Promise\.all\(\[loadState\(errors\), loadPool\(errors\)\]\)/)
  // 失败态下这些「会声称一件事实」的块必须撤下：0 本 / 未开启 都是一种声称
  assert.match(vue, /v-if="!poolError && state\.enabled"/)
  assert.match(vue, /v-else-if="!poolError"/)
  assert.match(vue, /<el-form v-if="!poolError" :inline="true" class="schedule-form"/)
})

test('C16：resetForm 覆盖 form 的全部可写字段（含动态写入的 icon_url）', () => {
  const vue = read(`${SRC}views/channel/ChannelManagement.vue`)
  const start = vue.indexOf('function resetForm()')
  const body = vue.slice(start, vue.indexOf('function openCreate()', start))
  // 锚到行首：`// form.x = []` 这种「注释掉但留着」的写法必须算没复位（变异探针抓到的空转）
  const reset = (f) => new RegExp(`^\\s*form\\.${f}\\s*=`, 'm')
  for (const f of ['book_rss_sources', 'icon_url', 'rss_sources', 'cover_url', 'manual_material_ids_text']) {
    assert.match(body, reset(f), `resetForm 漏清 ${f}：会串进下一个频道`)
  }
  // 声明字段全集 ⊂ 复位字段：漏一个就是跨频道串味（C16 的原始机制）
  // 注意终点取 reactive({...}) 的收尾而不是「下一个 const editing」——后者在声明之前就声明了
  const declStart = vue.indexOf('const form = reactive({')
  const decl = vue.slice(declStart, vue.indexOf('\n})', declStart))
  const declared = [...decl.matchAll(/^\s+([a-z_][a-z0-9_]*)\s*:/gm)].map((m) => m[1])
  assert.ok(declared.length > 15, `form 声明抽取失败（${declared.length} 个字段），本条门已空转`)
  const interactionOnly = new Set(['lookbackEnabled', 'inherit_segment_gap', 'inherit_bgm_gap'])
  const missed = declared.filter((f) => !reset(f).test(body) && !interactionOnly.has(f))
  assert.deepEqual(missed, [], `resetForm 未复位的声明字段：${missed.join(', ')}`)
})

test('C43：切到「按书聚合」即作废明细视图专有的精确定位', () => {
  const vue = read(`${SRC}views/channel/MaterialLibrary.vue`)
  assert.match(vue, /@change="onViewModeChange"/, '视图切换又直接走 onSearch：提示条会与真实过滤口径脱节')
  const start = vue.indexOf('function onViewModeChange')
  const fn = vue.slice(start, start + 900)
  assert.ok(start > 0, 'onViewModeChange 被删掉了')
  assert.match(fn, /materialIdFilter\.value = null/)
  assert.match(fn, /sourceFilter\.value = ''/)
  assert.match(fn, /按书聚合.*不支持按素材 ID/)
  // 后端聚合接口的参数面就是这条口径的事实源：多传不认，所以前端必须作废
  const be = read('../../../../backend/app/routers/admin/materials.py')
  const agg = be.slice(be.indexOf('@router.get("/aggregate")'), be.indexOf('@router.get("/aggregate")') + 1200)
  assert.doesNotMatch(agg, /material_id: int = Query/, '后端聚合接口已支持 material_id：前端作废逻辑与这条门要一起改')
})

test('E11：WorkflowDetail 用了 h() 就必须显式导入 h', () => {
  const vue = read(`${SRC}views/workflow/WorkflowDetail.vue`)
  assert.match(vue, /h\(/, '若已不再用 h()，请连同这条门一起删掉，别留空断言')
  assert.match(
    vue,
    /import \{[^}]*\bh\b[^}]*\} from 'vue'/,
    'AutoImport 没配 imports:["vue"]，缺 h 会运行时 ReferenceError 且被 Promise 吞掉（E11 原样）',
  )
  const cfg = read('../../vite.config.js')
  assert.doesNotMatch(cfg, /imports:\s*\[[^\]]*'vue'/, 'AutoImport 若已配 vue，本条门与显式 import 需要重新裁决')
})

/**
 * 「接错对象」门：错误态的形对了不算修好，重试必须接回**本页自己的加载函数**。
 * 覆盖率式断言（「四个页面都有重试入口」）会把 A 页的 @retry 接到 B 页的函数上照样全绿，
 * 所以这里逐页做「声明位 ↔ 实际调用位」配对：@retry 的处理函数名 + 该函数体内调用的加载器。
 */
const RETRY_WIRING = [
  { file: 'views/ad/AdSchedule.vue', handler: 'retryLoadSchedule', loads: 'fetchSchedule', errorRef: 'loadError' },
  { file: 'views/mobile/Home.vue', handler: 'retryLoad', loads: 'load()', errorRef: 'loadError' },
  { file: 'views/maintenance/Maintenance.vue', handler: 'retryLoadStatus', loads: 'loadStatus()', errorRef: 'statusError' },
  { file: 'views/channel/BookPoolPanel.vue', handler: 'retryLoadAll', loads: 'loadAll()', errorRef: 'poolError' },
]
for (const w of RETRY_WIRING) {
  test(`${w.file}：重试入口接回本页加载函数，且失败标志与错误态是同一个`, () => {
    const vue = read(`${SRC}${w.file}`)
    assert.match(vue, new RegExp(`@retry="${w.handler}"`), '重试没接到本页处理函数')
    const start = vue.indexOf(`function ${w.handler}`)
    assert.ok(start > 0, `${w.handler} 未定义`)
    const body = vue.slice(start, start + 260)
    assert.match(body, new RegExp(w.loads.replace(/[()]/g, (c) => `\\${c}`)), `${w.handler} 没有重新调用本页加载器`)
    // 声明位与实际调用位必须同一个 ref：@retry 复位 A、错误态读 B，等于点了没反应
    assert.match(vue, new RegExp(`${w.errorRef}\\.value = `), `${w.errorRef} 未被写入`)
  })
}

// -------------------------------------------------------------- PRD 追溯
test('PRD：M3 的 25 条覆盖清单与本批交付点对得上', () => {
  const prd = read('../../../../docs/需求规格说明书-UX优化.md')
  const row = prd.split('\n').find((l) => l.startsWith('| M3 | 25 |'))
  assert.ok(row, '里程碑覆盖表里的 M3 行不见了')
  const ids = row.split('|')[3].trim().split('、')
  assert.equal(ids.length, 25, `M3 行条目数是 ${ids.length}，不是 25`)
  for (const id of ['D25', 'C73', 'I15', 'M71', 'C16', 'C43', 'E11', 'H8', 'M2']) {
    assert.ok(ids.includes(id), `M3 覆盖清单缺少 ${id}`)
  }
})

test('FR-UX-302 的覆盖条目里必须包含本批接入错误态的页面', () => {
  const prd = read('../../../../docs/需求规格说明书-UX优化.md')
  const line = prd.split('\n').find((l) => l.startsWith('| FR-UX-302 |'))
  assert.ok(line, 'FR-UX-302 需求行不见了')
  const covered = frCoverage(line)
  for (const id of ['C5', 'M54', 'D25', 'C73', 'I15', 'M71', 'B21']) {
    assert.ok(covered.has(id), `FR-UX-302 覆盖清单未列入 ${id}（本批已按其口径交付，追溯不能断）`)
  }
})

test('FR-UX-305 认领「界面不得声称未发生的事」这一组', () => {
  const prd = read('../../../../docs/需求规格说明书-UX优化.md')
  const line = prd.split('\n').find((l) => l.startsWith('| FR-UX-305 |'))
  assert.ok(line, 'FR-UX-305 需求行不见了：本批的静默破坏类交付点将无 FR 可归')
  const covered = frCoverage(line)
  for (const id of ['C16', 'C43', 'E11', 'H8', 'M2']) {
    assert.ok(covered.has(id), `FR-UX-305 覆盖清单未列入 ${id}`)
  }
  // 里程碑表的 FR 数是给计划用的，加行必须同步，否则 §3 与 §4 自相矛盾
  const m3 = prd.split('\n').find((l) => l.startsWith('| M3 | 反馈通道与失败可见性 |'))
  assert.ok(m3, '§3 里程碑表里的 M3 行不见了')
  assert.equal(m3.split('|')[4].trim(), '5', 'M3 的 FR 数应与 FR 行数一致')
})

test('M3 的 25 条高危每条都要能在某个 FR 行的覆盖条目里找到（无孤儿）', () => {
  const prd = read('../../../../docs/需求规格说明书-UX优化.md')
  const m3Row = prd.split('\n').find((l) => l.startsWith('| M3 | 25 |'))
  assert.ok(m3Row, '§10 追溯表里的 M3 行不见了')
  const ids = m3Row.split('|')[3].trim().split('、')
  // 逐行取「覆盖条目」列并按分隔符切开——用 includes 会被 M2/M24 这类前缀互相吃掉
  const all = new Set()
  for (const l of prd.split('\n')) {
    if (/^\| FR-UX-\d+ \|/.test(l)) frCoverage(l).forEach((id) => all.add(id))
  }
  const orphans = ids.filter((id) => !all.has(id))
  assert.deepEqual(orphans, [], `这些 M3 条目没有归属的 FR，验收时无从追溯：${orphans.join(', ')}`)
})
