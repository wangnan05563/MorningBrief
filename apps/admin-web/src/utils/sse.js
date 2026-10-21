/**
 * SSE 客户端 + 跨标签页事件广播
 *
 * 设计要点：
 * - 每个标签页独立建立 EventSource 连接（V1.2 单机部署，连接数可控）
 * - BroadcastChannel 跨标签页联动：用户操作（删除/启停）广播到其他标签页触发刷新
 * - 心跳超时检测：连续 45s 未收到任何事件则关闭重连（防僵尸连接）
 * - 指数退避重连：1s → 2s → 4s → 8s（上限 30s），避免服务端故障时疯狂重连
 * - 引用计数：第一个订阅者建立连接，最后一个取消订阅时关闭连接
 *
 * 使用方式：
 *   const unsubscribe = sseClient.subscribe('workflow.completed', (event) => {...})
 *   onUnmounted(unsubscribe)
 */

// SSE 端点路径（相对根路径，EventSource 不走 axios baseURL）。
// 必须带 /news 前缀：与 axios baseURL 保持一致——
//   dev：经 Vite 代理 /news/admin/api 转发后端；
//   生产：经 Tailscale Funnel 的 --set-path /news/ 剥离前缀。
// 若缺 /news，dev 下不被代理（直打 Vite 返回 404/SPA 兜底）、prod 下也不在 Funnel 路径内，两端都连不上。
const SSE_ENDPOINT = '/news/admin/api/v1/events/stream'

// 心跳超时：3 次心跳间隔（15s × 3 = 45s）未收到任何事件则重连
const HEARTBEAT_TIMEOUT_MS = 45_000

// 重连退避：1s, 2s, 4s, 8s, 16s, 30s（上限）
const RECONNECT_INITIAL_MS = 1_000
const RECONNECT_MAX_MS = 30_000

// 跨标签页广播频道名
const BROADCAST_CHANNEL = 'news_sse'

// ---- 连接状态对外可见（FR-UX-702 / T02516）----
// 为什么必须有：断流此前只 console.warn，页面继续显示上一次拿到的数据，
// 管理员会把几分钟前的进度当实时进度做判断——「错误不可见」比报错本身更糟。
// 状态口径（给 FeedHealthBanner 直接消费，不再让页面猜 eventSource 对象）：
//   idle        无订阅者且从未连接（首屏前的正常态，不显示任何提示）
//   connecting  正在建立连接（含退避到点后的重连尝试）
//   open        已收到服务端事件（connected/heartbeat/业务事件都算证据）
//   retrying    断流后已进入退避，第 attempt 次尝试前等待 nextDelayMs
//   offline     连续失败达 OFFLINE_AFTER_ATTEMPTS 次，需要用户介入（可手动重连）
//   paused      页面隐藏/失焦导致的主动断开（T0xxxx 的 Edge 最小化保护），不是故障
const OFFLINE_AFTER_ATTEMPTS = 3

// 全局单例状态
let eventSource = null
let heartbeatTimer = null
let reconnectTimer = null
let reconnectAttempt = 0
let nextDelayMs = 0
let subscribers = new Map() // eventType → Set<handler>

let connectionState = 'idle'
let stateListeners = new Set() // (snapshot) => void
let lastEventAt = 0
let lastDisconnectReason = ''

// 跨标签页广播频道（同源标签页共享，不同源则降级为无广播）
let broadcastChannel = null
try {
  broadcastChannel = new BroadcastChannel(BROADCAST_CHANNEL)
} catch (e) {
  // 旧浏览器不支持 BroadcastChannel，降级为无跨标签页联动
  console.warn('[SSE] BroadcastChannel 不可用，跨标签页联动降级')
}

/**
 * 订阅 SSE 事件
 * @param {string} eventType 事件类型（如 'workflow.completed'）或 '*' 监听全部
 * @param {(event: {type: string, data: object, timestamp: number}) => void} handler
 * @returns {() => void} 取消订阅函数
 */
export function subscribe(eventType, handler) {
  if (!subscribers.has(eventType)) {
    subscribers.set(eventType, new Set())
  }
  subscribers.get(eventType).add(handler)

  // 首个订阅者建立连接
  if (!eventSource) {
    _connect()
  }

  return () => {
    const set = subscribers.get(eventType)
    if (set) {
      set.delete(handler)
      if (set.size === 0) {
        subscribers.delete(eventType)
      }
    }
    // 无订阅者时关闭连接，释放服务器资源
    if (subscribers.size === 0) {
      _disconnect()
      // 最后一个订阅者走掉后必须回到 idle：否则离开工作流页后 banner 的兄弟页面
      // 仍会看到上一个页面的 retrying/offline 残留
      reconnectAttempt = 0
      nextDelayMs = 0
      _setState('idle', { force: true })
    }
  }
}

/**
 * 向其他标签页广播用户操作事件（非 SSE 来源的本地事件）
 *
 * 如：批量删除工作流后，通知其他标签页的 WorkflowList 刷新
 * @param {string} eventType 事件类型（建议用 'local.*' 前缀区分）
 * @param {object} data 事件数据
 */
export function broadcastLocal(eventType, data) {
  if (!broadcastChannel) return
  broadcastChannel.postMessage({ type: eventType, data, timestamp: Date.now() / 1000 })
}

/** 当前连接状态快照（不可变副本，页面直接渲染） */
export function getStatus() {
  return {
    state: connectionState,
    attempt: reconnectAttempt,
    nextDelayMs,
    lastEventAt,
    lastDisconnectReason,
    // 只有真的断过流才有「多久没数据」的意义：open 时它就是最后一次事件时间
    silentForMs: connectionState === 'open' && lastEventAt ? Date.now() - lastEventAt : 0,
  }
}

/**
 * 订阅连接状态变化
 * @param {(snapshot: ReturnType<typeof getStatus>) => void} callback 立即以当前快照调用一次
 * @returns {() => void} 取消订阅
 */
export function subscribeStatus(callback) {
  if (typeof callback !== 'function') return () => {}
  stateListeners.add(callback)
  callback(getStatus())
  return () => stateListeners.delete(callback)
}

/**
 * 手动立即重连（banner 上的「立即重连」入口）
 *
 * 为什么需要显式入口而不是等退避：退避上限 30s，但服务重启后首分钟常是端口未就绪，
 * 用户守着页面等到恢复不如让他自己判断「服务起来了」按下按钮。
 * 这里把 attempt 归零，让退避重新从 1s 开始，避免手动点一次就落在 30s 长等待上。
 */
export function reconnectNow() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  reconnectAttempt = 0
  nextDelayMs = 0
  lastDisconnectReason = ''
  if (subscribers.size === 0) {
    // 没有订阅者时不做无意义连接，但状态回到 idle 让 banner 收起
    _setState('idle')
    return getStatus()
  }
  _disconnect()
  _connect()
  return getStatus()
}

function _setState(next, extra = {}) {
  if (extra.reason !== undefined) lastDisconnectReason = extra.reason
  if (next === connectionState && !extra.force) return
  connectionState = next
  const snapshot = getStatus()
  stateListeners.forEach((cb) => {
    try {
      cb(snapshot)
    } catch (err) {
      console.error('[SSE] 状态订阅者回调异常', err)
    }
  })
}

function _markOpen() {
  lastEventAt = Date.now()
  reconnectAttempt = 0
  nextDelayMs = 0
  lastDisconnectReason = ''
  if (connectionState !== 'open') _setState('open', { force: true })
}

function _markFailed(reason) {
  // 断流口径：error / 心跳超时都归到这里，由 _scheduleReconnect 决定 retrying 还是 offline
  lastDisconnectReason = reason
  if (subscribers.size === 0) {
    _setState('idle')
    return
  }
  _scheduleReconnect()
}

function _connect() {
  // NFR-M103：鉴权 token 存于 HttpOnly Cookie，同源 EventSource 自动携带（withCredentials）
  // 以非敏感的 admin_role 作为已登录代理态，避免无谓的 401 连接
  const role = localStorage.getItem('admin_role')
  if (!role) {
    // 有订阅者却没登录态（典型是 Cookie 过期后停留在页面上）：
    // 静默 return 会让 banner 永远停在 idle，用户看不到「实时通道已断开」——按离线报出。
    if (subscribers.size > 0) {
      _setState('offline', { reason: 'no_auth', force: true })
    }
    return
  }

  _setState('connecting')
  try {
    eventSource = new EventSource(SSE_ENDPOINT, { withCredentials: true })
  } catch (e) {
    console.error('[SSE] EventSource 创建失败', e)
    _markFailed('create_failed')
    return
  }

  // 通用的 message 事件兜底（未匹配 event 类型的数据帧）
  eventSource.onmessage = (e) => {
    _markOpen()
    _resetHeartbeat()
    // 不解析未知 message，避免噪声
  }

  // 连接建立事件：前端据此切换到 SSE 模式
  eventSource.addEventListener('connected', (e) => {
    _markOpen()
    _resetHeartbeat()
    console.debug('[SSE] 连接已建立')
  })

  // 心跳事件：仅重置超时计时器，不分发给订阅者
  eventSource.addEventListener('heartbeat', (e) => {
    _markOpen()
    _resetHeartbeat()
  })

  // 订阅所有业务事件类型：动态添加 listener
  // EventSource 不支持通配符，需为每个事件类型注册 listener
  // 这里用 addEventListener 而非 onmessage，因 SSE data 帧带 event: <type> 头
  const knownTypes = [
    'workflow.started',
    'workflow.completed',
    'workflow.failed',
    'workflow.step.completed',
    'workflow.step.failed',
    'channel.active_changed',
  ]
  knownTypes.forEach((type) => {
    eventSource.addEventListener(type, (e) => {
      _markOpen()
      _resetHeartbeat()
      try {
        const payload = JSON.parse(e.data)
        _dispatch(type, payload.data || {}, payload.timestamp)
      } catch (err) {
        console.error('[SSE] 解析事件失败', type, err)
      }
    })
  })

  eventSource.onerror = (e) => {
    console.warn('[SSE] 连接错误，准备重连', e)
    _disconnect()
    _markFailed('connection_error')
  }

  _resetHeartbeat()
}

function _disconnect() {
  if (eventSource) {
    try {
      eventSource.close()
    } catch (_) { /* 已关闭 */ }
    eventSource = null
  }
  if (heartbeatTimer) {
    clearTimeout(heartbeatTimer)
    heartbeatTimer = null
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function _scheduleReconnect() {
  if (reconnectTimer) return
  if (subscribers.size === 0) {
    _setState('idle')
    return
  }
  // 指数退避：1s, 2s, 4s, 8s, 16s, 30s
  const delay = Math.min(
    RECONNECT_INITIAL_MS * Math.pow(2, reconnectAttempt),
    RECONNECT_MAX_MS,
  )
  reconnectAttempt++
  nextDelayMs = delay
  // 失败可见：前 OFFLINE_AFTER_ATTEMPTS 次算「正在自动恢复」（retrying），
  // 之后升格为 offline——用户不该一直盯着「重连中」猜到底行不行。
  // 后台仍继续退避重连（服务恢复即自愈），offline 不是放弃。
  const state = reconnectAttempt >= OFFLINE_AFTER_ATTEMPTS ? 'offline' : 'retrying'
  _setState(state, { force: true })
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    nextDelayMs = 0
    if (subscribers.size > 0) {
      console.debug(`[SSE] 第 ${reconnectAttempt} 次重连`)
      _connect()
    }
  }, delay)
}

function _resetHeartbeat() {
  if (heartbeatTimer) clearTimeout(heartbeatTimer)
  heartbeatTimer = setTimeout(() => {
    // 45s 未收到任何事件，视为僵尸连接，主动关闭重连
    console.warn('[SSE] 心跳超时，主动重连')
    _disconnect()
    _markFailed('heartbeat_timeout')
  }, HEARTBEAT_TIMEOUT_MS)
}

/**
 * 分发事件到本标签页订阅者 + 其他标签页（通过 BroadcastChannel）
 */
function _dispatch(type, data, timestamp) {
  // 本标签页订阅者
  const handlers = subscribers.get(type)
  if (handlers) {
    handlers.forEach((h) => {
      try {
        h({ type, data, timestamp })
      } catch (err) {
        console.error('[SSE] 订阅者 handler 异常', type, err)
      }
    })
  }
  // 通配符订阅者
  const wildcardHandlers = subscribers.get('*')
  if (wildcardHandlers) {
    wildcardHandlers.forEach((h) => {
      try {
        h({ type, data, timestamp })
      } catch (err) {
        console.error('[SSE] 通配符 handler 异常', type, err)
      }
    })
  }
}

// 监听其他标签页广播的本地事件，分发给本标签页订阅者
if (broadcastChannel) {
  broadcastChannel.onmessage = (e) => {
    const { type, data, timestamp } = e.data || {}
    if (!type) return
    _dispatch(type, data, timestamp)
  }
}

// 页面隐藏时断开 SSE 连接，防止浏览器在最小化状态下的后台重连行为激活窗口
// 恢复可见时自动重连（仅当存在订阅者时）
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    if (eventSource) {
      console.debug('[SSE] 页面隐藏，断开 SSE 连接')
      _disconnect()
      // 主动断开 ≠ 故障：banner 要收起，否则切回来一片红，用户以为服务挂了
      _setState('paused', { force: true })
    }
  } else {
    // 页面恢复可见且有订阅者时重新建立连接
    if (!eventSource && subscribers.size > 0) {
      console.debug('[SSE] 页面恢复，重新连接 SSE')
      reconnectAttempt = 0
      _connect()
    }
  }
})

// Edge 中 blur 事件先于 visibilitychange 触发，必须在 blur 时就断开 SSE
// 否则 Edge 检测到活跃的 SSE 连接会立即恢复窗口（最小化后瞬间弹出）
window.addEventListener('blur', () => {
  if (eventSource) {
    console.debug('[SSE] window.blur，提前断开 SSE 连接')
    _disconnect()
    _setState('paused', { force: true })
  }
})

// 窗口恢复焦点时重新连接 SSE（与 visibilitychange 恢复逻辑互为补充）
window.addEventListener('focus', () => {
  // 延迟 2s 重连，与 window-guard 的恢复保护期一致，防止积压回调集中触发
  setTimeout(() => {
    if (!eventSource && subscribers.size > 0 && !document.hidden) {
      console.debug('[SSE] window.focus 恢复，重新连接 SSE')
      reconnectAttempt = 0
      _connect()
    }
  }, 2000)
})

// 页面卸载时清理连接
window.addEventListener('beforeunload', () => {
  _disconnect()
})
