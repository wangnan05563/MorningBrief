import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * D24（M2 / FR-UX-202）排期日历重叠可见性
 *
 * 改前：`map[dateKey][p.position] = { material_name }` 后写覆盖前写——
 * 同一个广告位、同一天有两条投放时，日历只显示最新那条，另一条**彻底消失**，
 * 既无「+1 条冲突」角标也无 tooltip。运营据此认为这个位子很干净，
 * 实际有两条在争同一个曝光位（重叠本身还会导致排期与投放规则页对不上）。
 *
 * 本 spec 用真实 Chrome 断言：冲突必须**不用悬停也能看见**（角标），
 * 悬停后必须能说出被折叠的是哪条。
 */

function scheduleOf(placements) {
  return { code: 0, message: 'success', data: { placements } }
}

async function openSchedule(page, placements) {
  await setLoginState(page)
  await page.route('**/admin/api/v1/ads/schedule**', (route) =>
    route.fulfill({ json: scheduleOf(placements) })
  )
  await page.goto('/ads/schedule', { waitUntil: 'networkidle' })
  await page.waitForSelector('[data-guide="ads-schedule-calendar"]', { timeout: 30000 })
}

test.describe('排期日历的投放重叠（D24）', () => {
  test.use({ expect: { timeout: 30000 } })

  test('同位同日两条投放：第二条不能被覆盖掉，必须出现重叠角标', async ({ page }) => {
    const ym = new Date().toISOString().slice(0, 7)
    await openSchedule(page, [
      { id: 11, material_name: '品牌广告A', position: 'head', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
      { id: 12, material_name: '竞品广告B', position: 'head', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
    ])

    const badge = page.locator('.slot-conflict').first()
    await expect(badge).toBeVisible()
    await expect(badge).toContainText('+1 条重叠')

    // T02927：角标点开后列出全部重叠投放（含素材名与区间），可直接处置
    await badge.click()
    const tip = page.locator('.el-popper:visible')
    await expect(tip).toContainText('竞品广告B')
    await expect(tip).toContainText('2 条投放重叠')
    await expect(tip).toContainText(`${ym}-01`)
  })

  test('无重叠时不出现角标（避免把正常排期渲染成冲突）', async ({ page }) => {
    const ym = new Date().toISOString().slice(0, 7)
    await openSchedule(page, [
      { id: 21, material_name: '品牌广告A', position: 'head', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
      { id: 22, material_name: '中部广告C', position: 'mid', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
    ])
    await expect(page.locator('.slot-conflict')).toHaveCount(0)
  })

  test('停用的那条不能把启用中的挤进折叠列表', async ({ page }) => {
    const ym = new Date().toISOString().slice(0, 7)
    await openSchedule(page, [
      // 先给一条已停用的，再给一条启用中的：主显必须是启用中的那条
      { id: 31, material_name: '过期广告D', position: 'tail', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 0, status: 'disabled' },
      { id: 32, material_name: '在投广告E', position: 'tail', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
    ])

    // 日历网格里前面还有上个月的空格子，断言只看真有数据的那些
    const tails = page.locator('.slot-tail')
    await expect(tails.filter({ hasText: '在投广告E' }).first()).toBeVisible()
    // 停用那条不得占据主显位（它只该出现在折叠清单里）
    expect(await tails.filter({ hasText: '过期广告D' }).count()).toBe(0)
    // 角标挂在主显（启用中）那条上
    await expect(tails.filter({ has: page.locator('.slot-conflict') }).first()).toContainText('在投广告E')
  })

  test('角标点开后就地停用其中一条：PUT enabled=0 并重新拉取排期', async ({ page }) => {
    const ym = new Date().toISOString().slice(0, 7)
    const conflicting = [
      { id: 101, material_name: '品牌广告A', position: 'head', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
      { id: 102, material_name: '竞品广告B', position: 'head', start_date: `${ym}-01`, end_date: `${ym}-28`, enabled: 1, status: 'active' },
    ]

    await setLoginState(page)
    let scheduleCalls = 0
    // 停用成功前，无论挂载时拉几次都返回两条重叠；PUT 之后才返回单条。
    // （按调用次数切换会被 el-calendar 挂载期的重复请求提前消费掉，导致角标闪没）
    let disabled = false
    await page.route('**/admin/api/v1/ads/schedule**', (route) => {
      scheduleCalls += 1
      route.fulfill({ json: scheduleOf(disabled ? [conflicting[0]] : conflicting) })
    })
    const puts = []
    await page.route('**/admin/api/v1/ads/placements/**', (route) => {
      if (route.request().method() === 'PUT') {
        puts.push({
          url: route.request().url(),
          body: JSON.parse(route.request().postData() || '{}'),
        })
        disabled = true
        return route.fulfill({
          json: { code: 0, message: 'success', data: { id: 102, enabled: 0, status: 'disabled' } },
        })
      }
      return route.continue()
    })

    await page.goto('/ads/schedule', { waitUntil: 'networkidle' })
    await page.waitForSelector('[data-guide="ads-schedule-calendar"]', { timeout: 30000 })
    await expect(page.locator('.slot-conflict').first()).toBeVisible()

    await page.locator('.slot-conflict').first().click()
    // 每个有冲突的日期都会预渲染一份 popover 内容，只有点开的那个是可见的
    const panel = page.locator('.el-popper:visible .conflict-panel')
    await expect(panel).toBeVisible()
    // 两条都在清单里，带各自的区间——运营能定位到底是谁和谁重叠
    await expect(panel).toContainText('品牌广告A')
    await expect(panel).toContainText('竞品广告B')
    await expect(panel).toContainText(`${ym}-01`)

    await panel
      .locator('.conflict-panel__row')
      .filter({ hasText: '竞品广告B' })
      .getByRole('button', { name: '停用' })
      .click()
    await page.getByRole('dialog').getByRole('button', { name: '确认停用' }).click()

    await expect.poll(() => puts.length, { timeout: 30000 }).toBe(1)
    expect(puts[0].url).toContain('/ads/placements/102')
    expect(puts[0].body).toEqual({ enabled: 0 })
    await expect.poll(() => scheduleCalls, { timeout: 30000 }).toBeGreaterThanOrEqual(2)
    await expect(page.locator('.slot-conflict')).toHaveCount(0)
  })
})
