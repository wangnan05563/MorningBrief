import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02799：系统清理页的长任务改后台作业（FR-UX-702）。
 *
 * 原来的执行路径是「页面挂一条 300s 的 POST」，超时文案只是兜底。现在非预览执行
 * 拆成两段：POST 落任务立刻返回 task_id，页面轮询 GET /maintenance/tasks/{id} 看进度。
 * 这里守的是页面接线与状态口径：
 * - 预览仍是同步结果，只有真实执行才轮询；
 * - 执行中进度可见并写明「数据库可能被锁定」，完成后自动刷新存储状态；
 * - 重复提交被后端合并时，页面要说明「跟踪的是同一个任务」；
 * - 轮询失败 ≠ 任务失败：连续失败才提示，且不放弃；
 * - 离开页面后停止轮询（NFR-UX-03：这不是新增的常驻轮询）。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

const statusResponse = ok({
  db: { db_size_mb: 12.5, playlog_count: 10, workflow_count: 2, review_count: 3, blacklist_count: 0 },
  logs: { total_size_mb: 1.2, file_count: 3 },
  cache: { ttlcache_count: 1, pycache_count: 0, temp_files: 0 },
})

const cleanupResult = {
  target: 'old_playlogs',
  days: 1,
  dry_run: false,
  cleaned: ['播放日志 已删除 3 条（1 天前）'],
  errors: [],
  total_deleted: 3,
}

const taskView = (overrides = {}) => ok({
  task_id: 'task-t02799',
  category: 'database',
  target: 'all',
  state: 'running',
  merged: false,
  admin_name: 'admin',
  created_at: '2026-10-26T16:00:00',
  started_at: '2026-10-26T16:00:01',
  finished_at: null,
  elapsed_ms: 1200,
  result: null,
  error: null,
  ...overrides,
})

async function startExecution(page, label = '数据库清理') {
  const card = page.locator('.cleanup-card').filter({ hasText: label })
  await card.locator('.el-switch').click()
  await card.getByRole('button', { name: /立即执行清理/ }).click()
  await page.locator('.el-message-box').getByRole('button', { name: '确认执行' }).click()
  return card
}

test.describe('系统清理 · 后台任务进度', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    // 兜底：离开本页后其他页面接口一律空响应，避免打到真实后端
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('执行清理：提交后显示进度，完成后自动刷新状态并呈现结果', async ({ page }) => {
    const posts = []
    let statusCalls = 0
    await page.route(`${API}/maintenance/status*`, (route) => {
      statusCalls += 1
      return route.fulfill({ json: statusResponse })
    })
    await page.route(`${API}/maintenance/database`, async (route) => {
      posts.push(JSON.parse(route.request().postData() || '{}'))
      return route.fulfill({ json: taskView() })
    })
    let polls = 0
    await page.route(`${API}/maintenance/tasks/**`, async (route) => {
      polls += 1
      const done = polls >= 2
      return route.fulfill({
        json: taskView({
          state: done ? 'succeeded' : 'running',
          finished_at: done ? '2026-10-26T16:00:05' : null,
          elapsed_ms: done ? 4200 : 1200,
          result: done ? cleanupResult : null,
        }),
      })
    })

    await page.goto('/maintenance')
    const card = await startExecution(page)

    const progress = card.locator('[data-guide="maintenance-task-progress"]')
    await expect(progress).toContainText('执行中')
    await expect(progress).toContainText('执行期间数据库可能被锁定，其他操作会变慢')
    await expect(progress).toContainText('已完成', { timeout: 10_000 })
    await expect(card.getByText('播放日志 已删除 3 条（1 天前）')).toBeVisible()
    // 完成后才刷新存储状态（执行中刷到的是被锁住的旧值）
    expect(statusCalls).toBeGreaterThanOrEqual(2)
    expect(posts[0]).toEqual({ target: 'all', days: 30, dry_run: false })
    // 轮询在任务结束后停止
    const pollsAtFinish = polls
    await page.waitForTimeout(2600)
    expect(polls).toBe(pollsAtFinish)
  })

  test('重复提交被合并：页面说明跟踪的是同一个任务', async ({ page }) => {
    await page.route(`${API}/maintenance/status*`, (route) => route.fulfill({ json: statusResponse }))
    await page.route(`${API}/maintenance/database`, (route) =>
      route.fulfill({ json: taskView({ merged: true }) }),
    )
    await page.route(`${API}/maintenance/tasks/**`, (route) =>
      route.fulfill({ json: taskView({ merged: false }) }),
    )

    await page.goto('/maintenance')
    const card = await startExecution(page)

    const progress = card.locator('[data-guide="maintenance-task-progress"]')
    await expect(progress).toContainText('这里跟踪的是同一个任务，不会再跑第二份')
    await expect(progress).toContainText('执行中')
  })

  test('轮询失败不误报任务失败：连续 3 次才提示，之后仍能拿到结果', async ({ page }) => {
    await page.route(`${API}/maintenance/status*`, (route) => route.fulfill({ json: statusResponse }))
    await page.route(`${API}/maintenance/database`, (route) =>
      route.fulfill({ json: taskView() }),
    )
    let polls = 0
    await page.route(`${API}/maintenance/tasks/**`, async (route) => {
      polls += 1
      if (polls <= 3) return route.abort('failed')
      return route.fulfill({
        json: taskView({ state: 'succeeded', finished_at: '2026-10-26T16:00:09', result: cleanupResult }),
      })
    })

    await page.goto('/maintenance')
    const card = await startExecution(page)

    const progress = card.locator('[data-guide="maintenance-task-progress"]')
    await expect(progress).toContainText('已连续 3 次取不到任务进度', { timeout: 12_000 })
    await expect(progress).toContainText('后台任务不受影响，仍在重试')
    // 失败提示不是失败终态：任务仍会被跟踪到完成
    await expect(progress).toContainText('已完成', { timeout: 12_000 })
  })

  test('离开页面停止轮询：任务在后端继续，前端不再空转', async ({ page }) => {
    await page.route(`${API}/maintenance/status*`, (route) => route.fulfill({ json: statusResponse }))
    await page.route(`${API}/maintenance/database`, (route) =>
      route.fulfill({ json: taskView() }),
    )
    let polls = 0
    await page.route(`${API}/maintenance/tasks/**`, (route) => {
      polls += 1
      return route.fulfill({ json: taskView() })
    })

    await page.goto('/maintenance')
    await startExecution(page)
    await expect.poll(() => polls).toBeGreaterThanOrEqual(1)

    await page.goto('/help')
    await page.waitForTimeout(300)
    const pollsAfterLeave = polls
    await page.waitForTimeout(4500)
    expect(polls).toBe(pollsAfterLeave)
  })
})
