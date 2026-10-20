/**
 * 知识库问答调用（FR-UX-701 / T02515）
 *
 * 为什么要从 KnowledgeQA.vue 里抽出来单独成模块：
 * 1. 「超时」「停止生成」「可重试」三件事原本挤在页面的 try/catch 里，只有把请求发起
 *    与结果分类抽成纯函数，才能用 node --test 逐条断言（真浏览器里等 130s 不现实，
 *    而把超时值调小又会验的是另一套代码）。测试通过 `client` 注入一个带自定义
 *    adapter 的 axios 实例，走的仍是 axios 真实的 timeout / signal 通路。
 * 2. api/index.js 的实例超时是 15s（给普通 CRUD 用的），问答必须显式覆盖它——
 *    原先 /ai/chat 沿用 15s，模型还没答完浏览器就先报错，而后端会继续跑到 30s，
 *    用户看到的是「timeout of 15000ms exceeded」这种没有重试入口的网络错误。
 *
 * 超时口径（与后端成对，改任何一边都要跑 tests/unit/ai-chat.test.mjs）：
 *   后端 LLM_CHAT_TIMEOUT_SEC=120s 先到点 → 返回 success=false/timeout=true 的可读提示；
 *   前端 AI_CHAT_TIMEOUT_MS=130s 只是兜底闸门，正常情况下不该由它先响。
 *
 * 「停止生成」的边界（如实写明，不假装能取消上游）：signal.abort() 只中止浏览器这条
 * 请求；非流式调用无法从客户端取消已在跑的模型任务，服务端仍会跑完并计入用量。
 * 真正的「停止即止」要等 SSE 流式（FR-UX-702）。
 *
 * 为什么 client 必传而不是默认取 src/api：src/api/index.js 会连带 import element-plus，
 * 在 node 里加载即报错（它按浏览器环境初始化）。传参让「超时/中止/分类」这三件事
 * 能被 node --test 用真实 axios 实例逐条断言，生产调用方（KnowledgeQA.vue）传全站那一个实例。
 */
import axios from 'axios'

/** 问答显式超时：ACC-UX-701 要求 ≥130s，且必须大于后端问答超时（120s） */
export const AI_CHAT_TIMEOUT_MS = 130000

function _isTimeoutError(err) {
  // axios 超时：code=ECONNABORTED 且 message 形如 "timeout of 130000ms exceeded"；
  // 取消也走 ECONNABORTED 家族，所以必须先用 isCancel 排除，否则点「停止生成」会被误判成超时
  if (axios.isCancel(err)) return false
  if (err?.code === 'ECONNABORTED' && /timeout/i.test(err?.message || '')) return true
  if (err?.code === 'ETIMEDOUT' || err?.code === 'ECONNREFUSED') return false
  return /timeout/i.test(err?.message || '') && !err?.response
}

/**
 * 发起一轮问答。永不抛异常：所有失败都归成 {ok:false, kind, message}，
 * 让调用方按 kind 决定「留输入 / 给重试按钮 / 只提示」，而不是在 UI 里正则猜错误文案。
 *
 * @param {object}   opts
 * @param {string}   opts.model        当前选中模型
 * @param {Array}    opts.messages     OpenAI 格式对话历史（含本轮提问）
 * @param {AbortSignal} [opts.signal]  「停止生成」用
 * @param {number}   [opts.timeoutMs]  覆盖超时（仅供测试注入小值）
 * @param {object}   opts.client       axios 实例（生产传 src/api 的单例，测试传带自定义 adapter 的实例）
 * @returns {Promise<{ok:boolean, kind:string, message?:string, data?:object}>}
 */
export async function callAiChat({
  model,
  messages,
  signal,
  timeoutMs = AI_CHAT_TIMEOUT_MS,
  client,
}) {
  if (!client || typeof client.post !== 'function') {
    // 不静默兜底成全局实例：调用方漏传时宁可立刻炸出来，也不要它"看起来能跑"
    throw new TypeError('callAiChat 需要 client（api 实例）')
  }
  let data
  try {
    // silent: 由本模块统一分类后再决定提示，避免拦截器先弹一条 "timeout of … exceeded"
    // 这种对用户没有行动信息的错误（且与页面自己的提示重复两条 toast）
    data = await client.post('/ai/chat', { model, messages }, { timeout: timeoutMs, signal, silent: true })
  } catch (err) {
    if (axios.isCancel(err)) return { ok: false, kind: 'aborted' }
    if (_isTimeoutError(err)) {
      // 秒数不做整除：测试会注入 150ms 这类小值，Math.round(150/1000)=0 会写出
      // 「超时（>0 秒）」这种没人信的话
      const sec = timeoutMs >= 1000 ? String(Math.round(timeoutMs / 1000)) : (timeoutMs / 1000).toFixed(1)
      return {
        ok: false,
        kind: 'timeout',
        message: `等待模型响应超时（>${sec} 秒），可以重试或把问题问得更具体`,
      }
    }
    // 业务/网络错误：拦截器已把 {code,message,data} 解包，非 0 code 时 err.message 就是后端文案
    return { ok: false, kind: 'error', message: err?.message || '问答请求失败' }
  }

  // data 为 null/undefined：响应被拦截器解包后确实可能是 null（后端 success 字段缺失）
  if (!data) return { ok: false, kind: 'error', message: '后端未返回内容，请重试' }
  if (data.success === false) {
    // 后端超时是「同一件事的另一种到点方式」，统一归到 timeout 让 UI 只认一个分支
    const kind = data.timeout === true ? 'timeout' : 'error'
    return { ok: false, kind, message: data.message || '问答失败', data }
  }
  return { ok: true, kind: 'ok', data }
}
