import { test, expect } from '@playwright/test'
import {
  setLoginState,
  statsOverviewResponse,
  statsTrendResponse,
} from './helpers/mock'

/**
 * 统计页面 E2E 测试
 *
 * 覆盖：
 * - 指标卡片显示
 * - 趋势图加载
 * - 切换指标重新加载
 */
test.describe('统计页面', () => {
  // 并行执行时 vite 首次编译各路由组件较慢，5s 默认超时不足
  test.use({ expect: { timeout: 15000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')

    // 概览数据
    await page.route('**/admin/api/v1/stats/overview*', async (route) => {
      await route.fulfill({ json: statsOverviewResponse })
    })

    // 趋势数据
    await page.route('**/admin/api/v1/stats/trend*', async (route) => {
      await route.fulfill({ json: statsTrendResponse })
    })
  })

  test('指标卡片显示', async ({ page }) => {
    await page.goto('/stats')

    await expect(page.getByText('数据统计').first()).toBeVisible({ timeout: 15000 })

    // 5 个指标卡片：DAU/播放量/完播率/平均收听/广告曝光
    await expect(page.getByText('DAU').first()).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('播放量').first()).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('完播率(%)').first()).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('平均收听(分钟)')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('广告曝光').first()).toBeVisible({ timeout: 15000 })

    // 概览数值应被渲染（formatNum 后的 12345）
    await expect(page.locator('.metric-value').filter({ hasText: '12,345' })).toBeVisible({ timeout: 15000 })
    // 完播率 0.65 → 65.0
    await expect(page.locator('.metric-value').filter({ hasText: '65.0' })).toBeVisible({ timeout: 15000 })
  })

  test('趋势图加载', async ({ page }) => {
    await page.goto('/stats')

    // 趋势卡片标题
    await expect(page.getByText('趋势分析')).toBeVisible({ timeout: 15000 })

    // hasTrend 为 true 时渲染 Line 图表（canvas）
    await expect(page.locator('canvas')).toBeVisible({ timeout: 15000 })

    // 指标切换按钮组应可见
    await expect(page.getByRole('radio', { name: 'DAU' })).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('radio', { name: '播放量' })).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('radio', { name: '完播率' })).toBeVisible({ timeout: 15000 })
  })

  test('切换指标重新加载', async ({ page }) => {
    // 记录 trend 接口被调用次数
    let trendCallCount = 0
    await page.route('**/admin/api/v1/stats/trend*', async (route) => {
      trendCallCount++
      await route.fulfill({ json: statsTrendResponse })
    })

    await page.goto('/stats')

    // 等待初始加载完成（onMounted 同时触发 loadOverview + loadTrend）
    await expect(page.locator('canvas')).toBeVisible({ timeout: 15000 })
    const initialCount = trendCallCount

    // 切换到"播放量"指标
    // Element Plus 的 el-radio-button 内部 input 被 .el-radio-button__inner span 遮挡，
    // 直接点击 radio role 会因 pointer interception 失败，改点击 .el-radio-button 容器
    await page.locator('.el-radio-button').filter({ hasText: '播放量' }).click()

    // 应触发一次新的 trend 请求
    await expect.poll(() => trendCallCount).toBe(initialCount + 1)
    // canvas 应仍然可见
    await expect(page.locator('canvas')).toBeVisible({ timeout: 15000 })
  })
})
