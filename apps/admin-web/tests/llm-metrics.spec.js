import { test, expect } from '@playwright/test'
import { setLoginState, llmMetricsResponse, llmMetricsLegacyResponse } from './helpers/mock'

/**
 * LLM 字数重试命中率页面 E2E 测试
 *
 * 覆盖：
 * - 派生率卡片显示（trigger_rate / improve_rate / not_improve_rate）
 * - 原始计数卡显示（total_calls / triggered / improved / not_improved）
 * - 漏斗可视化渲染（3 个 stage-bar）
 * - 刷新按钮触发重新加载
 * - 累计口径标注（T02508 / FR-UX-503：起点、PID、重启清零、缺字段退化）
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

    // T00811：内容区标题已移除，标题改由导航栏展示（meta.title=LLM 重试指标）
    await expect(page.getByText('LLM 重试指标').first()).toBeVisible({ timeout: 30000 })

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

  // T02508（FR-UX-503）：本页计数全部是进程内累计，重启归零。
  // PRD ACC-UX-501 要求「LLM 指标页明确显示累计自 x 时间，重启清零」，
  // 这里断言的是"起点时间 + PID + 重启清零"三个要素都在页面上，而不只是一句空话
  test('累计口径标注：写明累计起点与重启清零', async ({ page }) => {
    await page.goto('/stats/llm-metrics')
    const note = page.locator('[data-guide="llm-metrics-scope"]')

    await expect(note).toContainText('累计自 2026-07-18 09:30:00', { timeout: 30000 })
    await expect(note).toContainText('PID 4321')
    await expect(note).toContainText('重启后清零')
    // 运行时长让运维判断样本攒了多久（不断言具体天数，测试机时间不固定）
    await expect(note).toContainText('已运行')
  })

  test('后端未升级时不编造起点日期', async ({ page }) => {
    // 后注册的 route 优先命中：用不含 started_at 的老响应覆盖 beforeEach 的 mock
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      await route.fulfill({ json: llmMetricsLegacyResponse })
    })
    await page.goto('/stats/llm-metrics')
    const note = page.locator('[data-guide="llm-metrics-scope"]')

    await expect(note).toContainText('后端未返回累计起点时间', { timeout: 30000 })
    await expect(note).not.toContainText(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/)
    // 口径字段缺失不能连带把数据也弄没
    await expect(page.locator('.count-value').filter({ hasText: '100' })).toBeVisible({
      timeout: 30000,
    })
  })

  test('零调用空态同样标注口径', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      await route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            total_calls: 0,
            triggered: 0,
            improved: 0,
            not_improved: 0,
            trigger_rate: 0.0,
            improve_rate: 0.0,
            not_improve_rate: 0.0,
            started_at: '2026-07-18T09:30:00',
            pid: 4321,
          },
        },
      })
    })
    await page.goto('/stats/llm-metrics')

    // 空态时"0%"最容易被误读成"问题已修复"，口径必须在这时候也在场
    await expect(page.getByText('暂无 LLM 调用数据')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('[data-guide="llm-metrics-scope"]')).toContainText(
      '累计自 2026-07-18 09:30:00',
    )
  })
})
