import { test, expect } from '@playwright/test'
import { setLoginState, llmMetricsResponse } from './helpers/mock'

/**
 * LLM 字数重试命中率页面 E2E 测试
 *
 * 覆盖：
 * - 派生率卡片显示（trigger_rate / improve_rate / not_improve_rate）
 * - 原始计数卡显示（total_calls / triggered / improved / not_improved）
 * - 漏斗可视化渲染（3 个 stage-bar）
 * - 刷新按钮触发重新加载
 */
test.describe('LLM 重试指标页面', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      await route.fulfill({ json: llmMetricsResponse })
    })
  })

  test('派生率卡片显示', async ({ page }) => {
    await page.goto('/stats/llm-metrics')

    await expect(page.getByText('LLM 字数重试命中率').first()).toBeVisible({ timeout: 30000 })

    // 3 个派生率卡片：触发率 / 改善率 / 未改善率
    await expect(page.getByText('触发率').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('改善率').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('未改善率').first()).toBeVisible({ timeout: 30000 })

    // 派生率数值：mock 数据 30.00% / 66.67% / 33.33%
    await expect(page.locator('.rate-value').filter({ hasText: '30.00' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.rate-value').filter({ hasText: '66.67' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.rate-value').filter({ hasText: '33.33' })).toBeVisible({ timeout: 30000 })
  })

  test('原始计数卡显示', async ({ page }) => {
    await page.goto('/stats/llm-metrics')

    // 4 个原始计数卡：总调用 / 触发重试 / 改善 / 未改善
    await expect(page.getByText('总调用次数').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('触发重试次数').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('改善次数').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('未改善次数').first()).toBeVisible({ timeout: 30000 })

    // 计数数值：mock 数据 100/30/20/10
    await expect(page.locator('.count-value').filter({ hasText: '100' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.count-value').filter({ hasText: '30' })).toBeVisible({ timeout: 30000 })
  })

  test('漏斗可视化渲染', async ({ page }) => {
    await page.goto('/stats/llm-metrics')

    // 漏斗卡片标题
    await expect(page.getByText('重试漏斗')).toBeVisible({ timeout: 30000 })

    // 3 个漏斗阶段：总调用 / 触发重试 / 重试改善
    await expect(page.locator('.stage-label').filter({ hasText: '总调用' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-label').filter({ hasText: '触发重试' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-label').filter({ hasText: '重试改善' })).toBeVisible({ timeout: 30000 })

    // 漏斗数值：mock 数据 100/30/20
    await expect(page.locator('.stage-value').filter({ hasText: '100' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-value').filter({ hasText: '30' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-value').filter({ hasText: '20' })).toBeVisible({ timeout: 30000 })
  })

  test('刷新按钮触发重新加载', async ({ page }) => {
    let callCount = 0
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      callCount++
      await route.fulfill({ json: llmMetricsResponse })
    })

    await page.goto('/stats/llm-metrics')
    await expect(page.getByText('触发率').first()).toBeVisible({ timeout: 30000 })
    const initialCount = callCount

    // 点击刷新按钮
    await page.getByRole('button', { name: /刷新/ }).click()

    // 应触发一次新的 llm-metrics 请求
    await expect.poll(() => callCount).toBe(initialCount + 1)
  })
})
