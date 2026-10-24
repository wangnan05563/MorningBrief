import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * PC 队列页 page/size 写入 URL（T02764 / FR-UX-602 收尾）
 *
 * 缺陷面：`QueueManagement.vue` 的 page/size 此前只在组件内存里——
 * 刷新回到第 1 页、分享出去的链接不带分页、深链 `?page=3` 被当作第 1 页。
 *
 * 这一份只覆盖**接线后的用户可见行为**（同 tests/url-state.spec.js 的分层）：
 * 深链起页、翻页/换尺寸写回地址、刷新保留、越界页码落最后一页并如实点名。
 * 规则本体（整数/下限/上限/回落）已在 tests/unit/url-state.test.mjs 逐条断言。
 *
 * 数据面 total=45：size=20 时最后一页是 3，专门用来验 `?page=999` 的钳制
 * ——落到第 3 页而不是退回第 1 页的空表。行状态一律 success，避免队列页
 * 的 5s 活跃轮询插进来干扰请求计数（无活跃任务时是 30s 档）。
 */

const API = '**/admin/api/v1'
const TOTAL = 45
const ok = (data) => ({ code: 0, message: 'success', data })

function pageItems(page, size) {
  const start = (page - 1) * size
  const count = Math.max(0, Math.min(size, TOTAL - start))
  return Array.from({ length: count }, (_, i) => ({
    id: `wf-${start + i + 1}`,
    episode_date: '2026-07-08',
    source: 'cron',
    status: 'success',
    channel_id: 1,
    channel_name: '科技频道',
    priority: 5,
    started_at: '2026-07-08T05:00:00',
    finished_at: '2026-07-08T05:10:00',
    error: null,
  }))
}

/** 按请求里的 page/size 返回对应切片——总页数/当前页因此有真实含义 */
async function mockQueue(page) {
  await page.route(`${API}/events/stream**`, (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }),
  )
  await page.route(`${API}/queue/stats`, (route) =>
    route.fulfill({ json: ok({ queued: 0, running: 0, success: TOTAL, failed: 0, cancelled: 0 }) }),
  )
  await page.route(`${API}/queue/config`, (route) =>
    route.fulfill({ json: ok({ execution_mode: 'serial', max_concurrent: 1 }) }),
  )
  await page.route(`${API}/queue/tasks*`, (route) => {
    const url = new URL(route.request().url())
    const p = Number(url.searchParams.get('page') || 1)
    const s = Number(url.searchParams.get('size') || 20)
    return route.fulfill({ json: ok({ total: TOTAL, items: pageItems(p, s) }) })
  })
  await page.route(`${API}/channels*`, (route) =>
    route.fulfill({ json: ok([{ id: 1, name: '科技频道', channel_type: 'news', enabled: true }]) }),
  )
  await setLoginState(page, 'admin')
}

const activePage = (page) => page.locator('.el-pagination .el-pager li.is-active')
const correctedAlert = (page) => page.locator('[data-guide="queue-url-corrected"]')

test.describe('PC 队列页：page/size 写进 URL', () => {
  test.beforeEach(async ({ page }) => {
    await mockQueue(page)
  })

  test('深链 ?page=2&size=10 直接落在那一页（请求、分页器、地址一致）', async ({ page }) => {
    const req = page.waitForRequest((r) => {
      if (!r.url().includes('/queue/tasks')) return false
      const q = new URL(r.url()).searchParams
      return q.get('page') === '2' && q.get('size') === '10'
    })
    await page.goto('/news/queue?page=2&size=10')
    await req
    await expect(activePage(page)).toHaveText('2')
    await expect(page.locator('.el-table__row')).toHaveCount(10)
    const q = new URL(page.url()).searchParams
    expect(q.get('page')).toBe('2')
    expect(q.get('size')).toBe('10')
  })

  test('默认值不写进 URL；翻到第 2 页后地址出现 page=2，刷新仍在第 2 页', async ({ page }) => {
    await page.goto('/news/queue')
    await expect(activePage(page)).toHaveText('1')
    // 等于默认值的参数不写进地址（分享链接不该被脏参数淹没）
    expect(new URL(page.url()).searchParams.has('page')).toBe(false)
    expect(new URL(page.url()).searchParams.has('size')).toBe(false)

    await page.locator('.el-pagination .el-pager li', { hasText: /^2$/ }).click()
    await expect(page).toHaveURL(/page=2/)
    await expect(activePage(page)).toHaveText('2')

    // 刷新即丢是原缺陷：重载后必须还停在第 2 页（请求也仍带 page=2）
    const req = page.waitForRequest((r) => {
      if (!r.url().includes('/queue/tasks')) return false
      return new URL(r.url()).searchParams.get('page') === '2'
    })
    await page.reload()
    await req
    await expect(activePage(page)).toHaveText('2')
  })

  test('换分页尺寸回第 1 页并把 size 写回地址', async ({ page }) => {
    await page.goto('/news/queue?page=2')
    await expect(activePage(page)).toHaveText('2')

    await page.locator('.el-pagination .el-select__wrapper').click()
    await page.locator('.el-select-dropdown__item', { hasText: '50条/页' }).last().click()

    // 第 2 页 × 20 行换成 50 行/页后第 2 页已不存在：换尺寸必须回第 1 页
    await expect(activePage(page)).toHaveText('1')
    await expect(page).toHaveURL(/size=50/)
    expect(new URL(page.url()).searchParams.has('page')).toBe(false)
  })

  test('?page=999 钳到最后一页并改写地址（不是退回第 1 页的空表）', async ({ page }) => {
    await page.goto('/news/queue?page=999')
    // total=45 / size=20 ⇒ 最后一页是 3
    await expect(activePage(page)).toHaveText('3')
    expect(new URL(page.url()).searchParams.get('page')).toBe('3')
    const alert = correctedAlert(page)
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('超过上限')
    await expect(alert).toContainText('已落到最后一页')
    await expect(page.locator('.el-table__row')).toHaveCount(5)
  })

  test('非法 ?page=abc / 非档位 ?size=7 回落修正并在页内点名', async ({ page }) => {
    await page.goto('/news/queue?page=abc&size=7')
    await expect(activePage(page)).toHaveText('1')
    // 7 不在可选档位（10/20/50/100）里：就近取 10，绝不按 7 行渲染
    await expect(page.locator('.el-table__row')).toHaveCount(10)
    const alert = correctedAlert(page)
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('page=abc')
    await expect(alert).toContainText('size=7')
    await expect(alert).toContainText('已按 10 处理')
    const q = new URL(page.url()).searchParams
    // 地址栏不再撒谎：page 回到默认值被省略，size 改写成真正生效的 10
    expect(q.has('page')).toBe(false)
    expect(q.get('size')).toBe('10')
  })
})
