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

// SSE 端点路径（相对根路径，EventSource 不走 axios baseURL）
const SSE_ENDPOINT = '/admin/api/v1/events/stream'

// 心跳超时：3 次心跳间隔（15s × 3 = 45s）未收到任何事件则重连
const HEARTBEAT_TIMEOUT_MS = 45_000

// 重连退避：1s, 2s, 4s, 8s, 16s, 30s（上限）
const RECONNECT_INITIAL_MS = 1_000
const RECONNECT_MAX_MS = 30_000

// 跨标签页广播频道名
const BROADCAST_CHANNEL = 'news_sse'

// 全局单例状态
let eventSource = null
let heartbeatTimer = null
let reconnectTimer = null
let reconnectAttempt = 0
let subscribers = new Map() // eventType → Set<handler>

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

function _connect() {
  const token = localStorage.getItem('admin_token')
  if (!token) {
    // 未登录不建立连接，避免 401 刷日志
    return
  }

  try {
    eventSource = new EventSource(`${SSE_ENDPOINT}?token=${encodeURIComponent(token)}`)
  } catch (e) {
    console.error('[SSE] EventSource 创建失败', e)
    _scheduleReconnect()
    return
  }

  // 通用的 message 事件兜底（未匹配 event 类型的数据帧）
  eventSource.onmessage = (e) => {
    _resetHeartbeat()
    // 不解析未知 message，避免噪声
  }

  // 连接建立事件：前端据此切换到 SSE 模式
  eventSource.addEventListener('connected', (e) => {
    _resetHeartbeat()
    reconnectAttempt = 0
    console.debug('[SSE] 连接已建立')
  })

  // 心跳事件：仅重置超时计时器，不分发给订阅者
  eventSource.addEventListener('heartbeat', (e) => {
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
    _scheduleReconnect()
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
  // 指数退避：1s, 2s, 4s, 8s, 16s, 30s
  const delay = Math.min(
    RECONNECT_INITIAL_MS * Math.pow(2, reconnectAttempt),
    RECONNECT_MAX_MS,
  )
  reconnectAttempt++
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
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
    _scheduleReconnect()
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

// 页面卸载时清理连接
window.addEventListener('beforeunload', () => {
  _disconnect()
})
