import { test, expect } from '@playwright/test'
import {
  setLoginState,
  channelsListResponse,
  channelCreateSuccessResponse,
  queueActionSuccessResponse,
} from './helpers/mock'

/**
 * 频道管理页 E2E 测试
 *
 * 覆盖 SRS 10.2 要求：
 * - 列表加载
 * - 新增频道（含表单校验）
 * - 编辑频道
 * - 删除频道（含二次确认）
 * - 启用/停用切换
 * - RBAC：operator 无增删改按钮
 */
test.describe('频道管理', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    // 频道列表 + 单频道操作：glob 的 * 不匹配 /，需用 ** 覆盖子路径
    // GET /channels          → 列表
    // POST /channels         → 新增
    // PUT /channels/{id}     → 编辑/切换
    // DELETE /channels/{id}  → 删除
    await page.route('**/admin/api/v1/channels**', async (route) => {
      const method = route.request().method()
      if (method === 'GET') {
        await route.fulfill({ json: channelsListResponse })
      } else {
        await route.fulfill({ json: channelCreateSuccessResponse })
      }
    })
  })

  test('列表加载显示频道', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    await expect(page.getByText('频道管理').first()).toBeVisible({ timeout: 30000 })
    // 表格应展示 mock 数据
    await expect(page.getByText('科技频道')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('财经频道')).toBeVisible({ timeout: 30000 })
  })

  test('admin 显示新增按钮', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    await expect(page.getByRole('button', { name: '新增频道' })).toBeVisible({ timeout: 30000 })
  })

  test('operator 无新增与操作按钮', async ({ page }) => {
    await setLoginState(page, 'operator')
    await page.goto('/channels')

    // operator 不应看到新增按钮
    await expect(page.getByRole('button', { name: '新增频道' })).toHaveCount(0, { timeout: 30000 })
    // 也不应看到编辑/删除按钮
    await expect(page.getByRole('button', { name: '编辑' })).toHaveCount(0, { timeout: 30000 })
    await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0, { timeout: 30000 })
  })

  test('新增频道表单校验', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    await page.getByRole('button', { name: '新增频道' }).click()

    // 弹窗显示
    await expect(page.locator('.el-dialog').filter({ hasText: '新增频道' })).toBeVisible({ timeout: 30000 })

    // 直接点确认，触发 required 校验
    await page.getByRole('button', { name: '确认' }).click()
    // Element Plus 表单校验提示
    await expect(page.getByText('请输入频道名称')).toBeVisible({ timeout: 30000 })
  })

  test('新增频道成功', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    await page.getByRole('button', { name: '新增频道' }).click()
    await expect(page.locator('.el-dialog').filter({ hasText: '新增频道' })).toBeVisible({ timeout: 30000 })

    // 填写表单
    await page.getByPlaceholder('请输入频道名称').fill('体育频道')
    await page.getByPlaceholder('频道描述（选填）').fill('体育赛事')

    // 捕获 POST 请求
    const createRequest = page.waitForRequest(
      (req) => req.url().includes('/channels') && req.method() === 'POST'
    )
    await page.getByRole('button', { name: '确认' }).click()
    const request = await createRequest
    const body = JSON.parse(request.postData())
    expect(body.name).toBe('体育频道')
    expect(body.description).toBe('体育赛事')

    // 成功提示（后端代码实际消息为"已创建"）
    await expect(page.locator('.el-message').getByText('已创建')).toBeVisible({ timeout: 30000 })
  })

  test('编辑频道预填数据', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    // 点击第一行的编辑按钮
    await page.getByRole('button', { name: '编辑' }).first().click()

    // 弹窗标题应为"编辑频道"
    await expect(page.locator('.el-dialog').filter({ hasText: '编辑频道' })).toBeVisible({ timeout: 30000 })
    // 名称应预填"科技频道"
    await expect(page.getByPlaceholder('请输入频道名称')).toHaveValue('科技频道', { timeout: 30000 })
  })

  test('删除频道二次确认', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    // 等待表格加载完成
    await expect(page.getByText('科技频道')).toBeVisible({ timeout: 30000 })

    // 点击删除
    await page.getByRole('button', { name: '删除' }).first().click()

    // ElMessageBox 二次确认：消息含频道名，用部分文本匹配避免特殊字符问题
    await expect(page.locator('.el-message-box').getByText(/确认删除频道/)).toBeVisible({ timeout: 30000 })
    // 确认按钮文本为"确认删除"（handleDelete 中 confirmButtonText 指定）
    await page.locator('.el-message-box').getByRole('button', { name: '确认删除' }).click()

    // 成功提示（后端代码实际消息为"已删除"）
    await expect(page.locator('.el-message').getByText('已删除')).toBeVisible({ timeout: 30000 })
  })

  test('启用/停用切换', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    // 等待表格加载完成
    await expect(page.getByText('科技频道')).toBeVisible({ timeout: 30000 })

    // 捕获 PUT 请求验证切换被触发（比消息提示更稳定）
    const toggleRequest = page.waitForRequest(
      (req) => req.url().includes('/channels/') && req.method() === 'PUT'
    )

    // 点击第一个 switch
    await page.locator('.el-switch').first().click()

    const request = await toggleRequest
    const body = JSON.parse(request.postData())
    // 验证请求体含 is_active 字段
    expect(body).toHaveProperty('is_active')

    // 成功提示（用 first 避免匹配到前序测试残留的 el-message）
    await expect(page.locator('.el-message').getByText(/已禁用|已启用/).first()).toBeVisible({ timeout: 30000 })
  })
})
