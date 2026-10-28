import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 配置页草稿恢复明示（T02534 / F2 裁决：草稿优先 + 明示）
 *
 * 此前 useDraft 在加载成功后静默深合并本地草稿：屏幕上看到的是草稿值，页面却没有任何提示，
 * 一次「保存配置」就把陈旧草稿写回线上，随后 commitDraft 抹掉唯一的痕迹（见
 * `_validate/news2/result_T02534_f2_evidence.md` 的 F2PROBE 读数）。
 *
 * 本文件按四段走真实浏览器，覆盖五个接入页：
 *   1. 种入与服务端不同的草稿 → 页顶横幅可见且报出差异项数，两个出口都在；
 *   2. 点「保留草稿」→ 横幅消失、本机草稿仍在（下次进入会再次带出）；
 *   3. 重新进入 → 横幅再次出现；
 *   4. 点「丢弃草稿，载入服务器值」→ 横幅消失、表单回到服务器值、本机草稿被删除。
 *
 * 反向约束（横幅不能常驻）：无草稿时不得出现横幅，见 COS 用例的第二段。
 */

const NAV_TIMEOUT = 30000

function ok(data) {
  return { json: { code: 0, message: 'ok', data } }
}

const CASES = [
  {
    name: 'AI 服务配置',
    path: '/ai-config',
    key: 'mb_draft_ai-config-llm',
    draft: { timeout_sec: 45 },
    fieldLabel: '超时(秒)',
    serverValue: '30',
    draftValue: '45',
    routes: {
      'ai/config': {
        llm: {
          api_key: '', base_url: 'https://server.example.com', model: 'gpt-4o',
          timeout_sec: 30, chat_timeout_sec: 120, retry_attempts: 3,
        },
        tts: { provider: 'aliyun' },
        image: {},
      },
      'ai/presets': [],
      'ai/audio-profile': null,
      'ai/voices': [],
    },
  },
  {
    name: '云端配置（COS）',
    path: '/cos-config',
    key: 'mb_draft_cos-config',
    draft: { cdn_domain: 'draft-cdn.example.com' },
    fieldLabel: 'CDN 加速域名',
    serverValue: 'server-cdn.example.com',
    draftValue: 'draft-cdn.example.com',
    routes: {
      'cos/config': {
        secret_id: '****', secret_key: '****', region: 'ap-guangzhou',
        bucket: 'demo-1250000000', cdn_domain: 'server-cdn.example.com',
      },
      'cos/status': { configured: true, bucket: 'demo-1250000000', region: 'ap-guangzhou' },
    },
  },
  {
    name: '通知管理',
    path: '/notification',
    key: 'mb_draft_notification-config',
    draft: { email_smtp_port: 2525 },
    fieldLabel: 'SMTP 端口',
    serverValue: '587',
    draftValue: '2525',
    routes: {
      'notification/config': {
        global_enabled: true, failed_enabled: true, review_enabled: true, published_enabled: false,
        dingtalk_webhook: '****', email_smtp_port: 587,
        auto_detected_base_url: 'http://127.0.0.1:8000',
      },
      'notification/templates': [],
      'notification/logs': { items: [], total: 0 },
    },
  },
  {
    name: '自动审批配置',
    path: '/auto-review',
    key: 'mb_draft_auto-review-config',
    draft: { require_content_safe: false },
    switchIndex: 1,
    serverChecked: true,
    draftChecked: false,
    routes: {
      'auto-review/config': {
        enabled: false, require_content_safe: true, require_steps_first_success: true,
        keyword_whitelist: [], risk_acknowledged: false, skipped_rules: ['keyword_whitelist'],
        updated_at: '2026-10-18T10:00:00', updated_by: 'admin',
      },
      'auto-review/stats': {
        total: 0, success_count: 0, failed_count: 0, success_rate: 0,
        avg_time_saved_sec: 0, total_time_saved_sec: 0, fail_distribution: [],
      },
      'auto-review/history': { list: [], total: 0 },
    },
  },
  {
    name: '内网穿透（Tunnel）',
    path: '/tunnel',
    key: 'mb_draft_tunnel-config',
    draft: { local_port: 9999 },
    fieldLabel: '本地端口',
    serverValue: '8000',
    draftValue: '9999',
    routes: {
      'tunnel/config': {
        provider: 'cloudflare', local_port: 8000, binary_path: '', auto_start: false,
        tunnel_mode: 'quick', tunnel_name: '', tunnel_id: '', credentials_file: '',
        hostname: '', cert_file: '',
      },
      'tunnel/status': { running: false, provider: 'cloudflare', url: '' },
    },
  },
]

function pickRoute(table, url) {
  for (const key of Object.keys(table)) {
    if (url.includes(`/admin/api/v1/${key}`)) return table[key]
  }
  return null
}

async function installRoutes(page, table) {
  await page.route('**/admin/api/v1/**', (route) => {
    const req = route.request()
    if (req.method() !== 'GET') return route.fulfill(ok(null))
    if (req.url().includes('/events/stream')) {
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
    }
    return route.fulfill(ok(pickRoute(table, req.url())))
  })
}

async function boot(page, tc) {
  // 页面隐藏时 axios 会静默丢弃 ElMessage，headless 下需覆盖
  await page.addInitScript(() => {
    Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
    Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
  })
  await installRoutes(page, tc.routes)
  await setLoginState(page, 'admin')
}

async function seedDraft(page, key, draft) {
  await page.addInitScript(([k, d]) => {
    try {
      localStorage.setItem(k, JSON.stringify(d))
    } catch {
      // about:blank 无 localStorage，正式页面加载时脚本会再执行
    }
  }, [key, draft])
}

async function fieldValue(page, label) {
  const input = page.locator('.el-form-item', { hasText: label }).locator('input').first()
  await expect(input).toBeVisible({ timeout: NAV_TIMEOUT })
  return input.inputValue()
}

async function switchChecked(page, index) {
  const sw = page.locator('.config-form .el-switch').nth(index)
  await expect(sw).toBeVisible({ timeout: NAV_TIMEOUT })
  return sw.evaluate((el) => el.classList.contains('is-checked'))
}

async function expectDraftState(page, tc, useDraftValue) {
  if (tc.switchIndex !== undefined) {
    expect(await switchChecked(page, tc.switchIndex)).toBe(useDraftValue ? tc.draftChecked : tc.serverChecked)
    return
  }
  expect(await fieldValue(page, tc.fieldLabel)).toBe(useDraftValue ? tc.draftValue : tc.serverValue)
}

for (const tc of CASES) {
  test.describe(`草稿恢复明示 · ${tc.name}`, () => {
    test('恢复即明示：保留继续用草稿 / 丢弃回填服务器值并清本机草稿', async ({ page }) => {
      await boot(page, tc)
      await seedDraft(page, tc.key, tc.draft)
      await page.goto(tc.path)

      const banner = page.getByTestId('draft-restored')
      await expect(banner).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(banner).toContainText('已恢复本地未保存草稿（1 项与服务器值不同）')
      await expect(banner.getByRole('button', { name: '保留草稿' })).toBeVisible()
      await expect(banner.getByRole('button', { name: '丢弃草稿，载入服务器值' })).toBeVisible()
      // 草稿优先：横幅出现时表单里确实是草稿值
      await expectDraftState(page, tc, true)

      // 保留：只是不再提示，本机草稿仍在
      await banner.getByRole('button', { name: '保留草稿' }).click()
      await expect(banner).toHaveCount(0)
      expect(await page.evaluate((k) => localStorage.getItem(k), tc.key)).not.toBeNull()

      // 重新进入：草稿仍会带出，因此横幅必须再来一次
      await page.reload()
      await expect(page.getByTestId('draft-restored')).toBeVisible({ timeout: NAV_TIMEOUT })
      await expectDraftState(page, tc, true)

      // 丢弃：表单回到服务器值，本机草稿删除
      await page.getByTestId('draft-restored').getByRole('button', { name: '丢弃草稿，载入服务器值' }).click()
      await expect(page.getByTestId('draft-restored')).toHaveCount(0)
      await expectDraftState(page, tc, false)
      expect(await page.evaluate((k) => localStorage.getItem(k), tc.key)).toBeNull()
    })
  })
}

test.describe('草稿横幅不得常驻 · 云端配置（COS）', () => {
  const tc = CASES.find((c) => c.path === '/cos-config')

  test('无草稿时加载成功不出现横幅', async ({ page }) => {
    await boot(page, tc)
    await page.goto(tc.path)
    await expect(page.locator('.config-load-error')).toHaveCount(0)
    await expect(page.getByTestId('draft-restored')).toHaveCount(0)
    expect(await fieldValue(page, tc.fieldLabel)).toBe(tc.serverValue)
  })
})
