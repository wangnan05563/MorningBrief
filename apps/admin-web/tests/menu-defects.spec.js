import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 逐菜单缺陷消化（T02518 / FR-UX-704）
 *
 * 这一批的共同形状不是「功能坏了」，而是**界面说的话和实际做的不一致**——
 * 只有把弹窗点开、把开关拨一下才会暴露，纯走查又容易看漏，所以全部落成用户可见断言：
 *
 * - C15 新增频道：「启用」开关此前根本不在请求体里（后端 `ChannelCreateRequest` 也没有该字段），
 *   关掉开关创建出来仍是已启用频道，而提示只说「已创建」——新频道当天就被调度抓稿。
 * - C17 编辑频道：`_channel_to_dict` 漏 `icon_url`，弹窗每次打开都显示「无图标」，
 *   运营以为图标丢了去重复上传/重复 AI 生成（每次生成有成本）。
 * - C37 试听 BGM：URL 拼的是裸 `/bgm/…`，既不带 `/news` 前缀、dev 也没有代理条目 ⇒ 必然 404；
 *   同一问题在预制封面处（T00730）已修过，BGM 漏改。
 * - C18 AI 推荐：按钮点一下就落库，底部「取消」却写「放弃修改」——用户以为撤销了，其实没有。
 * - C27 素材池面板：`onToggleMode` 早已写好并接了 API，但没有任何控件绑定它（死代码），
 *   独立页 /channels/book-pool 根本没有模式开关可用。
 * - C80 预览下次生成：一次性 POST、结果常驻显示，此后排序/加入/移出都不让它失效。
 * - D45 频道健康度：各卡 mini 折线 Y 轴独立自适应且无刻度，形状相似的两条线可能相差百倍。
 * - I5 移动端审批：缺 PC 端早就有的「成品时长 / 凑时」信号，外勤会把凑时长的节目判为合格。
 *
 * 地址一律带 `/news` 前缀（路由 base 为 `/news/`，裸路径会被解析成 `/`），
 * 数据面全部走 route 拦截——**不碰真实库**（新增频道/切模式/批删都有真实副作用）。
 */

const tinyPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

/** 频道行：bgm_path/icon_url 都有值，才能验「回填」和「试听」两条路 */
function channelRow(overrides = {}) {
  return {
    id: 7,
    name: '讲书阁',
    description: '',
    channel_type: 'audiobook',
    type_label: '讲书稿',
    is_active: 1,
    display_order: 0,
    schedule_time: '04:00:00',
    rss_sources: '[]',
    book_rss_sources: '[]',
    keywords: '',
    bgm_path: 'prelude/news_01.mp3',
    bgm_volume: 0.3,
    segment_gap_sec: 1,
    bgm_gap_mode: 'silence',
    enable_thinking_question: 1,
    enable_ad: 1,
    selection_strategy: 'outline',
    material_lookback_days: null,
    min_duration_sec: null,
    cover_url: '',
    disclaimer_level: 'none',
    icon_url: '/channel-assets/channel_7_icon.png',
    created_at: '2026-10-01T09:00:00',
    updated_at: '2026-10-01T09:00:00',
    ...overrides,
  }
}

/**
 * @param {object} opts
 * @param {number} [opts.scriptEnabled] 素材池模式初始状态（影响开关断言起点）
 * @param {object[]} [opts.poolItems] 书单行
 */
async function mockApi(page, opts = {}) {
  const channels = [channelRow()]
  const calls = { create: null, update: null, scriptMode: null, schedule: null, reset: 0, removed: [] }
  const poolItems = opts.poolItems || [
    { id: 11, title: 'A 书', material_id: 101, enabled: true },
    { id: 12, title: 'B 书', material_id: 102, enabled: true },
  ]
  const scriptState = {
    enabled: opts.scriptEnabled === undefined ? false : !!opts.scriptEnabled,
    cursor: 1,
    pool_total: poolItems.length,
    interval_days: 1,
    loop: false,
    last_run_date: '2026-10-20',
    last_title: 'A 书',
    rss_sources: [],
    book_rss_sources: [],
  }

  const ok = (data) => ({ code: 0, message: 'success', data })
  const pick = (url) => url.pathname.replace(/^\/news\/admin\/api\/v1/, '')

  await page.route('**/admin/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const p = pick(url)

    if (p === '/channels' && route.request().method() === 'GET') {
      // 后端这里返回的就是数组本体（与 tests/helpers/mock.js 同口径）
      return route.fulfill({ json: ok(channels) })
    }
    if (p === '/channels' && route.request().method() === 'POST') {
      calls.create = JSON.parse(route.request().postData() || '{}')
      return route.fulfill({ json: ok(channelRow({ id: 88, name: calls.create.name, is_active: calls.create.is_active ?? 1, icon_url: null })) })
    }
    if (/^\/channels\/\d+$/.test(p) && route.request().method() === 'PUT') {
      calls.update = JSON.parse(route.request().postData() || '{}')
      return route.fulfill({ json: ok(channelRow({ ...calls.update })) })
    }
    if (/\/recommend-bgm$/.test(p)) {
      return route.fulfill({ json: ok({ path: 'prelude/ai_recommend.mp3', reason: '按频道调性推荐' }) })
    }
    if (/\/recommend-sources$/.test(p)) {
      return route.fulfill({ json: ok({ rss_sources: ['游民星空-资讯'], keywords: '游戏', reason: '略' }) })
    }
    if (p === '/channels/bgm/list') return route.fulfill({ json: ok({ items: [{ name: 'news_01.mp3', path: 'prelude/news_01.mp3' }] }) })
    if (p === '/channels/rss/sources') return route.fulfill({ json: ok({ items: ['游民星空-资讯', '三言科技'] }) })
    if (p === '/channels/book-rss/sources') return route.fulfill({ json: ok({ items: ['豆瓣读书-书评'] }) })
    if (p === '/channels/cover-presets') return route.fulfill({ json: ok({ items: [] }) })
    if (/\/script-mode$/.test(p) && route.request().method() === 'GET') return route.fulfill({ json: ok(scriptState) })
    if (/\/script-mode$/.test(p) && route.request().method() === 'PUT') {
      calls.scriptMode = JSON.parse(route.request().postData() || '{}')
      scriptState.enabled = !!calls.scriptMode.enabled
      return route.fulfill({ json: ok({ ...scriptState, changed: true, message: calls.scriptMode.enabled ? '已开启讲书稿模式' : '已关闭讲书稿模式' }) })
    }
    if (/\/script-mode\/schedule$/.test(p) && route.request().method() === 'PUT') {
      calls.schedule = JSON.parse(route.request().postData() || '{}')
      return route.fulfill({ json: ok({ ...scriptState, ...calls.schedule }) })
    }
    if (/\/book-pool\/candidates/.test(p)) return route.fulfill({ json: ok({ items: [] }) })
    if (/\/book-pool\/progress\/reset$/.test(p) && route.request().method() === 'POST') {
      calls.reset += 1
      scriptState.cursor = 0
      return route.fulfill({ json: ok({ ...scriptState }) })
    }
    if (/\/book-pool\/items\/\d+$/.test(p) && route.request().method() === 'DELETE') {
      calls.removed.push(p)
      const itemId = Number(p.split('/').pop())
      return route.fulfill({ json: ok({ items: poolItems.filter((i) => i.id !== itemId) }) })
    }
    if (p.endsWith('/book-pool') && route.request().method() === 'GET') {
      return route.fulfill({ json: ok({ items: poolItems, state: scriptState }) })
    }
    if (p.endsWith('/book-pool/pick-preview')) {
      return route.fulfill({ json: ok({ status: 'ok', item: { title: 'B 书' }, cursor: 1, total: poolItems.length }) })
    }
    if (p.endsWith('/reviews')) {
      return route.fulfill({
        json: ok({
          total: 1,
          list: [{
            id: 42,
            title: '主机游戏日报',
            episode_date: '2026-10-20',
            workflow_id: 'wf-42',
            channel_name: '主机游戏',
            channel_type: 'news',
            status: 'pending',
            content_preview: '今日摘要……',
            created_at: '2026-10-20T05:00:00',
            measured_duration_sec: 192,
            original_duration_sec: 172,
            supplement_sec: 20,
          }],
        }),
      })
    }
    if (p.endsWith('/events/stream')) {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
      })
    }
    return route.fulfill({ json: ok({ items: [], list: [], total: 0 }) })
  })

  // 图标/封面静态资源：给一张 1×1 PNG，让 el-image 走 success 分支而不是错误插槽
  await page.route('**/news/channel-assets/**', (route) =>
    route.fulfill({ status: 200, headers: { 'content-type': 'image/png' }, body: tinyPng }),
  )

  return { calls, scriptState }
}

const tab = (page, name) => page.locator('.el-tabs__item', { hasText: name }).first()
const dialog = (page) => page.locator('.el-dialog:visible').last()

test.describe('频道弹窗：启用开关、图标回填、BGM 试听、AI 推荐即时生效', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
  })

  test('C15 关掉「启用」新增频道，请求体必须带 is_active=0', async ({ page }) => {
    const { calls } = await mockApi(page)
    await page.goto('/news/channels')
    await page.getByRole('button', { name: '新增频道' }).click()
    const box = dialog(page)
    await box.locator('input[placeholder="请输入频道名称"]').fill('T02518 停用频道')
    // 「启用」开关在基础信息页签里；默认开，点一下变关
    await box.locator('.el-form-item:has-text("启用") .el-switch').click()
    await box.getByRole('button', { name: '确认' }).click()

    await expect.poll(() => calls.create?.name).toBe('T02518 停用频道')
    expect(calls.create.is_active).toBe(0)
  })

  test('C15 开关保持默认时仍创建为已启用（不影响既有行为）', async ({ page }) => {
    const { calls } = await mockApi(page)
    await page.goto('/news/channels')
    await page.getByRole('button', { name: '新增频道' }).click()
    const box = dialog(page)
    await box.locator('input[placeholder="请输入频道名称"]').fill('T02518 默认频道')
    await box.getByRole('button', { name: '确认' }).click()
    await expect.poll(() => calls.create?.name).toBe('T02518 默认频道')
    expect(calls.create.is_active).toBe(1)
  })

  test('C17 编辑弹窗按列表行的 icon_url 回填图标，不再显示「无图标」', async ({ page }) => {
    await mockApi(page)
    await page.goto('/news/channels')
    await page.getByRole('button', { name: '编辑' }).first().click()
    const box = dialog(page)
    await expect(box.locator('.icon-preview img')).toBeVisible()
    // 前缀约定：带 /news，生产 Funnel 才路由得到（与 T00730 的封面同一条约定）
    await expect(box.locator('.icon-preview img')).toHaveAttribute('src', /^\/news\/channel-assets\//)
    await expect(box.getByText('无图标')).toHaveCount(0)
  })

  test('C37 BGM 试听 URL 带 /news 前缀（裸 /bgm 在 dev 与生产都会 404）', async ({ page }) => {
    await mockApi(page)
    await page.goto('/news/channels')
    await page.getByRole('button', { name: '编辑' }).first().click()
    const box = dialog(page)
    await tab(box, '音频与 BGM').click()
    await box.getByRole('button', { name: '试听' }).click()
    await expect(box.locator('audio')).toHaveAttribute('src', /^\/news\/bgm\//)
  })

  test('C18 AI 推荐即时落库后：页脚写明「已即时生效」，取消时如实告知且不静默关闭', async ({ page }) => {
    await mockApi(page)
    await page.goto('/news/channels')
    await page.getByRole('button', { name: '编辑' }).first().click()
    const box = dialog(page)
    await tab(box, '音频与 BGM').click()

    await expect(box.locator('[data-guide="channel-immediate-saved"]')).toHaveCount(0)
    await box.getByRole('button', { name: 'AI 推荐' }).click()
    await expect(box.locator('[data-guide="channel-immediate-saved"]')).toContainText('已即时生效：BGM 配置')

    await box.getByRole('button', { name: '取消' }).click()
    const confirm = page.locator('.el-message-box')
    await expect(confirm).toBeVisible()
    await expect(confirm).toContainText('有配置已即时生效')
    await expect(confirm).toContainText('不会撤销')
    // 选「继续编辑」⇒ 弹窗必须还开着（此前点取消 = 直接关，用户以为撤销了）
    await confirm.getByRole('button', { name: '继续编辑' }).click()
    await expect(dialog(page)).toBeVisible()
  })
})

test.describe('讲书稿素材池面板：模式开关可用 + 预览失效', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
  })

  test('C27 面板内有可用的模式开关（此前 onToggleMode 是无人绑定的死代码）', async ({ page }) => {
    const { calls } = await mockApi(page, { scriptEnabled: false })
    await page.goto('/news/channels/book-pool?channelId=7')
    const sw = page.locator('[data-guide="book-pool-mode-switch"]')
    await expect(sw).toBeVisible()
    await sw.click()
    await expect.poll(() => calls.scriptMode).toEqual({ enabled: true })
  })

  test('C80 预览结果在改动调度参数后立即失效（不再常驻显示过期结论）', async ({ page }) => {
    await mockApi(page)
    await page.goto('/news/channels/book-pool?channelId=7')
    await page.getByRole('button', { name: '预览下次生成' }).click()
    await expect(page.locator('.book-pool-panel .el-alert').filter({ hasText: '下次将生成' })).toBeVisible()

    // 取书间隔 +1 ⇒ 「下次取哪本」的前提变了，旧预览必须消失
    // 用控件类名而非 EP 的 aria-label：后者随组件版本/语言包变化（本机为 "increase number"）
    await page.locator('.schedule-form .el-input-number').first().locator('.el-input-number__increase').click()
    await expect(page.locator('.book-pool-panel .el-alert').filter({ hasText: '下次将生成' })).toHaveCount(0)
  })

  test('C80 重新点预览会取当前状态，不受上次结果影响', async ({ page }) => {
    await mockApi(page)
    await page.goto('/news/channels/book-pool?channelId=7')
    const previewBtn = page.getByRole('button', { name: '预览下次生成' })
    await previewBtn.click()
    await expect(page.locator('.book-pool-panel .el-alert').filter({ hasText: '下次将生成：《B 书》' })).toBeVisible()
    // 移出《A 书》后预览失效，再点一次拿到新结果
    await page.getByRole('button', { name: '移出' }).first().click()
    await page.locator('.el-message-box').getByRole('button', { name: '确认移出' }).click()
    await expect(page.locator('.book-pool-panel .el-alert').filter({ hasText: '下次将生成' })).toHaveCount(0)
    await previewBtn.click()
    await expect(page.locator('.book-pool-panel .el-alert').filter({ hasText: '下次将生成：《B 书》' })).toBeVisible()
  })

  test('T02596 重置进度/移出书单：确认框写全影响面，取消不发请求', async ({ page }) => {
    const { calls } = await mockApi(page)
    await page.goto('/news/channels/book-pool?channelId=7')
    const box = page.locator('.el-message-box')

    await page.getByRole('button', { name: '重置进度' }).click()
    await expect(box).toBeVisible()
    await expect(box.getByText('重置书单进度：频道 ID 7 的讲书稿书单（共 2 本）')).toBeVisible()
    await expect(box.getByText('影响范围：取书进度 1 项（复位到书单第 1 本；书单与排序保留）')).toBeVisible()
    await expect(box.getByText(/重置后原来的取书位置不会保留/)).toBeVisible()
    await box.getByRole('button', { name: '取消' }).click()
    await expect(box).toBeHidden()
    expect(calls.reset).toBe(0)

    await page.getByRole('button', { name: '重置进度' }).click()
    await box.getByRole('button', { name: '确认重置' }).click()
    await expect.poll(() => calls.reset).toBe(1)

    const firstRow = page.locator('.book-pool-panel .el-table__row').first()
    await firstRow.getByRole('button', { name: '移出' }).click()
    await expect(box.getByText('移出书单：《A 书》')).toBeVisible()
    await expect(box.getByText('影响范围：书单条目 1 条（2 本 → 1 本）')).toBeVisible()
    await expect(box.getByText(/素材库中的素材不受影响/)).toBeVisible()
    await box.getByRole('button', { name: '取消' }).click()
    await expect(box).toBeHidden()
    expect(calls.removed).toHaveLength(0)

    await firstRow.getByRole('button', { name: '移出' }).click()
    await box.getByRole('button', { name: '确认移出' }).click()
    await expect.poll(() => calls.removed).toHaveLength(1)
    expect(calls.removed[0]).toMatch(/\/channels\/7\/book-pool\/items\/11$/)
  })
})

test.describe('频道健康度：卡片之间可比（D45）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
  })

  // 统一标尺的数字口径由 tests/channel-health.spec.js 覆盖；
  // 这里守的是「上限来自全体最大值」这一条：只看首卡峰值不足以发现各卡自适应的老问题
  test('D45 每张卡片显示本卡峰值，并共用全体上限', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/channel-health*', (route) =>
      route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            channels: [
              { channel_id: 1, name: '小流量', is_active: true, today_pending: 0, range_total: 3, rss_source_count: 1, keyword_count: 1, health_status: 'healthy', daily_trend: [{ date: '2026-07-20', count: 1 }, { date: '2026-07-21', count: 2 }] },
              { channel_id: 2, name: '大流量', is_active: true, today_pending: 0, range_total: 90, rss_source_count: 1, keyword_count: 1, health_status: 'healthy', daily_trend: [{ date: '2026-07-20', count: 90 }, { date: '2026-07-21', count: 1 }] },
            ],
            summary: { healthy: 2, warning: 0, critical: 0, total: 2 },
          },
        },
      }),
    )
    await page.goto('/news/stats/channel-health')
    const caps = page.locator('[data-guide="channel-health-trend-caption"]')
    await expect(caps.first()).toContainText('峰值 2 条', { timeout: 30000 })
    await expect(caps.first()).toContainText('上限 90 条')
    await expect(caps.nth(1)).toContainText('峰值 90 条')
    await expect(caps.nth(1)).toContainText('上限 90 条')
  })
})

test.describe('移动端审批卡片：时长与凑时信号（I5）', () => {
  test.use({ viewport: { width: 375, height: 667 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
  })

  test('卡片直接显示「成品时长」与「凑时」，与 PC 同口径', async ({ page }) => {
    await mockApi(page)
    await page.goto('/news/m/review')
    const meta = page.locator('.m-review__meta').first()
    await expect(meta).toContainText('成品 3 分 12 秒', { timeout: 30000 })
    await expect(meta.locator('[data-guide="m-review-supplement"]')).toContainText('凑时 20s')
  })

  test('无凑时的条目不显示凑时标记（避免每条都挂着警告色）', async ({ page }) => {
    await mockApi(page)
    await page.route('**/admin/api/v1/reviews*', (route) => {
      const url = new URL(route.request().url())
      if (url.pathname.endsWith('/reviews')) {
        return route.fulfill({
          json: {
            code: 0, message: 'success',
            data: { total: 1, list: [{ id: 43, title: '正常条目', status: 'pending', channel_type: 'news', content_preview: 'x', measured_duration_sec: 45, supplement_sec: 0, created_at: '2026-10-20T05:00:00' }] },
          },
        })
      }
      return route.continue()
    })
    await page.goto('/news/m/review')
    await expect(page.locator('.m-review__meta').first()).toContainText('成品 45 秒', { timeout: 30000 })
    await expect(page.locator('[data-guide="m-review-supplement"]')).toHaveCount(0)
  })

  test('展开详情写明凑时口径（成品含 BGM/静音，内容实测另计）', async ({ page }) => {
    await mockApi(page)
    await page.route('**/admin/api/v1/reviews/42*', (route) =>
      route.fulfill({
        json: { code: 0, message: 'success', data: { id: 42, episode_date: '2026-10-20', created_at: '2026-10-20T05:00:00', script: { full_text: '正文' } } },
      }),
    )
    await page.goto('/news/m/review')
    await page.locator('.m-review__title').first().click()
    const note = page.locator('[data-guide="m-review-duration-note"]')
    await expect(note).toContainText('含 20s BGM/静音', { timeout: 30000 })
    await expect(note).toContainText('内容实测 2 分 52 秒')
  })
})
