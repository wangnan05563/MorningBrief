import { test, expect } from '@playwright/test'
import { setLoginState, reviewListResponse } from './helpers/mock'

/**
 * T03328：后台改密入口（顶栏用户菜单 → 弹窗 → 回登录页）
 *
 * 覆盖：
 * - 入口可见、弹窗打开；
 * - 前端最小长度/两次一致校验先拦住，不发请求；
 * - 旧口令错：后端业务码 400 由统一提示出口弹出，弹窗不关、会话不丢；
 * - 成功：回登录页并清掉本地非敏感态（后端已吊销 token + 清 Cookie）。
 */
test.describe('修改密码', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
      Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
    })
    await setLoginState(page, 'admin')
    // 兜底：Layout 挂载后会静默检查更新等后台请求，别放行到真实后端（会 401 踢人）
    await page.route('**/admin/api/v1/**', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { total: 0, list: [], items: [] } } }),
    )
    await page.route('**/admin/api/v1/reviews*', (route) =>
      route.fulfill({ json: reviewListResponse }),
    )
  })

  async function openDialog(page) {
    await page.goto('/review')
    await expect(page.getByRole('tab', { name: '待审核' })).toBeVisible({ timeout: 30000 })
    // el-dropdown 默认 hover 触发；click 前先 hover，不依赖某个版本对 click 的处理
    await page.locator('.user-info').hover()
    const item = page.locator('.el-dropdown-menu__item', { hasText: '修改密码' })
    await item.waitFor({ state: 'visible', timeout: 10000 })
    await item.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible({ timeout: 10000 })
    return dialog
  }

  test('用户菜单里有改密入口并打开弹窗', async ({ page }) => {
    const dialog = await openDialog(page)
    await expect(dialog).toContainText('当前密码')
    await expect(dialog).toContainText('新密码')
  })

  test('新密码过短与两次不一致被前端拦下，不发请求', async ({ page }) => {
    let calls = 0
    page.on('request', (req) => {
      if (req.url().includes('/auth/change-password')) calls += 1
    })
    const dialog = await openDialog(page)

    await dialog.getByPlaceholder('请输入当前密码').fill('Old-Pass-123')
    await dialog.getByPlaceholder('至少 8 位').fill('short')
    await dialog.getByPlaceholder('请再次输入新密码').fill('short')
    await dialog.getByRole('button', { name: '确认修改' }).click()

    await expect(dialog.getByText('新密码至少 8 位')).toBeVisible()
    expect(calls).toBe(0)

    await dialog.getByPlaceholder('至少 8 位').fill('New-Pass-456')
    await dialog.getByPlaceholder('请再次输入新密码').fill('New-Pass-999')
    await dialog.getByRole('button', { name: '确认修改' }).click()
    await expect(dialog.getByText('两次输入的新密码不一致')).toBeVisible()
    expect(calls).toBe(0)
  })

  test('旧口令错误：统一提示出口报错，弹窗保持打开', async ({ page }) => {
    await page.route('**/admin/api/v1/auth/change-password', (route) =>
      route.fulfill({ json: { code: 400, message: '原密码错误', data: null } }),
    )
    const dialog = await openDialog(page)

    await dialog.getByPlaceholder('请输入当前密码').fill('Wrong-Pass-1')
    await dialog.getByPlaceholder('至少 8 位').fill('New-Pass-456')
    await dialog.getByPlaceholder('请再次输入新密码').fill('New-Pass-456')
    await dialog.getByRole('button', { name: '确认修改' }).click()

    await expect(page.locator('.el-message')).toContainText('原密码错误')
    await expect(dialog).toBeVisible()
    await expect(page).toHaveURL(/\/review$/)
    expect(await page.evaluate(() => localStorage.getItem('admin_role'))).toBe('admin')
  })

  test('成功：提示后用新口令重新登录', async ({ page }) => {
    let payload = null
    await page.route('**/admin/api/v1/auth/change-password', async (route) => {
      payload = route.request().postDataJSON()
      await route.fulfill({ json: { code: 0, message: 'success', data: { success: true, relogin_required: true } } })
    })
    const dialog = await openDialog(page)

    await dialog.getByPlaceholder('请输入当前密码').fill('Old-Pass-123')
    await dialog.getByPlaceholder('至少 8 位').fill('New-Pass-456')
    await dialog.getByPlaceholder('请再次输入新密码').fill('New-Pass-456')
    await dialog.getByRole('button', { name: '确认修改' }).click()

    await expect(page.locator('.el-message')).toContainText('密码已修改')
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    expect(payload).toEqual({ old_password: 'Old-Pass-123', new_password: 'New-Pass-456' })
    const state = await page.evaluate(() => ({
      role: localStorage.getItem('admin_role'),
      username: localStorage.getItem('admin_username'),
    }))
    expect(state).toEqual({ role: null, username: null })
  })
})
