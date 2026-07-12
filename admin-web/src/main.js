/**
 * 应用入口：创建 Vue 实例 + 挂载插件
 *
 * 插件加载顺序：Pinia（状态）→ Router（路由）→ Element Plus（UI）
 * - 全局注入安全的 ElMessage，防止最小化时弹窗激活浏览器窗口
 */
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