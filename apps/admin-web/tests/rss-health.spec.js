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
 * - 累计口径标注（T02508 / FR-UX-503：巡检状态存在进程内存，重启归零）
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

    // T00811：内容区标题已移除，标题改由导航栏展示（meta.title=RSS 源状态）
    await expect(page.getByText('RSS 源状态').first()).toBeVisible({ timeout: 30000 })

    // 4 个汇总卡片：全局源清单总数/正常/失败/未巡检
    // D46：这张卡数的是后端 rss.yaml 全局清单，标签必须自证归属，
    // 与频道健康度卡片的「本频道已配源」区分开
    await expect(page.getByText('全局源清单总数').first()).toBeVisible({ timeout: 30000 })
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

  // D56（FR-UX-704）：搜索生效后，radio 计数与汇总卡仍显示全量数字，
  // 表格却只剩几行——用户会以为筛选坏了；无匹配时还写「暂无 RSS 源」。
  test('搜索时计数跟着命中走，无匹配说明是「没有匹配」', async ({ page }) => {
    await page.goto('/stats/rss-health')
    await expect(page.getByText('人民网-国内').first()).toBeVisible({ timeout: 30000 })

    await page.getByPlaceholder('按源名/URL/品类搜索').fill('科技')
    // 夹具里「科技」命中 rsshub 失效源 + 未巡检源
    await expect(page.locator('.el-table__row')).toHaveCount(2)
    await expect(page.locator('.el-radio-button').filter({ hasText: '全部（2）' })).toHaveCount(1)
    await expect(page.locator('.el-radio-button').filter({ hasText: '失败（1）' })).toHaveCount(1)
    await expect(page.locator('.el-radio-button').filter({ hasText: '未巡检（1）' })).toHaveCount(1)
    await expect(page.locator('.el-radio-button').filter({ hasText: '正常（0）' })).toHaveCount(1)
    // 汇总卡改口「搜索命中」，不再冒充全局总数
    await expect(page.getByText('搜索命中').first()).toBeVisible()

    await page.getByPlaceholder('按源名/URL/品类搜索').fill('不存在的源')
    await expect(page.locator('.el-table__row')).toHaveCount(0)
    await expect(page.getByText('没有匹配「不存在的源」的 RSS 源')).toBeVisible()
    await expect(page.getByText('暂无 RSS 源')).toHaveCount(0)
  })

  // T02508（FR-UX-503）：巡检状态与「连续失败次数」存在进程内存里，重启归零。
  // 页面必须写出累计起点，否则"刚重启所以全绿"会被读成"源一直正常"
  test('累计口径标注：写明巡检状态的累计起点与重启清零', async ({ page }) => {
    await page.goto('/stats/rss-health')
    const note = page.locator('[data-guide="rss-health-scope"]')

    await expect(note).toContainText('累计自 2026-07-18 09:30:00', { timeout: 30000 })
    await expect(note).toContainText('PID 4321')
    await expect(note).toContainText('连续失败次数')
    await expect(note).toContainText('重启后清零')
  })
})

