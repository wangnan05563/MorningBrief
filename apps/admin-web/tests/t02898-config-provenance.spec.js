import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * T02898：AI / 通知配置页也要承认「请求成功 ≠ 屏上的值是库里存的」。
 *
 * T02527 已在云端存储页落了 INT-UX-04 三态；本单把同一契约接到另外两个配置面。
 * 三态分别是：
 * - 库里有一部分：显示最后一次入库修改时间 + 点名 .env 回落字段；
 * - 请求成功但读表失败：横幅写原因、保存禁用（通知页的测试发送也会先保存，同样禁用）；
 * - 库里无记录：写「库里暂无记录」并点名回落字段（AI 按 llm./tts./image. 路径）。
 *
 * 截图落在 _validate/news2/tmp_t02898_shots（全部为 mock 数据，不含真实凭据）。
 */

const NAV_TIMEOUT = 60000
const SHOTS = fileURLToPath(new URL('../../../_validate/news2/tmp_t02898_shots', import.meta.url))

const AI_BASE = {
  llm: { api_key: '****wxyz', base_url: 'https://llm.example/v1', model: 'qwen-max', preset_configs: {} },
  tts: { provider: 'aliyun', api_key: '****abcd' },
  image: { api_key: '', base_url: '', model: '' },
}

const NOTIFY_BASE = {
  global_enabled: true,
  failed_enabled: true,
  review_enabled: true,
  published_enabled: false,
  dingtalk_webhook: '',
  dingtalk_secret: '',
  wecom_webhook: '',
  email_smtp_host: '',
  email_smtp_port: 587,
  email_smtp_user: '',
  email_smtp_password: '',
  email_to: '',
  admin_base_url: '',
  auto_detected_base_url: 'http://localhost:8000',
}

const ok = (data) => ({ status: 200, json: { code: 0, message: 'ok', data } })

async function mockAiConfig(page, data) {
  // 兜底：页面里还有音色同步/用量等旁路请求，别让它们经 Vite 代理撞上本机 8000
  // 的另一个后端，把所有调用都拦清楚，截图才只有本单要证明的东西
  await page.route('**/admin/api/v1/ai/**', (route) => route.fulfill(ok({})))
  await page.route('**/admin/api/v1/ai/config', (route) =>
    route.fulfill(ok({ ...AI_BASE, ...data })),
  )
  await page.route('**/admin/api/v1/ai/presets', (route) => route.fulfill(ok([])))
  await page.route('**/admin/api/v1/ai/audio-profile', (route) => route.fulfill(ok({})))
  await page.route('**/admin/api/v1/ai/voices*', (route) => route.fulfill(ok([])))
}

async function waitSplashGone(page) {
  // 启动 splash 在无后端时会驻留约 2s，遮住页面却不影响可见性断言；
  // 不等待的话截图只剩「正在连接服务…」，证据等于没留
  await page
    .locator('#app-splash')
    .waitFor({ state: 'detached', timeout: 15000 })
    .catch(() => {})
}

async function openAi(page) {
  await page.goto('/ai-config')
  await expect(page.locator('[data-guide="ai-config-form"]')).toBeVisible({ timeout: NAV_TIMEOUT })
  await waitSplashGone(page)
}

async function mockNotifyConfig(page, data) {
  await page.route('**/admin/api/v1/notification/**', (route) => route.fulfill(ok({})))
  await page.route('**/admin/api/v1/notification/config', (route) =>
    route.fulfill(ok({ ...NOTIFY_BASE, ...data })),
  )
  await page.route('**/admin/api/v1/notification/templates*', (route) => route.fulfill(ok([])))
  await page.route('**/admin/api/v1/notification/logs*', (route) =>
    route.fulfill(ok({ items: [], total: 0 })),
  )
}

async function openNotify(page) {
  await page.goto('/notification')
  await expect(page.locator('[data-guide="notification-form"]')).toBeVisible({
    timeout: NAV_TIMEOUT,
  })
  await waitSplashGone(page)
}

mkdirSync(SHOTS, { recursive: true })

test.describe('T02898 AI 配置页的来源信息', () => {
  test('库里存过一部分：写明修改时间并点出 .env 回落字段', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockAiConfig(page, {
      loaded: true,
      load_error: null,
      updated_at: '2026-10-22T09:15:30',
      fallback_fields: ['llm.api_key', 'tts.timeout_sec'],
    })
    await openAi(page)

    const line = page.locator('[data-guide="ai-config-provenance"]')
    await expect(line).toBeVisible()
    await expect(line).toContainText('库里最后一次修改：2026-10-22 09:15:30')
    await expect(line).toContainText(
      '以下字段的值来自环境变量回落，库里并未保存：LLM · api_key、TTS · timeout_sec',
    )
    await expect(page.locator('[data-guide="ai-config-load-error"]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeEnabled()
    await page.screenshot({ path: resolve(SHOTS, 'ai_1_partial_fallback.png'), fullPage: true })
  })

  test('请求成功但读表失败：横幅写原因 + 保存禁用', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockAiConfig(page, {
      loaded: false,
      load_error: "RuntimeError: no such column: config_value; api_key='sk-<已脱敏>'",
      updated_at: null,
      fallback_fields: ['llm.api_key', 'tts.timeout_sec', 'image.model'],
    })
    await openAi(page)

    const banner = page.locator('[data-guide="ai-config-load-error"]')
    await expect(banner).toBeVisible()
    await expect(banner).toContainText('已禁止保存：RuntimeError')
    // 读失败时任何「上次修改时间」都不是本次读到的
    await expect(page.locator('[data-guide="ai-config-provenance"]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeDisabled()
    await page.screenshot({ path: resolve(SHOTS, 'ai_2_load_error_gated.png'), fullPage: true })
  })

  test('库内无记录：写「库里暂无记录」并逐个点名回落字段', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockAiConfig(page, {
      loaded: true,
      load_error: null,
      updated_at: null,
      fallback_fields: ['llm.api_key', 'tts.timeout_sec', 'image.model'],
    })
    await openAi(page)

    const line = page.locator('[data-guide="ai-config-provenance"]')
    await expect(line).toBeVisible()
    await expect(line).toContainText('库里暂无记录')
    await expect(line).toContainText('LLM · api_key')
    await expect(line).toContainText('TTS · timeout_sec')
    await expect(line).toContainText('图片生成 · model')
    await page.screenshot({ path: resolve(SHOTS, 'ai_3_empty_table.png'), fullPage: true })
  })
})

test.describe('T02898 通知配置页的来源信息', () => {
  test('库里存过一部分：写明修改时间并点出默认值回落字段', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockNotifyConfig(page, {
      loaded: true,
      load_error: null,
      updated_at: '2026-10-21T18:20:00',
      fallback_fields: ['dingtalk_webhook', 'email_smtp_host'],
    })
    await openNotify(page)

    const line = page.locator('[data-guide="notification-provenance"]')
    await expect(line).toBeVisible()
    await expect(line).toContainText('库里最后一次修改：2026-10-21 18:20:00')
    await expect(line).toContainText(
      '以下字段库里未保存，当前使用的是默认值：钉钉 Webhook、SMTP 服务器',
    )
    await expect(page.locator('[data-guide="notification-load-error"]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeEnabled()
    await page.screenshot({ path: resolve(SHOTS, 'notify_1_partial_fallback.png'), fullPage: true })
  })

  test('读表失败：保存与测试发送都禁用（测试前会先保存）', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockNotifyConfig(page, {
      loaded: false,
      load_error: 'RuntimeError: database is locked',
      updated_at: null,
      fallback_fields: ['global_enabled', 'dingtalk_webhook'],
    })
    await openNotify(page)

    const banner = page.locator('[data-guide="notification-load-error"]')
    await expect(banner).toBeVisible()
    await expect(banner).toContainText('已禁止保存：RuntimeError')
    await expect(page.locator('[data-guide="notification-provenance"]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeDisabled()
    await expect(page.getByRole('button', { name: '测试发送' }).first()).toBeDisabled()
    await page.screenshot({ path: resolve(SHOTS, 'notify_2_load_error_gated.png'), fullPage: true })
  })

  test('库内无记录：写「库里暂无记录」并点名全部默认值字段', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockNotifyConfig(page, {
      loaded: true,
      load_error: null,
      updated_at: null,
      fallback_fields: ['global_enabled', 'dingtalk_webhook'],
    })
    await openNotify(page)

    const line = page.locator('[data-guide="notification-provenance"]')
    await expect(line).toBeVisible()
    await expect(line).toContainText('库里暂无记录')
    await expect(line).toContainText('全局总开关')
    await expect(line).toContainText('钉钉 Webhook')
    await page.screenshot({ path: resolve(SHOTS, 'notify_3_empty_table.png'), fullPage: true })
  })
})
