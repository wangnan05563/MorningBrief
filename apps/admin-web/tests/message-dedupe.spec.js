import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { setLoginState, queueStatsResponse, channelsListResponse } from './helpers/mock'

/**
 * 提示去重与单一出口（T02497：FR-UX-303）
 *
 * 两条要求分别对应两类真实噪声：
 * - 「2 秒内去重」：并行请求同时失败时，拦截器为每个请求各弹一条同样的文案；
 * - 「拦截器已弹不二次弹」：页面 catch 又用同一个 e.message 弹一遍，一件事两条 toast。
 * 另外守住「单一出口」：任何模块不得绕过 utils/message 直接用 element-plus 的 ElMessage，
 * 否则去重与窗口守卫形同虚设——这条用源码扫描断言，比口头约定可靠。
 */
const SRC_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src')

/** 打开队列页并把三个只读接口都 mock 成给定响应，返回后页面已具备 __safeMessage */
async function openQueuePage(page, handler) {
  await setLoginState(page, 'admin')
  await page.route('**/admin/api/v1/events/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }))
  // 队列页筛选下拉要拉频道列表；不 mock 会打到未运行的后端，多弹一条网络错误提示干扰计数
  await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
  await page.route('**/admin/api/v1/queue/**', handler)
  await page.goto('/queue')
  await page.waitForFunction(() => typeof globalThis.__safeMessage?.show === 'function')
}

test.describe('提示去重与单一出口', () => {

  test('同类型同文案 2 秒内只弹一条', async ({ page }) => {
    await openQueuePage(page, (route) => route.fulfill({ json: queueStatsResponse }))
    const n = await page.evaluate(async () => {
      globalThis.__safeMessage.reset()
      await new Promise((r) => setTimeout(r, 700))
      const baseline = document.querySelectorAll('.el-message').length
      for (let i = 0; i < 3; i++) globalThis.__safeMessage.show('error', '网络请求失败')
      await new Promise((r) => setTimeout(r, 300))
      return {
        toasts: document.querySelectorAll('.el-message').length - baseline,
        keys: globalThis.__safeMessage.recentKeys(),
        windowMs: globalThis.__safeMessage.dedupeMs,
      }
    })
    expect(n.toasts).toBe(1)
    expect(n.keys).toEqual(['error|网络请求失败'])
    expect(n.windowMs).toBe(2000)
  })

  test('同文案不同类型不互相吞掉', async ({ page }) => {
    await openQueuePage(page, (route) => route.fulfill({ json: queueStatsResponse }))
    const count = await page.evaluate(async () => {
      globalThis.__safeMessage.reset()
      await new Promise((r) => setTimeout(r, 700))
      const baseline = document.querySelectorAll('.el-message').length
      globalThis.__safeMessage.show('error', '配额不足')
      globalThis.__safeMessage.show('warning', '配额不足')
      await new Promise((r) => setTimeout(r, 300))
      return document.querySelectorAll('.el-message').length - baseline
    })
    expect(count).toBe(2)
  })

  test('不同文案照常各弹一条', async ({ page }) => {
    await openQueuePage(page, (route) => route.fulfill({ json: queueStatsResponse }))
    const count = await page.evaluate(async () => {
      globalThis.__safeMessage.reset()
      await new Promise((r) => setTimeout(r, 700))
      const baseline = document.querySelectorAll('.el-message').length
      globalThis.__safeMessage.show('error', 'A 接口超时')
      globalThis.__safeMessage.show('error', 'B 接口超时')
      await new Promise((r) => setTimeout(r, 300))
      return document.querySelectorAll('.el-message').length - baseline
    })
    expect(count).toBe(2)
  })

  test('超过 2 秒窗口后同文案可再次提醒', async ({ page }) => {
    await openQueuePage(page, (route) => route.fulfill({ json: queueStatsResponse }))
    const count = await page.evaluate(async () => {
      globalThis.__safeMessage.reset()
      await new Promise((r) => setTimeout(r, 700))
      globalThis.__safeMessage.show('error', '持续失败的服务')
      await new Promise((r) => setTimeout(r, 2300))
      globalThis.__safeMessage.show('error', '持续失败的服务')
      await new Promise((r) => setTimeout(r, 300))
      // 按文案筛选：页面加载过程中拦截器可能另有其它文案的提示并存，
      // 只数本用例这条文案的节点才不会受干扰
      return [...document.querySelectorAll('.el-message')].filter((el) => el.textContent.includes('持续失败的服务')).length
    })
    // 2 秒窗口已过 → 第二次真的弹了出来；第一条默认 3 秒才消失，故此刻两条并存
    expect(count).toBe(2)
  })

  test('并行请求同时失败时，拦截器只弹一条', async ({ page }) => {
    // 队列页一次并发 stats / config / tasks 三个请求，全部返回同一条业务错误
    await openQueuePage(page, (route) =>
      route.fulfill({ json: { code: 500, message: '服务暂不可用', data: null } }))
    await expect(page.locator('.el-message')).toHaveCount(1, { timeout: 30000 })
    await expect(page.locator('.el-message').first()).toContainText('服务暂不可用')
  })

  test('拦截器已弹过的错误，页面不再二次弹', async ({ page }) => {
    await openQueuePage(page, (route) => route.fulfill({ json: queueStatsResponse }))
    const result = await page.evaluate(async () => {
      globalThis.__safeMessage.reset()
      await new Promise((r) => setTimeout(r, 700))
      // 模拟拦截器已为该错误弹过提示（__uiNotified 由 api 层写入）
      const notified = Object.assign(new Error('服务暂不可用'), { __uiNotified: true })
      globalThis.__safeMessage.notifyOnce(notified, '服务暂不可用')
      const plain = new Error('频道名已存在')
      globalThis.__safeMessage.notifyOnce(plain, '创建失败')
      await new Promise((r) => setTimeout(r, 300))
      return {
        toasts: [...document.querySelectorAll('.el-message')].map((el) => el.textContent),
      }
    })
    // 未标记的错误按调用方文案弹出；已标记的那条完全不弹（不再出现「同一件事两条 toast」）
    expect(result.toasts.filter((t) => t.includes('创建失败'))).toHaveLength(1)
    expect(result.toasts.filter((t) => t.includes('服务暂不可用'))).toHaveLength(0)
  })

  test('提示必须走 utils/message 单一出口（含 ElNotification 等旁路）', () => {
    const offenders = []
    // 直引这些符号都等于绕过统一出口：去重、窗口守卫、隐藏期补发全部失效。
    // 包装器本体（utils/message.js）是唯一允许直连 element-plus 的地方；
    // main.js 的默认导入只用于 app.use(ElementPlus) 注册组件，不产生提示。
    const NAMED_BYPASS =
      /import\s*\{[^}]*\b(?:ElMessage|ElMessageBox|ElNotification|ElLoading)\b[^}]*\}\s*from\s*['"]element-plus['"]/
    const NS_BYPASS = /import\s*\*\s*as\s+\w+\s+from\s*['"]element-plus['"]/
    const walk = (dir) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) { walk(full); continue }
        if (!/\.(vue|js)$/.test(entry.name)) continue
        // 包装器本体必须直连 element-plus
        if (full.endsWith(path.join('utils', 'message.js'))) continue
        const text = fs.readFileSync(full, 'utf-8')
        if (NAMED_BYPASS.test(text) || NS_BYPASS.test(text)) {
          offenders.push(path.relative(SRC_DIR, full))
        }
      }
    }
    walk(SRC_DIR)
    expect(offenders, `绕过统一提示出口的页面：${offenders.join(', ')}`).toEqual([])
  })

  test('页面 catch 与拦截器同一件事只留一条说明（真实链路）', async ({ page }) => {
    // 落地点选自动审批保存：请求非 silent，拦截器会先弹后端 message；
    // 页面 catch 改用 notifyErrorOnce 后不得再弹一条「保存失败：…」。
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/auto-review/config', (route) => {
      if (route.request().method() === 'PUT') {
        return route.fulfill({ json: { code: 500, message: '规则保存被拒绝', data: null } })
      }
      return route.fulfill({ json: { code: 0, message: 'ok', data: {
        enabled: false,
        require_content_safe: true,
        require_steps_first_success: false,
        keyword_whitelist: [],
        skipped_rules: [],
        risk_acknowledged: false,
      } } })
    })
    await page.route('**/admin/api/v1/auto-review/stats**', (route) =>
      route.fulfill({ json: { code: 0, message: 'ok', data: { fail_distribution: [] } } }))
    await page.route('**/admin/api/v1/auto-review/history**', (route) =>
      route.fulfill({ json: { code: 0, message: 'ok', data: { total: 0, list: [] } } }))
    // 布局层的「检查更新」也是非 silent 请求；不 mock 会打到未运行/旧版后端，多弹一条干扰计数
    await page.route('**/admin/api/v1/about/check-update', (route) =>
      route.fulfill({ json: { code: 0, message: 'ok', data: { update_available: false } } }))

    await page.goto('/auto-review')
    await page.getByRole('button', { name: '保存配置' }).click()

    // 先等拦截器那条真的出现，再给页面 catch 一个「补第二条」的机会（若回归会发生在这里）
    await expect(page.locator('.el-message').filter({ hasText: '规则保存被拒绝' })).toHaveCount(1)
    await page.waitForTimeout(400)
    const toasts = await page.locator('.el-message').allTextContents()
    expect(toasts).toHaveLength(1)
    expect(toasts[0]).toContain('规则保存被拒绝')
  })
})
