/**
 * 累计口径文案单元测试（FR-UX-503 / T02508）
 *
 * 为什么用 node --test 而不是只靠 Playwright：
 * 两个页面（LLM 指标 / RSS 健康度）共用 utils/scope.js 生成同一句口径，
 * 「后端没给起点时绝不编一个日期」这条规则只有在这里才能被直接断言——
 * E2E 里它藏在 computed 里，改动 utils 时不会立刻暴露。
 * 运行：cd apps/admin-web && node --test tests/unit/scope.test.mjs
 * （Node 24 在本机不接受 `node --test tests/unit` 这种目录形式，会被当模块加载）
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import dayjs from 'dayjs'

import { cumulativeScopeText, parseStartedAt, uptimeText } from '../../src/utils/scope.js'

describe('parseStartedAt：只认后端给的起点', () => {
  it('解析本地 naive 的 YYYY-MM-DDTHH:mm:ss', () => {
    const d = parseStartedAt('2026-07-18T09:30:00')
    assert.ok(d)
    assert.equal(d.format('YYYY-MM-DD HH:mm:ss'), '2026-07-18 09:30:00')
  })

  it('null / 空串 / 非法字符串一律给 null', () => {
    assert.equal(parseStartedAt(null), null)
    assert.equal(parseStartedAt(''), null)
    assert.equal(parseStartedAt('不是时间'), null)
  })
})

describe('cumulativeScopeText：AC 要求的三要素都在', () => {
  it('有起点时给出时间、PID 与「重启后清零」', () => {
    const text = cumulativeScopeText({
      startedAt: '2026-07-18T09:30:00',
      pid: 4321,
      subject: '本页全部计数与派生率',
    })
    assert.match(text, /累计自 2026-07-18 09:30:00/)
    assert.match(text, /PID 4321/)
    assert.match(text, /重启后清零/)
    assert.ok(text.startsWith('本页全部计数与派生率'), '主语必须写在最前面，一眼知道这句话说的是谁')
  })

  it('没有 PID 时不留下空括号', () => {
    const text = cumulativeScopeText({ startedAt: '2026-07-18T09:30:00', subject: '指标' })
    assert.ok(!text.includes('（）'), text)
  })

  it('后端缺 started_at 时如实说明，绝不拿当前时间冒充起点', () => {
    const text = cumulativeScopeText({ startedAt: null, pid: 4321, subject: '各源巡检状态' })
    assert.match(text, /后端未返回累计起点时间/)
    assert.ok(!/\d{4}-\d{2}-\d{2}/.test(text), `缺起点时不该出现任何日期：${text}`)
  })
})

describe('uptimeText：样本攒了多久', () => {
  const started = '2026-07-18T09:30:00'

  it('不足 1 小时只报分钟', () => {
    assert.equal(uptimeText({ startedAt: started, now: dayjs('2026-07-18T09:55:00') }), '25 分钟')
    // 时间戳倒挂（后端时钟异常）时不给负数
    assert.equal(uptimeText({ startedAt: started, now: dayjs('2026-07-18T09:00:00') }), '0 分钟')
  })

  it('满小时按「时+分」，跨天按「天+小时」', () => {
    assert.equal(uptimeText({ startedAt: started, now: dayjs('2026-07-18T13:45:00') }), '4 小时 15 分钟')
    assert.equal(uptimeText({ startedAt: started, now: dayjs('2026-07-21T11:30:00') }), '3 天 2 小时')
  })

  it('缺起点或缺当前时刻返回空串（调用方据此不渲染）', () => {
    assert.equal(uptimeText({ startedAt: null, now: dayjs() }), '')
    assert.equal(uptimeText({ startedAt: started }), '')
  })
})
