import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02599：系统清理页的「指定工作流全链清理」入口。
 *
 * 后端 service 的级联口径由 backend/tests/test_maintenance_cleanup_workflows_cascade.py 锁；
 * 这里守的是页面接线：选目标 → 填 ID → 预览/真删分别打到独立端点，
 * 且请求体只带 workflow_id / dry_run（全链清理没有 days 语义）。
 */

const API = '**/admin/api/v1'

const ok = (data) => ({ code: 0, message: 'success', data })

const statusResponse = ok({
  db: { db_size_mb: 12.5, playlog_count: 10, workflow_count: 2, review_count: 3, blacklist_count: 0 },
  logs: { total_size_mb: 1.2, file_count: 3 },
  cache: { ttlcache_count: 1, pycache_count: 0, temp_files: 0 },
})

const chainResult = (dryRun) => ok({
  target: 'workflow_chain',
  workflow_id: 'wf-123',
  dry_run: dryRun,
  cleaned: ['工作流步骤 将删除 1 条', '稿件 将删除 1 条', '节目 将删除 2 条', '工作流 将删除 1 条'],
  errors: [],
  counts: { workflow_steps: 1, scripts: 1, episodes: 2, workflows: 1 },
  total_deleted: 5,
})

async function pickWorkflowChain(page) {
  const dbCard = page.locator('.cleanup-card').filter({ hasText: '数据库清理' })
  await dbCard.locator('.el-select').click()
  await page.locator('.el-select-dropdown__item').filter({ hasText: '指定工作流全链清理' }).click()
  return dbCard
}

test.describe('系统清理 · 指定工作流全链清理', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/maintenance/status*`, (route) => route.fulfill({ json: statusResponse }))
  })

  test('预览走独立端点：请求体只有 workflow_id / dry_run，结果逐表列出', async ({ page }) => {
    const calls = []
    await page.route(`${API}/maintenance/workflow-chain`, async (route) => {
      calls.push(JSON.parse(route.request().postData() || '{}'))
      return route.fulfill({ json: chainResult(true) })
    })

    await page.goto('/maintenance')
    const dbCard = await pickWorkflowChain(page)
    await page.getByPlaceholder('粘贴工作流 ID').fill('wf-123')
    await dbCard.getByRole('button', { name: '预览清理' }).click()

    await expect(dbCard.getByText('节目 将删除 2 条')).toBeVisible()
    expect(calls).toHaveLength(1)
    // days 对全链清理没有语义：带上会被后端 extra=forbid 拒掉
    expect(calls[0]).toEqual({ workflow_id: 'wf-123', dry_run: true })
  })

  test('未填工作流 ID：页面本地拦下，不发请求', async ({ page }) => {
    let calls = 0
    await page.route(`${API}/maintenance/workflow-chain`, (route) => {
      calls += 1
      return route.fulfill({ json: chainResult(true) })
    })

    await page.goto('/maintenance')
    const dbCard = await pickWorkflowChain(page)
    await dbCard.getByRole('button', { name: '预览清理' }).click()

    await expect(
      page.locator('.el-message').filter({ hasText: '请填写要清理的工作流 ID' }),
    ).toHaveCount(1)
    expect(calls).toBe(0)
  })

  test('真删前确认写明工作流 ID 与「其他工作流不受影响」', async ({ page }) => {
    const calls = []
    await page.route(`${API}/maintenance/workflow-chain`, async (route) => {
      calls.push(JSON.parse(route.request().postData() || '{}'))
      // T02799：非预览改为后台任务，POST 只返回任务视图
      return route.fulfill({
        json: ok({
          task_id: 'task-wf-456',
          category: 'workflow_chain',
          target: 'wf-456',
          state: 'running',
          merged: false,
          elapsed_ms: 300,
          result: null,
          error: null,
        }),
      })
    })
    await page.route(`${API}/maintenance/tasks/**`, (route) => route.fulfill({
      json: ok({
        task_id: 'task-wf-456',
        category: 'workflow_chain',
        target: 'wf-456',
        state: 'succeeded',
        merged: false,
        elapsed_ms: 800,
        result: chainResult(false).data,
        error: null,
      }),
    }))

    await page.goto('/maintenance')
    const dbCard = await pickWorkflowChain(page)
    await page.getByPlaceholder('粘贴工作流 ID').fill('wf-456')
    await dbCard.locator('.el-switch').click()
    await dbCard.getByRole('button', { name: /立即执行清理/ }).click()

    const dialog = page.locator('.el-message-box')
    await expect(dialog).toContainText('工作流 wf-456')
    await expect(dialog).toContainText('其他工作流不受影响')
    await dialog.getByRole('button', { name: '确认执行' }).click()

    await expect.poll(() => calls.length).toBe(1)
    expect(calls[0]).toEqual({ workflow_id: 'wf-456', dry_run: false })
  })
})
