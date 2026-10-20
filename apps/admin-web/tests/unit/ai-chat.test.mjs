/**
 * 知识库问答超时与停止（FR-UX-701 / T02515）单元测试
 *
 * 为什么用真 axios + 真 hang 住的本地 http server，而不是 mock 一个假错误对象：
 * 「超时」和「中止」这两件事的判定依据（ECONNABORTED / CanceledError）是 axios 适配器
 * 在运行时产出的，自定义 adapter 根本不会触发它们（timeout 与 signal 都在 xhr/http 适配器
 * 内部实现）。用 mock 只能证明「我写的分支匹配我编的错误」，换 axios 版本或错误形态就失真。
 *
 * 同时这里做跨端断言：前端 130s 与后端 120s 是一对契约，分处两种语言、两个目录，
 * 没有任何编译期关系。以前一类缺陷（问答沿用 15s 全局超时）正是因为没人把这对关系
 * 写成断言，改动一边时另一边静默失配。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/ai-chat.test.mjs
 */
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFileSync, readdirSync } from 'node:fs'
import { after, before, describe, it } from 'node:test'

import axios from 'axios'

import { AI_CHAT_TIMEOUT_MS, callAiChat } from '../../src/api/aiChat.js'

/** 读仓库内文件（tests/unit → repo root 上溯 4 层） */
const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf8')

/**
 * 起一个可控的假后端：
 * - mode='hang'   永不响应（用来触发真实超时与真实中止）
 * - mode='reply'  按 payload 立刻返回 {code:0,message:'',data:payload}
 * 顺带记录「请求是否真的在网络上断了」（req 的 aborted/close 事件），
 * 这样「停止生成」不是只在 UI 上把 loading 关掉，而是确实中止了请求。
 */
function createFakeBackend(mode, payload) {
  const seen = { requests: 0, aborted: 0 }
  const server = createServer((req, res) => {
    seen.requests += 1
    req.on('aborted', () => { seen.aborted += 1 })
    res.on('close', () => { if (!res.writableEnded) seen.aborted += 1 })
    if (mode === 'hang') return // 故意不响应
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ code: 0, message: '', data: payload }))
  })
  return { server, seen }
}

/** 造一个与 src/api 同解包口径的实例（真实实例带 {code,message,data} 解包拦截器） */
function makeClient(baseUrl) {
  const client = axios.create({ baseURL: baseUrl })
  client.interceptors.response.use((r) => r.data.data)
  return client
}

describe('AI_CHAT_TIMEOUT_MS 契约常量', () => {
  it('问答显式超时 ≥130s（ACC-UX-701），且不是沿用 api/index.js 的 15s 全局值', () => {
    assert.ok(AI_CHAT_TIMEOUT_MS >= 130000, `期望 ≥130000，实际 ${AI_CHAT_TIMEOUT_MS}`)
    const globalTimeout = Number(repoFile('apps/admin-web/src/api/index.js').match(/timeout:\s*(\d+)/)[1])
    assert.ok(AI_CHAT_TIMEOUT_MS > globalTimeout, '问答超时必须显式大于全局 CRUD 超时')
  })

  it('后端问答超时严格早于前端，且不短于 60s（长回答不中断）', () => {
    const cfg = repoFile('backend/app/config.py')
    const backSec = Number(cfg.match(/LLM_CHAT_TIMEOUT_SEC:\s*int\s*=\s*(\d+)/)[1])
    assert.ok(backSec * 1000 < AI_CHAT_TIMEOUT_MS, `后端 ${backSec}s 必须 < 前端 ${AI_CHAT_TIMEOUT_MS / 1000}s，否则前端先到点`)
    assert.ok(backSec >= 60, `后端 ${backSec}s 撑不住「长回答（>60s）不中断」`)
    // 批量任务超时仍是 30s：两个值必须是两条独立通道，不能图省事合成一个
    const batchSec = Number(cfg.match(/LLM_TIMEOUT_SEC:\s*int\s*=\s*(\d+)/)[1])
    assert.ok(batchSec < backSec, '问答超时不该复用批量任务的 LLM_TIMEOUT_SEC')
    assert.match(repoFile('backend/.env.example'), /LLM_CHAT_TIMEOUT_SEC=120/)
  })

  it('后端配置三通路齐（读返显 / 写映射 / 热更新登记），漏一处就是 T01729 那种静默丢键', () => {
    const svc = repoFile('backend/app/services/ai_config_service.py')
    const router = repoFile('backend/app/routers/admin/ai_config.py')
    assert.match(svc, /"llm_chat_timeout_sec":\s*"LLM_CHAT_TIMEOUT_SEC"/, 'CONFIG_KEY_MAP 缺登记 → 热更新时被跳过')
    assert.match(svc, /"llm_chat_timeout_sec",/, 'INT_KEYS 缺登记 → 存成字符串，float() 当场炸')
    assert.match(svc, /result\["llm_chat_timeout_sec"\]\s*=\s*str\(config\["chat_timeout_sec"\]\)/, '写路径缺映射 → 管理端改了不生效')
    assert.match(svc, /"chat_timeout_sec":\s*_get_int\(/, '读路径缺返显 → 页面显示默认值而非实际值')
    assert.match(router, /chat_timeout_sec:\s*int\s*=\s*120/, 'PUT body 未声明该字段 → pydantic 丢键')
    // 关掉 SDK 自动重试是在 service 里（真正发请求的地方）
    assert.match(svc, /max_retries=0/, 'SDK 默认重试会把总耗时抬到 3×超时，必须显式关')
    assert.match(svc, /isinstance\(e, \(APITimeoutError, TimeoutError\)\)/, '后端超时没单独归类 → 前端拿不到 timeout 标记')
    // 兜底范围用 isinstance 而非 __module__ 字符串：测试桩异常类的 __module__ 不是 openai，
    // 字符串判定会把真实超时异常当代码 bug 抛出（生产看不出来，用例在自己的夹具里炸）
    assert.match(svc, /if not isinstance\(e, APIError\):\s*\n\s*raise/, '异常兜底范围没按 SDK 层级判定')
  })

  it('管理端把问答超时暴露成可热调字段，且上限不越过前端 130s', () => {
    const view = repoFile('apps/admin-web/src/views/ai/AIConfig.vue')
    assert.match(view, /v-model="llmForm\.chat_timeout_sec"\s+:min="(\d+)"\s+:max="(\d+)"/, '问答超时字段缺失')
    const max = Number(view.match(/v-model="llmForm\.chat_timeout_sec"\s+:min="\d+"\s+:max="(\d+)"/)[1])
    assert.ok(max * 1000 < AI_CHAT_TIMEOUT_MS, `表单上限 ${max}s 不允许越过前端 ${AI_CHAT_TIMEOUT_MS / 1000}s 兜底`)
    assert.match(view, /chat_timeout_sec:\s*120,/, 'llmForm 默认值缺失 → PUT 时该键不出现')
  })
})

describe('callAiChat：真超时 / 真中止 / 结果分类', () => {
  let baseUrl = ''
  let fake = null

  before(async () => {
    fake = createFakeBackend('hang')
    await new Promise((r) => fake.server.listen(0, '127.0.0.1', r))
    baseUrl = `http://127.0.0.1:${fake.server.address().port}`
  })
  after(() => new Promise((r) => fake.server.close(r)))

  it('请求会带着显式 timeout 与 silent 出去（否则又落回 15s 全局值 + 拦截器抢弹错误）', async () => {
    const configs = []
    const client = { post: async (url, body, config) => { configs.push({ url, body, config }); return { success: true, reply: 'x' } } }
    const res = await callAiChat({ client, model: 'm', messages: [{ role: 'user', content: 'q' }] })
    assert.equal(res.kind, 'ok')
    assert.equal(configs[0].config.timeout, AI_CHAT_TIMEOUT_MS)
    assert.equal(configs[0].config.silent, true)
    assert.equal(configs[0].url, '/ai/chat')
  })

  it('模型迟迟不答 → kind=timeout，提示里带「重试」，而不是抛给 UI 一句 ECONNABORTED', async () => {
    const res = await callAiChat({ client: makeClient(baseUrl), model: 'm', messages: [], timeoutMs: 150 })
    assert.equal(res.ok, false)
    assert.equal(res.kind, 'timeout')
    assert.match(res.message, /超时/)
    assert.match(res.message, /重试/)
    assert.doesNotMatch(res.message, /ECONNABORTED|timeout of/, '不能把 axios 原文案直接甩给用户')
    assert.match(res.message, />0\.1?5? 秒/, '小超时值不该被四舍五入成「>0 秒」')
  })

  it('点「停止生成」→ kind=aborted，且请求真的在网络层断了（不只是 UI 关掉 loading）', async () => {
    const before = fake.seen.requests
    const ctrl = new AbortController()
    const p = callAiChat({ client: makeClient(baseUrl), model: 'm', messages: [], signal: ctrl.signal, timeoutMs: 5000 })
    await new Promise((r) => setTimeout(r, 60))
    ctrl.abort()
    const res = await p
    assert.equal(res.kind, 'aborted')
    assert.ok(fake.seen.requests > before, '请求确实发出去了')
    // 长超时值下被判成 aborted（而不是 timeout）——证明 abort 先于超时到达分类逻辑
    assert.ok(fake.seen.aborted >= 1, '服务端侧没看到连接中止，说明 signal 没真的透传')
  })

  it('中止不会被误判成超时（用户明明点的是停止）', async () => {
    const ctrl = new AbortController()
    ctrl.abort() // 立即中止：如果分类只看 ECONNABORTED 家族，这里会被错报成「超时可重试」
    const res = await callAiChat({ client: makeClient(baseUrl), model: 'm', messages: [], signal: ctrl.signal, timeoutMs: 5000 })
    assert.equal(res.kind, 'aborted')
  })

  it('漏传 client 直接抛错，不悄悄用某个默认实例', async () => {
    await assert.rejects(() => callAiChat({ model: 'm', messages: [] }), TypeError)
  })
})

describe('callAiChat：后端业务结果的归类', () => {
  const withBackend = async (payload, fn) => {
    const fake = createFakeBackend('reply', payload)
    await new Promise((r) => fake.server.listen(0, '127.0.0.1', r))
    try {
      return await fn(makeClient(`http://127.0.0.1:${fake.server.address().port}`))
    } finally {
      await new Promise((r) => fake.server.close(r))
    }
  }

  it('success=true 走 ok 并把回复带回来', () =>
    withBackend({ success: true, reply: '今日三条新闻' }, async (client) => {
      const res = await callAiChat({ client, model: 'm', messages: [] })
      assert.equal(res.kind, 'ok')
      assert.equal(res.data.reply, '今日三条新闻')
    }))

  it('后端 timeout=true 归成 timeout（与前端超时同一个 UI 分支）', () =>
    withBackend({ success: false, timeout: true, retryable: true, message: '模型响应超时（>120 秒），可以重试' }, async (client) => {
      const res = await callAiChat({ client, model: 'm', messages: [] })
      assert.equal(res.kind, 'timeout')
      assert.match(res.message, /120 秒/)
    }))

  it('普通业务失败归成 error，用后端原文案', () =>
    withBackend({ success: false, timeout: false, message: 'API Key 未配置，请先在「LLM 大模型」中填写并保存' }, async (client) => {
      const res = await callAiChat({ client, model: 'm', messages: [] })
      assert.equal(res.kind, 'error')
      assert.match(res.message, /API Key 未配置/)
    }))
})

describe('KnowledgeQA.vue：停止生成与不留 loading', () => {
  const src = () => repoFile('apps/admin-web/src/views/ai/KnowledgeQA.vue')

  it('问答必须走 aiChat 模块，不再直接用 api.post（那会退回 15s 全局超时）', () => {
    assert.doesNotMatch(src(), /api\.post\(\s*['"]\/ai\/chat/, '页面里又直连 /ai/chat 了：显式超时与中止都丢了')
    assert.match(src(), /from '\.\.\/\.\.\/api\/aiChat'/)
    assert.match(src(), /client:\s*api/, 'callAiChat 没传 api 实例')
  })

  it('有「停止生成」入口且真的 abort 当前请求', () => {
    assert.match(src(), /inline-text="停止生成"/)
    assert.match(src(), /@click="stopGenerating"/)
    assert.match(src(), /chatAbort\.abort\(\)/)
    assert.match(src(), /new AbortController\(\)/)
  })

  it('replying 在 finally 里收口（切走 tab 再回来不能还转圈）', () => {
    const body = src().match(/async function runChat[\s\S]*?\n\}/)[0]
    assert.match(body, /finally\s*\{[\s\S]*?replying\.value\s*=\s*false/)
    assert.match(body, /finally\s*\{[\s\S]*?chatAbort\s*=\s*null/)
  })

  it('超时气泡给重试入口，普通失败不给', () => {
    const s = src()
    // 只有一处 retryable:true，且它就在 timeout 分支里：普通失败（如 API Key 未配置）
    // 给重试按钮等于引导用户对同一个配置错误反复点击
    assert.equal((s.match(/retryable: true/g) || []).length, 1)
    // 切片必须以 timeout 分支为起点：notifyErrorOnce 在文件顶部 import 里也出现，
    // 用不带起始位的 indexOf 会把切片终点算到分支之前（第一版就被这样切空过）
    const start = s.indexOf("res.kind === 'timeout'")
    const timeoutBranch = s.slice(start, s.indexOf('notifyErrorOnce', start))
    assert.match(timeoutBranch, /retryable: true/)
    assert.match(timeoutBranch, /retryHistory: history/)
    assert.match(src(), /async function retryMessage/)
  })

  it('失败气泡不进对话历史（否则超时提示会被当成 AI 的回答喂回模型）', () => {
    assert.match(src(), /filter\(\(m\)\s*=>\s*!m\.failed\)/)
    assert.match(src(), /stopped:\s*true|failed:\s*true/)
  })

  it('离开页面时中止在途请求', () => {
    const unmount = src().match(/onUnmounted\(\(\)\s*=>\s*\{[\s\S]*?\}\)/)[0]
    assert.match(unmount, /chatAbort/)
    assert.match(unmount, /abort\(\)/)
  })
})

describe('单测清单与 CI 口径一致（防「门禁只存在于 CI glob」）', () => {
  it('npm run test:unit 逐个列出 tests/unit 下所有用例文件', () => {
    const pkg = JSON.parse(repoFile('apps/admin-web/package.json'))
    const cmd = pkg.scripts['test:unit'] || ''
    const files = readdirSync(new URL('../../tests/unit/', import.meta.url))
      .filter((f) => f.endsWith('.test.mjs'))
      .sort()
    for (const f of files) {
      // 漏一个文件 = 本地 npm run test:unit 跑不到它，只有 CI glob 跑得动，
      // 开发者改坏契约后本地一片绿（本次 CI 新增单测步骤就是为了不再靠本机手跑）
      assert.ok(cmd.includes(`tests/unit/${f}`), `test:unit 未包含 ${f}`)
    }
    const ci = repoFile('.github/workflows/ci.yml')
    assert.match(ci, /node --test tests\/unit\/\*\.test\.mjs/, 'CI 未接管理端单测 → 跨端超时契约只在本机生效')
  })
})
