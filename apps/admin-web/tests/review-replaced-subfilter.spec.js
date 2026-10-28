import { test, expect } from '@playwright/test'
import {
  setLoginState,
  reviewListResponse,
  reviewApprovedListResponse,
  reviewReplacedListResponse,
} from './helpers/mock'

/**
 * T02643（DEC-UX-001 方案 B）验收：replaced 的可见去向
 *
 * 方案 B：第 4 态 replaced 不单开 tab（避免与 SRS 三栏冲突），
 * 在「已通过」tab 内加子筛选决定真正请求的 status。
 * 后端零改动——list_reviews 的 status 是等值过滤，`status=replaced` 现在就查得到。
 */
test.describe('已通过子筛选（DEC-UX-001 方案 B）', () => {
  // 首次按需编译路由组件可能超过默认 5s；test.use({ expect }) 在 Playwright 1.61 是空选项（T02778）
  const expectLong = expect.configure({ timeout: 30000 })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    // 兜底先注册（后注册的 route 优先），避免放行真实后端 401 后被踢到登录页
    await page.route('**/admin/api/v1/**', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { total: 0, list: [], items: [] } } }),
    )
    await page.route('**/admin/api/v1/reviews*', (route) => {
      const status = new URL(route.request().url()).searchParams.get('status')
      const payload =
        status === 'replaced'
          ? reviewReplacedListResponse
          : status === 'approved'
            ? reviewApprovedListResponse
            : reviewListResponse
      return route.fulfill({ json: payload })
    })
  })

  test('「已通过」tab 出现子筛选，默认仍只看 approved', async ({ page }) => {
    await page.goto('/review')
    await page.getByRole('tab', { name: '已通过' }).click()
    await expectLong(page.locator('[aria-label="已通过子筛选"]')).toBeVisible()
    await expectLong(page.getByRole('row').filter({ hasText: 'wf-003' })).toBeVisible()
    await expectLong(page.getByRole('row').filter({ hasText: 'wf-005' })).toHaveCount(0)
  })

  test('切到「仅已替换」后 replaced 记录可见且文案为中文', async ({ page }) => {
    await page.goto('/review')
    await page.getByRole('tab', { name: '已通过' }).click()
    const sub = page.locator('[aria-label="已通过子筛选"]')
    await sub.getByText('仅已替换').click()
    const row = page.getByRole('row').filter({ hasText: 'wf-005' })
    await expectLong(row.getByText('已替换')).toBeVisible()
    await expectLong(page.getByText('replaced', { exact: true })).toHaveCount(0)
  })

  test('切走 tab 时子筛选复位，不会把 replaced 泄漏到别的 tab', async ({ page }) => {
    await page.goto('/review')
    await page.getByRole('tab', { name: '已通过' }).click()
    await page.locator('[aria-label="已通过子筛选"]').getByText('仅已替换').click()
    await page.getByRole('tab', { name: '待审核' }).click()
    await expectLong(page.locator('[aria-label="已通过子筛选"]')).toHaveCount(0)
    // 子筛选复位后待审核 tab 请求的 status 必须是 pending（列表里出现 wf-001、无 wf-005）
    await expectLong(page.getByRole('row').filter({ hasText: 'wf-001' })).toBeVisible()
    await expectLong(page.getByRole('row').filter({ hasText: 'wf-005' })).toHaveCount(0)
  })

  test('再回到「已通过」时子筛选回到默认的仅已通过', async ({ page }) => {
    await page.goto('/review')
    await page.getByRole('tab', { name: '已通过' }).click()
    await page.locator('[aria-label="已通过子筛选"]').getByText('仅已替换').click()
    await expectLong(page.getByRole('row').filter({ hasText: 'wf-005' })).toBeVisible()
    await page.getByRole('tab', { name: '待审核' }).click()
    await page.getByRole('tab', { name: '已通过' }).click()
    // 复位若丢失，这里会继续停在 replaced 子筛选、把 wf-005 当成「已通过」的默认结果
    await expectLong(page.getByRole('row').filter({ hasText: 'wf-003' })).toBeVisible()
    await expectLong(page.getByRole('row').filter({ hasText: 'wf-005' })).toHaveCount(0)
  })
})
