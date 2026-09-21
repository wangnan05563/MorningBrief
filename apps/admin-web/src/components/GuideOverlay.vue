<template>
  <teleport to="body">
    <div v-if="guide.active.value" class="mb-guide-mask" aria-label="新手引导">
      <div ref="bubbleEl" class="mb-guide-bubble" :class="{ 'is-top': place === 'top' }">
        <button class="mb-guide-close" aria-label="关闭引导" @click="guide.skip()">
          <el-icon><Close /></el-icon>
        </button>
        <div class="mb-guide-progress">第 {{ guide.stepIndex.value + 1 }} / {{ guide.steps.value.length }} 步</div>
        <div class="mb-guide-title">{{ currentStep.t }}</div>
        <div class="mb-guide-text">{{ currentStep.d }}</div>
        <div class="mb-guide-actions">
          <button class="mb-guide-link" @click="guide.skip()">跳过</button>
          <!-- 自动播放开关始终可见：开启中显示状态、点击可关闭；关闭后可再开启（手动步进与自动播放两模式切换） -->
          <button class="mb-guide-link" :aria-label="autoLabel" @click="guide.toggleAuto()">
            {{ autoLabel }}
          </button>
          <button v-if="guide.stepIndex.value > 0" class="mb-guide-btn" @click="guide.prev()">上一步</button>
          <button class="mb-guide-btn mb-guide-btn-primary" @click="guide.next()">
            {{ guide.stepIndex.value < guide.steps.value.length - 1 ? '下一步' : '完成' }}
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 引导浮层（T00863）
 *
 * 职责：
 * 1. 高亮当前步骤目标元素（挖洞遮罩：给目标加 outline + 大 box-shadow，其余区域自然变暗）
 * 2. 气泡卡定位到目标旁（优先下方，空间不足翻上方；水平居中防溢出视口）
 * 3. 手动步进（上一步/下一步/跳过）与自动播放（每步 2.6s 自动前进）
 *
 * 为什么用目标元素自身 box-shadow 而非全屏遮罩挖洞：全屏遮罩 + pointer-events 处理
 * 在多个固定定位元素（侧栏/顶部栏）下层级易冲突；目标自身大 box-shadow 视觉等价、
 * 层级可控、且天然不拦截目标上的点击。
 */
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { Close } from '@element-plus/icons-vue'
import { useGuide } from '../guide/useGuide'

const guide = useGuide()
const bubbleEl = ref(null)
const place = ref('bottom')
const BUBBLE_W = 340
const GAP = 14

const currentStep = computed(() => guide.steps.value[guide.stepIndex.value] || {})
const autoLabel = computed(() => (guide.autoPlay.value ? '自动播放中' : '开自动播放'))

let highlightEl = null
let timer = null
let tick = 0

function resolveTarget() {
  const selectors = currentStep.value.s || []
  for (const sel of selectors) {
    const el = document.querySelector(sel)
    if (el) return el
  }
  return null
}

function clearHighlight() {
  if (highlightEl) {
    highlightEl.classList.remove('mb-guide-highlight')
    highlightEl = null
  }
}

function applyHighlight() {
  clearHighlight()
  const target = resolveTarget()
  if (!target) {
    // 目标未渲染（如数据未加载）：气泡居中展示，步骤仍可继续
    place.value = 'center'
    if (bubbleEl.value) {
      const el = bubbleEl.value
      el.style.left = `${Math.max(16, (window.innerWidth - BUBBLE_W) / 2)}px`
      el.style.top = `${Math.max(16, window.innerHeight / 2 - 120)}px`
    }
    return
  }
  target.classList.add('mb-guide-highlight')
  highlightEl = target
  target.scrollIntoView({ block: 'center', behavior: 'smooth' })
  nextTick(() => layoutBubble(target))
}

function layoutBubble(target) {
  const bubble = bubbleEl.value
  if (!bubble) return
  const rect = target.getBoundingClientRect()
  const bh = bubble.offsetHeight || 160
  let top = rect.bottom + GAP
  let dir = 'bottom'
  if (top + bh > window.innerHeight - 16) {
    top = rect.top - GAP - bh
    dir = 'top'
    if (top < 16) top = 16 // 目标本身贴近视口上下边缘时兜底，避免气泡出界
  }
  const left = Math.min(Math.max(16, rect.left + rect.width / 2 - BUBBLE_W / 2), window.innerWidth - BUBBLE_W - 16)
  place.value = dir
  bubble.style.left = `${left}px`
  bubble.style.top = `${top}px`
}

function startAuto() {
  stopAuto()
  if (!guide.active.value || !guide.autoPlay.value) return
  timer = setInterval(() => {
    if (!guide.active.value) return stopAuto()
    tick += 1
    if (tick >= 2) {
      tick = 0
      guide.next()
    }
  }, 1300)
}

function stopAuto() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch(
  () => [guide.active.value, guide.stepIndex.value, guide.autoPlay.value],
  async () => {
    if (!guide.active.value) {
      clearHighlight()
      stopAuto()
      return
    }
    tick = 0
    await nextTick()
    applyHighlight()
    startAuto()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  clearHighlight()
  stopAuto()
})
</script>

<style scoped>
.mb-guide-mask {
  position: fixed;
  inset: 0;
  z-index: 12000;
}
.mb-guide-bubble {
  position: fixed;
  width: 340px;
  padding: 18px 20px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
  color: #1f2937;
  font-size: 13px;
  box-sizing: border-box;
}
.mb-guide-close {
  position: absolute;
  top: 10px;
  right: 10px;
  border: none;
  background: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 2px;
}
.mb-guide-close:hover {
  color: #374151;
}
.mb-guide-progress {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}
.mb-guide-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 6px;
  color: #111827;
}
.mb-guide-text {
  line-height: 1.6;
  color: #4b5563;
  margin-bottom: 14px;
}
.mb-guide-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-end;
}
.mb-guide-link {
  border: none;
  background: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 13px;
  padding: 4px 6px;
}
.mb-guide-link:hover {
  color: #2563eb;
}
.mb-guide-btn {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
  border-radius: 8px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 13px;
}
.mb-guide-btn:hover {
  border-color: #2563eb;
  color: #2563eb;
}
.mb-guide-btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.mb-guide-btn-primary:hover {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}
</style>

<style>
/* 高亮目标：全局样式（scoped 无法命中 teleport 外部目标元素） */
.mb-guide-highlight {
  outline: 2px solid #2563eb !important;
  outline-offset: 2px;
  box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.5) !important;
  position: relative !important;
  border-radius: 6px;
  transition: box-shadow 0.2s ease;
}
</style>
