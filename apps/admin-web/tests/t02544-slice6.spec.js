import { test, expect } from '@playwright/test'
import { setLoginState, useMobileViewport } from './helpers/mock'

/**
 * T02544 切片 6 真机验收（口径见 T02336 §4.3 修订后的四条）
 *
 * - H11：COS 批量上传必须给出「成功 N / 失败 M + 失败清单」；取消即停止本批，
 *        不能把剩下的文件一个个再弹确认。
 * - I59：跨端自动切换后在落点页说明「换了哪一端」，并给一条能真正回到原端的回链；
 *        离开落点后提示自动失效。
 * - I6：移动端处理一条审核后重载列表，不得重置其它行的展开态、详情与滚动位置。
 * - M66：日志清理页明确告知「正在写入的最新日志不会被清理」（排除逻辑由后端测试
 *        test_t02544_m66_active_log.py 保证，这里守住界面说法）。
 */

const NAV = 30000
const API = '**/admin/api/v1'

const ok = (data) => ({ code: 0, message: 'success', data })

// ============== H11：批量上传 ==============

function mockCos(page, { existsFor = [], headFailsFor = [] } = {}) {
  return page.route('**/admin/api/v1/cos**', (route) => {
    const url = route.request().url()
    const method = route.request().method()
    const key = new URL(url).searchParams.get('key') || ''
    if (url.includes('/cos/status')) {
      return route.fulfill({
        json: ok({ configured: true, bucket: 'bkt', region: 'ap-guangzhou', backup_keep_count: 5 }),
      })
    }
    if (url.includes('/cos/objects')) {
      return route.fulfill({ json: ok({ prefix: '', folders: [], files: [] }) })
    }
    if (url.includes('/cos/exists')) {
      if (headFailsFor.some((f) => key.endsWith(f))) {
        return route.fulfill({ status: 500, json: { code: 500, message: 'COS 服务不可用', data: null } })
      }
      const exists = existsFor.some((f) => key.endsWith(f))
      return route.fulfill({
        json: ok({
          key, exists, size: exists ? 2048 : 0,
          last_modified: exists ? 'Wed, 15 Oct 2026 08:00:00 GMT' : '',
          content_type: exists ? 'audio/mpeg' : '',
        }),
      })
    }
    if (method === 'POST' && url.includes('/cos/upload')) {
      return route.fulfill({ json: ok({ key: 'uploaded', size: 4, content_type: 'audio/mpeg' }) })
    }
    return route.fulfill({ json: ok(null) })
  })
}

const fakeFile = (name) => ({ name, mimeType: 'audio/mpeg', buffer: Buffer.from('DATA') })

test.describe('H11 COS 批量上传汇总', () => {
  test('部分失败：仍逐个上传，汇总给出成功/失败数与失败清单', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { headFailsFor: ['bad.mp3'] })
    const uploads = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/upload')) uploads.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('该目录下暂无内容')).toBeVisible({ timeout: NAV })
    await page.setInputFiles('input[type=file]', [
      fakeFile('ok1.mp3'), fakeFile('bad.mp3'), fakeFile('ok2.mp3'),
    ])

    await expect(page.getByText('上传完成：成功 2 个，失败 1 个')).toBeVisible({ timeout: NAV })
    const report = page.locator('[data-guide="cos-upload-report"]')
    await expect(report).toBeVisible()
    await expect(report).toContainText('本次上传：成功 2 个，失败 1 个')
    await expect(report).toContainText('bad.mp3：同名检测失败，无法确认是否会覆盖已有文件')
    await expect.poll(() => uploads.length, { timeout: NAV }).toBe(2)
  })

  test('覆盖确认处取消：本批立即停止，剩余文件不逐个弹窗', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { existsFor: ['c1.mp3'] })
    const uploads = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/upload')) uploads.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('该目录下暂无内容')).toBeVisible({ timeout: NAV })
    await page.setInputFiles('input[type=file]', [
      fakeFile('c1.mp3'), fakeFile('c2.mp3'), fakeFile('c3.mp3'),
    ])

    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV })
    await box.getByRole('button', { name: '取消' }).click()

    await expect(page.getByText('上传完成：成功 0 个，失败 0 个，取消 3 个')).toBeVisible({ timeout: NAV })
    const report = page.locator('[data-guide="cos-upload-report"]')
    await expect(report).toContainText('取消 3 个')
    // 确认框只出现过一次（c2/c3 不能被挨个弹）
    await expect(page.locator('.el-message-box')).toHaveCount(0)
    expect(uploads).toHaveLength(0)
  })
})

// ============== I59：跨端切换提示 ==============

test.describe('I59 跨端自动切换提示与回链', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => {
      const path = new URL(route.request().url()).pathname
      if (path.endsWith('/reviews') || /\/reviews\/\d+$/.test(path)) {
        return route.fulfill({ json: ok({ total: 0, list: [] }) })
      }
      return route.fulfill({ json: ok({}) })
    })
  })

  test('宽屏打开移动端深链：落点页说明换端，回链能真正回到移动端', async ({ page }) => {
    // 本用例就是要验证「宽屏 → 自动换到桌面端」，视口必须显式是桌面宽度
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/m/review?workflow_id=9&channel_name=讲书阁')

    const notice = page.locator('[data-testid="cross-end-notice"]')
    await expect(notice).toBeVisible({ timeout: NAV })
    await expect(notice).toContainText('已按当前桌面端视图自动切换页面。')
    await expect(page).toHaveURL(/\/review\?.*workflow_id=9/)

    const link = page.locator('[data-testid="cross-end-notice-link"]')
    await expect(link).toHaveText('仍要查看原页面')
    await expect(link).toHaveAttribute('href', /\/m\/review\?.*mode=mobile/)

    await link.click()
    await expect(page).toHaveURL(/\/m\/review\?.*mode=mobile/)
    await expect(page.locator('.m-review')).toBeVisible({ timeout: NAV })
    // 回链把端模式写进会话，后续去掉 query 也不会被再次切回桌面端
    expect(await page.evaluate(() => sessionStorage.getItem('admin_force_mode'))).toBe('mobile')
    // 离开落点后提示失效
    await expect(page.locator('[data-testid="cross-end-notice"]')).toHaveCount(0)
  })

  test('离开落点页后提示不再出现（不跨越页面残留）', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/m/review')
    await expect(page.locator('[data-testid="cross-end-notice"]')).toBeVisible({ timeout: NAV })

    await page.goto('/about')
    await expect(page.locator('[data-testid="cross-end-notice"]')).toHaveCount(0)
  })
})

// ============== I6：移动端审核列表状态保持 ==============

const reviewRow = (id, title) => ({
  id,
  title,
  content_preview: `${title} 摘要`,
  workflow_id: `wf-${id}`,
  workflow_name: `工作流 ${id}`,
  channel_name: '讲书阁',
  channel_type: 'audiobook',
  status: 'pending',
  created_at: '2026-10-27T05:00:00',
})

function mockMobileReview(page, { rows }) {
  const state = { listCalls: 0, actions: [] }
  page.route(`${API}/**`, (route) => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (path.endsWith('/reviews') && req.method() === 'GET') {
      state.listCalls += 1
      return route.fulfill({ json: ok({ total: rows.length, list: rows }) })
    }
    if (/\/reviews\/\d+\/action$/.test(path)) {
      state.actions.push(JSON.parse(req.postData() || '{}'))
      return route.fulfill({ json: ok(null) })
    }
    if (/\/reviews\/\d+$/.test(path)) {
      const id = Number(path.split('/').pop())
      return route.fulfill({
        json: ok({
          id,
          episode_date: '2026-10-27',
          channel_name: '讲书阁',
          workflow_name: `工作流 ${id}`,
          channel_type: 'audiobook',
          created_at: '2026-10-27T05:00:00',
          audio_url: '',
          script: { full_text: `全文 ${id}`, segments: [] },
        }),
      })
    }
    return route.fulfill({ json: ok({}) })
  })
  return state
}

test.describe('I6 移动端审核列表重载保留状态', () => {
  test('处理一条后，其它行的展开态与滚动位置不被重置', async ({ page }) => {
    await setLoginState(page, 'admin')
    await useMobileViewport(page)
    const rows = Array.from({ length: 12 }, (_, i) => reviewRow(i + 1, `第 ${i + 1} 条`))
    const state = mockMobileReview(page, { rows })

    await page.goto('/m/review')
    await expect(page.locator('.m-review__item')).toHaveCount(rows.length, { timeout: NAV })

    // 展开最后一条（需要先滚到底部），详情加载后保持展开
    const last = page.locator('.m-review__item').last()
    await last.scrollIntoViewIfNeeded()
    await last.locator('.m-review__title-row').click()
    await expect(last.locator('.m-review__title-row')).toHaveAttribute('aria-expanded', 'true')
    await expect(last.getByText('全文 12')).toBeVisible({ timeout: NAV })

    const scroller = page.locator('.m-content')
    await scroller.evaluate((el) => { el.scrollTop = el.scrollHeight })
    const before = await scroller.evaluate((el) => el.scrollTop)
    expect(before).toBeGreaterThan(0)

    // 在当前可见位置处理最后一条：通过
    await last.getByRole('button', { name: '通过' }).click()
    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV })
    await box.getByRole('button', { name: '确认通过' }).click()

    await expect.poll(() => state.actions.length, { timeout: NAV }).toBe(1)
    await expect.poll(() => state.listCalls, { timeout: NAV }).toBe(2)
    // 同一行仍是展开态，详情没有被清空
    await expect(page.locator('.m-review__item').last().locator('.m-review__title-row'))
      .toHaveAttribute('aria-expanded', 'true')
    await expect(page.locator('.m-review__item').last().getByText('全文 12')).toBeVisible()
    // 滚动位置保持（差值容忍 1px 取整）
    await expect.poll(() => scroller.evaluate((el) => el.scrollTop), { timeout: NAV })
      .toBeGreaterThan(before - 2)
  })
})

// ============== M66：日志清理排除正在写入的最新日志 ==============

test.describe('M66 日志清理界面口径', () => {
  test('清理目标下方说明最新日志不会被清理', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => {
      const path = new URL(route.request().url()).pathname
      if (path.endsWith('/maintenance/status')) {
        return route.fulfill({
          json: ok({
            db: { db_size_mb: 12.5, playlog_count: 10, workflow_count: 2, review_count: 3, blacklist_count: 0 },
            logs: { total_size_mb: 1.2, file_count: 3 },
            cache: { ttlcache_count: 1, pycache_count: 0, temp_files: 0 },
          }),
        })
      }
      return route.fulfill({ json: ok({}) })
    })

    await page.goto('/maintenance')
    const card = page.locator('.cleanup-card').filter({ hasText: '日志清理' })
    await expect(card).toBeVisible({ timeout: NAV })
    await expect(card.getByText('正在写入的最新日志文件（MorningBrief_*.log）不会被清理')).toBeVisible()
  })
})
