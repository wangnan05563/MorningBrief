<template>
  <div class="m-app">
    <header class="m-appbar">
      <span class="m-appbar__title">{{ title }}</span>
    </header>

    <main class="m-content">
      <router-view />
    </main>

    <nav class="m-tabbar">
      <router-link
        v-for="tab in tabs"
        :key="tab.name"
        :to="tab.to"
        class="m-tabbar__item"
        active-class="m-tabbar__item--active"
      >
        <el-icon class="m-tabbar__icon"><component :is="tab.icon" /></el-icon>
        <span class="m-tabbar__label">{{ tab.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'

const route = useRoute()
const userStore = useUserStore()

// 基础底部标签；「管理」仅管理员可见（与路由 requireRole 一致）
const allTabs = [
  { name: 'home', to: '/m/home', label: '首页', icon: 'HomeFilled' },
  { name: 'review', to: '/m/review', label: '审批', icon: 'Document' },
  { name: 'message', to: '/m/message', label: '消息', icon: 'Bell' },
  { name: 'manage', to: '/m/manage', label: '管理', icon: 'Setting', adminOnly: true },
  { name: 'mine', to: '/m/mine', label: '我的', icon: 'User' },
]

const tabs = computed(() =>
  allTabs.filter((t) => !t.adminOnly || userStore.isAdmin)
)

const title = computed(
  () => route.meta.title || titleMap[route.name] || '运营助手'
)

const titleMap = {
  home: '运营助手',
  review: '内容审批',
  message: '消息中心',
  manage: '管理',
  mine: '我的',
}
</script>

<style scoped>
.m-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh; /* 移动端动态视口，避开地址栏 */
  background: #f5f6f8;
  color: #1f2329;
}

.m-appbar {
  flex: 0 0 auto;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-bottom: 1px solid #ebedf0;
  position: sticky;
  top: 0;
  z-index: 10;
  padding-top: env(safe-area-inset-top);
}

.m-appbar__title {
  font-size: 17px;
  font-weight: 600;
}

.m-content {
  flex: 1 1 auto;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

.m-tabbar {
  flex: 0 0 auto;
  display: flex;
  background: #fff;
  border-top: 1px solid #ebedf0;
  padding-bottom: env(safe-area-inset-bottom);
}

.m-tabbar__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 6px 0 4px;
  color: #8a8f99;
  text-decoration: none;
  font-size: 11px;
}

.m-tabbar__item--active {
  color: var(--el-color-primary, #409eff);
}

.m-tabbar__icon {
  font-size: 22px;
  margin-bottom: 2px;
}
</style>
