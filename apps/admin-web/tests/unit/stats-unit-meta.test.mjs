/**
 * INT-UX-03：统计页的单位不能再写死在页面里
 *
 * 后端 `meta` 的单位登记表是唯一事实来源（backend/app/services/stats_metrics.py），
 * 数值换算一律走 utils/format.js 的 metricValue/metricText。本文件守两件事：
 *
 * 1. 换算出口本身：`unit=percent`（值已是 0~100，factor=1）与 `unit=ratio`（值 0~1，
 *    factor=100）都必须只乘一次——这两类同名 `_rate` 字段量级相反，写死 "%" 的页面
 *    看不出来，接到同一个格式化器上就会把 47% 显示成 4700%。
 * 2. 接线：LLM 指标页与 RSS 健康页确实把响应里的 `meta` 交给出口，而不是自己拼单位。
 *
 * 登记表本身与实际响应是否带 meta 由 backend/tests/test_int03_stats_unit_metadata.py 断言
 * （那边有真 HTTP 边界），这里不重复编一份 meta 假装是后端下发的。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/stats-unit-meta.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import { metricLabel, metricNumber, metricText } from '../../src/utils/format.js'

const LLM_VIEW = readFileSync(
  new URL('../../src/views/stats/LlmMetrics.vue', import.meta.url),
  'utf8',
)
const RSS_VIEW = readFileSync(
  new URL('../../src/views/stats/RssHealth.vue', import.meta.url),
  'utf8',
)
const CHANNEL_VIEW = readFileSync(
  new URL('../../src/views/stats/ChannelHealth.vue', import.meta.url),
  'utf8',
)
const AUTO_REVIEW_VIEW = readFileSync(
  new URL('../../src/views/system/AutoReviewConfig.vue', import.meta.url),
  'utf8',
)
const MOBILE_USERS_VIEW = readFileSync(
  new URL('../../src/views/mobile/ManageUsers.vue', import.meta.url),
  'utf8',
)

const PERCENT = { label: '触发率', unit: 'percent', display: { unit: '%', factor: 1, precision: 2 } }
const MS = { label: '响应延迟', unit: 'millisecond', display: { unit: 'ms', factor: 1, precision: 0 } }
const FAILS = { label: '连续失败', unit: 'count', display: { unit: '次', factor: 1, precision: 0 } }

describe('INT-UX-03 单位换算只乘一次', () => {
  // ratio（0~1 → ×100）那一半由 tests/unit/format.test.mjs 守着；
  // 这里只补本单新引入的第二种量级：后端已乘过 100 的 percent，换算必须是 1。
  it('percent 类 meta 不再乘任何数（否则 47% 显示成 4700%）', () => {
    assert.equal(metricNumber(50.0, PERCENT), 50)
    assert.equal(metricText(50.0, PERCENT), '50.00%')
    assert.equal(metricText(0.0, PERCENT), '0.00%')
  })

  it('列名与数值文案都由 meta 拼出，页面不再另写一份单位', () => {
    assert.equal(metricLabel(MS), '响应延迟(ms)')
    assert.equal(metricLabel(FAILS), '连续失败(次)')
    assert.equal(metricText(812, MS), '812 ms')
    assert.equal(metricText(3, FAILS), '3 次')
  })
})

describe('INT-UX-03 两个统计页接的是 meta，不是写死单位', () => {
  it('LLM 指标页不再写死 "%"，率卡片按 meta 取单位', () => {
    assert.doesNotMatch(LLM_VIEW, /\{\{\s*r\.value\s*\}\}%/, '页面写死 % 时后端改口径没人发现')
    assert.match(LLM_VIEW, /metricText\(metrics\.value\[key\], meta\[key\]\)/)
    assert.match(LLM_VIEW, /meta: \{\}/)
  })

  it('RSS 健康页延迟列名与数值都取自 meta', () => {
    assert.doesNotMatch(RSS_VIEW, /\{\{\s*row\.latency_ms\s*\}\}\s*ms/, '表头/单元格写死 ms')
    assert.match(RSS_VIEW, /metricText\(row\.latency_ms, meta\.latency_ms\)/)
    assert.match(RSS_VIEW, /meta\.value = data\.meta \|\| \{\}/)
    assert.match(RSS_VIEW, /metricLabel\(meta\.value\.latency_ms\)/)
  })

  it('接口下发的每一条 meta，页面都得真接上', () => {
    // 连续失败列以前只有写死的表头：meta 下发了却没人接，等于没修。
    // 这条按后端登记表的清单逐条核对，以后往清单里加字段不会漏掉接线。
    const registry = readFileSync(
      new URL('../../../../backend/app/services/stats_metrics.py', import.meta.url),
      'utf8',
    )
    const pages = [
      ['RSS_HEALTH_METRICS', RSS_VIEW],
      ['CHANNEL_HEALTH_METRICS', CHANNEL_VIEW],
      ['AUTO_REVIEW_METRICS', AUTO_REVIEW_VIEW],
      ['USER_LISTEN_METRICS', MOBILE_USERS_VIEW],
    ]
    for (const [listName, view] of pages) {
      const listed = registry.match(new RegExp(`${listName} = \\[([\\s\\S]*?)\\]`))?.[1]
      assert.ok(listed, `后端登记表里应能解析出 ${listName}`)
      for (const field of listed.match(/"[a-z_]+"/g).map((s) => s.replaceAll('"', ''))) {
        assert.match(
          view,
          new RegExp(`meta(\\.value)?\\.${field}\\b`),
          `${field} 下发了 meta 但页面没接`,
        )
      }
    }
    assert.doesNotMatch(RSS_VIEW, /label="连续失败"/, '表头写死，meta.consecutive_failures 白下发')
  })

  it('LLM 页把登记表里的每个指标都渲染出来，单位字不再写死', () => {
    const registry = readFileSync(
      new URL('../../../../backend/app/services/stats_metrics.py', import.meta.url),
      'utf8',
    )
    const listed = registry.match(/LLM_METRICS = \[([\s\S]*?)\]/)?.[1]
    assert.ok(listed, '后端登记表里应能解析出 LLM_METRICS')
    const expected = listed.match(/"[a-z_]+"/g).map((s) => s.replaceAll('"', '')).sort()

    // 页面渲染的指标键 = 率卡的 rate('key'…) + 计数卡 legacy 里的键
    const rates = [...LLM_VIEW.matchAll(/rate\('([a-z_]+)'/g)].map((m) => m[1])
    const legacyBlock = LLM_VIEW.match(/const legacy = \{([\s\S]*?)\n  \}/)?.[1]
    assert.ok(legacyBlock, 'LLM 页应保留计数卡字段清单（缺 meta 时的退回文案）')
    const counts = [...legacyBlock.matchAll(/([a-z_]+):/g)].map((m) => m[1])
    assert.deepEqual([...rates, ...counts].sort(), expected, '登记表加了指标但页面没渲染')

    assert.doesNotMatch(LLM_VIEW, /\} 次调用/, '计数单位写死在页面里')
    assert.match(LLM_VIEW, /metricLabel\(meta\[key\]\)/)
    assert.match(LLM_VIEW, /metricValue\(metrics\.value\[key\], meta\[key\]\)/)
  })

  it('频道健康页的单位字取自 meta，不再写死「条」', () => {
    assert.match(CHANNEL_VIEW, /meta\.value\.count\?\.display\?\.unit/)
    assert.match(CHANNEL_VIEW, /\$\{ctx\.parsed\.y\} \$\{countUnit\.value\}/)
    assert.doesNotMatch(CHANNEL_VIEW, /峰值 \{\{ peakOf\(ch\) \}\} 条/, '文案写死单位')
  })

  it('自动审核成功率按 meta 换算，页面不得自己乘 100（T02708）', () => {
    assert.match(AUTO_REVIEW_VIEW, /metricText\(stats\?\.success_rate, meta\.success_rate\)/)
    assert.match(AUTO_REVIEW_VIEW, /meta\.value = res\?\.meta \|\| \{\}/)
    // 页面自带换算/格式化函数一旦回来，meta 就只是装饰
    assert.doesNotMatch(AUTO_REVIEW_VIEW, /formatPercent/)
    assert.doesNotMatch(AUTO_REVIEW_VIEW, /rate\s*\*\s*100/, '页面又自己乘 100')
  })

  it('移动端累计收听的单位取自 meta，不再写死「次 / 秒」（T02708）', () => {
    assert.match(
      MOBILE_USERS_VIEW,
      /metricText\(u\.total_listen_count, meta\.total_listen_count\)/,
    )
    assert.match(
      MOBILE_USERS_VIEW,
      /metricText\(u\.total_listen_duration, meta\.total_listen_duration\)/,
    )
    assert.match(MOBILE_USERS_VIEW, /meta\.value = data\.meta \|\| \{\}/)
    assert.doesNotMatch(MOBILE_USERS_VIEW, /\}\}\s*次\s*·\s*\{\{/, '收听次数单位写死在页面里')
    assert.doesNotMatch(MOBILE_USERS_VIEW, /\}\}\s*秒\s*·\s*注册/, '收听时长单位写死在页面里')
  })
})
