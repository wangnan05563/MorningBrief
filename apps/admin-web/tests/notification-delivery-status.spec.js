import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 通知发送日志：投递状态文案与配色（T02702 / FR-UX-405）
 *
 * 此前筛选下拉、tag 配色、tag 文案在同一文件里各写一份，改成
 * `NOTIFICATION_DELIVERY_STATUS` 字典后本用例锁住「现网文案不变」：
 * 四个状态的中文、颜色、筛选顺序都必须与改动前逐字一致；
 * 后端出现字典外的旧值时仍按原样显示英文，不吞成空白。
 */

const ok = (data) => ({ json: { code: 0, message: 'ok', data } })

const LOGS = [
  { id: 1, event_type: 'test', title: '成功记录', status: 'success' },
  { id: 2, event_type: 'test', title: '失败记录', status: 'failed' },
  { id: 3, event_type: 'test', title: '封顶记录', status: 'failed_capped' },
  { id: 4, event_type: 'test', title: '静默记录', status: 'suppressed' },
  { id: 5, event_type: 'test', title: '旧值记录', status: 'legacy_status' },
].map((row) => ({
  ...row,
  error: '',
  payload: '',
  workflow_id: '',
  created_at: '2026-10-25T09:00:00',
}))

const EXPECTED_TAGS = [
  ['成功记录', '成功', 'el-tag--success'],
  ['失败记录', '失败', 'el-tag--danger'],
  ['封顶记录', '失败达上限', 'el-tag--warning'],
  ['静默记录', '已抑制', 'el-tag--info'],
]

test.beforeEach(async ({ page }) => {
  await setLoginState(page, 'admin')

  await page.route('**/admin/api/v1/notification/config', (route) =>
    route.fulfill(
      ok({
        global_enabled: true,
        failed_enabled: true,
        review_enabled: true,
        published_enabled: false,
        dingtalk_webhook: '',
        wecom_webhook: '',
        email_smtp_port: 587,
      }),
    ),
  )
  await page.route('**/admin/api/v1/notification/templates*', (route) =>
    route.fulfill(ok([])),
  )
  await page.route('**/admin/api/v1/notification/logs*', (route) =>
    route.fulfill(ok({ items: LOGS, total: LOGS.length })),
  )
})

test('筛选下拉与状态标签沿用原文案和配色', async ({ page }) => {
  await page.goto('/notification')
  await page.getByRole('tab', { name: '发送日志' }).click()

  for (const [title, label, cls] of EXPECTED_TAGS) {
    const row = page.locator('.el-table__row', { hasText: title })
    await expect(row).toBeVisible({ timeout: 30000 })
    const statusTag = row.locator('.el-tag').nth(1)
    await expect(statusTag).toHaveText(label)
    await expect(statusTag).toHaveClass(new RegExp(cls))
  }

  // 字典外的历史值：不认识的英文原样露出（与改动前的 map[status] || status 一致）
  const legacy = page.locator('.el-table__row', { hasText: '旧值记录' })
  await expect(legacy.locator('.el-tag').nth(1)).toHaveText('legacy_status')

  // 状态筛选下拉：选项文案与顺序（与后端枚举声明顺序一致）
  await page.locator('.filter-bar .el-select').nth(1).click()
  await expect(page.locator('.el-select-dropdown__item:visible')).toHaveText([
    '成功',
    '失败',
    '失败达上限',
    '已抑制',
  ])
})
