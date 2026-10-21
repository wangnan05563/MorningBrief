/**
 * INT-UX-05（T02528）：问答超时「与网关实测对齐」的跨端契约
 *
 * 与 ai-chat.test.mjs 的分工：那边锁的是 T02515 已经交付的前端一侧（130s 显式超时、
 * 停止生成、结果分类）；这边锁 T02528 补上的两处对齐——
 * 1. 区间 30–125 现在由后端 PUT /ai/config 强制校验。原来只有 el-input-number 的
 *    :max="125"，直接调接口写 600 会一路热更进 Settings，之后每次问答先到点的是
 *    浏览器 130s，用户又看到没有重试入口的网络错误。
 * 2. 网关侧的未知数已经实测掉（DEC-UX-003）：Tailscale Funnel 对 origin 300s 不返回
 *    任何字节的 GET、200s 的 POST 都原样透传到 200。所以页面上那句
 *    「若网关更早断流，调大本值无效」的假设必须消失，实测结论要留在可追溯的地方。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/ai-chat-timeout-alignment.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { AI_CHAT_TIMEOUT_MS } from '../../src/api/aiChat.js'

const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf8')

const config = () => repoFile('backend/app/config.py')
const router = () => repoFile('backend/app/routers/admin/ai_config.py')
const view = () => repoFile('apps/admin-web/src/views/ai/AIConfig.vue')

/** 从 Settings 源码里取某个 int 常量的默认值 */
const settingDefault = (src, name) => {
  const m = src.match(new RegExp(`\\b${name}:\\s*int\\s*=\\s*(\\d+)`))
  assert.ok(m, `backend/app/config.py 里找不到 ${name} 的默认值`)
  return Number(m[1])
}

describe('问答超时区间只有一个出处', () => {
  it('后端声明 MIN/MAX 两个常量，且默认值落在区间内', () => {
    const src = config()
    const lo = settingDefault(src, 'LLM_CHAT_TIMEOUT_MIN_SEC')
    const hi = settingDefault(src, 'LLM_CHAT_TIMEOUT_MAX_SEC')
    const def = settingDefault(src, 'LLM_CHAT_TIMEOUT_SEC')
    assert.ok(lo < hi, `区间反了：${lo}–${hi}`)
    assert.ok(lo <= def && def <= hi, `默认 ${def} 不在 ${lo}–${hi} 内`)
  })

  it('管理端输入框的 min/max 与后端常量一模一样（数字漂移＝契约裂开）', () => {
    const src = view()
    const m = src.match(/v-model="llmForm\.chat_timeout_sec"\s+:min="(\d+)"\s+:max="(\d+)"/)
    assert.ok(m, '问答超时字段缺失')
    assert.equal(Number(m[1]), settingDefault(config(), 'LLM_CHAT_TIMEOUT_MIN_SEC'), '页面下限与后端不一致')
    assert.equal(Number(m[2]), settingDefault(config(), 'LLM_CHAT_TIMEOUT_MAX_SEC'), '页面上限与后端不一致')
  })

  it('上限严格小于前端 130s：后端必须先到点才给得出「超时可重试」', () => {
    const hi = settingDefault(config(), 'LLM_CHAT_TIMEOUT_MAX_SEC')
    assert.ok(hi * 1000 < AI_CHAT_TIMEOUT_MS, `上限 ${hi}s 不允许越过前端 ${AI_CHAT_TIMEOUT_MS / 1000}s`)
  })
})

describe('越界值由后端拒绝，而不是靠页面拦', () => {
  it('PUT /ai/config 校验问答超时，且边界数字取自那两个常量', () => {
    const src = router()
    assert.match(src, /settings\.LLM_CHAT_TIMEOUT_MIN_SEC/, '下限写成了字面量 → 改 config 不会跟着动')
    assert.match(src, /settings\.LLM_CHAT_TIMEOUT_MAX_SEC/, '上限写成了字面量 → 改 config 不会跟着动')
    assert.match(src, /lo <= body\.llm\.chat_timeout_sec && body\.llm\.chat_timeout_sec <= hi|lo <= body\.llm\.chat_timeout_sec <= hi/)
  })

  it('校验发生在整份配置写入之前（越界时不能留下半份新配置）', () => {
    const src = router()
    const guard = src.indexOf('LLM_CHAT_TIMEOUT_MAX_SEC', src.indexOf('async def save_config'))
    const write = src.indexOf('await svc.update_config', src.indexOf('async def save_config'))
    assert.ok(guard > 0 && write > 0, '找不到校验或找不到写入点，本条断言需要重写')
    assert.ok(guard < write, '先写后校验：越界请求已经把其余字段落库了')
  })

  it('拒绝时的文案带上下限数字与「可重试」缘由，并点明字段名', () => {
    const src = router()
    const msg = src.slice(src.indexOf('async def save_config'), src.indexOf('svc = AIConfigService(db)', src.indexOf('async def save_config')))
    assert.match(msg, /f"问答超时需在 \{lo\}–\{hi\} 秒之间/)
    assert.match(msg, /可重试/)
    assert.match(msg, /fields.*llm\.chat_timeout_sec/s, '不给字段名，前端没法把错误落到那一个输入框')
  })
})

describe('网关实测结论落档（DEC-UX-003）', () => {
  it('PRD 的 DEC-UX-003 已写成实测结论，且原始数字在档（第一版只断言了汇总句，探针 P2 因此存活）', () => {
    const doc = repoFile('docs/需求规格说明书-UX优化.md')
    assert.match(doc, /DEC-UX-003[\s\S]{0,200}已闭/)
    assert.doesNotMatch(doc, /\| DEC-UX-003 \| 公网网关超时 \| 需实测/, '待决策原样留着＝这条口子还没闭')
    // 只写「300 秒不断流」的结论句是可以被凭空编出来的，实测记录要带当时那行原始输出
    assert.match(doc, /time_starttransfer=300\.043s/, 'GET 300s 那一条的原始计时没落档')
    assert.match(doc, /starttransfer=200\.100s/, 'POST 200s 那一条的原始计时没落档')
  })

  it('配置页不再把网关当成未知约束（老文案会让人以为调大超时没用）', () => {
    const src = view()
    assert.doesNotMatch(src, /若网关更早断流，调大本值无效/, '假设句还挂着，实测结论没落进 UI')
    assert.match(src, /data-guide="ai-chat-timeout-tip"/, '提示缺少可定位的 data-guide')
    assert.match(src, /300\s*秒不断流/)
  })

  it('后端注释记录同一组实测数字，避免下一个人重新猜', () => {
    assert.match(config(), /300s[\s\S]{0,60}GET[\s\S]{0,40}200s[\s\S]{0,40}POST/)
  })

  it('断连那一档状态码在前端有专门归类（实测：网关断连回 502 且响应体为空）', () => {
    const src = repoFile('apps/admin-web/src/api/aiChat.js')
    assert.match(src, /status === 502 \|\| status === 503 \|\| status === 504/)
    assert.match(src, /网关到后端的连接中断/)
    assert.match(repoFile('docs/需求规格说明书-UX优化.md'), /HTTP=502 Bad Gateway[\s\S]{0,120}Content-Length: 0/, '断流形态没落档')
  })
})
