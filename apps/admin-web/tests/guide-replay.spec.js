import { test, expect } from '@playwright/test'
import { setLoginState, reviewListResponse } from './helpers/mock'

/**
 * 引导可用性（T02502 / FR-UX-403）
 *
 * 这条需求有两半，都不在「锚点是否指对」的口径里（那部分由 guide-target.spec.js 与
 * scripts/guide-anchor-audit.mjs 负责）：
 * 1. 「跳过」必须记账——否则用户每次进这个菜单都要再被弹一次，引导变成骚扰；
 * 2. 引导要能从帮助页重新唤起——跳过/看完之后想再看，不能只能清 localStorage。
 *
 * 帮助页重放走的是真实用户路径：不带 ?guide=demo，靠 open(..., {force:true}) 绕开
 * 自动化守卫（用户点击是明确意图，守卫只为防自动弹层挡住被测按钮）。
 */
test.describe('引导重放与跳过记账', () => {
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/events/stream**', (route) =>
      route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }))
    await page.route('**/admin/api/v1/reviews**', (route) =>
      route.fulfill({ json: reviewListResponse }))
  })

  async function skipReviewGuide(page) {
    await page.goto('/review?guide=demo')
    const bubble = page.locator('.mb-guide-bubble')
    await expect(bubble.getByText('内容审核')).toBeVisible()
    await bubble.getByRole('button', { name: '跳过' }).click()
    await expect(bubble).toHaveCount(0)
  }

  test('「跳过」把该菜单记为已引导（修复前不记账，会反复弹）', async ({ page }) => {
    await skipReviewGuide(page)
    const map = await page.evaluate(() => JSON.parse(localStorage.getItem('mb_guide_done') || '{}'))
    expect(map['/review']).toBe(1)
  })

  test('帮助页点菜单即可跳转并重放该菜单的引导', async ({ page }) => {
    await page.goto('/help')
    await page.getByRole('button', { name: '播放「内容审核」引导' }).click()

    await expect(page).toHaveURL(/\/review$/)
    const bubble = page.locator('.mb-guide-bubble')
    await expect(bubble.getByText('内容审核')).toBeVisible()
    // 高亮必须落在审核页自己的锚点上，而不是兜底容器
    await expect(page.locator('.mb-guide-highlight')).toHaveAttribute('data-guide', 'review-page')
  })

  test('已跳过的菜单仍可从帮助页重放（重放前撤销记账 + force）', async ({ page }) => {
    await skipReviewGuide(page)
    await page.goto('/help')
    await page.getByRole('button', { name: '播放「内容审核」引导' }).click()

    await expect(page).toHaveURL(/\/review$/)
    await expect(page.locator('.mb-guide-bubble').getByText('内容审核')).toBeVisible()
  })

  test('清除引导记录后各菜单恢复首访口径', async ({ page }) => {
    await skipReviewGuide(page)
    await page.goto('/help')
    await page.getByRole('button', { name: '清除引导记录' }).click()
    await page.getByRole('button', { name: '确认清除' }).click()

    const map = await page.evaluate(() => JSON.parse(localStorage.getItem('mb_guide_done') || '{}'))
    expect(map['/review']).toBeUndefined()
  })

  test('重放清单与侧栏同口径：运营角色看不到 admin 专属菜单', async ({ page }) => {
    // /tunnel（内网穿透）meta.requireRole=admin：给运营放出来只会点了被守卫弹回，引导永不弹
    await setLoginState(page, 'operator')
    await page.goto('/help')
    await expect(page.getByRole('button', { name: '播放「内容审核」引导' })).toBeVisible()
    await expect(page.getByRole('button', { name: '播放「内网穿透」引导' })).toHaveCount(0)
  })
})
