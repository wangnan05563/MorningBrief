import { test, expect } from '@playwright/test'
import {
  setLoginState,
  queueStatsResponse,
  queueConfigResponse,
  queueTasksResponse,
  channelsListResponse,
  workflowListResponse,
} from './helpers/mock'

/**
 * NFR-UX-03「新增错误态/重试不引入额外轮询 + 列表分页尺寸上限 100」E2E（T02521）
 *
 * PRD 要求的是「手测 + 网络面板验证」。网络面板在这里用 `page.on('request')` 做成可编程版本：
 * 只统计真正发往后台的业务请求，剔除 SSE 长连接（`/events/stream` 是常驻连接，不是轮询）。
 *
 * 为什么是「稳态请求数对比」而不是「绝对不许有请求」：
 * 队列页与工作流列表**本来就有兜底轮询**（QueueManagement 5s/30s、WorkflowList 有活跃任务时 5s），
 * 那是 NFR-UX-03 之前存在的能力，本单不打算动它。要抓的是「**新增**的错误态/重试按钮额外带来了请求」。
 * 所以两臂只差在列表接口成不成功，比较同一个窗口内的请求数：
 * 失败态不得比健康态发出更多请求（失败态反而更安静是可接受的）。
 *
 * 与已有用例的分工：
 * - `feed-capabilities.spec.js:163` 已验 ReviewList 失败态 4s 内不自发重试；
 *   这一份把它扩到队列/工作流/频道三页、窗口拉长到 8s（必须 > 5s 轮询周期，否则永远测不到轮询），
 *   并新增「点一次重试恰好发几次」的预算断言——重试按钮最容易变成「顺手多发几个请求」。
 * - `list-error-state.spec.js` 验错误态**出现**，本单验它**不发**。
 *
 * 数据面全部 route 拦截，不发真实请求。
 */

const API = '/admin/api/v1/'
const SSE = '/events/stream'
/** 观测窗口：必须大于最密的 5s 轮询周期，否则健康态的轮询落不进来，比较就失去意义 */
const WINDOW_MS = 8000
/** 点重试后的观察时长：足够一次请求往返，又短于任何轮询周期 */
const RETRY_MS = 1500

function watchRequests(page) {
  // 统计口径：除 SSE 长连接之外、打到后台的所有请求都算，包含外壳级的
  // `/about/check-update` 自动更新定时器（实测每页都会跑到窗口里）。它**故意不剔除**：
  // 两臂都有它，属于共模信号；真把它剔了，「错误态顺手触发了更新检查」这类回归就看不见了。
  const log = []
  page.on('request', (req) => {
    const url = req.url()
    if (!url.includes(API) || url.includes(SSE)) return
    log.push({ url, size: new URL(url).searchParams.get('size') })
  })
  return log
}

async function steadyState(page, log, ms) {
  const before = log.length
  await page.waitForTimeout(ms)
  return log.slice(before)
}

/** 打一条 SSE 空流：后端没起时 ECONNREFUSED 会让用例 flaky */
const stubSse = (page) =>
  page.route(`**${API}${'events/stream**'}`, (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }),
  )

test.describe('错误态与重试不引入额外轮询（NFR-UX-03）', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s；本组用例本身就要跑 8s 窗口
  test.use({ expect: { timeout: 30000 } })

  /**
   * @param {object} cfg
   * @param {string} cfg.url             页面地址
   * @param {string} cfg.listPattern     列表接口的 route pattern（失败态由它打断）
   * @param {object} cfg.listJson        列表接口的成功夹具
   * @param {string} cfg.readySelector   健康态「首屏数据已渲染」的选择器
   * @param {string} cfg.emptySelector   失败态不得出现的空态文案选择器
   * @param {number} cfg.retryBudget     点一次重试**最多**发几个请求
   * @param {number} [cfg.minHealthy]    健康态窗口内**至少**该有几个请求
   */
  async function measurePage(page, cfg) {
    await setLoginState(page, 'admin')
    await stubSse(page)
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    if (cfg.extraRoutes) await cfg.extraRoutes(page)
    await page.route(cfg.listPattern, (route) => route.fulfill({ json: cfg.listJson }))

    const log = watchRequests(page)

    // ---- 健康态 ----
    await page.goto(cfg.url)
    await expect(page.locator(cfg.readySelector).first()).toBeVisible({ timeout: 30000 })
    const healthy = await steadyState(page, log, WINDOW_MS)
    // 「窗口看得见轮询」自检：队列页与工作流列表在有活跃任务时是 5s 轮询，
    // 8s 窗口必须至少捞到一次。捞不到说明观测本身失效，后面的 E<=H 就会变成
    // 「0 <= 0」的空断言——这是本组用例唯一能证明自己不是在自我安慰的地方。
    if (cfg.minHealthy !== undefined) {
      expect(
        healthy.length,
        `健康态窗口只发了 ${healthy.length} 个请求，观测失效：` +
          `${JSON.stringify(healthy.slice(0, 8).map((r) => r.url.replace(/^.*\/admin\/api\/v1/, '')))}`,
      ).toBeGreaterThanOrEqual(
        cfg.minHealthy,
      )
    }

    // ---- 失败态：把列表接口换成 abort（后注册优先），重载页面 ----
    await page.route(cfg.listPattern, (route) => route.abort())
    await page.reload()
    const banner = page.locator('.list-load-error')
    await expect(banner).toBeVisible({ timeout: 30000 })
    if (cfg.emptySelector) await expect(page.locator(cfg.emptySelector)).toHaveCount(0)
    const failed = await steadyState(page, log, WINDOW_MS)

    expect(
      failed.length,
      `失败态 8s 内发了 ${failed.length} 个请求，健康态只有 ${healthy.length} 个：` +
        `${JSON.stringify(failed.slice(0, 8).map((r) => r.url.replace(/^.*\/admin\/api\/v1/, '')))}`,
    ).toBeLessThanOrEqual(healthy.length)

    // ---- 重试：一次点击的预算 ----
    const before = log.length
    await banner.getByRole('button', { name: '重试', exact: true }).click()
    await page.waitForTimeout(RETRY_MS)
    const clicked = log.slice(before)
    // 至少 1（真的重发了），至多 retryBudget（不许顺手多发）
    expect(clicked.length).toBeGreaterThanOrEqual(1)
    expect(clicked.length).toBeLessThanOrEqual(cfg.retryBudget)
    return { healthy, failed, clicked }
  }

  test('队列页：失败态静默、重试只发一次任务查询', async ({ page }) => {
    await measurePage(page, {
      url: '/queue',
      listPattern: '**/admin/api/v1/queue/tasks*',
      listJson: queueTasksResponse,
      extraRoutes: (p) =>
        Promise.all([
          p.route('**/admin/api/v1/queue/stats', (r) => r.fulfill({ json: queueStatsResponse })),
          p.route('**/admin/api/v1/queue/config', (r) => r.fulfill({ json: queueConfigResponse })),
        ]),
      readySelector: '.el-table__row',
      emptySelector: 'text=暂无队列任务',
      // loadTasks 只打 /queue/tasks 一个接口
      retryBudget: 1,
      // T02837 修复后：首轮数据落定再排定时器，活跃队列在 8s 窗口里会出现一次 5s 轮询。
      // 这里仍不设 minHealthy——本计数含壳层请求，无法证明「轮询真的发生」；
      // 队列页的 5s/30s 节奏由 queue-polling-cadence.spec.js 直接盯 /queue/tasks 证明。
    })
  })

  test('工作流列表：失败态静默、重试只发一次列表查询', async ({ page }) => {
    await measurePage(page, {
      url: '/workflows',
      listPattern: '**/admin/api/v1/workflows*',
      listJson: workflowListResponse,
      readySelector: '.el-table__row',
      emptySelector: 'text=暂无工作流',
      retryBudget: 1,
      // workflowListResponse 里有 running → 5s 轮询一次（silent loadList 只打 /workflows）
      minHealthy: 1,
    })
  })

  test('频道管理：失败态静默、重试只发一次频道查询', async ({ page }) => {
    await measurePage(page, {
      url: '/channels',
      listPattern: '**/admin/api/v1/channels*',
      listJson: channelsListResponse,
      readySelector: '.el-table__row',
      emptySelector: 'text=暂无频道',
      retryBudget: 1,
      // 频道页没有基线轮询：健康态窗口本就是 0，所以这一页的 E<=H 是「失败态必须也是 0」，
      // 比前两页更严——不设 minHealthy 自检，因为这里 0 才是正确的观测结果。
    })
  })
})

test.describe('深链分页尺寸不得超过上限 100（NFR-UX-03）', () => {
  test.use({ expect: { timeout: 30000 } })

  /** 把 /workflows 的 size 记进数组，返回「所有实际发出去的 size」 */
  async function mockWorkflows(page) {
    const sizes = []
    await setLoginState(page, 'admin')
    await stubSse(page)
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    await page.route('**/admin/api/v1/workflows*', (route) => {
      const url = new URL(route.request().url())
      sizes.push(Number(url.searchParams.get('size')))
      const size = Number(url.searchParams.get('size') || 20)
      const rows = Array.from({ length: Math.min(size, 5) }, (_, i) => ({
        id: `wf-00${i + 1}`,
        episode_date: '2026-07-08',
        source: 'cron',
        status: 'success',
        started_at: '2026-07-08T05:00:00',
        finished_at: '2026-07-08T05:30:00',
      }))
      route.fulfill({ json: { code: 0, message: 'success', data: { total: 100, list: rows } } })
    })
    return sizes
  }

  const sentSizes = async (sizes) => {
    await test.expect
      .poll(() => sizes.length, { timeout: 30000 })
      .toBeGreaterThan(0)
    return sizes
  }

  test('WorkflowList：?size=999 钳到档位内并页内点名，绝不把 999 发给后端', async ({ page }) => {
    const sizes = await mockWorkflows(page)
    await page.goto('/workflows?size=999')
    await sentSizes(sizes)
    // 上限 100，且必须是选择器里存在的档位
    expect(Math.max(...sizes)).toBeLessThanOrEqual(100)
    expect(sizes.every((s) => [10, 20, 50, 100].includes(s))).toBe(true)
    await expect(page.locator('[data-guide="workflows-url-corrected"]')).toContainText('size=999')
    await expect.poll(() => new URL(page.url()).searchParams.get('size')).toBe('100')
  })

  test('WorkflowList：?size=7 落到最近档位（表格不能渲染出选择器里没有的行数）', async ({ page }) => {
    const sizes = await mockWorkflows(page)
    await page.goto('/workflows?size=7')
    await sentSizes(sizes)
    expect(sizes.every((s) => [10, 20, 50, 100].includes(s))).toBe(true)
    await expect.poll(() => new URL(page.url()).searchParams.get('size')).toBe('10')
  })

  test('WorkflowList：档位选择器提供 100 这一档（与 ReviewList 同一份 PAGE_SIZE_OPTIONS）', async ({ page }) => {
    await mockWorkflows(page)
    await page.goto('/workflows')
    const sizesLabel = page.locator('.pagination .el-pagination__sizes')
    await expect(sizesLabel).toContainText(/\b20\b/)
    await sizesLabel.locator('.el-select').click()
    const items = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    await expect(items).toHaveCount(4)
    const text = await items.allInnerTexts()
    expect(text.join('|')).toMatch(/\b100\b/)
  })

  test('深链 ?page=999 落在最后一页，而不是「一页一次请求」往回退到第 1 页', async ({ page }) => {
    // loadList 里那段「当前页空了就 page-1 再来一次」的递归，在深链指向一个不存在的页时
    // 会变成 999 次串行请求——正好是 NFR-UX-03 要拦的那类「额外请求」。
    // 夹具：总共只有 100 条（每页 20 → 5 页），第 6 页起一律返回空列表。
    const pages = []
    await setLoginState(page, 'admin')
    await stubSse(page)
    await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
    await page.route('**/admin/api/v1/workflows*', (route) => {
      const url = new URL(route.request().url())
      const pageNo = Number(url.searchParams.get('page') || 1)
      pages.push(pageNo)
      const list =
        pageNo <= 5
          ? Array.from({ length: 20 }, (_, i) => ({
              id: `wf-p${pageNo}-${i}`,
              episode_date: '2026-07-08',
              source: 'cron',
              status: 'success',
              started_at: '2026-07-08T05:00:00',
              finished_at: '2026-07-08T05:30:00',
            }))
          : []
      route.fulfill({ json: { code: 0, message: 'success', data: { total: 100, list } } })
    })

    await page.goto('/workflows?page=999')
    await test.expect
      .poll(() => pages.length, { timeout: 30000 })
      .toBeGreaterThan(0)
    await page.waitForTimeout(1500)

    expect(pages.length, `深链越界页码发了 ${pages.length} 个请求，页码序列=${JSON.stringify(pages)}`).toBeLessThanOrEqual(
      2,
    )
    // 落点是最后一页（5），不是第 1 页：回到头部会让用户以为数据变少了
    await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('5')
    await expect(page.locator('[data-guide="workflows-url-corrected"]')).toContainText('page=999')
  })
})
