import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02598：系统清理页的「无主素材治理」入口。
 *
 * 无主素材＝channel_id 还写着某个已删除频道的素材行（旧版删频道不解绑的存量，
 * 生产库实测 8 条）。它们在任何按频道筛选的列表里都看不见，只能靠这个入口治理。
 * 这里守的是页面接线与口径：
 * - 两个目标分别发 orphan_materials_detach / orphan_materials_delete；
 * - 都不带 days（没有天数语义，后端 target 才是唯一条件）；
 * - 天数输入框隐藏；
 * - 执行前的确认框把「改什么、能不能恢复」说清楚，且解绑与删除的措辞不同。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

const statusResponse = ok({
  db: { db_size_mb: 12.5, playlog_count: 10, workflow_count: 2, review_count: 3, blacklist_count: 0 },
  logs: { total_size_mb: 1.2, file_count: 3 },
  cache: { ttlcache_count: 1, pycache_count: 0, temp_files: 0 },
})

const orphanResult = (target, dryRun) => ok({
  target,
  days: 0,
  dry_run: dryRun,
  cleaned: [
    `无主素材${dryRun ? '解绑：将影响' : '解绑：已处理'} 8 条（channel_id 置空，素材回到全局素材池）；样例 ID 2134, 2135`,
  ],
  errors: [],
  total_deleted: dryRun ? 0 : 8,
})

// T02799：非预览执行改为后台任务——POST 只返回任务视图，结果从任务状态里取
const taskSubmitted = (target) => ok({
  task_id: `task-${target}`,
  category: 'database',
  target,
  state: 'running',
  merged: false,
  elapsed_ms: 900,
  result: null,
  error: null,
})

const taskSucceeded = (target, cleaned) => ok({
  task_id: `task-${target}`,
  category: 'database',
  target,
  state: 'succeeded',
  merged: false,
  elapsed_ms: 1200,
  result: { target, days: 0, dry_run: false, cleaned, errors: [], total_deleted: 8 },
  error: null,
})

async function pickDbTarget(page, label) {
  const dbCard = page.locator('.cleanup-card').filter({ hasText: '数据库清理' })
  await dbCard.locator('.el-select').click()
  await page.locator('.el-select-dropdown__item').filter({ hasText: label }).first().click()
  return dbCard
}

test.describe('系统清理 · 无主素材治理', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/maintenance/status*`, (route) => route.fulfill({ json: statusResponse }))
  })

  test('解绑预览：请求体只有 target / dry_run，天数输入隐藏', async ({ page }) => {
    const calls = []
    await page.route(`${API}/maintenance/database`, async (route) => {
      calls.push(JSON.parse(route.request().postData() || '{}'))
      return route.fulfill({ json: orphanResult('orphan_materials_detach', true) })
    })

    await page.goto('/maintenance')
    const dbCard = await pickDbTarget(page, '无主素材解绑')

    await expect(dbCard.getByText('指 channel_id 仍写着某个频道')).toBeVisible()
    // 无主素材只按「channel_id 悬空」这一个条件筛，没有天数输入
    await expect(dbCard.getByText('保留天数')).toHaveCount(0)
    await dbCard.getByRole('button', { name: '预览清理' }).click()

    await expect(dbCard.getByText('无主素材解绑：将影响 8 条')).toBeVisible()
    expect(calls).toHaveLength(1)
    expect(calls[0]).toEqual({ target: 'orphan_materials_detach', dry_run: true })
  })

  test('解绑执行：确认框说的是解绑后果，不是「删除不可恢复」', async ({ page }) => {
    const calls = []
    await page.route(`${API}/maintenance/database`, async (route) => {
      const body = JSON.parse(route.request().postData() || '{}')
      calls.push(body)
      if (body.dry_run) {
        return route.fulfill({ json: orphanResult('orphan_materials_detach', true) })
      }
      return route.fulfill({ json: taskSubmitted('orphan_materials_detach') })
    })
    await page.route(`${API}/maintenance/tasks/**`, (route) => route.fulfill({
      json: taskSucceeded('orphan_materials_detach', [
        '无主素材解绑：已处理 8 条（channel_id 置空，素材回到全局池）；样例 ID 2134, 2135',
      ]),
    }))

    await page.goto('/maintenance')
    const dbCard = await pickDbTarget(page, '无主素材解绑')
    // 先做一次预览，确认框才有一条「上次预览命中」可引用
    await dbCard.getByRole('button', { name: '预览清理' }).click()
    await dbCard.locator('.el-switch').click()
    await dbCard.getByRole('button', { name: /立即执行清理/ }).click()

    const box = page.locator('.el-message-box')
    await expect(box.getByText('无主素材解绑（orphan_materials_detach）')).toBeVisible()
    await expect(
      box.getByText('归属置空，正文保留并回到全局素材池；正常素材不受影响'),
    ).toBeVisible()
    await expect(box.getByText('解绑后认不回原频道')).toBeVisible()
    await expect(box.getByText('上次预览命中 1 项')).toBeVisible()
    await box.getByRole('button', { name: '确认执行' }).click()

    await expect
      .poll(() => calls.length)
      .toBe(2)
    expect(calls[1]).toEqual({ target: 'orphan_materials_detach', dry_run: false })
  })

  test('删除口径：确认框写明连正文一起删，且没有误选解绑的文案', async ({ page }) => {
    const calls = []
    await page.route(`${API}/maintenance/database`, async (route) => {
      calls.push(JSON.parse(route.request().postData() || '{}'))
      return route.fulfill({ json: taskSubmitted('orphan_materials_delete') })
    })
    await page.route(`${API}/maintenance/tasks/**`, (route) => route.fulfill({
      json: taskSucceeded('orphan_materials_delete', [
        '无主素材删除：已处理 8 条（素材行连同正文一起删除）；样例 ID 2134, 2135',
      ]),
    }))

    await page.goto('/maintenance')
    const dbCard = await pickDbTarget(page, '无主素材删除')
    await dbCard.locator('.el-switch').click()
    await dbCard.getByRole('button', { name: /立即执行清理/ }).click()

    const box = page.locator('.el-message-box')
    await expect(box.getByText('连同正文一起删除')).toBeVisible()
    await expect(box.getByText('尚未做过 dry-run 预览')).toBeVisible()
    await box.getByRole('button', { name: '确认执行' }).click()

    await expect
      .poll(() => calls.length)
      .toBe(1)
    expect(calls[0]).toEqual({ target: 'orphan_materials_delete', dry_run: false })
  })
})
