import { test, expect } from '@playwright/test'
import { setLoginState, channelHealthResponse } from './helpers/mock'

/**
 * 频道健康度页面 E2E 测试
 *
 * 覆盖：
 * - 汇总卡片显示（healthy/warning/critical/total）
 * - 频道卡片渲染（含健康徽章）
 * - 切换回溯天数重新加载
 * - 折线口径标注（T02508 / FR-UX-503：仅趋势声明 + 具体统计区间）
 */
test.describe('频道健康度页面', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/stats/channel-health*', async (route) => {
      await route.fulfill({ json: channelHealthResponse })
    })
  })

  test('汇总卡片显示', async ({ page }) => {
    await page.goto('/stats/channel-health')

    // T00811：内容区标题已移除，标题改由导航栏展示（meta.title=频道健康度）
    await expect(page.getByText('频道健康度').first()).toBeVisible({ timeout: 30000 })

    // 4 个汇总卡片：健康/警告/严重/频道总数
    await expect(page.getByText('健康').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('警告').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('严重').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('频道总数').first()).toBeVisible({ timeout: 30000 })

    // 汇总数值：mock 数据 healthy=1, warning=1, critical=1, total=3
    const summaryValues = page.locator('.summary-value')
    await expect(summaryValues.filter({ hasText: '1' }).first()).toBeVisible({ timeout: 30000 })
    await expect(summaryValues.filter({ hasText: '3' }).first()).toBeVisible({ timeout: 30000 })
  })

  test('频道卡片渲染', async ({ page }) => {
    await page.goto('/stats/channel-health')

    // 3 个频道卡片应渲染：科技前沿/财经观察/主机游戏
    await expect(page.getByText('科技前沿').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('财经观察').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('主机游戏').first()).toBeVisible({ timeout: 30000 })

    // 每个频道卡片应含 mini 折线图 canvas
    await expect(page.locator('canvas').first()).toBeVisible({ timeout: 30000 })
  })

  test('切换回溯天数重新加载', async ({ page }) => {
    let callCount = 0
    let lastParams = null
    await page.route('**/admin/api/v1/stats/channel-health*', async (route) => {
      callCount++
      lastParams = route.request().url()
      await route.fulfill({ json: channelHealthResponse })
    })

    await page.goto('/stats/channel-health')
    await expect(page.getByText('科技前沿').first()).toBeVisible({ timeout: 30000 })
    const initialCount = callCount
    expect(lastParams).toContain('range_days=7')

    // 切换到"近 14 天"
    await page.locator('.el-radio-button').filter({ hasText: '近 14 天' }).click()

    await expect.poll(() => callCount).toBe(initialCount + 1)
    expect(lastParams).toContain('range_days=14')
  })

  // T02508（FR-UX-503）：卡片里的 mini 折线刻意不画坐标轴，那就必须
  // ① 写明"仅趋势"，② 把"近 N 天"落到具体日期窗口，③ 悬停能读到带单位的准确值
  test('折线口径：标注仅趋势并给出具体统计区间', async ({ page }) => {
    await page.goto('/stats/channel-health')

    const caption = page.locator('[data-guide="channel-health-trend-caption"]').first()
    await expect(caption).toContainText('仅趋势 · 未标刻度', { timeout: 30000 })

    // 统计区间直接来自后端下发的 daily_trend 首尾日期，不是前端按"今天"倒推
    await expect(page.locator('.window-note')).toContainText('2026-07-15 ~ 2026-07-21')
  })
})

