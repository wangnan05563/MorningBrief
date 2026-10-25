import { test, expect } from '@playwright/test'
import { setLoginState, useMobileViewport } from './helpers/mock'

/**
 * 移动端用户反馈页：状态字典单一来源（T02703）
 *
 * 本页此前把 pending/processed/resolved 的中文写了两份、徽章色写了一份、按钮文案又拼了一份，
 * 现在是 `src/constants/enums.js` 的 `FEEDBACK_STATUS` 一处供给。用例按**逐字文案**断言
 * tab / 徽章 / 按钮，证明「统一来源」没有顺手改掉界面；再断言筛选与流转的请求参数，
 * 证明状态取值仍与后端服务层 `_ALLOWED_STATUS` 一致（回归点：把字典键改错会让对应请求失效）。
 */

const ITEMS = [
  {
    id: 1,
    category: '播放问题',
    content: '早间新闻音频卡顿',
    contact: '138****0000',
    created_at: '2026-10-24T09:30:00',
    status: 'pending',
  },
  {
    id: 2,
    category: '内容建议',
    content: '希望增加财经板块',
    contact: '',
    created_at: '2026-10-23T18:05:00',
    status: 'processed',
  },
  {
    id: 3,
    category: '其他',
    content: '已处理完毕的反馈',
    contact: '',
    created_at: '2026-10-22T08:00:00',
    status: 'resolved',
  },
]

const TABS = ['全部', '待处理', '处理中', '已解决']
const BADGES = [
  { text: '待处理', cls: 'm-badge--warn' },
  { text: '处理中', cls: 'm-badge--info' },
  { text: '已解决', cls: 'm-badge--on' },
]

const calls = { list: [], put: [] }

async function mockFeedback(page) {
  await page.route('**/admin/api/v1/**', (route) => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    if (path.endsWith('/events/stream')) {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
      })
    }
    if (path.endsWith('/feedbacks') && req.method() === 'GET') {
      calls.list.push(new URL(req.url()).searchParams.get('status'))
      return route.fulfill({
        json: { code: 0, message: 'success', data: { total: ITEMS.length, list: ITEMS } },
      })
    }
    if (/\/feedbacks\/\d+\/status$/.test(path)) {
      calls.put.push({ path, body: JSON.parse(req.postData() || '{}') })
      return route.fulfill({ json: { code: 0, message: 'success', data: null } })
    }
    return route.fulfill({ json: { code: 0, message: 'success', data: { items: [], list: [], total: 0 } } })
  })
}

test.describe('移动端用户反馈页', () => {
  test.beforeEach(async ({ page }) => {
    calls.list.length = 0
    calls.put.length = 0
    await setLoginState(page, 'admin')
    await useMobileViewport(page)
    await mockFeedback(page)
    await page.goto('/m/manage/feedback')
    await expect(page.locator('.m-fb__item')).toHaveCount(3, { timeout: 30000 })
  })

  test('tab / 徽章 / 按钮文案与状态取值逐字对应', async ({ page }) => {
    await expect(page.locator('.m-fb__tab')).toHaveText(TABS)
    // 首屏不带 status 参数（全量）
    expect(calls.list).toEqual([null])

    const items = page.locator('.m-fb__item')
    for (let i = 0; i < BADGES.length; i++) {
      const badge = items.nth(i).locator('.m-badge')
      await expect(badge).toHaveText(BADGES[i].text)
      await expect(badge).toHaveClass(new RegExp(`\\b${BADGES[i].cls}\\b`))
    }

    // 按钮文案 = 「标记为」+ 下一状态的中文，取自同一份字典
    await expect(items.nth(0).locator('.m-fb__actions button')).toHaveText('标记为处理中')
    await expect(items.nth(1).locator('.m-fb__actions button')).toHaveText('标记为已解决')
    // 已解决是终态：不给按钮
    await expect(items.nth(2).locator('.m-fb__actions')).toHaveCount(0)
  })

  test('切 tab 只按字典值筛选，选中态唯一', async ({ page }) => {
    await page.locator('.m-fb__tab', { hasText: '处理中' }).click()
    await expect(page.locator('.m-fb__tab--active')).toHaveText('处理中')
    expect(calls.list).toEqual([null, 'processed'])

    await page.locator('.m-fb__tab', { hasText: '已解决' }).click()
    expect(calls.list).toEqual([null, 'processed', 'resolved'])
    await expect(page.locator('.m-fb__tab--active')).toHaveText('已解决')
  })

  test('流转按钮发下一状态，成功后本地徽章与按钮同步', async ({ page }) => {
    const first = page.locator('.m-fb__item').nth(0)
    await first.locator('.m-fb__actions button').click()

    await expect.poll(() => calls.put.length).toBe(1)
    // 只断后缀：部署前缀（如 /news）由 baseURL 决定，与本页无关
    expect(calls.put[0].path.endsWith('/admin/api/v1/feedbacks/1/status')).toBe(true)
    expect(calls.put[0].body).toEqual({ status: 'processed' })

    await expect(first.locator('.m-badge')).toHaveText('处理中')
    await expect(first.locator('.m-badge')).toHaveClass(/m-badge--info/)
    await expect(first.locator('.m-fb__actions button')).toHaveText('标记为已解决')
  })
})
