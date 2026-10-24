import { test, expect } from '@playwright/test'
import { useMobileViewport, llmMetricsResponse } from './helpers/mock'

/**
 * 隐藏期间丢弃的 401，切回前台后补跳登录页（T02614）
 *
 * 原行为：`document.hidden` 时的 401 直接 reject，不跳转、不清本地态、也不留痕迹。
 * 好处是后台标签页不会把人踢下线；坏处是用户切回前台后界面仍停在过期会话上，
 * 要等下一次点击失败才反应。新语义：隐藏期只记标记，切回前台的恢复窗口结束时
 * （2s）补跳登录页；没丢弃过 401 则什么都不做——尤其不能为了判断会话再打一次接口。
 *
 * 测试要点：
 * - 请求必须在**可见时发出**、隐藏后才收到 401（window-guard 在隐藏期本就丢弃新请求，
 *   所以用例用「挂住响应」而不是「隐藏后点击」来构造真实时序）；
 * - 隐藏期收到 401 不得立刻跳走/清态（原契约）；
 * - 移动端的补跳目标必须按当前端落到 /m/login，且 redirect 保留 /m 路径。
 */

const API = '**/admin/api/v1'

/** 可控遮罩：让页面像真实后台标签页一样「隐藏但仍能收响应」 */
async function setupVisibility(page) {
  await page.addInitScript(() => {
    let hidden = false
    Object.defineProperty(document, 'hidden', { get: () => hidden, configurable: true })
    Object.defineProperty(document, 'visibilityState', {
      get: () => (hidden ? 'hidden' : 'visible'),
      configurable: true,
    })
    window.__setHidden = (v) => {
      hidden = v
      document.dispatchEvent(new Event('visibilitychange'))
    }
  })
}

/** 会话过期的 401：后端会带中文原因，前端按端跳登录页 */
const expired = { status: 401, json: { code: 401, message: '登录已过期，请重新登录' } }

/**
 * 只给首个文档注入登录态。
 *
 * 不能直接用 helpers 的 setLoginState：那是 addInitScript，**每次整页导航都会重跑**。
 * 补跳登录页正是整页导航，重跑会把刚被清掉的 admin_username/admin_role 又填回去，
 * 「跳转后本地态已清」就永远断不出来（测试自己制造的假象）。
 */
async function seedLoginOnce(page) {
  await page.addInitScript(() => {
    if (window.sessionStorage.getItem('__e2e_login_seeded__')) return
    window.sessionStorage.setItem('__e2e_login_seeded__', '1')
    localStorage.setItem('admin_token', 'test-token-admin')
    localStorage.setItem('admin_username', 'admin')
    localStorage.setItem('admin_role', 'admin')
  })
}

/** 一个可外部放行的 Promise，用来把响应「扣在手里」跨越隐藏/可见切换 */
function deferred() {
  let resolve
  const promise = new Promise((r) => {
    resolve = r
  })
  return { promise, resolve }
}

test.describe('隐藏期的 401 在恢复前台后补跳登录页', () => {
  test.beforeEach(async ({ page }) => {
    await setupVisibility(page)
    // PC 外壳启动时会静默查一次更新；给个确定答案，避免未 mock 的请求干扰计数
    await page.route(`${API}/about/check-update*`, (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { has_update: false } } })
    )
    await page.route(`${API}/events/stream**`, (route) =>
      route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
    )
  })

  test('PC：隐藏期间收到 401 不立即踢人，恢复后带 redirect 跳 /login', async ({ page }) => {
    await seedLoginOnce(page)
    const gate = deferred()
    let hold = false
    let intercepted
    const requestHeld = new Promise((r) => {
      intercepted = r
    })
    await page.route(`${API}/stats/llm-metrics*`, async (route) => {
      if (!hold) return route.fulfill({ json: llmMetricsResponse })
      intercepted()
      await gate.promise
      return route.fulfill(expired)
    })

    await page.goto('/stats/llm-metrics')
    await expect(page.locator('[data-guide="llm-metrics-page"]')).toBeVisible({ timeout: 30000 })

    // 地址栏口径以页面实际值为准：dev 的 router base 是 /news/，而 vite base 是 /，
    // 两者在开发态并不一致（生产同为 /news/）。这里只断言「隐藏期间一次都没被改写」。
    const beforeHide = page.url()
    hold = true
    await page.getByRole('button', { name: /刷新/ }).click()
    await requestHeld

    // 请求已发出，此时才切到后台，再放行 401 响应
    await page.evaluate(() => window.__setHidden(true))
    gate.resolve()
    await page.waitForTimeout(400)

    // 原契约：隐藏期收到 401 不得立刻清态/跳转（否则后台标签页会被踢下线）
    expect(page.url()).toBe(beforeHide)
    expect(await page.evaluate(() => localStorage.getItem('admin_username'))).toBe('admin')

    await page.evaluate(() => window.__setHidden(false))
    await page.waitForURL(/\/login\?redirect=/, { timeout: 15000 })

    const url = new URL(page.url())
    // 应用路由 base 是 /news/：补跳写入 /login 后由 router 规范化成 /news/login
    // （即票据要求的 PC 登录地址；生产下 base 前缀的换算由单测 login-target.test.mjs 锁定）
    expect(url.pathname).toBe('/news/login')
    // redirect 必须指回刚才那一页（含 query）。dev 的 vite base 为 '/'，因此这里保留
    // router base 前缀 /news/；生产 base 为 '/news/' 时会剥掉它，两种基址都在单测里断言。
    const original = new URL(beforeHide)
    expect(url.searchParams.get('redirect')).toBe(original.pathname + original.search)
    // 非敏感的本地态随会话一起清掉（token 在 HttpOnly Cookie 里，JS 清不了）
    expect(await page.evaluate(() => localStorage.getItem('admin_username'))).toBeNull()
    expect(await page.evaluate(() => localStorage.getItem('admin_role'))).toBeNull()
  })

  test('移动端：补跳 /m/login，redirect 保留 /m 路径', async ({ page }) => {
    await useMobileViewport(page)
    await seedLoginOnce(page)
    await page.route(`${API}/m/dashboard-summary*`, (route) =>
      route.fulfill({
        json: { code: 0, message: 'success', data: { today: {}, pending_review: 0, unread_message: 1 } },
      })
    )
    await page.route(`${API}/m/inbox*`, (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            total: 1,
            unread_count: 1,
            items: [
              {
                id: 1,
                read: false,
                level: 'info',
                msg_type: 'system',
                title: '测试消息',
                body: '内容',
                created_at: '2026-10-24T10:00:00',
              },
            ],
          },
        },
      })
    )

    const gate = deferred()
    let hold = false
    let intercepted
    const requestHeld = new Promise((r) => {
      intercepted = r
    })
    await page.route(`${API}/m/inbox/mark-read`, async (route) => {
      if (!hold) return route.fulfill({ json: { code: 0, message: 'success', data: null } })
      intercepted()
      await gate.promise
      return route.fulfill(expired)
    })

    await page.goto('/m/message')
    const markAll = page.getByRole('button', { name: '全部已读' })
    await expect(markAll).toBeVisible({ timeout: 30000 })

    hold = true
    await markAll.click()
    await requestHeld
    const beforeHide = page.url()
    await page.evaluate(() => window.__setHidden(true))
    gate.resolve()
    await page.waitForTimeout(400)

    expect(page.url()).toBe(beforeHide)
    expect(await page.evaluate(() => localStorage.getItem('admin_username'))).toBe('admin')

    await page.evaluate(() => window.__setHidden(false))
    await page.waitForURL(/\/m\/login\?redirect=/, { timeout: 15000 })

    const url = new URL(page.url())
    // 与 PC 同源：路由 base /news/ 把 /m/login 规范化为 /news/m/login（即票据要求的地址）
    expect(url.pathname).toBe('/news/m/login')
    const original = new URL(beforeHide)
    expect(url.searchParams.get('redirect')).toBe(original.pathname + original.search)
  })

  test('未丢弃过 401：恢复前台不跳转、也不额外请求', async ({ page }) => {
    await seedLoginOnce(page)
    let calls = 0
    await page.route(`${API}/stats/llm-metrics*`, (route) => {
      calls += 1
      return route.fulfill({ json: llmMetricsResponse })
    })

    await page.goto('/stats/llm-metrics')
    await expect(page.locator('[data-guide="llm-metrics-page"]')).toBeVisible({ timeout: 30000 })
    // 等首屏请求沉降：断言的是「恢复前后请求数不变」，不能被挂载期请求算进来
    await page.waitForTimeout(600)
    const before = calls
    const beforeHide = page.url()

    await page.evaluate(() => window.__setHidden(true))
    await page.waitForTimeout(300)
    await page.evaluate(() => window.__setHidden(false))
    // 越过 2s 恢复窗口，确认它结束也不会「顺手探活」
    await page.waitForTimeout(2600)

    expect(page.url()).toBe(beforeHide)
    expect(calls).toBe(before)
    expect(await page.evaluate(() => localStorage.getItem('admin_username'))).toBe('admin')
  })
})
