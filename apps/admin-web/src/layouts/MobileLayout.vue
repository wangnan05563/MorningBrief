<template>
  <div class="m-app">
    <header class="m-appbar">
      <!-- T02511（FR-UX-602）：hidden 子页（管理下的 7 个二级页）此前只有一枚底部 tab 条，
           进来之后回不到上一级——ACC-UX-601#2 要求「从 /m/manage/users 可一键返回 /m/manage」。
           返回目标按路由逐级上溯算出来，不写死：以后再加二级页自动就有返回键。 -->
      <button
        v-if="backTo"
        type="button"
        class="m-appbar__back"
        data-guide="mobile-appbar-back"
        :aria-label="`返回${backTo.label}`"
        @click="goBack"
      >
        <el-icon><ArrowLeft /></el-icon>
        <!-- T02512（FR-UX-603）：只有箭头时「回到哪一层」要靠猜，把上级名字写出来 -->
        <span class="m-appbar__back-label">{{ backTo.label }}</span>
      </button>
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
        :aria-label="tab.ariaLabel"
      >
        <span class="m-tabbar__icon-wrap">
          <el-icon class="m-tabbar__icon"><component :is="tab.icon" /></el-icon>
          <span
            v-if="tab.badge"
            class="m-tabbar__badge"
            :data-guide="`mobile-tab-badge-${tab.name}`"
          >{{ tab.badge }}</span>
        </span>
        <span class="m-tabbar__label">{{ tab.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { getDashboardSummary } from '../api/mobile'
import { subscribe } from '../utils/sse'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 基础底部标签；「管理」仅管理员可见（与路由 requireRole 一致）
// badgeKind：角标数字的语义前缀，用于 aria-label——「3」单独念出来没有意义，
// 读屏用户需要知道这是待办数还是未读数（T02510 / I27）
const allTabs = [
  { name: 'home', to: '/m/home', label: '首页', icon: 'HomeFilled' },
  { name: 'review', to: '/m/review', label: '审批', icon: 'Document', badgeKind: '待办' },
  { name: 'message', to: '/m/message', label: '消息', icon: 'Bell', badgeKind: '未读' },
  { name: 'manage', to: '/m/manage', label: '管理', icon: 'Setting', adminOnly: true },
  { name: 'mine', to: '/m/mine', label: '我的', icon: 'User' },
]

// 角标计数来源：/m/dashboard-summary 已经聚合了 pending_review / unread_message
// （移动端首页 Home.vue 一直在用，这里只是把同一份数据提到壳层，不新增接口）
const pendingReview = ref(0)
const unreadMessage = ref(0)
// 计数是否拿到过：没拿到过就一个角标都不画。
// 加载失败时保留上一次的值（而不是归零）——归零会让用户以为「没有待办了」，
// 那比不显示角标更危险（这正是 I27 要解决的「必须逐个 tab 点进去看」的反面）
const countsKnown = ref(false)

// 数字折叠：超过 99 显示 99+（角标是 10px 小字，三位数已经会顶到相邻 tab）
const BADGE_FOLD_AT = 99
const foldCount = (n) => (n > BADGE_FOLD_AT ? `${BADGE_FOLD_AT}+` : String(n))

// 刷新节流：壳层的刷新点有 4 个（进入、切 tab、回前台、SSE 完成事件），
// 不打节流会变成「每次点 tab 都打一次聚合接口」——那才真的违反 NFR-UX-03
const REFRESH_MIN_INTERVAL_MS = 10_000
let lastRefreshAt = 0
let refreshing = false

async function refreshCounts({ force = false } = {}) {
  // 该接口是 B 端鉴权；未登录（理论上到不了这个布局）不请求，避免 401 弹提示
  if (!userStore.role) return
  const now = Date.now()
  if (!force && now - lastRefreshAt < REFRESH_MIN_INTERVAL_MS) return
  if (refreshing) return
  refreshing = true
  lastRefreshAt = now
  try {
    const data = await getDashboardSummary()
    pendingReview.value = data?.pending_review ?? 0
    unreadMessage.value = data?.unread_message ?? 0
    countsKnown.value = true
  } catch (e) {
    // 静默：角标是辅助提示，失败时保持上一次的值即可，不值得为它弹 toast
    // （FR-UX-303 的提示去重要求下，壳层的非关键失败更应该沉默）
    console.warn('[mobile-tabbar] 待办/未读计数刷新失败，沿用上次值:', e?.message || e)
  } finally {
    refreshing = false
  }
}

const tabs = computed(() =>
  allTabs
    .filter((t) => !t.adminOnly || userStore.isAdmin)
    .map((t) => {
      const raw =
        t.name === 'review'
          ? pendingReview.value
          : t.name === 'message'
            ? unreadMessage.value
            : 0
      const badge = countsKnown.value && raw > 0 ? foldCount(raw) : ''
      return {
        ...t,
        badge,
        ariaLabel: badge ? `${t.label}（${t.badgeKind} ${badge}）` : t.label,
      }
    })
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

/**
 * hidden 子页的返回目标（T02511）。
 *
 * 逐级砍掉路径最后一段，取**第一个真实存在的路由**作为上级：
 * `/m/manage/users` → `/m/manage`；假以常日再加 `/m/manage/ads/edit` 也能自动上溯。
 * 一路砍到只剩 `/m` 都找不到时兜底回首页——「没有返回键」和「返回键回到首页」
 * 都比「点了没反应」好。底部 tab 上的页面（home/review/message/mine/manage）不显示返回键，
 * 它们本来就在一级导航里。
 */
const backTo = computed(() => {
  if (!route.meta.hidden) return null
  const segs = route.path.split('/').filter(Boolean) // ['m','manage','users']
  while (segs.length > 1) {
    segs.pop()
    const path = '/' + segs.join('/')
    const resolved = safeResolve(path)
    if (resolved) return { path, label: resolved.meta?.title || titleMap[resolved.name] || '上级' }
  }
  return { path: '/m/home', label: '首页' }
})

/** resolve 对未知路径会抛错；这里只关心「存不存在」，异常吞掉当作不存在 */
function safeResolve(path) {
  try {
    const r = router.resolve(path)
    return r.matched?.length ? r : null
  } catch {
    return null
  }
}

function goBack() {
  if (!backTo.value) return
  router.push(backTo.value.path).catch((err) => console.warn('[mobile-back] 返回被拒绝:', err?.message || err))
}

// SSE：工作流完成 = 有新节目进入待审队列，是「停在审批 tab 也能感知新待办」的实时通道。
// 这里不引入任何轮询——刷新全部由事件/交互触发（NFR-UX-03）
let unsubscribeSse = null
function onWorkflowCompleted() {
  refreshCounts({ force: true })
}
function onVisibility() {
  if (!document.hidden) refreshCounts({ force: true })
}

onMounted(() => {
  refreshCounts()
  unsubscribeSse = subscribe('workflow.completed', onWorkflowCompleted)
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  if (unsubscribeSse) unsubscribeSse()
  document.removeEventListener('visibilitychange', onVisibility)
})

// 切 tab 后回前台时的补刷：用户在审批页处理完再切走，计数已变，节流窗口过了就更新
watch(
  () => route.name,
  () => refreshCounts()
)
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

/* 返回键绝对定位在左侧：appbar 用 justify-content:center 居中标题，
   直接把按钮塞进 flex 流会把标题顶偏 */
.m-appbar__back {
  position: absolute;
  left: 4px;
  top: 50%;
  transform: translateY(-50%);
  min-width: 40px;
  height: 40px;
  max-width: 40%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 0 8px 0 4px;
  border: none;
  background: transparent;
  color: #1f2329;
  font-size: 20px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
/* 上级名称：小一号，超长直接截断——标题居中显示，返回区不能把它顶走（375px 下也稳） */
.m-appbar__back-label {
  font-size: 13px;
  line-height: 1;
  max-width: 8em;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.m-appbar__back:active {
  opacity: 0.6;
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

/* 角标挂在图标右上角：图标是 22px，label 只有 11px，压在文字上会把 label 糊住 */
.m-tabbar__icon-wrap {
  position: relative;
  display: inline-flex;
}

.m-tabbar__badge {
  position: absolute;
  top: -3px;
  right: -13px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  box-sizing: border-box;
  border-radius: 8px;
  /* 底色取深红而非 #E6544A：白字压 #E6544A 只有 ~3.4:1，10px 小字不达 WCAG AA；
     #C9433B 配白字 ≈ 4.8:1（与 T02728 漏斗角标同一口径，避免再犯一次同色不可读） */
  background: #c9433b;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
  pointer-events: none;
}
</style>
