import { test, expect } from '@playwright/test'
import { setLoginState, useMobileViewport } from './helpers/mock'

/**
 * T02602：投放状态必须按「开关 + 日期区间」派生四态。
 *
 * 缺陷：PC 状态列与移动端 badge 只看 enabled，12 月排期和过期一个月的投放
 * 都显示「投放中」；运营据此误以为在投/已停，与 C 端 get_active_placements
 * 的真实播放不一致。四态由服务端随响应下发，本 spec 钉住三处界面都如实渲染。
 */

const today = new Date()
const ym = today.toISOString().slice(0, 7)
const monthStart = `${ym}-01`
const monthEnd = `${ym}-28`

// 前端不推算状态，只渲染服务端下发的 status；这里直接给四态各一条
const placements = [
  { id: 1, material_id: 1, material_name: '生效中广告A', position: 'head', start_date: monthStart, end_date: monthEnd, enabled: 1, status: 'active' },
  { id: 2, material_id: 2, material_name: '待投放广告B', position: 'mid', start_date: monthStart, end_date: monthEnd, enabled: 1, status: 'pending' },
  { id: 3, material_id: 3, material_name: '已过期广告C', position: 'tail', start_date: '2020-01-01', end_date: '2020-01-31', enabled: 1, status: 'expired' },
  { id: 4, material_id: 4, material_name: '已停用广告D', position: 'head', start_date: monthStart, end_date: monthEnd, enabled: 0, status: 'disabled' },
]

async function stubPlacements(page) {
  await page.route('**/admin/api/v1/ads/placements**', (route) =>
    route.fulfill({ json: { code: 0, message: 'success', data: { total: placements.length, list: placements } } })
  )
}

test.describe('投放四态（T02602）', () => {
  test.use({ expect: { timeout: 30000 } })

  test('PC 状态列：四态各自可见，过期/待投放不再显示成已启用', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubPlacements(page)
    await page.goto('/ads/placements')

    const row = (name) => page.getByRole('row').filter({ hasText: name })
    await expect(row('生效中广告A').locator('.status-text')).toHaveText('生效中')
    await expect(row('待投放广告B').locator('.status-text')).toHaveText('待投放')
    await expect(row('已过期广告C').locator('.status-text')).toHaveText('已过期')
    await expect(row('已停用广告D').locator('.status-text')).toHaveText('已停用')

    // 已过期这条开关仍是开着的：状态文字必须由区间派生，而不是跟开关同义
    await expect(row('已过期广告C').locator('.el-switch.is-checked')).toBeVisible()
  })

  test('移动端 badge：四态各自可见', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubPlacements(page)
    await useMobileViewport(page)
    await page.goto('/m/manage/ads')

    const item = (name) => page.locator('.m-ads__item').filter({ hasText: name })
    await expect(item('生效中广告A').locator('.m-badge')).toHaveText('生效中')
    await expect(item('待投放广告B').locator('.m-badge')).toHaveText('待投放')
    await expect(item('已过期广告C').locator('.m-badge')).toHaveText('已过期')
    await expect(item('已停用广告D').locator('.m-badge')).toHaveText('已停用')
  })

  test('排期日历：待投放/已过期/已停用逐格标出，生效中不打扰', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/ads/schedule**', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            placements: [
              // 同位不同日：前半段待投放，后半段生效中
              { material_name: '待投放字幕E', position: 'head', start_date: `${ym}-01`, end_date: `${ym}-05`, enabled: 1, status: 'pending' },
              { material_name: '生效中字幕F', position: 'head', start_date: `${ym}-06`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
              { material_name: '已过期字幕G', position: 'mid', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'expired' },
              { material_name: '已停用字幕H', position: 'tail', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 0, status: 'disabled' },
            ],
          },
        },
      })
    )
    await page.goto('/ads/schedule')

    await expect(page.locator('.slot-pending').filter({ hasText: '待投放' }).first()).toBeVisible()
    await expect(page.locator('.slot-expired').filter({ hasText: '已过期' }).first()).toBeVisible()
    await expect(page.locator('.slot-off').filter({ hasText: '已停用' }).first()).toBeVisible()

    // 生效中那条：格子不加状态标签，避免和「今天真在播」混淆
    const activeSlot = page.locator('.slot-head').filter({ hasText: '生效中字幕F' }).first()
    await expect(activeSlot).toBeVisible()
    await expect(activeSlot.locator('.slot-status-tag')).toHaveCount(0)
  })
})
