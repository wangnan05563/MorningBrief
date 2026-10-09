import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * 桌面页面内边距（防「内容贴边」回归）
 *
 * 背景：`Layout.vue` 的 `.main-content` 是 `padding: 0`，页面内边距由各页面根容器的
 * `.page-container`（padding: 24px）提供。实测「讲书稿素材池」曾漏加该类 ⇒ 卡片与卡片内的
 * 「书单（顺序即取书顺序）」标题、「从素材库导入」按钮 0px 紧贴侧栏与窗口右缘（用户反馈）。
 * 「素材库管理」同源，「素材录入」（/materials）随后合入，一并纳入本用例。
 *
 * 注：「数据库维护」（/db-admin）是有意的全屏分栏布局（侧栏+数据区自带 16px 内边距），
 * 属 .page-container 约定的白名单例外，不纳入本用例。
 */

const PAGES = [
  { name: '讲书稿素材池', path: '/channels/book-pool?channelId=1' },
  { name: '素材库管理', path: '/channels/material-library?channelId=1' },
  { name: '素材录入', path: '/materials' },
]

/** 期望的最小页面内边距（与 .page-container 的 24px 对齐，留 2px 容差） */
const MIN_GAP = 22

test.describe('桌面页面内边距', () => {
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    // 单一 handler 按 pathname 分支：过宽的 glob（如 **/book-pool**）会把页面文档请求
    // 也拦成 JSON，导致 SPA 根本不渲染
    await page.route('**/admin/api/v1/**', (route) => {
      const path = new URL(route.request().url()).pathname
      const ok = (data) => route.fulfill({ json: { code: 0, message: 'success', data } })
      if (path.endsWith('/channels')) return ok(channelsListResponse.data)
      if (path.includes('/script-mode')) return ok({ enabled: false, pool_total: 0, cursor: 0 })
      if (path.includes('/book-pool')) return ok({ items: [], total: 0, state: { enabled: false } })
      if (path.includes('/materials')) return ok({ total: 0, list: [] })
      return ok({})
    })
  })

  for (const p of PAGES) {
    test(`${p.name}：内容卡片不贴边`, async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.goto(p.path)

      const main = page.locator('.main-content').first()
      await expect(main).toBeVisible()
      const card = page.locator('.el-card').first()
      await expect(card).toBeVisible()

      const { left, right } = await card.evaluate((n, mainSel) => {
        const cardBox = n.getBoundingClientRect()
        const mainBox = n.closest(mainSel).getBoundingClientRect()
        return { left: Math.round(cardBox.left - mainBox.left), right: Math.round(mainBox.right - cardBox.right) }
      }, '.main-content')

      expect(left, `左侧仅 ${left}px（应 ≥ ${MIN_GAP}px，检查页面根容器是否带 page-container）`)
        .toBeGreaterThanOrEqual(MIN_GAP)
      expect(right, `右侧仅 ${right}px（应 ≥ ${MIN_GAP}px，检查页面根容器是否带 page-container）`)
        .toBeGreaterThanOrEqual(MIN_GAP)
    })
  }

  for (const p of PAGES) {
    test(`${p.name}：不得出现空卡片 body 占位（多出一条空白带）`, async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.goto(p.path)

      // 先确认页面真的渲染出来了（存在卡片），否则「没有空 body」会是假通过
      await expect(page.locator('.el-card').first()).toBeVisible()

      // EP 空 body 仍占 20px 上下内边距 = 40px 空白带（如只剩 #header 的标题卡片）
      const empty = await page.evaluate(() =>
        Array.from(document.querySelectorAll('.el-card__body'))
          .filter((b) => {
            const r = b.getBoundingClientRect()
            return r.height > 4 && !(b.textContent || '').trim() && b.children.length === 0
          })
          .map((b) => Math.round(b.getBoundingClientRect().height)),
      )
      expect(empty, `存在空的卡片 body 占位：${JSON.stringify(empty)}px`).toEqual([])
    })
  }
})
