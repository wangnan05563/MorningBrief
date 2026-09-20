import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * 素材库管理页 E2E（T00775）
 *
 * 回归点：后端 GET /admin/api/v1/materials 返回 { total, list }，页面曾按 `items`
 * 取值导致列表恒为空（「从素材库加入书籍」能看到书，点「管理素材」跳过去查不到）。
 * 本用例用真实浏览器渲染真实组件，断言按 `list` 解析后表格能渲染出素材行。
 */

// 素材列表 mock：严格按后端契约 { code, message, data: { total, list } }
const materialsListResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 2,
    list: [
      {
        id: 101,
        source: '我只知道人是什么',
        title: '我只知道人是什么 · 第一章',
        category: '哲学',
        status: 'pending',
        crawled_at: '2026-09-18T10:00:00',
        url: 'list://1/aaaaaaaa',
      },
      {
        id: 102,
        source: '我只知道人是什么',
        title: '我只知道人是什么 · 第二章',
        category: '哲学',
        status: 'pending',
        crawled_at: '2026-09-18T10:01:00',
        url: 'list://1/bbbbbbbb',
      },
    ],
  },
}

const materialDetailResponse = {
  code: 0,
  message: 'success',
  data: {
    id: 102,
    source: '我只知道人是什么',
    source_type: 'list',
    title: '我只知道人是什么 · 第二章',
    content: '正文正文正文',
    category: '哲学',
    status: 'pending',
    channel_id: 1,
    crawled_at: '2026-09-18T10:01:00',
    url: 'list://1/bbbbbbbb',
  },
}

test.describe('素材库管理', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await page.route('**/admin/api/v1/channels**', (route) =>
      route.fulfill({ json: channelsListResponse }),
    )
    await page.route('**/admin/api/v1/materials/**', (route) =>
      route.fulfill({ json: materialDetailResponse }),
    )
    await page.route('**/admin/api/v1/materials**', (route) =>
      route.fulfill({ json: materialsListResponse }),
    )
  })

  test('列表渲染素材（后端返回 list 键）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels/material-library?channelId=1')

    await expect(page.getByText('素材库管理').first()).toBeVisible({ timeout: 30000 })
    // 修复前：data.items 取不到值 → 表格恒为「没有匹配的素材」
    await expect(page.getByText('我只知道人是什么 · 第一章')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('我只知道人是什么 · 第二章')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('没有匹配的素材')).toHaveCount(0)
  })

  test('按素材 ID 深链定位（书单「素材 ID」入口）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels/material-library?channelId=1&materialId=102')

    // 深链定位提示 + 关键词回填命中该素材
    await expect(page.getByText('已定位素材 ID 102')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('我只知道人是什么 · 第二章')).toBeVisible({ timeout: 30000 })
  })
})
