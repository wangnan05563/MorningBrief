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
 */

import { ElMessage as _ElMessage, ElMessageBox as _ElMessageBox } from 'element-plus'

const _MAX_QUEUE = 5
const _TTL_MS = 60000
const _RESTORE_MS = 2000

// 严重度用于聚合时挑选展示哪条文案（error 优先于 warning/info/success）
const _RANK = { error: 3, warning: 2, info: 1, success: 0 }

let _isRestoring = false
let _restoreTimer = null
/** @type {{type: string, text: string, ts: number}[]} */
const _queue = []

function _shouldBlock() {
  return document.hidden || _isRestoring
}

/** 入队：同类型同文案去重（刷新时间戳），超过上限丢最旧（FIFO） */
function _enqueue(type, text, ts = Date.now()) {
  const t = (text || '').trim()
  if (!t) return
  const normalized = type && _RANK[type] !== undefined ? type : 'info'
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
  return _ElMessage(options)
}, _ElMessage)

safeElMessage.closeAll = () => {
  // 显式清空提示时，隐藏期间的积压也一并作废（否则会在稍后凭空冒出来）
  _queue.length = 0
  return _ElMessage.closeAll()
}

const _typed = (type) => (...args) => {
  if (_shouldBlock()) return _enqueue(type, _textOf(args[0]))
  return _ElMessage[type](...args)
}

safeElMessage.success = _typed('success')
safeElMessage.error = _typed('error')
safeElMessage.warning = _typed('warning')
safeElMessage.info = _typed('info')
// loading 不入队：见文件头
safeElMessage.loading = (...args) => {
  if (_shouldBlock()) return
  return _ElMessage.loading(...args)
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
  }
}

export { safeElMessage as ElMessage, safeElMessageBox as ElMessageBox }
