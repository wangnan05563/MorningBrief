/**
 * URL 状态读写单元测试（FR-UX-602 / T02511）
 *
 * 为什么用 node --test 而不是只靠 Playwright：深链校验的规则（非法值回落默认值、
 * 越界钳到最后一页、等于默认值不进 URL、未知 query 键不能被抹掉、开放重定向拦截）
 * 全在 src/utils/urlState.js 这一份纯函数里。e2e 只能看到「页面上恰好显示的那一种」，
 * 而规则一旦被后续改动破坏，只有这里能逐条断言到。
 * 运行：cd apps/admin-web && node --test tests/unit/url-state.test.mjs
 * （Node 24 在本机不接受 `node --test tests/unit` 这种目录形式，会被当模块加载）
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import {
  crossEndTarget,
  detailLocation,
  isMobilePath,
  isQueryDirty,
  MATERIALS_QUERY_SPECS,
  parseFromQuery,
  readUrlState,
  returnTarget,
  SCOPED_REVIEW_SPECS,
  sanitizeRedirect,
  splitAppUrl,
  stripModeQuery,
  validateDateRange,
  validateIsoDate,
  writeUrlQuery,
} from '../../src/utils/urlState.js'

const SPECS = {
  tab: { default: 'pending', enum: ['pending', 'approved', 'rejected'] },
  page: { type: 'int', default: 1 },
  size: { type: 'int', default: 10 },
}

describe('readUrlState：非法值一律回落默认值并如实报告', () => {
  it('空 query 全按默认值', () => {
    const { values, invalid } = readUrlState({}, SPECS)
    assert.deepEqual(values, { tab: 'pending', page: 1, size: 10 })
    assert.deepEqual(invalid, [])
  })

  it('?tab=approved&page=3 原样读出（深链的正例）', () => {
    const { values, invalid } = readUrlState({ tab: 'approved', page: '3' }, SPECS)
    assert.equal(values.tab, 'approved')
    assert.equal(values.page, 3)
    assert.equal(invalid.length, 0)
  })

  it('枚举白名单外的 ?tab=replaced 回落 pending 并进 invalid（不允许渲染空白表）', () => {
    const { values, invalid } = readUrlState({ tab: 'replaced' }, SPECS)
    assert.equal(values.tab, 'pending')
    assert.equal(invalid.length, 1)
    assert.equal(invalid[0].key, 'tab')
    assert.match(invalid[0].reason, /不在允许值/)
  })

  it('大小写敏感：?tab=Approved 属非法（tab 值直接进接口参数）', () => {
    const { values, invalid } = readUrlState({ tab: 'Approved' }, SPECS)
    assert.equal(values.tab, 'pending')
    assert.equal(invalid.length, 1)
  })

  it('非整数 ?page=abc 回落第 1 页', () => {
    const { values, invalid } = readUrlState({ page: 'abc' }, SPECS)
    assert.equal(values.page, 1)
    assert.match(invalid[0].reason, /不是整数/)
  })

  it('?page=0 / 负数低于下限也回落', () => {
    for (const raw of ['0', '-3']) {
      const { values, invalid } = readUrlState({ page: raw }, SPECS)
      assert.equal(values.page, 1, raw)
      assert.match(invalid[0].reason, /小于下限/)
    }
  })

  it('给了动态上限（最大页码）时越界钳到上限而不是回第 1 页，并留痕', () => {
    const { values, invalid } = readUrlState({ page: '999' }, { ...SPECS, page: { ...SPECS.page, max: 7 } })
    assert.equal(values.page, 7)
    assert.equal(invalid.length, 1)
    assert.match(invalid[0].reason, /超过上限 7/)
  })

  it('数组形态 ?tab=a&tab=b 取第一个并在 invalid 留痕', () => {
    const { values, invalid } = readUrlState({ tab: ['approved', 'rejected'] }, SPECS)
    assert.equal(values.tab, 'approved')
    assert.match(invalid[0].reason, /同一参数出现多次/)
  })

  it('空串按「未提供」处理，不当成非法', () => {
    const { values, invalid } = readUrlState({ tab: '', page: '' }, SPECS)
    assert.deepEqual(values, { tab: 'pending', page: 1, size: 10 })
    assert.deepEqual(invalid, [])
  })

  it('validator 失败（C68 那类「频道不存在」）回落默认值并报出原因', () => {
    const specs = { channelId: { default: '1', validator: (v) => (['1', '2'].includes(v) ? true : '查无此频道') } }
    const ok = readUrlState({ channelId: '2' }, specs)
    assert.equal(ok.values.channelId, '2')
    assert.equal(ok.invalid.length, 0)
    const bad = readUrlState({ channelId: '9999' }, specs)
    assert.equal(bad.values.channelId, '1')
    assert.equal(bad.invalid[0].reason, '查无此频道')
  })
})

describe('writeUrlQuery：等于默认值不写脏地址，未知键不能被抹掉', () => {
  it('默认值键被删除，非默认值键写入', () => {
    const q = writeUrlQuery({}, SPECS, { tab: 'approved', page: 1, size: 10 })
    assert.deepEqual(q, { tab: 'approved' })
  })

  it('其他页面挂上来的 query 键（channel_name / workflow_id）原样保留', () => {
    const cur = { channel_name: '科技前沿', workflow_id: '123' }
    const q = writeUrlQuery(cur, SPECS, { tab: 'rejected', page: 2, size: 10 })
    assert.deepEqual(q, { channel_name: '科技前沿', workflow_id: '123', tab: 'rejected', page: '2' })
  })

  it('数值写成字符串（router query 只认字符串，数字会在比较时误判 dirty）', () => {
    const q = writeUrlQuery({}, SPECS, { page: 3 })
    assert.equal(q.page, '3')
  })

  it('不修改入参', () => {
    const cur = { tab: 'approved' }
    writeUrlQuery(cur, SPECS, { tab: 'pending' })
    assert.deepEqual(cur, { tab: 'approved' })
  })

  it('isQueryDirty：只有真的会改变 URL 才需要写回（防 replace 抖动）', () => {
    assert.equal(isQueryDirty({ tab: 'approved' }, SPECS, { tab: 'approved', page: 1, size: 10 }), false)
    assert.equal(isQueryDirty({ tab: 'approved' }, SPECS, { tab: 'rejected', page: 1, size: 10 }), true)
    assert.equal(isQueryDirty({ tab: 'approved', page: '4' }, SPECS, { tab: 'approved', page: 4, size: 10 }), false)
  })
})

describe('stripModeQuery：mode= 是端覆盖开关，跨端跳转必须丢掉', () => {
  it('只丢 mode，其余保留', () => {
    assert.deepEqual(stripModeQuery({ mode: 'mobile', tab: 'approved' }), { tab: 'approved' })
  })
})

describe('crossEndTarget：跨端重定向保留 path 与 query', () => {
  it('手机上打开 /queue?status=failed → /m/manage/queue 且 query 带过去', () => {
    const t = crossEndTarget('/queue', { status: 'failed' }, 'mobile')
    assert.equal(t.path, '/m/manage/queue')
    assert.deepEqual(t.query, { status: 'failed' })
  })

  it('/review?tab=approved&page=3 → /m/review 且 tab/page 都在', () => {
    const t = crossEndTarget('/review', { tab: 'approved', page: '3' }, 'mobile')
    assert.equal(t.path, '/m/review')
    assert.equal(t.query.tab, 'approved')
    assert.equal(t.query.page, '3')
  })

  it('反向：PC 视口访问 /m/review?workflow_id=9 → /review 且 workflow_id 保留', () => {
    const t = crossEndTarget('/m/review', { workflow_id: '9' }, 'desktop')
    assert.equal(t.path, '/review')
    assert.equal(t.query.workflow_id, '9')
  })

  it('mode= 不会跟着跳（否则切完立刻被反向判定切回原端）', () => {
    const t = crossEndTarget('/review', { mode: 'mobile', tab: 'approved' }, 'mobile')
    assert.equal(t.query.mode, undefined)
    assert.equal(t.query.tab, 'approved')
  })

  it('对不上等价表时回对面首页，但原路径留在 from 里，query 不丢', () => {
    const t = crossEndTarget('/db-admin', { keyword: 'x' }, 'mobile')
    assert.equal(t.path, '/m/home')
    assert.equal(t.query.from, '/db-admin')
    assert.equal(t.query.keyword, 'x')
  })

  it('PC 视口下访问 PC 路径不重定向（path 为 null）', () => {
    const t = crossEndTarget('/review', { tab: 'approved' }, 'desktop')
    assert.equal(t.path, null)
    assert.equal(t.query.tab, 'approved')
  })

  // 实测踩过的坑：端归属用 `startsWith('/m')` 判断，于是 PC 的 /materials、/maintenance
  // 也被当成移动端路径——桌面打开素材录入被重定向到 /review，页面直接进错。
  it('桌面视口下访问以 /m 开头的 PC 路径不重定向（/materials、/maintenance）', () => {
    for (const p of ['/materials', '/maintenance', '/message-not-mobile']) {
      const t = crossEndTarget(p, { keyword: 'x' }, 'desktop')
      assert.equal(t.path, null, `${p} 不该被当成移动端路径`)
      assert.equal(t.query.keyword, 'x')
    }
  })

  it('手机视口下访问 /materials 走移动端首页并保留 from（它确实不是移动端路径）', () => {
    const t = crossEndTarget('/materials', {}, 'mobile')
    assert.equal(t.path, '/m/home')
    assert.equal(t.query.from, '/materials')
  })

  it('手机视口下已在移动端路径不重定向（/m/manage/queue 不被削段误判）', () => {
    const t = crossEndTarget('/m/manage/queue', { status: 'failed' }, 'mobile')
    assert.equal(t.path, null)
    assert.equal(t.query.status, 'failed')
  })
})

describe('isMobilePath：移动端命名空间只有 /m 与 /m/…', () => {
  it('/m 与 /m/ 子路径算移动端', () => {
    assert.equal(isMobilePath('/m'), true)
    assert.equal(isMobilePath('/m/home'), true)
    assert.equal(isMobilePath('/m/manage/alert'), true)
    assert.equal(isMobilePath('/m/login'), true)
  })

  it('以 /m 开头的 PC 路径不算移动端', () => {
    for (const p of ['/materials', '/maintenance', '/message', '/mod']) {
      assert.equal(isMobilePath(p), false, `${p} 是 PC 路径`)
    }
  })

  it('空值/异常输入不炸，按非移动端处理', () => {
    assert.equal(isMobilePath(''), false)
    assert.equal(isMobilePath(undefined), false)
    assert.equal(isMobilePath(null), false)
  })
})

describe('sanitizeRedirect：只认站内绝对路径', () => {
  it('站内路径 + query 放行', () => {
    assert.equal(sanitizeRedirect('/review?tab=approved&page=3'), '/review?tab=approved&page=3')
  })

  it('协议相对 //evil.com 拒绝（开放重定向的经典入口）', () => {
    assert.equal(sanitizeRedirect('//evil.com'), null)
  })

  it('外链与 javascript: 拒绝', () => {
    for (const raw of ['https://evil.com', 'javascript:alert(1)', 'evil.com/x']) {
      assert.equal(sanitizeRedirect(raw), null, raw)
    }
  })

  it('指回登录页自身拒绝（防自我循环）', () => {
    assert.equal(sanitizeRedirect('/login?redirect=/review'), null)
    assert.equal(sanitizeRedirect('/m/login'), null)
  })

  it('数组形态取第一个，空值拒绝', () => {
    assert.equal(sanitizeRedirect(['/review', '/queue']), '/review')
    assert.equal(sanitizeRedirect(undefined), null)
  })
})

// ============ T02512 / FR-UX-603：隐藏子页的来源地址与返回 ============

describe('splitAppUrl：把应用内地址拆成 path + query', () => {
  it('带 query 的地址拆干净', () => {
    assert.deepEqual(splitAppUrl('/review?tab=approved&page=2'), {
      path: '/review',
      query: { tab: 'approved', page: '2' },
    })
  })

  it('无 query 与只有 ? 的边界', () => {
    assert.deepEqual(splitAppUrl('/workflows'), { path: '/workflows', query: {} })
    assert.deepEqual(splitAppUrl('/workflows?'), { path: '/workflows', query: {} })
    assert.deepEqual(splitAppUrl(''), { path: '/', query: {} })
  })

  it('空值参数与无等号参数保留为空串', () => {
    assert.deepEqual(splitAppUrl('/queue?status=&x'), { path: '/queue', query: { status: '', x: '' } })
  })

  it('裸百分号不能把整条地址解析打挂（safeDecode 容错）', () => {
    assert.deepEqual(splitAppUrl('/search?q=100%'), { path: '/search', query: { q: '100%' } })
  })
})

describe('detailLocation：进详情时把来源地址挂到 ?from=', () => {
  it('from 放原样地址，不预先百分号编码', () => {
    const to = detailLocation('/review?tab=approved&page=2', '/review/9')
    assert.equal(to.path, '/review/9')
    // 交给 vue-router 序列化：它只会转义会破坏 query 分组的 & # + 空格，
    // 预编码反而会让地址栏出现 %252F，且让 URLSearchParams.get('from') 读到编码串
    assert.equal(to.query.from, '/review?tab=approved&page=2')
  })

  it('额外的详情参数与 from 共存', () => {
    const to = detailLocation('/m/manage/queue', '/m/review', { workflow_id: '12', channel_name: '财经' })
    assert.equal(to.query.workflow_id, '12')
    assert.equal(to.query.channel_name, '财经')
    assert.equal(to.query.from, '/m/manage/queue')
  })

  it('来源地址缺失时退化成空串，由 parseFromQuery 判为无来源', () => {
    assert.equal(detailLocation(undefined, '/review/9').query.from, '')
    assert.equal(parseFromQuery({ from: '' }), null)
  })
})

describe('parseFromQuery / returnTarget：返回目标只认站内地址', () => {
  it('还原来源筛选，且不会把 from 自己带回去', () => {
    assert.deepEqual(parseFromQuery({ from: '/review?tab=approved&page=2' }), {
      path: '/review',
      query: { tab: 'approved', page: '2' },
    })
  })

  it('整串百分号编码（手工粘贴的链接）也能解', () => {
    assert.deepEqual(parseFromQuery({ from: '%2Freview%3Ftab%3Dapproved' }), {
      path: '/review',
      query: { tab: 'approved' },
    })
  })

  it('嵌套的 from 被剥掉，避免地址越跳越长', () => {
    const t = parseFromQuery({ from: '/review?from=%2Fqueue&tab=pending' })
    assert.equal(t.path, '/review')
    // 返回目标是「列表那一页」，它自己不该再带 from——否则每次进出详情都往地址上叠一层
    assert.deepEqual(t.query, { tab: 'pending' })
    assert.equal('from' in t.query, false)
  })

  it('站外与协议相对地址一律不接受', () => {
    for (const raw of ['https://evil.com', '//evil.com', 'evil.com/x', 'javascript:alert(1)']) {
      assert.equal(parseFromQuery({ from: raw }), null, raw)
    }
  })

  it('指回登录页的来源不接受（与 sanitizeRedirect 同一道闸）', () => {
    assert.equal(parseFromQuery({ from: '/login?redirect=/review' }), null)
    assert.equal(parseFromQuery({ from: '/m/login' }), null)
  })

  it('数组形态取第一个', () => {
    assert.deepEqual(parseFromQuery({ from: ['/review?tab=approved', '/queue'] }), {
      path: '/review',
      query: { tab: 'approved' },
    })
  })

  it('没有 from 时兜到 fallback，query 为空', () => {
    assert.deepEqual(returnTarget({}, '/workflows'), { path: '/workflows', query: {} })
    assert.deepEqual(returnTarget({ tab: 'approved' }, '/review'), { path: '/review', query: {} })
  })

  it('有可信 from 时优先按 from 回', () => {
    assert.deepEqual(returnTarget({ from: '/workflows?source=cron&status=failed' }, '/workflows'), {
      path: '/workflows',
      query: { source: 'cron', status: 'failed' },
    })
  })
})

describe('跨端 withFrom 与详情 from 同一口径（parseFromQuery 一个入口都能认）', () => {
  it('桌面访问移动端独有页时挂的 from 能被解析回来', () => {
    const t = crossEndTarget('/m/manage/users', {}, 'mobile') // 已在移动端命名空间：不挂 from
    assert.equal(t.path, null)
    const q = crossEndTarget('/message-center', {}, 'mobile') // 等价表对不上：from 记原路径
    assert.deepEqual(parseFromQuery(q.query), { path: '/message-center', query: {} })
  })
})

// ---------------------------------------------------------------------------
// T02760 / FR-UX-602 E12：深链参数校验补全
// ---------------------------------------------------------------------------

describe('MATERIALS_QUERY_SPECS：素材库深链只放合法值进查询', () => {
  it('合法深链原样生效', () => {
    const { values, invalid } = readUrlState(
      { channelId: '7', materialId: '21', source: '人工智能简史', keyword: '语音', view: 'book' },
      MATERIALS_QUERY_SPECS,
    )
    assert.deepEqual(values, {
      channelId: 7,
      materialId: 21,
      source: '人工智能简史',
      keyword: '语音',
      view: 'book',
    })
    assert.deepEqual(invalid, [])
  })

  it('没有参数时全部回默认值（不把 undefined 带进查询）', () => {
    assert.deepEqual(readUrlState({}, MATERIALS_QUERY_SPECS).values, {
      channelId: null,
      materialId: null,
      source: '',
      keyword: '',
      view: '',
    })
  })

  it('channelId / materialId 只认正整数：负数、小数、非数字一律丢弃并留痕', () => {
    for (const raw of ['-1', '0', '1.5', 'abc', '']) {
      const { values, invalid } = readUrlState({ channelId: raw, materialId: raw }, MATERIALS_QUERY_SPECS)
      assert.equal(values.channelId, null, `channelId=${JSON.stringify(raw)} 不该进查询`)
      assert.equal(values.materialId, null, `materialId=${JSON.stringify(raw)} 不该进查询`)
      const keys = invalid.map((i) => i.key)
      if (raw !== '') {
        assert.ok(keys.includes('channelId'), `channelId=${raw} 被静默丢弃，没有留痕`)
        assert.ok(keys.includes('materialId'), `materialId=${raw} 被静默丢弃，没有留痕`)
      }
    }
  })

  it('重复参数（?channelId=7&channelId=8）取第一个并留痕', () => {
    const { values, invalid } = readUrlState({ channelId: ['7', '8'] }, MATERIALS_QUERY_SPECS)
    assert.equal(values.channelId, 7)
    assert.equal(invalid[0].key, 'channelId')
    assert.match(invalid[0].reason, /出现多次/)
  })

  it('view 只认 book；自由文本超长直接丢弃而不是截断进地址', () => {
    const long = '书'.repeat(81)
    const { values, invalid } = readUrlState(
      { view: 'list', source: long, keyword: long },
      MATERIALS_QUERY_SPECS,
    )
    assert.equal(values.view, '')
    assert.equal(values.source, '')
    assert.equal(values.keyword, '')
    assert.deepEqual(invalid.map((i) => i.key).sort(), ['keyword', 'source', 'view'])
  })

  it('恰好 80 字的书名仍然可用（边界不该误杀）', () => {
    const exact = '书'.repeat(80)
    assert.equal(readUrlState({ source: exact }, MATERIALS_QUERY_SPECS).values.source, exact)
  })
})

describe('SCOPED_REVIEW_SPECS：移动端作用域参数与 PC 审核列表同口径', () => {
  it('UUID 风格的 workflow_id 可用，channel_name 原样带上', () => {
    const wf = '3c5b7f96-7ac3-46ec-b4db-9a5908bde9d3'
    const { values, invalid } = readUrlState(
      { workflow_id: wf, channel_name: '科技前沿' },
      SCOPED_REVIEW_SPECS,
    )
    assert.deepEqual(values, { workflow_id: wf, channel_name: '科技前沿' })
    assert.deepEqual(invalid, [])
  })

  it('格式不符/超长/空白的 workflow_id 不让页面进入作用域模式', () => {
    for (const raw of ['abc def', '#12', 'x'.repeat(65), '   ', '/etc/passwd']) {
      const { values, invalid } = readUrlState({ workflow_id: raw }, SCOPED_REVIEW_SPECS)
      assert.equal(values.workflow_id, '', `workflow_id=${raw} 不该被当成作用域`)
      if (raw.trim()) assert.equal(invalid[0].key, 'workflow_id')
    }
  })

  it('重复 workflow_id 取第一个并留痕（地址被手改时不静默扩大范围）', () => {
    const { values, invalid } = readUrlState(
      { workflow_id: ['wf-1', 'wf-2'] },
      SCOPED_REVIEW_SPECS,
    )
    assert.equal(values.workflow_id, 'wf-1')
    assert.equal(invalid[0].key, 'workflow_id')
  })

  it('channel_name 只是展示文本，超长丢弃不阻断作用域过滤', () => {
    const { values } = readUrlState(
      { workflow_id: 'wf-1', channel_name: '名'.repeat(41) },
      SCOPED_REVIEW_SPECS,
    )
    assert.equal(values.workflow_id, 'wf-1')
    assert.equal(values.channel_name, '')
  })
})

describe('日期筛选参数（T02804）：格式与日历真实性都校验', () => {
  const DATE_SPECS = {
    date_from: { default: '', validator: validateIsoDate },
    date_to: { default: '', validator: validateIsoDate },
  }

  it('合法的 YYYY-MM-DD 原样保留', () => {
    const { values, invalid } = readUrlState(
      { date_from: '2026-10-20', date_to: '2026-10-21' },
      DATE_SPECS,
    )
    assert.equal(values.date_from, '2026-10-20')
    assert.equal(values.date_to, '2026-10-21')
    assert.deepEqual(invalid, [])
  })

  it('非 YYYY-MM-DD 回落默认值并说明格式要求', () => {
    for (const bad of ['2026/10/20', '2026-1-1', '20261020', 'abc']) {
      const { values, invalid } = readUrlState({ date_from: bad }, DATE_SPECS)
      assert.equal(values.date_from, '', `${bad} 应被丢弃，而不是原样发给后端`)
      assert.equal(invalid[0].key, 'date_from')
      assert.match(invalid[0].reason, /YYYY-MM-DD/)
    }
  })

  it('正则能过但日历上不存在的日期一样回落', () => {
    // 只做 pattern 校验时这三个值都能通过，然后换来一次 400 或静默空列表
    for (const bad of ['2026-02-30', '2026-13-01', '2026-04-31']) {
      const { values, invalid } = readUrlState({ date_to: bad }, DATE_SPECS)
      assert.equal(values.date_to, '', `${bad} 不是真实日期`)
      assert.match(invalid[0].reason, /不是有效日期/)
    }
  })

  it('闰年边界：2028-02-29 合法、2027-02-29 非法', () => {
    assert.equal(validateIsoDate('2028-02-29'), true)
    assert.match(String(validateIsoDate('2027-02-29')), /不是有效日期/)
  })

  it('区间反了给出人话；相等或只填一端时通过', () => {
    assert.equal(validateDateRange('2026-10-21', '2026-10-20'), '开始日期不能晚于结束日期')
    assert.equal(validateDateRange('2026-10-20', '2026-10-20'), true)
    assert.equal(validateDateRange('', '2026-10-20'), true)
    assert.equal(validateDateRange('2026-10-20', ''), true)
    assert.match(String(validateDateRange('2026-02-30', '2026-03-01')), /^开始日期不是有效日期/)
  })

  it('写回 URL：默认空值省略，设置值保留', () => {
    const query = writeUrlQuery({}, DATE_SPECS, { date_from: '2026-10-20', date_to: '' })
    assert.deepEqual(query, { date_from: '2026-10-20' })
  })
})

describe('接线：两个页面不再手写 Number/String(route.query)', () => {
  const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
  const read = (rel) => readFileSync(path.join(ROOT, rel), 'utf8')

  it('素材库：channelId/materialId/source/keyword/view 全部走 MATERIALS_QUERY_SPECS', () => {
    const src = read('src/views/channel/MaterialLibrary.vue')
    assert.doesNotMatch(src, /Number\(route\.query\./, '又出现了手写 Number(route.query.*)')
    assert.doesNotMatch(src, /String\(route\.query\./, '又出现了手写 String(route.query.*)')
    assert.match(src, /readUrlState\(route\.query, MATERIALS_QUERY_SPECS\)/)
    // 存在性：频道列表里找不到的 channelId 不能直接进筛选
    assert.match(src, /\.some\(\(c\) => c\.id === deepLink\.values\.channelId\)/)
    assert.match(src, /地址中的筛选参数无效/)
  })

  it('移动审核：作用域参数走 SCOPED_REVIEW_SPECS，非法值不参与过滤', () => {
    const src = read('src/views/mobile/ReviewList.vue')
    assert.doesNotMatch(src, /route\.query\.workflow_id/, '又直接读了 workflow_id')
    assert.doesNotMatch(src, /route\.query\.channel_name/, '又直接读了 channel_name')
    assert.match(src, /readUrlState\(route\.query, SCOPED_REVIEW_SPECS\)/)
    assert.match(src, /params\.workflow_id = scopedValues\.value\.workflow_id/)
    assert.match(src, /地址中的筛选参数无效/)
  })
})
