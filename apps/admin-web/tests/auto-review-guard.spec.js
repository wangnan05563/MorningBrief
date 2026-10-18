import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02492 / FR-UX-204 自动审批护栏 E2E
 *
 * 覆盖 PRD 三点：
 * 1. 三条校验改为「默认校验，显式关闭才跳过」——关闭项必须在界面上点名；
 * 2. 开启前必须勾选风险确认——未勾选时不发请求，服务端拒绝时也不报假成功；
 * 3. 每次自动通过的命中规则可读——历史列不再甩原始 JSON。
 */

const skippedOf = (payload) => {
  const skipped = []
  if (!payload.require_content_safe) skipped.push('content_safe')
  if (!payload.require_steps_first_success) skipped.push('steps_first_success')
  if (!payload.keyword_whitelist?.length) skipped.push('keyword_whitelist')
  return skipped
}

const initialConfig = {
  enabled: false,
  require_content_safe: true,
  require_steps_first_success: true,
  keyword_whitelist: [],
  risk_acknowledged: false,
  risk_acknowledged_by: null,
  risk_acknowledged_at: null,
  enforced_rules: ['content_safe', 'steps_first_success'],
  skipped_rules: ['keyword_whitelist'],
  updated_by: 'admin',
  updated_at: '2026-10-18T10:00:00',
}

const statsResponse = {
  code: 0, message: 'success',
  data: {
    start_date: '2026-10-11', end_date: '2026-10-19',
    total: 3, success_count: 2, failed_count: 1, success_rate: 0.6667,
    avg_time_saved_sec: 420, total_time_saved_sec: 840,
    fail_distribution: [{ reason: '内容安全检测命中违规', count: 1 }],
  },
}

const historyResponse = {
  code: 0, message: 'success',
  data: {
    total: 2,
    list: [
      {
        id: 2, review_id: 21, workflow_id: 'wf-2', success: true,
        trigger_reason: JSON.stringify({
          matched_rules: ['content_safe'],
          skipped_rules: ['steps_first_success', 'keyword_whitelist'],
        }),
        error_message: null, time_saved_sec: 420, created_at: '2026-10-18T09:00:00',
      },
      {
        id: 1, review_id: 20, workflow_id: 'wf-1', success: false,
        trigger_reason: JSON.stringify({
          skipped_rules: ['content_safe', 'steps_first_success', 'keyword_whitelist'],
          guard: 'no_enforced_rule',
        }),
        error_message: '无生效校验规则（三条校验均关闭），已拒绝自动通过并转人工审核',
        time_saved_sec: null, created_at: '2026-10-18T08:00:00',
      },
    ],
  },
}

async function mockAutoReview(page, { rejectGuard = false } = {}) {
  const calls = []
  await page.route('**/admin/api/v1/auto-review/**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()
    if (url.includes('/config') && method === 'PUT') {
      const body = JSON.parse(route.request().postData() || '{}')
      calls.push({ method, body })
      if (rejectGuard && body.enabled) {
        return route.fulfill({
          json: {
            code: 400,
            message: '自动审批护栏未通过：跳过的校验（内容安全检测、步骤一次成功）将不再检查',
            data: null,
          },
        })
      }
      const skipped = skippedOf(body)
      return route.fulfill({
        json: {
          code: 0, message: 'success',
          data: {
            ...initialConfig, ...body,
            risk_acknowledged_at: body.risk_acknowledged ? '2026-10-19T00:00:00' : null,
            enforced_rules: ['content_safe', 'steps_first_success', 'keyword_whitelist']
              .filter((r) => !skipped.includes(r)),
            skipped_rules: skipped,
          },
        },
      })
    }
    if (url.includes('/config')) {
      return route.fulfill({ json: { code: 0, message: 'success', data: initialConfig } })
    }
    if (url.includes('/stats')) return route.fulfill({ json: statsResponse })
    if (url.includes('/history')) return route.fulfill({ json: historyResponse })
    return route.continue()
  })
  return calls
}

async function gotoPage(page, opts) {
  await setLoginState(page, 'admin')
  const calls = await mockAutoReview(page, opts)
  await page.goto('/auto-review')
  await expect(page.locator('.config-form .el-switch').first()).toBeVisible({ timeout: 30000 })
  return calls
}

const switches = (page) => page.locator('.config-form .el-switch')
const ackCheckbox = (page) => page.locator('.el-checkbox', { hasText: '我已确认风险' })
const save = (page) => page.getByRole('button', { name: '保存配置' })
const puts = (calls) => calls.filter((c) => c.method === 'PUT')

test.describe('自动审批护栏', () => {
  test.use({ expect: { timeout: 30000 } })

  test('关闭校验即点名「本项不再检查」，并给出生效/跳过清单', async ({ page }) => {
    await gotoPage(page)
    // 关键词白名单为空：默认就应说明这项不检查
    await expect(page.getByText('未配置关键词：本项不检查')).toBeVisible()

    await switches(page).nth(0).click()
    await switches(page).nth(1).click()
    await expect(page.getByText('已关闭：本项不再检查，命中即放行')).toBeVisible()
    const summary = page.locator('.rule-summary')
    // 生效清单里只剩「步骤一次成功」；内容安全检测落到跳过清单（红色标签）
    await expect(summary.locator('.el-tag--success')).toHaveText(['步骤一次成功'])
    await expect(summary.locator('.el-tag--danger')).toHaveText(['内容安全检测', '关键词白名单'])
  })

  test('未勾选风险确认时开启被前端拦截，不发请求', async ({ page }) => {
    const calls = await gotoPage(page)
    await switches(page).nth(0).click()
    await expect(ackCheckbox(page)).toBeVisible()
    await save(page).click()
    await expect(page.getByText('请先勾选风险确认，再开启自动审批')).toBeVisible()
    expect(puts(calls)).toHaveLength(0)
  })

  test('勾选风险确认后保存，PUT 带上 risk_acknowledged 且确认框收起', async ({ page }) => {
    const calls = await gotoPage(page)
    await switches(page).nth(0).click()
    await ackCheckbox(page).click()
    await save(page).click()
    await expect(page.getByText('配置已保存')).toBeVisible()

    expect(puts(calls)).toHaveLength(1)
    expect(puts(calls)[0].body).toMatchObject({
      enabled: true, require_content_safe: true, risk_acknowledged: true,
    })
    // 服务端已记录确认：日常保存不该反复要求打勾
    await expect(ackCheckbox(page)).toHaveCount(0)
  })

  test('三条校验全关时前端拦截，不发起开启请求', async ({ page }) => {
    const calls = await gotoPage(page)
    await switches(page).nth(1).click()
    await switches(page).nth(2).click()
    await switches(page).nth(0).click()
    await ackCheckbox(page).click()
    await save(page).click()
    await expect(page.getByText('三条校验全部关闭时不能开启自动审批')).toBeVisible()
    expect(puts(calls)).toHaveLength(0)
  })

  test('服务端拒绝时如实提示，不报假成功', async ({ page }) => {
    const calls = await gotoPage(page, { rejectGuard: true })
    await switches(page).nth(1).click()
    await switches(page).nth(2).click()
    await switches(page).nth(0).click()
    // 补一个关键词，让「只剩一条校验」通过前端预检，把拒绝交给服务端护栏
    await page.locator('.keyword-input-wrap input').fill('时政')
    await page.getByRole('button', { name: '添加' }).click()
    await ackCheckbox(page).click()
    await save(page).click()
    await expect(page.getByText('保存失败：自动审批护栏未通过')).toBeVisible()
    await expect(page.getByText('配置已保存')).toHaveCount(0)
    expect(puts(calls)).toHaveLength(1)
  })

  test('历史列把命中/跳过规则渲染成中文', async ({ page }) => {
    await gotoPage(page)
    const rows = page.locator('.el-table__row')
    await expect(rows.nth(0)).toContainText('命中：内容安全检测 / 跳过：步骤一次成功、关键词白名单')
    await expect(rows.nth(1)).toContainText('无生效校验规则')
  })
})
