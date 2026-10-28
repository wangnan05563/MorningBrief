import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T03439：系统配置 →「用户管理」（后台账号）菜单与页面。
 *
 * 守四件 mock 里可判定的事：
 * 1. 菜单入口真实存在且能进页面，列表复用 ADMIN_ROLE 字典（不出现裸枚举）；
 * 2. 自己的账号不能重置口令/删除，编辑弹窗里角色与状态锁死（后端守卫的前端镜像）；
 * 3. 禁用确认必须说清会话边界（JWT 最长约 2 小时），不能承诺「立即下线」；
 * 4. 页面旁审计块只读 category=admin_user。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

const ACCOUNTS = [
  {
    id: 1,
    username: 'admin',
    nickname: '值班管理员',
    role: 'admin',
    status: 1,
    last_login_at: '2026-10-27T09:30:00',
    created_at: '2026-01-01T08:00:00',
    updated_at: null,
  },
  {
    id: 2,
    username: 'ops01',
    nickname: '夜班运营',
    role: 'operator',
    status: 1,
    last_login_at: null,
    created_at: '2026-05-06T10:00:00',
    updated_at: null,
  },
]

async function mockUsers(page) {
  const calls = []
  // 用正则而非 glob：glob 的 `*` 不跨 `/`，`/auth/users*` 匹配不到 `/auth/users/2`，
  // PUT/DELETE 会漏到 beforeEach 的兜底路由，导致「提交了但没记录」的假象。
  await page.route(/\/admin\/api\/v1\/auth\/users(\/|\?|$)/, async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const method = req.method()
    if (method === 'GET') {
      const keyword = url.searchParams.get('keyword') || ''
      const list = ACCOUNTS.filter(
        (a) => !keyword || a.username.includes(keyword) || (a.nickname || '').includes(keyword),
      )
      calls.push({ method, query: url.searchParams.toString() })
      return route.fulfill({ json: ok({ list, total: list.length, page: 1, size: 100 }) })
    }
    const body = req.postDataJSON()
    calls.push({ method, path: url.pathname, body })
    return route.fulfill({ json: ok({ ...ACCOUNTS[0], ...body }) })
  })
  return calls
}

async function mockAudit(page) {
  const asked = []
  await page.route(`${API}/audit-logs*`, (route) => {
    asked.push(new URL(route.request().url()).searchParams.get('category'))
    return route.fulfill({
      json: ok({
        items: [
          {
            id: 1,
            category: 'admin_user',
            action: 'create',
            target: 'ops01',
            operator: 'admin',
            detail: { role: 'operator', reason: '新增夜班' },
            created_at: '2026-10-27T10:00:00',
          },
        ],
        total: 1,
        page: 1,
        page_size: 5,
      }),
    })
  })
  return asked
}

test.describe('后台账号管理（T03439）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    // 兜底：Layout 挂载时的版本检查等旁路请求若落到真后端并拿到 401，
    // 拦截器会清本地态把人踢回登录页，页面用例就测不到本页。具体接口随后覆盖。
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('菜单入口可达，列表用字典文案而非裸枚举', async ({ page }) => {
    await mockUsers(page)
    await mockAudit(page)

    await page.goto('/system/users')
    await expect(page.locator('.sidebar').getByText('用户管理')).toBeVisible()

    const adminRow = page.locator('tr', { hasText: 'admin' })
    const opsRow = page.locator('tr', { hasText: 'ops01' })
    await expect(adminRow).toContainText('管理员')
    await expect(adminRow).toContainText('当前登录')
    await expect(opsRow).toContainText('运营')
    await expect(opsRow).toContainText('启用')
    await expect(page.locator('body')).not.toContainText('role=')
  })

  test('新增账号提交用户名/角色/初始口令与原因', async ({ page }) => {
    const calls = await mockUsers(page)
    await mockAudit(page)

    await page.goto('/system/users')
    await page.getByRole('button', { name: '新增账号' }).click()
    const dialog = page.locator('.el-dialog', { hasText: '新增后台账号' })
    await dialog.getByPlaceholder('3-32 位字母、数字或下划线').fill('reviewer_1')
    await dialog.getByPlaceholder('用于列表与审计展示（可选）').fill('审核一号')
    await dialog.getByPlaceholder('至少 8 位').fill('Init-Pass-123')
    await dialog.getByLabel('备注 / 原因（可选，会写入审计）').fill('新增夜班审核')
    await dialog.getByRole('button', { name: '创建' }).click()

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length).toBe(1)
    const posted = calls.find((c) => c.method === 'POST')
    expect(posted.body).toEqual({
      username: 'reviewer_1',
      nickname: '审核一号',
      role: 'operator',
      password: 'Init-Pass-123',
      reason: '新增夜班审核',
    })
  })

  test('自己的账号：重置/删除不可点，编辑弹窗锁死角色与状态', async ({ page }) => {
    await mockUsers(page)
    await mockAudit(page)

    await page.goto('/system/users')
    const adminRow = page.locator('tr', { hasText: 'admin' })
    await expect(adminRow.getByRole('button', { name: '重置口令' })).toBeDisabled()
    await expect(adminRow.getByRole('button', { name: '删除' })).toBeDisabled()

    await adminRow.getByRole('button', { name: '编辑' }).click()
    const dialog = page.locator('.el-dialog', { hasText: '编辑账号「admin」' })
    // EP 2.14 把 is-disabled 放在 el-select 的 wrapper 上，不是根节点
    await expect(dialog.locator('.el-select__wrapper')).toHaveClass(/is-disabled/)
    await expect(dialog.locator('.el-switch')).toHaveClass(/is-disabled/)
    await expect(dialog.getByText('不能修改自己的角色')).toBeVisible()
    await expect(dialog.getByText('不能禁用当前登录的账号')).toBeVisible()
  })

  test('禁用确认说清会话边界，并提交 status=0', async ({ page }) => {
    const calls = await mockUsers(page)
    await mockAudit(page)

    await page.goto('/system/users')
    await page.locator('tr', { hasText: 'ops01' }).getByRole('button', { name: '禁用' }).click()

    const box = page.locator('.el-message-box')
    await expect(box).toContainText('约 2 小时')
    await expect(box).not.toContainText('立即下线')
    await box.getByRole('button', { name: '确认禁用' }).click()

    await expect.poll(() => calls.filter((c) => c.method === 'PUT').length).toBe(1)
    const put = calls.find((c) => c.method === 'PUT')
    expect(put.path).toMatch(/\/auth\/users\/2$/)
    expect(put.body).toMatchObject({ status: 0 })
  })

  test('审计块只读 category=admin_user', async ({ page }) => {
    await mockUsers(page)
    const asked = await mockAudit(page)

    await page.goto('/system/users')
    const block = page.locator('[data-guide="admin-user-audit"]')
    await expect(block).toContainText('create · ops01')
    await expect(block).toContainText('reason=新增夜班')
    expect(asked.length).toBeGreaterThanOrEqual(1)
    expect(asked.every((c) => c === 'admin_user')).toBe(true)
  })
})
