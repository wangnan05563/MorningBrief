import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * PC 投放规则列表的筛选与分页写入 URL（T02758 / FR-UX-602 / D13）
 *
 * 缺陷面：`AdPlacements.vue` 的 enabled 筛选与 page/size 此前只在组件内存里——
 * 刷新回到「全部状态 + 第 1 页」、分享出去的链接不带筛选、深链参数被当成没写。
 * 状态列本身已由 D13/D14 落下，本用例只锁「地址栏与界面一致」这一半。
 *
 * 数据面 total=45：size=20 时最后一页是 3，专门用来验 `?page=999` 的钳制。
 */

const API = '**/admin/api/v1'
const TOTAL = 45
const ok = (data) => ({ code: 0, message: 'success', data })

function pageItems(pageNo, size) {
  const start = (pageNo - 1) * size
  const count = Math.max(0, Math.min(size, TOTAL - start))
  return Array.from({ length: count }, (_, i) => ({
    id: start + i + 1,
    material_id: 1,
    material_name: `品牌广告${start + i + 1}`,
    position: 'head',
    start_date: '2026-07-01',
    end_date: '2026-07-31',
    enabled: 1,
    status: 'active',
  }))
}

async function mockPlacements(page) {
  await page.route(`${API}/ads/placements*`, (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    const url = new URL(route.request().url())
    const p = Number(url.searchParams.get('page') || 1)
    const s = Number(url.searchParams.get('size') || 20)
    return route.fulfill({ json: ok({ total: TOTAL, list: pageItems(p, s) }) })
  })
  await setLoginState(page, 'admin')
}

const activePage = (page) => page.locator('.el-pagination .el-pager li.is-active')
const correctedAlert = (page) => page.locator('[data-guide="ads-url-corrected"]')
const enabledSelect = (page) => page.locator('.toolbar .el-select__wrapper')

test.describe('PC 投放规则：筛选与分页写进 URL', () => {
  test.beforeEach(async ({ page }) => {
    await mockPlacements(page)
  })

  test('深链 ?enabled=0&page=2&size=10 直接落在那一页（请求、筛选器、分页器一致）', async ({ page }) => {
    const req = page.waitForRequest((r) => {
      if (!r.url().includes('/admin/api/v1/ads/placements')) return false
      const q = new URL(r.url()).searchParams
      return q.get('enabled') === '0' && q.get('page') === '2' && q.get('size') === '10'
    })
    await page.goto('/news/ads/placements?enabled=0&page=2&size=10')
    await req
    await expect(enabledSelect(page)).toContainText('仅停用')
    await expect(activePage(page)).toHaveText('2')
    await expect(page.locator('.el-table__row')).toHaveCount(10)
    const q = new URL(page.url()).searchParams
    expect(q.get('enabled')).toBe('0')
    expect(q.get('page')).toBe('2')
    expect(q.get('size')).toBe('10')
  })

  test('改筛选/翻页写回地址，刷新后仍是同一筛选与页码', async ({ page }) => {
    await page.goto('/news/ads/placements')
    await expect(activePage(page)).toHaveText('1')
    // 等于默认值的参数不写进地址
    expect(new URL(page.url()).searchParams.has('enabled')).toBe(false)
    expect(new URL(page.url()).searchParams.has('page')).toBe(false)
    expect(new URL(page.url()).searchParams.has('size')).toBe(false)

    // 先翻到第 2 页，再换筛选：必须回第 1 页，否则筛完可能落在空页
    await page.locator('.el-pagination .el-pager li', { hasText: /^2$/ }).click()
    await expect(page).toHaveURL(/page=2/)

    await enabledSelect(page).click()
    await page.locator('.el-select-dropdown__item', { hasText: '仅启用' }).last().click()

    await expect(activePage(page)).toHaveText('1')
    const q = new URL(page.url()).searchParams
    expect(q.get('enabled')).toBe('1')
    expect(q.has('page')).toBe(false)

    // 刷新即丢是原缺陷：重载后筛选与页码都要从地址恢复
    await page.reload()
    await expect(enabledSelect(page)).toContainText('仅启用')
    await expect(activePage(page)).toHaveText('1')
  })

  test('地址栏被外部改动（点侧栏回到无参地址）时筛选与分页跟着复位', async ({ page }) => {
    await page.goto('/news/ads/placements?enabled=1&page=2')
    await expect(enabledSelect(page)).toContainText('仅启用')
    await expect(activePage(page)).toHaveText('2')

    // 侧栏菜单 :router="true" 指向不带 query 的同一路由——这是一次外部改动，
    // 页面必须跟着地址复位并**重新取数**，而不是继续显示「仅启用 + 第 2 页」的旧数据
    const resetReq = page.waitForRequest((r) => {
      if (!r.url().includes('/admin/api/v1/ads/placements')) return false
      const q = new URL(r.url()).searchParams
      return !q.has('enabled') && q.get('page') === '1'
    })
    await page.locator('.el-sub-menu__title', { hasText: '广告管理' }).click()
    await page.locator('.el-menu-item', { hasText: '投放规则' }).click()
    await resetReq

    await expect(page).toHaveURL(/\/ads\/placements$/)
    await expect(enabledSelect(page)).toContainText('全部状态')
    await expect(activePage(page)).toHaveText('1')
  })

  test('?page=999 钳到最后一页并改写地址（不是退回第 1 页的空表）', async ({ page }) => {
    await page.goto('/news/ads/placements?page=999')
    // total=45 / size=20 ⇒ 最后一页是 3
    await expect(activePage(page)).toHaveText('3')
    expect(new URL(page.url()).searchParams.get('page')).toBe('3')
    const alert = correctedAlert(page)
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('超过上限')
    await expect(alert).toContainText('已落到最后一页')
    await expect(page.locator('.el-table__row')).toHaveCount(5)
  })

  test('非法 ?enabled=2 / ?page=abc / 非档位 ?size=7 回落修正并在页内点名', async ({ page }) => {
    await page.goto('/news/ads/placements?enabled=2&page=abc&size=7')
    await expect(activePage(page)).toHaveText('1')
    // 7 不在可选档位（10/20/50/100）里：就近取 10，绝不按 7 行渲染
    await expect(page.locator('.el-table__row')).toHaveCount(10)
    const alert = correctedAlert(page)
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('enabled=2')
    await expect(alert).toContainText('page=abc')
    await expect(alert).toContainText('size=7')
    await expect(alert).toContainText('已按 10 处理')
    const q = new URL(page.url()).searchParams
    expect(q.has('enabled')).toBe(false)
    expect(q.has('page')).toBe(false)
    expect(q.get('size')).toBe('10')
  })
})
