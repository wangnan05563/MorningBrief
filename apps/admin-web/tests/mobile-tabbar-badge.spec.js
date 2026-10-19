import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 移动端底部导航未读/待办角标（T02510 / FR-UX-601 需求项②、T02323 I27）
 *
 * 要防的回归正是 I27 抱怨的那件事：运营停在「首页」tab 时不知道「审批」里压了几条待办，
 * 只能逐个 tab 点进去看。角标本身是壳层能力，不依赖具体页面数据，
 * 所以这里只 mock `/m/dashboard-summary`（H5 侧唯一的计数来源，移动端首页一直在用，
 * 本单把它提到壳层，不新增接口），其余接口给空数据即可。
 *
 * 刷新触发点有 4 个（进入 / 切 tab / 回前台 / SSE 工作流完成事件），全部复用同一次请求，
 * 外加 10s 节流——NFR-UX-03 明确「新增错误态/重试不引入额外轮询」，
 * 因此这里刻意**不**用定时器轮询，改由 BroadcastChannel 模拟跨标签页广播
 * （与 SSE 分发共用同一个 `_dispatch` 通道），验证「事件到了角标才变」这条链。
 *
 * 视口取 375px（NFR-UX-04 的验收宽度）。
 */

/** 角标接口返回值：'FAIL' 表示接口挂了 */
let summary = { today: 0, pending_review: 3, unread_message: 5 }

async function mockShell(page) {
  await page.route('**/admin/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/events/stream')) {
      // 给一条正常的 SSE 首帧，避免测试里出现无意义的重连噪声
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
      })
    }
    if (path.endsWith('/m/dashboard-summary')) {
      if (summary === 'FAIL') {
        return route.fulfill({ status: 500, json: { code: 500, message: '计数接口挂了', data: null } })
      }
      return route.fulfill({ json: { code: 0, message: 'success', data: summary } })
    }
    return route.fulfill({ json: { code: 0, message: 'success', data: { items: [], list: [], total: 0 } } })
  })
}

/** 触发一次「SSE/跨标签页」刷新（壳层订阅的是 workflow.completed） */
async function fireWorkflowCompleted(page) {
  await page.evaluate(() => {
    const ch = new BroadcastChannel('news_sse')
    ch.postMessage({ type: 'workflow.completed', data: { workflow_id: 1 }, timestamp: Date.now() / 1000 })
    ch.close()
  })
}

const badge = (page, name) => page.locator(`[data-guide="mobile-tab-badge-${name}"]`)

test.describe('移动端底部导航角标', () => {
  test.use({ viewport: { width: 375, height: 667 } })

  test.beforeEach(async ({ page }) => {
    summary = { today: 0, pending_review: 3, unread_message: 5 }
    await setLoginState(page, 'admin')
    await mockShell(page)
  })

  test('有待办/未读 → 审批、消息各画一个角标，数字语义进 aria-label', async ({ page }) => {
    await page.goto('/m/home')

    await expect(badge(page, 'review')).toHaveText('3')
    await expect(badge(page, 'message')).toHaveText('5')
    // 无障碍：单独一个「3」念出来没有意义，必须带「待办/未读」语义前缀
    await expect(page.locator('.m-tabbar__item').filter({ has: badge(page, 'review') })).toHaveAttribute(
      'aria-label',
      '审批（待办 3）',
    )
    await expect(page.locator('.m-tabbar__item').filter({ has: badge(page, 'message') })).toHaveAttribute(
      'aria-label',
      '消息（未读 5）',
    )
    // 无计数的 tab 不画角标（首页/管理/我的）
    await expect(badge(page, 'home')).toHaveCount(0)
  })

  test('计数为 0 → 不画角标（而不是画一个 0 骗人说「看到了但没处理」）', async ({ page }) => {
    summary = { today: 0, pending_review: 0, unread_message: 0 }
    await page.goto('/m/home')
    await expect(page.locator('.m-tabbar__badge')).toHaveCount(0)
    await expect(page.locator('.m-tabbar__item').nth(1)).toHaveAttribute('aria-label', '审批')
  })

  test('超过 99 → 折叠为 99+（三位数会把 10px 小字顶到相邻 tab）', async ({ page }) => {
    summary = { today: 0, pending_review: 137, unread_message: 99 }
    await page.goto('/m/home')
    await expect(badge(page, 'review')).toHaveText('99+')
    await expect(badge(page, 'message')).toHaveText('99')
  })

  test('SSE 工作流完成事件 → 角标数字跟着刷新（不是靠定时器轮询）', async ({ page }) => {
    await page.goto('/m/home')
    await expect(badge(page, 'review')).toHaveText('3')

    const requests = []
    page.on('request', (r) => {
      if (r.url().includes('/m/dashboard-summary')) requests.push(r.url())
    })

    summary = { today: 0, pending_review: 7, unread_message: 5 }
    await fireWorkflowCompleted(page)
    await expect(badge(page, 'review')).toHaveText('7')
    // 一次事件 = 一次请求；没有第二条并发请求
    expect(requests.length).toBeLessThanOrEqual(1)
  })

  test('计数接口失败 → 沉默并沿用上一次值（归零比不显示更危险）', async ({ page }) => {
    await page.goto('/m/home')
    await expect(badge(page, 'review')).toHaveText('3')

    const toasts = []
    page.on('console', (m) => {
      if (m.type() === 'error') toasts.push(m.text())
    })

    summary = 'FAIL'
    await fireWorkflowCompleted(page)
    // 等一轮：既不该改数字，也不该冒错误提示
    await page.waitForTimeout(600)
    await expect(badge(page, 'review')).toHaveText('3')
    await expect(page.locator('.el-message')).toHaveCount(0)
    expect(toasts.filter((t) => t.includes('计数'))).toEqual([])
  })

  test('375px 下角标不撑破 tabbar：无横向滚动且角标完整可见', async ({ page }) => {
    summary = { today: 0, pending_review: 12, unread_message: 8 }
    await page.goto('/m/home')

    const bar = page.locator('.m-tabbar')
    await expect(bar).toBeVisible()
    const geom = await bar.evaluate((el) => ({
      scrollW: el.scrollWidth,
      clientW: el.clientWidth,
    }))
    expect(geom.scrollW, '角标把 tabbar 撑出横向滚动了').toBeLessThanOrEqual(geom.clientW)

    for (const name of ['review', 'message']) {
      const b = badge(page, name)
      await expect(b).toBeInViewport()
      const box = await b.boundingBox()
      const barBox = await bar.boundingBox()
      expect(box.x, '角标越出 tabbar 左边界').toBeGreaterThanOrEqual(barBox.x - 1)
      expect(box.x + box.width, '角标越出 tabbar 右边界').toBeLessThanOrEqual(barBox.x + barBox.width + 1)
      expect(box.height).toBeGreaterThan(0)
    }
  })

  test('角标底色用对比度达标的 #C9433B（不是同色相但只有 3.4:1 的 #E6544A）', async ({ page }) => {
    await page.goto('/m/home')
    await expect(badge(page, 'review')).toHaveCSS('background-color', 'rgb(201, 67, 59)')
    await expect(badge(page, 'review')).toHaveCSS('color', 'rgb(255, 255, 255)')
  })
})
