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
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

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

    await expect(page.getByText('数据统计').first()).toBeVisible({ timeout: 30000 })

    // 5 个指标卡片：卡片名称与单位全部来自接口 meta（FR-UX-501 / T02506）
    await expect(page.getByText('DAU').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('播放量').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('完播率(%)').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('平均收听(分钟)')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('广告曝光').first()).toBeVisible({ timeout: 30000 })

    // 概览数值应被渲染（千分位后的 12345）
    await expect(page.locator('.metric-value').filter({ hasText: '12,345' })).toBeVisible({ timeout: 30000 })
    // 完播率 0.65 → 65.0（换算来自 meta.display，不是页面里写的 *100）
    await expect(page.locator('.metric-value').filter({ hasText: '65.0' })).toBeVisible({ timeout: 30000 })
    // 平均收听：后端下发 512 秒，按 meta 换算显示 8.5 分钟；秒值原样出现在卡片即为回归
    await expect(page.locator('.metric-value').filter({ hasText: '8.5' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.metric-value').filter({ hasText: '512' })).toHaveCount(0)
  })

  // T02506（FR-UX-501）：「全端一致」的用例——同一份数据（dashboard-summary 内嵌
  // 与 PC 完全相同的 overview + meta），移动端首页必须显示与 PC 相同的单位与数值。
  // 此前移动端把秒直接标成「(分)」、完播率不乘 100，同一指标两端差 60 倍 / 100 倍。
  test('移动端首页与 PC 卡片同口径', async ({ page }) => {
    await page.route('**/admin/api/v1/m/dashboard-summary*', async (route) => {
      await route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            today: statsOverviewResponse.data,
            pending_review: 4,
            unread_message: 2,
          },
        },
      })
    })
    await page.goto('/m/home')

    const labels = page.locator('.m-card__label')
    const values = page.locator('.m-card__value')
    await expect(labels.nth(2)).toHaveText('完播率(%)', { timeout: 30000 })
    await expect(values.nth(2)).toHaveText('65.0', { timeout: 30000 })
    await expect(labels.nth(3)).toHaveText('平均收听(分钟)', { timeout: 30000 })
    await expect(values.nth(3)).toHaveText('8.5', { timeout: 30000 })
    // 秒值与「0.65%」这类未换算的原始值不得出现在首页
    await expect(values.filter({ hasText: '512' })).toHaveCount(0)
    await expect(values.filter({ hasText: /^0\.65/ })).toHaveCount(0)
  })

  // 缺元数据时的失败形态：卡片仍在，但显示 '-'，不会把后端的秒当分钟猜一个单位。
  // 这是「宁可空着也不猜」的契约，用反证跑一次留成常驻用例（T02506）。
  test('meta 缺失时显示 - 而不是原始秒值', async ({ page }) => {
    const withoutMeta = { ...statsOverviewResponse.data }
    delete withoutMeta.meta
    await page.route('**/admin/api/v1/stats/overview*', async (route) => {
      await route.fulfill({ json: { code: 0, message: 'success', data: withoutMeta } })
    })
    await page.goto('/stats')

    const values = page.locator('.metric-value')
    await expect(values).toHaveCount(5, { timeout: 30000 })
    await expect(values.filter({ hasText: '-' })).toHaveCount(5, { timeout: 30000 })
    await expect(values.filter({ hasText: '512' })).toHaveCount(0)
    await expect(page.locator('.metric-label')).toHaveCount(5)
  })

  test('趋势图加载', async ({ page }) => {
    await page.goto('/stats')

    // 趋势卡片标题
    await expect(page.getByText('趋势分析')).toBeVisible({ timeout: 30000 })

    // hasTrend 为 true 时渲染 Line 图表（canvas）
    await expect(page.locator('canvas')).toBeVisible({ timeout: 30000 })

    // 指标切换按钮组应可见
    await expect(page.getByRole('radio', { name: 'DAU' })).toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('radio', { name: '播放量' })).toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('radio', { name: '完播率' })).toBeVisible({ timeout: 30000 })
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
    await expect(page.locator('canvas')).toBeVisible({ timeout: 30000 })
    const initialCount = trendCallCount

    // 切换到"播放量"指标
    // Element Plus 的 el-radio-button 内部 input 被 .el-radio-button__inner span 遮挡，
    // 直接点击 radio role 会因 pointer interception 失败，改点击 .el-radio-button 容器
    await page.locator('.el-radio-button').filter({ hasText: '播放量' }).click()

    // 应触发一次新的 trend 请求
    await expect.poll(() => trendCallCount).toBe(initialCount + 1)
    // canvas 应仍然可见
    await expect(page.locator('canvas')).toBeVisible({ timeout: 30000 })
  })
})

