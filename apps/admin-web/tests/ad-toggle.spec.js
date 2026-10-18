import { test, expect } from '@playwright/test'
import {
  setLoginState,
  adPlacementsListResponse,
  adScheduleResponse,
} from './helpers/mock'

/**
 * T02491 / FR-UX-203 广告启停修复 E2E
 *
 * 覆盖 PRD 三点：PC 端提供「停用」、停用即时生效的可信口径、失败回滚；
 * 外加排期日历对停用状态的可见性（同一 bug 的另一半：日历看不出停过）。
 */
test.describe('广告投放启停', () => {
  test.use({ expect: { timeout: 30000 } })

  async function mockPlacements(page, { putStatus = 200 } = {}) {
    const calls = []
    await page.route('**/admin/api/v1/ads/placements**', async (route) => {
      const method = route.request().method()
      if (method === 'GET') {
        await route.fulfill({ json: adPlacementsListResponse })
        return
      }
      if (method === 'PUT') {
        calls.push({
          url: route.request().url(),
          body: JSON.parse(route.request().postData() || '{}'),
        })
        if (putStatus === 200) {
          await route.fulfill({
            json: { code: 0, message: 'success', data: { id: 1, enabled: 0 } },
          })
        } else {
          await route.fulfill({ status: putStatus, body: 'boom' })
        }
        return
      }
      await route.continue()
    })
    return calls
  }

  async function gotoPlacements(page, opts) {
    await setLoginState(page, 'admin')
    const calls = await mockPlacements(page, opts)
    await page.goto('/ads/placements')
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: 30000 })
    return calls
  }

  test('状态列按 enabled 渲染开关（第 1 行启用、第 2 行停用）', async ({ page }) => {
    await gotoPlacements(page)
    const rows = page.locator('.el-table__row')
    await expect(rows.nth(0).locator('.el-switch.is-checked')).toBeVisible()
    await expect(rows.nth(1).locator('.el-switch:not(.is-checked)')).toBeVisible()
  })

  test('点停用弹出确认框，取消则不发 PUT', async ({ page }) => {
    const calls = await gotoPlacements(page)
    const firstSwitch = page.locator('.el-table__row').nth(0).locator('.el-switch')
    await firstSwitch.click()

    const box = page.getByRole('dialog')
    await expect(box).toBeVisible({ timeout: 30000 })
    // 确认规范四要素：动作 + 对象 + 影响范围 + 结论声明
    await expect(box.getByText('停用投放：开头位 · 品牌广告A')).toBeVisible()
    await expect(box.getByText('生效区间 2026-07-01 ~ 2026-07-31')).toBeVisible()
    await expect(box.getByText('停用后，之后新生成的节目不再插入该广告')).toBeVisible()
    // 文案必须如实说明生效边界：已生成节目里的广告是拼进音频的，停用不会去掉
    await expect(box.getByText('已经生成好的节目里广告是拼在音频里的')).toBeVisible()

    await box.getByRole('button', { name: '取消' }).click()
    await expect(box).toBeHidden({ timeout: 30000 })
    expect(calls).toHaveLength(0)
    // 取消后开关保持原状
    await expect(page.locator('.el-table__row').nth(0).locator('.el-switch.is-checked')).toBeVisible()
  })

  test('确认停用后发出 PUT {enabled:0} 并落到开关', async ({ page }) => {
    const calls = await gotoPlacements(page)
    await page.locator('.el-table__row').nth(0).locator('.el-switch').click()
    await page.getByRole('dialog').getByRole('button', { name: '确认停用' }).click()

    await expect
      .poll(() => calls.length, { timeout: 30000 })
      .toBe(1)
    expect(calls[0].url).toContain('/ads/placements/1')
    expect(calls[0].body).toEqual({ enabled: 0 })

    await expect(page.locator('.el-message').getByText('已停用')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.el-table__row').nth(0).locator('.el-switch:not(.is-checked)')).toBeVisible()
  })

  test('PUT 失败时开关回弹，不出现假成功', async ({ page }) => {
    const calls = await gotoPlacements(page, { putStatus: 500 })
    await page.locator('.el-table__row').nth(0).locator('.el-switch').click()
    await page.getByRole('dialog').getByRole('button', { name: '确认停用' }).click()

    await expect
      .poll(() => calls.length, { timeout: 30000 })
      .toBe(1)
    // 失败后 row.enabled 未写回 → 开关回到启用态
    await expect(page.locator('.el-table__row').nth(0).locator('.el-switch.is-checked')).toBeVisible()
    await expect(page.locator('.el-message').getByText('已停用')).toBeHidden()
  })

  test('移动端启停文案如实描述生效边界，确认后 badge 落位', async ({ page }) => {
    await setLoginState(page, 'admin')
    const calls = []
    await page.route('**/admin/api/v1/ads/placements**', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ json: adPlacementsListResponse })
      } else if (route.request().method() === 'PUT') {
        calls.push(JSON.parse(route.request().postData() || '{}'))
        await route.fulfill({ json: { code: 0, message: 'success', data: { id: 1, enabled: 0 } } })
      } else {
        await route.continue()
      }
    })
    await page.goto('/m/manage/ads')
    await expect(page.locator('.m-ads__item').first()).toBeVisible({ timeout: 30000 })

    await page.locator('.m-ads__item').first().getByRole('button', { name: '停用' }).click()
    const box = page.getByRole('dialog')
    await expect(box).toBeVisible({ timeout: 30000 })
    // 对象名取自 material_name（修复前用不存在的 p.name，永远只显示 id）
    await expect(box.getByText('停用广告投放：投放「品牌广告A」')).toBeVisible()
    await expect(box.getByText('之后新生成的节目不再插入该广告，已排期不变')).toBeVisible()
    await expect(box.getByText('停用不会去掉已生成节目里的广告')).toBeVisible()

    await box.getByRole('button', { name: '确认停用' }).click()
    await expect.poll(() => calls.length, { timeout: 30000 }).toBe(1)
    expect(calls[0]).toEqual({ enabled: 0 })
    await expect(
      page.locator('.m-ads__item').first().getByText('已停用')
    ).toBeVisible({ timeout: 30000 })
  })

  test('排期日历标出「已停用」', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/ads/schedule*', async (route) => {
      await route.fulfill({ json: adScheduleResponse })
    })
    await page.goto('/ads/schedule')

    const off = page.locator('.slot-off')
    await expect(off.first()).toBeVisible({ timeout: 30000 })
    await expect(off.first().getByText('已停用')).toBeVisible()
    // 启用中的排期不带停用标记
    await expect(page.locator('.slot-name').filter({ hasText: '品牌广告A' }).first()).toBeVisible()
    await expect(page.locator('.slot-name').filter({ hasText: '促销广告B' }).first().locator('..')).toHaveClass(/slot-off/)
  })
})
