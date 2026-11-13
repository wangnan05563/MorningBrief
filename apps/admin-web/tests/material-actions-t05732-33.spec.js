import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T05732 + T05733：找书 → 占位书 → 上传书稿链路的两个入口补齐。
 *
 * T05732：
 * - 找书工具「随机」结果行必须带可用的书源下载链接（后端 random_books 已返回 url，
 *   结果表已有「打开链接」列；本用例守「随机路径也有链接、无 url 行不渲染空跳转」）；
 * - 素材库管理明细操作栏新增「下载」按钮（打开来源链接；无链接禁用不报错）。
 * T05733：
 * - 素材库管理对「空书单」（book_plan 占位书）提供「上传书稿」入口（明细行 +
 *   聚合行），跳素材录入页并预填频道与书名——上传后章节按书名聚合回该书。
 *
 * 地址带 /news 前缀（路由 base 为 /news/）；数据面全部走 route 拦截，不碰真实库。
 */

const ok = (data) => ({ code: 0, message: 'success', data })

/** 素材明细：1 条 book_plan 占位（带书源 url）+ 1 条普通 list 素材（无 url） */
const materialsData = {
  total: 2,
  list: [
    { id: 1, channel_id: 7, source: '百年孤独', source_type: 'book_plan', title: '《百年孤独》', summary: '待上传书稿（找书工具加入待讲书单）', category: '文学', status: 'pending', crawled_at: '2026-11-13T09:00:00', url: 'https://pan.example.com/bl', media_type: 'text', media_url: null, media_thumb_url: null },
    { id: 2, channel_id: 7, source: '活着', source_type: 'list', title: '活着 · 第一章', summary: null, category: '文学', status: 'pending', crawled_at: '2026-11-13T08:00:00', url: null, media_type: 'text', media_url: null, media_thumb_url: null },
  ],
}

const aggregateData = {
  total: 2,
  list: [
    { source: '百年孤独', category: '文学', chapters: 1, pending_chapters: 1, sample_material_id: 1, latest_at: '2026-11-13T09:00:00', channel_id: 7, all_placeholder: true },
    { source: '活着', category: '文学', chapters: 3, pending_chapters: 3, sample_material_id: 2, latest_at: '2026-11-13T08:00:00', channel_id: 7, all_placeholder: false },
  ],
}

const randomData = {
  scanned_categories: ['index(1000 分类)'],
  failed_categories: [],
  hits: [
    { title: '活着', author: '余华', category: '文学', url: 'https://pan.example.com/hz' },
    { title: '无链接书', author: '佚名', category: '其他', url: '' },
  ],
  index_ready: true,
}

async function mockLibraryApi(page) {
  await page.route('**/admin/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const p = url.pathname.replace(/^\/news\/admin\/api\/v1/, '')

    if (p === '/channels' && route.request().method() === 'GET') {
      // 后端这里返回数组本体（与 tests/helpers/mock.js 同口径）
      return route.fulfill({ json: ok([{ id: 7, name: '每日听书', channel_type: 'audiobook' }]) })
    }
    if (p === '/materials' && route.request().method() === 'GET') {
      return route.fulfill({ json: ok(materialsData) })
    }
    if (p === '/materials/aggregate') {
      return route.fulfill({ json: ok(aggregateData) })
    }
    return route.fulfill({ json: ok({ items: [], list: [], total: 0 }) })
  })
}

async function mockBookFinderApi(page) {
  await page.route('**/admin/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const p = url.pathname.replace(/^\/news\/admin\/api\/v1/, '')

    if (p === '/channels' && route.request().method() === 'GET') {
      return route.fulfill({ json: ok([{ id: 7, name: '每日听书', channel_type: 'audiobook' }]) })
    }
    if (p === '/ebooks/random') return route.fulfill({ json: ok(randomData) })
    if (p === '/ebooks/index/status') {
      return route.fulfill({ json: ok({ ready: true, book_count: 1000, category_count: 20, built_at: '2026-11-13T08:00:00', stale: false, build: { running: false } }) })
    }
    if (p === '/ebooks/categories') return route.fulfill({ json: ok({ count: 1, categories: ['文学'] }) })
    return route.fulfill({ json: ok({ items: [], list: [], total: 0 }) })
  })
}

test.describe('T05733：素材库管理「空书单」上传入口', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockLibraryApi(page)
  })

  test('明细视图：book_plan 占位行显示「上传书稿」，点击跳素材录入并预填频道与书名', async ({ page }) => {
    await page.goto('/news/channels/material-library')
    const planRow = page.locator('.el-table__row', { hasText: '《百年孤独》' })
    const uploadBtn = planRow.getByRole('button', { name: '上传书稿' })
    await expect(uploadBtn).toBeVisible()
    // 普通行（list 素材）不应出现上传入口
    await expect(page.locator('.el-table__row', { hasText: '活着' }).getByRole('button', { name: '上传书稿' })).toHaveCount(0)

    await uploadBtn.click()
    // 深链带频道与书名，素材录入页预填
    await expect(page).toHaveURL(/\/news\/materials\?channelId=7&source=/)
    await expect(page).toHaveURL(/source=%E7%99%BE%E5%B9%B4%E5%AD%A4%E7%8B%AC/)
    const sourceInput = page.locator('input[placeholder="上传后自动填入文件名"]')
    await expect(sourceInput).toHaveValue('百年孤独')
    await expect(page.locator('.el-message').filter({ hasText: '预填来源与频道' })).toBeVisible()
  })

  test('聚合视图：空书单（all_placeholder）行显示「上传书稿」，真书不显示', async ({ page }) => {
    await page.goto('/news/channels/material-library')
    // el-radio-button 的 role=radio 内层 span 会拦截 pointer events，按容器类名点
    await page.locator('.el-radio-button', { hasText: '按书聚合' }).click()
    const planRow = page.locator('.el-table__row', { hasText: '百年孤独' })
    await expect(planRow.getByRole('button', { name: '上传书稿' })).toBeVisible()
    await expect(page.locator('.el-table__row', { hasText: '活着' }).getByRole('button', { name: '上传书稿' })).toHaveCount(0)
  })
})

test.describe('T05732：素材库「下载」按钮 + 找书工具随机结果下载链接', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
  })

  test('素材库明细：有来源链接的行「下载」可用，无链接的行禁用且不报错', async ({ page }) => {
    // window.open(url, '_blank', 'noopener') 打开的新页面不保证触发 popup 事件，
    // 注入探针记录调用参数来断言「点击 → 打开来源链接」
    await page.addInitScript(() => {
      window.__openedUrls = []
      const orig = window.open
      window.open = (url, target, features) => {
        window.__openedUrls.push(String(url))
        return orig ? orig.call(window, url, target, features) : null
      }
    })
    await mockLibraryApi(page)
    await page.goto('/news/channels/material-library')

    const planRow = page.locator('.el-table__row', { hasText: '《百年孤独》' })
    const dl = planRow.getByRole('button', { name: '下载', exact: true })
    await expect(dl).toBeVisible()
    await expect(dl).toBeEnabled()
    await dl.click()
    await expect.poll(() => page.evaluate(() => window.__openedUrls)).toContain('https://pan.example.com/bl')

    // 无链接行：下载按钮禁用（可见但不报错）
    const noUrlRow = page.locator('.el-table__row', { hasText: '活着' })
    await expect(noUrlRow.getByRole('button', { name: /下载（无来源链接）/ })).toBeDisabled()
  })

  test('找书工具「随机」：结果行带书源下载链接，无链接行不渲染空跳转', async ({ page }) => {
    await mockBookFinderApi(page)
    await page.goto('/news/ebooks')
    await page.getByRole('button', { name: '随机' }).click()

    const hitRow = page.locator('[data-guide="ebooks-results"] .el-table__row', { hasText: '活着' })
    await expect(hitRow).toBeVisible()
    await expect(hitRow.getByRole('link', { name: '打开链接 ↗' })).toHaveAttribute('href', 'https://pan.example.com/hz')

    // 无 url 的随机结果行：不渲染空跳转链接
    const noUrlRow = page.locator('[data-guide="ebooks-results"] .el-table__row', { hasText: '无链接书' })
    await expect(noUrlRow).toBeVisible()
    await expect(noUrlRow.getByRole('link', { name: '打开链接 ↗' })).toHaveCount(0)
  })
})
