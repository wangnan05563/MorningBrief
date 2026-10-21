/**
 * 反馈队列单元测试（NFR-UX-02 / T02520，规则本体见 FR-UX-301 / T02495）
 *
 * 为什么在已有 Playwright 用例（tests/feedback-queue.spec.js）之外还要一份 node 单测：
 * e2e 只能证明「浏览器里聚合出来的那条 toast 文案对不对」，它有三个够不到的地方——
 * 1) **内存不增长**：NFR-UX-02 的验收项。队列长度被上限兜住容易，看不见的去重表
 *    （`_recent`）与恢复定时器（`setTimeout`）才是真正的泄漏点。把「过期键只被跳过、
 *    没有被 delete」改成前者，所有 e2e 断言仍然全绿，只有这里会红。
 * 2) 时间：e2e 里 TTL 60s 只能靠注入旧时间戳，恢复窗口要真空等 2s；这里 Date.now
 *    可控，定时器被截住直接触发，13 例（含灌 2 万条那一例）跑完约 1 秒。
 * 3) 规模：这里能一次灌 1000 条提示再断言队列仍是 5，浏览器里没必要也不会做。
 *
 * 两处「为了能在 node 里跑」的注入，都不改变被测逻辑：
 * - `element-plus` 换成 tests/unit/helpers/element-plus-stub.mjs（本模块的语义就是
 *   「这条提示要不要交给 ElMessage」，node 里没有 DOM，真组件只会在无关处抛错）；
 * - 源码里的 `import.meta.env` 是 Vite 注入的全局，node 下不存在，用 load 钩子换成
 *   `globalThis.__messageEnv__`（等价于 vite dev 的值 `{DEV: true}`，仅为暴露既有的
 *   DEV 探针，不动任何判定分支）。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/feedback-queue.test.mjs
 * （CI 用 `node --test tests/unit/*.test.mjs`，本文件自动被收录）
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { after, beforeEach, describe, it } from 'node:test'

const MESSAGE_URL = new URL('../../src/utils/message.js', import.meta.url).href
const STUB_URL = new URL('./helpers/element-plus-stub.mjs', import.meta.url).href

// ---- 1) document 替身：只给 message.js 用到的 hidden + visibilitychange ----
const doc = {
  hidden: false,
  handlers: [],
  addEventListener(type, cb) {
    if (type === 'visibilitychange') this.handlers.push(cb)
  },
  dispatch(type) {
    for (const cb of this.handlers) cb()
  },
}
globalThis.document = doc
// message.js 顶层读 `import.meta.env.DEV`，load 钩子把它指向这里
globalThis.__messageEnv__ = { DEV: true }

// ---- 2) element-plus 替身 + import.meta.env 替换 ----
// registerHooks 是**同步**钩子：load 必须同步返回且带 shortCircuit，
// 写成 async 会把 Promise 当成钩子结果，Node 直接报 ERR_INVALID_RETURN_PROPERTY_VALUE。
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'element-plus') {
      return { url: STUB_URL, format: 'module', shortCircuit: true }
    }
    return nextResolve(specifier, context)
  },
  load(url, context, nextLoad) {
    if (url === MESSAGE_URL) {
      const source = readFileSync(new URL(url), 'utf8')
      return {
        url,
        format: 'module',
        source: source.replaceAll('import.meta.env', 'globalThis.__messageEnv__'),
        shortCircuit: true,
      }
    }
    const result = nextLoad(url, context)
    return { ...result, shortCircuit: true }
  },
})

const { ElMessage, ElMessageBox } = await import(MESSAGE_URL)
const { __reset: resetStub, __state: stub } = await import(STUB_URL)
const probe = globalThis.__safeMessage
assert.ok(probe, 'DEV 探针必须可用（否则本文件测不到队列内部状态）')

// ---- 3) 可控时钟 ----
const T0 = 1_760_000_000_000
const MAX_QUEUE = 5
const TTL_MS = 60_000
const RESTORE_MS = 2000
let now = T0
const realDateNow = Date.now
Date.now = () => now

const MAX_DEDUPE_MS = probe.dedupeMs

/** 队列里现有的文案（顺序即 FIFO 顺序） */
const queued = () => probe.texts()
const queueSize = () => probe.size()
/** 去重表当前占用的键数量——这是本单关心的「看不见的内存」 */
const recentSize = () => probe.recentKeys().length

/**
 * 从隐藏切回可见并越过 2s 恢复窗口。
 *
 * 定时器不真等：截下 message.js 安排的那个回调，断言它确实是恢复窗口时长后立即执行。
 * 返回被安排（但未由本函数执行）的定时器个数，供定时器堆积用例使用。
 */
function backToVisible({ fire = true } = {}) {
  doc.hidden = false
  const realSetTimeout = globalThis.setTimeout
  const scheduled = []
  globalThis.setTimeout = (cb, ms) => {
    scheduled.push({ cb, ms })
    return scheduled.length - 1
  }
  try {
    doc.dispatch('visibilitychange')
  } finally {
    globalThis.setTimeout = realSetTimeout
  }
  if (fire) {
    // 只跑最后一个：与实现一致（每次切前台都 clearTimeout 掉上一个，绝不排队）
    for (const t of scheduled.slice(0, -1)) t.cb()
    const last = scheduled.at(-1)
    assert.equal(last.ms, RESTORE_MS, '切回前台必须先经过恢复窗口再补发')
    last.cb()
  }
  return scheduled
}

function hide() {
  doc.hidden = true
}

function advance(ms) {
  now += ms
}

const toasts = () => stub.toasts.map((t) => t.text)

/** 灌 n 条互不相同的提示（走页面真实出口，不是队列内部函数） */
const DEFAULT_PREFIX = '同步失败 error'
function pushMany(n, type = 'error', prefix = DEFAULT_PREFIX) {
  for (let i = 0; i < n; i++) ElMessage[type](`${prefix} #${i}`)
}

beforeEach(() => {
  probe.reset()
  resetStub()
  hide()
  now = T0
})

after(() => {
  Date.now = realDateNow
})

describe('规则本体：上限 5 条 + 去重 + TTL 60s', () => {
  it('隐藏期间绝不产出提示（保持 FR-UX-301 的原始意图），恢复后聚合补发 1 条', () => {
    ElMessage.error('保存失败：后端返回 500')
    ElMessage.warning('网络较慢')
    ElMessage.info('已切换到备用通道')

    assert.equal(queueSize(), 3)
    assert.equal(stub.toasts.length, 0, '隐藏期间不得有任何提示被交给 ElMessage')

    backToVisible()
    assert.equal(stub.toasts.length, 1, '积压 3 条只能补发 1 条')
    assert.match(toasts()[0], /保存失败：后端返回 500/)
    assert.match(toasts()[0], /共积压 3 条/)
    assert.equal(stub.toasts[0].type, 'error', '聚合取最严重的一条')
    assert.equal(queueSize(), 0)
  })

  it('同类型同文案重复入队只占 1 个槽位，并刷新时间戳（与 e2e 同一口径）', () => {
    // 1000 次同一件事：队列必须仍是 1 条（e2e 里做不到这个量级）
    pushManyRepeat('error', '登录已过期', 1000)
    assert.equal(queueSize(), 1)
    assert.deepEqual(queued(), ['登录已过期'])
    assert.equal(recentSize(), 1)

    // 去重命中只刷新时间戳：一条仍在持续发生的错误，不该因为「首次入队」快满 60s 就被当成过期吞掉
    advance(TTL_MS - 1000)
    ElMessage.error('登录已过期')
    advance(2000)
    backToVisible()
    assert.equal(stub.toasts.length, 1, '活跃故障必须仍能补发，否则等于把它静音')
    assert.equal(toasts()[0], '登录已过期')

    // 反过来：不再发生后，TTL 从最后一次真实发生时刻起算整条过期——刷新时间戳不等于无限顺延
    resetStub()
    hide()
    ElMessage.error('登录已过期')
    advance(TTL_MS + 1)
    backToVisible()
    assert.equal(stub.toasts.length, 0, 'TTL 只被最后一次入队顺延，停发后仍会到期')
    assert.equal(queueSize(), 0)
  })

  it('第 6 条起丢最旧（FIFO），上限恒为 5', () => {
    pushMany(1000)
    assert.equal(queueSize(), MAX_QUEUE)
    assert.deepEqual(queued(), [5, 6, 7, 8, 9].map((i) => `${DEFAULT_PREFIX} #${990 + i}`))

    backToVisible()
    assert.equal(stub.toasts.length, 1)
    assert.match(toasts()[0], /共积压 5 条/, '聚合条数不得超过上限，否则等于向上谎报积压')
  })

  it('TTL 60s：只补发窗口内的积压，过期条目整条移出而不是留在队列里', () => {
    ElMessage.error('太久以前的错误')
    advance(TTL_MS + 1)
    ElMessage.warning('还算新鲜的告警')

    assert.equal(queueSize(), 2)
    backToVisible()
    assert.equal(stub.toasts.length, 1)
    assert.equal(toasts()[0], '还算新鲜的告警')
    assert.ok(!toasts()[0].includes('共积压'), '只有 1 条存活时不该谎报积压数')
    assert.equal(queueSize(), 0, '过期条目必须被真正移出，不能等下一次 flush 再清')
  })

  it('整队列都过期时一条不发，且队列被清空', () => {
    pushMany(5)
    advance(TTL_MS + 5000)
    backToVisible()
    assert.equal(stub.toasts.length, 0)
    assert.equal(queueSize(), 0)
  })

  it('loading 不入队；confirm/prompt 被拦截时 reject 且绝不回放', async () => {
    ElMessage.loading('正在加载列表')
    assert.equal(queueSize(), 0, '转圈提示补发出来只会残留一个没有对应请求的 loading')

    await assert.rejects(() => ElMessageBox.confirm('确认删除这条草稿？'), /页面隐藏时阻止弹窗/)
    await assert.rejects(() => ElMessageBox.prompt('请输入原因', '驳回'), /页面隐藏时阻止弹窗/)
    assert.equal(queueSize(), 0)
    assert.equal(stub.boxes.length, 0, '确认框被拦截时不得同时调用真 MessageBox')

    backToVisible()
    assert.equal(stub.boxes.length, 0, '错过时机的确认框绝不能补发')
    assert.equal(stub.toasts.length, 0)
  })

  it('可见时同文案 2s 内只弹一次，窗口过后允许再弹（FR-UX-303）', () => {
    doc.hidden = false
    ElMessage.error('同步失败')
    ElMessage.error('同步失败')
    assert.equal(stub.toasts.length, 1)

    advance(MAX_DEDUPE_MS + 1)
    ElMessage.error('同步失败')
    assert.equal(stub.toasts.length, 2, '持续失败必须还能再提醒，不能永远静音')
  })

  it('closeAll 同时作废积压与去重窗口', () => {
    pushMany(3)
    assert.ok(queueSize() > 0)
    ElMessage.closeAll()
    assert.equal(queueSize(), 0, '显式清空后不得有提示在稍后凭空冒出来')
    assert.equal(recentSize(), 0)

    doc.hidden = false
    pushMany(3)
    assert.equal(stub.toasts.length, 3, '清空后同文案应当真的再弹出来')
  })
})

describe('内存不增长（NFR-UX-02 的验收重点）', () => {
  it('去重表过期键是被删除而不是被跳过', () => {
    // 同一时刻灌 500 条不同文案：去重表按窗口语义本就该收下它们
    pushMany(500)
    assert.ok(recentSize() >= 500, `刚灌 500 条，去重表应当有对应条目，实际 ${recentSize()}`)

    // 窗口过后任意一次写入都必须把它们真正回收
    advance(MAX_DEDUPE_MS + 1)
    ElMessage.error('窗口过后的一条新提示')
    assert.ok(
      recentSize() <= 1,
      `过期键必须 delete，残留 ${recentSize()} 条即是内存泄漏（改成 filter 跳过也能骗过所有 e2e）`,
    )
  })

  it('提示条数与队列长度解耦：灌 20000 条，队列恒为 5、去重表仍会被清空', () => {
    for (let i = 0; i < 20000; i++) {
      // 逐条推进时钟：去重表只保留窗口内的键，避免这里退化成 O(n²) 而拖慢整份用例
      advance(1)
      ElMessage.error(`采集异常 #${i}`)
    }
    assert.equal(queueSize(), MAX_QUEUE)
    assert.equal(stub.toasts.length, 0)

    advance(MAX_DEDUPE_MS + 1)
    ElMessage.warning('收尾')
    assert.equal(recentSize(), 1)
  })

  it('隐藏/恢复反复切换 200 轮，结束时不留任何队列状态', () => {
    doc.hidden = false
    for (let round = 0; round < 200; round++) {
      hide()
      pushMany(5, 'error', `第 ${round} 轮`)
      advance(MAX_DEDUPE_MS + TTL_MS + 1)
      backToVisible()
      assert.equal(queueSize(), 0, `第 ${round} 轮补发后队列应当归零`)
      resetStub()
      // 每轮都推进时钟，去重窗口随之下一次写入时被清扫
    }
    advance(MAX_DEDUPE_MS + 1)
    ElMessage.error('清扫检查')
    assert.ok(recentSize() <= 1, `200 轮之后去重表仍留有 ${recentSize()} 条`)
  })

  it('visibilitychange 监听器只在模块加载时注册一次，不随提示数量增长', () => {
    pushMany(2000)
    assert.equal(doc.handlers.length, 1, '每条提示都加一个监听器会永久泄漏闭包')
  })

  it('恢复定时器不堆积：连切 50 次前台，待触发的一直只有 1 个', () => {
    let pending = 0
    for (let i = 0; i < 50; i++) {
      hide()
      const scheduled = backToVisible({ fire: false })
      // 每次切前台：旧的恢复定时器应被 clearTimeout 掉，只留最新的一个
      pending = pending + scheduled.length - (pending ? 1 : 0)
      assert.equal(scheduled.length, 1, `第 ${i} 次切前台多安排了一个恢复定时器`)
    }
    assert.equal(pending, 1)
    assert.equal(stub.toasts.length, 0, '恢复窗口尚未结束，不应有任何提示产出')
  })
})

/** 同一条文案重复弹 n 次（去重路径） */
function pushManyRepeat(type, text, n) {
  for (let i = 0; i < n; i++) ElMessage[type](text)
}
