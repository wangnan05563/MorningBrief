<template>
  <div
    class="wf-progress"
    :class="{ 'is-compact': compact }"
  >
    <!-- 5 个状态灯：水平排列，颜色映射阶段状态 -->
    <ul class="lights" aria-label="阶段进度状态灯列表">
      <li
        v-for="(step, idx) in stepsWithMeta"
        :key="step.name"
        class="light-item"
        :class="[`is-${step.lightStatus}`, { 'is-clickable': step.error }]"
        :aria-label="step.ariaLabel"
        @click="step.error && showError(step)"
      >
        <span class="light" :title="step.tooltipText">
          <!-- 状态灯主体；用 i 标签承载颜色，便于过渡动画 -->
          <i class="light-dot" />
        </span>
        <span class="light-name">{{ step.label }}</span>
      </li>
    </ul>

    <!-- 整体进度百分比：基于已完成阶段数量 / 5 -->
    <span class="percent" :aria-hidden="true">{{ progressPercent }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessageBox } from '../../../utils/message'
import { formatTime } from '../../../utils/format'

const props = defineProps({
  // 后端返回的 steps_summary 数组：[{ name, status, finished_at, error }, ...]
  steps: {
    type: Array,
    default: () => [],
  },
  // 工作流整体状态：cancelled 时未完成阶段视为已中断
  workflowStatus: {
    type: String,
    default: '',
  },
  // 紧凑模式：移动端使用，缩小灯径与间距
  compact: {
    type: Boolean,
    default: false,
  },
})

// 5 阶段固定顺序与中文标签：与详情页 STEP_LABEL_MAP 保持一致
const STEP_LABELS = {
  crawl: '爬虫采集',
  rewrite: 'LLM改写',
  tts: '语音合成',
  stitch: '音频拼接',
  review: '创建审核',
}

// 步骤状态到状态灯颜色的映射：
// success → 绿色，running/retrying → 黄色，failed → 红色，pending → 灰色
function mapLightStatus(stepStatus, workflowStatus) {
  if (stepStatus === 'success') return 'done'
  if (stepStatus === 'running' || stepStatus === 'retrying') return 'active'
  if (stepStatus === 'failed') return 'error'
  // 工作流被取消时，pending 视为已中断（语义更准确，但视觉仍为灰色）
  if (workflowStatus === 'cancelled' && stepStatus === 'pending') return 'idle'
  return 'idle'
}

// 将后端 steps_summary 转换为带视觉元数据的列表
const stepsWithMeta = computed(() => {
  const list = Array.isArray(props.steps) ? props.steps : []
  // 索引到 step 的 map，缺失时回退到 pending
  const stepMap = list.reduce((acc, s) => {
    if (s && s.name) acc[s.name] = s
    return acc
  }, {})

  return Object.keys(STEP_LABELS).map((name) => {
    const step = stepMap[name] || { name, status: 'pending' }
    const lightStatus = mapLightStatus(step.status, props.workflowStatus)
    const label = STEP_LABELS[name]
    const finishedText = step.finished_at
      ? `完成时间：${formatTime(step.finished_at)}`
      : '未完成'
    const statusText = step.status === 'pending' && props.workflowStatus === 'cancelled'
      ? '已中断'
      : stepStatusLabel(step.status)
    return {
      name,
      label,
      lightStatus,
      error: step.error || null,
      tooltipText: `${label} · ${statusText}\n${finishedText}`,
      ariaLabel: `${label}，状态：${statusText}，${finishedText}`,
    }
  })
})

// 步骤状态中文文案
function stepStatusLabel(s) {
  const m = {
    pending: '等待中',
    running: '运行中',
    success: '成功',
    retrying: '重试中',
    failed: '失败',
  }
  return m[s] || s
}

// 进度百分比：已完成阶段数 / 总数 * 100，四舍五入
const progressPercent = computed(() => {
  const doneCount = stepsWithMeta.value.filter((s) => s.lightStatus === 'done').length
  return Math.round((doneCount / stepsWithMeta.value.length) * 100)
})

// 错误详情弹窗：仅 failed 阶段可触发
async function showError(step) {
  await ElMessageBox.alert(
    step.error || '该阶段失败但未提供错误详情',
    `${step.label} 阶段错误详情`,
    {
      type: 'error',
      confirmButtonText: '知道了',
    }
  )
}
</script>

<style scoped lang="scss">
@use '../../../styles/variables.scss' as *;

.wf-progress {
  display: inline-flex;
  align-items: center;
  gap: 10px;

  .lights {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .light-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    cursor: default;

    &.is-clickable {
      cursor: pointer;

      &:focus-visible {
        outline: 2px solid $color-primary;
        outline-offset: 2px;
        border-radius: 4px;
      }
    }

    .light {
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    // 状态灯本体：直径 18px，确保视觉清晰
    .light-dot {
      display: block;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background-color: #9E9E9E; // 默认灰色（已中断/未开始）
      box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8), 0 1px 3px rgba(0, 0, 0, 0.15);
      // 状态切换时的平滑过渡动画（350ms 在 300-500ms 范围内）
      transition: background-color 350ms ease, box-shadow 350ms ease, transform 350ms ease;
    }

    // 阶段名称：默认隐藏，悬停或紧凑模式下显示
    .light-name {
      font-size: 11px;
      color: $color-text-secondary;
      opacity: 0;
      transition: opacity 350ms ease;
      white-space: nowrap;
    }

    &:hover,
    &:focus-visible {
      .light-dot {
        transform: scale(1.15);
      }
      .light-name {
        opacity: 1;
      }
    }

    // 状态色：使用 WCAG 2.1 AA 对比度的色值
    &.is-done .light-dot {
      background-color: #4CAF50; // 绿色（已完成）
    }
    &.is-active .light-dot {
      background-color: #FFC107; // 黄色（进行中）
      // 进行中加脉冲效果，提升可见性
      animation: pulse 1.6s ease-in-out infinite;
    }
    &.is-error .light-dot {
      background-color: #F44336; // 红色（错误）
    }
    &.is-idle .light-dot {
      background-color: #9E9E9E; // 灰色（已中断/未开始）
    }
  }

  .percent {
    font-size: 12px;
    font-weight: 600;
    color: $color-text-primary;
    min-width: 36px;
    text-align: right;
  }

  // 紧凑模式：移动端缩小灯径与间距
  &.is-compact {
    .lights {
      gap: 8px;
    }
    .light-item {
      gap: 2px;
      .light-dot {
        width: 16px;
        height: 16px;
      }
      .light-name {
        display: none; // 紧凑模式不显示名称，仅 tooltip
      }
    }
  }
}

// 进行中脉冲动画：黄色灯柔和闪烁
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8), 0 1px 3px rgba(0, 0, 0, 0.15); }
  50% { box-shadow: 0 0 0 4px rgba(255, 193, 7, 0.4), 0 1px 3px rgba(0, 0, 0, 0.15); }
}

// 响应式：窄屏切换为紧凑模式
@media (max-width: 768px) {
  .wf-progress {
    .lights {
      gap: 8px;
    }
    .light-item {
      .light-dot {
        width: 16px;
        height: 16px;
      }
      .light-name {
        display: none;
      }
    }
  }
}
</style>
