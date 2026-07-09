/**
 * 应用入口：创建 Vue 实例 + 挂载插件
 *
 * 插件加载顺序：Pinia（状态）→ Router（路由）→ Element Plus（UI）
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/global.scss'

const app = createApp(App)

// 注册 Element Plus 图标（全局组件，供菜单/按钮使用）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: undefined }) // 默认中文

app.mount('#app')
