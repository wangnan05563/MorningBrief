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
    // T02708：成功率是 0~1 比值，×100 与小数位只写在 meta 里
    meta: {
      success_rate: {
        label: '成功率', unit: 'ratio',
        display: { unit: '%', factor: 100, precision: 2 },
      },
    },
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

async function mockAutoReview(page, { rejectGuard = false, config = initialConfig } = {}) {
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
            ...config, ...body,
            risk_acknowledged_at: body.risk_acknowledged ? '2026-10-19T00:00:00' : null,
            enforced_rules: ['content_safe', 'steps_first_success', 'keyword_whitelist']
              .filter((r) => !skipped.includes(r)),
            skipped_rules: skipped,
          },
        },
      })
    }
    if (url.includes('/config')) {
      return route.fulfill({ json: { code: 0, message: 'success', data: config } })
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

/**
 * T02603：负向断言「横幅不存在」必须与「页面还在配置页」同时成立。
 * 本机 dev 代理指向 8000 端口，若有别的后端实例在跑会回 401，拦截器随后清登录态
 * 直接跳登录页——那时页面上什么都没有，toHaveCount(0) 会假绿。取一次原子快照，
 * 页面已被踢走就直接判红。
 */
const bannerSnapshot = (page) => page.evaluate(() => ({
  path: window.location.pathname,
  onPage: !!document.querySelector('[data-guide="auto-review-page"]'),
  banners: document.querySelectorAll('[data-guide="auto-review-legacy-ack"]').length,
}))

test.describe('自动审批护栏', () => {

  test('成功率按后端 meta 换算：页面不再自己乘 100（T02708）', async ({ page }) => {
    await gotoPage(page)
    // meta 给 precision=2、factor=100：0.6667 → 66.67%。
    // 页面若仍保留 formatPercent（×100 后固定 1 位），这里只会显示 66.7%。
    await expect(
      page.locator('.stat-detail').filter({ hasText: '成功率 66.67%' }),
    ).toBeVisible()
  })

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

  test('T02596 重试失败自动审批：确认框写明会直接发布，取消不发请求', async ({ page }) => {
    await gotoPage(page)
    const retries = []
    await page.route('**/admin/api/v1/auto-review/retry/**', (route) => {
      retries.push(route.request().url())
      return route.fulfill({ json: { code: 0, message: 'success', data: { auto_approved: true } } })
    })

    await page.getByRole('button', { name: '重试' }).click()
    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible()
    await expect(box.getByText('重试自动审批：工作流 wf-1（记录 #1）')).toBeVisible()
    await expect(box.getByText('影响范围：自动审批 1 条（仅审核记录仍为 pending 时执行）')).toBeVisible()
    await expect(box.getByText(/重试成功会直接通过审核并自动发布对应节目/)).toBeVisible()
    await expect(box.getByText(/自动发布后无法在本页撤回/)).toBeVisible()

    await box.getByRole('button', { name: '取消' }).click()
    await expect(box).toBeHidden()
    expect(retries).toHaveLength(0)

    await page.getByRole('button', { name: '重试' }).click()
    await page.locator('.el-message-box').getByRole('button', { name: '确认重试' }).click()
    await expect.poll(() => retries.length).toBe(1)
    expect(retries[0]).toMatch(/\/auto-review\/retry\/1$/)
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
    // T02629 起业务错误由拦截器弹后端原文，页面 notifyErrorOnce 不再补第二条
    // （message-dedupe「页面 catch 与拦截器同一件事只留一条说明」锁的就是这个口径）；
    // 这里守住「如实提示且只有一条」，仍然禁止报假成功。
    const rejected = page.locator('.el-message').filter({ hasText: '自动审批护栏未通过' })
    await expect(rejected).toHaveCount(1)
    await expect(rejected.first()).toContainText('跳过的校验（内容安全检测、步骤一次成功）将不再检查')
    await expect(page.getByText('配置已保存')).toHaveCount(0)
    expect(puts(calls)).toHaveLength(1)
  })

  test('历史列把命中/跳过规则渲染成中文', async ({ page }) => {
    await gotoPage(page)
    const rows = page.locator('.el-table__row')
    await expect(rows.nth(0)).toContainText('命中：内容安全检测 / 跳过：步骤一次成功、关键词白名单')
    await expect(rows.nth(1)).toContainText('无生效校验规则')
  })

  // T02603 裁决3：存量「已开启但从未风险确认」只点名、不停用、不阻断保存
  test('存量未确认配置在页顶点名，勾选确认保存后提示消失', async ({ page }) => {
    const legacy = { ...initialConfig, enabled: true, risk_acknowledged: false }
    const calls = await gotoPage(page, { config: legacy })
    const banner = page.locator('[data-guide="auto-review-legacy-ack"]')
    await expect(banner).toBeVisible()
    await expect(banner).toContainText('从未做过风险确认')
    await expect(banner).toContainText('自动审批仍按现有校验自动通过并发布')
    // 只提示不阻断：保存可用，且勾选确认后即可补上
    await expect(save(page)).toBeEnabled()
    await ackCheckbox(page).click()
    await save(page).click()
    await expect(page.getByText('配置已保存')).toBeVisible()
    expect(puts(calls)).toHaveLength(1)
    expect(puts(calls)[0].body.risk_acknowledged).toBe(true)
    const after = await bannerSnapshot(page)
    expect(after.onPage).toBe(true)
    expect(after.banners).toBe(0)
  })

  test('已确认的开启配置不点名', async ({ page }) => {
    const acked = {
      ...initialConfig, enabled: true, risk_acknowledged: true,
      risk_acknowledged_by: 'admin', risk_acknowledged_at: '2026-10-18T10:00:00',
    }
    await gotoPage(page, { config: acked })
    // 先等配置真正落到页面（「上次更新」标签只在 config 到手后渲染），再取横幅快照
    await expect(page.locator('.config-section .section-header .el-tag')).toContainText('上次更新')
    const snap = await bannerSnapshot(page)
    expect(snap.path).toContain('/auto-review')
    expect(snap).toMatchObject({ onPage: true, banners: 0 })
  })

  test('关闭状态的配置不点名（升级后不该满屏黄条）', async ({ page }) => {
    await gotoPage(page)
    // 同「已确认」用例：配置到手后才有「上次更新」标签，避免在配置未到达前取快照
    await expect(page.locator('.config-section .section-header .el-tag')).toContainText('上次更新')
    const snap = await bannerSnapshot(page)
    expect(snap.path).toContain('/auto-review')
    expect(snap).toMatchObject({ onPage: true, banners: 0 })
  })
})
