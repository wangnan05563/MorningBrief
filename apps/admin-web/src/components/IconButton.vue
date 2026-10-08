<template>
  <el-tooltip
    v-if="tooltip"
    :content="tip"
    placement="top"
    :fallback-placements="['bottom', 'left', 'right']"
    :disabled="!tip"
    :show-after="150"
  >
    <el-button
      class="icon-btn"
      :type="type"
      :size="size"
      :plain="plain"
      :link="link"
      :text="text"
      :circle="circle"
      :loading="loading"
      :disabled="disabled"
      :aria-label="label"
      :style="btnStyle"
      @click="handleClick"
    >
      <el-icon v-if="icon && !loading" class="icon-btn__icon">
        <component :is="icon" />
      </el-icon>
      <span v-if="inlineText" class="icon-btn__text">{{ inlineText }}</span>
    </el-button>
  </el-tooltip>
  <!-- 无 Tooltip 形态：用于 el-dropdown 触发按钮等已有悬浮语义的场景，避免提示与下拉菜单同时弹出 -->
  <el-button
    v-else
    class="icon-btn"
    :type="type"
    :size="size"
    :plain="plain"
    :link="link"
    :text="text"
    :circle="circle"
    :loading="loading"
    :disabled="disabled"
    :aria-label="label"
    :style="btnStyle"
    @click="handleClick"
  >
    <el-icon v-if="icon && !loading" class="icon-btn__icon">
      <component :is="icon" />
    </el-icon>
    <span v-if="inlineText" class="icon-btn__text">{{ inlineText }}</span>
  </el-button>
</template>

<script setup>
/**
 * 全局图标按钮（T00812：系统管理端按钮重构为动画图标交互）
 *
 * 为什么自建而非直接用 el-button：
 * - 任务要求「纯图标 + 悬浮 Tooltip（中文名+功能描述）+ 点击图标切换动画」，
 *   且全站同类功能必须同一图标；封装成单一组件才能保证语义一致与统一动画。
 * - aria-label 设为中文名：E2E 与无障碍仍可按按钮名称定位（兼容既有测试）。
 *
 * Props 说明：
 * - icon：@element-plus/icons-vue 图标组件（必填，语义见图标映射规范）
 * - label：中文名（必填，作为 aria-label 与 Tooltip 主名）
 * - desc：功能描述（可选，Tooltip 显示「label：desc」）
 * - 其余透传 el-button 的 type/size/plain/link/text/circle/loading/disabled
 */
import { computed } from 'vue'

const props = defineProps({
  icon: { type: [Object, Function], required: true },
  label: { type: String, required: true },
  desc: { type: String, default: '' },
  // 图标旁可选内联精简文字：仅需图标+文字同显以区分类似按钮时设置，默认隐藏
  inlineText: { type: String, default: '' },
  type: { type: String, default: '' },
  size: { type: String, default: 'default' },
  plain: { type: Boolean, default: false },
  link: { type: Boolean, default: false },
  text: { type: Boolean, default: false },
  circle: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  // 透传给内部 el-button 的内联样式（需要按项自定义配色时用；style 属性无法经 el-tooltip 落到按钮上）
  btnStyle: { type: Object, default: null },
  // 是否包 Tooltip；el-dropdown 触发按钮等已有悬浮语义的场景传 false
  tooltip: { type: Boolean, default: true },
})

const emit = defineEmits(['click'])

// Tooltip 内容：中文名 + 一句话功能描述（任务要求）
const tip = computed(() => (props.desc ? `${props.label}：${props.desc}` : props.label))

// 点击触发图标切换动画（CSS :active 缩放 + 旋转），并透传 click 事件
function handleClick(e) {
  emit('click', e)
}
</script>

<style scoped lang="scss">
.icon-btn {
  // 点击反馈动画：缩放 + 轻微旋转，形成「图标切换」的动效观感（T00812）
  .icon-btn__icon {
    transition: transform 0.18s ease;
  }

  .icon-btn__text {
    margin-left: 6px;
    font-size: 13px;
    line-height: 1;
  }

  &:active .icon-btn__icon {
    transform: scale(0.82) rotate(10deg);
  }
}
</style>
