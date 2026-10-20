import { test, expect } from '@playwright/test'
import { setLoginState, MOBILE_VIEWPORT } from './helpers/mock'

/**
 * 断言超时口径（实测踩坑，别照着旧 spec 抄）
 *
 * 全量并发跑（205 条 / 2 worker）时，本文件的「列表页首屏挂载」可能超过 Playwright 默认的 5s 断言超时
 * ——单独跑 9/9 全绿、全量跑却报 `element(s) not found`，而**失败快照里那个元素已经在页面上了**：
 * 断言窗口比挂载时间短，不是功能没做出来。
 *
 * ⚠ 仓库里二十来个 spec 写的 `test.use({ expect: { timeout: 30000 } })` 是**空选项**：
 * Playwright 1.61 的 TestOptions 里没有 `expect` 这一项（`node_modules/playwright/types/test.d.ts`
 * 查无 ExpectOptions），传进去被静默忽略，失败日志里仍然是 `Timeout: 5000ms`。
 * 所以这里用 `expect.configure({ timeout })` 派生一个本文件专用的断言器：实测（node 脚本计时）它
 * 只作用于派生对象，不会泄漏到全局默认（全局仍是 5s），也不影响同 worker 里的其他 spec。
 * 另注：把 `{ timeout }` 写在 `.toBe()/`.toHaveValue()` 上对 `expect.poll` **无效**（poll 的超时是
 * `expect.poll(fn, { timeout })` 的第二参），实测 1.2s 的显式超时仍按 5s 走完。空选项的存量清理已建派生单。
 */
const expectLong = expect.configure({ timeout: 30000 })

/**
 * 隐藏子页的层级与返回（T02512 / FR-UX-603，验收口径 ACC-UX-601#2「从详情返回列表保留原筛选」）
 *
 * 这一份要防的回归：详情页的「返回」把用户丢回列表的**默认视图**。
 * 此前两处返回各写死自己的口径——审核详情 `router.push('/review')`（回到待审核第 1 页），
 * 工作流详情 `router.back()`（后退只回到那个地址，可列表的筛选活在组件内存里，
 * 重新挂载即全部重置成「未筛选」）。两种写法都回不到「我来的那一页」。
 *
 * 修法是在进入详情时把来源地址挂到 `?from=`，返回按它走（`utils/urlState.js` 的 returnTarget）。
 * 规则本体（开放重定向拦截、嵌套 from 剥离、百分号编码容错）在 tests/unit/url-state.test.mjs 断言；
 * 这一层只验**用户可见结果**：面包屑在不在、上级能不能点、筛选与分页有没有真带回来、
 * 接口有没有真的按筛选参数发请求。
 *
 * 地址一律写成 `/news/…`：路由 base 是 `/news/`，dev 下由 Vite 挂在 `/`，
 * 裸路径会被解析成 `/`（与 tests/url-state.spec.js 同一口径）。
 */

const ok = (data) => ({ code: 0, message: 'success', data })

const reviewRows = {
  pending: { total: 2, list: [{ id: 1, episode_date: '2026-07-08', workflow_id: 'wf-001', status: 'pending', created_at: '2026-07-08T05:00:00' }] },
  // approved 故意做成「total=100、当前页只有 1 条」：page=2 既合法又能被分页控件证实
  approved: { total: 100, list: [{ id: 3, episode_date: '2026-07-06', workflow_id: 'wf-003', status: 'approved', created_at: '2026-07-06T05:00:00' }] },
  rejected: { total: 0, list: [] },
}

const workflowRows = [
  { id: 'wf-001', episode_date: '2026-07-08', source: 'cron', status: 'success', started_at: '2026-07-08T05:00:00', finished_at: '2026-07-08T05:30:00' },
  { id: 'wf-002', episode_date: '2026-07-07', source: 'manual', status: 'failed', started_at: '2026-07-07T05:00:00', finished_at: null },
  { id: 'wf-003', episode_date: '2026-07-06', source: 'cron', status: 'failed', started_at: '2026-07-06T05:00:00', finished_at: null },
]

const queueTasks = [
  { id: 41, episode_date: '2026-07-08', source: 'cron', status: 'success', channel_id: 1, channel_name: '科技前沿', priority: 5 },
]

/**
 * @param {object} opts.record 为 true 时把最后一次 /workflows 请求的 query 存到 opts.onListQuery，
 *   供「筛选真的跟着返回回来了」的断言（只看控件显示什么是不够的，接口参数才是用户看到的数据口径）
 */
async function mockApi(page, { onListQuery } = {}) {
  page.__lastWorkflowsQuery = null
  await page.route('**/admin/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path.endsWith('/events/stream')) {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
      })
    }
    if (path.endsWith('/reviews') && route.request().method() === 'GET') {
      // 作用域模式（移动端从队列「去审核」带 workflow_id 进来）刻意返回空列表：
      // 手机屏幕上「返回队列」只在作用域空态里出现，这正是 E12 那套「空态也要能回去」的入口
      if (url.searchParams.get('workflow_id')) {
        return route.fulfill({ json: ok({ total: 0, list: [], items: [] }) })
      }
      const status = url.searchParams.get('status') || 'pending'
      return route.fulfill({ json: ok(reviewRows[status] || { total: 0, list: [] }) })
    }
    if (/\/reviews\/\d+\/action$/.test(path)) {
      return route.fulfill({ json: ok({ id: 3, status: 'approved' }) })
    }
    if (/\/reviews\/\d+$/.test(path)) {
      return route.fulfill({
        json: ok({
          id: 3,
          episode_date: '2026-07-06',
          workflow_id: 'wf-003',
          status: 'approved',
          audio_url: '',
          images: [],
          script: { full_text: '<p>正文</p>', segments: [] },
        }),
      })
    }
    if (path.endsWith('/workflows/stats')) {
      return route.fulfill({ json: ok({ queued: 0, running: 0, success: 1, failed: 1 }) })
    }
    if (path.endsWith('/workflows') && route.request().method() === 'GET') {
      const q = Object.fromEntries(url.searchParams.entries())
      if (onListQuery) onListQuery(q)
      page.__lastWorkflowsQuery = q
      const filtered = workflowRows.filter((r) => {
        if (q.source && r.source !== q.source) return false
        if (q.status && r.status !== q.status) return false
        if (q.channel_id && String(r.channel_id ?? '') !== q.channel_id) return false
        if (q.episode_date && r.episode_date !== q.episode_date) return false
        return true
      })
      return route.fulfill({ json: ok({ total: filtered.length, list: filtered }) })
    }
    if (/\/workflows\/[\w-]+$/.test(path)) {
      return route.fulfill({
        json: ok({
          workflow_id: 'wf-001',
          episode_date: '2026-07-08',
          source: 'cron',
          status: 'success',
          started_at: '2026-07-08T05:00:00',
          finished_at: '2026-07-08T05:30:00',
          error: null,
          steps: [
            { name: 'crawl', status: 'success', started_at: '2026-07-08T05:00:00', finished_at: '2026-07-08T05:10:00', retry_count: 0, error: null },
          ],
        }),
      })
    }
    if (path.endsWith('/queue/tasks')) {
      // ⚠ 移动端队列页读的是 `data.items`（见 views/mobile/ManageQueue.vue 的 `d.items || []`），
      // 返回 `list` 会让它拿到空数组并渲染「队列为空」——列表根本没机会出现，
      // 「去审核」按钮的等待最后只会超时（实测踩过）。
      return route.fulfill({ json: ok({ total: queueTasks.length, items: queueTasks }) })
    }
    if (path.endsWith('/queue/stats')) {
      return route.fulfill({ json: ok({ queued: 0, running: 0, success: 1, failed: 0 }) })
    }
    if (path.endsWith('/channels') || path.endsWith('/channels/list')) {
      return route.fulfill({ json: ok([{ id: 1, name: '科技前沿', channel_type: 'news', enabled: true }]) })
    }
    if (path.endsWith('/messages') || path.endsWith('/m/dashboard-summary')) {
      return route.fulfill({ json: ok({ items: [], list: [], total: 0, today: 0, pending_review: 0, unread_message: 0 }) })
    }
    return route.fulfill({ json: ok({ items: [], list: [], total: 0 }) })
  })
}

/**
 * 筛选下拉的「显示值」定位。
 * ⚠ Element Plus 2.14 重构了 el-select：选中项的文案渲染在 `.el-select__placeholder` 文本节点里，
 * 那个 `<input class="el-select__input">` 只在 filterable 时承接输入，非可搜索单选框里它**恒为空**
 * （拿 `toHaveValue` 断言会永远读到 ""，误判成「URL 参数没灌回控件」）。
 * 因此这里按容器可见文本断言——用户看到的是什么，就断言什么。
 */
const selectBox = (page, index) => page.locator('.filter-bar .el-select').nth(index)

test.describe('PC 审核详情：层级可见 + 返回保留来源', () => {
  test.use({ viewport: { width: 1280, height: 720 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockApi(page)
  })

  test('从「已通过 第 2 页」进详情，面包屑点上级能原路返回', async ({ page }) => {
    await page.goto('/news/review?tab=approved&page=2')
    await expectLong(page.locator('.el-tabs__item.is-active')).toHaveText('已通过')
    await expectLong(page.locator('.el-pagination .is-active')).toHaveText('2')

    await page.getByRole('button', { name: '审核' }).first().click()
    await expectLong(page).toHaveURL(/\/news\/review\/3\?from=/)

    // 层级可见：上级是可点的「内容审核」，当前层是「审核详情」
    const crumbs = page.locator('[data-guide="page-breadcrumb"] .el-breadcrumb__inner')
    await expectLong(crumbs.nth(0)).toHaveText('内容审核')
    await expectLong(crumbs.nth(1)).toHaveText('审核详情')

    await page.locator('[data-guide="breadcrumb-parent"]').click()
    await expectLong(page).toHaveURL('/news/review?tab=approved&page=2')
    await expectLong(page.locator('.el-tabs__item.is-active')).toHaveText('已通过')
    await expectLong(page.locator('.el-pagination .is-active')).toHaveText('2')
  })

  test('详情页里提交「通过」后回到的仍是来源那一页，不是待审核第 1 页', async ({ page }) => {
    await page.goto('/news/review?tab=approved&page=2')
    await page.getByRole('button', { name: '审核' }).first().click()
    await expectLong(page.locator('[data-guide="page-breadcrumb"]')).toBeVisible()

    // 表单默认就是「通过」，直接提交并确认
    await page.getByRole('button', { name: '提交' }).click()
    await page.locator('.el-message-box__btns .el-button--primary').click()

    await expectLong(page).toHaveURL('/news/review?tab=approved&page=2')
    await expectLong(page.locator('.el-tabs__item.is-active')).toHaveText('已通过')
  })

  test('深链直接打开详情（没有 from）时返回兜到列表首页', async ({ page }) => {
    await page.goto('/news/review/3')
    await expectLong(page.locator('[data-guide="breadcrumb-current"]')).toHaveText('审核详情')
    await page.getByRole('button', { name: '返回列表' }).click()
    await expectLong(page).toHaveURL(/\/news\/review(\?|$)/)
    await expectLong(page.locator('.el-tabs__item.is-active')).toHaveText('待审核')
  })

  test('?from= 指向站外时不接受，返回仍留在站内', async ({ page }) => {
    await page.goto('/news/review/3?from=%2F%2Fevil.com%2Freview')
    await page.getByRole('button', { name: '返回列表' }).click()
    // 断言写成 `(\?|$)`：`/news/review/3?from=…` 里同样含有 `/news/review`，
    // 用宽松正则会在**根本没离开详情页**时通过（实测踩过——第一次就误报绿）。
    await expectLong(page).toHaveURL(/\/news\/review(\?|$)/)
    expect(page.url()).not.toContain('evil.com')
  })
})

test.describe('PC 工作流：筛选写进 URL，详情返回带回来源筛选', () => {
  test.use({ viewport: { width: 1280, height: 720 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockApi(page)
  })

  test('地址里的筛选会灌回控件并按参数请求', async ({ page }) => {
    await page.goto('/news/workflows?source=cron&status=success')
    // 0=频道 1=状态 2=来源（模板顺序；中间的日期选择器不是 .el-select，不占序号）
    await expectLong(selectBox(page, 2)).toContainText('定时')
    await expectLong(selectBox(page, 1)).toContainText('成功')
    await expectLong.poll(() => page.__lastWorkflowsQuery).toMatchObject({ source: 'cron', status: 'success' })
    await expectLong(page.locator('.el-table__row')).toHaveCount(1)
  })

  test('带筛选进详情后点「返回列表」，筛选与请求都恢复', async ({ page }) => {
    await page.goto('/news/workflows?source=cron&status=failed')
    await expectLong(page.locator('.el-table__row')).toHaveCount(1)

    await page.locator('.el-link', { hasText: 'wf-003' }).click()
    await expectLong(page).toHaveURL(/\/news\/workflows\/wf-003\?from=/)
    const crumbs = page.locator('[data-guide="page-breadcrumb"] .el-breadcrumb__inner')
    await expectLong(crumbs.nth(0)).toHaveText('工作流监控')
    await expectLong(crumbs.nth(1)).toHaveText('工作流详情')

    await page.getByRole('button', { name: '返回列表' }).click()
    await expectLong(page).toHaveURL('/news/workflows?source=cron&status=failed')
    await expectLong.poll(() => page.__lastWorkflowsQuery).toMatchObject({ source: 'cron', status: 'failed' })
    await expectLong(selectBox(page, 2)).toContainText('定时')
    await expectLong(page.locator('.el-table__row')).toHaveCount(1)
  })

  test('翻页/改页长会写进地址栏，非法枚举如实点名而不是按未筛选渲染', async ({ page }) => {
    await page.goto('/news/workflows?size=10&page=1&status=done')
    await expectLong(page.locator('[data-guide="workflows-url-corrected"]')).toBeVisible()
    await expectLong(page.locator('[data-guide="workflows-url-corrected"]')).toContainText('status')
    // 地址栏跟着收拾干净：非默认页长 size=10 留着（这是用户的选择），
    // 等于默认值的 page=1 与非法的 status=done 一起被省略——分享出去的就是当前视图
    await expectLong(page).toHaveURL('/news/workflows?size=10')
    // 非法值按「未筛选」请求，但绝不静默——用户看到的是被修正后的全量数据
    // ⚠ `expect.poll(...)` 返回的是断言对象而非 Promise，不能 `.then()`（那是 node assert 的写法）
    // 先确认真发生过请求（`__lastWorkflowsQuery` 初值是 null，直接断 status undefined 会在还没发请求时就空过）
    await expectLong.poll(() => page.__lastWorkflowsQuery).not.toBeNull()
    await expectLong.poll(() => page.__lastWorkflowsQuery?.status).toBeUndefined()
  })
})

test.describe('移动端：去审核与返回队列、二级页层级', () => {
  test.use({ viewport: MOBILE_VIEWPORT })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockApi(page)
  })

  test('队列「去审核」挂上来源，审核页「返回队列」按原路回', async ({ page }) => {
    await page.goto('/news/m/manage/queue')
    await page.getByRole('button', { name: '去审核' }).first().click()
    await expectLong(page).toHaveURL(/\/news\/m\/review\?.*from=%2Fm%2Fmanage%2Fqueue|\/news\/m\/review\?.*from=\/m\/manage\/queue/)

    await page.getByRole('button', { name: '返回队列' }).click()
    await expectLong(page).toHaveURL(/\/news\/m\/manage\/queue/)
  })

  test('管理二级页的返回键写明上级名称', async ({ page }) => {
    await page.goto('/news/m/manage/users')
    const back = page.locator('[data-guide="mobile-appbar-back"]')
    await expectLong(back).toBeVisible()
    await expectLong(back).toContainText('管理')
  })
})
