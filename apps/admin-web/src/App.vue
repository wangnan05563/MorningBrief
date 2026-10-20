<template>
  <router-view />
</template>

<script setup>
// 根组件仅承载 router-view，布局由 Layout.vue / MobileLayout.vue 处理。
//
// 移动端自动触发（参考 Karpathy-Wiki 的 useIsMobile）：
// 用 matchMedia 判定视口是否手机宽度（<768px），是则自动切到 /m 命名空间（移动端外壳），
// 否则留在桌面端。关键——DevTools 设备工具栏只改视口、不触发路由导航，
// 因此必须在「路由就绪后」与「视口变化时」「路径变化时」三处都做重定向，
// 才能同时覆盖"开设备模拟即进移动端"和"直接深链进来就要换端"两种进入方式。
import { watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useIsMobile, setForcedMode, resolveMode } from './composables/useIsMobile'
import { crossEndTarget, isMobilePath } from './utils/urlState'

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
//
// T02511（FR-UX-602）：这里原来直接 `replace('/m/home')` / `replace('/review')`，
// 于是手机上打开 `/queue?status=failed` 这类深链会被**抹平成首页且丢掉 query**，
// PC 上访问 `/m/manage/users` 同理。现在按等价表换到对面同名页，
// 对不上的回对面首页并把原路径留在 `?from=` 里；query 永远跟着走。
// 未登录时把原始 fullPath 作为 `?redirect=` 交给登录页（登录页会 sanitizeRedirect 校验）。
//
// 端归属一律走 `isMobilePath()`：`startsWith('/m')` 会把 PC 的 `/materials`、`/maintenance`
// 误判成移动端路径（实测素材录入页被重定向到 `/review`）。
function resolveTarget() {
  const onMobileRoute = isMobilePath(route.path)
  const role = localStorage.getItem('admin_role')
  if (isMobile.value && !onMobileRoute) {
    if (!role) return { path: '/m/login', query: { redirect: route.fullPath } }
    return crossEndTarget(route.path, route.query, 'mobile')
  }
  if (!isMobile.value && onMobileRoute) {
    if (!role) return { path: '/login', query: { redirect: route.fullPath } }
    return crossEndTarget(route.path, route.query, 'desktop')
  }
  return null
}

function syncModeRoute() {
  const target = resolveTarget()
  if (!target || !target.path || target.path === route.path) return
  // 目标路由为懒加载分块；若分块瞬时拉取失败（dev HMR 中断 / 网络抖动），
  // router.replace 返回的 Promise 会 reject。此处 catch 避免冒泡为
  // "Uncaught (in promise) TypeError: Failed to fetch dynamically imported module"
  router
    .replace({ path: target.path, query: target.query })
    .catch((err) => console.warn('[App] 路由重定向被拒绝（已静默处理）:', err?.message || err))
}

// App.vue 挂载时，路由的首次导航往往还没解析完（子路由全是懒加载分块），
// 此时 `route.path` 还是起始位置的 `/`。在这里直接跳转会把深链**当成根路径处理**：
// 手机上打开 `/m/review?workflow_id=9` 被劫持到 `/m/home`，PC 上打开 `/m/...` 又因
// 判定不成立而不重定向——两头都不对，且 query 全程丢失。
// 因此首次同步必须等 `router.isReady()`，之后再由「视口 / 路径」变化驱动。
onMounted(() => {
  router.isReady().then(() => {
    applyModeOverride()
    syncModeRoute()
  })
})
watch(isMobile, syncModeRoute)
// 这里**不**监听 `route.path`：跨端换端已由 `router/index.js` 的 `beforeEach` 在导航阶段完成
// （那里拿到的 `to.path` 是解析完的目标，且早于组件挂载，不存在「首帧还是 `/`」的竞态）。
// 证伪对照（实测两组）：停用守卫、保留路径监听 → 7 条跨端/返回用例仍全绿；
// 保留守卫、去掉路径监听 → `url-state` 全部 20 条绿。两处都做同一件事只会多一次 replace，
// 于是分工定为：**守卫管导航，这里只管视口与 `mode=` 覆盖变化**。
</script>

<style>
#app {
  width: 100%;
  height: 100vh;
}
</style>
