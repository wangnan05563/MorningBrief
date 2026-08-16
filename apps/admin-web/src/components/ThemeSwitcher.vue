<template>
  <el-dialog
    v-model="visible"
    title="系统主题"
    width="640px"
    :close-on-click-modal="true"
    append-to-body
  >
    <div class="theme-grid">
      <div
        v-for="theme in THEMES"
        :key="theme.id"
        class="theme-card"
        :class="{ active: themeStore.currentTheme === theme.id }"
        @click="selectTheme(theme.id)"
      >
        <!-- 色块预览：模拟主题实际视觉氛围 -->
        <div class="theme-preview" :style="getPreviewStyle(theme)">
          <div class="preview-header" :style="getHeaderStyle(theme)">
            <span class="preview-dot" :style="{ background: theme.colors[0] }"></span>
            <span class="preview-line"></span>
          </div>
          <div class="preview-body">
            <div class="preview-card" :style="getCardStyle(theme)">
              <div class="preview-text" :style="{ color: theme.colors[1] }"></div>
              <div class="preview-text short" :style="{ color: theme.colors[1] }"></div>
            </div>
            <div class="preview-card" :style="getCardStyle(theme)">
              <div class="preview-text" :style="{ color: theme.colors[1] }"></div>
            </div>
          </div>
        </div>
        <div class="theme-info">
          <div class="theme-name">
            <span>{{ theme.name }}</span>
            <el-icon v-if="themeStore.currentTheme === theme.id" class="check-icon">
              <CircleCheckFilled />
            </el-icon>
          </div>
          <div class="theme-desc">{{ theme.description }}</div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
/**
 * 主题切换对话框
 *
 * 设计要点：
 * - 6 个主题卡片网格展示，每个卡片有迷你预览（模拟侧边栏+卡片布局）
 * - 点击即时切换并应用，无需"确认"按钮
 * - 当前主题高亮显示对勾标识
 */
import { ref } from 'vue'
import { CircleCheckFilled } from '@element-plus/icons-vue'
import { useThemeStore, THEMES } from '../stores/theme'
import { ElMessage } from '../utils/message'

const themeStore = useThemeStore()
const visible = ref(false)

function open() {
  visible.value = true
}

function selectTheme(themeId) {
  themeStore.applyTheme(themeId)
  ElMessage.success(`已切换为「${THEMES.find((t) => t.id === themeId)?.name}」主题`)
}

// 预览样式：用主题色模拟实际界面氛围
function getPreviewStyle(theme) {
  return {
    background: theme.colors[2],
  }
}

function getHeaderStyle(theme) {
  return {
    background: theme.isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.03)',
    borderBottom: `1px solid ${theme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)'}`,
  }
}

function getCardStyle(theme) {
  return {
    background: theme.isDark ? '#1E1E2A' : '#FFFFFF',
    border: `1px solid ${theme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)'}`,
  }
}

defineExpose({ open })
</script>

<style scoped lang="scss">
@use '../styles/variables.scss' as *;

.theme-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 8px 4px;
}

.theme-card {
  cursor: pointer;
  border-radius: $radius-md;
  border: 2px solid transparent;
  overflow: hidden;
  transition: all 0.2s ease;
  background: $color-bg-card;

  &:hover {
    transform: translateY(-2px);
    box-shadow: $shadow-md;
  }

  &.active {
    border-color: $color-primary;
    box-shadow: 0 0 0 3px rgba(126, 206, 193, 0.15);
  }
}

.theme-preview {
  height: 110px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;

  .preview-header {
    height: 18px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 6px;
  }

  .preview-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .preview-line {
    flex: 1;
    height: 4px;
    background: rgba(160, 174, 192, 0.3);
    border-radius: 2px;
  }

  .preview-body {
    flex: 1;
    display: flex;
    gap: 6px;
  }

  .preview-card {
    flex: 1;
    border-radius: 4px;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .preview-text {
    height: 4px;
    border-radius: 2px;
    background: currentColor;
    opacity: 0.6;

    &.short {
      width: 60%;
    }
  }
}

.theme-info {
  padding: 10px 12px;

  .theme-name {
    font-size: 14px;
    font-weight: 600;
    color: $color-text-primary;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;

    .check-icon {
      color: $color-primary;
      font-size: 16px;
    }
  }

  .theme-desc {
    font-size: 12px;
    color: $color-text-secondary;
    line-height: 1.4;
  }
}
</style>
