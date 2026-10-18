import { test, expect } from '@playwright/test'
import {
  setLoginState,
  reviewReplacedListResponse,
  reviewReplacedDetailResponse,
} from './helpers/mock'

/**
 * 审核第 4 态 replaced 的文案口径（T02501 / FR-UX-402 的决策无关部分）
 *
 * 后端 review 有 4 态（backend/app/models/review.py ReviewStatus），且「替换段落」是
 * 待审核详情页一步可达的动作（ReviewDetail.vue 的 el-radio value="replace"），
 * 所以 replaced 记录随时会真实产生。修复前列表/详情只有 3 态映射，
 * statusText 走 `|| status` 兜底会把英文枚举裸值当文案显示。
 *
 * 本 spec 只锁一条决策无关的不变量：渲染器绝不把枚举裸值当文案。
 * replaced 的「可见去向」（第 4 个 tab / 并入已通过加子筛选 / 并入已打回）由 DEC-UX-001 拍板，
 * 拍板前不改 tab 结构，因此这里不覆盖 tab，用直达详情 + 注入列表载荷两种方式触达渲染器。
 */
test.describe('审核 4 态文案口径', () => {
  test.use({ expect: { timeout: 30000 } })

  async function mockReviews(page, listPayload) {
    await setLoginState(page, 'admin')
    // 兜底要先注册（后注册的 route 优先），避免放行到真实后端 401 后被踢到登录页
    await page.route('**/admin/api/v1/**', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { total: 0, list: [], items: [] } } }),
    )
    await page.route('**/admin/api/v1/reviews/5', (route) =>
      route.fulfill({ json: reviewReplacedDetailResponse }),
    )
    await page.route('**/admin/api/v1/reviews*', (route) =>
      route.fulfill({ json: listPayload }),
    )
  }

  test('详情页展示 replaced 记录时显示「已替换」而非裸枚举', async ({ page }) => {
    await mockReviews(page, reviewReplacedListResponse)
    await page.goto('/review/5')
    await expect(page.getByText('已替换')).toBeVisible()
    await expect(page.getByText('replaced', { exact: true })).toHaveCount(0)
  })

  test('列表收到 replaced 行时状态列显示「已替换」', async ({ page }) => {
    await mockReviews(page, reviewReplacedListResponse)
    await page.goto('/review')
    const row = page.getByRole('row').filter({ hasText: 'wf-005' })
    await expect(row.getByText('已替换')).toBeVisible()
    await expect(page.getByText('replaced', { exact: true })).toHaveCount(0)
  })

  test('既有 3 态文案不被本次补齐破坏', async ({ page }) => {
    await mockReviews(page, {
      code: 0,
      message: 'success',
      data: {
        total: 3,
        list: [
          { id: 11, episode_date: '2026-07-03', workflow_id: 'wf-p', status: 'pending', created_at: '2026-07-03T05:00:00' },
          { id: 12, episode_date: '2026-07-02', workflow_id: 'wf-a', status: 'approved', created_at: '2026-07-02T05:00:00' },
          { id: 13, episode_date: '2026-07-01', workflow_id: 'wf-r', status: 'rejected', created_at: '2026-07-01T05:00:00' },
        ],
      },
    })
    await page.goto('/review')
    for (const label of ['待审核', '已通过', '已打回']) {
      // 「待审核」同时是 tab 文案，按行断言避免误命中
      await expect(page.getByRole('row').filter({ hasText: label }).first()).toBeVisible()
    }
  })
})
