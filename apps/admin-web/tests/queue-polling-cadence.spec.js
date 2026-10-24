import { test, expect } from '@playwright/test'
import {
  setLoginState,
  queueStatsResponse,
  queueConfigResponse,
  queueTasksResponse,
  channelsListResponse,
} from './helpers/mock'

/**
 * 队列页轮询节奏（T02837）
 *
 * 修复前：onMounted 里 loadTasks() 未 await 就 scheduleNextPoll()，
 * 排定时 tasks 还是空数组 → hasActiveTasks() 恒为假 → 首个间隔恒 30s，
 * 且数据到达后不会重算已排定的 timeout。
 *
 * 本用例不复用 nfr03 的「8s 窗口总请求数」基线，而是直接盯 /queue/tasks 的到达时刻：
 * - 有 queued/running：首轮加载后 ≤5s 档触发第二次；
 * - 无活跃任务：8s 窗口内不得有第二次（维持 30s 省流量）。
 */

const idleTasks = {
  code: 0,
  message: 'success',
  data: {
    total: 1,
    items: [queueTasksResponse.data.items[1]],
  },
}

async function mockPage(page, tasksJson) {
  await page.route('**/admin/api/v1/events/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }),
  )
  await page.route('**/admin/api/v1/queue/stats', (route) =>
    route.fulfill({ json: queueStatsResponse }),
  )
  await page.route('**/admin/api/v1/queue/config', (route) =>
    route.fulfill({ json: queueConfigResponse }),
  )
  await page.route('**/admin/api/v1/queue/tasks*', (route) =>
    route.fulfill({ json: tasksJson }),
  )
  await page.route('**/admin/api/v1/channels*', (route) =>
    route.fulfill({ json: channelsListResponse }),
  )
  await setLoginState(page, 'admin')
}

/** 记录任务列表请求的到达时刻；操作类 /queue/tasks/{id}/... 不计入 */
function watchTaskList(page) {
  const stamps = []
  page.on('request', (req) => {
    const url = new URL(req.url())
    if (url.pathname.endsWith('/queue/tasks')) stamps.push(Date.now())
  })
  return stamps
}

test.describe('队列页轮询节奏（T02837）', () => {

  test('有活跃任务：首轮加载后按 5s 档触发下一次轮询', async ({ page }) => {
    await mockPage(page, queueTasksResponse)
    const stamps = watchTaskList(page)

    await page.goto('/queue')
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: 30000 })

    await expect
      .poll(() => stamps.length, { timeout: 9000, message: '活跃队列 9s 内没有出现第二次轮询' })
      .toBeGreaterThanOrEqual(2)

    const gap = stamps[1] - stamps[0]
    expect(gap, `首轮与第二次轮询间隔 ${gap}ms，应落在 5s 档`).toBeGreaterThanOrEqual(3500)
    expect(gap, `首轮与第二次轮询间隔 ${gap}ms，不应退到 30s 档`).toBeLessThanOrEqual(8000)
  })

  test('无活跃任务：8s 窗口内不补发（维持 30s 档）', async ({ page }) => {
    await mockPage(page, idleTasks)
    const stamps = watchTaskList(page)

    await page.goto('/queue')
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: 30000 })

    await page.waitForTimeout(8000)
    expect(stamps.length, '无 queued/running 时不应按 5s 轮询').toBe(1)
  })
})
