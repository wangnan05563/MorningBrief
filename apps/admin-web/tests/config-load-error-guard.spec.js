import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 配置页加载失败禁存 + 重试（T02487 / FR-UX-104，来源建议 H1、G2、G8）
 *
 * 覆盖四个配置页（COS / 内网穿透 / 通知 / AI 服务）：
 * - 首次加载失败 → 页内错误态可见 + 「重新加载」按钮存在
 * - 保存按钮必须禁用（此前会把代码默认值当已加载配置提交，覆盖线上配置）
 * - 重试成功后错误态消失、保存恢复可用
 */

const FAIL = { json: { code: 500, message: '服务不可用（测试注入）' } }

// dev 服务器冷启动时首个懒加载 chunk 要现场编译，首屏可能远超 expect 默认 5s
const NAV_TIMEOUT = 30000

function ok(data) {
  return { json: { code: 0, message: 'ok', data } }
}

async function mockRoutes(page, paths, responses) {
  for (const p of paths) {
    await page.route(`**/admin/api/v1/${p}**`, (route) => {
      const resp = responses.get(p)
      return route.fulfill(resp.fail ? { ...resp.fail, status: 200 } : ok(resp.data))
    })
  }
}

for (const tc of [
  {
    name: '云端配置（COS）',
    path: '/cos-config',
    configKey: 'cos/config',
    extra: [
      ['cos/status', { data: { configured: true, bucket: 'demo', region: 'ap-guangzhou' } }],
    ],
    loaded: { data: { secret_id: '****', secret_key: '****', region: 'ap-guangzhou', bucket: 'demo', cdn_domain: '' } },
  },
  {
    name: '内网穿透（Tunnel）',
    path: '/tunnel',
    configKey: 'tunnel/config',
    extra: [['tunnel/status', { data: { running: false, provider: 'cloudflare', url: '' } }]],
    loaded: {
      data: {
        provider: 'cloudflare', local_port: 8000, binary_path: '', auto_start: false,
        tunnel_mode: 'quick', tunnel_name: '', tunnel_id: '', credentials_file: '',
        hostname: '', cert_file: '',
      },
    },
  },
  {
    name: '通知管理',
    path: '/notification',
    configKey: 'notification/config',
    extra: [
      ['notification/templates', { data: [] }],
      ['notification/templates*', { data: [] }],
      ['notification/logs*', { data: { items: [], total: 0 } }],
    ],
    loaded: {
      data: {
        global_enabled: true, failed_enabled: true, review_enabled: true, published_enabled: false,
        dingtalk_webhook: '****', email_smtp_port: 587, auto_detected_base_url: 'http://127.0.0.1:8000',
      },
    },
  },
  {
    name: 'AI 服务配置',
    path: '/ai-config',
    configKey: 'ai/config',
    extra: [
      ['ai/presets', { data: [] }],
      ['ai/audio-profile', { data: null }],
      ['ai/voices*', { data: [] }],
    ],
    loaded: { data: { llm: { base_url: 'https://api.example.com', model: 'gpt-4o' }, tts: { provider: 'aliyun' }, image: {} } },
  },
]) {
  test.describe(`配置加载失败禁存 · ${tc.name}`, () => {
    /** 每个路由键的当前响应；测试内可翻转 fail -> loaded 模拟重试成功 */
    let responses

    test.beforeEach(async ({ page }) => {
      // 页面隐藏时 axios 会静默丢弃 ElMessage，headless 下需覆盖
      await page.addInitScript(() => {
        Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
        Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
      })
      responses = new Map([[tc.configKey, { fail: FAIL }], ...tc.extra])
      await mockRoutes(page, [tc.configKey, ...tc.extra.map(([k]) => k)], responses)
      await setLoginState(page, 'admin')
    })

    test('加载失败：显示页内错误态 + 重试，保存按钮禁用', async ({ page }) => {
      await page.goto(tc.path)

      // 限定到错误横幅本身：同一条错误文案也会以 el-message toast 出现，全局文本会命中两个元素
      const banner = page.locator('.config-load-error')
      await expect(banner).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(banner).toContainText('服务不可用（测试注入）')
      await expect(banner.getByRole('button', { name: '重新加载' })).toBeVisible()

      const save = page.getByRole('button', { name: '保存配置' }).first()
      await expect(save).toBeVisible()
      await expect(save).toBeDisabled()
    })

    test('重试成功后：错误态消失且保存恢复可用', async ({ page }) => {
      await page.goto(tc.path)
      await expect(page.locator('.config-load-error')).toBeVisible({ timeout: NAV_TIMEOUT })

      // 后端恢复：翻转配置接口为成功再点重试
      responses.set(tc.configKey, tc.loaded)
      await page.locator('.config-load-error').getByRole('button', { name: '重新加载' }).click()

      await expect(page.locator('.config-load-error')).toHaveCount(0)
      await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeEnabled()
    })
  })
}
