import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * 频道编辑弹窗「频道图标」区按钮可读性回归（T00775 姊妹问题）
 *
 * 背景（实测）：variables.scss 把 Element Plus 的 primary light-3/5/7/9 全部指向
 * 同一色值 --color-primary-light，而 EP 的禁用态 plain 按钮用 light-5 作文字色、
 * light-9 作背景色 —— 二者相等 ⇒ 文字与背景同色，按钮看起来"完全空白"。
 * 用户反馈「频道图标右侧按钮默认显示空白」即此（AI 生成 按钮未填关键词时禁用）。
 *
 * 本用例断言：禁用态按钮必须有可见文字，且文字色 != 背景色（防止再次出现隐形按钮）。
 */

async function computed(btn) {
  return btn.evaluate((n) => {
    const c = getComputedStyle(n)
    return { color: c.color, background: c.backgroundColor, text: n.textContent.trim() }
  })
}

/** 解析 computed 的 rgb()/rgba() 为 [r,g,b] */
function rgb(str) {
  const m = str.match(/rgba?\(([^)]+)\)/)
  if (!m) throw new Error(`无法解析颜色: ${str}`)
  return m[1].split(',').slice(0, 3).map((v) => Number(v.trim()))
}

/** WCAG 相对亮度 */
function luminance([r, g, b]) {
  const f = (v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}

/** WCAG 对比度（1 = 完全同色 ⇒ 文字不可见） */
function contrastRatio(fg, bg) {
  const [l1, l2] = [luminance(rgb(fg)), luminance(rgb(bg))].sort((a, b) => b - a)
  return (l1 + 0.05) / (l2 + 0.05)
}

/**
 * 禁用态按钮的可辨性判据
 *
 * WCAG 对"禁用控件"豁免对比度要求，故不按 4.5:1 卡；但文字与背景必须明显可辨：
 * 实测复现的缺陷（light-5 == light-9 == #B5EAD7）对比度 = 1.0（文字完全隐形），
 * 仅把文字改成同色系浅色也只有 ~1.1。取 2.0 作为"看得出这是个按钮"的下限。
 */
const MIN_CONTRAST = 2.0

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

  test('编辑态：禁用的「AI 生成」按钮文字可见（不得与背景同色）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')
    await page.getByRole('button', { name: '编辑' }).first().click()

    const btn = page.locator('.ai-gen-row .el-button').first()
    await expect(btn).toBeVisible()
    // 未填关键词 → 仍应按语义禁用
    await expect(btn).toBeDisabled()
    await expect(btn).toHaveText('AI 生成')

    const { color, background, text } = await computed(btn)
    expect(text).toBe('AI 生成')
    const ratio = contrastRatio(color, background)
    expect(ratio, `文字 ${color} 与背景 ${background} 对比度仅 ${ratio.toFixed(2)}，按钮会"看起来空白"`)
      .toBeGreaterThanOrEqual(MIN_CONTRAST)
  })

  test('新增态：禁用的「上传图标」按钮文字可见（实底按钮同样不得隐形）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')
    await page.getByRole('button', { name: '新增频道' }).click()

    // el-upload 包裹层也带 role=button，须限定到真实 <button> 上
    const btn = page.locator('button.el-button').filter({ hasText: '上传图标' })
    await expect(btn).toBeVisible()
    await expect(btn).toBeDisabled()

    const { color, background, text } = await computed(btn)
    expect(text).toBe('上传图标')
    const ratio = contrastRatio(color, background)
    expect(ratio, `文字 ${color} 与背景 ${background} 对比度仅 ${ratio.toFixed(2)}，按钮会"看起来空白"`)
      .toBeGreaterThanOrEqual(MIN_CONTRAST)
  })
})
