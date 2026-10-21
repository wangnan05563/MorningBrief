/**
 * 流式/轮询断流可见可恢复 + 长任务超时解耦（FR-UX-702 / T02516）单元测试
 *
 * 三条测试思路，各自对应一类「写了但没生效」的历史缺陷：
 * 1) 超时判定用**真 axios + 真 hang 住的本地 http server / 真 AbortController**产出错误对象，
 *    而不是手搓 `{code:'ECONNABORTED'}`。理由与 ai-chat.test.mjs 相同：ECONNABORTED 与
 *    CanceledError 由适配器在运行时生成，mock 只能证明「分支匹配我编的对象」。
 * 2) SSE 状态机与页面接线走源码静态断言：sse.js 在模块加载期就绑定 document/window/localStorage，
 *    node 里 import 必炸；真实行为（断开→retrying→offline→手动重连）交给 Playwright 实测。
 * 3) NFR-UX-03「新增错误态/重试不得引入额外轮询」是**否定式约束**，最容易在后续迭代被无意破坏
 *    （加个 setInterval 刷新时间就能通过所有正向断言），所以把它写成 grep 门禁。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/feed-health.test.mjs
 */
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFileSync } from 'node:fs'
import { after, before, describe, it } from 'node:test'

import axios from 'axios'

import {
  LONG_TASK_TIMEOUT_MS,
  isRequestTimeout,
  longTaskTimeoutText,
} from '../../src/utils/requestTimeout.js'

const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf8')
const srcFile = (rel) => readFileSync(new URL(`../../src/${rel}`, import.meta.url), 'utf8')

let server
let baseUrl = ''

before(async () => {
  // /hang 永不响应（触发真实超时）；/boom 立刻 500（真实业务错误，绝不能被判成超时）
  server = createServer((req, res) => {
    if (req.url === '/hang') return
    res.writeHead(500, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ code: 500, message: '后端炸了' }))
  })
  await new Promise((r) => server.listen(0, '127.0.0.1', r))
  baseUrl = `http://127.0.0.1:${server.address().port}`
})

after(() => new Promise((r) => server.close(r)))

/** 真实拿一个「等到超时」的 axios 错误 */
async function captureTimeoutError() {
  try {
    await axios.get(`${baseUrl}/hang`, { timeout: 120 })
  } catch (e) {
    return e
  }
  throw new Error('预期超时，实际请求成功返回')
}

/** 真实拿一个「用户主动取消」的 axios 错误 */
async function captureCancelError() {
  const ac = new AbortController()
  const p = axios.get(`${baseUrl}/hang`, { signal: ac.signal, timeout: 5000 })
  ac.abort()
  try {
    await p
  } catch (e) {
    return e
  }
  throw new Error('预期取消，实际请求成功返回')
}

describe('isRequestTimeout 判定口径', () => {
  it('真实 axios 超时可识别（长任务要据此说「后端仍在执行」）', async () => {
    const err = await captureTimeoutError()
    assert.equal(isRequestTimeout(err), true, `超时错误未被识别: ${err.message}`)
  })

  it('用户主动取消不算超时（否则会把「我停了」报成「后端还在跑」）', async () => {
    const err = await captureCancelError()
    assert.ok(axios.isCancel(err), '取消错误应由 axios.isCancel 识别')
    assert.equal(isRequestTimeout(err), false)
  })

  it('HTTP 500 业务错误不算超时', async () => {
    const err = await axios.get(`${baseUrl}/boom`).catch((e) => e)
    assert.equal(err.response?.status, 500)
    assert.equal(isRequestTimeout(err), false)
  })

  it('空值/普通 Error 不误判', () => {
    assert.equal(isRequestTimeout(undefined), false)
    assert.equal(isRequestTimeout(new Error('清理失败')), false)
  })
})

describe('长任务超时与全局 CRUD 超时成对（M62）', () => {
  it('LONG_TASK_TIMEOUT_MS 显式大于 api/index.js 的全局 15s', () => {
    const globalTimeout = Number(repoFile('apps/admin-web/src/api/index.js').match(/timeout:\s*(\d+)/)[1])
    assert.ok(LONG_TASK_TIMEOUT_MS > globalTimeout, `${LONG_TASK_TIMEOUT_MS} 必须大于 ${globalTimeout}`)
    assert.ok(LONG_TASK_TIMEOUT_MS >= 120000, 'VACUUM 上界不该只给几十秒')
  })

  it('维护类三个清理接口都覆盖为长超时，不再共用 15s', () => {
    const src = srcFile('api/maintenance.js')
    const used = (src.match(/timeout: LONG_TASK_TIMEOUT_MS/g) || []).length
    assert.ok(used >= 3, `api/maintenance.js 只有 ${used} 处显式超时，database/logs/cache 三个都要覆盖`)
  })

  it('Maintenance.vue 执行清理用长超时并自持超时文案', () => {
    const view = srcFile('views/maintenance/Maintenance.vue')
    assert.match(view, /timeout: LONG_TASK_TIMEOUT_MS/, '清理请求仍走全局 15s')
    assert.match(view, /isRequestTimeout\(error\)/, '超时分支缺失：用户只会看到「清理失败」并重复提交')
    assert.match(view, /longTaskTimeoutText\(\)/, '超时后必须明确「后端仍在执行」')
  })

  it('超时文案写明「后端仍在执行」且劝阻重复提交', () => {
    const text = longTaskTimeoutText(300000)
    assert.match(text, /后端仍在继续执行/)
    assert.match(text, /请勿重复提交/)
    assert.match(text, /300 秒/)
  })
})

describe('SSE 连接状态对外可见（sse.js）', () => {
  const sse = () => srcFile('utils/sse.js')

  it('导出状态快照、订阅与手动重连三个入口', () => {
    for (const fn of ['export function getStatus()', 'export function subscribeStatus(', 'export function reconnectNow(']) {
      assert.ok(sse().includes(fn), `sse.js 缺少 ${fn}`)
    }
  })

  it('区分「主动暂停」与「故障断流」——页面隐藏不能让 banner 变红', () => {
    assert.ok(sse().includes("_setState('paused'"), 'visibilitychange/blur 断开未标注 paused')
    // retrying / offline 由同一条三元式产出（见下一条断言），两种状态必须都存在
    assert.match(sse(), /'offline' : 'retrying'/, '退避中与实际离线必须有两种状态')
  })

  it('连续失败达阈值升为 offline，但不放弃后台重连', () => {
    assert.match(sse(), /OFFLINE_AFTER_ATTEMPTS\s*=\s*3/)
    assert.match(sse(), /reconnectAttempt >= OFFLINE_AFTER_ATTEMPTS \? 'offline' : 'retrying'/)
    // offline 之后仍要挂 setTimeout 退避：不能一离线就停，服务恢复要能自愈
    assert.match(sse(), /reconnectTimer = setTimeout/)
  })

  it('登录态缺失时按离线报出，不再静默 return', () => {
    // 此前 `if (!role) return` 是断流不可见的一条路径：有订阅者却永不连接，状态停在 idle
    assert.match(sse(), /reason: 'no_auth'/)
  })

  it('收到任何事件都作为「通道活着」的证据并清零退避', () => {
    assert.ok((sse().match(/_markOpen\(\)/g) || []).length >= 4, 'connected/heartbeat/业务事件/onmessage 都该标记 open')
    assert.match(sse(), /reconnectAttempt = 0/)
  })

  it('最后一个订阅者离开后回到 idle，不残留上一页面的离线态', () => {
    assert.match(sse(), /_setState\('idle', \{ force: true \}\)/)
  })
})

describe('useFeedHealth 聚合与页面接线', () => {
  const composable = () => srcFile('composables/useFeedHealth.js')
  const banner = () => srcFile('components/FeedHealthBanner.vue')

  it('只聚合状态，不自带定时器（NFR-UX-03：错误态/重试不得引入额外轮询）', () => {
    for (const src of [composable(), banner()]) {
      assert.ok(!/setInterval\(/.test(src), '健康度层出现了额外定时器，违反 NFR-UX-03')
      assert.ok(!/setTimeout\(/.test(src), '健康度层出现了额外定时器，违反 NFR-UX-03')
    }
  })

  it('失败明细优先取后端业务文案，而不是 axios 的状态码串', () => {
    // 实测触发过的问题：HTTP 500 时 e.message 是 "Request failed with status code 500"，
    // 后端的「服务暂时不可用」在 e.response.data.message 里；silent 模式没有 toast，
    // 这行明细是用户唯一的失败信息来源，只剩状态码等于没说。
    assert.match(composable(), /error\?\.response\?\.data\?\.message \|\| error\?\.message/)
  })

  it('不直接弹 toast：提示去重由 utils/message.js 承担（NFR-UX-02）', () => {
    assert.ok(!/ElMessage/.test(banner()), 'banner 自己弹 toast 会与拦截器重复，且绕过 5 条上限/TTL 去重')
    assert.ok(!/ElMessage/.test(composable()), '同上')
  })

  it('refreshNow 同时重连 SSE 并触发一次手动刷新', () => {
    assert.match(composable(), /reconnectNow\(\)/)
    assert.match(composable(), /await onRefresh\(\)/)
  })

  it('工作流列表与详情页都挂了 banner 并记账刷新成败', () => {
    for (const rel of ['views/workflow/WorkflowList.vue', 'views/workflow/WorkflowDetail.vue']) {
      const v = srcFile(rel)
      assert.ok(v.includes('<FeedHealthBanner'), `${rel} 未接入健康度条`)
      assert.ok(v.includes('useFeedHealth'), `${rel} 未接入 useFeedHealth`)
      assert.match(v, /feed\.markPollSuccess\(\)/, `${rel} 成功侧未记账：失败计数永远清不掉`)
      assert.match(v, /feed\.markPollFailure\(/, `${rel} 失败侧未记账：silent 轮询失败仍然不可见`)
    }
  })

  it('详情页 silent 请求失败不再被 catch 空块吞掉', () => {
    // 修复前：loadDetail 的 catch 是 /* 拦截器已提示 */，而 silent 恰好把提示也抑制了
    const v = srcFile('views/workflow/WorkflowDetail.vue')
    assert.ok(!/catch \{ \/\* 拦截器已提示 \*\/ \} finally \{\n    if \(!silent\) loading\.value = false/.test(v), 'loadDetail 仍是空 catch')
  })

  it('banner 提供「立即重连并刷新」入口与陈旧时间锚点', () => {
    const b = banner()
    assert.match(b, /label="立即重连并刷新"/)
    assert.match(b, /最后成功更新：/)
    assert.match(b, /data-testid="feed-health-banner"/, 'e2e 需要稳定选择器，别依赖文案子串')
  })
})

describe('跨端契约：后端事件流端点与前端 SSE 路径一致', () => {
  it('前端 SSE_ENDPOINT 指向后端真实注册的流式路由', () => {
    const endpoint = srcFile('utils/sse.js').match(/const SSE_ENDPOINT = '([^']+)'/)[1]
    assert.ok(endpoint.includes('/events/stream'), `端点异常: ${endpoint}`)
    const route = repoFile('backend/app/routers/admin/events.py')
    assert.match(route, /@router\.get\(["']\/stream["']/, '后端 /events/stream 路由不存在或被改名')
  })
})
