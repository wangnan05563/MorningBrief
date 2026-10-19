/**
 * 指标格式化单元测试（FR-UX-502 / T02507）
 *
 * 为什么单独用 node --test 跑：趋势曲线画在 canvas 里，Playwright 能断言到的是
 * 图上方那行「纵轴/峰值」摘要，而「换算只乘一次」这件事的真正载体是 metricNumber。
 * 这条测试把它从「走查代码」变成「跑一条命令」：
 *   cd apps/admin-web && node --test tests/unit/format.test.mjs
 * （Node 24 在本机不接受 `node --test tests/unit` 这种目录形式，会被当模块加载）
 *
 * 元数据不手写副本，读 `scripts/gen_stats_metric_meta.py` 从后端表生成的 JSON，
 * 后端改单位、这里立刻跟着红（与 test_stats_metric_meta.py 的漂移守卫同一条链路）。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

import { metricLabel, metricNumber, metricText, metricValue } from '../../src/utils/format.js'

const meta = JSON.parse(
  readFileSync(fileURLToPath(new URL('../helpers/stats-metric-meta.json', import.meta.url)), 'utf8'),
)

describe('metricNumber：换算只发生一次', () => {
  it('ratio 0.65 按 meta 乘成 65（卡片与曲线共用这一个出口）', () => {
    assert.equal(metricNumber(0.65, meta.completion_rate), 65)
    // 曲线数据点必须仍是数字，不能是 '65.0' 这类字符串
    assert.equal(typeof metricNumber(0.65, meta.completion_rate), 'number')
  })

  it('秒 512 按 meta 换算成 8.5 分钟，精度取自 meta', () => {
    assert.equal(metricNumber(512, meta.avg_listen_duration), 8.5)
  })

  it('计数类不换算、取整', () => {
    assert.equal(metricNumber(12345, meta.dau), 12345)
    assert.equal(metricNumber(1500.4, meta.play_count), 1500)
  })

  it('缺 meta / 非数一律 null，不猜单位也不补 0', () => {
    assert.equal(metricNumber(0.65, undefined), null)
    assert.equal(metricNumber(null, meta.dau), null)
    assert.equal(metricNumber('', meta.dau), null)
    assert.equal(metricNumber('abc', meta.dau), null)
  })

  it('把已经百分化的 65 再喂进来会得到 6500——接口必须按原始单位下发', () => {
    // 这条不是「希望发生」，而是把风险量化：后端一旦提前乘 100，展示端会翻倍放大，
    // 数值离谱到肉眼可见（而不是 0.65 这种看着像另一种刻度的小数）
    assert.equal(metricNumber(65, meta.completion_rate), 6500)
  })
})

describe('metricValue / metricText：同一数值的不同呈现', () => {
  it('0 位小数用千分位，带小数用定点', () => {
    assert.equal(metricValue(12345, meta.dau), '12,345')
    assert.equal(metricValue(0.65, meta.completion_rate), '65.0')
  })

  it('% 紧跟数字，其余单位留空格', () => {
    assert.equal(metricText(0.65, meta.completion_rate), '65.0%')
    assert.equal(metricText(512, meta.avg_listen_duration), '8.5 分钟')
    assert.equal(metricText(1500, meta.play_count), '1,500 次')
  })

  it('换算不了时呈现为 -，且不带单位', () => {
    assert.equal(metricText(0.65, undefined), '-')
    assert.equal(metricValue(0.65, undefined), '-')
  })
})

describe('metricLabel：轴/卡片标题带单位', () => {
  it('单位存在时写成「名称(单位)」，缺 meta 时是 -', () => {
    assert.equal(metricLabel(meta.completion_rate), '完播率(%)')
    assert.equal(metricLabel(meta.avg_listen_duration), '平均收听(分钟)')
    assert.equal(metricLabel(undefined), '-')
  })
})
