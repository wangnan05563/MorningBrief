import { test, expect } from '@playwright/test'
import { setLoginState, useMobileViewport } from './helpers/mock'

/**
 * window-guard 丢弃的请求不得变成用户可见的「网络故障」（T02833）
 *
 * 背景（来源 T02520 取证）：页面切回前台后，移动端壳层在 visibilitychange 里立刻刷新角标，
 * 而 window-guard 的 2s 恢复保护期还没结束（_shouldBlockNetwork = hidden || _isRestoring），
 * 于是请求在 send 层被丢弃、axios 抛 `Network Error`；拦截器把它当真实网络故障弹提示，
 * 反馈队列再把它留到恢复窗口结束后补发——用户凭空看到一条自造的错误。
 *
 * 现在的语义：
 * - 恢复保护期内发起的请求**挂起**，保护期结束原样重发一次（不是失败，也不怕重复请求）；
 * - 页面隐藏期发起的请求仍然丢弃（后台不该发请求），但会打 __guardAborted 标记，
 *   拦截器据此静默收尾：不弹 toast、不进反馈队列，也不会在回前台后重放。
 */

const API = '**/admin/api/v1'
const NAV_TIMEOUT = 30000
const RESTORE_MS = 2000

/** 可控的 document.hidden + toast 文案记录（队列补发的 toast 也要算进来） */
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
    window.__toasts = []
    const obs = new MutationObserver((records) => {
      for (const r of records) {
        for (const n of r.addedNodes) {
          const el = n.nodeType === 1 ? n : null
          if (el?.classList?.contains('el-message')) {
            window.__toasts.push((el.textContent || '').trim())
          }
        }
      }
    })
    document.addEventListener('DOMContentLoaded', () =>
      obs.observe(document.body, { childList: true, subtree: true }),
    )
  })
}

/** 兜住壳层的其它接口，避免本机后端状态把断言变成环境探测 */
async function mockShell(page) {
  await page.route(`${API}/**`, (route) =>
    route.fulfill({
      json: { code: 0, message: 'success', data: { items: [], list: [], total: 0 } },
    }),
  )
  await page.route(`${API}/events/stream**`, (route) =>
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
    }),
  )
  await page.route(`${API}/m/maintenance-status**`, (route) =>
    route.fulfill({
      json: {
        code: 0,
        message: 'success',
        data: { enabled: false, reason: null, by: null, at: null },
      },
    }),
  )
}

const networkToasts = (page) =>
  page.evaluate(() =>
    window.__toasts.filter((t) => /Network Error|Failed to fetch|网络|请求失败/.test(t)),
  )

test.describe('window-guard 丢弃的请求与反馈队列', () => {
  test('恢复保护期内发起的刷新在就绪后重放，不弹 Network Error', async ({ page }) => {
    await setupVisibility(page)
    await mockShell(page)
    await useMobileViewport(page)
    await setLoginState(page, 'admin')

    let summaryCalls = 0
    await page.route(`${API}/m/dashboard-summary**`, (route) => {
      summaryCalls += 1
      return route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: { today: {}, pending_review: 0, unread_message: 1 },
        },
      })
    })

    await page.goto('/m/manage/alert')
    await expect(page.getByRole('button', { name: '应急停服', exact: true })).toBeVisible({
      timeout: NAV_TIMEOUT,
    })
    await expect.poll(() => summaryCalls).toBe(1)

    await page.evaluate(() => window.__setHidden(true))
    await page.waitForTimeout(300)
    await page.evaluate(() => window.__setHidden(false))

    // 恢复窗口内：请求已被挂起（尚未发出），且没有被当成失败塞进反馈队列
    await page.waitForTimeout(400)
    expect(summaryCalls).toBe(1)
    expect(await page.evaluate(() => window.__safeMessage.texts())).toEqual([])
    expect(await networkToasts(page)).toEqual([])

    // 保护期结束：挂起的刷新补发一次——数据真的刷新了，而不是被静默丢掉
    await expect.poll(() => summaryCalls, { timeout: RESTORE_MS + 4000 }).toBe(2)
    await page.waitForTimeout(600)
    expect(await page.evaluate(() => window.__safeMessage.size())).toBe(0)
    expect(await networkToasts(page)).toEqual([])
  })

  test('挂起期间页面再次隐藏：还没发出的动作作废，不会被补打', async ({ page }) => {
    await setupVisibility(page)
    await mockShell(page)
    await useMobileViewport(page)
    await setLoginState(page, 'admin')

    let markReadCalls = 0
    await page.route(`${API}/m/inbox**`, (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            total: 1,
            unread_count: 1,
            items: [
              {
                id: 1,
                read: false,
                level: 'info',
                msg_type: 'system',
                title: '测试消息',
                body: '内容',
                created_at: '2026-10-24T10:00:00',
              },
            ],
          },
        },
      }),
    )
    await page.route(`${API}/m/inbox/mark-read`, (route) => {
      markReadCalls += 1
      return route.fulfill({ json: { code: 0, message: 'success', data: null } })
    })

    await page.goto('/m/message')
    const markAll = page.getByRole('button', { name: '全部已读' })
    await expect(markAll).toBeVisible({ timeout: NAV_TIMEOUT })

    // 恢复保护期内点击：请求已 open 但被挂起，还没离开浏览器
    // 用 el.click() 而不是 Playwright 的 click()：后者要等操作稳定性，几秒过去保护期都结束了
    await page.evaluate(() => window.__setHidden(false))
    await markAll.evaluate((el) => el.click())
    await page.waitForTimeout(300)
    expect(markReadCalls).toBe(0)

    // 保护期没结束就又切后台 -> 挂起的提交必须作废：等下一次回前台才打出去，
    // 用户看到的是一个「几分钟前的动作」突然生效（陈旧提交）
    await page.evaluate(() => window.__setHidden(true))
    await page.waitForTimeout(300)
    await page.evaluate(() => window.__setHidden(false))
    await page.waitForTimeout(RESTORE_MS + 1200)

    expect(markReadCalls).toBe(0)
    expect(await page.evaluate(() => window.__safeMessage.size())).toBe(0)
    expect(await networkToasts(page)).toEqual([])
  })

  test('隐藏期发起的请求静默丢弃：不弹提示、不入队、回前台也不重放', async ({ page }) => {
    await setupVisibility(page)
    await mockShell(page)
    await useMobileViewport(page)
    await setLoginState(page, 'admin')

    let markReadCalls = 0
    await page.route(`${API}/m/inbox**`, (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            total: 1,
            unread_count: 1,
            items: [
              {
                id: 1,
                read: false,
                level: 'info',
                msg_type: 'system',
                title: '测试消息',
                body: '内容',
                created_at: '2026-10-24T10:00:00',
              },
            ],
          },
        },
      }),
    )
    await page.route(`${API}/m/inbox/mark-read`, (route) => {
      markReadCalls += 1
      return route.fulfill({ json: { code: 0, message: 'success', data: null } })
    })

    await page.goto('/m/message')
    const markAll = page.getByRole('button', { name: '全部已读' })
    await expect(markAll).toBeVisible({ timeout: NAV_TIMEOUT })

    await page.evaluate(() => window.__setHidden(true))
    await markAll.click()
    await page.waitForTimeout(400)

    // 请求在 send 层被丢弃：既没到后端，也没被当成网络故障入队
    expect(markReadCalls).toBe(0)
    expect(await page.evaluate(() => window.__safeMessage.texts())).toEqual([])

    await page.evaluate(() => window.__setHidden(false))
    await page.waitForTimeout(RESTORE_MS + 900)

    // 隐藏期请求不回放（否则回前台会打出一批陈旧请求，违背 NFR-UX-03），也不弹任何提示
    expect(markReadCalls).toBe(0)
    expect(await page.evaluate(() => window.__safeMessage.size())).toBe(0)
    expect(await networkToasts(page)).toEqual([])
  })
})
