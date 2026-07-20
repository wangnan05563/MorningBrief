/**
 * 路由配置 + RBAC 守卫
 *
 * 路由结构：
 * - /login          公开页面（无需登录）
 * - /               主布局（需登录），子路由按职能分组
 *
 * 菜单分组（meta.group）：
 *   内容运营  - 内容审核、频道管理、队列管理
 *   广告管理  - 广告素材、投放规则、排期日历
 *   数据分析  - 数据统计
 *   AI 自动化 - 工作流监控、AI 服务（仅 admin）
 *   系统配置  - 通知管理、内网穿透（仅 admin）
 *   维护工具  - 数据库维护、系统清理、参数计算器（仅 admin）
 *   帮助      - 帮助文档、关于
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
        meta: { title: '内容审核', icon: 'Document', group: '内容运营' },
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
        meta: { title: '广告素材', icon: 'PictureFilled', group: '广告管理' },
      },
      {
        path: 'ads/placements',
        name: 'AdPlacements',
        component: () => import('../views/ad/AdPlacements.vue'),
        meta: { title: '投放规则', icon: 'Setting', group: '广告管理' },
      },
      {
        path: 'ads/schedule',
        name: 'AdSchedule',
        component: () => import('../views/ad/AdSchedule.vue'),
        meta: { title: '排期日历', icon: 'Calendar', group: '广告管理' },
      },
      {
        path: 'stats',
        name: 'Stats',
        component: () => import('../views/stats/StatsOverview.vue'),
        meta: { title: '数据统计', icon: 'DataLine', group: '数据分析' },
      },
      {
        path: 'channels',
        name: 'Channels',
        component: () => import('../views/channel/ChannelManagement.vue'),
        meta: { title: '频道管理', icon: 'Menu', group: '内容运营' },
      },
      {
        path: 'queue',
        name: 'Queue',
        component: () => import('../views/queue/QueueManagement.vue'),
        meta: { title: '队列管理', icon: 'Operation', group: '内容运营' },
      },
      {
        path: 'workflows',
        name: 'Workflows',
        component: () => import('../views/workflow/WorkflowList.vue'),
        meta: { title: '工作流监控', icon: 'Monitor', group: 'AI 自动化', requireRole: 'admin' },
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
        meta: { title: '内网穿透', icon: 'Connection', group: '系统配置', requireRole: 'admin' },
      },
      {
        path: 'ai-config',
        name: 'AIConfig',
        component: () => import('../views/ai/AIConfig.vue'),
        meta: { title: 'AI 服务', icon: 'Cpu', group: 'AI 自动化', requireRole: 'admin' },
      },
      {
        path: 'notification',
        name: 'NotificationConfig',
        component: () => import('../views/notification/NotificationConfig.vue'),
        meta: { title: '通知管理', icon: 'Bell', group: '系统配置', requireRole: 'admin' },
      },
      {
        path: 'tools/calculator',
        name: 'ParamCalculator',
        component: () => import('../views/tools/ParamCalculator.vue'),
        meta: { title: '参数计算器', icon: 'Stopwatch', group: '维护工具', requireRole: 'admin' },
      },
      {
        path: 'db-admin',
        name: 'DatabaseAdmin',
        component: () => import('../views/maintenance/DatabaseAdmin.vue'),
        meta: { title: '数据库维护', icon: 'Coin', group: '维护工具', requireRole: 'admin' },
      },
      {
        path: 'maintenance',
        name: 'Maintenance',
        component: () => import('../views/maintenance/Maintenance.vue'),
        meta: { title: '系统清理', icon: 'Brush', group: '维护工具', requireRole: 'admin' },
      },
      {
        path: 'help',
        name: 'Help',
        component: () => import('../views/help/Help.vue'),
        meta: { title: '帮助文档', icon: 'QuestionFilled', group: '帮助' },
      },
      {
        path: 'about',
        name: 'About',
        component: () => import('../views/about/About.vue'),
        meta: { title: '关于', icon: 'InfoFilled', group: '帮助' },
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
