import { test, expect } from '@playwright/test'
import {
  setLoginState,
  channelsListResponse,
  materialsListResponse,
  workflowDetailResponse,
  statsOverviewResponse,
  statsTrendResponse,
} from './helpers/mock'
import { statsMetricMeta } from './helpers/statsMeta'

/**
 * M5「指标单位与口径说错话」E2E（T02538）
 *
 * 单元测试钉源码写法，这份钉「用户真的看得见」：推算脚注、两种源计数的归属、
 * 帮助文档里的真实数字、以及素材库/工作流详情是否还像两个东西。
 * 每条都成对断言：新说法在 DOM 上，旧说法不在了。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

async function stubEverything(page) {
  await setLoginState(page, 'admin')
  await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  await page.route(`${API}/channels*`, (route) => route.fulfill({ json: channelsListResponse }))
  await page.route(`${API}/events/stream**`, (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
  )
}

test.describe('M5 指标口径必须说清楚', () => {

  test('D39：广告曝光卡片自带「推算」标签与脚注', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/stats/overview*`, (route) => route.fulfill({ json: statsOverviewResponse }))
    await page.route(`${API}/stats/trend*`, (route) => route.fulfill({ json: statsTrendResponse }))

    await page.goto('/stats')

    // 标签来自 meta：带「推算」两个字
    await expect(page.getByText('推算广告曝光(次)').first()).toBeVisible()
    // 脚注跟着数字走，写明算法和「不是真实埋点」
    const note = page.locator('.metric-note').filter({ hasText: '按每期 3 段推算' })
    await expect(note).toBeVisible()
    await expect(note).toContainText('不是真实曝光埋点')
    // 只有这一个指标有脚注，不能把所有卡片都塞一句
    await expect(page.locator('.metric-note')).toHaveCount(1)
  })

  test('D46：频道卡片写「本频道已配源」，并指向全局源页', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/stats/channel-health*`, (route) =>
      route.fulfill({
        json: ok({
          channels: [
            {
              channel_id: 1,
              name: '科技频道',
              is_active: 1,
              health_status: 'healthy',
              today_pending: 5,
              range_total: 21,
              rss_source_count: 3,
              keyword_count: 12,
              daily_trend: [
                { date: '2026-07-14', count: 2 },
                { date: '2026-07-15', count: 4 },
              ],
            },
          ],
          summary: { healthy: 1, warning: 0, critical: 0, total: 1 },
          meta: { count: statsMetricMeta.count },
        }),
      })
    )

    await page.goto('/stats/channel-health')

    const label = page.getByText('本频道已配源（个）')
    await expect(label).toBeVisible()
    await expect(page.getByText('RSS 源', { exact: true })).toHaveCount(0)
    // 悬停取口径：气泡必须指出去哪儿看全局可达性
    await label.hover()
    await expect(page.getByText(/全局源清单与可达性请看/).first()).toBeVisible()
  })

  test('D46：RSS 源页写「全局源清单总数」，并说明与频道卡片不必相等', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/stats/rss-health*`, (route) =>
      route.fulfill({
        json: ok({
          total: 9,
          ok: 8,
          fail: 1,
          unknown: 0,
          sources: [],
          started_at: '2026-07-15T08:00:00',
          pid: 4321,
          meta: { ...statsMetricMeta },
        }),
      })
    )

    await page.goto('/stats/rss-health')

    await expect(page.getByText('全局源清单总数').first()).toBeVisible()
    await expect(page.getByText('源总数', { exact: true })).toHaveCount(0)
    const scope = page.locator('[data-guide="rss-source-scope"]')
    await expect(scope).toContainText('rss.yaml')
    await expect(scope).toContainText('本频道已配源')
  })

  test('M81：帮助文档写的是 210 字/分与秒制，不再出现 330 WPM', async ({ page }) => {
    await stubEverything(page)

    await page.goto('/help')

    await expect(page.getByText(/基础语速是项目常量 210 字\/分/).first()).toBeVisible()
    await expect(page.getByText(/时长 60–1800 秒/).first()).toBeVisible()
    await expect(page.getByText(/应用到 AI 配置/).first()).toBeVisible()
    await expect(page.getByText(/330/)).toHaveCount(0)
    await expect(page.getByText(/WPM/)).toHaveCount(0)
    await expect(page.getByText(/语速调节建议/)).toHaveCount(0)
  })

  test('C114：素材库页与工作流详情同一套术语、字段与状态', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/materials*`, (route) => route.fulfill({ json: materialsListResponse }))
    await page.route(`${API}/workflows/wf-001/audio`, (route) => route.fulfill({ json: ok({ tts: [], episode: null }) }))
    await page.route(`${API}/workflows/wf-001`, (route) => route.fulfill({ json: workflowDetailResponse }))
    await page.route(`${API}/workflows*`, (route) => route.fulfill({ json: ok({ list: [], total: 0 }) }))

    // ---- 素材库管理页：状态筛选取自共享字典，跨页刷新有入口
    await page.goto('/channels/material-library')
    await expect(page.getByText('与工作流详情「爬虫采集 · 素材库」是同一份数据').first()).toBeVisible()
    await expect(page.getByRole('button', { name: '刷新' })).toBeVisible()
    await page.locator('.filter-form .el-select').nth(1).click()
    await expect(page.getByRole('option', { name: '待消费' })).toBeVisible()
    await expect(page.getByRole('option', { name: '待处理' })).toHaveCount(0)

    // ---- 工作流详情：同一个实体叫「素材库」，字段叫「分类」，URL 不再假必填
    await page.goto('/workflows/wf-001')
    await page.getByText('爬虫采集 · 素材库').click()
    await expect(page.getByText('爬虫采集 · 素材库')).toBeVisible()
    await expect(page.getByText('与菜单「素材库管理」同一份数据').first()).toBeVisible()
    await expect(page.locator('.el-table__header').getByText('分类').first()).toBeVisible()
    await expect(page.locator('.el-table__header').getByText('品类')).toHaveCount(0)

    // 新增素材：表单里没有 URL 字段（list 录入的 URL 由后端按正文哈希合成）
    await page.getByRole('button', { name: '新增素材' }).click()
    const dlg = page.locator('.el-dialog').filter({ hasText: '新增素材' })
    await expect(dlg).toBeVisible()
    await expect(dlg.locator('.el-form-item__label').filter({ hasText: 'URL' })).toHaveCount(0)

    // 只填标题/来源/正文就能提交，且请求体里不带 url
    const inputs = dlg.locator('input')
    await inputs.nth(0).fill('C114 新素材')
    await inputs.nth(1).fill('测试来源')
    await dlg.locator('textarea').fill('这是一段足够长的正文，用于验证新增素材不再要求填写 URL。')

    const [req] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('/admin/api/v1/materials') && r.method() === 'POST'),
      dlg.getByRole('button', { name: '保存' }).click(),
    ])
    const body = req.postDataJSON()
    expect(body.title).toBe('C114 新素材')
    expect(body).not.toHaveProperty('url')
    await expect(page.getByText('素材已新增')).toBeVisible()
  })
})
