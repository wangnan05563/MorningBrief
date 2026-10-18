/**
 * ElMessage / ElMessageBox 安全包装器
 *
 * 核心策略：页面不可见或正在恢复时不向 DOM 插入提示，防止激活最小化窗口。
 *
 * FR-UX-301 起被拦截的普通提示不再直接丢弃，而是 FIFO 入队（去重、上限 5 条、TTL 60s），
 * 等 `visibilitychange` 恢复且 `_isRestoring` 窗口结束后**聚合补发一条**——
 * 既保留「隐藏期间零 DOM 节点」的原意，又不会把隐藏期间的失败原因永久吞掉。
 *
 * ElMessageBox 的 confirm/prompt 被阻止时仍返回 rejected Promise（语义 = 用户点取消），
 * 绝不回放：补发一个已经错过时机的确认框会诱导用户在毫不知情的情况下确认高危动作。
 * ElMessage.loading 不入队：转圈提示补发出来只会残留一个没有对应请求的 loading。
 *
 * FR-UX-303 起再加一层「2 秒内同文案同类型只弹一次」去重：
 * 拦截器已经为一次请求失败弹过提示，页面自己的 catch 常常又用同一个 `e.message`
 * 弹一遍，于是一件事两条 toast；并行多个请求同时失败时更会一次刷出 N 条。
 * 去重放在包装器里而不是各页面，是因为提示的唯一出口就是这个模块——
 * 页面无法（也不该）知道拦截器是否已经弹过。
 * confirm/prompt 不参与去重：确认框被吞掉等于替用户做了决定。
 */

import { ElMessage as _ElMessage, ElMessageBox as _ElMessageBox } from 'element-plus'

const _MAX_QUEUE = 5
const _TTL_MS = 60000
const _RESTORE_MS = 2000
// FR-UX-303：同类型同文案的提示在这个窗口内只弹一次（拦截器弹过，页面 catch 不再重复弹）
const _DEDUPE_MS = 2000

// 严重度用于聚合时挑选展示哪条文案（error 优先于 warning/info/success）
const _RANK = { error: 3, warning: 2, info: 1, success: 0 }

let _isRestoring = false
let _restoreTimer = null
/** @type {{type: string, text: string, ts: number}[]} */
const _queue = []
/** @type {Map<string, number>} `类型|文案` -> 该窗口首次展示时刻 */
const _recent = new Map()

function _shouldBlock() {
  return document.hidden || _isRestoring
}

/**
 * 判断并登记一条提示：2 秒窗口内同类型同文案已弹过则返回 true（调用方应放弃弹），
 * 否则登记本次时刻并返回 false。
 *
 * 窗口锚定在「首次展示」而不是每次重复都顺延：持续失败时每隔 2 秒仍能再提醒一次，
 * 不至于因为请求连绵不断而永远不再出现。
 */
function _suppressDuplicate(type, text, now = Date.now()) {
  const t = (text || '').trim()
  if (!t) return false
  for (const [key, ts] of _recent) {
    if (now - ts > _DEDUPE_MS) _recent.delete(key)
  }
  const key = `${type}|${t}`
  const first = _recent.get(key)
  if (first !== undefined && now - first < _DEDUPE_MS) return true
  _recent.set(key, now)
  return false
}

/** 入队：同类型同文案去重（刷新时间戳），超过上限丢最旧（FIFO） */
function _enqueue(type, text, ts = Date.now()) {
  const t = (text || '').trim()
  if (!t) return
  const normalized = type && _RANK[type] !== undefined ? type : 'info'
  // 隐藏期间同样去重：否则一次页面隐藏里 5 个并行请求失败会挤掉 5 个队列槽位，
  // 补发时的「共积压 N 条」也变成虚报次数
  if (_suppressDuplicate(normalized, t, ts)) return
  const hit = _queue.find((i) => i.type === normalized && i.text === t)
  if (hit) {
    hit.ts = ts
    return
  }
  _queue.push({ type: normalized, text: t, ts })
  if (_queue.length > _MAX_QUEUE) _queue.shift()
}

/** 聚合补发：TTL 内的积压合并成 1 条（取最严重的一条文案 + 总条数） */
function _flush() {
  if (document.hidden) return
  if (!_queue.length) return
  const now = Date.now()
  const alive = _queue.splice(0).filter((i) => now - i.ts <= _TTL_MS)
  if (!alive.length) return
  const worst = alive.reduce((a, b) => (_RANK[b.type] > _RANK[a.type] ? b : a))
  const suffix = alive.length > 1 ? `（页面隐藏期间共积压 ${alive.length} 条提示，已聚合）` : ''
  _ElMessage({ type: worst.type, message: `${worst.text}${suffix}`, duration: 6000 })
}

document.addEventListener('visibilitychange', () => {
  // 切到后台不做事；切回前台先进入 2s 恢复窗口，窗口结束才补发（避免刚露面就刷弹窗）
  if (document.hidden) return
  _isRestoring = true
  if (_restoreTimer) clearTimeout(_restoreTimer)
  _restoreTimer = setTimeout(() => {
    _isRestoring = false
    _restoreTimer = null
    _flush()
  }, _RESTORE_MS)
})

// ---- ElMessage 安全包装 ----

const _textOf = (options) => (typeof options === 'string' ? options : options?.message)
const _typeOf = (options, fallback) =>
  (options && typeof options === 'object' && options.type) || fallback || 'info'

const safeElMessage = Object.assign(function (options) {
  if (_shouldBlock()) return _enqueue(_typeOf(options), _textOf(options))
  if (_suppressDuplicate(_typeOf(options), _textOf(options))) return undefined
  return _ElMessage(options)
}, _ElMessage)

safeElMessage.closeAll = () => {
  // 显式清空提示时，隐藏期间的积压也一并作废（否则会在稍后凭空冒出来）
  _queue.length = 0
  // 去重窗口同样作废：既然要求「清空」，下一条同文案提示应当真的弹出来
  _recent.clear()
  return _ElMessage.closeAll()
}

const _typed = (type) => (...args) => {
  if (_shouldBlock()) return _enqueue(type, _textOf(args[0]))
  if (_suppressDuplicate(type, _textOf(args[0]))) return undefined
  return _ElMessage[type](...args)
}

safeElMessage.success = _typed('success')
safeElMessage.error = _typed('error')
safeElMessage.warning = _typed('warning')
safeElMessage.info = _typed('info')
// loading 不参与去重：调用方常持有返回的 handler 去 close 它，
// 被去重吞掉会返回 undefined 而让调用方报错
safeElMessage.loading = (...args) => {
  if (_shouldBlock()) return
  return _ElMessage.loading(...args)
}

/**
 * 页面 catch 里的「只弹一次」提示（FR-UX-303）。
 *
 * 拦截器已经为这个错误弹过提示时不再弹第二条。为什么不能只靠文案去重：
 * 页面常写「删除预览失败：xxx」这种带上下文的合成文案，与拦截器弹的原文不同，
 * 按字面合不起来，用户看到的仍是同一件事的两条 toast。
 *
 * @param err      catch 到的错误（api 层弹过提示时会带 __uiNotified 标记）
 * @param text     提示文案，或 (err) => string；省略时取 err.message
 */
export function notifyErrorOnce(err, text) {
  if (err && err.__uiNotified) return undefined
  const resolved = typeof text === 'function' ? text(err) : (text || err?.message || '操作失败')
  return safeElMessage.error(resolved)
}

// ---- ElMessageBox 安全包装 ----
// confirm/prompt 被阻止时 reject，模拟用户点击"取消"；alert 被阻止时 resolve
// 三者都不入队、不回放（FR-UX-301）

const safeElMessageBox = Object.assign({}, _ElMessageBox)

safeElMessageBox.alert = (...args) => {
  if (_shouldBlock()) return Promise.resolve()
  return _ElMessageBox.alert(...args)
}

safeElMessageBox.confirm = (...args) => {
  if (_shouldBlock()) return Promise.reject(new Error('页面隐藏时阻止弹窗'))
  return _ElMessageBox.confirm(...args)
}

safeElMessageBox.prompt = (...args) => {
  if (_shouldBlock()) return Promise.reject(new Error('页面隐藏时阻止弹窗'))
  return _ElMessageBox.prompt(...args)
}

if (import.meta.env.DEV) {
  // 仅供 e2e 断言队列语义（去重 / 上限 / TTL / loading 不入队）；生产构建不含此全局
  globalThis.__safeMessage = {
    size: () => _queue.length,
    texts: () => _queue.map((i) => i.text),
    push: _enqueue,
    loading: (text) => safeElMessage.loading(text),
    // FR-UX-303 语义探针：recentKeys 记录当前去重窗口内存过的「类型|文案」；
    // show 让 e2e 能直接从统一出口弹提示（断言 DOM 里 .el-message 的条数）；
    // reset 供用例之间清空窗口、队列与已渲染的提示（否则上一条用例弹过的文案会让本条误判「已去重」）
    recentKeys: () => [..._recent.keys()],
    dedupeMs: _DEDUPE_MS,
    show: (type, text) => safeElMessage[type](text),
    notifyOnce: notifyErrorOnce,
    reset: () => safeElMessage.closeAll(),
  }
}

export { safeElMessage as ElMessage, safeElMessageBox as ElMessageBox }
