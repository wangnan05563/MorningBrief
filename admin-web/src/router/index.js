/**
 * 路由配置 + RBAC 守卫
 *
 * 路由结构：
 * - /login          公开页面（无需登录）
 * - /               主布局（需登录），子路由为各功能页
 *   - /review       内容审核（operator + admin）
 *   - /ads/*        广告管理（operator + admin）
 *   - /stats        数据统计（operator + admin）
 *   - /workflows/*  工作流监控（仅 admin）
 */
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

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
