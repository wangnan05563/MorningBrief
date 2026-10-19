import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 枚举文案统一（T02504 / FR-UX-405）
 *
 * 这一组断言盯的都是修复前「肉眼看得见、代码里查不出」的三种错：
 * 1. 后端真实状态值在前端映射里没有 → 页面上直接漏出英文原值（移动端把 `finished`
 *    当成成功态抄了一份，于是 `success` 的任务在手机上显示 "success"）；
 * 2. 步骤状态套用了「工作流状态」的映射 → `pending` / `retrying` 漏英文；
 * 3. 同一个值在不同页面两套说法（成功 / 已完成、运行中 / 执行中、排队中 / 等待中）。
 * 构建期门禁（scripts/validate-nav.mjs）能拦住来源，这里拦住用户可见的结果。
 */

const NAV_TIMEOUT = 30000

const statsResponse = {
  code: 0,
  message: 'success',
  data: { queued: 1, running: 0, success: 7, failed: 2, cancelled: 1 },
}

const tasksResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 2,
    items: [
      {
        id: 'wf-20261018-0001',
        episode_date: '2026-10-18',
        source: 'cron',
        status: 'success',
        channel_id: 1,
        channel_name: '科技频道',
        priority: 5,
        started_at: '2026-10-18T05:00:00',
        finished_at: '2026-10-18T05:12:00',
        error: null,
        steps: [
          { name: 'crawl', status: 'success', started_at: '2026-10-18T05:00:00', finished_at: '2026-10-18T05:01:00' },
          { name: 'quality_check', status: 'retrying', started_at: '2026-10-18T05:02:00', finished_at: null },
          { name: 'tts', status: 'pending', started_at: null, finished_at: null },
        ],
      },
      {
        id: 'wf-20261018-0002',
        episode_date: '2026-10-18',
        source: 'manual',
        status: 'cancelled',
        channel_id: 2,
        channel_name: '财经频道',
        priority: 3,
        started_at: null,
        finished_at: null,
        error: null,
        steps: [],
      },
    ],
  },
}

async function mockQueue(page) {
  await page.route('**/admin/api/v1/events/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }),
  )
  await page.route('**/admin/api/v1/queue/stats', (route) => route.fulfill({ json: statsResponse }))
  await page.route('**/admin/api/v1/queue/config', (route) =>
    route.fulfill({ json: { code: 0, message: 'success', data: { mode: 'serial', max_concurrency: 1 } } }),
  )
  await page.route('**/admin/api/v1/queue/tasks*', (route) => route.fulfill({ json: tasksResponse }))
  await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: { code: 0, message: 'success', data: [] } }))
}

test.describe('枚举文案统一', () => {
  test.use({ expect: { timeout: NAV_TIMEOUT } })

  test('移动端队列：后端状态值全部有中文徽章，统计卡不再有恒空的格子', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockQueue(page)
    await page.goto('/m/manage/queue')
    await expect(page.locator('.m-q__item').first()).toBeVisible({ timeout: NAV_TIMEOUT })

    // `success` 任务显示「成功」（修复前：映射里只有 finished，这里漏出英文原值）
    await expect(page.locator('.m-badge').filter({ hasText: '成功' })).toHaveCount(1)
    await expect(page.locator('.m-badge').filter({ hasText: '已取消' })).toHaveCount(1)
    await expect(page.locator('.m-badge').filter({ hasText: /success|cancelled|queued/ })).toHaveCount(0)

    // 统计卡读 stats.success（修复前读的是后端根本不返回的 stats.finished → 永远显示 -）
    await expect(page.locator('.m-q__stat').filter({ hasText: '成功' }).locator('.m-q__stat-v')).toHaveText('7')
    await expect(page.locator('.m-q__stat').filter({ hasText: '排队中' }).locator('.m-q__stat-v')).toHaveText('1')
  })

  test('PC 队列详情：步骤状态与步骤名取自字典（修复前 pending/retrying 漏英文）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockQueue(page)
    await page.goto('/queue')
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: NAV_TIMEOUT })

    // 列表状态标签与移动端同一口径：都是「成功」，不再是「已完成」
    await expect(page.locator('.el-table__row').first().locator('.el-tag').filter({ hasText: '成功' })).toBeVisible()

    await page.locator('.el-table__row').first().getByRole('button', { name: '详情' }).click()
    const drawer = page.locator('.el-drawer')
    await expect(drawer.getByText('步骤时间线')).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(drawer.locator('.step-name')).toHaveText(['爬虫采集', '质量审核', '语音合成'])
    await expect(drawer.locator('.step-status')).toHaveText(['成功', '重试中', '等待中'])
    await expect(drawer.getByText(/retrying|pending|quality_check|tts/)).toHaveCount(0)
  })

  test('频道类型：后端 type_label 优先展示（修复前填了不显示）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/channels*', async (route) => {
      if (route.request().method() !== 'GET') return route.fallback()
      await route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: [
            { id: 1, name: '课程频道A', channel_type: 'course', type_label: '热门课程', is_active: 1, created_at: '2026-10-01T10:00:00' },
            { id: 2, name: '资讯频道B', channel_type: 'news', type_label: null, is_active: 1, created_at: '2026-10-02T10:00:00' },
            { id: 3, name: '自定义频道C', channel_type: 'feature', type_label: null, is_active: 1, created_at: '2026-10-03T10:00:00' },
          ],
        },
      })
    })
    await page.goto('/channels')
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: NAV_TIMEOUT })

    // type_label 有值就显示运营自己填的那个词，不再被枚举标签覆盖
    await expect(page.locator('.el-table__row').filter({ hasText: '课程频道A' })).toContainText('热门课程')
    // type_label 为空才回落到字典标签
    await expect(page.locator('.el-table__row').filter({ hasText: '资讯频道B' })).toContainText('资讯')
    // 字典里没有的类型（后端 channel_type 不是模型枚举，允许自由值）原样显示，不谎报成「资讯」
    await expect(page.locator('.el-table__row').filter({ hasText: '自定义频道C' })).toContainText('feature')
  })
})
