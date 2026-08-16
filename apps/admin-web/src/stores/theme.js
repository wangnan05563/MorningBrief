/**
 * 主题状态管理：当前主题 + localStorage 持久化
 *
 * 设计要点：
 * - 主题列表与 themes.scss 中的 [data-theme] 选择器一一对应
 * - applyTheme 通过 document.documentElement.dataset.theme 切换 CSS 变量集
 * - localStorage 持久化，刷新与跨标签页（storage 事件）保持一致
 */
import { defineStore } from 'pinia'

export const THEME_STORAGE_KEY = 'admin_theme'

// 主题元数据：用于主题切换面板渲染预览
// colors 字段用于面板色块展示，必须与 themes.scss 中的实际色值保持一致
export const THEMES = [
  {
    id: 'macaron',
    name: '马卡龙',
    description: '薄荷青 + 暖灰，柔和治愈',
    colors: ['#7ECEC1', '#FFD3E0', '#F9FDFB'],
    isDark: false,
  },
  {
    id: 'enterprise',
    name: '现代企业',
    description: '科技蓝 + 高级灰，专业可信赖',
    colors: ['#2B6CB0', '#BEE3F8', '#F7FAFC'],
    isDark: false,
  },
  {
    id: 'creative',
    name: '创意品牌',
    description: '粉橙渐变 + 活泼色，年轻创新',
    colors: ['#C53030', '#4ECDC4', '#FFF8F0'],
    isDark: false,
  },
  {
    id: 'showcase',
    name: '产品展示',
    description: '暗黑 + 霓虹点缀，科技未来感',
    colors: ['#00E5FF', '#B388FF', '#0A0A0F'],
    isDark: true,
  },
  {
    id: 'commerce',
    name: '电商零售',
    description: '明亮扁平 + 电商红，干净舒适',
    colors: ['#BC2A38', '#457B9D', '#F1FAF8'],
    isDark: false,
  },
  {
    id: 'portfolio',
    name: '艺术作品集',
    description: '极简高雅 + 优雅金',
    colors: ['#8B6F3C', '#8B7355', '#FAFAFA'],
    isDark: false,
  },
]

export const useThemeStore = defineStore('theme', {
  state: () => ({
    // 默认马卡龙，从 localStorage 恢复时优先于默认值
    currentTheme: localStorage.getItem(THEME_STORAGE_KEY) || 'macaron',
  }),

  getters: {
    currentThemeMeta: (state) =>
      THEMES.find((t) => t.id === state.currentTheme) || THEMES[0],
    isDark: (state) => {
      const meta = THEMES.find((t) => t.id === state.currentTheme)
      return meta ? meta.isDark : false
    },
  },

  actions: {
    /**
     * 应用主题到 documentElement
     * 必须在主题变化时调用，包括初始化时
     */
    applyTheme(themeId) {
      const theme = THEMES.find((t) => t.id === themeId)
      if (!theme) return
      this.currentTheme = themeId
      localStorage.setItem(THEME_STORAGE_KEY, themeId)
      document.documentElement.setAttribute('data-theme', themeId)
    },

    /**
     * 初始化主题：在应用启动时调用一次
     * 避免 SSR 或刷新时主题闪烁
     */
    initTheme() {
      const saved = localStorage.getItem(THEME_STORAGE_KEY) || 'macaron'
      document.documentElement.setAttribute('data-theme', saved)
      this.currentTheme = saved
    },
  },
})
