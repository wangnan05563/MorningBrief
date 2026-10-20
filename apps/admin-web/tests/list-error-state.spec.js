import { test, expect } from '@playwright/test'
import {
  setLoginState,
  useMobileViewport,
  queueStatsResponse,
  queueConfigResponse,
  queueTasksResponse,
  channelsListResponse,
  workflowListResponse,
  statsOverviewResponse,
} from './helpers/mock'

/**
 * 列表/详情错误态与重试 E2E（T02496：FR-UX-302 / ACC-UX-301 第 3 条）
 *
 * 核心断言只有一句话：请求失败时界面不得显示「暂无数据 / 队列为空 / 暂无频道」这类空态，
 * 必须给出页内错误态与重试入口。每条用例都同时断言「错误态出现」与「空态文案不存在」。
 *
 * 覆盖 PRD 列出的取证点：
 * - C5  ChannelManagement（旧代码只有 try/finally，失败落空态）
 * - M54 DatabaseAdmin（失败置空 + 写操作未禁用）
 * - E1  WorkflowList（无 catch、无独立刷新入口）
 * - ACC-UX-301#3 队列页断网显示「加载失败，重试」而非「暂无数据」（PC + 移动端都验）
 * - 趋势图空档期不再画 0 折线（hasTrend 改看实际数据点）
 */

// 第一次请求失败、之后成功的路由：模拟「接口挂了 → 点重试恢复」
async function failFirstThenSucceed(page, pattern, json) {
  let calls = 0
  await page.route(pattern, async (route) => {
    calls += 1
    if (calls === 1) return route.abort()
    return route.fulfill({ json })
  })
}

// 各页面都会订阅 SSE，后端没起时 ECONNREFUSED 会让用例 flaky，统一给一条空流
async function stubSse(page) {
  await page.route('**/admin/api/v1/events/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
  )
}

test.describe('列表错误态与重试', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubSse(page)
  })

  test('PC 队列页：任务接口失败显示加载失败而非「暂无队列任务」', async ({ page }) => {
    await page.route('**/admin/api/v1/queue/stats', (route) => route.fulfill({ json: queueStatsResponse }))
    await page.route('**/admin/api/v1/queue/config', (route) => route.fulfill({ json: queueConfigResponse }))
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    await page.route('**/admin/api/v1/queue/tasks*', (route) => route.abort())

    await page.goto('/queue')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(banner).toContainText('加载失败')
    // 关键：空态文案不得出现（旧代码失败后正是这条文案骗人）
    await expect(page.getByText('暂无队列任务')).toHaveCount(0)
    // 错误态必须自带重试按钮
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  test('PC 队列页：重试成功后错误态消失并恢复列表', async ({ page }) => {
    await page.route('**/admin/api/v1/queue/stats', (route) => route.fulfill({ json: queueStatsResponse }))
    await page.route('**/admin/api/v1/queue/config', (route) => route.fulfill({ json: queueConfigResponse }))
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    await failFirstThenSucceed(page, '**/admin/api/v1/queue/tasks*', queueTasksResponse)

    await page.goto('/queue')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })

    await banner.getByRole('button', { name: '重试', exact: true }).click()
    await expect(banner).toHaveCount(0)
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: 30000 })
  })

  test('移动端队列页：断网显示「加载失败，重试」而非「队列为空」', async ({ page }) => {
    await page.route('**/admin/api/v1/queue/stats', (route) => route.fulfill({ json: queueStatsResponse }))
    await page.route('**/admin/api/v1/queue/tasks*', (route) => route.abort())

    // 移动端队列要在手机视口下测：桌面视口打开 /m/… 会被跨端策略换到 PC 队列页（T02511）
    await useMobileViewport(page)
    await page.goto('/m/manage/queue')
    await expect(page.getByText(/加载失败/)).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('队列为空')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  test('频道管理：列表接口失败显示错误态而非「暂无频道」', async ({ page }) => {
    await page.route('**/admin/api/v1/channels*', (route) => route.abort())

    await page.goto('/channels')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('暂无频道')).toHaveCount(0)
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  test('工作流列表：接口失败显示错误态，且页面有独立刷新入口', async ({ page }) => {
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    await page.route('**/admin/api/v1/workflows*', (route) => route.abort())

    await page.goto('/workflows')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('暂无工作流')).toHaveCount(0)
    // E1 的另一半：此前没有刷新入口，只能靠改筛选条件触发重载
    await expect(page.getByRole('button', { name: '刷新', exact: true })).toBeVisible()
  })

  test('数据管理：表清单失败显示错误态而非「请从左侧选择一张表」', async ({ page }) => {
    await page.route('**/admin/api/v1/db-admin/tables*', (route) => route.abort())

    await page.goto('/db-admin')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('请从左侧选择一张表')).toHaveCount(0)
  })

  test('趋势图：空档期（values 全为 null）不画 0 折线', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/overview*', (route) => route.fulfill({ json: statsOverviewResponse }))
    await page.route('**/admin/api/v1/stats/trend*', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          // dates 恒等于区间天数（这正是旧 hasTrend 误判的来源），values 全 null 表示这些天没有记录
          data: { dates: ['2026-10-12', '2026-10-13', '2026-10-14'], values: [null, null, null] },
        },
      })
    )

    await page.goto('/stats')
    await expect(page.getByText('暂无趋势数据')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('canvas')).toHaveCount(0)
  })

  test('趋势图：接口失败显示错误态与重试', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/overview*', (route) => route.fulfill({ json: statsOverviewResponse }))
    await failFirstThenSucceed(page, '**/admin/api/v1/stats/trend*', {
      code: 0,
      message: 'success',
      data: { dates: ['2026-10-12', '2026-10-13'], values: [3, 5] },
    })

    await page.goto('/stats')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })

    await banner.getByRole('button', { name: '重试', exact: true }).click()
    await expect(banner).toHaveCount(0)
    await expect(page.locator('canvas')).toBeVisible({ timeout: 30000 })
  })
})
