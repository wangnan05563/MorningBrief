import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02827：脱敏行在「数据库维护」里必须是可行动的
 *
 * T02519 把 notify_*_webhook 与 llm_preset_configs 纳入行级敏感后，这两类行显示 ***，
 * 原样存回会被后端拒绝，但页面既不说明 *** 从哪来，也不给专用配置入口——
 * 操作者只能猜菜单，现实路径往往是手工清库重填。
 *
 * 本用例守两件事：
 * 1. 列表页 *** 悬停能说明「不是脏数据」，并点名去哪儿改；
 * 2. 编辑弹窗里（含后端拒绝后的字段错误）都有可点跳转，不只是一句中文。
 */
const NAV_TIMEOUT = 30000

const SHOT_DIR = process.env.T02827_SHOT_DIR
async function shot(page, name) {
  if (!SHOT_DIR) return
  await page.screenshot({ path: `${SHOT_DIR}/${name}.png` })
}

const tablesResponse = {
  code: 0,
  message: 'success',
  data: [{ name: 'ai_config', label: 'AI 配置', rows: 2 }],
}

const schemaResponse = {
  code: 0,
  message: 'success',
  data: {
    columns: [
      { name: 'id', type: 'INTEGER', primary_key: true, sensitive: false, nullable: false },
      { name: 'config_key', type: 'VARCHAR(64)', primary_key: false, sensitive: false, nullable: false },
      { name: 'config_value', type: 'TEXT', primary_key: false, sensitive: true, nullable: true },
    ],
  },
}

const rowsResponse = {
  code: 0,
  message: 'success',
  data: {
    rows: [
      { id: 1, config_key: 'notify_admin_webhook', config_value: '***' },
      { id: 2, config_key: 'llm_preset_configs', config_value: '***' },
    ],
    total: 2,
  },
}

const MASK_FIELD_MESSAGE =
  '字段 config_value 传入的是脱敏占位值，保存会用 *** 覆盖真实凭据；' +
  '请留空保持原值，或通过对应的专用配置入口修改'

test.describe('数据库维护 · 脱敏值来源与专用入口（T02827）', () => {

  test.beforeEach(async ({ page }) => {
    await page.route('**/admin/api/v1/db-admin/tables/ai_config/schema', (route) =>
      route.fulfill({ json: schemaResponse }),
    )
    await page.route('**/admin/api/v1/db-admin/tables/ai_config/rows**', async (route) => {
      const method = route.request().method()
      if (method === 'GET') return route.fulfill({ json: rowsResponse })
      // 模拟后端 _mask_writeback_error 的字段级拒绝。
      // 后端 BizError 默认 http_status=200，信封里 code=400 —— 与真机一致，
      // 否则前端走的是 axios 错误分支，拿不到 data.errors，字段级错误就渲染不出来。
      return route.fulfill({
        json: {
          code: 400,
          message:
            '敏感字段 config_value 传入的是脱敏占位值，保存会用 *** 覆盖真实凭据；' +
            '请留空保持原值，或通过对应的专用配置入口修改',
          data: { errors: [{ field: 'config_value', message: MASK_FIELD_MESSAGE }] },
        },
      })
    })
    await page.route('**/admin/api/v1/db-admin/tables', (route) =>
      route.fulfill({ json: tablesResponse }),
    )
    await page.route('**/admin/api/v1/db-admin/audit-log*', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { items: [], total: 0 } } }),
    )
    // 顶栏的「检查更新」与本单无关：后端不在跑时 vite 代理回 500，
    // 会弹一句与取证无关的红色 toast，盖住页面。mock 成正常降级结果。
    await page.route('**/admin/api/v1/about/check-update', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            current: '0.0.0',
            latest: '0.0.0',
            has_update: false,
            release_url: '',
            checked_at: '2026-01-01T00:00:00',
            source: 'local',
            reason: 'repo_not_configured',
          },
        },
      }),
    )

    await setLoginState(page, 'admin')
    await page.goto('/db-admin')
    await page.locator('.table-item').filter({ hasText: 'AI 配置' }).click({ timeout: NAV_TIMEOUT })
    await expect(page.locator('.data-table .el-table__row')).toHaveCount(2, { timeout: NAV_TIMEOUT })
  })

  const row = (page, n) => page.locator('.data-table .el-table__row').nth(n)
  const editButton = (page, n) => row(page, n).getByRole('button', { name: '编辑' })
  const dialog = (page) => page.locator('.el-dialog').filter({ hasText: '编辑行' })

  test('列表页 *** 悬停说明「不是脏数据」并指向专用入口', async ({ page }) => {
    await row(page, 0).locator('.cell-sensitive').hover()
    // Element Plus 的 tooltip 是复用同一个 popper 容器，切换 hover 时旧节点仍在 DOM 里，
    // 故按可见文本取当前那一个，而不是取第一个 role=tooltip。
    const tip = page.getByRole('tooltip').filter({ hasText: '通知设置' })
    await expect(tip).toBeVisible()
    await expect(tip).toContainText('脱敏显示，不是脏数据')
    await expect(tip).toContainText('通知设置')
    // 等待 tooltip 的淡入动画结束再取证，否则截到半透明帧，底下的表头会透出来
    await page.waitForTimeout(500)
    await shot(page, '01-list-tooltip')

    await page.mouse.move(0, 0)
    await row(page, 1).locator('.cell-sensitive').hover()
    await expect(page.getByRole('tooltip').filter({ hasText: 'AI 服务配置' })).toContainText(
      'AI 服务配置',
    )
  })

  test('编辑通知类行：脱敏提示带「通知设置」可点跳转', async ({ page }) => {
    await editButton(page, 0).click()
    const dlg = dialog(page)
    await expect(dlg.getByText(/该值已脱敏显示，请前往/)).toBeVisible()
    const link = dlg.locator('.mask-hint__link', { hasText: '通知设置' })
    await expect(link).toBeVisible()
    await expect(link).toHaveAttribute('href', /\/notification$/)
    await shot(page, '02-edit-hint-notification')
  })

  test('编辑 AI 预设行：脱敏提示带「AI 服务配置」可点跳转', async ({ page }) => {
    await editButton(page, 1).click()
    const dlg = dialog(page)
    const link = dlg.locator('.mask-hint__link', { hasText: 'AI 服务配置' })
    await expect(link).toBeVisible()
    await expect(link).toHaveAttribute('href', /\/ai-config$/)
  })

  test('误存被后端拒绝时，字段错误里仍给出可点入口且不回传 ***', async ({ page }) => {
    await editButton(page, 1).click()
    const dlg = dialog(page)

    const putRequest = page.waitForRequest(
      (req) => req.method() === 'PATCH' && req.url().includes('/db-admin/tables/ai_config/rows/'),
    )
    const keyInput = dlg.locator('.el-form-item').filter({ hasText: 'config_key' }).locator('input')
    await keyInput.fill('llm_preset_configs_renamed')
    await dlg.getByRole('button', { name: '确认' }).click()

    const sent = await putRequest
    expect(sent.postDataJSON().values).not.toHaveProperty('config_value')

    const err = dlg.locator('.field-error')
    await expect(err).toBeVisible()
    await expect(err).toContainText('请留空保持原值')
    const link = err.locator('.mask-hint__link', { hasText: 'AI 服务配置' })
    await expect(link).toBeVisible()
    await expect(link).toHaveAttribute('href', /\/ai-config$/)
    await shot(page, '03-mask-rejection-with-link')
  })
})
