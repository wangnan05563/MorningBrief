import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * T02804：审核列表四类筛选的浏览器级验收（后端全 mock，只验前端接线）。
 *
 * 工单要求的手工路径在这里固化成用例：按审核人筛 → 刷新地址栏仍在该筛选 → 清空筛选回全量。
 * 另外两条是同一批参数里最容易「看起来能用」的坑：
 * - 频道筛选必须真的进请求（`channel_id`），且结果能看见频道名；
 * - 日历上不存在的日期（2026-02-30）不能发给后端，地址栏先回落并点名。
 *
 * 后端过滤逻辑本身由 backend/tests/test_review_list_filters.py 覆盖；本 spec 不重复断数据语义。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

function row(id, reviewerName) {
  return {
    id,
    workflow_id: `wf-00${id}`,
    episode_date: '2026-10-20',
    status: 'pending',
    reviewer_name: reviewerName,
    channel_name: '科技频道',
    created_at: '2026-10-20T05:00:00',
  }
}

const FULL_LIST = ok({ total: 2, list: [row(1, 'alice'), row(2, 'bob')] })
const ALICE_ONLY = ok({ total: 1, list: [row(1, 'alice')] })

test.describe('审核列表筛选（T02804）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    // 兜底必须最先注册（Playwright 后注册的路由优先），避免布局页的其它请求打到真实后端触发 401 跳登录
    await page.route(`${API}/**`, (route) =>
      route.fulfill({ json: ok({ total: 0, list: [], items: [] }) }),
    )
    await page.route(`${API}/channels*`, (route) => route.fulfill({ json: channelsListResponse }))
  })

  test('按审核人筛 → 地址栏保留 → 刷新仍在筛选 → 重置回全量', async ({ page }) => {
    const seen = []
    await page.route(`${API}/reviews*`, (route) => {
      const reviewer = new URL(route.request().url()).searchParams.get('reviewer') || ''
      seen.push(reviewer)
      route.fulfill({ json: reviewer ? ALICE_ONLY : FULL_LIST })
    })

    await page.goto('/review')
    const reviewerInput = page.getByPlaceholder('按审核人用户名前缀')
    await expect(reviewerInput).toBeVisible()
    await expect(page.locator('[data-guide="review-table"] .el-table__row')).toHaveCount(2)

    await reviewerInput.fill('alice')
    await page.getByRole('button', { name: '搜索' }).click()

    // 1) 筛选真的进了请求，且结果按后端返回渲染
    await expect.poll(() => seen.at(-1)).toBe('alice')
    await expect(page.locator('[data-guide="review-table"] .el-table__row')).toHaveCount(1)
    // 2) 地址栏可分享：筛选条件必须落到 URL 上
    await expect(page).toHaveURL(/reviewer=alice/)

    // 3) 刷新后仍在该筛选（URL 是单一事实源，不是只存在内存里）
    await page.reload()
    await expect(reviewerInput).toHaveValue('alice')
    await expect(page).toHaveURL(/reviewer=alice/)
    await expect.poll(() => seen.at(-1)).toBe('alice')
    await expect(page.locator('[data-guide="review-table"] .el-table__row')).toHaveCount(1)

    // 4) 重置回全量：输入框、地址栏、请求三者同时恢复
    await page.getByRole('button', { name: '重置' }).click()
    await expect(reviewerInput).toHaveValue('')
    await expect(page).not.toHaveURL(/reviewer=/)
    await expect.poll(() => seen.at(-1)).toBe('')
    await expect(page.locator('[data-guide="review-table"] .el-table__row')).toHaveCount(2)
  })

  test('频道筛选中后请求带 channel_id，结果能看见频道名', async ({ page }) => {
    const seen = []
    await page.route(`${API}/reviews*`, (route) => {
      const channelId = new URL(route.request().url()).searchParams.get('channel_id')
      seen.push(channelId)
      route.fulfill({ json: channelId ? ALICE_ONLY : FULL_LIST })
    })

    await page.goto('/review')
    await expect(page.locator('[data-guide="review-table"] .el-table__row')).toHaveCount(2)

    // el-select 的占位符在 Element Plus 里是文本节点而不是 input 的 placeholder 属性，
    // 按表单里的下拉容器定位（筛选区只有这一个 select）
    const channelSelect = page.locator('[data-guide="review-filters"] .el-select')
    await channelSelect.click()
    await page.locator('.el-select-dropdown__item', { hasText: '科技频道' }).click()
    await page.getByRole('button', { name: '搜索' }).click()

    await expect.poll(() => seen.at(-1)).toBe('1')
    await expect(page).toHaveURL(/channel_id=1/)
    await expect(page.locator('[data-guide="review-table"] .el-table__row')).toHaveCount(1)
    // 筛完仍不知道结果属于哪个频道，等于筛选没有交付价值
    await expect(page.locator('[data-guide="review-table"]').getByText('科技频道')).toBeVisible()
  })

  test('地址栏里的非法节目日期回落并在页内点名，不发日期参数给后端', async ({ page }) => {
    const seen = []
    await page.route(`${API}/reviews*`, (route) => {
      seen.push(new URL(route.request().url()).searchParams.get('date_from'))
      route.fulfill({ json: FULL_LIST })
    })

    await page.goto('/review?date_from=2026-02-30')

    await expect(page.locator('[data-guide="review-url-corrected"]')).toBeVisible()
    await expect(page.locator('[data-guide="review-url-corrected"]')).toContainText('date_from')
    await expect(page).not.toHaveURL(/date_from=/)
    await expect.poll(() => seen.length).toBeGreaterThan(0)
    expect(seen.every((v) => v === null)).toBe(true)
  })
})
