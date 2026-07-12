import { test, expect } from '@playwright/test'
import {
  loginSuccessResponse,
  loginFailResponse,
  reviewListResponse,
} from './helpers/mock'

/**
 * 登录流程 E2E 测试
 *
 * 覆盖：
 * - 页面元素展示
 * - 表单校验
 * - 成功跳转
 * - 失败提示
 */
test.describe('登录流程', () => {
  // 并行执行时 vite 首次编译各路由组件较慢，5s 默认超时不足
  test.use({ expect: { timeout: 15000 } })

  test.beforeEach(async ({ page }) => {
    // 覆盖 document.hidden/visibilityState，确保 axios 拦截器不会跳过 ElMessage
    // axios 拦截器在页面不可见时静默丢弃 ElMessage，headless 下可能被判定为 hidden
    await page.addInitScript(() => {
      Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
      Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
    })
    // mock 登录成功响应：默认返回成功，单条用例可覆盖为失败
    await page.route('**/admin/api/v1/auth/login', async (route) => {
      await route.fulfill({ json: loginSuccessResponse })
    })
    // mock 审核列表：登录成功后跳转 /review，需要列表数据避免空页面
    await page.route('**/admin/api/v1/reviews*', async (route) => {
      await route.fulfill({ json: reviewListResponse })
    })
  })

  test('登录页显示标题和表单', async ({ page }) => {
    await page.goto('/login')

    // 标题（显式超时避免 vite 首次编译延迟导致 flaky）
    await expect(page.locator('.login-title')).toHaveText('20_News 运营后台', { timeout: 15000 })
    // 用户名/密码输入框存在
    await expect(page.getByPlaceholder('请输入用户名')).toBeVisible({ timeout: 15000 })
    await expect(page.getByPlaceholder('请输入密码')).toBeVisible({ timeout: 15000 })
    // 登录按钮存在
    await expect(page.getByRole('button', { name: '登录' })).toBeVisible({ timeout: 15000 })
  })

  test('空表单提交显示校验错误', async ({ page }) => {
    await page.goto('/login')

    // 直接点击登录，触发 required 校验
    await page.getByRole('button', { name: '登录' }).click()

    // Element Plus 表单校验提示在 DOM 中渲染
    await expect(page.getByText('请输入用户名')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('请输入密码')).toBeVisible({ timeout: 15000 })
  })

  test('正确凭据登录跳转审核页', async ({ page }) => {
    await page.goto('/login')

    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('admin123')
    await page.getByRole('button', { name: '登录' }).click()

    // SPA 导航：等待审核页 tab 出现表示页面已渲染完成
    // 不使用 waitForURL，避免 vite 首次编译期间 socket 连接问题
    await expect(page.getByRole('tab', { name: '待审核' })).toBeVisible({ timeout: 15000 })
    await expect(page).toHaveURL(/\/review$/)
    // localStorage 应有 token
    const token = await page.evaluate(() => window.localStorage.getItem('admin_token'))
    expect(token).toBe('test-token-admin')
  })

  test('错误凭据显示错误提示', async ({ page }) => {
    // 覆盖默认 mock：本次返回业务错误
    await page.route('**/admin/api/v1/auth/login', async (route) => {
      await route.fulfill({ json: loginFailResponse })
    })

    await page.goto('/login')

    await page.getByPlaceholder('请输入用户名').fill('wrong')
    await page.getByPlaceholder('请输入密码').fill('wrong')
    await page.getByRole('button', { name: '登录' }).click()

    // axios 拦截器对 code !== 0 调用 ElMessage.error 显示错误
    await expect(page.locator('.el-message').getByText('用户名或密码错误')).toBeVisible({ timeout: 15000 })
    // 仍停留在登录页
    await expect(page).toHaveURL(/\/login/)
  })
})
