import { test, expect } from '@playwright/test'
import { setLoginState, workflowListResponse } from './helpers/mock'

/**
 * T02543 / ACC-UX-007：长任务与流式收尾的浏览器级验收。
 *
 * 四条对应 FR-UX-701 与 FR-UX-702 的可观察点：
 * 1. 长回答（>60s）不中断——真实等待 61s，而不是只断言常量；
 * 2. 点「停止生成」后请求中止、loading 收起、问题回到输入框；
 * 3. VACUUM 这类分钟级操作不再被全局 15s 判死——延迟 16s 仍以「预览完成」收场；
 * 4. SSE 断流可见（banner 升到 offline）且「立即重连并刷新」真的发起重连 + 刷新。
 *
 * 超时/中止的纯函数分支已由 tests/unit/ai-chat.test.mjs 与 feed-health.test.mjs 覆盖，
 * 本 spec 只证浏览器里确实这样走，不重复断常量。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

async function mockAssistantBase(page) {
  await page.route(`${API}/ai/models`, (route) =>
    route.fulfill({ json: ok({ success: true, models: [{ id: 'deepseek-chat' }] }) })
  )
  await page.route(`${API}/ai/selected-model`, (route) => {
    if (route.request().method() === 'POST') return route.fulfill({ json: ok(null) })
    return route.fulfill({ json: ok({ model: 'deepseek-chat' }) })
  })
}

async function openQa(page) {
  await setLoginState(page, 'admin')
  await mockAssistantBase(page)
  await page.goto('/ai-qa')
  await page.getByRole('tab', { name: '知识库问答' }).click()
  // el-input 把透传属性落在 textarea 自身，不能用「data-guide 容器 > textarea」；
  // 按可见的 textbox 语义定位，切到问答页签后调度输入框不在可见树里
  return page.getByRole('textbox', { name: /输入问题/ })
}

test.describe('ACC-UX-701 长回答与停止生成', () => {
  test('长回答等待 61 秒仍能收到回复，不被 15s 全局超时打断', async ({ page }) => {
    // 61s 真实等待 + 全量并发跑的双 worker 排队：断言窗口留到 90s，单测预算 150s
    test.setTimeout(150_000)
    const input = await openQa(page)
    await page.route(`${API}/ai/chat`, async (route) => {
      await new Promise((r) => setTimeout(r, 61_000))
      try {
        await route.fulfill({ json: ok({ success: true, reply: '超过一分钟的长回答已完整返回' }) })
      } catch {
        /* 页面提前关闭时路由已失效 */
      }
    })

    await input.fill('请用很长的篇幅解释这套系统的数据流')
    const t0 = Date.now()
    await page.getByRole('button', { name: '发送' }).click()

    // 20s 时仍在「正在思考」：如果还沿用 15s 全局超时，这里已经变成超时气泡
    await page.waitForTimeout(20_000)
    await expect(page.locator('.as-typing')).toHaveCount(1)
    await expect(page.locator('.as-typing')).toContainText('正在思考')

    await expect(page.locator('.as-msg-assistant', { hasText: '超过一分钟的长回答已完整返回' }))
      .toBeVisible({ timeout: 90_000 })
    expect(Date.now() - t0).toBeGreaterThan(60_000)
    await expect(page.locator('.as-typing')).toHaveCount(0)
  })

  test('点「停止生成」后请求中止、loading 收起、问题回到输入框', async ({ page }) => {
    const input = await openQa(page)
    await page.route(`${API}/ai/chat`, async (route) => {
      // 模拟一个迟迟不答的模型；用户中止后浏览器会断开这条请求
      await new Promise((r) => setTimeout(r, 30_000))
      try {
        await route.fulfill({ json: ok({ success: true, reply: '不该到达' }) })
      } catch {
        /* 请求已因中止被丢弃 */
      }
    })

    await input.fill('这个问题的回答太慢了')
    await page.getByRole('button', { name: '发送' }).click()
    await expect(page.locator('.as-typing')).toBeVisible()

    await page.getByRole('button', { name: '停止生成' }).click()

    await expect(page.locator('.as-msg-assistant', { hasText: '已停止生成' })).toBeVisible()
    await expect(page.locator('.as-typing')).toHaveCount(0)
    // 停止后界面必须立刻可继续输入，问题也放回输入框
    await expect(input).toBeEnabled()
    await expect(input).toHaveValue('这个问题的回答太慢了')
    await expect(page.getByRole('button', { name: '停止生成' })).toHaveCount(0)
  })
})

test.describe('FR-UX-702 分钟级操作与断流可见', () => {
  test('清理请求 16 秒才返回也不判失败，结果正常呈现', async ({ page }) => {
    test.setTimeout(90_000)
    await setLoginState(page, 'admin')
    await page.route(`${API}/maintenance/status`, (route) =>
      route.fulfill({
        json: ok({
          db: { db_size_mb: 12.5, playlog_count: 3, workflow_count: 2, review_count: 1, blacklist_count: 0 },
          logs: { total_size_mb: 1.2, file_count: 2, oldest: '2026-10-01' },
          cache: { ttlcache_count: 5, pycache_count: 1, temp_files: 2 },
        }),
      })
    )
    let chatElapsed = 0
    await page.route(`${API}/maintenance/cache`, async (route) => {
      const t0 = Date.now()
      await new Promise((r) => setTimeout(r, 16_000))
      chatElapsed = Date.now() - t0
      try {
        await route.fulfill({
          json: ok({ cleaned: ['临时文件 3 个（共 12.5 KB）'], errors: [] }),
        })
      } catch {
        /* 页面关闭 */
      }
    })

    await page.goto('/maintenance')
    await page.getByRole('button', { name: '预览清理' }).first().click()

    // 15s 之后才回来：全局 15s 超时会让这里只剩错误 toast、结果永远不出现
    await expect(page.locator('.cleanup-result')).toContainText('临时文件 3 个', { timeout: 25_000 })
    expect(chatElapsed).toBeGreaterThanOrEqual(15_000)
    await expect(page.locator('.cleanup-result')).not.toContainText('清理失败')
  })

  test('SSE 断流升到 offline 可见，点「立即重连并刷新」真的重连并刷新', async ({ page }) => {
    test.setTimeout(60_000)
    await setLoginState(page, 'admin')
    await page.route(`${API}/workflows*`, (route) => route.fulfill({ json: ok(workflowListResponse.data) }))
    let sseAttempts = 0
    let listHits = 0
    await page.route(`${API}/events/stream`, (route) => {
      sseAttempts += 1
      return route.abort('failed')
    })
    page.on('request', (req) => {
      if (req.url().includes('/admin/api/v1/workflows') && req.method() === 'GET') listHits += 1
    })

    await page.goto('/workflows')
    const banner = page.getByTestId('feed-health-banner')
    // 1s → 2s 两次退避后第 3 次失败升为 offline；retrying 阶段标题也含「实时通道已断开」，
    // 所以先等次数到 3，再断言标题是 offline 的那一句（没有「正在自动重连」后缀）
    await expect.poll(() => sseAttempts, { timeout: 20_000 }).toBeGreaterThanOrEqual(3)
    await expect(banner).toBeVisible()
    await expect(page.getByTestId('feed-health-title')).toHaveText('实时通道已断开')
    await expect(banner.getByTestId('feed-health-reconnect')).toBeVisible()
    const attemptsBefore = sseAttempts
    const listBefore = listHits
    await page.getByRole('button', { name: '立即重连并刷新' }).click()

    // 重连：EventSource 重新建立；刷新：列表再取一次（非静默，属于用户主动动作）
    await expect.poll(() => sseAttempts, { timeout: 15_000 }).toBeGreaterThan(attemptsBefore)
    await expect.poll(() => listHits, { timeout: 15_000 }).toBeGreaterThan(listBefore)
  })
})
