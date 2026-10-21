/**
 * INT-UX-01：业务错误的字段级明细必须活着到达页面
 *
 * 后端在信封的 data 位返回 `{ errors: [{ field, message }] }`，但前端响应拦截器
 * 原先只把 message 包成 Error 就 reject，data 当场丢失——于是运营端知道
 * 「这次保存会用 *** 覆盖凭据」，却不知道是哪个输入框，只能整句 toast。
 *
 * 为什么用真 axios + 真本地 http server（与 ai-chat.test.mjs 同一取向）：
 * 要证的正是**拦截器**这一段行为。直接 `new Error()` 手搓一个带 payload 的对象，
 * 断的就只是「我写的分支匹配我编的错误」，拦截器改回丢 data 也照样绿。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/api-field-error.test.mjs
 */
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { after, before, describe, it } from 'node:test'

const MESSAGE_URL = new URL('../../src/utils/message.js', import.meta.url).href
const STUB_URL = new URL('./helpers/element-plus-stub.mjs', import.meta.url).href
const API_URL = new URL('../../src/api/index.js', import.meta.url).href

// ---- element-plus 替身 + message.js 的 import.meta.env 替换（同 feedback-queue 的接法）----
globalThis.document = {
  hidden: false,
  addEventListener() {},
}
globalThis.__messageEnv__ = { DEV: true }

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'element-plus') {
      return { url: STUB_URL, format: 'module', shortCircuit: true }
    }
    // index.js 写的是 `from '../utils/message'`（Vite 会补 .js，node 的 ESM 解析器不会）
    if (specifier.endsWith('/utils/message')) {
      return { url: MESSAGE_URL, format: 'module', shortCircuit: true }
    }
    return nextResolve(specifier, context)
  },
  load(url, context, nextLoad) {
    if (url === MESSAGE_URL) {
      const source = readFileSync(new URL(url), 'utf8').replace(
        /import\.meta\.env/g,
        'globalThis.__messageEnv__',
      )
      return { url, format: 'module', source, shortCircuit: true }
    }
    return nextLoad(url, context)
  },
})

const { __state, __reset } = await import(STUB_URL)

/** 被拒响应：HTTP 200 + 业务 code 400 + data 带字段级明细（本项目信封约定） */
const REJECT_BODY = {
  code: 400,
  message: '敏感字段 config_value 传入的是脱敏占位值，保存会用 *** 覆盖真实凭据',
  data: {
    errors: [
      { field: 'config_value', message: '字段 config_value 传入的是脱敏占位值，请留空保持原值' },
    ],
  },
}

let server
let baseUrl

before(async () => {
  server = createServer((req, res) => {
    let body = ''
    req.on('data', (chunk) => (body += chunk))
    req.on('end', () => {
      const mode = new URL(req.url, 'http://127.0.0.1').searchParams.get('mode')
      const payload =
        mode === 'legacy'
          ? // 老契约：data 为 null，只有整句中文
            { code: REJECT_BODY.code, message: REJECT_BODY.message, data: null }
          : mode === 'ok'
            ? { code: 0, message: 'success', data: { ok: true } }
            : REJECT_BODY
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify(payload))
    })
    void body
  })
  await new Promise((r) => server.listen(0, '127.0.0.1', r))
  baseUrl = `http://127.0.0.1:${server.address().port}/news/admin/api/v1`
})

after(() => server.close())

describe('INT-UX-01 字段级错误的跨端契约', () => {
  it('业务错误 reject 出的 Error 带得上字段级明细，且聚合中文提示照旧', async () => {
    const mod = await import(API_URL)
    const api = mod.default
    api.defaults.baseURL = baseUrl
    __reset()
    const err = await api
      .patch('/db-admin/tables/ai_config/rows/1?mode=reject', { values: { config_value: '***' } })
      .then(() => null, (e) => e)
    assert.ok(err, '被拒请求必须 reject')
    assert.equal(err.code, 400, '业务码要留在 Error 上')
    assert.equal(err.payload.errors[0].field, 'config_value')
    // 字段级明细是叠加不是替换：拦截器原本那次全局 toast 不能因此消失
    assert.equal(__state.toasts.length, 1, '拦截器只弹一次全局提示')
    assert.match(__state.toasts[0].text, /脱敏占位值/)
  })

  it('老形状错误（data 为 null）不能让拦截器炸掉', async () => {
    // 视图那侧写的是 `e?.payload?.errors` + Array.isArray 兜底；
    // 这里断的是拦截器本身对「没有明细的业务错误」保持原行为——本项目绝大多数 BizError 都是这种。
    const mod = await import(API_URL)
    const api = mod.default
    api.defaults.baseURL = baseUrl
    const err = await api
      .patch('/db-admin/tables/ai_config/rows/1?mode=legacy', { values: { config_value: '***' } })
      .then(() => null, (e) => e)
    assert.equal(err.code, 400)
    assert.equal(err.payload, null)
  })

  it('成功响应仍直接返回 data，不受改动影响', async () => {
    const mod = await import(API_URL)
    const api = mod.default
    api.defaults.baseURL = baseUrl
    __reset()
    const data = await api.patch('/db-admin/tables/ai_config/rows/1?mode=ok', { values: {} })
    assert.deepEqual(data, { ok: true })
  })

  it('字段级明细要落到具体输入框，而不是止步于 Error 对象', () => {
    // 跨端契约的后半段：视图必须消费 payload.errors。它没有编译期关系，
    // 只做后端断言的话，「后端加了字段级错误、前端照旧弹整句」这种失配没人拦得住。
    const vue = readFileSync(
      new URL('../../src/views/maintenance/DatabaseAdmin.vue', import.meta.url),
      'utf8',
    )
    assert.match(vue, /e\?\.payload\?\.errors/, '视图要从 payload 取字段级明细')
    assert.match(vue, /v-if="fieldErrors\[col\.name\]"/, '明细要按列名挂到对应输入框下')
  })

  it('后端契约文本对齐：字段名键为 field、明细数组键为 errors', () => {
    // 前后端各写一份键名，拼错一个字母就是「永远取不到明细」的静默失配
    const svc = readFileSync(
      new URL('../../../../backend/app/services/db_admin_service.py', import.meta.url),
      'utf8',
    )
    assert.match(svc, /data=\{"errors": \[\{"field": col, /, '后端明细形状要与视图读取口径一致')
  })
})
