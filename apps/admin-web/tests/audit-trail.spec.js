import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02909：模块页旁边的「最近操作审计」必须真读得到、读不到要说清楚。
 *
 * 缺陷形状是「写了一直有，读没有」：30+ 处审计写入覆盖 15 类操作，统一读口原先只放行
 * db_admin 与移动端停服两类，出事以后「刚才那次是谁做的」得手工捞表。本单把只读接口
 * 开给全量管理员（工单裁决），并在动作发生的页面旁挂出最近几条。
 *
 * 这里守四件在 mock 里可判定的事：
 * 1. 请求带本模块 category，不会串到别的桶（接错对象最常见的形态）；
 * 2. 渲染出「谁 / 做了什么 / 为什么」，长尾明细截断而不是丢掉整行；
 * 3. 读取失败走 ListLoadError（含重试），绝不说成「该模块暂无审计记录」（T02496 口径），
 *    且因为是 silent 请求，不额外抢一条全局 toast；
 * 4. 后端脱敏后的 `***` 原样呈现，前端不再自行猜测哪些算敏感。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

const auditRow = (overrides = {}) => ({
  id: 1,
  category: 'maintenance',
  action: 'cleanup',
  target: 'old_playlogs',
  operator: 'admin',
  detail: { days: 7, count: 3 },
  created_at: '2026-10-26T16:00:00',
  ...overrides,
})

const auditList = (rows) => ok({ items: rows, total: rows.length, page: 1, page_size: 5 })

function auditRoute(page, handler) {
  return page.route(`${API}/audit-logs*`, (route) => handler(route))
}

test.describe('系统清理 · 最近操作审计（T02909）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('审计块按本模块 category 取数并呈现谁/做了什么/为什么', async ({ page }) => {
    const asked = []
    await auditRoute(page, (route) => {
      asked.push(new URL(route.request().url()).searchParams.toString())
      return route.fulfill({ json: auditList([
        auditRow(),
        auditRow({ id: 2, action: 'restore', target: 'snapshot-01', operator: 'ops01',
          detail: { reason: '误删书单后回滚' } }),
      ]) })
    })

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block).toContainText('admin')
    await expect(block).toContainText('cleanup · old_playlogs')
    await expect(block).toContainText('days=7 · count=3')
    await expect(block).toContainText('ops01')
    await expect(block.getByText('reason=误删书单后回滚')).toBeVisible()
    await expect(block).toContainText('2026-10-26 16:00:00')

    expect(asked.length).toBeGreaterThanOrEqual(1)
    for (const qs of asked) {
      expect(qs).toContain('category=maintenance')
      expect(qs).toContain('page_size=5')
    }
    await expect(block.getByText('该模块暂无审计记录')).toHaveCount(0)
  })

  test('读取失败：说「加载失败」并给重试，不说成暂无记录，也不抢全局 toast', async ({ page }) => {
    let fail = true
    await auditRoute(page, (route) =>
      route.fulfill({ json: fail ? { code: 50000, message: '审计日志读取失败', data: null } : auditList([auditRow()]) }))

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText('加载失败：审计日志读取失败')).toBeVisible()
    await expect(block.getByText('请求未成功，数据并未加载')).toBeVisible()
    await expect(block.getByText('该模块暂无审计记录')).toHaveCount(0)
    // silent 请求：失败只体现在组件自己的失败态里
    await expect(page.locator('.el-message')).toHaveCount(0)

    fail = false
    await block.getByRole('button', { name: '重试' }).click()
    await expect(block.getByText('cleanup · old_playlogs')).toBeVisible()
    await expect(block.getByText('加载失败：审计日志读取失败')).toHaveCount(0)
  })

  test('刷新按钮重新取数（不靠整页刷新）', async ({ page }) => {
    let calls = 0
    await auditRoute(page, (route) => {
      calls += 1
      return route.fulfill({
        json: auditList([auditRow({ id: calls, action: calls === 1 ? 'cleanup' : 'restore' })]),
      })
    })

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText('cleanup · old_playlogs')).toBeVisible()
    expect(calls).toBe(1)

    await block.getByRole('button', { name: '刷新' }).click()
    await expect(block.getByText('restore · old_playlogs')).toBeVisible()
    expect(calls).toBe(2)
  })

  test('后端脱敏值原样呈现，前端不再自行判断敏感字段', async ({ page }) => {
    await auditRoute(page, (route) =>
      route.fulfill({ json: auditList([auditRow({
        action: 'update_config',
        target: 'cos_config',
        detail: { secret_id: '***', secret_key: '***', bucket: 'news-prod' },
      })]) }))

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText(/\*\*\*/)).toBeVisible()
    await expect(block).not.toContainText('AKIA')
  })

  test('真·无记录才说暂无（与失败态是两件事）', async ({ page }) => {
    await auditRoute(page, (route) => route.fulfill({ json: auditList([]) }))

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText('该模块暂无审计记录')).toBeVisible()
    await expect(block.getByText('加载失败')).toHaveCount(0)
  })
})

test.describe('审核页审计块只读自己的 category（T02909）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('审核页请求 category=review，不串到 maintenance', async ({ page }) => {
    const asked = []
    await auditRoute(page, (route) => {
      asked.push(new URL(route.request().url()).searchParams.get('category'))
      return route.fulfill({ json: auditList([auditRow({ category: 'review', action: 'approve', target: 'wf-001' })]) })
    })

    await page.goto('/review')
    const block = page.locator('[data-guide="review-audit"]')
    await expect(block.getByText('approve · wf-001')).toBeVisible()
    expect(asked.every((c) => c === 'review')).toBe(true)
    expect(asked).not.toContain('maintenance')
  })
})
