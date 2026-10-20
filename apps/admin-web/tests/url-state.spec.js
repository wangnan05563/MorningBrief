import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 深链参数与状态保留（T02511 / FR-UX-602，验收口径 ACC-UX-601#2、#3）
 *
 * 这一份要防的回归，是「链接不可信」这一整类问题：
 * - #3 刷新 `/review?tab=approved&page=3` 必须仍在原状态（此前 tab/page 只活在组件内存里，刷新即丢）；
 * - #2 从 `/m/manage/users` 可一键返回 `/m/manage`（此前移动端 hidden 子页只有一条底部 tab 条，
 *   进得去回不来）；
 * - 跨端重定向此前把 `/queue?status=failed` 抹平成 `/m/home`，深链与筛选状态一起丢；
 * - C68：`?channelId=` 指向不存在的频道时静默按空池渲染，用户以为看的是地址里那个频道。
 *
 * 校验规则本体（回落/钳制/开放重定向）在 tests/unit/url-state.test.mjs 里逐条断言；
 * 这一份只覆盖**接线后的用户可见行为**——页面是否真的按 URL 起、校正是否真的可见、
 * 返回入口是否真的能点。两层分开，改动时不会出现「规则改坏了但 e2e 恰好没测那条」。
 *
 * 数据面：审核列表 mock 成「pending 2 条 / approved 1 条但 total=100 / rejected 0 条」——
 * total=100 专门用来验 `?page=999` 的钳制（分到最后一页 10 而不是退回第 1 页的空表），
 * rejected 留空专门用来验空态文案（若文案仍写死「待审核」，这条用例会当场失败）。
 *
 * 地址一律写成 `/news/…`：路由 base 是 `/news/`（生产同前缀），但 dev 由 Vite 挂在 `/`，
 * 直接用裸路径会让 vue-router 把 base 之外的路径解析成 `/`，测出来的就不是目标页了。
 */

const reviewsByStatus = {
  pending: { total: 2, list: [{ id: 1, episode_date: '2026-07-08', workflow_id: 'wf-001', status: 'pending', created_at: '2026-07-08T05:00:00' }, { id: 2, episode_date: '2026-07-07', workflow_id: 'wf-002', status: 'pending', created_at: '2026-07-07T05:00:00' }] },
  approved: { total: 100, list: [{ id: 3, episode_date: '2026-07-06', workflow_id: 'wf-003', status: 'approved', created_at: '2026-07-06T05:00:00' }] },
  rejected: { total: 0, list: [] },
}

/** 频道夹具：1 是资讯、2 是讲书稿；99999 故意不存在（C68 用例） */
const channels = [
  { id: 1, name: '科技前沿', channel_type: 'news', enabled: true },
  { id: 2, name: '讲书阁', channel_type: 'audiobook', enabled: true },
]

const ok = (data) => ({ route: null, body: { code: 0, message: 'success', data } })

async function mockApi(page, { emptyReviews = false } = {}) {
  await page.route('**/admin/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path.endsWith('/events/stream')) {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
      })
    }
    if (path.endsWith('/reviews')) {
      if (emptyReviews) return route.fulfill({ json: ok({ total: 0, list: [], items: [] }).body })
      const status = url.searchParams.get('status') || 'pending'
      return route.fulfill({ json: ok(reviewsByStatus[status] || { total: 0, list: [] }).body })
    }
    // 频道列表：后端这里返回的就是**数组本体**（见 tests/helpers/mock.js 的 channelsListResponse），
    // 包成 {items,list} 会让页面拿不到选项、静默渲染成空池——那是夹具的错，不是产品的错
    if (path === '/news/admin/api/v1/channels' || path.endsWith('/channels')) {
      return route.fulfill({ json: ok(channels).body })
    }
    if (path.endsWith('/script-mode')) {
      return route.fulfill({ json: ok({ enabled: false, sort_strategy: 'sequential' }).body })
    }
    if (path.endsWith('/book-pool') || path.endsWith('/book-pool/candidates')) {
      return route.fulfill({ json: ok({ items: [], list: [], total: 0 }).body })
    }
    if (path.endsWith('/queue/stats') || path.includes('/workflows')) {
      return route.fulfill({ json: ok({ items: [], list: [], total: 0, running: 0, pending: 0, failed: 0 }).body })
    }
    if (path.endsWith('/m/dashboard-summary')) {
      return route.fulfill({ json: ok({ today: 0, pending_review: 0, unread_message: 0 }).body })
    }
    return route.fulfill({ json: ok({ items: [], list: [], total: 0 }).body })
  })
}

const activeTabText = (page) => page.locator('.el-tabs__item.is-active')
const currentPageText = (page) => page.locator('.el-pagination .is-active')

test.describe('PC 审核列表：tab/分页写进 URL', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockApi(page)
  })

  test('ACC-UX-601#3 深链 ?tab=approved&page=3 直接落在那一页', async ({ page }) => {
    const req = page.waitForRequest((r) => /\/reviews\?/.test(r.url()) && new URL(r.url()).searchParams.get('page') === '3')
    await page.goto('/news/review?tab=approved&page=3')
    expect(new URL((await req).url()).searchParams.get('status')).toBe('approved')
    await expect(activeTabText(page)).toHaveText('已通过')
    await expect(currentPageText(page)).toHaveText('3')
  })

  test('点第 2 页后地址栏出现 page=2（刷新可回到同一视图）', async ({ page }) => {
    await page.goto('/news/review')
    await expect(activeTabText(page)).toHaveText('待审核')
    // 默认值不进 URL：刚进页面时地址是干净的
    expect(new URL(page.url()).searchParams.has('page')).toBe(false)
    // approved 那页 total=100 / size=10 ⇒ 有第 2 页可点
    await page.goto('/news/review?tab=approved')
    await page.locator('.el-pagination .number', { hasText: '2' }).first().click()
    await expect(page).toHaveURL(/page=2/)
    expect(new URL(page.url()).searchParams.get('tab')).toBe('approved')
  })

  test('翻页用 replace 不塞历史：后退键仍能离开这一页', async ({ page }) => {
    await page.goto('/news/review?tab=approved')
    const entries = await page.evaluate(() => window.history.length)
    await page.locator('.el-pagination .number', { hasText: '2' }).first().click()
    await expect(page).toHaveURL(/page=2/)
    await page.locator('.el-pagination .number', { hasText: '3' }).first().click()
    await expect(page).toHaveURL(/page=3/)
    // 两次翻页各一次 replace ⇒ 历史条目数不变
    expect(await page.evaluate(() => window.history.length)).toBe(entries)
  })

  test('?page=999 钳到最后一页并改写地址（不是退回第 1 页的空表）', async ({ page }) => {
    await page.goto('/news/review?tab=approved&page=999')
    // total=100 / size=10 ⇒ 最后一页是 10
    await expect(currentPageText(page)).toHaveText('10')
    expect(new URL(page.url()).searchParams.get('page')).toBe('10')
    await expect(page.locator('[data-guide="review-url-corrected"]')).toBeVisible()
    await expect(page.locator('[data-guide="review-url-corrected"]')).toContainText('超过上限')
  })

  test('非法 ?tab=replaced / ?page=abc 回落默认值并在页内点名', async ({ page }) => {
    await page.goto('/news/review?tab=replaced&page=abc')
    await expect(activeTabText(page)).toHaveText('待审核')
    const alert = page.locator('[data-guide="review-url-corrected"]')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('链接里的参数已修正')
    await expect(alert).toContainText('tab=replaced')
    await expect(alert).toContainText('page=abc')
  })

  test('空态文案跟着 tab 走（已通过 tab 不说「暂无待审核稿件」）', async ({ page }) => {
    await page.goto('/news/review?tab=rejected')
    await expect(page.locator('.el-empty__description')).toHaveText('暂无已打回的稿件')
  })
})

test.describe('跨端重定向：path 与 query 一起带走', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockApi(page)
  })

  test('手机视口打开 /queue?status=failed → 落到移动端队列页且筛选保留', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/news/queue?status=failed')
    await expect(page).toHaveURL(/\/m\/manage\/queue/)
    expect(new URL(page.url()).searchParams.get('status')).toBe('failed')
  })

  test('手机视口打开 /review?tab=approved&page=3 → /m/review 且参数不丢', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/news/review?tab=approved&page=3')
    await expect(page).toHaveURL(/\/m\/review/)
    const q = new URL(page.url()).searchParams
    expect(q.get('tab')).toBe('approved')
    expect(q.get('page')).toBe('3')
  })

  test('桌面视口访问 /m/review?workflow_id=9 → 回 PC 审核页并带上 workflow_id', async ({ page }) => {
    await page.goto('/news/m/review?workflow_id=9')
    // 必须等重定向落定：`/\/review/` 这种宽松写法在 `/m/review` 上就会先匹配成功，
    // 于是紧接着读 page.url() 抓到的是跳转前的地址（实测竞态）
    await expect(page).toHaveURL(/\/news\/review\?workflow_id=9/)
    expect(new URL(page.url()).pathname).toBe('/news/review')
    expect(new URL(page.url()).searchParams.get('workflow_id')).toBe('9')
  })

  test('桌面视口访问移动端管理子页 → 等价表命中 PC 队列页', async ({ page }) => {
    // /m/manage/* 的第二段是 manage，等价表里映射到 PC 的 /queue——这类页面有同名对端，
    // 不该被丢到首页；?from= 只留给「确实没有对端」的页面（下一条用例）
    await page.goto('/news/m/manage/feedback')
    await expect(page).toHaveURL(/\/news\/queue/)
    expect(new URL(page.url()).searchParams.has('from')).toBe(false)
  })

  test('手机视口打开只有桌面版的页面 → 移动端首页并保留来源 ?from=', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/news/stats')
    await expect(page).toHaveURL(/\/m\/home/)
    expect(new URL(page.url()).searchParams.get('from')).toBe('/stats')
  })

})

test.describe('未登录深链：?redirect= 带回原页（T02511）', () => {
  // 这一组故意不调 setLoginState——只有缺登录态才看得见守卫写的 redirect 参数
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
  })

  test('未登录时深链进 ?redirect=，登录成功后回到那一页', async ({ page }) => {
    // 清掉登录态（不给 setLoginState 即未登录；role 缺失守卫会跳登录页）
    await page.goto('/news/review?tab=approved&page=3')
    await expect(page).toHaveURL(/\/news\/login/)
    const redirect = new URL(page.url()).searchParams.get('redirect')
    expect(redirect).toBe('/review?tab=approved&page=3')
    await page.route('**/admin/api/v1/auth/login', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { token: 't', username: 'admin', role: 'admin' } } }),
    )
    await page.fill('input[type="text"], input:not([type="password"])', 'admin')
    await page.fill('input[type="password"]', 'secret')
    // 提交用密码框回车（Login.vue 的 el-input 绑了 @keyup.enter="handleLogin"）；
    // 登录按钮是 IconButton 组件，选择器不稳，没必要为它加锚点
    await page.press('input[type="password"]', 'Enter')
    // 登录成功后回到深链指向的那一页（tab + page 都保留）；
    // 必须等导航落定再断言，否则抓到的是跳转中间态（实测竞态）
    await expect(page).toHaveURL(/\/news\/review\?tab=approved/)
    expect(new URL(page.url()).pathname).toBe('/news/review')
    expect(new URL(page.url()).searchParams.get('page')).toBe('3')
  })

  test('?redirect=//evil.com 不会被跟着跳出去（开放重定向收口）', async ({ page }) => {
    await page.goto('/news/login?redirect=%2F%2Fevil.com')
    // 地址栏里留着 evil.com 的**参数原文**是允许的（那是用户自己贴进来的），
    // 要防的是登录成功后 location 真的跳到那个域——所以断言落在站内
    await page.route('**/admin/api/v1/auth/login', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { token: 't', username: 'admin', role: 'admin' } } }),
    )
    await page.fill('input[type="text"], input:not([type="password"])', 'admin')
    await page.fill('input[type="password"]', 'secret')
    await page.press('input[type="password"]', 'Enter')
    await expect(page).toHaveURL(/\/news\/review/)
    expect(new URL(page.url()).hostname).toBe('localhost')
  })
})

test.describe('移动端：hidden 子页返回入口 + 作用域空态', () => {
  test.use({ viewport: { width: 375, height: 667 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    // 移动端这几条测的是**空态文案**，夹具必须给空列表
    await mockApi(page, { emptyReviews: true })
  })

  test('ACC-UX-601#2 /m/manage/users 顶部有返回键，一键回 /m/manage', async ({ page }) => {
    await page.goto('/news/m/manage/users')
    const back = page.locator('[data-guide="mobile-appbar-back"]')
    await expect(back).toBeVisible()
    await expect(back).toHaveAttribute('aria-label', /返回/)
    await back.click()
    await expect(page).toHaveURL(/\/m\/manage$/)
  })

  test('一级页（/m/home）不显示返回键', async ({ page }) => {
    await page.goto('/news/m/home')
    await expect(page.locator('[data-guide="mobile-appbar-back"]')).toHaveCount(0)
  })

  test('从队列带 workflow_id 进来的空态说「这一条没有待审稿件」并可返回队列', async ({ page }) => {
    await page.goto('/news/m/review?workflow_id=999&channel_name=科技前沿')
    const empty = page.locator('[data-guide="m-review-empty"]')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText('暂无待审稿件')
    await expect(empty).toContainText('科技前沿')
    // 关键：作用域模式绝不能出现「暂无待审内容 🎉」——那是「整个队列干净了」的意思
    await expect(empty).not.toContainText('暂无待审内容')
    await page.locator('[data-guide="m-review-back-queue"]').click()
    await expect(page).toHaveURL(/\/m\/manage\/queue/)
  })

  test('非作用域（不带 workflow_id）空态保持原庆祝文案', async ({ page }) => {
    await page.goto('/news/m/review')
    await expect(page.locator('[data-guide="m-review-empty"]')).toContainText('暂无待审内容')
  })
})

test.describe('讲书稿素材池：深链 channelId 校验存在性（C68）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockApi(page)
  })

  test('?channelId=99999 查无此频道 → 回落真实频道、改写地址并显式告警', async ({ page }) => {
    await page.goto('/news/channels/book-pool?channelId=99999')
    const alert = page.locator('[data-guide="book-pool-dead-channel"]')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('99999')
    await expect(alert).toContainText('已切换')
    // 地址栏不再撒谎：channelId 被替换成真正生效的那个（夹具里的讲书稿频道 2）
    await expect.poll(() => new URL(page.url()).searchParams.get('channelId')).toBe('2')
  })

  test('合法 ?channelId=1 原样命中，不误报、不改写', async ({ page }) => {
    await page.goto('/news/channels/book-pool?channelId=1')
    await expect(page.locator('[data-guide="book-pool-dead-channel"]')).toHaveCount(0)
    expect(new URL(page.url()).searchParams.get('channelId')).toBe('1')
  })

  test('切换频道把选择写回地址（分享出去就是同一频道）', async ({ page }) => {
    await page.goto('/news/channels/book-pool?channelId=1')
    await page.locator('[data-guide="book-pool-channel"]').click()
    await page.locator('.el-select-dropdown__item', { hasText: '讲书阁' }).first().click()
    await expect.poll(() => new URL(page.url()).searchParams.get('channelId')).toBe('2')
  })
})
