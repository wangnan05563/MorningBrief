/**
 * 审计摘要拍平单元测试（T03670）
 *
 * 缺陷形状：AuditTrail.vue 的 summarize() 用模板串取 `${detail[k]}`，k 命中
 * result/before/after 这类结构化值时 JS 默认转成 `[object Object]`，
 * 生产库快照上值班速读的那一行整条失效（`result=[object Object],[object Object]`）。
 *
 * 为什么用 node:test 而不是只靠 e2e：e2e 断言的是"这一屏看不到那串字样"，
 * 而四类输入（嵌套对象 / 数组 / 深层嵌套 / 大对象）的组合边界只有纯函数用例跑得干净，
 * 也才能在修复被回退时立刻转红（见本文件末尾的接线守卫）。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

import { summarizeAuditDetail } from '../../src/utils/format.js'

const NOISE = '[object Object]'

/** 验收点名的四类输入 + 现场形态，统一用来扫「不得出现 [object Object]」 */
const SHAPE_CASES = [
  ['嵌套对象', { before: { nickname: 'old', role: 'admin' }, after: { nickname: 'new', role: 'admin' } }],
  ['对象数组（现场 batch_approve 的 result）', { review_id: 'wf-20260820-0008', result: [{ ok: true, episode: 12 }, { ok: true, episode: 13 }] }],
  ['标量数组', { result: { disabled: true, sessions: [1, 2, 3] } }],
  ['超长数组', { items: Array.from({ length: 40 }, (_, i) => ({ id: i })) }],
  ['深层嵌套', { a: { b: { c: { d: { e: { f: 1 } } } } } }],
  ['大对象（键数远超展示上限）', Object.fromEntries(Array.from({ length: 60 }, (_, i) => [`k${i}`, i]))],
  ['空对象与空数组', { before: {}, after: [] }],
  ['null 与布尔', { deleted: null, ok: false, days: 0 }],
  ['字符串内含花括号', { reason: '手滑输入了 { 和 }' }],
]

describe('summarizeAuditDetail 拍平结构化值（T03670）', () => {
  it('四类以上结构化输入一律不出现 [object Object]', () => {
    for (const [label, detail] of SHAPE_CASES) {
      const out = summarizeAuditDetail(detail)
      assert.ok(!out.includes(NOISE), `${label} 仍渲染成 [object Object]：${out}`)
    }
  })

  it('嵌套对象深一层取标量，形如 before={nickname:old,…}', () => {
    const out = summarizeAuditDetail({ before: { nickname: 'old', role: 'admin' } })
    assert.equal(out, 'before={nickname:old,role:admin}')
  })

  it('数组元素是对象时给出可读条目并有 remainder', () => {
    const out = summarizeAuditDetail({
      result: Array.from({ length: 5 }, (_, i) => ({ ok: true, id: i })),
    })
    assert.match(out, /^result=\[\{ok:true,id:0\},\{ok:true,id:1\},\{ok:true,id:2\},…\+2项\]$/)
  })

  it('嵌套过深转省略形态，不再无限展开', () => {
    const out = summarizeAuditDetail({ a: { b: { c: { d: { e: 1 } } } } })
    assert.equal(out, 'a={b:{c:{d:…}}}')
  })

  it('循环引用不炸栈也不漏 [object Object]', () => {
    const node = { name: 'root' }
    node.self = node
    const out = summarizeAuditDetail({ result: node })
    assert.ok(!out.includes(NOISE))
    assert.ok(out.length <= 200)
  })

  it('大对象受键数与整行字符双重上限', () => {
    const big = Object.fromEntries(Array.from({ length: 200 }, (_, i) => [`field_${i}`, 'x'.repeat(120)]))
    const out = summarizeAuditDetail(big)
    // 只展示前 3 个键，且拼出来的行仍要收口到字符上限
    assert.ok(!out.includes('field_3'), `第 4 个键不该出现：${out}`)
    assert.ok(out.length <= 200, `未收口到字符上限：${out.length}`)
    assert.ok(out.endsWith('…'), `超长应补省略号：${out.slice(-12)}`)
    assert.match(out, /^field_0=xxx/)
  })

  it('键数超过展示上限时点名还有多少没显示', () => {
    const out = summarizeAuditDetail({ items: Array.from({ length: 9 }, (_, i) => ({ id: i })) })
    assert.ok(out.includes('…+6项'), out)
  })

  it('标量口径保持原行为（T02909 的 days=7 · count=3 不变）', () => {
    assert.equal(summarizeAuditDetail({ days: 7, count: 3 }), 'days=7 · count=3')
    assert.equal(summarizeAuditDetail('纯字符串'), '纯字符串')
    assert.equal(summarizeAuditDetail(undefined), '')
    assert.equal(summarizeAuditDetail({}), '')
  })

  it('优先展示语义键，缺失才回落前 3 个键', () => {
    const out = summarizeAuditDetail({ zzz: 1, reason: '误删书单后回滚', aaa: 2 })
    assert.equal(out, 'reason=误删书单后回滚')
    assert.equal(summarizeAuditDetail({ zzz: 1, aaa: 2, bbb: 3, ccc: 4 }), 'zzz=1 · aaa=2 · bbb=3')
  })

  it('后端脱敏值原样呈现，前端不二次加工（T02909 口径）', () => {
    const out = summarizeAuditDetail({ secret_key: '***', access_token: '***' })
    assert.equal(out, 'secret_key=*** · access_token=***')
  })
})

describe('接线守卫：摘要逻辑只有一份（T03670）', () => {
  const source = readFileSync(
    fileURLToPath(new URL('../../src/components/AuditTrail.vue', import.meta.url)),
    'utf8',
  )
  // 只看 <script> 里的代码：注释里允许出现"曾经怎么写"的字样做说明
  const scriptBlock = source.split('<script')[1]?.split('</script>')[0] ?? ''

  it('组件不再自带本地 summarize（防回归到模板串）', () => {
    assert.ok(scriptBlock.includes('function'), '没取到 <script> 段，守卫等于失效')
    assert.ok(!/function summarize\(/.test(scriptBlock), 'AuditTrail.vue 里又出现了本地 summarize')
    assert.ok(
      !/\$\{detail\[/.test(scriptBlock),
      '模板串直取结构化值的写法会重新产生 [object Object]',
    )
  })

  it('组件确实改用公共拍平函数（不是"改了但没接上"）', () => {
    assert.match(scriptBlock, /import \{ summarizeAuditDetail \} from '..\/utils\/format'/)
    assert.match(source, /\{\{ summarizeAuditDetail\(row\.detail\) \}\}/)
  })

  it('长串兜底样式在位：字符上限之外还要能换行', () => {
    assert.match(source, /overflow-wrap: anywhere/)
  })
})

