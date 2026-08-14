/**
 * 应用入口：创建 Vue 实例 + 挂载插件
 *
 * 插件加载顺序：window-guard（全局拦截）→ 主题初始化 → Pinia → Router → Element Plus
 * - window-guard 必须最先加载，在任何其他代码调用可能激活窗口的 API 之前安装 hook
 * - 主题初始化紧随其后，避免 Vue 挂载前出现主题闪烁
 * - 全局注入安全的 ElMessage，防止最小化时弹窗激活浏览器窗口
 */
// 全局页面可见性守卫：必须在所有其他模块之前加载，安装 window/alert/location 等 hook
import './utils/window-guard'

// 全局兜底：捕获未被任何调用栈 catch 的 Promise 拒绝与原生异常，
// 避免控制台刷出 "Uncaught (in promise)" 噪声（典型来源：懒加载路由分块瞬时拉取失败、
// 个别依赖内部的未处理拒绝）。仅做诊断性记录并 preventDefault 抑制默认报错，不阻断应用运行。
window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason
  // reason 可能是 Error 实例，也可能是普通对象（如某些依赖自定义的错误 DTO）
  const desc =
    reason && reason.stack
      ? reason.stack
      : reason && (reason.message || reason.name)
        ? `${reason.name || 'Error'}: ${reason.message}`
        : String(reason)
  console.warn('[global] 未处理的 Promise 拒绝（已捕获，避免控制台报错）:', desc)
  // 阻止浏览器将其作为 "Uncaught (in promise)" 默认上报
  if (typeof event.preventDefault === 'function') event.preventDefault()
})
window.addEventListener('error', (event) => {
  // 仅记录脚本运行时错误；资源的加载失败（img/script 404）由浏览器自行处理，不在此拦截
  if (event.message && !event.filename) {
    console.warn('[global] 全局错误（已捕获）:', event.message)
  }
})

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/global.scss'

// 全局安全的 ElMessage：页面隐藏/恢复中时静默丢弃，防止 DOM 插入激活最小化窗口
import { ElMessage } from './utils/message'

// 主题初始化：在 Vue 挂载前设置 data-theme 属性，避免主题闪烁
// 此处直接读取 localStorage 并设置属性，无需等待 Pinia 初始化
const savedTheme = localStorage.getItem('admin_theme') || 'macaron'
document.documentElement.setAttribute('data-theme', savedTheme)

const app = createApp(App)

// 注册 Element Plus 图标（全局组件，供菜单/按钮使用）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
// ElementPlus 插件内部会注册 $message 全局属性（指向原始版本），
// 必须在 app.use(ElementPlus) 之后再覆盖为安全版本，否则会被插件覆盖
app.use(ElementPlus, { locale: undefined })

// 覆盖 ElementPlus 注入的原始 $message，使 this.$message 走安全包装器
app.config.globalProperties.$message = ElMessage

app.mount('#app')