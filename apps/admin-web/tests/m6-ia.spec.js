import { test, expect } from '@playwright/test'
import {
  setLoginState,
  reviewDetailResponse,
  adPlacementsListResponse,
  queueStatsResponse,
  workflowDetailResponse,
  workflowAudioResponse,
  channelsListResponse,
  materialsListResponse,
  useMobileViewport,
} from './helpers/mock'

/**
 * M6「信息架构与深链」E2E（T02540）
 *
 * 每条都断言「用户真的看见 / 地址栏真的变了」：
 *  - B12 试听走鉴权代理，失败时给出原因与重试（不再黑着）；
 *  - D13 投放列表能按状态筛选，且请求参数真的带 enabled；
 *  - I19 审批提醒点击后直达作用域审核页；
 *  - I48 「去审核」使用 workflow_id（不是队列编号）；
 *  - M88 帮助搜索命中正文关键词；
 *  - E12 直接打开详情深链，点返回落到列表而不是无反应。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })
const EMPTY_WAV =
  'UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA='

/**
 * 兜底路由必须先注册：Playwright 后注册的处理器优先匹配，
 * 先挂 `**` 再挂具体接口，具体断言才能拿到真实结构（反过来会被兜底吞掉）。
 */
async function stubFallback(page) {
  await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
}

test.describe('M6 信息架构与深链', () => {

  test('B12：试听经代理加载，403 时说明原因并可重试', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubFallback(page)
    const proxyCalls = []
    await page.route(`${API}/workflows/wf-001/audio/proxy**`, async (route) => {
      proxyCalls.push(route.request().url())
      if (proxyCalls.length === 1) {
        await route.fulfill({
          status: 403,
          contentType: 'application/json',
          body: JSON.stringify({ code: 403, message: '代理拒绝访问（私有桶）' }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'audio/wav',
        body: Buffer.from(EMPTY_WAV, 'base64'),
      })
    })
    await page.route(`${API}/reviews/1`, (route) => route.fulfill({ json: reviewDetailResponse }))

    await page.goto('/review/1')

    const alert = page.locator('[data-guide="review-audio-error"]')
    await expect(alert).toBeVisible({ timeout: 30000 })
    // 原因与出处都要说清：直连私有桶会被拒绝，必须经后端代理
    await expect(alert).toContainText('私有桶/COS')
    expect(proxyCalls[0]).toContain('/workflows/wf-001/audio/proxy')
    expect(proxyCalls[0]).toContain('url=')

    await page.getByRole('button', { name: '重试加载' }).click()
    await expect(page.locator('audio.audio-player')).toBeVisible({ timeout: 30000 })
    await expect(alert).toBeHidden()
    expect(proxyCalls).toHaveLength(2)
  })

  test('D13：按「仅停用」筛选时请求带 enabled=0，行上写明已停用', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubFallback(page)
    const listUrls = []
    await page.route(`${API}/ads/placements**`, async (route) => {
      if (route.request().method() !== 'GET') return route.fulfill({ json: ok({}) })
      const url = new URL(route.request().url())
      listUrls.push(url)
      const enabled = url.searchParams.get('enabled')
      const all = adPlacementsListResponse.data.list
      const list = enabled === null || enabled === '' ? all : all.filter((p) => String(p.enabled ?? 1) === enabled)
      await route.fulfill({ json: ok({ list, total: list.length }) })
    })

    await page.goto('/ads/placements')
    await expect(page.locator('.el-table__row').first()).toBeVisible()

    await page.locator('[data-guide="ads-enabled-filter"]').click()
    await page.getByRole('option', { name: '仅停用' }).click()

    await expect.poll(() => listUrls.at(-1)?.searchParams.get('enabled')).toBe('0')
    await expect(page.getByRole('row').filter({ hasText: '已停用' }).first()).toBeVisible()
  })

  test('I19：审批提醒点击后直达带 workflow_id 的审核页', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubFallback(page)
    // 移动端页面必须在手机视口下测：桌面视口会被 T02511 跨端守卫换到 PC 同名页
    await useMobileViewport(page)
    await page.route(`${API}/m/inbox**`, async (route) => {
      if (route.request().method() === 'POST') return route.fulfill({ json: ok(null) })
      await route.fulfill({
        json: ok({
          items: [
            {
              id: 11,
              msg_type: 'review',
              title: '有 1 条内容待审批',
              body: '请及时处理',
              level: 'warning',
              read: false,
              created_at: '2026-07-08T09:00:00',
              payload: { workflow_id: 'wf-9' },
            },
          ],
          total: 1,
          unread_count: 1,
        }),
      })
    })

    await page.goto('/m/message')
    await expect(page.getByText('有 1 条内容待审批')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.m-msg__go').first()).toBeVisible()

    await page.locator('.m-msg__item').first().click()
    await expect.poll(() => new URL(page.url()).searchParams.get('workflow_id')).toBe('wf-9')
    expect(new URL(page.url()).pathname).toBe('/news/m/review')
  })

  test('I48：「去审核」携带 workflow_id 而不是队列编号', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubFallback(page)
    await useMobileViewport(page)
    await page.route(`${API}/queue/stats`, (route) => route.fulfill({ json: queueStatsResponse }))
    await page.route(`${API}/queue/tasks**`, (route) =>
      route.fulfill({
        json: ok({
          total: 1,
          items: [
            {
              id: 'task-20260708-0001',
              workflow_id: 'wf-42',
              episode_date: '2026-07-08',
              source: 'cron',
              status: 'queued',
              channel_id: 1,
              channel_name: '科技频道',
              priority: 8,
              started_at: '2026-07-08T05:00:00',
              finished_at: null,
              error: null,
            },
          ],
        }),
      })
    )

    await page.goto('/m/manage/queue')
    await expect(page.getByText('task-20260708-0001')).toBeVisible({ timeout: 30000 })

    await page.getByRole('button', { name: '去审核' }).click()
    await expect.poll(() => new URL(page.url()).searchParams.get('workflow_id')).toBe('wf-42')
    expect(new URL(page.url()).searchParams.get('workflow_id')).not.toBe('task-20260708-0001')
  })

  test('M88：搜索正文里的 IMPORT 能命中数据库维护章节', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubFallback(page)

    await page.goto('/help')
    const search = page.getByPlaceholder('搜索章节...')
    await expect(search).toBeVisible({ timeout: 30000 })

    // IMPORT 只出现在「数据库维护」正文（不在任何标题/简介里），命中即证明搜的是全文
    await search.fill('IMPORT')
    await expect(page.locator('.anchor-item').filter({ hasText: '数据库维护' })).toBeVisible()
    await expect(page.getByText('IMPORT', { exact: false }).first()).toBeVisible()
  })

  test('E12：直接打开详情深链后，「返回列表」落到工作流列表', async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubFallback(page)
    await page.route(`${API}/events/stream**`, (route) =>
      route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
    )
    await page.route(`${API}/channels**`, (route) => route.fulfill({ json: channelsListResponse }))
    await page.route(`${API}/materials**`, (route) => route.fulfill({ json: materialsListResponse }))
    await page.route(`${API}/workflows/wf-001/audio`, (route) => route.fulfill({ json: workflowAudioResponse }))
    await page.route(`${API}/workflows/wf-001`, (route) => route.fulfill({ json: workflowDetailResponse }))

    // 直接深链进入：没有站内历史栈
    await page.goto('/workflows/wf-001')
    await expect(page.getByText('wf-001').first()).toBeVisible({ timeout: 30000 })

    await page.getByRole('button', { name: '返回列表' }).click()
    await expect.poll(() => new URL(page.url()).pathname).toBe('/news/workflows')
  })
})
