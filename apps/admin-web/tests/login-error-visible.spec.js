import { test, expect } from '@playwright/test'
import { loginSuccessResponse, useMobileViewport } from './helpers/mock'

/**
 * 登录失败可见性（T02498：FR-UX-304）
 *
 * 要求两条：给可见原因、保留输入并聚焦密码框。此前的实现把提示完全交给
 * axios 拦截器，而登录这条路径上拦截器要么把 401 当成「跳登录页」（人已经在
 * 登录页，于是什么都不发生），要么弹一条三秒即散的 toast——用户抬头时既不知道
 * 错在哪，也不知道自己是不是真点了按钮。现在由登录页自己常驻显示原因。
 */
const BANNER = '[data-testid="login-error"]'

async function keepPageVisible(page) {
  await page.addInitScript(() => {
    Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
    Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
  })
}

async function mockLogin(page, handler) {
  await page.route('**/admin/api/v1/auth/login', handler)
}

test.describe('登录失败可见', () => {

  test.beforeEach(async ({ page }) => {
    await keepPageVisible(page)
    // 其它接口给空壳响应，避免后端未启动时的网络错误干扰断言
    await page.route('**/admin/api/v1/**', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: {} } }))
  })

  test('业务错误码 401：常驻显示后端给的原文', async ({ page }) => {
    await mockLogin(page, (route) =>
      route.fulfill({ json: { code: 401, message: '用户名或密码错误', data: null } }))
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('bad')
    await page.getByRole('button', { name: '登录' }).click()

    await expect(page.locator(BANNER)).toContainText('用户名或密码错误', { timeout: 30000 })
    await expect(page.getByPlaceholder('请输入用户名')).toHaveValue('admin')
    await expect(page.getByPlaceholder('请输入密码')).toBeFocused()
  })

  test('HTTP 401：不再静默跳转，页面给出原因', async ({ page }) => {
    await mockLogin(page, (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ code: 401, message: '登录已过期，请重新登录', data: null }),
      }))
    // T02633 验收：只要复位地址真的判对了「已在登录页」，401 就不该触发整页导航。
    // 仅断言 URL 停在 /login 不够——刷新回 /login 也满足；这里数文档加载次数。
    await page.addInitScript(() => {
      window.__docLoads = (window.__docLoads || 0) + 1
    })
    await page.goto('/login')
    const loadsBefore = await page.evaluate(() => window.__docLoads)
    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('bad')
    await page.getByRole('button', { name: '登录' }).click()

    await expect(page.locator(BANNER)).toContainText('登录已过期', { timeout: 30000 })
    // 仍在登录页，没有被 location.href 刷走
    await expect(page).toHaveURL(/\/login$/)
    expect(await page.evaluate(() => window.__docLoads)).toBe(loadsBefore)
  })

  test('账号被禁用（403）显示对应原因', async ({ page }) => {
    await mockLogin(page, (route) =>
      route.fulfill({ json: { code: 403, message: '账号已禁用', data: null } }))
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill('olduser')
    await page.getByPlaceholder('请输入密码').fill('x')
    await page.getByRole('button', { name: '登录' }).click()

    await expect(page.locator(BANNER)).toContainText('账号已禁用', { timeout: 30000 })
  })

  test('连不上后端时给人话，而不是 Network Error', async ({ page }) => {
    await mockLogin(page, (route) => route.abort('connectionrefused'))
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('x')
    await page.getByRole('button', { name: '登录' }).click()

    await expect(page.locator(BANNER)).toContainText('无法连接服务器', { timeout: 30000 })
  })

  test('重试成功后横幅消失并进入系统', async ({ page }) => {
    let attempt = 0
    await mockLogin(page, (route) => {
      attempt += 1
      return attempt === 1
        ? route.fulfill({ json: { code: 401, message: '用户名或密码错误', data: null } })
        : route.fulfill({ json: loginSuccessResponse })
    })
    await page.route('**/admin/api/v1/reviews*', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { list: [], total: 0 } } }))
    await page.goto('/login')

    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('wrong')
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page.locator(BANNER)).toBeVisible({ timeout: 30000 })

    // 第二次成功：横幅不应残留（否则用户以为还没登录进去）
    await page.getByPlaceholder('请输入密码').fill('admin123')
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page.locator(BANNER)).toHaveCount(0, { timeout: 30000 })
    await expect(page).toHaveURL(/\/review$/, { timeout: 30000 })
  })

  test('移动端登录页同样常驻原因并聚焦密码', async ({ page }) => {
    await mockLogin(page, (route) =>
      route.fulfill({ json: { code: 401, message: '用户名或密码错误', data: null } }))
    // 移动端登录页按视口分流：手机视口才留在 /m/login（T02511 跨端口径）
    await useMobileViewport(page)
    await page.goto('/m/login')

    await page.getByPlaceholder('账号').fill('admin')
    await page.getByPlaceholder('密码').fill('bad')
    await page.getByRole('button', { name: '登 录' }).click()

    await expect(page.locator(BANNER)).toContainText('用户名或密码错误', { timeout: 30000 })
    await expect(page.getByPlaceholder('账号')).toHaveValue('admin')
    await expect(page.getByPlaceholder('密码')).toBeFocused()
  })
})

/**
 * T02634：连续失败 ≥3 次的下一步引导。
 *
 * 事实依据见 `src/utils/loginError.js` 的注释：后端没有失败计数与锁定策略，
 * 所以引导只说「找管理员 / 不会锁定」，且只在横幅下方追加一行——不新增 toast。
 */
const GUIDE = '[data-testid="login-retry-guide"]'
const WRONG = { code: 401, message: '用户名或密码错误', data: null }

test.describe('登录连续失败引导（T02634）', () => {
  test.beforeEach(async ({ page }) => {
    await keepPageVisible(page)
    // toast 三秒自动消失，事后查 DOM 会漏（toHaveCount 还会一直重试到它消失为止）。
    // 用 MutationObserver 把「出现过」记下来，才算真的证明没有第二条提示出口。
    await page.addInitScript(() => {
      window.__toastsSeen = 0
      new MutationObserver((records) => {
        for (const r of records) {
          for (const n of r.addedNodes) {
            if (n.nodeType !== 1) continue
            if (n.classList?.contains('el-message') || n.querySelector?.('.el-message')) {
              window.__toastsSeen += 1
            }
          }
        }
      }).observe(document, { childList: true, subtree: true })
    })
    await page.route('**/admin/api/v1/**', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: {} } }))
  })

  test('第 1/2 次不出现，第 3 次追加引导且不叠第二条提示', async ({ page }) => {
    let attempts = 0
    await mockLogin(page, (route) => {
      attempts += 1
      // 第 4 次（用正确密码）成功，用来验证成功后引导不再出现
      return attempts < 4
        ? route.fulfill({ json: WRONG })
        : route.fulfill({ json: loginSuccessResponse })
    })
    await page.route('**/admin/api/v1/reviews*', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { list: [], total: 0 } } }))

    await page.goto('/login')
    const btn = page.getByRole('button', { name: '登录' })
    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('wrong')

    await btn.click()
    await expect.poll(() => attempts).toBe(1)
    await expect(page.locator(BANNER)).toContainText('用户名或密码错误')
    await expect(page.locator(GUIDE)).toHaveCount(0)

    await btn.click()
    await expect.poll(() => attempts).toBe(2)
    await expect(page.locator(GUIDE)).toHaveCount(0)

    await btn.click()
    await expect.poll(() => attempts).toBe(3)
    await expect(page.locator(GUIDE)).toBeVisible({ timeout: 30000 })
    await expect(page.locator(GUIDE)).toContainText('联系管理员')
    await expect(page.locator(GUIDE)).toContainText('不会锁定')
    // 不出现第二条提示出口：失败仍然只有常驻横幅一条
    expect(await page.evaluate(() => window.__toastsSeen)).toBe(0)

    // 成功后引导随离开登录页一起消失，且不会残留在列表页
    await page.getByPlaceholder('请输入密码').fill('admin123')
    await btn.click()
    await expect(page).toHaveURL(/\/review$/, { timeout: 30000 })
    await expect(page.locator(GUIDE)).toHaveCount(0)
  })

  test('移动端第 3 次失败同样追加引导', async ({ page }) => {
    await mockLogin(page, (route) => route.fulfill({ json: WRONG }))
    await useMobileViewport(page)
    await page.goto('/m/login')

    const btn = page.getByRole('button', { name: '登 录' })
    await page.getByPlaceholder('账号').fill('admin')
    await page.getByPlaceholder('密码').fill('wrong')

    for (let i = 0; i < 2; i++) {
      await btn.click()
      await expect(page.locator(BANNER)).toBeVisible({ timeout: 30000 })
    }
    await expect(page.locator(GUIDE)).toHaveCount(0)

    await btn.click()
    await expect(page.locator(GUIDE)).toBeVisible({ timeout: 30000 })
    await expect(page.locator(GUIDE)).toContainText('不会锁定')
  })
})
