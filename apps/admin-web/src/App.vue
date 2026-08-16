<template>
  <router-view />
</template>

<script setup>
// 根组件仅承载 router-view，布局由 Layout.vue / MobileLayout.vue 处理。
//
// 移动端自动触发（参考 Karpathy-Wiki 的 useIsMobile）：
// 用 matchMedia 判定视口是否手机宽度（<768px），是则自动切到 /m 命名空间（移动端外壳），
// 否则留在桌面端。关键——DevTools 设备工具栏只改视口、不触发路由导航，
// 因此必须在 onMounted + watch(isMobile) 两处都做重定向，才能覆盖"开设备模拟即进移动端"。
import { watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useIsMobile, setForcedMode, resolveMode } from './composables/useIsMobile'

const router = useRouter()
const route = useRoute()
const { isMobile } = useIsMobile()

// ?mode=mobile|desktop|auto 会话级覆盖：访问带该 query 的 URL 即写入 sessionStorage，
// 之后即使去掉 query 也保持（便于在宽屏强制预览移动端、或反之）。auto 恢复跟随视口。
function applyModeOverride() {
  const m = route.query.mode
  if (m === 'mobile' || m === 'desktop' || m === 'auto') {
    setForcedMode(m)
    isMobile.value = resolveMode()
  }
}
watch(() => route.query.mode, applyModeOverride, { immediate: true })

// 根据「当前是否移动端路由」+「登录态」计算应跳转的目标；已在正确侧则返回 null
function resolveTarget() {
  const onMobileRoute = route.path.startsWith('/m')
  const role = localStorage.getItem('admin_role')
  if (isMobile.value && !onMobileRoute) {
    return role ? '/m/home' : '/m/login'
  }
  if (!isMobile.value && onMobileRoute) {
    return role ? '/review' : '/login'
  }
  return null
}

function syncModeRoute() {
  const target = resolveTarget()
  if (target && target !== route.path) {
    // 目标路由为懒加载分块；若分块瞬时拉取失败（dev HMR 中断 / 网络抖动），
    // router.replace 返回的 Promise 会 reject。此处 catch 避免冒泡为
    // "Uncaught (in promise) TypeError: Failed to fetch dynamically imported module"
    router
      .replace(target)
      .catch((err) => console.warn('[App] 路由重定向被拒绝（已静默处理）:', err?.message || err))
  }
}

onMounted(syncModeRoute)
watch(isMobile, syncModeRoute)
</script>

<style>
#app {
  width: 100%;
  height: 100vh;
}
</style>
