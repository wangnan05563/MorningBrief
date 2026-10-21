import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 列表能力落地 E2E（T02517 / FR-UX-703：分页尺寸选择、筛选持久化、批量选择、移动端分页）
 *
 * 与 tests/unit/list-capabilities.test.mjs 的分工：
 * - 单测那份是**静态门禁**（枚举所有 .vue 断言 layout 里有 sizes、档位不超 100、:limit 配 :on-exceed），
 *   它能防「新页面忘了接」，但防不住「属性写了却没绑到状态上」；
 * - 这一份验的是**跑起来真的生效**：选档位后请求参数是否真的变了、刷新后是否真的回填、
 *   勾选后批删请求体是否真的是勾的那些 id、加载更多是否真的取第 2 页。
 * 两层缺一不可——历史缺陷（WorkflowDetail 面板写死 20、Message 只取首页 20 条）都是
 * 「模板看着没问题、状态却没接上」，只有浏览器实测能抓。
 *
 * 数据面全部 route 拦截成夹具，**不发真实请求**：批删是硬删除，绝不能在用户真实库上试。
 * 覆盖 PRD 取证点：B3（审核列表无 sizes 档）、B4（workflow_id 筛选）、B6（列表失败静默落空态）、
 * C52（素材库无勾选批删）、I21（移动端消息只取首页）。
 */

const stubSse = (page) =>
  page.route('**/admin/api/v1/events/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }),
  )

/** 审核夹具：每个状态 100+ 条，保证「有第 2 页」「换档位后总页数变化」都可观察 */
function reviewRows(n, status) {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    episode_date: '2026-07-08',
    workflow_id: `wf-${String(i + 1).padStart(3, '0')}`,
    status,
    created_at: '2026-07-08T05:00:00',
  }))
}

const ok = (data) => ({ code: 0, message: 'success', data })

/**
 * 审核列表 mock：把 size 记进夹具返回值（list 长度按 size 切），
 * 这样「档位真的进了请求参数」可以被断言成「页面渲染的行数 = 请求的 size」。
 */
async function mockReviews(page, { failFirst = false } = {}) {
  const calls = []
  let first = true
  await page.route('**/admin/api/v1/reviews**', (route) => {
    const url = new URL(route.request().url())
    const size = Number(url.searchParams.get('size') || 10)
    const pageNo = Number(url.searchParams.get('page') || 1)
    const workflowId = url.searchParams.get('workflow_id')
    calls.push({ size, page: pageNo, workflow_id: workflowId })
    if (failFirst && first) {
      first = false
      return route.abort()
    }
    const all = reviewRows(size + 1, 'pending')
    const list = all.slice((pageNo - 1) * size, pageNo * size)
    return route.fulfill({ json: ok({ total: 100, list }) })
  })
  await page.route('**/admin/api/v1/channels**', (route) =>
    route.fulfill({ json: ok([{ id: 1, name: '科技前沿', channel_type: 'news', enabled: true }]) }),
  )
  await page.route('**/admin/api/v1/auto-review/config**', (route) =>
    route.fulfill({ json: ok({ enabled: false }) }),
  )
  return calls
}

const reviewTableRows = (page) => page.locator('[data-guide="review-table"] tbody tr')
const sizesLabel = (page) => page.locator('[data-guide="review-pagination"] .el-pagination__sizes')

/**
 * 档位文案按 Element Plus 当前 locale 渲染（本项目 main.js 传的是 `locale: undefined`，
 * 内置文案仍是英文「50/page」），所以断言只认**数字**，选择器只按 PAGE_SIZE_OPTIONS 的下标点。
 * 「中英混排」是另一件事，已建派生单（见 T02517 回传文档），不在此处将就成中文断言。
 */
const SIZE_TIERS = [10, 20, 50, 100]

async function chooseSize(page, n) {
  await sizesLabel(page).locator('.el-select').click()
  const options = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
  await expect(options).toHaveCount(SIZE_TIERS.length)
  await options.nth(SIZE_TIERS.indexOf(n)).click()
}

test.describe('审核列表：分页档位 + 筛选持久化 + 失败可见（B3/B4/B6）', () => {
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubSse(page)
  })

  test('档位选择器可见，选 50 后请求带 size=50 且行数跟着变', async ({ page }) => {
    const calls = await mockReviews(page)
    await page.goto('/news/review')
    await expect(sizesLabel(page)).toContainText(/\b10\b/)
    await expect(reviewTableRows(page)).toHaveCount(10)

    await chooseSize(page, 50)
    await expect.poll(() => calls.at(-1).size).toBe(50)
    await expect.poll(() => new URL(page.url()).searchParams.get('size')).toBe('50')
    await expect(reviewTableRows(page)).toHaveCount(50)
  })

  test('深链 ?size=100 直接按 100 起（分享出去的地址打开就是那个视图）', async ({ page }) => {
    const calls = await mockReviews(page)
    await page.goto('/news/review?size=100')
    await expect(sizesLabel(page)).toContainText(/\b100\b/)
    await expect.poll(() => calls.at(-1).size).toBe(100)
    await expect(reviewTableRows(page)).toHaveCount(100)
  })

  test('非法 ?size=999 钳到上限 100 并在页内点名（不静默按 999 请求）', async ({ page }) => {
    const calls = await mockReviews(page)
    await page.goto('/news/review?size=999')
    await expect(sizesLabel(page)).toContainText(/\b100\b/)
    await expect.poll(() => calls.at(-1).size).toBe(100)
    await expect(page.locator('[data-guide="review-url-corrected"]')).toContainText('size=999')
    // 校正后的值写回地址：分享出去的地址不再撒谎。
    // 必须 poll——`calls` 在请求发出时就记了一笔，紧接着读 page.url() 会抢在
    // 前端处理完响应、回写 URL 之前（实测踩过，与 url-state.spec.js 的导航竞态同源）
    await expect.poll(() => new URL(page.url()).searchParams.get('size')).toBe('100')
  })

  test('工作流 ID 筛选：查询进请求、写进地址、刷新后回填', async ({ page }) => {
    const calls = await mockReviews(page)
    await page.goto('/news/review')
    await page.fill('[data-guide="review-filters"] input', 'wf-007')
    await page.getByRole('button', { name: '搜索' }).click()
    await expect.poll(() => calls.at(-1).workflow_id).toBe('wf-007')
    // 同上：URL 是响应处理完才回写的，只能 poll，不能紧跟在请求断言后面同步读
    await expect.poll(() => new URL(page.url()).searchParams.get('workflow_id')).toBe('wf-007')

    await page.reload()
    await expect.poll(() => calls.at(-1).workflow_id).toBe('wf-007')
    await expect(page.locator('[data-guide="review-filters"] input')).toHaveValue('wf-007')
  })

  test('非法 workflow_id（含空格）回落空筛选并提示，不原样发给后端', async ({ page }) => {
    const calls = await mockReviews(page)
    await page.goto('/news/review?workflow_id=wf%20007')
    await expect.poll(() => calls.at(-1)).toBeTruthy()
    expect(calls.every((c) => c.workflow_id === null)).toBe(true)
    await expect(page.locator('[data-guide="review-url-corrected"]')).toBeVisible()
    await expect(page.locator('[data-guide="review-filters"] input')).toHaveValue('')
  })

  test('列表加载失败：页内错误态 + 重试，绝不显示「暂无数据」', async ({ page }) => {
    await mockReviews(page, { failFirst: true })
    await page.goto('/news/review')
    const error = page.locator('.list-load-error')
    await expect(error).toBeVisible()
    await expect(error).toContainText('重试')
    await expect(page.locator('.el-empty')).toHaveCount(0)
    // 重试一次即恢复（failFirst 只打断第一条请求）。
    // ⚠ ListLoadError 的重试是 IconButton：可见文案只有图标，「重试」在 aria-label 上，
    // 用 hasText 选不到（实测等 60s 超时），必须按可访问名选
    await error.getByRole('button', { name: '重试' }).click()
    await expect(reviewTableRows(page)).toHaveCount(10)
    await expect(page.locator('.list-load-error')).toHaveCount(0)
  })

  test('NFR-UX-03：失败态停留期间不自发重试/轮询（请求只在点击后增加）', async ({ page }) => {
    const calls = await mockReviews(page, { failFirst: true })
    await page.goto('/news/review')
    await expect(page.locator('.list-load-error')).toBeVisible()
    const before = calls.length
    await page.waitForTimeout(4000)
    expect(calls.length).toBe(before)
  })
})

test.describe('素材库：勾选批量删除（C52）', () => {
  test.use({ expect: { timeout: 30000 } })

  const materialRows = (n) =>
    Array.from({ length: n }, (_, i) => ({
      id: 100 + i,
      source: '测试源',
      title: `素材 ${i + 1}`,
      category: 'tech',
      status: 'pending',
      source_type: 'list',
      url: `https://a.com/${i + 1}`,
      created_at: '2026-07-08T05:00:00',
    }))

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubSse(page)
    await page.route('**/admin/api/v1/channels**', (route) =>
      route.fulfill({ json: ok([{ id: 1, name: '科技前沿', channel_type: 'news', enabled: true }]) }),
    )
    await page.route('**/admin/api/v1/materials/batch-delete', (route) =>
      route.fulfill({ json: ok({ deleted: 2, requested: 2 }) }),
    )
    await page.route('**/admin/api/v1/materials**', (route) =>
      route.fulfill({ json: ok({ total: 5, list: materialRows(5) }) }),
    )
  })

  test('勾选列存在，勾选后出现批量删除入口且条数如实', async ({ page }) => {
    await page.goto('/channels/material-library')
    await expect(page.locator('[data-guide="material-library-table"] th.el-table__cell .el-checkbox')).toBeVisible()
    await expect(page.locator('.batch-bar')).toHaveCount(0)

    const boxes = page.locator('[data-guide="material-library-table"] tbody .el-checkbox')
    await boxes.nth(0).click()
    await boxes.nth(1).click()
    await expect(page.locator('.batch-bar')).toContainText('已选 2 条素材')
  })

  test('批删要二次确认，确认后请求体就是勾选的那两个 ID', async ({ page }) => {
    const requests = []
    await page.route('**/admin/api/v1/materials/batch-delete', (route) => {
      requests.push(JSON.parse(route.request().postData() || '{}'))
      return route.fulfill({ json: ok({ deleted: 2, requested: 2 }) })
    })
    await page.goto('/channels/material-library')
    const boxes = page.locator('[data-guide="material-library-table"] tbody .el-checkbox')
    await boxes.nth(0).click()
    await boxes.nth(1).click()
    await page.getByRole('button', { name: '批量删除' }).click()

    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible()
    // §6.3 确认规范：动作 + 对象 + 影响条数 + 不可逆声明
    await expect(box).toContainText('2 条素材')
    await expect(box).toContainText('不可恢复')
    await box.getByRole('button', { name: '确认删除' }).click()

    await expect.poll(() => requests.length).toBe(1)
    expect(requests[0].ids).toEqual([100, 101])
    await expect(page.locator('.batch-bar')).toHaveCount(0)
  })

  test('取消只关弹窗：不发请求、不清勾选', async ({ page }) => {
    let sent = 0
    await page.route('**/admin/api/v1/materials/batch-delete', (route) => {
      sent += 1
      return route.fulfill({ json: ok({ deleted: 0, requested: 0 }) })
    })
    await page.goto('/channels/material-library')
    const boxes = page.locator('[data-guide="material-library-table"] tbody .el-checkbox')
    await boxes.nth(0).click()
    await page.getByRole('button', { name: '批量删除' }).click()
    await page.locator('.el-message-box').getByRole('button', { name: '取消' }).click()
    await expect(page.locator('.batch-bar')).toContainText('已选 1 条素材')
    expect(sent).toBe(0)
  })
})

test.describe('移动端消息：分页取全量（I21）', () => {
  test.use({ viewport: { width: 375, height: 667 }, expect: { timeout: 30000 } })

  const msg = (i) => ({
    id: i,
    title: `消息 ${i}`,
    content: '正文',
    type: 'system',
    is_read: i > 3,
    created_at: '2026-07-08 05:00:00',
  })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await stubSse(page)
  })

  test('50 条消息：首屏 20 条，点「加载更多」取到第 2 页并累加', async ({ page }) => {
    const calls = []
    await page.route('**/admin/api/v1/m/inbox**', (route) => {
      const url = new URL(route.request().url())
      const p = Number(url.searchParams.get('page') || 1)
      const size = Number(url.searchParams.get('page_size') || 20)
      calls.push({ p, size })
      const total = 50
      // 末页只回剩余条数（真实后端如此）；夹具若固定回满 20 条，测的就是「后端违约时客户端怎么办」
      const count = Math.max(0, Math.min(size, total - (p - 1) * size))
      return route.fulfill({
        json: ok({ total, unread_count: 3, items: Array.from({ length: count }, (_, i) => msg((p - 1) * size + i + 1)) }),
      })
    })
    await page.goto('/news/m/message')
    await expect(page.locator('.m-msg__pager')).toContainText('已显示 20 / 50')

    await page.getByRole('button', { name: /加载更多/ }).click()
    await expect.poll(() => calls.at(-1).p).toBe(2)
    await expect(page.locator('.m-msg__pager')).toContainText('已显示 40 / 50')

    await page.getByRole('button', { name: /加载更多/ }).click()
    await expect(page.locator('.m-msg__pager')).toContainText('已显示 50 / 50')
    await expect(page.getByRole('button', { name: /加载更多/ })).toHaveCount(0)
    await expect(page.locator('.m-msg__pager')).toContainText('没有更多了')
  })

  test('取完第 2 页不重复计数（后端分页重叠时按 id 去重）', async ({ page }) => {
    await page.route('**/admin/api/v1/m/inbox**', (route) => {
      const url = new URL(route.request().url())
      const p = Number(url.searchParams.get('page') || 1)
      // 故意让第 2 页从 16 开始（与第 1 页尾部重叠 5 条），且回满剩下的 15 条
      const start = p === 1 ? 1 : 16
      const count = p === 1 ? 20 : 15
      return route.fulfill({
        json: ok({ total: 30, unread_count: 0, items: Array.from({ length: count }, (_, i) => msg(start + i)) }),
      })
    })
    await page.goto('/news/m/message')
    await expect(page.locator('.m-msg__pager')).toContainText('已显示 20 / 30')
    await page.getByRole('button', { name: /加载更多/ }).click()
    await expect(page.locator('.m-msg__item')).toHaveCount(30)
    await expect(page.locator('.m-msg__pager')).toContainText('已显示 30 / 30')
  })

  test('加载失败给出页内错误态与重试，不伪装成「暂无消息」', async ({ page }) => {
    let first = true
    await page.route('**/admin/api/v1/m/inbox**', (route) => {
      if (first) {
        first = false
        return route.fulfill({ json: { code: 500, message: '服务暂不可用', data: null } })
      }
      return route.fulfill({ json: ok({ total: 1, unread_count: 1, items: [msg(1)] }) })
    })
    await page.goto('/news/m/message')
    const error = page.locator('.m-msg__error')
    await expect(error).toContainText('服务暂不可用')
    await error.getByRole('button', { name: '重试' }).click()
    await expect(page.locator('.m-msg__item')).toHaveCount(1)
    await expect(page.locator('.m-msg__error')).toHaveCount(0)
  })
})
