import { test, expect } from '@playwright/test'
import {
  setLoginState,
  useMobileViewport,
  channelsListResponse,
  adScheduleResponse,
} from './helpers/mock'

/**
 * M3「失败可见性」E2E（T02534 / FR-UX-302 与 ACC-UX-301 第 3 条口径）
 *
 * 与 list-error-state.spec.js 的分工：那份管「列表失败被说成暂无数据」，
 * 这份管**会声称一件事实的非列表块**——日历的「—」、进度标签的「已取 X / 共 Y 本」、
 * 状态卡的「0 条」。它们的共同点不是「空」，而是「把不知道说成一个具体的数」，
 * 所以每条用例都同时断言两件事：错误态出现、且那句断言从 DOM 上消失。
 *
 * 覆盖条目：D25（排期日历）、I15（移动首页指标）、M71（维护中心状态）、C73（讲书稿进度跨频道残留）。
 */

const API = '**/admin/api/v1'

async function stubSse(page) {
  await page.route(`${API}/events/stream**`, (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
  )
}

const ok = (data) => ({ code: 0, message: 'success', data })

const bookPoolStateResponse = ok({
  enabled: true, cursor: 1, pool_total: 3, interval_days: 1, loop: false,
  last_run_date: '2026-10-20', last_title: '《书A》', rss_sources: [], book_rss_sources: [],
})
const bookPoolItemsResponse = ok({ items: [{ id: 11, title: '《书A》', status: 'pending' }] })

test.describe('M3 失败不得伪装成事实', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s：真要放宽就写在具体断言上（{ timeout: N }）；
  // test.use({ expect: { timeout } }) 在 Playwright 1.61 是空选项，会被静默忽略（T02778）

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubSse(page)
  })

  test('D25 排期接口失败：给错误态与重试，日历不再用「—」冒充本月无排期', async ({ page }) => {
    await page.route(`${API}/ads/schedule*`, (route) => route.abort())

    await page.goto('/ads/schedule')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(banner).toContainText('加载失败')
    // 旧行为：接口失败后日历照常渲染，每个格子都是「—」——用户读作「本月无排期」
    await expect(page.locator('.el-calendar')).toHaveCount(0)
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  test('D25 重试成功：错误态消失、日历回来', async ({ page }) => {
    let calls = 0
    await page.route(`${API}/ads/schedule*`, async (route) => {
      calls += 1
      if (calls === 1) return route.abort()
      return route.fulfill({ json: adScheduleResponse })
    })

    await page.goto('/ads/schedule')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })

    await banner.getByRole('button', { name: '重试', exact: true }).click()
    await expect(banner).toHaveCount(0)
    await expect(page.locator('.el-calendar')).toBeVisible({ timeout: 30000 })
  })

  test('I15 移动端首页断网：不出现「待审 0 / 未读 0」的假正常态', async ({ page }) => {
    await page.route(`${API}/m/dashboard-summary*`, (route) => route.abort())

    await useMobileViewport(page)
    await page.goto('/m')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    // 旧代码 `.catch(() => ({today:{},pending_review:0,unread_message:0}))` 正是把这些区块铺成 0
    await expect(page.locator('.m-section')).toHaveCount(0)
    await expect(banner.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  })

  test('I15 重试成功：指标区恢复', async ({ page }) => {
    let calls = 0
    await page.route(`${API}/m/dashboard-summary*`, async (route) => {
      calls += 1
      if (calls === 1) return route.abort()
      return route.fulfill({ json: ok({ today: { dau: 20 }, pending_review: 3, unread_message: 1 }) })
    })

    await useMobileViewport(page)
    await page.goto('/m')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })

    await banner.getByRole('button', { name: '重试', exact: true }).click()
    await expect(banner).toHaveCount(0)
    await expect(page.locator('.m-section').first()).toBeVisible({ timeout: 30000 })
  })

  test('M71 首次状态加载失败：三卡整块撤下，而不是写「0 条 / 0 个」', async ({ page }) => {
    await page.route(`${API}/maintenance/status*`, (route) => route.abort())

    await page.goto('/maintenance')
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    // M71 的原始后果：运维把「0 条日志、无需清理」当成事实去判断清理效果
    await expect(page.locator('.status-section')).toHaveCount(0)
    await expect(page.getByText(/0 条/)).toHaveCount(0)
  })

  test('M71 二次刷新失败：保留旧数值，但改口为「可能已过期」', async ({ page }) => {
    let calls = 0
    await page.route(`${API}/maintenance/status*`, async (route) => {
      calls += 1
      if (calls === 1) {
        return route.fulfill({
          json: ok({
            db: { db_size_mb: 12.5, playlog_count: 8121, workflow_count: 30, review_count: 44, blacklist_count: 2 },
            logs: { total_size_mb: 3.2, file_count: 7 },
            cache: { ttlcache_count: 5, pycache_count: 1, temp_files: 0 },
          }),
        })
      }
      return route.abort()
    })

    await page.goto('/maintenance')
    await expect(page.getByText('播放日志 8121 条')).toBeVisible({ timeout: 30000 })

    await page.getByRole('button', { name: '刷新状态' }).click()
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    // 已有旧数据时不能声称「数据未加载」；也不能假装数值是新鲜的
    await expect(banner).toContainText('上次成功加载的数据')
    await expect(page.getByText('播放日志 8121 条')).toBeVisible()
  })

  test('C73 切到接口失败的频道：上一频道的「已取 1 / 共 3 本」必须消失', async ({ page }) => {
    await page.route(`${API}/channels**`, async (route) => {
      const url = route.request().url()
      if (/\/channels\?|\/channels$/.test(url)) return route.fulfill({ json: channelsListResponse })
      if (url.includes('/channels/2/')) return route.abort()
      if (url.includes('book-pool')) return route.fulfill({ json: bookPoolItemsResponse })
      if (url.includes('script-mode')) return route.fulfill({ json: bookPoolStateResponse })
      return route.abort()
    })

    await page.goto('/channels/book-pool?channelId=1')
    const progress = page.getByText(/已取 1 \/ 共 3 本/)
    await expect(progress).toBeVisible({ timeout: 30000 })

    await page.locator('.el-select').first().click()
    await page.getByRole('option', { name: /财经频道/ }).click()

    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    // 这一句才是 C73 的病灶：标题已经是财经频道，进度说的却还是科技频道
    await expect(progress).toHaveCount(0)
    await expect(page.getByText(/上次：《书A》/)).toHaveCount(0)
  })
})
