<template>
  <el-alert
    v-if="visible"
    :type="alertType"
    :closable="false"
    show-icon
    class="feed-health-banner"
    :class="`feed-health-banner--${feed.sse.value.state}`"
    data-testid="feed-health-banner"
  >
    <template #title>
      <span data-testid="feed-health-title">{{ title }}</span>
    </template>
    <div class="feed-health-banner__body">
      <div class="feed-health-banner__lines">
        <p v-if="feed.pollFailures.value > 0" class="feed-health-banner__line">
          自动刷新已连续失败 {{ feed.pollFailures.value }} 次：{{ feed.pollMessage.value }}
        </p>
        <p v-if="feed.lastSuccessAt.value" class="feed-health-banner__line" data-testid="feed-health-stale">
          最后成功更新：{{ clockText(feed.lastSuccessAt.value) }}
        </p>
        <p class="feed-health-banner__note">{{ note }}</p>
      </div>
      <!-- 包一层 div 挂 data-testid：IconButton 是 el-tooltip + el-button 的多根节点组件，
           透传属性落不到按钮上（e2e 选择器曾经因此取不到元素） -->
      <div data-testid="feed-health-reconnect">
        <IconButton
          type="primary"
          plain
          :loading="feed.reconnecting.value"
          label="立即重连并刷新"
          desc="重连实时通道，并立刻发起一次手动刷新（不会改变原有轮询频率）"
          :icon="Refresh"
          @click="emit('refresh')"
        />
      </div>
    </div>
  </el-alert>
</template>

<script setup>
/**
 * 实时通道/轮询健康度条（FR-UX-702 / T02516）
 *
 * 与 ListLoadError 的分工：那个组件回答「这一次请求失败了，点重试」，
 * 本组件回答「后台那条持续的数据通道断了，你看到的数字可能是旧的」——
 * 后者是持续性状态，不能靠一次性 toast 表达（toast 会消失，而状态一直在）。
 *
 * 刻意不弹 toast：NFR-UX-02 的去重队列已由 utils/message.js 承担，
 * 断流是持续状态而不是「一次事件」，若每轮退避都发一条会刷屏。
 * 也不设自己的定时器：NFR-UX-03 要求新增错误态/重试不引入额外轮询。
 */
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

import IconButton from './IconButton.vue'

const props = defineProps({
  // useFeedHealth() 的返回值（ref 已在此处 .value 解引用由 computed 保证响应性）
  feed: { type: Object, required: true },
})

const emit = defineEmits(['refresh'])

const visible = computed(() => props.feed.visible.value)
const state = computed(() => props.feed.sse.value.state)
const reason = computed(() => props.feed.sse.value.lastDisconnectReason)
const pollFailures = computed(() => props.feed.pollFailures.value)

const alertType = computed(() => {
  // 登录态失效与刷新失败是「确定坏了」，用 error；纯退避中的断流是「正在自愈」，用 warning
  if (reason.value === 'no_auth') return 'error'
  if (state.value === 'offline') return 'error'
  if (pollFailures.value > 0) return 'error'
  return 'warning'
})

const title = computed(() => {
  if (reason.value === 'no_auth') return '登录状态已失效，实时通道无法连接'
  if (state.value === 'offline') return '实时通道已断开'
  if (state.value === 'retrying') {
    return `实时通道已断开，正在自动重连（第 ${props.feed.sse.value.attempt} 次${delayText.value}）`
  }
  // SSE 本身正常，只有轮询在失败：说清楚是「刷新失败」而不是「通道断开」
  return `自动刷新失败（连续 ${pollFailures.value} 次）`
})

const delayText = computed(() => {
  const ms = props.feed.sse.value.nextDelayMs
  if (!ms) return ''
  return `，${Math.round(ms / 1000)} 秒后重试`
})

const note = computed(() => {
  if (reason.value === 'no_auth') return '请重新登录后再回到本页，期间进度不会自动更新。'
  if (state.value === 'offline') return '后台仍会按退避继续尝试，恢复后自动回到实时；也可点右侧按钮立即重连。'
  if (state.value === 'retrying') return '期间页面显示的是最后一次成功加载的数据，可能已过期。'
  return '下方/右侧数据为上次成功加载的结果，可能已过期。'
})

/** 只在组件内做 HH:MM:SS，避免与 utils/format.js 的秒/毫秒口径纠缠 */
function clockText(ms) {
  if (!ms) return '—'
  const d = new Date(ms)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
</script>

<style scoped lang="scss">
.feed-health-banner {
  margin-bottom: 12px;

  &__body {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }

  &__lines {
    min-width: 0;
  }

  &__line {
    margin: 0 0 4px;
  }

  &__note {
    margin: 0;
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
}
</style>
