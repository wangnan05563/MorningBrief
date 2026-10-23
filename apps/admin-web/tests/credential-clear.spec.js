import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02919：四类凭据各有一条真的能清空的通道，且界面只指这些通道。
 *
 * F3 那一轮把「留空＝不修改」写进界面，代价是除 LLM 之外（TTS / 图片 / COS）
 * 根本没有清除入口，而 TTS/图片页的提示还在让用户点「恢复初始配置」——
 * 那句话对它们是不成立的（那个接口只清 LLM 的四项）。
 *
 * 这里在真实浏览器里核对三件事：
 * 1. 三个新入口（清除 TTS 凭证 / 清除图片 Key / COS 清除凭证）走统一确认规范
 *    （动作 + 对象 + 影响范围 + 不可逆声明），确认后打到带 scope 的接口；
 * 2. 清除成功后界面返显后端返回的清除后配置，不是继续挂着旧的脱敏值；
 * 3. 配置没读到（loaded=false 或接口失败）时按钮点不动——清凭据不可逆，
 *    不允许在未知状态下动线上凭证。
 *
 * 运行：cd apps/admin-web && PW_CHANNEL=chrome npx playwright test tests/credential-clear.spec.js --workers=1
 */

const NAV_TIMEOUT = 30000

const ok = (data) => ({ status: 200, json: { code: 0, message: 'ok', data } })

// GET /ai/config 下发的是脱敏值；清除后端再次下发（无 .env 回落时为空）
const AI_LOADED = {
  llm: { api_key: '****abcd', base_url: 'https://api.example.com', model: 'gpt-4o' },
  tts: {
    provider: 'aliyun',
    api_key: '****tts',
    appkey: '****app',
    tencent_secret_id: '****txid',
    tencent_secret_key: '****txkey',
  },
  image: { api_key: '****img', base_url: '', model: '' },
}
const AI_CLEARED = {
  ...AI_LOADED,
  tts: { ...AI_LOADED.tts, api_key: '', appkey: '', tencent_secret_id: '', tencent_secret_key: '' },
  image: { ...AI_LOADED.image, api_key: '' },
}

const COS_BASE = {
  configured: true,
  secret_id: '****tZ5P',
  secret_key: '****kU3Q',
  region: 'ap-beijing',
  bucket: 'morningbrief-audio-1311027859',
  cdn_domain: '',
  loaded: true,
  load_error: null,
  updated_at: '2026-08-11T02:45:46',
  fallback_fields: [],
}

async function mockAi(page, configResponse) {
  await page.route('**/admin/api/v1/ai/config**', (route) =>
    route.fulfill(
      configResponse.fail
        ? { status: 200, json: { code: 500, message: '服务不可用（测试注入）', data: null } }
        : ok(configResponse.data),
    ),
  )
  await page.route('**/admin/api/v1/ai/presets**', (route) => route.fulfill(ok([])))
  await page.route('**/admin/api/v1/ai/audio-profile**', (route) => route.fulfill(ok(null)))
  await page.route('**/admin/api/v1/ai/voices**', (route) => route.fulfill(ok([])))
}

async function openAi(page, tabName) {
  await page.goto('/ai-config')
  if (tabName) await page.getByRole('tab', { name: tabName }).click()
}

const clearRequest = (page, path, scope) =>
  page.waitForRequest(
    (req) => req.method() === 'POST' && req.url().includes(`${path}${scope ? `?scope=${scope}` : ''}`),
    { timeout: NAV_TIMEOUT },
  )

test.describe('T02919 凭据清除通道', () => {
  test.describe('AI 服务页', () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript(() => {
        Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
        Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
      })
      await mockAi(page, { data: AI_LOADED })
      await page.route('**/admin/api/v1/ai/reset-config**', (route) => route.fulfill(ok(AI_CLEARED)))
      await setLoginState(page, 'admin')
    })

    test('「清除 TTS 凭证」确认四要素齐全，确认后按 scope=tts 调用并返显清除后配置', async ({ page }) => {
      await openAi(page, 'TTS 语音合成')
      const btn = page.getByRole('button', { name: '清除 TTS 凭证' })
      await expect(btn).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(btn).toBeEnabled()

      await btn.click()
      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      // 动作 + 对象
      await expect(box.getByText('清除 TTS 凭证：已保存的 TTS 凭据')).toBeVisible()
      // 影响范围逐行列出被清掉的凭据族
      await expect(box.getByText('影响范围：阿里云 AccessToken / AppKey')).toBeVisible()
      await expect(box.getByText('腾讯云 SecretId / SecretKey')).toBeVisible()
      // 不可逆声明
      await expect(box.getByText(/此操作不可恢复/)).toBeVisible()

      const req = clearRequest(page, '/admin/api/v1/ai/reset-config', 'tts')
      await box.getByRole('button', { name: '确认清除' }).click()
      await req

      await expect(page.locator('.el-message').getByText('TTS 凭证已清除，回退到 .env 默认值').first()).toBeVisible()
      // 返显后端清除后的值，而不是继续挂着 ****tts
      await expect(page.locator('input[placeholder^="NLS AccessToken"]')).toHaveValue('')
    })

    test('取消确认不发出清除请求', async ({ page }) => {
      await openAi(page, '图片模型')
      await page.getByRole('button', { name: '清除图片 Key' }).click()
      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(box.getByText('清除图片生成 Key：已保存的图片生成 API Key')).toBeVisible()
      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()

      const sent = page
        .waitForRequest((req) => req.url().includes('reset-config'), { timeout: 2000 })
        .then(() => true)
        .catch(() => false)
      expect(await sent).toBe(false)
    })

    test('图片清除只带 scope=image，并提示回退 .env', async ({ page }) => {
      await openAi(page, '图片模型')
      await page.getByRole('button', { name: '清除图片 Key' }).click()
      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })

      const req = clearRequest(page, '/admin/api/v1/ai/reset-config', 'image')
      await box.getByRole('button', { name: '确认清除' }).click()
      const request = await req
      expect(request.url()).toContain('scope=image')
      expect(request.url()).not.toContain('scope=all')

      await expect(
        page.locator('.el-message').getByText('图片生成 Key 已清除，回退到 .env 默认值').first(),
      ).toBeVisible()
      await expect(page.locator('input[placeholder^="图像生成服务 API Key"]')).toHaveValue('')
    })

    test('LLM 的「恢复初始配置」只清 llm，不再被当作 TTS/图片的清除入口', async ({ page }) => {
      await openAi(page)
      const req = clearRequest(page, '/admin/api/v1/ai/reset-config', 'llm')
      await page.getByRole('button', { name: '恢复初始配置' }).click()
      const box = page.locator('.el-message-box')
      await expect(box.getByText('恢复 LLM 初始配置：当前 LLM 配置与全部预设')).toBeVisible({
        timeout: NAV_TIMEOUT,
      })
      await box.getByRole('button', { name: '确认恢复' }).click()
      await req

      // 提示文案指的就是这个按钮，且 TTS/图片那两处不再指它
      await expect(page.locator('.field-tip:visible').filter({ hasText: '留空＝不修改' }).first()).toContainText(
        '要清除请点右上角「恢复初始配置」',
      )
      await openAi(page, 'TTS 语音合成')
      await expect(page.locator('.field-tip:visible').filter({ hasText: '留空＝不修改' }).first()).toContainText(
        '要作废请点下方「清除 TTS 凭证」',
      )
    })

    test('配置加载失败时三个清除入口全部点不动', async ({ page }) => {
      await mockAi(page, { fail: true })
      await openAi(page)
      await expect(page.locator('.config-load-error')).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(page.getByRole('button', { name: '恢复初始配置' })).toBeDisabled()

      await openAi(page, 'TTS 语音合成')
      await expect(page.getByRole('button', { name: '清除 TTS 凭证' })).toBeDisabled()
      await openAi(page, '图片模型')
      await expect(page.getByRole('button', { name: '清除图片 Key' })).toBeDisabled()
    })
  })

  test.describe('云端配置页', () => {
    async function mockCos(page, configData) {
      await page.route('**/admin/api/v1/cos/config**', (route) => route.fulfill(ok(configData)))
      await page.route('**/admin/api/v1/cos/status**', (route) =>
        route.fulfill(ok({ ...COS_BASE, configured: true })),
      )
      await page.route('**/admin/api/v1/cos/reset-config**', (route) =>
        route.fulfill(ok({ ...COS_BASE, secret_id: '', secret_key: '', configured: false })),
      )
    }

    test.beforeEach(async ({ page }) => {
      await page.addInitScript(() => {
        Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
        Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
      })
      await mockCos(page, COS_BASE)
      await setLoginState(page, 'admin')
    })

    test('「清除凭证」只清凭证、明确保留地域/桶/CDN，确认后调用并重新拉取配置', async ({ page }) => {
      let reloads = 0
      page.on('request', (req) => {
        if (req.method() === 'GET' && req.url().includes('/cos/config')) reloads += 1
      })
      await page.goto('/cos-config')
      const btn = page.getByRole('button', { name: '清除凭证' })
      await expect(btn).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(btn).toBeEnabled()

      await btn.click()
      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(box.getByText('清除 COS 凭证：已保存的 SecretId / SecretKey')).toBeVisible()
      await expect(box.getByText('影响范围：地域、存储桶、CDN 域名保留不变')).toBeVisible()
      await expect(box.getByText('清除后回退到 .env 默认值，旧凭证立即不可用')).toBeVisible()

      const req = clearRequest(page, '/admin/api/v1/cos/reset-config')
      await box.getByRole('button', { name: '确认清除' }).click()
      await req

      await expect(page.locator('.el-message').getByText('COS 凭证已清除，回退到 .env 默认值').first()).toBeVisible()
      // 清除后必须重新拉取：否则屏幕上还是清除前那份脱敏值
      await expect.poll(() => reloads, { timeout: NAV_TIMEOUT }).toBeGreaterThan(1)
    })

    test('读表失败（loaded=false）时清除凭证点不动', async ({ page }) => {
      await mockCos(page, {
        ...COS_BASE,
        loaded: false,
        load_error: 'RuntimeError: no such column: config_value',
        fallback_fields: ['secret_id', 'secret_key', 'region', 'bucket', 'cdn_domain'],
      })
      await page.goto('/cos-config')
      await expect(page.locator('[data-guide="cos-config-load-error"]')).toBeVisible({
        timeout: NAV_TIMEOUT,
      })
      await expect(page.getByRole('button', { name: '清除凭证' })).toBeDisabled()
    })

    test('提示文案点名的就是页面上这个按钮', async ({ page }) => {
      await page.goto('/cos-config')
      await expect(page.locator('.el-alert').filter({ hasText: '腾讯云 COS 凭证' })).toContainText(
        '要**作废**凭证请点右上角「清除凭证」',
      )
      await expect(page.getByRole('button', { name: '清除凭证' })).toBeVisible({ timeout: NAV_TIMEOUT })
    })
  })
})
