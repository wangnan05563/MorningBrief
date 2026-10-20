import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse, useMobileViewport } from './helpers/mock'

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
  test.use({ expect: { timeout: NAV_TIMEOUT } })

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
      await expect(box.getByText(/变成无主数据/)).toBeVisible()
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
})
