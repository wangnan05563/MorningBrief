import { test, expect } from '@playwright/test'
import { setLoginState, useMobileViewport } from './helpers/mock'

/**
 * 可见性感知的反馈队列（T02495 / FR-UX-301，来源建议 D78、A19、E1）
 *
 * 既有意图保留：页面隐藏时绝不向 DOM 插入提示（不激活最小化窗口）。
 * 新增语义：隐藏期间的普通提示 FIFO 入队（去重、上限 5 条、TTL 60s），
 * 恢复可见且 2s 恢复窗口结束后聚合补发 1 条；confirm/prompt 保持 reject 且绝不回放；
 * loading 不入队。
 *
 * 用 `window.__safeMessage`（仅 DEV 构建暴露）驱动队列语义，避免为了测试去伪造真实接口时序。
 */

const NAV_TIMEOUT = 30000
const RESTORE_MS = 2000

/** 可控的 document.hidden + .el-message DOM 插入计数 */
async function setupVisibility(page) {
  await page.addInitScript(() => {
    let hidden = false
    Object.defineProperty(document, 'hidden', { get: () => hidden, configurable: true })
    Object.defineProperty(document, 'visibilityState', {
      get: () => (hidden ? 'hidden' : 'visible'),
      configurable: true,
    })
    window.__setHidden = (v) => {
      hidden = v
      document.dispatchEvent(new Event('visibilitychange'))
    }
    // 记录提示节点（含聚合补发的 toast 与确认框）被插入 DOM 的次数
    window.__domHits = []
    const obs = new MutationObserver((records) => {
      for (const r of records) {
        for (const n of r.addedNodes) {
          const el = n.nodeType === 1 ? n : null
          if (!el) continue
          if (el.classList?.contains('el-message')) window.__domHits.push('message')
          if (el.classList?.contains('el-message-box__wrapper') || el.querySelector?.('.el-message-box')) {
            window.__domHits.push('box')
          }
        }
      }
    })
    document.addEventListener('DOMContentLoaded', () => obs.observe(document.body, { childList: true, subtree: true }))
  })
}

const hits = (page) => page.evaluate(() => window.__domHits.length)
const queueSize = (page) => page.evaluate(() => window.__safeMessage.size())
const queueTexts = (page) => page.evaluate(() => window.__safeMessage.texts())

test.describe('可见性感知的反馈队列', () => {
  test('隐藏期间零 DOM 插入，恢复后聚合补发一条', async ({ page }) => {
    await setupVisibility(page)
    await page.goto('/login')
    await expect(page.locator('#app')).toBeVisible({ timeout: NAV_TIMEOUT })

    await page.evaluate(() => window.__setHidden(true))
    await page.evaluate(() => {
      const q = window.__safeMessage
      q.push('error', '保存失败：后端返回 500')
      q.push('warning', '网络较慢')
      q.push('error', '保存失败：后端返回 500') // 同类型同文案 -> 去重
    })
    await page.waitForTimeout(300)

    // 原意图：隐藏期间不得有任何提示节点进入 DOM
    expect(await queueSize(page)).toBe(2)
    expect(await hits(page)).toBe(0)
    await expect(page.locator('.el-message')).toHaveCount(0)

    await page.evaluate(() => window.__setHidden(false))
    await page.waitForTimeout(RESTORE_MS + 700)

    // 聚合补发：1 条，取最严重文案 + 积压条数，不重复也不丢
    const toast = page.locator('.el-message')
    await expect(toast).toHaveCount(1)
    await expect(toast).toContainText('保存失败：后端返回 500')
    await expect(toast).toContainText('共积压 2 条')
    expect(await hits(page)).toBe(1)
    expect(await queueSize(page)).toBe(0)
  })

  test('去重与上限 5 条（FIFO 丢最旧）', async ({ page }) => {
    await setupVisibility(page)
    await page.goto('/login')
    await expect(page.locator('#app')).toBeVisible({ timeout: NAV_TIMEOUT })
    await page.evaluate(() => window.__setHidden(true))

    await page.evaluate(() => {
      const q = window.__safeMessage
      for (let i = 0; i < 7; i++) q.push('error', `错误 ${i}`)
      q.push('error', '错误 6') // 重复：不新增，只刷新时间戳
    })
    expect(await queueSize(page)).toBe(5)
    expect(await queueTexts(page)).toEqual(['错误 2', '错误 3', '错误 4', '错误 5', '错误 6'])
    expect(await hits(page)).toBe(0)
  })

  test('TTL 60s：过期提示不补发', async ({ page }) => {
    await setupVisibility(page)
    await page.goto('/login')
    await expect(page.locator('#app')).toBeVisible({ timeout: NAV_TIMEOUT })
    await page.evaluate(() => window.__setHidden(true))

    await page.evaluate(() => {
      window.__safeMessage.push('error', '很久以前的错误', Date.now() - 61000)
    })
    expect(await queueTexts(page)).toEqual(['很久以前的错误'])

    await page.evaluate(() => window.__setHidden(false))
    await page.waitForTimeout(RESTORE_MS + 700)
    await expect(page.locator('.el-message')).toHaveCount(0)
    expect(await hits(page)).toBe(0)
    expect(await queueSize(page)).toBe(0)
  })

  test('loading 不入队', async ({ page }) => {
    await setupVisibility(page)
    await page.goto('/login')
    await expect(page.locator('#app')).toBeVisible({ timeout: NAV_TIMEOUT })
    await page.evaluate(() => window.__setHidden(true))

    await page.evaluate(() => {
      window.__safeMessage.loading('正在加载列表')
      window.__safeMessage.push('info', '普通提示')
    })
    expect(await queueSize(page)).toBe(1)
    expect(await queueTexts(page)).toEqual(['普通提示'])
  })

  test('confirm/prompt 隐藏时 reject 且恢复后绝不回放', async ({ page }) => {
    const requests = []
    await setupVisibility(page)
    const ok = (data) => ({ code: 0, message: 'ok', data })
    const OFF = { enabled: false, reason: null, by: null, at: null }
    await page.route('**/admin/api/v1/m/maintenance-status**', (r) =>
      r.fulfill({ status: 200, json: ok(OFF) }),
    )
    await page.route('**/admin/api/v1/m/emergency/stop**', (r) => {
      requests.push(r.request().url())
      return r.fulfill({ status: 200, json: ok({ ...OFF, enabled: true, at: '2026-10-18T09:00:00' }) })
    })
    await setLoginState(page, 'admin')

    await useMobileViewport(page)
    await page.goto('/m/manage/alert')
    const stopBtn = page.getByRole('button', { name: '应急停服', exact: true })
    await expect(stopBtn).toBeVisible({ timeout: NAV_TIMEOUT })

    // 切后台后点高危按钮：prompt 被拦截为 reject（等价于用户取消），既无弹窗也不发请求
    await page.evaluate(() => window.__setHidden(true))
    await stopBtn.click()
    await page.waitForTimeout(400)
    await expect(page.locator('.el-message-box')).toHaveCount(0)
    expect(await hits(page)).toBe(0)
    expect(requests.length).toBe(0)

    // 切回前台：确认框不得回放（错过时机的二次确认会误导高危操作）
    await page.evaluate(() => window.__setHidden(false))
    await page.waitForTimeout(RESTORE_MS + 700)
    await expect(page.locator('.el-message-box')).toHaveCount(0)
    expect(requests.length).toBe(0)
    expect(await hits(page)).toBe(0)
  })
})
