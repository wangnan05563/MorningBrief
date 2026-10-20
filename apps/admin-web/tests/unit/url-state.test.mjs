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

import {
  crossEndTarget,
  isMobilePath,
  isQueryDirty,
  readUrlState,
  sanitizeRedirect,
  stripModeQuery,
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
