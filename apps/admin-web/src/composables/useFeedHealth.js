/**
 * 实时通道 + 轮询的健康度聚合（FR-UX-702 / T02516）
 *
 * 要解决的问题：SSE 断流只在控制台 warn，工作流轮询失败在 silent 模式下连 toast 都被
 * 拦截器咽掉（`silent: true` 同时抑制 loading 与提示），于是页面一直显示上一次的数据——
 * 管理员把几分钟前的进度当实时进度做判断，比直接报错更危险。
 *
 * 这里只做「记账 + 状态聚合」，不做任何定时请求：
 * NFR-UX-03 明确要求新增错误态/重试不能引入额外轮询，页面原有的 5s 兜底轮询与
 * SSE 事件刷新是唯一请求来源，本 composable 记录它们的成败并把失败显式化。
 *
 * 用法：
 *   const feed = useFeedHealth({ onRefresh: () => loadList() })
 *   feed.markPollSuccess() / feed.markPollFailure(e)   // 在 loadX 的成功/失败分支各调一次
 *   <FeedHealthBanner :feed="feed" @refresh="feed.refreshNow" />
 */
import { computed, onUnmounted, ref } from 'vue'

import { getStatus, reconnectNow, subscribeStatus } from '../utils/sse'

/** 需要向用户显报的 SSE 状态（idle/connecting/open/paused 不打扰） */
const ATTENTION_STATES = new Set(['retrying', 'offline'])

export function useFeedHealth({ onRefresh = null, now = () => Date.now() } = {}) {
  const sse = ref(getStatus())
  const pollFailures = ref(0)
  const pollMessage = ref('')
  const lastSuccessAt = ref(0)
  const reconnecting = ref(false)

  const unsubscribeStatus = subscribeStatus((snapshot) => {
    sse.value = snapshot
  })
  onUnmounted(unsubscribeStatus)

  /** 一次成功刷新：清掉失败计数与陈旧起点 */
  function markPollSuccess() {
    lastSuccessAt.value = now()
    if (pollFailures.value !== 0) pollFailures.value = 0
    if (pollMessage.value !== '') pollMessage.value = ''
  }

  /** 一次失败刷新（含 silent 轮询）：只累加计数，弹提示交给拦截器 + message.js 的去重队列 */
  function markPollFailure(error) {
    pollFailures.value += 1
    // 优先取响应体里的业务文案：axios 对 HTTP 500 抛的 e.message 是 "Request failed with status code 500"，
    // 后端那句「服务暂时不可用」在 e.response.data.message 里——用户看得懂的是后者。
    // （silent 模式下拦截器不弹 toast，这条明细是唯一的失败信息来源，不能只剩状态码。）
    pollMessage.value =
      error?.response?.data?.message || error?.message || String(error) || '刷新失败'
  }

  /**
   * 「立即重连 / 刷新」：重连 SSE 并主动做一次非静默刷新。
   * 这次刷新由用户点击触发，不属于额外轮询（NFR-UX-03 约束的是周期性请求）。
   */
  async function refreshNow() {
    reconnecting.value = true
    try {
      reconnectNow()
      if (onRefresh) await onRefresh()
    } finally {
      reconnecting.value = false
    }
  }

  const sseAttention = computed(() => ATTENTION_STATES.has(sse.value.state))

  // 刻意不做「已 N 分钟未更新」这种随时间推进的文案：那需要一个定时器或假计时钟，
  // 而 NFR-UX-03 禁止为新增错误态引入额外轮询/定时任务。这里只报**事实**——
  // 最后一次成功刷新的时刻，由用户自己判断这个时间离现在多久。
  const visible = computed(() => sseAttention.value || pollFailures.value > 0)

  return {
    sse,
    pollFailures,
    pollMessage,
    lastSuccessAt,
    reconnecting,
    sseAttention,
    visible,
    markPollSuccess,
    markPollFailure,
    refreshNow,
    /** 供单测/e2e 断言：当前聚合快照（不可变） */
    snapshot: () => ({
      state: sse.value.state,
      attempt: sse.value.attempt,
      nextDelayMs: sse.value.nextDelayMs,
      reason: sse.value.lastDisconnectReason,
      pollFailures: pollFailures.value,
    }),
  }
}
