import { test, expect } from '@playwright/test'
import {
  setLoginState,
  statsOverviewResponse,
  statsTrendCompletionResponse,
  statsTrendResponse,
} from './helpers/mock'

/**
 * 统计页面 E2E 测试
 *
 * 覆盖：
 * - 指标卡片显示
 * - 趋势图加载
 * - 切换指标重新加载
 * - 完播率三处同刻度（FR-UX-501 / FR-UX-502）
 * - 日期筛选与趋势范围的口径关系写明（FR-UX-503 / T02508）
 */

/**
 * 读出画在 canvas 里的曲线位置（T02507）
 *
 * 曲线刻度是本单最容易「DOM 全绿、图还是 0~1」的死角：轴标题与峰值是 DOM 文字，
 * 而 dataset 是画进画布的像素。Chart.js 的网格线 alpha≈0.1、面积填充 alpha≈0.18，
 * 主线与数据点是实色（alpha=255），按 alpha>120 过滤后只剩曲线本身。
 * 返回曲线顶端/底端在画布高度中的占比，供用例断言「画的是换算后的量级」。
 */
async function curveBand(page) {
  return page.evaluate(() => {
    const canvas = document.querySelector('.trend-plot canvas')
    if (!canvas) return null
    const g = canvas.getContext('2d')
    const { data, width, height } = g.getImageData(0, 0, canvas.width, canvas.height)
    // 横向只取 35%~90%：左侧是旋转的纵轴标题和刻度文字，右侧避开末端留白
    const x0 = Math.floor(width * 0.35)
    const x1 = Math.floor(width * 0.9)
    let top = -1
    let bottom = -1
    for (let y = 0; y < height; y++) {
      for (let x = x0; x <= x1; x++) {
        if (data[(y * width + x) * 4 + 3] > 120) {
          if (top < 0) top = y
          bottom = y
          break
        }
      }
    }
    if (top < 0) return null
    return { topFrac: top / height, bottomFrac: bottom / height }
  })
}
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

  // T02507（FR-UX-502）：完播率在「卡片 / 趋势 / 移动端」三处必须是同一刻度。
  // 趋势曲线本身画在 canvas 里断言不到，但峰值与曲线数据出自同一个
  // trendPoints（按 meta.display.factor 换算的结果），所以断言峰值文案
  // 就等于断言了曲线刻度；再与卡片 65.0、移动端 65.0 对齐即 ACC-UX-501 #2。
  test('趋势图与卡片同刻度（完播率）', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/trend*', async (route) => {
      await route.fulfill({ json: statsTrendCompletionResponse })
    })
    await page.goto('/stats')
    await expect(page.locator('canvas')).toBeVisible({ timeout: 30000 })
    await page.locator('.el-radio-button').filter({ hasText: '完播率' }).click()

    await expect(page.locator('.trend-summary__axis')).toHaveText('纵轴 完播率(%)', {
      timeout: 30000,
    })
    await expect(page.locator('.trend-summary__peak')).toHaveText(
      '峰值 65.0%（2026-07-02）',
      { timeout: 30000 },
    )
    // 卡片与趋势峰值是同一个数（0.65 → 65.0，只乘一次 100）
    await expect(
      page.locator('.metric-value').filter({ hasText: '65.0' }),
    ).toBeVisible({ timeout: 30000 })
    // 原始 ratio 不得出现在任何刻度文案里
    await expect(page.locator('[data-guide="stats-trend-summary"]')).not.toContainText('0.65')
    await expect(page.locator('.trend-plot')).toHaveAttribute(
      'aria-label',
      /完播率\(%\).*峰值 65\.0%/,
    )
  })

  // 曲线本体：峰值文案证明「换算只乘一次」，这条证明「乘完的结果真的画进了画布」。
  // 数据 50/65/42（占比 0.5/0.65/0.42 换算而来）应落在画布上半部；
  // 若有人把原始 ratio 直接喂给 dataset（0.42~0.65 对 0~65 的轴），
  // 曲线会贴着底部横轴，顶端占比 >0.9 —— 正是本次改造前的形态。
  test('趋势曲线按换算后的刻度绘制', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/trend*', async (route) => {
      await route.fulfill({ json: statsTrendCompletionResponse })
    })
    await page.goto('/stats')
    await page.locator('.el-radio-button').filter({ hasText: '完播率' }).click()
    await expect(page.locator('.trend-summary__peak')).toContainText('65.0%', {
      timeout: 30000,
    })

    const band = await curveBand(page)
    expect(band, '画布上读不到曲线（未渲染或被遮挡）').not.toBeNull()
    expect(band.topFrac).toBeLessThan(0.5)
    expect(band.bottomFrac).toBeGreaterThan(0.15)
  })

  // 反证：趋势缺 meta 时，页面不得把 0~1 的原始值当百分数报出来，  // 只能显示「没有单位 / 没有峰值」——与卡片的「宁可空着也不猜」同一条契约。
  test('趋势缺 meta 时不猜刻度', async ({ page }) => {
    const withoutMeta = { ...statsTrendCompletionResponse.data }
    delete withoutMeta.meta
    await page.route('**/admin/api/v1/stats/trend*', async (route) => {
      await route.fulfill({ json: { code: 0, message: 'success', data: withoutMeta } })
    })

    await page.goto('/stats')
    await expect(page.locator('.trend-summary__axis')).toHaveText('纵轴 -', { timeout: 30000 })
    await expect(page.locator('.trend-summary__peak')).toHaveText('峰值 暂无数据', {
      timeout: 30000,
    })
    await expect(page.locator('[data-guide="stats-trend-summary"]')).not.toContainText('0.65')
  })

  // T02508（FR-UX-503）：日期选择器只驱动当日卡片，趋势固定按 range 从今天往前取，
  // 两者互不相干。这里既断言文案写明，也用请求次数把这个关系钉死——
  // 光有文案而行为不对，比没文案更误导
  test('口径标注：日期筛选与趋势范围互不影响', async ({ page }) => {
    let overviewCalls = 0
    let trendCalls = 0
    let lastOverviewUrl = ''
    await page.route('**/admin/api/v1/stats/overview*', async (route) => {
      overviewCalls++
      lastOverviewUrl = route.request().url()
      await route.fulfill({ json: statsOverviewResponse })
    })
    await page.route('**/admin/api/v1/stats/trend*', async (route) => {
      trendCalls++
      await route.fulfill({ json: statsTrendResponse })
    })

    await page.goto('/stats')

    const note = page.locator('[data-guide="stats-scope-note"]')
    await expect(note).toContainText('上方日期只影响下面这组当日卡片', { timeout: 30000 })
    await expect(note).toContainText('近 7 天')
    await expect(note).toContainText('不随所选日期改变')
    // 区间直接取响应里的 dates 首尾，不是前端按"今天"倒推出来的猜测
    await expect(page.locator('.trend-summary__window')).toContainText('2026-07-01 ~ 2026-07-03', {
      timeout: 30000,
    })

    const overviewBefore = overviewCalls
    const trendBefore = trendCalls

    // 切趋势范围：只应重发 trend，卡片一次都不动
    await page.locator('.el-radio-button').filter({ hasText: '30 天' }).click()
    await expect.poll(() => trendCalls).toBe(trendBefore + 1)
    expect(overviewCalls).toBe(overviewBefore)

    // 改日期：只应重发 overview，趋势不跟着动
    const dateInput = page.locator('.top-bar .el-date-editor input')
    await dateInput.click()
    await dateInput.fill('2026-07-05')
    await page.keyboard.press('Enter')
    await expect.poll(() => overviewCalls).toBe(overviewBefore + 1)
    expect(lastOverviewUrl).toContain('date=2026-07-05')
    expect(trendCalls).toBe(trendBefore + 1)
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

