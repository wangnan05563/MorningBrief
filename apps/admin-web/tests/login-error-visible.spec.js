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
  test.use({ expect: { timeout: 30000 } })

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
    await page.goto('/login')
    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('bad')
    await page.getByRole('button', { name: '登录' }).click()

    await expect(page.locator(BANNER)).toContainText('登录已过期', { timeout: 30000 })
    // 仍在登录页，没有被 location.href 刷走
    await expect(page).toHaveURL(/\/login$/)
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
