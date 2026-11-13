import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T05724：每日听书素材池「从素材库加入」弹窗必须可见素材库内符合频道条件的全部书籍。
 *
 * 根因：list_candidates 此前排除 book_plan，而找书工具「加入待讲书单」写入的正是 book_plan
 * 占位素材——用户在素材库管理看得到、弹窗里查不到，误以为丢书。
 * 修复：book_plan 占位书在弹窗**可见**，但标记为 needs_upload（待上传书稿）并禁止入池；
 * 上传正文（list 素材）后自动转为「可加入」。
 *
 * 地址带 /news 前缀（路由 base 为 /news/）；数据面全部走 route 拦截，不碰真实库。
 */

const ok = (data) => ({ code: 0, message: 'success', data })

const candidatesData = {
  total: 2,
  items: [
    { book_key: '活着', title: '活着', chapters: 5, pending_chapters: 5, category: '文学', sample_material_id: 1, in_pool: false, needs_upload: false },
    { book_key: '百年孤独', title: '百年孤独', chapters: 0, pending_chapters: 0, category: '文学', sample_material_id: 2, in_pool: false, needs_upload: true },
  ],
}

async function mockApi(page) {
  await page.route('**/admin/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const p = url.pathname.replace(/^\/news\/admin\/api\/v1/, '')

    if (p === '/channels' && route.request().method() === 'GET') {
      return route.fulfill({ json: ok([{ id: 7, name: '每日听书', channel_type: 'audiobook' }]) })
    }
    if (/\/script-mode$/.test(p) && route.request().method() === 'GET') {
      return route.fulfill({ json: ok({ enabled: false, cursor: 0, pool_total: 0, interval_days: 1, loop: false, channel_type: 'audiobook', rss_sources: [], book_rss_sources: [] }) })
    }
    if (p.endsWith('/book-pool') && route.request().method() === 'GET') {
      return route.fulfill({ json: ok({ items: [], total: 0, state: { enabled: false, cursor: 0, pool_total: 0, interval_days: 1, loop: false, channel_type: 'audiobook', rss_sources: [], book_rss_sources: [] } }) })
    }
    if (/\/book-pool\/candidates/.test(p)) {
      return route.fulfill({ json: ok(candidatesData) })
    }
    return route.fulfill({ json: ok({ items: [], list: [], total: 0 }) })
  })
}

test.describe('T05724：素材池候选弹窗必须可见 book_plan 占位书', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockApi(page)
  })

  test('候选弹窗显示 book_plan 占位书为「待上传书稿」且禁止勾选，普通书为「可加入」', async ({ page }) => {
    await page.goto('/news/channels/book-pool?channelId=7')
    // 打开「从素材库加入」弹窗
    await page.getByRole('button', { name: '从素材库加入' }).click()

    const dlg = page.locator('.el-dialog:visible').last()
    await expect(dlg).toBeVisible()

    // 占位书《百年孤独》必须可见（修复前被排除 → 查不到）
    const planRow = dlg.locator('.el-table__row', { hasText: '百年孤独' })
    await expect(planRow).toBeVisible()
    await expect(planRow.getByText('待上传书稿')).toBeVisible()
    // 占位书禁止勾选入池（C103：无正文不可当讲书稿）
    await expect(planRow.locator('.el-checkbox')).toHaveClass(/is-disabled/)

    // 普通书《活着》为「可加入」且可勾选
    const normalRow = dlg.locator('.el-table__row', { hasText: '活着' })
    await expect(normalRow).toBeVisible()
    await expect(normalRow.getByText('可加入')).toBeVisible()
    await expect(normalRow.locator('.el-checkbox')).not.toHaveClass(/is-disabled/)

    // 顶部上传引导提示出现（存在待上传书稿）
    await expect(dlg.getByText(/标记为「待上传书稿」的书尚未上传正文/)).toBeVisible()

    // 总数口径：本频道共 2 本书（含占位）
    await expect(dlg.getByText(/本频道共 2 本书/)).toBeVisible()
  })
})
