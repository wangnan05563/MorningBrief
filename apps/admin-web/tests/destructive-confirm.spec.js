import { test, expect } from '@playwright/test'
import {
  setLoginState,
  channelsListResponse,
  adPlacementsListResponse,
  useMobileViewport,
} from './helpers/mock'

/**
 * T02490（FR-UX-202）破坏性操作确认规范 E2E
 *
 * 口径（PRD §6.3）：动作 + 对象 + 影响条数 + 不可逆声明；
 * 高风险/批量动作再要求逐字输入确认词；影响面预览失败禁止提交。
 */
const NAV_TIMEOUT = 30000

const deletePreviewResponse = {
  code: 0,
  message: 'success',
  data: {
    channel_id: 1,
    channel_name: '科技频道',
    book_pool_items: 12,
    materials: 340,
    workflows: 5,
  },
}

test.describe('破坏性操作确认', () => {

  test.describe('频道删除（C9/C10）', () => {
    // 单条 route 内分流：`channels*` 的 * 不跨 /，必须用 ** 才能覆盖 /channels/1 与子路径
    const mockChannels = (previewFails = false) => async (route) => {
      const method = route.request().method()
      if (route.request().url().includes('/delete-preview')) {
        return previewFails
          ? route.fulfill({ status: 500, json: { code: 500, message: '预览服务不可用', data: null } })
          : route.fulfill({ json: deletePreviewResponse })
      }
      if (method === 'GET') return route.fulfill({ json: channelsListResponse })
      return route.fulfill({ json: { code: 0, message: '已删除', data: null } })
    }

    test.beforeEach(async ({ page }) => {
      await page.route('**/admin/api/v1/channels**', mockChannels())
    })

    test('确认框四要素齐全且需逐字输入频道名', async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.goto('/channels')
      await expect(page.getByText('科技频道').first()).toBeVisible({ timeout: NAV_TIMEOUT })

      const deleteRequest = page.waitForRequest(
        (req) => req.url().includes('/channels/1') && req.method() === 'DELETE',
      )
      await page.getByRole('button', { name: '删除' }).first().click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      // 动作 + 对象
      await expect(box.getByText('删除频道：频道「科技频道」')).toBeVisible()
      // 影响条数（来自服务端预览，不是写死的「不可恢复」一句）
      await expect(box.getByText('书单 12 本 / 素材 340 条 / 工作流 5 条')).toBeVisible()
      await expect(box.getByText(/讲书稿书单 12 条随频道一并删除/)).toBeVisible()
      await expect(box.getByText(/正文保留并回到全局素材池/)).toBeVisible()
      // 不可逆声明
      await expect(box.getByText('此操作不可恢复：频道及其书单没有回收站')).toBeVisible()

      // 确认词：不输入直接点确认不得放行
      await box.getByRole('button', { name: '确认删除' }).click()
      await expect(box.getByText('请逐字输入 科技频道')).toBeVisible()
      await box.locator('input').fill('科技频道')
      await box.getByRole('button', { name: '确认删除' }).click()

      await deleteRequest
      await expect(page.locator('.el-message').getByText('已删除').first()).toBeVisible()
    })

    test('取消确认不发出删除请求', async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.goto('/channels')
      await expect(page.getByText('科技频道').first()).toBeVisible({ timeout: NAV_TIMEOUT })

      await page.getByRole('button', { name: '删除' }).first().click()
      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()

      const sent = page
        .waitForRequest((req) => req.method() === 'DELETE', { timeout: 2000 })
        .then(() => true)
        .catch(() => false)
      expect(await sent).toBe(false)
    })

    test('影响面预览失败时禁止进入删除确认（C10）', async ({ page }) => {
      await page.route('**/admin/api/v1/channels**', mockChannels(true))
      await setLoginState(page, 'admin')
      await page.goto('/channels')
      await expect(page.getByText('科技频道').first()).toBeVisible({ timeout: NAV_TIMEOUT })

      await page.getByRole('button', { name: '删除' }).first().click()
      await expect(
        page.locator('.el-message').getByText(/无法获取删除影响面预览，已禁止删除/).first(),
      ).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(page.locator('.el-message-box')).toHaveCount(0)

      const sent = page
        .waitForRequest((req) => req.method() === 'DELETE', { timeout: 2000 })
        .then(() => true)
        .catch(() => false)
      expect(await sent).toBe(false)
    })
  })

  test.describe('数据库后台删除（M31/M32/M33/M37）', () => {
    const tablesResponse = {
      code: 0,
      message: 'success',
      data: [{ name: 'workflow', label: '工作流主表', rows: 1 }],
    }
    const schemaResponse = {
      code: 0,
      message: 'success',
      data: {
        columns: [
          { name: 'id', type: 'VARCHAR(64)', primary_key: true, sensitive: false },
          { name: 'status', type: 'VARCHAR(32)', primary_key: false, sensitive: false },
        ],
      },
    }
    const rowsResponse = {
      code: 0,
      message: 'success',
      data: { rows: [{ id: 'wf-001', status: 'success' }], total: 1 },
    }
    const cascadeResponse = {
      code: 0,
      message: 'success',
      data: {
        table: 'workflow',
        total_affected: 3,
        undeclared_downstream:
          '本预览只覆盖已声明的关联表（workflow_step）。script / review / episode / play_log 等下游数据不会随之删除，可能留下悬空引用；需要按全链路清理请改用「系统清理」页。',
        relations: [
          { table: 'workflow_step', fk: 'workflow_id', action: 'cascade', count: 3, description: '工作流步骤将一并删除' },
        ],
      },
    }

    test.beforeEach(async ({ page }) => {
      await page.route('**/admin/api/v1/db-admin/tables/workflow/cascade-preview', (route) =>
        route.fulfill({ json: cascadeResponse }),
      )
      await page.route('**/admin/api/v1/db-admin/tables/workflow/rows*', async (route) => {
        const method = route.request().method()
        if (method === 'GET') return route.fulfill({ json: rowsResponse })
        return route.fulfill({
          json: { code: 0, message: 'success', data: { ok: true, affected: 1, cascade: { workflow_step: 3 } } },
        })
      })
      await page.route('**/admin/api/v1/db-admin/tables/workflow/schema', (route) =>
        route.fulfill({ json: schemaResponse }),
      )
      await page.route('**/admin/api/v1/db-admin/tables', (route) =>
        route.fulfill({ json: tablesResponse }),
      )
      await page.route('**/admin/api/v1/db-admin/audit-log*', (route) =>
        route.fulfill({ json: { code: 0, message: 'success', data: { items: [], total: 0 } } }),
      )
    })

    const rowDeleteButton = (page) =>
      page.locator('.data-table .el-table__row').first().getByRole('button', { name: '删除' })

    test('删除弹窗给出中文表名、合计受影响与未声明下游提示', async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.goto('/db-admin')
      await page.locator('.table-item').filter({ hasText: '工作流主表' }).click({ timeout: NAV_TIMEOUT })
      await expect(rowDeleteButton(page)).toBeVisible({ timeout: NAV_TIMEOUT })

      await rowDeleteButton(page).click()
      const dlg = page.locator('.el-dialog').filter({ hasText: '确认删除' })
      await expect(dlg).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(dlg.getByText(/删除「工作流主表」/)).toBeVisible()
      await expect(dlg.getByText(/合计受影响 4 行（主表 1 \+ 级联 3）/)).toBeVisible()
      await expect(dlg.getByText(/未声明的下游|script \/ review \/ episode/).first()).toBeVisible()
      await expect(dlg.getByText('此操作不可恢复：SQLite 没有回收站')).toBeVisible()
    })

    test('级联预览失败时不打开删除弹窗', async ({ page }) => {
      await page.route('**/admin/api/v1/db-admin/tables/workflow/cascade-preview', (route) =>
        route.fulfill({ status: 500, json: { code: 500, message: '预览失败', data: null } }),
      )
      await setLoginState(page, 'admin')
      await page.goto('/db-admin')
      await page.locator('.table-item').filter({ hasText: '工作流主表' }).click({ timeout: NAV_TIMEOUT })
      await expect(rowDeleteButton(page)).toBeVisible({ timeout: NAV_TIMEOUT })

      await rowDeleteButton(page).click()
      await expect(
        page.locator('.el-message').getByText(/级联影响预览失败，已禁止删除/).first(),
      ).toBeVisible({ timeout: NAV_TIMEOUT })
      // T02629：预览请求 silent——后端原文（「预览失败」）不得再单独弹一条，否则同一件事
      // 两条提示，其中一条还没说清「已禁止删除」。按整条文案精确比对：页面自己那条
      // 「级联影响预览失败，已禁止删除」也含「预览失败」四个字，模糊匹配会误伤。
      const toasts = (await page.locator('.el-message').allTextContents()).map((t) => t.trim())
      expect(toasts).not.toContain('预览失败')
      await expect(page.locator('.el-dialog').filter({ hasText: '确认删除' })).toHaveCount(0)
    })
  })

  test.describe('移动审批一键通过（I1/I2）', () => {
    const listResponse = {
      code: 0,
      message: 'success',
      data: {
        total: 3,
        list: [
          { id: 1, title: 'A 条', channel_name: '科技频道', status: 'pending', episode_date: '2026-10-18' },
          { id: 2, title: 'B 条', channel_name: '科技频道', status: 'pending', episode_date: '2026-10-18' },
          { id: 3, title: 'C 条', channel_name: '财经频道', status: 'pending', episode_date: '2026-10-18' },
        ],
      },
    }

    test.beforeEach(async ({ page }) => {
      await page.route('**/admin/api/v1/reviews*', async (route) => {
        const method = route.request().method()
        if (method === 'GET') return route.fulfill({ json: listResponse })
        return route.fulfill({
          json: { code: 0, message: 'success', data: { succeeded: [1, 2, 3], skipped: [], failed: [] } },
        })
      })
    })

    test('跨频道一键通过前必须确认并列出频道分布', async ({ page }) => {
      await setLoginState(page, 'admin')
      // 移动审批要在手机视口下测（桌面视口会被跨端策略换到 PC 审核页，T02511）
      await useMobileViewport(page)
      await page.goto('/m/review')
      await expect(page.getByText('A 条').first()).toBeVisible({ timeout: NAV_TIMEOUT })

      await page.locator('.m-btn--approve-all').click()
      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(box.getByText('一键全部通过并自动发布：本页 3 条待审内容（覆盖 2 个频道）')).toBeVisible()
      await expect(box.getByText('· 科技频道：2 条')).toBeVisible()
      await expect(box.getByText('· 财经频道：1 条')).toBeVisible()
      await expect(box.getByText('批量发布后无法整体撤回')).toBeVisible()
      // 未限定频道时属于「无范围一键放行」，要求输入确认词
      await expect(box.getByText('请输入 全部通过 以确认')).toBeVisible()

      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()
      const sent = page
        .waitForRequest((req) => req.method() === 'POST', { timeout: 2000 })
        .then(() => true)
        .catch(() => false)
      expect(await sent).toBe(false)
    })
  })

  test.describe('批量删除工作流 / 队列任务（T02596）', () => {
    // 影响条数来自服务端 delete_preview，而非前端选中的行数
    const previewResponse = {
      code: 0,
      message: 'success',
      data: {
        workflows: 1, scripts: 3, reviews: 2, episodes: 1, play_logs: 5,
        play_progress: 5, comments: 0, favorites: 0, auto_review_stats: 1,
        workflow_steps: 4, materials_retained: 2,
      },
    }
    const wfList = {
      code: 0,
      message: 'success',
      data: { total: 2, list: [
        { id: 'wf-001', episode_date: '2026-07-08', source: 'cron', status: 'success', started_at: '2026-07-08T05:00:00', finished_at: '2026-07-08T05:30:00' },
        { id: 'wf-002', episode_date: '2026-07-07', source: 'manual', status: 'success', started_at: '2026-07-07T05:00:00', finished_at: null },
      ] },
    }
    // 分流：preview / 真删 / 列表；`/workflows*` 的 * 不跨 /，必须用 **
    const mockWorkflows = (previewFails = false) => async (route) => {
      const url = route.request().url()
      const method = route.request().method()
      if (url.includes('/batch-delete/preview')) {
        return previewFails
          ? route.fulfill({ status: 500, json: { code: 500, message: '预览服务不可用', data: null } })
          : route.fulfill({ json: previewResponse })
      }
      if (url.endsWith('/workflows/batch-delete') && method === 'POST') {
        return route.fulfill({ json: { code: 0, message: 'success', data: { deleted: ['wf-001'] } } })
      }
      if (method === 'GET') return route.fulfill({ json: wfList })
      return route.fulfill({ json: { code: 0, message: 'success', data: null } })
    }
    const isDeleteRequest = (req) => req.url().endsWith('/workflows/batch-delete') && req.method() === 'POST'
    // 等待必须在点击「确定删除」之前登记：点完再开始监听会漏掉已经发出的请求
    const watchDeleteRequest = (page) => page.waitForRequest(isDeleteRequest)
    const expectNoDeleteRequest = async (page) => {
      const sent = await page
        .waitForRequest(isDeleteRequest, { timeout: 2000 })
        .then(() => true)
        .catch(() => false)
      expect(sent).toBe(false)
    }
    const selectFirstRow = async (page) => {
      // 行选框的原生 <input> 被 Element Plus 隐藏（可见的是 .el-checkbox__inner），
      // 直接点 input 会「element is not visible」；点可见的方框本体
      await page.locator('.el-table__body .el-checkbox__inner').first().click()
      await expect(page.getByText('已选 1 项')).toBeVisible({ timeout: NAV_TIMEOUT })
    }

    test.beforeEach(async ({ page }) => {
      await page.route('**/admin/api/v1/workflows**', mockWorkflows())
    })

    test('确认框列出服务端级联条数并需逐字输入 DELETE', async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.goto('/workflows')
      await expect(page.getByText('wf-001').first()).toBeVisible({ timeout: NAV_TIMEOUT })

      await selectFirstRow(page)
      await page.getByRole('button', { name: '批量删除' }).click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      // 动作 + 对象
      await expect(box.getByText('批量删除工作流：1 个工作流')).toBeVisible()
      // 影响条数来自服务端预览（不是写死的分类清单，也不是「选中的行数」）
      await expect(box.getByText('稿件 3 篇 / 审核 2 条 / 节目 1 个 / 播放记录 5 条')).toBeVisible()
      await expect(box.getByText(/工作流步骤 4 条、自动审批统计 1 条/)).toBeVisible()
      await expect(box.getByText(/素材 2 条不删除，重置为待处理状态/)).toBeVisible()
      // 不可逆声明
      await expect(box.getByText('此操作不可撤销：稿件/审核/节目/播放记录随之删除')).toBeVisible()

      // 高风险批量动作要求确认词：不输入直接点确认不得放行
      await box.getByRole('button', { name: '确定删除' }).click()
      await expect(box.getByText('请逐字输入 DELETE')).toBeVisible()
      await box.locator('input').fill('DELETE')
      const delReq = watchDeleteRequest(page)
      await box.getByRole('button', { name: '确定删除' }).click()

      await delReq
      await expect(page.locator('.el-message').getByText('已删除').first()).toBeVisible()
    })

    test('取消确认不发出删除请求', async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.goto('/workflows')
      await expect(page.getByText('wf-001').first()).toBeVisible({ timeout: NAV_TIMEOUT })
      await selectFirstRow(page)
      await page.getByRole('button', { name: '批量删除' }).click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()

      await expectNoDeleteRequest(page)
    })

    test('影响面预览失败时禁止进入删除确认', async ({ page }) => {
      await page.route('**/admin/api/v1/workflows**', mockWorkflows(true))
      await setLoginState(page, 'admin')
      await page.goto('/workflows')
      await expect(page.getByText('wf-001').first()).toBeVisible({ timeout: NAV_TIMEOUT })
      await selectFirstRow(page)
      await page.getByRole('button', { name: '批量删除' }).click()

      await expect(
        page.locator('.el-message').getByText(/无法获取删除影响面预览，已禁止删除/).first(),
      ).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(page.locator('.el-message-box')).toHaveCount(0)

      await expectNoDeleteRequest(page)
    })

    test('队列页批量删除复用同一服务端预览并列出条数', async ({ page }) => {
      // 队列任务的批量删除走 /queue/tasks/batch-delete，但预览统一取工作流级联预览
      const qList = { code: 0, message: 'success', data: { total: 1, items: [
        { id: 'wf-001', channel_name: '科技频道', priority: 5, status: 'success', started_at: '2026-07-08T05:00:00' },
      ] } }
      await page.route('**/admin/api/v1/queue/tasks**', async (route) => {
        if (route.request().method() === 'GET') return route.fulfill({ json: qList })
        return route.fulfill({ json: { code: 0, message: 'success', data: { deleted: ['wf-001'] } } })
      })
      await page.route('**/admin/api/v1/queue/stats**', (route) =>
        route.fulfill({ json: { code: 0, message: 'success', data: { running: 0, queued: 0, success: 1, failed: 0 } } }))
      await page.route('**/admin/api/v1/queue/config**', (route) =>
        route.fulfill({ json: { code: 0, message: 'success', data: {} } }))
      await page.route('**/admin/api/v1/channels**', (route) =>
        route.fulfill({ json: { code: 0, message: 'success', data: [] } }))
      await page.route('**/admin/api/v1/workflows/batch-delete/preview', (route) =>
        route.fulfill({ json: previewResponse }))

      await setLoginState(page, 'admin')
      await page.goto('/queue')
      await expect(page.getByText('科技频道').first()).toBeVisible({ timeout: NAV_TIMEOUT })

      await page.locator('.el-table__body .el-checkbox__inner').first().click()
      await page.getByRole('button', { name: '批量删除' }).click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(box.getByText('批量删除任务：1 个任务')).toBeVisible()
      await expect(box.getByText('稿件 3 篇 / 审核 2 条 / 节目 1 个 / 播放记录 5 条')).toBeVisible()
      await expect(box.getByText('请输入 DELETE 以确认')).toBeVisible()
    })
  })

  test.describe('素材删除三入口（T02596 切片B）', () => {
    // 素材是硬删除且无外键级联，影响条数就是请求范围本身；
    // 确认框必须把这层如实讲出来，不能只写一句「不可恢复」
    const stubSse = (page) =>
      page.route('**/admin/api/v1/events/stream**', (route) =>
        route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }))

    test('素材库单条删除：对象+条数+不可恢复写全，取消不发请求', async ({ page }) => {
      await setLoginState(page, 'admin')
      await stubSse(page)
      await page.route('**/admin/api/v1/channels**', (route) =>
        route.fulfill({ json: { code: 0, message: 'success', data: [
          { id: 1, name: '科技前沿', channel_type: 'news', enabled: true },
        ] } }))
      const deletes = []
      await page.route('**/admin/api/v1/materials**', (route) => {
        const method = route.request().method()
        if (method === 'DELETE') {
          deletes.push(route.request().url())
          return route.fulfill({ json: { code: 0, message: 'success', data: null } })
        }
        return route.fulfill({ json: { code: 0, message: 'success', data: { total: 1, list: [
          { id: 100, source: '人民网', title: '素材一', category: 'tech', status: 'pending',
            source_type: 'list', url: 'https://a.com/1', crawled_at: '2026-07-08T05:00:00' },
        ] } } })
      })

      await page.goto('/channels/material-library')
      const row = page.locator('[data-guide="material-library-table"] .el-table__body tr').first()
      await expect(row).toContainText('素材一', { timeout: NAV_TIMEOUT })
      await row.getByRole('button', { name: '删除' }).click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(box.getByText('删除素材：「素材一」（ID 100）')).toBeVisible()
      await expect(box.getByText('影响范围：素材 1 条')).toBeVisible()
      await expect(box.getByText(/素材为硬删除，无关联数据被连带删除/)).toBeVisible()
      await expect(box.getByText(/删除后不可恢复/)).toBeVisible()

      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()
      expect(deletes).toHaveLength(0)

      // 确认后请求打到这条素材本身（不是「选中的第一行」之外的对象）
      await row.getByRole('button', { name: '删除' }).click()
      await page.locator('.el-message-box').getByRole('button', { name: '确认删除' }).click()
      await expect.poll(() => deletes.length).toBe(1)
      expect(deletes[0]).toMatch(/\/materials\/100$/)
    })

    test('广告素材删除：先讲明关联投放会拒删，取消不发请求', async ({ page }) => {
      await setLoginState(page, 'admin')
      const deletes = []
      await page.route('**/admin/api/v1/ads/materials**', (route) => {
        const method = route.request().method()
        if (method === 'DELETE') {
          deletes.push(route.request().url())
          return route.fulfill({ json: { code: 0, message: 'success', data: null } })
        }
        return route.fulfill({ json: { code: 0, message: 'success', data: { total: 2, list: [
          { id: 1, name: '品牌广告A', description: '默认素材', duration: 15,
            file_url: 'https://example.com/ads/a.mp3', is_default: true },
          { id: 2, name: '促销广告B', description: '促销素材', duration: 30,
            file_url: 'https://example.com/ads/b.mp3', is_default: false },
        ] } } })
      })

      await page.goto('/ads/materials')
      // 第 1 行是默认素材，删除按钮禁用；点第 2 行
      const row = page.locator('.el-table__body tr').nth(1)
      await expect(row).toContainText('促销广告B', { timeout: NAV_TIMEOUT })
      await row.getByRole('button', { name: '删除' }).click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(box.getByText('删除广告素材：「促销广告B」（ID 2）')).toBeVisible()
      await expect(box.getByText('影响范围：广告素材 1 条；关联的投放规则不会被连带删除')).toBeVisible()
      await expect(box.getByText(/仍被投放规则引用，后端会拒绝删除/)).toBeVisible()
      await expect(box.getByText(/删除后不可恢复/)).toBeVisible()

      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()
      // 转换前这里没有 catch，取消会抛未处理的 rejection；提前拦下后必须一条请求都不发
      expect(deletes).toHaveLength(0)

      await row.getByRole('button', { name: '删除' }).click()
      await page.locator('.el-message-box').getByRole('button', { name: '确认删除' }).click()
      await expect.poll(() => deletes.length).toBe(1)
      expect(deletes[0]).toMatch(/\/ads\/materials\/2$/)
    })
  })

  test.describe('单对象硬删除（T02596 切片C）', () => {
    test('投放规则删除：点名广告位+素材与排期，取消不发请求', async ({ page }) => {
      await setLoginState(page, 'admin')
      const deletes = []
      await page.route('**/admin/api/v1/ads/placements**', (route) => {
        if (route.request().method() === 'DELETE') {
          deletes.push(route.request().url())
          return route.fulfill({ json: { code: 0, message: 'success', data: null } })
        }
        return route.fulfill({ json: adPlacementsListResponse })
      })

      await page.goto('/ads/placements')
      const row = page.locator('.el-table__body tr').first()
      await expect(row).toContainText('品牌广告A', { timeout: NAV_TIMEOUT })
      await row.getByRole('button', { name: '删除' }).click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      // 动作 + 对象：广告位与素材名都要在，不能只写一个「投放 #1」
      await expect(box.getByText('删除投放规则：开头位 · 品牌广告A')).toBeVisible()
      await expect(box.getByText('影响范围：投放规则 1 条（生效区间 2026-07-01 ~ 2026-07-31）')).toBeVisible()
      // 说清「已生成节目里的广告不会被去掉」与素材不受影响，避免误判为连坐删除
      await expect(box.getByText(/已生成节目里拼进音频的广告不会被去掉/)).toBeVisible()
      await expect(box.getByText(/广告素材本身不受影响/)).toBeVisible()
      await expect(box.getByText(/删除后不可恢复/)).toBeVisible()

      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()
      expect(deletes).toHaveLength(0)

      await row.getByRole('button', { name: '删除' }).click()
      await page.locator('.el-message-box').getByRole('button', { name: '确认删除' }).click()
      await expect.poll(() => deletes.length).toBe(1)
      expect(deletes[0]).toMatch(/\/ads\/placements\/1$/)
    })

    test('COS 文件夹删除：说明递归范围与数量以服务端为准，取消不发请求', async ({ page }) => {
      await setLoginState(page, 'admin')
      const deletes = []
      await page.route('**/admin/api/v1/cos**', (route) => {
        const url = route.request().url()
        const method = route.request().method()
        if (url.includes('/cos/status')) {
          return route.fulfill({
            json: { code: 0, message: 'ok', data: { configured: true, bucket: 'bkt', region: 'ap-guangzhou', cdn_domain: '' } },
          })
        }
        if (url.includes('/cos/objects')) {
          return route.fulfill({
            json: { code: 0, message: 'ok', data: { prefix: '', folders: ['books/'], files: [] } },
          })
        }
        if (url.includes('/cos/folder') && method === 'DELETE') {
          deletes.push(url)
          return route.fulfill({ json: { code: 0, message: '已删除 3 个对象', data: { deleted: 3 } } })
        }
        return route.fulfill({ json: { code: 0, message: 'ok', data: null } })
      })

      await page.goto('/cos-files')
      const row = page.locator('[data-guide="cos-files-table"] .el-table__body tr').first()
      await expect(row).toContainText('books', { timeout: NAV_TIMEOUT })
      await row.getByRole('button', { name: '删除' }).click()

      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      // 对象要带完整 key：只写显示名「books」会让人以为删的是空目录
      await expect(box.getByText('删除 COS 文件夹：「books」（books/）')).toBeVisible()
      await expect(box.getByText(/影响范围：文件夹 1 个及其下全部对象（数量以服务端实际删除为准）/)).toBeVisible()
      await expect(box.getByText(/只删对象存储里的文件，素材库\/数据库记录不受影响/)).toBeVisible()
      await expect(box.getByText(/删除后不可恢复：COS 没有回收站/)).toBeVisible()

      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()
      expect(deletes).toHaveLength(0)

      await row.getByRole('button', { name: '删除' }).click()
      await page.locator('.el-message-box').getByRole('button', { name: '确认删除' }).click()
      await expect.poll(() => deletes.length).toBe(1)
      expect(deletes[0]).toContain('/cos/folder')
      expect(deletes[0]).toMatch(/prefix=books(%2F|\/)/)
      // 成功提示必须给出服务端实际删除数量，而不是笼统的「已删除」
      await expect(
        page.locator('.el-message').getByText('已删除 3 个对象').first(),
      ).toBeVisible({ timeout: NAV_TIMEOUT })
    })
  })

  test.describe('终端用户禁用/启用（T02596 切片D）', () => {
    const usersResponse = {
      code: 0,
      message: 'success',
      data: {
        total: 1,
        list: [
          { id: 5, nickname: '张三', openid: 'o_abcdefghijklmn', disabled: 0,
            total_listen_count: 3, total_listen_duration: 120, created_at: '2026-07-01T00:00:00' },
        ],
        // T02708：累计收听是 lifetime 口径，单位与起点都由后端下发
        meta: {
          total_listen_count: {
            label: '累计收听', unit: 'count',
            display: { unit: '次', factor: 1, precision: 0 },
          },
          total_listen_duration: {
            label: '累计收听时长', unit: 'second',
            display: { unit: '分钟', factor: 1 / 60, precision: 1 },
          },
        },
      },
    }

    test('累计收听单位取自 meta，页面不再硬写「次 / 秒」（T02708）', async ({ page }) => {
      await setLoginState(page, 'admin')
      await useMobileViewport(page)
      await page.route('**/admin/api/v1/users**', (route) => route.fulfill({ json: usersResponse }))

      await page.goto('/m/manage/users')
      // 120 秒按 meta 换算成 2.0 分钟：页面若仍写死「秒」，这里显示 120 秒
      await expect(
        page.getByText(/收听 3 次 · 2\.0 分钟 · 注册 2026-07-01/),
      ).toBeVisible({ timeout: NAV_TIMEOUT })
    })

    test('禁用前讲明登录与会话影响，取消不发请求', async ({ page }) => {
      await setLoginState(page, 'admin')
      await useMobileViewport(page)
      const posts = []
      await page.route('**/admin/api/v1/users**', (route) => {
        if (route.request().method() === 'GET') return route.fulfill({ json: usersResponse })
        posts.push({ url: route.request().url(), body: route.request().postData() })
        return route.fulfill({ json: { code: 0, message: 'success', data: null } })
      })

      await page.goto('/m/manage/users')
      await expect(page.getByText('张三').first()).toBeVisible({ timeout: NAV_TIMEOUT })

      await page.getByRole('button', { name: '禁用' }).click()
      const box = page.locator('.el-message-box')
      await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
      await expect(box.getByText('禁用用户：「张三」')).toBeVisible()
      await expect(box.getByText('影响范围：用户 1 个')).toBeVisible()
      await expect(box.getByText(/禁用后该用户无法登录管理端与小程序/)).toBeVisible()
      await expect(box.getByText(/禁用期间的访问不会被补回/)).toBeVisible()

      await box.getByRole('button', { name: '取消' }).click()
      await expect(box).toBeHidden()
      expect(posts).toHaveLength(0)

      await page.getByRole('button', { name: '禁用' }).click()
      await page.locator('.el-message-box').getByRole('button', { name: '确认禁用' }).click()
      await expect.poll(() => posts.length).toBe(1)
      expect(posts[0].url).toMatch(/\/users\/5\/toggle-status$/)
      expect(JSON.parse(posts[0].body)).toEqual({ disabled: 1 })
    })
  })
})
