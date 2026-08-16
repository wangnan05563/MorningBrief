import { test, expect } from '@playwright/test'
import { setLoginState, rssHealthResponse } from './helpers/mock'

/**
 * RSS 源状态页面 E2E 测试
 *
 * 覆盖：
 * - 汇总卡片显示（总数/正常/失败/未巡检）
 * - 源状态表格渲染
 * - 立即巡检按钮触发 refresh=true 请求
 * - 状态筛选
 */
test.describe('RSS 源状态页面', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/stats/rss-health*', async (route) => {
      await route.fulfill({ json: rssHealthResponse })
    })
  })

  test('汇总卡片显示', async ({ page }) => {
    await page.goto('/stats/rss-health')

    await expect(page.getByText('RSS 源可达性').first()).toBeVisible({ timeout: 30000 })

    // 4 个汇总卡片：源总数/正常/失败/未巡检
    await expect(page.getByText('源总数').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('正常').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('失败').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('未巡检').first()).toBeVisible({ timeout: 30000 })
  })

  test('源状态表格渲染', async ({ page }) => {
    await page.goto('/stats/rss-health')

    // 表格应包含 3 个 mock 源
    await expect(page.getByText('人民网-国内').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('rsshub 失效源').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('未巡检源').first()).toBeVisible({ timeout: 30000 })

    // 失败源的连续失败徽章应渲染（badge value=3）
    await expect(page.locator('.el-badge__content').filter({ hasText: '3' })).toBeVisible({ timeout: 30000 })
  })

  test('立即巡检触发 refresh=true', async ({ page }) => {
    let lastUrl = null
    await page.route('**/admin/api/v1/stats/rss-health*', async (route) => {
      lastUrl = route.request().url()
      await route.fulfill({ json: rssHealthResponse })
    })

    await page.goto('/stats/rss-health')
    await expect(page.getByText('人民网-国内').first()).toBeVisible({ timeout: 30000 })
    // 首次加载不应带 refresh=true
    expect(lastUrl).not.toContain('refresh=true')

    // 点击"立即巡检"按钮
    await page.getByRole('button', { name: '立即巡检' }).click()

    // 应触发带 refresh=true 的请求
    await expect.poll(() => lastUrl).toContain('refresh=true')
  })

  test('状态筛选', async ({ page }) => {
    await page.goto('/stats/rss-health')
    await expect(page.getByText('人民网-国内').first()).toBeVisible({ timeout: 30000 })

    // 默认显示全部 3 条
    expect(await page.locator('.el-table__row').count()).toBe(3)

    // 切换到"失败"筛选：仅显示 rsshub 失效源
    await page.locator('.el-radio-button').filter({ hasText: '失败' }).click()

    await expect(page.locator('.el-table__row')).toHaveCount(1, { timeout: 5000 })
    await expect(page.locator('.el-table__row').first()).toContainText('rsshub 失效源')
  })
})

