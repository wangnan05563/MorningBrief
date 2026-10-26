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
  // vite 首次按需编译路由组件可能耗时 15-25s：真要放宽就写在具体断言上（{ timeout: N }）；
  // test.use({ expect: { timeout } }) 在 Playwright 1.61 是空选项，会被静默忽略（T02778）

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

  // ---------------------------------------------------------------
  // T02626（FR-UX-302）：详情页与统计/管理页的错误态。
  // 每页只断言同一件事——失败时给出页内错误横幅与重试入口，
  // 且不能把「没取到」说成「没有数据」。数据本身在其它用例覆盖。
  // ---------------------------------------------------------------

  test('审核详情：详情接口失败显示错误态而不是空稿件', async ({ page }) => {
    await page.route(/\/admin\/api\/v1\/reviews\/\d+$/, (route) => route.abort())

    await page.goto('/review/1')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
    // 稿件区未渲染（不是「稿件全文」空壳）
    await expect(page.getByText('稿件全文')).toHaveCount(0)
  })

  test('工作流详情：详情接口失败显示错误态，重试取到后时间线才出现', async ({ page }) => {
    // 详情请求可能带 silent 之类的 query，按后缀匹配会把它们漏给 vite 代理
    await failFirstThenSucceed(page, '**/admin/api/v1/workflows/1*', {
      code: 0,
      message: 'success',
      data: {
        workflow_id: 1,
        source: 'crawler',
        status: 'running',
        // 只给 crawl 一步，其余步骤由前端补成 pending —— 用来区分「真数据」与「空壳」
        steps: [{ name: 'crawl', status: 'success' }],
      },
    })

    await page.goto('/workflows/1')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    // 六步流水线未渲染：detail 为 {} 时那六行全是「等待中」，等于替后端断言「还没开始跑」
    await expect(page.getByText('等待中')).toHaveCount(0)

    // 重试必须打回详情接口（接到别的 loader 上时这里既不会消失也不会有数据）
    await banner.getByRole('button', { name: '重试', exact: true }).click()
    await expect(banner).toHaveCount(0)
    await expect(page.getByText('等待中').first()).toBeVisible({ timeout: 30000 })
  })

  test('素材库：列表接口失败显示错误态而非「没有匹配的素材」', async ({ page }) => {
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    await page.route(/\/admin\/api\/v1\/materials\//, (route) => route.abort())

    await page.goto('/channels/material-library')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('没有匹配的素材')).toHaveCount(0)
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  test('COS 文件：对象列表失败显示错误态而非「该目录下暂无内容」', async ({ page }) => {
    await page.route('**/admin/api/v1/cos/status', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { configured: true, backup_keep_count: 5 } } })
    )
    await page.route('**/admin/api/v1/cos/objects*', (route) => route.abort())

    await page.goto('/cos-files')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('该目录下暂无内容')).toHaveCount(0)
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  test('找书工具：随机抽取失败显示错误态而非「没有匹配的书目」', async ({ page }) => {
    await page.route('**/admin/api/v1/ebooks/index/status', (route) =>
      route.fulfill({
        json: { code: 0, message: 'success', data: { ready: true, book_count: 10, category_count: 3, built_at: null, build: {} } },
      })
    )
    await page.route('**/admin/api/v1/ebooks/categories*', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { categories: [] } } })
    )
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    await page.route('**/admin/api/v1/ebooks/random*', (route) => route.abort())

    await page.goto('/ebooks')
    await page.getByRole('button', { name: '随机', exact: true }).click()
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(/没有匹配的书目/)).toHaveCount(0)
  })

  test('广告素材：列表失败显示错误态而非「暂无广告素材」', async ({ page }) => {
    await page.route('**/admin/api/v1/ads/materials*', (route) => route.abort())

    await page.goto('/ads/materials')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(/暂无广告素材/)).toHaveCount(0)
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  /**
   * T02626 首版的真实事故：这几个页面把 useLoadState 的 ref 当布尔直接用在模板里
   * （`v-if="listLoad.isError"`），拿到的其实是 ref 对象——恒真。于是**成功取数时**
   * 错误横幅也一直挂着、提交按钮恒禁用、空态永不出现；上面每条失败路径用例却照样全绿。
   * 所以必须有一组成功路径断言：横幅不在，内容在。
   */
  test('成功取数时广告素材/频道健康/LLM 指标都不挂错误横幅', async ({ page }) => {
    await page.route('**/admin/api/v1/ads/materials*', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            total: 1,
            list: [{ id: 1, name: '占位音频', description: '测试', duration: 10, is_default: false }],
          },
        },
      })
    )
    await page.route('**/admin/api/v1/stats/channel-health*', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            channels: [
              {
                channel_id: 1,
                name: '科技前沿',
                is_active: true,
                health_status: 'healthy',
                today_pending: 0,
                range_total: 1,
                rss_source_count: 1,
                keyword_count: 2,
                daily_trend: [],
              },
            ],
            summary: { healthy: 1, warning: 0, critical: 0, total: 1 },
            meta: {},
          },
        },
      })
    )
    await page.route('**/admin/api/v1/stats/llm-metrics*', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            total_calls: 3,
            triggered: 1,
            improved: 1,
            not_improved: 0,
            trigger_rate: 0.33,
            improve_rate: 1,
            not_improve_rate: 0,
            started_at: '2026-10-26T08:00:00',
            pid: 1,
            meta: {},
          },
        },
      })
    )

    const cases = [
      ['/ads/materials', '[data-guide="ads-materials-table"] .el-table__row'],
      ['/stats/channel-health', '[data-guide="channel-health-cards"]'],
      ['/stats/llm-metrics', '[data-guide="llm-metrics-rates"]'],
    ]
    for (const [path, content] of cases) {
      await page.goto(`/news${path}`)
      await expect(page.locator(content).first()).toBeVisible({ timeout: 30000 })
      await expect(page.locator('.list-load-error')).toHaveCount(0)
    }
  })

  test('广告投放：列表失败显示错误态而非「暂无投放规则」', async ({ page }) => {
    await page.route('**/admin/api/v1/ads/placements*', (route) => route.abort())

    await page.goto('/ads/placements')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(/暂无投放规则/)).toHaveCount(0)
  })

  test('频道健康度：接口失败显示错误态而非「暂无频道数据」', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/channel-health*', (route) => route.abort())

    await page.goto('/stats/channel-health')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('暂无频道数据')).toHaveCount(0)
  })

  test('LLM 指标：接口失败不显示「暂无 LLM 调用数据」', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/llm-metrics*', (route) => route.abort())

    await page.goto('/stats/llm-metrics')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(/暂无 LLM 调用数据/)).toHaveCount(0)
  })

  test('RSS 健康度：接口失败不显示「暂无 RSS 源」也不会画成 0 个失败源', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/rss-health*', (route) => route.abort())

    await page.goto('/stats/rss-health')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('暂无 RSS 源')).toHaveCount(0)
    await expect(page.getByText('全局源清单总数')).toHaveCount(0)
  })

  test('自动审批：统计与历史各自显示错误态而非「暂无审批记录」', async ({ page }) => {
    await page.route('**/admin/api/v1/auto-review/config', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            enabled: false,
            require_content_safe: true,
            require_steps_first_success: true,
            keyword_whitelist: [],
            updated_at: null,
            skipped_rules: [],
          },
        },
      })
    )
    await page.route('**/admin/api/v1/auto-review/stats*', (route) => route.abort())
    await page.route('**/admin/api/v1/auto-review/history*', (route) => route.abort())

    await page.goto('/auto-review')
    const banners = page.locator('.list-load-error')
    await expect(banners).toHaveCount(2, { timeout: 30000 })
    await expect(page.getByText('暂无审批记录')).toHaveCount(0)
  })
})
