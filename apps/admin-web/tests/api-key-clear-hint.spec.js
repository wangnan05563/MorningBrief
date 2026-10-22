import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * F3：AI 服务页三处密钥输入框，界面要把「留空＝不修改」说实话（FR-UX-101 / ACC-UX-101 第 8 条）
 *
 * 原缺陷的用户侧形态：清空 API Key → 保存 → 提示成功 → 旧 Key 还在，界面上没有任何地方
 * 解释这件事，用户只会以为保存坏了（或者更糟：以为自己已经删掉了密钥）。
 * 这里在真实浏览器里核对三处提示确实渲染出来了、指路按钮真的存在且可用，
 * 并核对配置加载失败时「恢复初始配置」是点不动的——那按钮真会清空 llm_api_key。
 *
 * 运行：cd apps/admin-web && PW_CHANNEL=chrome npx playwright test tests/api-key-clear-hint.spec.js
 */

const NAV_TIMEOUT = 30000
const CONFIG_KEY = 'ai/config'

function ok(data) {
  return { json: { code: 0, message: 'ok', data } }
}

// 后端 GET 下发的就是脱敏值，前端提交时再折算成空串（AIConfig.vue:1366）
const LOADED = ok({
  llm: { api_key: '****abcd', base_url: 'https://api.example.com', model: 'gpt-4o' },
  tts: { provider: 'aliyun', api_key: '****tts', appkey: '' },
  image: { api_key: '****img', base_url: '', model: '' },
})
const EXTRA = new Map([
  ['ai/presets', ok([])],
  ['ai/audio-profile', ok(null)],
  ['ai/voices*', ok([])],
])

async function mock(page, overrides) {
  const responses = new Map([[CONFIG_KEY, overrides || LOADED], ...EXTRA])
  for (const key of responses.keys()) {
    await page.route(`**/admin/api/v1/${key}**`, (route) => {
      const resp = responses.get(key)
      return route.fulfill(resp.fail ? { ...resp.fail, status: 200 } : resp)
    })
  }
}

test.describe('F3 密钥留空语义在界面上的呈现', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
      Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
    })
    await mock(page)
    await setLoginState(page, 'admin')
  })

  test('LLM 页：提示可见，且指路的「恢复初始配置」按钮真的存在可用', async ({ page }) => {
    await page.goto('/ai-config')
    const tip = page.locator('.field-tip:visible', { hasText: '留空＝不修改' }).first()
    await expect(tip).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(tip).toContainText('清空这一栏并保存不会删除已保存的 Key')
    await expect(tip).toContainText('要清除请点右上角「恢复初始配置」')

    const reset = page.getByRole('button', { name: '恢复初始配置' })
    await expect(reset).toBeVisible()
    await expect(reset).toBeEnabled()
  })

  test('TTS 与图片页同样有留空提示（不能只修被点名的 LLM 一处）', async ({ page }) => {
    await page.goto('/ai-config')
    await page.getByRole('tab', { name: 'TTS 语音合成' }).click()
    // el-tabs 只是把非当前面板 display:none，DOM 还在；不加 :visible 会命中隐藏的那份
    await expect(
      page.locator('.field-tip:visible', { hasText: '不会删除已保存的凭证' }).first(),
    ).toBeVisible({ timeout: NAV_TIMEOUT })

    await page.getByRole('tab', { name: '图片模型' }).click()
    await expect(
      page.locator('.field-tip:visible', { hasText: '留空＝不修改' }).first(),
    ).toBeVisible({ timeout: NAV_TIMEOUT })
  })

  test('配置没加载成功时「恢复初始配置」点不动（它真会清空线上 Key）', async ({ page }) => {
    await mock(page, { fail: { json: { code: 500, message: '服务不可用（测试注入）' } } })
    await page.goto('/ai-config')
    await expect(page.locator('.config-load-error')).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(page.getByRole('button', { name: '恢复初始配置' })).toBeDisabled()
  })
})
