import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * 频道编辑弹窗「频道图标」区按钮可识别性回归（T00775 姊妹问题，T00812 后适配）
 *
 * 背景（实测）：variables.scss 把 Element Plus 的 primary light-3/5/7/9 全部指向
 * 同一色值 --color-primary-light，而 EP 的禁用态 plain 按钮用 light-5 作文字色、
 * light-9 作背景色 —— 二者相等 ⇒ 文字与背景同色，按钮看起来"完全空白"。
 * 用户反馈「频道图标右侧按钮默认显示空白」即此（AI 生成 按钮未填关键词时禁用）。
 *
 * T00812 后按钮为纯图标（无文字）：可识别性改为断言「可访问名 + 图标可见」，
 * 替代原「文字对比度」检查；禁用态语义由 aria-label 保证。
 */

test.describe('频道图标区按钮可读性', () => {
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await page.route('**/admin/api/v1/channels**', (route) => {
      if (route.request().method() === 'GET') return route.fulfill({ json: channelsListResponse })
      return route.fulfill({ json: { code: 0, message: 'ok', data: {} } })
    })
    await page.route('**/admin/api/v1/ai-config**', (route) =>
      route.fulfill({ json: { code: 0, message: 'ok', data: {} } }),
    )
    await page.route('**/book-pool**', (route) =>
      route.fulfill({ json: { code: 0, message: 'ok', data: { enabled: false, exists: false } } }),
    )
  })

  test('编辑态：禁用的「AI 生成」图标按钮可识别（不得隐形）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')
    await page.getByRole('button', { name: '编辑' }).first().click()

    // T00812 后为纯图标按钮：以可访问名定位，断言图标可见（替代原文字对比度检查）
    const btn = page.getByRole('button', { name: 'AI 生成' }).first()
    await expect(btn).toBeVisible()
    await expect(btn).toBeDisabled()
    await expect(btn.locator('.el-icon')).toBeVisible()
  })

  test('新增态：禁用的「上传图标」图标按钮可识别（实底按钮同样不得隐形）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')
    await page.getByRole('button', { name: '新增频道' }).click()

    // el-upload 包裹层也带 role=button，须限定到真实 <button> 上（用 aria-label 属性精确定位）
    const btn = page.locator('button.el-button[aria-label="上传图标"]').first()
    await expect(btn).toBeVisible()
    await expect(btn).toBeDisabled()
    await expect(btn.locator('.el-icon')).toBeVisible()
  })
})
