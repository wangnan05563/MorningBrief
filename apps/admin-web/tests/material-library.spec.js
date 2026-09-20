import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * 素材库管理页 E2E（T00775）
 *
 * 回归点：
 * 1) 后端 GET /admin/api/v1/materials 返回 { total, list }，页面曾按 `items`
 *    取值导致列表恒为空（「从素材库加入书籍」能看到书，点「管理素材」跳过去查不到）；
 * 2) 深链定位改走 material_id 精确过滤（不再用标题关键词模糊匹配）；
 * 3) 新增「按书聚合」视图（一行一本书），点书名下钻到该书明细。
 */

const BOOK = '我只知道人是什么'

const RAW_MATERIALS = [
  {
    id: 101,
    source: BOOK,
    source_type: 'list',
    title: `${BOOK} · 第一章`,
    category: '哲学',
    status: 'pending',
    crawled_at: '2026-09-18T10:00:00',
    url: 'list://1/aaaaaaaa',
  },
  {
    id: 102,
    source: BOOK,
    source_type: 'list',
    title: `${BOOK} · 第二章`,
    category: '哲学',
    status: 'pending',
    crawled_at: '2026-09-18T10:01:00',
    url: 'list://1/bbbbbbbb',
  },
  {
    id: 103,
    source: '人民网-文化',
    source_type: 'rss',
    title: '一条文化资讯',
    category: '娱乐',
    status: 'pending',
    crawled_at: '2026-09-18T11:00:00',
    url: 'https://example.com/rss/103',
  },
]

const json = (data) => ({ code: 0, message: 'success', data })

const AGGREGATE_RESPONSE = json({
  total: 1,
  list: [
    {
      source: BOOK,
      category: '哲学',
      chapters: 2,
      pending_chapters: 2,
      sample_material_id: 101,
      latest_at: '2026-09-18T10:01:00',
    },
  ],
})

const DETAIL_RESPONSE = json({
  ...RAW_MATERIALS[1],
  source_type: 'list',
  content: '正文正文正文',
  channel_id: 1,
})

test.describe('素材库管理', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await page.route('**/admin/api/v1/channels**', (route) =>
      route.fulfill({ json: channelsListResponse }),
    )
    // 单一 handler 按 pathname 分支：多个重叠 glob 会互相覆盖（后注册/通配符优先级不可控）
    await page.route('**/admin/api/v1/materials**', (route) => {
      const url = new URL(route.request().url())
      const path = url.pathname
      if (path.endsWith('/materials/aggregate')) {
        return route.fulfill({ json: AGGREGATE_RESPONSE })
      }
      if (!path.endsWith('/materials')) {
        // /materials/{id} 详情
        return route.fulfill({ json: DETAIL_RESPONSE })
      }
      // 明细列表：模拟后端 material_id / source / source_type 过滤
      const id = url.searchParams.get('material_id')
      const source = url.searchParams.get('source')
      const sourceType = url.searchParams.get('source_type')
      let list = RAW_MATERIALS
      if (id) list = RAW_MATERIALS.filter((m) => String(m.id) === id)
      else if (source) list = RAW_MATERIALS.filter((m) => m.source === source)
      else if (sourceType) list = RAW_MATERIALS.filter((m) => (m.source_type || 'list') === sourceType)
      return route.fulfill({ json: json({ total: list.length, list }) })
    })
  })

  test('列表渲染素材（后端返回 list 键）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels/material-library?channelId=1')

    await expect(page.getByText('素材库管理').first()).toBeVisible({ timeout: 30000 })
    // 修复前：data.items 取不到值 → 表格恒为「没有匹配的素材」
    await expect(page.getByText(`${BOOK} · 第一章`)).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(`${BOOK} · 第二章`)).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('一条文化资讯')).toBeVisible({ timeout: 30000 })
  })

  test('来源类型筛选：只看书稿，排除 RSS 资讯', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels/material-library?channelId=1')
    await expect(page.getByText('一条文化资讯')).toBeVisible({ timeout: 30000 })

    await page.locator('.filter-form .el-select').filter({ hasText: '全部渠道' }).click()
    await page.getByRole('option', { name: '书稿文档（上传/手动录入）' }).click()

    // 书稿保留，RSS 资讯被排除（请求带 source_type=list）
    await expect(page.getByText('一条文化资讯')).toHaveCount(0, { timeout: 30000 })
    await expect(page.getByText(`${BOOK} · 第一章`)).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('Total 2')).toBeVisible({ timeout: 30000 })
  })

  test('明细表点「来源」按书名精确下钻', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels/material-library?channelId=1')

    await page.locator('.el-table__row', { hasText: '一条文化资讯' }).getByText('人民网-文化').click()
    await expect(page.getByText('已按书名《人民网-文化》过滤')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('一条文化资讯')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(`${BOOK} · 第一章`)).toHaveCount(0)
  })

  test('按素材 ID 深链精确过滤（书单「素材 ID」入口）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels/material-library?channelId=1&materialId=102')

    await expect(page.getByText('已按素材 ID 102 定位')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(`${BOOK} · 第二章`)).toBeVisible({ timeout: 30000 })
    // 精确过滤：同书另一章（101）不应出现
    await expect(page.getByText(`${BOOK} · 第一章`)).toHaveCount(0)
  })

  test('按书聚合视图：一行一本书，点书名下钻明细', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels/material-library?channelId=1')

    // Element Plus radio-button：真实可点区域是内层 span（label），不是隐藏的 input
    await page.locator('.el-radio-button__inner', { hasText: '按书聚合' }).click()
    await expect(page.getByRole('cell', { name: BOOK, exact: true })).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('2 章（待消费 2）')).toBeVisible({ timeout: 30000 })

    // 下钻：切回明细视图并按书名精确过滤
    await page.getByRole('button', { name: '查看章节' }).click()
    await expect(page.getByText(`已按书名《${BOOK}》过滤`)).toBeVisible({ timeout: 30000 })
    await expect(page.getByText(`${BOOK} · 第一章`)).toBeVisible({ timeout: 30000 })
  })
})
