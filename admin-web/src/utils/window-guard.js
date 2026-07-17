/**
 * 全局页面可见性守卫
 *
 * 核心目标：页面隐藏（最小化/切换标签页）时，拦截所有可能激活浏览器窗口的 API 调用。
 *
 * 为什么需要这个模块：
 *   Element Plus 的 ElMessage/ElMessageBox 等组件在创建时向 document.body 插入 DOM，
 *   某些浏览器在窗口最小化时收到 DOM 插入会尝试"提醒用户"（任务栏闪烁甚至窗口恢复）。
 *   仅靠 message.js 包装 ElMessage 不够全面——ElMessageBox、原生 alert/confirm、
 *   location 跳转、window.focus 等都可能触发激活。
 *
 * 拦截策略：
 *   window.blur 或 document.hidden === true 时，以下操作被静默丢弃或延迟到页面恢复后执行：
 *   - window.focus / window.open
 *   - HTMLElement.prototype.focus（Element Plus 组件 blur 时可能调用，Edge 会激活窗口）
 *   - window.alert / window.confirm / window.prompt
 *   - location.href 赋值 / location.assign / location.replace
 *   - document.title 修改（防止任务栏闪烁）
 *   - EventSource 构造（不新建 SSE 连接）
 *   - fetch / XMLHttpRequest（阻止后台网络活动，Edge 特有问题的根因）
 *   - Element Plus 的 ElMessageBox / ElNotification
 *
 * Edge 特有问题：
 *   Edge 中 window.blur 事件先于 visibilitychange 触发。
 *   最小化窗口时，如果 blur 和 visibilitychange 之间有代码调用了 element.focus()
 *   或其他激活 API，hook 来不及生效，窗口会被瞬间拉回。
 *   因此必须在 blur 事件时就激活拦截，不能等 visibilitychange。
 */

// 窗口是否失去焦点（blur 事件触发，先于 visibilitychange）
let _windowBlurred = false

// 是否处于恢复保护期（页面刚恢复可见的 2s 内仍拦截，防止积压的回调集中触发）
let _isRestoring = false
let _restoreTimer = null

function _shouldBlock() {
  return document.hidden || _isRestoring || _windowBlurred
}

// 保存所有原始方法的引用
const _orig = {}

function _installHooks() {
  // ---- window.focus ----
  _orig.focus = window.focus.bind(window)
  window.focus = function (...args) {
    if (_shouldBlock()) return
    return _orig.focus(...args)
  }

  // ---- HTMLElement.prototype.focus ----
  // Element Plus 组件（ElInput/ElSelect 等）在 blur 时可能调用 element.focus() 重新聚焦
  // 在 Edge 中，element.focus() 会激活最小化的窗口，这是"最小化后瞬间弹出"的根因
  _orig.elementFocus = HTMLElement.prototype.focus
  HTMLElement.prototype.focus = function (...args) {
    if (_shouldBlock()) return
    return _orig.elementFocus.apply(this, args)
  }

  // ---- window.open ----
  _orig.open = window.open.bind(window)
  window.open = function (...args) {
    if (_shouldBlock()) {
      // 返回 null 而非抛异常，与浏览器弹窗拦截器的行为一致
      return null
    }
    return _orig.open(...args)
  }

  // ---- 原生对话框：alert / confirm / prompt ----
  // 这些是系统级模态对话框，在 Windows 上会直接激活最小化窗口
  _orig.alert = window.alert.bind(window)
  _orig.confirm = window.confirm.bind(window)
  _orig.prompt = window.prompt.bind(window)
  window.alert = function (...args) {
    if (_shouldBlock()) return undefined
    return _orig.alert(...args)
  }
  window.confirm = function (...args) {
    if (_shouldBlock()) return false
    return _orig.confirm(...args)
  }
  window.prompt = function (...args) {
    if (_shouldBlock()) return null
    return _orig.prompt(...args)
  }

  // ---- location 跳转 ----
  // location.href 赋值和 location.assign/replace 会导致页面跳转，可能激活窗口
  _orig.locationHref = Object.getOwnPropertyDescriptor(
    window.Location.prototype,
    'href'
  )
  if (_orig.locationHref && _orig.locationHref.set) {
    Object.defineProperty(window.Location.prototype, 'href', {
      get: _orig.locationHref.get,
      set(url) {
        if (_shouldBlock()) {
          console.debug('[window-guard] 页面隐藏时阻止 location.href 跳转:', url)
          return
        }
        _orig.locationHref.set.call(this, url)
      },
      configurable: true,
    })
  }

  _orig.locationAssign = window.Location.prototype.assign
  window.Location.prototype.assign = function (url) {
    if (_shouldBlock()) {
      console.debug('[window-guard] 页面隐藏时阻止 location.assign:', url)
      return
    }
    return _orig.locationAssign.call(this, url)
  }

  _orig.locationReplace = window.Location.prototype.replace
  window.Location.prototype.replace = function (url) {
    if (_shouldBlock()) {
      console.debug('[window-guard] 页面隐藏时阻止 location.replace:', url)
      return
    }
    return _orig.locationReplace.call(this, url)
  }

  // ---- document.title ----
  // 修改 title 会导致 Windows 任务栏闪烁，可能被用户感知为"窗口弹出"
  _orig.titleDesc = Object.getOwnPropertyDescriptor(
    Document.prototype,
    'title'
  )
  if (_orig.titleDesc && _orig.titleDesc.set) {
    Object.defineProperty(document, 'title', {
      get: _orig.titleDesc.get,
      set(v) {
        if (_shouldBlock()) {
          console.debug('[window-guard] 页面隐藏时阻止 title 修改:', v)
          return
        }
        _orig.titleDesc.set.call(document, v)
      },
      configurable: true,
    })
  }

  // ---- EventSource 构造函数 ----
  // 页面隐藏时不建立新的 SSE 连接，防止浏览器后台网络活动触发窗口行为
  if (window.EventSource) {
    _orig.EventSource = window.EventSource
    window.EventSource = function (url, config) {
      if (_shouldBlock()) {
        console.debug('[window-guard] 页面隐藏时阻止 EventSource 创建:', url)
        // 返回一个已关闭的假 EventSource，防止调用方报错
        const fake = {
          readyState: _orig.EventSource.CLOSED,
          close() {},
          addEventListener() {},
          removeEventListener() {},
          dispatchEvent() { return false },
        }
        return fake
      }
      return new _orig.EventSource(url, config)
    }
    // 保留静态常量
    window.EventSource.CONNECTING = _orig.EventSource.CONNECTING
    window.EventSource.OPEN = _orig.EventSource.OPEN
    window.EventSource.CLOSED = _orig.EventSource.CLOSED
  }

  // ---- fetch ----
  // Edge 在后台标签页持续发送网络请求时会激活窗口，必须完全阻止
  // 返回 rejected Promise，让 axios 拦截器走 error 分支（silent 请求不弹提示）
  _orig.fetch = window.fetch.bind(window)
  window.fetch = function (input, init) {
    if (_shouldBlock()) {
      const url = typeof input === 'string' ? input : input?.url
      console.debug('[window-guard] 页面隐藏时阻止 fetch:', url)
      return Promise.reject(new TypeError('Failed to fetch: page is hidden'))
    }
    return _orig.fetch(input, init)
  }

  // ---- XMLHttpRequest ----
  // 拦截 XHR 的 open 方法，页面隐藏时不允许新建请求
  _orig.xhrOpen = XMLHttpRequest.prototype.open
  _orig.xhrSend = XMLHttpRequest.prototype.send
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._guardUrl = url
    if (_shouldBlock()) {
      console.debug('[window-guard] 页面隐藏时阻止 XHR.open:', method, url)
      this._guardBlocked = true
    }
    return _orig.xhrOpen.call(this, method, url, ...rest)
  }
  XMLHttpRequest.prototype.send = function (body) {
    if (this._guardBlocked) {
      console.debug('[window-guard] 页面隐藏时阻止 XHR.send:', this._guardUrl)
      // 不调用原始 send，请求被静默丢弃
      return
    }
    return _orig.xhrSend.call(this, body)
  }
}

/**
 * 强制清理残留的 v-loading 遮罩
 *
 * 触发场景：浏览器最小化期间，CSS transition 与 setTimeout 被冻结，
 * Element Plus v-loading 指令的 mask 隐藏流程不执行，DOM 永久残留。
 * 仅靠 Vue 状态 toggle 不可靠（值未变化时 watch 不触发；transitionend
 * 不会触发；setTimeout 仍被 throttle 到 1s 间隔）。
 *
 * 为什么用 document.querySelectorAll 而不是限定范围：
 *   - keep-alive 路由下的组件可能挂载到 body 直接子节点，限定范围会漏；
 *   - 残留 mask 本就属于异常状态，强制清理后用户操作会触发新的 mask；
 *   - 在页面已可见时清理无副作用，组件下次 loading 会重新创建。
 *
 * @returns {number} 清理的 mask 数量（用于日志诊断）
 */
function _cleanupStaleLoadingMasks() {
  // 使用 :not([data-keep]) 选择器为未来保留扩展点：标记 [data-keep] 的 mask 不清理
  const masks = document.querySelectorAll('.el-loading-mask:not([data-keep])')
  let removed = 0
  masks.forEach((mask) => {
    if (mask.parentNode) {
      mask.parentNode.removeChild(mask)
      removed++
    }
  })
  if (removed > 0) {
    console.debug(`[window-guard] 清理残留 loading mask: ${removed} 个`)
  }
  return removed
}

function _onVisibilityChange() {
  if (document.hidden) {
    // 页面隐藏：hooks 自动生效（_shouldBlock 返回 true）
    console.debug('[window-guard] 页面隐藏，拦截已激活')
  } else {
    // 页面恢复：启动 2s 保护期，防止隐藏期间积压的 Promise 回调集中触发
    if (!_isRestoring) {
      _isRestoring = true
      if (_restoreTimer) clearTimeout(_restoreTimer)
      _restoreTimer = setTimeout(() => {
        _isRestoring = false
        console.debug('[window-guard] 恢复保护期结束，所有操作恢复正常')
      }, 2000)
      console.debug('[window-guard] 页面恢复，启动 2s 保护期')
    }
    // 兜底清理残留 mask：双 rAF 确保浏览器完成首帧渲染后再清理，
    // 避免清理动作与 Vue 响应式更新产生竞争
    requestAnimationFrame(() => {
      requestAnimationFrame(_cleanupStaleLoadingMasks)
    })
  }
}

// Edge 中 blur 事件先于 visibilitychange 触发，必须在此刻就激活拦截
// 否则 blur 和 visibilitychange 之间的代码（如 Element Plus 的 focus 调用）会激活窗口
window.addEventListener('blur', () => {
  _windowBlurred = true
  console.debug('[window-guard] window.blur 触发，拦截已提前激活')
})

window.addEventListener('focus', () => {
  // 窗口恢复焦点时，延迟 2s 清除 blur 标志（与恢复保护期一致）
  if (_windowBlurred) {
    _windowBlurred = false
    console.debug('[window-guard] window.focus 触发，拦截已解除')
  }
})

document.addEventListener('visibilitychange', _onVisibilityChange)

// 模块加载时立即安装 hooks（确保在所有其他代码之前）
_installHooks()

/**
 * 对外暴露：强制清理所有残留的 v-loading mask
 *
 * 适用场景：
 *   - 组件内部在 visibilitychange 之外的其他时机需要清理（如路由切换、定时器触发）
 *   - 不想监听 visibilitychange 又需要立即清理
 *   - 测试时验证清理逻辑
 */
function cleanupLoadingMasks() {
  return _cleanupStaleLoadingMasks()
}

export { _shouldBlock as shouldBlock, cleanupLoadingMasks }
