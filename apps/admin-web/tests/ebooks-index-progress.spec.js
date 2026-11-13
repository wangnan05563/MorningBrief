import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 找书工具：索引构建进度可视化（T05719）
 *
 * 把原有的「静态文本 索引构建中 / 20/1000 个分类」升级为**动态进度条**，
 * 并新增「构建中 / 初始化中 / 构建失败」三态。后端 /ebooks/index/status 的
 * build 状态（running / done / total / started_at / error）驱动前端渲染。
 *
 * 数据面全部走 route 拦截——不碰真实库；地址带 /news 前缀（路由 base 为 /news/）。
 */

function ok(data) {
  return { code: 0, message: 'success', data }
}

/** 全量拦截找书工具页依赖的接口，status 由 caller 覆盖 */
async function mockEbooks(page, statusData) {
  await page.route('**/admin/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const p = url.pathname.replace(/^\/news\/admin\/api\/v1/, '')

    if (p === '/ebooks/index/status') return route.fulfill({ json: ok(statusData) })
    if (p === '/ebooks/index/rebuild') return route.fulfill({ json: ok({ triggered: true }) })
    if (p === '/ebooks/categories') return route.fulfill({ json: ok({ categories: ['文学', '科技'] }) })
    if (p === '/channels' && route.request().method() === 'GET') return route.fulfill({ json: ok([]) })
    if (p === '/events/stream') {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
      })
    }
    return route.fulfill({ json: ok({ items: [], list: [], total: 0 }) })
  })
}

test.describe('找书工具：索引构建进度条（T05719）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
  })

  test('构建进行中：渲染进度条并显示「已完成/总数 (百分比)」与预计剩余', async ({ page }) => {
    const startedAt = new Date(Date.now() - 10 * 1000).toISOString() // 已耗时 10s
    await mockEbooks(page, {
      ready: false,
      book_count: 0,
      category_count: 0,
      age_days: null,
      stale: false,
      build: { running: true, done: 20, total: 1000, failed: 0, started_at: startedAt, finished_at: null, error: null },
    })
    await page.goto('/news/ebooks')

    // 进度条（el-progress，带 .index-progress 类）可见，且「构建索引」按钮禁用（构建中）
    // 注意 indexReady=false 时按钮文案是「构建索引」，「重建索引」只在索引就绪后出现
    const progress = page.locator('.index-progress')
    await expect(progress).toBeVisible()
    await expect(page.getByRole('button', { name: '构建索引' })).toBeDisabled()

    // 实时文本：已完成/总数 与 百分比（20/1000 = 2%）
    await expect(page.locator('.index-card')).toContainText('构建中：20 / 1000 个分类')
    await expect(page.locator('.index-card')).toContainText('（2%）')
    // 预计剩余：10s 完成 20 个 ⇒ 速率 2 个/秒 ⇒ 剩余 980 个 ≈ 490 秒 ≈ 8 分 10 秒
    await expect(page.locator('.index-card')).toContainText('预计剩余')
  })

  test('总数未知时进入「初始化中」态，不显示百分比', async ({ page }) => {
    await mockEbooks(page, {
      ready: false,
      book_count: 0,
      category_count: 0,
      age_days: null,
      stale: false,
      build: { running: true, done: 0, total: 0, failed: 0, started_at: new Date().toISOString(), finished_at: null, error: null },
    })
    await page.goto('/news/ebooks')

    await expect(page.locator('.index-card')).toContainText('正在初始化构建任务')
    await expect(page.locator('.index-card')).not.toContainText('（2%）')
  })

  test('构建失败：显示错误详情并提供重试入口', async ({ page }) => {
    await mockEbooks(page, {
      ready: false,
      book_count: 0,
      category_count: 0,
      age_days: null,
      stale: false,
      build: { running: false, done: 5, total: 1000, failed: 0, started_at: new Date().toISOString(), finished_at: new Date().toISOString(), error: 'ConnectionResetError: 远程主机强迫关闭了一个现有的连接。' },
    })
    await page.goto('/news/ebooks')

    // 进度动画停止，转错误态（不再显示进度条）
    await expect(page.locator('.index-progress')).toHaveCount(0)
    await expect(page.locator('.index-card')).toContainText('索引构建失败')
    await expect(page.locator('.index-card')).toContainText('远程主机强迫关闭了一个现有的连接')
    // 错误态内联重试入口 + 底部「构建索引」按钮均可用
    // el-link 无 href 时不产生 link role，按文本/类名定位
    await expect(page.locator('.index-card .el-link', { hasText: '重试' })).toBeVisible()
    await expect(page.getByRole('button', { name: '构建索引' })).toBeEnabled()
  })
})
