/**
 * 路由配置 + RBAC 守卫
 *
 * 路由结构：
 * - /login          公开页面（无需登录）
 * - /               主布局（需登录），子路由为各功能页
 *   - /review       内容审核（operator + admin）
 *   - /ads/*        广告管理（operator + admin）
 *   - /stats        数据统计（operator + admin）
 *   - /channels     频道管理（operator 只读 + admin 可操作）
 *   - /queue        队列管理（operator 只读 + admin 可操作）
 *   - /workflows/*  工作流监控（仅 admin）
 */
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from '../utils/message'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../layouts/Layout.vue'),
    redirect: '/review',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'review',
        name: 'Review',
        component: () => import('../views/review/ReviewList.vue'),
        meta: { title: '内容审核', icon: 'Document' },
      },
      {
        path: 'review/:id',
        name: 'ReviewDetail',
        component: () => import('../views/review/ReviewDetail.vue'),
        meta: { title: '审核详情', hidden: true },
      },
      {
        path: 'ads/materials',
        name: 'AdMaterials',
        component: () => import('../views/ad/AdMaterials.vue'),
        meta: { title: '广告素材', icon: 'PictureFilled' },
      },
      {
        path: 'ads/placements',
        name: 'AdPlacements',
        component: () => import('../views/ad/AdPlacements.vue'),
        meta: { title: '投放规则', icon: 'Setting' },
      },
      {
        path: 'ads/schedule',
        name: 'AdSchedule',
        component: () => import('../views/ad/AdSchedule.vue'),
        meta: { title: '排期日历', icon: 'Calendar' },
      },
      {
        path: 'stats',
        name: 'Stats',
        component: () => import('../views/stats/StatsOverview.vue'),
        meta: { title: '数据统计', icon: 'DataLine' },
      },
      {
        path: 'channels',
        name: 'Channels',
        component: () => import('../views/channel/ChannelManagement.vue'),
        meta: { title: '频道管理', icon: 'Menu' },
      },
      {
        path: 'queue',
        name: 'Queue',
        component: () => import('../views/queue/QueueManagement.vue'),
        meta: { title: '队列管理', icon: 'Operation' },
      },
      {
        path: 'workflows',
        name: 'Workflows',
        component: () => import('../views/workflow/WorkflowList.vue'),
        meta: { title: '工作流监控', icon: 'Monitor', requireRole: 'admin' },
      },
      {
        path: 'workflows/:id',
        name: 'WorkflowDetail',
        component: () => import('../views/workflow/WorkflowDetail.vue'),
        meta: { title: '工作流详情', hidden: true, requireRole: 'admin' },
      },
      {
        path: 'tunnel',
        name: 'Tunnel',
        component: () => import('../views/tunnel/Tunnel.vue'),
        meta: { title: '内网穿透', icon: 'Connection', requireRole: 'admin' },
      },
      {
        path: 'ai-config',
        name: 'AIConfig',
        component: () => import('../views/ai/AIConfig.vue'),
        meta: { title: 'AI 服务', icon: 'Cpu', requireRole: 'admin' },
      },
      {
        path: 'notification',
        name: 'NotificationConfig',
        component: () => import('../views/notification/NotificationConfig.vue'),
        meta: { title: '通知管理', icon: 'Bell', requireRole: 'admin' },
      },
      {
        path: 'tools/calculator',
        name: 'ParamCalculator',
        component: () => import('../views/tools/ParamCalculator.vue'),
        meta: { title: '参数计算器', icon: 'Stopwatch', requireRole: 'admin' },
      },
      {
        path: 'db-admin',
        name: 'DatabaseAdmin',
        component: () => import('../views/maintenance/DatabaseAdmin.vue'),
        meta: { title: '数据库维护', icon: 'Coin', requireRole: 'admin' },
      },
      {
        path: 'maintenance',
        name: 'Maintenance',
        component: () => import('../views/maintenance/Maintenance.vue'),
        meta: { title: '系统清理', icon: 'Brush', requireRole: 'admin' },
      },
    ],
  },
  // 404 兜底：未匹配路由统一回到审核页，避免白屏
  { path: '/:pathMatch(.*)*', redirect: '/review' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局守卫：登录校验 + 角色校验
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('admin_token')
  const role = localStorage.getItem('admin_role')

  // 公开页面直接放行
  if (to.meta.public) {
    next()
    return
  }

  // 未登录跳转登录页
  if (!token) {
    next('/login')
    return
  }

  // 角色校验（工作流监控仅 admin 可访问）
  if (to.meta.requireRole === 'admin' && role !== 'admin') {
    ElMessage.error('仅管理员可访问')
    next(false)
    return
  }

  next()
})

export default router
