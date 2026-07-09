import { test, expect } from '@playwright/test'
import {
  setLoginState,
  workflowListResponse,
  workflowDetailResponse,
  workflowTriggerResponse,
} from './helpers/mock'

/**
 * 工作流监控 E2E 测试
 *
 * 覆盖：
 * - 列表加载
 * - 非 admin 不显示触发按钮（RBAC）
 * - 跳转详情
 * - 详情页步骤展示
 */
test.describe('工作流监控', () => {
  // 并行执行时 vite 首次编译各路由组件较慢，5s 默认超时不足
  test.use({ expect: { timeout: 15000 } })

  test.beforeEach(async ({ page }) => {
    // 工作流列表接口：glob 尾部需带 * 以匹配查询参数 ?page=1&size=20
    await page.route('**/admin/api/v1/workflows*', async (route) => {
      await route.fulfill({ json: workflowListResponse })
    })

    // 工作流详情接口
    await page.route('**/admin/api/v1/workflows/wf-001', async (route) => {
      await route.fulfill({ json: workflowDetailResponse })
    })

    // 触发接口
    await page.route('**/admin/api/v1/workflows/trigger', async (route) => {
      await route.fulfill({ json: workflowTriggerResponse })
    })
  })

  test('工作流列表加载', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows')

    await expect(page.getByText('工作流监控').first()).toBeVisible()
    // 表格应展示 mock 数据
    await expect(page.getByText('wf-001')).toBeVisible()
    await expect(page.getByText('wf-002')).toBeVisible()
    // 状态标签
    await expect(page.locator('.el-tag').filter({ hasText: '成功' })).toBeVisible()
    await expect(page.locator('.el-tag').filter({ hasText: '运行中' })).toBeVisible()
  })

  test('非 admin 不显示触发按钮', async ({ page }) => {
    // operator 角色访问工作流列表页
    // 注意：路由守卫对 requireRole === 'admin' 拒绝跳转，但仅作用于 /workflows 路由
    // 这里直接访问，验证 v-if="userStore.isAdmin" 不渲染按钮
    await setLoginState(page, 'operator')
    await page.goto('/workflows')

    // 由于 operator 角色无权访问工作流路由，会被守卫拦截
    // 但即便访问成功，也不应看到"手动触发"按钮
    await expect(page.getByRole('button', { name: '手动触发' })).toHaveCount(0)
  })

  test('admin 显示触发按钮并可触发', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows')

    // admin 应看到触发按钮
    await expect(page.getByRole('button', { name: '手动触发' })).toBeVisible()

    // 点击触发
    await page.getByRole('button', { name: '手动触发' }).click()
    // ElMessageBox 二次确认（项目未配置中文 locale，默认按钮文本为 OK）
    await page.getByRole('button', { name: 'OK' }).click()

    // 应显示成功提示，包含新工作流 ID
    await expect(page.locator('.el-message').getByText('已触发，工作流 ID: wf-003')).toBeVisible()
  })

  test('点击工作流跳转详情', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows')

    // 点击工作流 ID 链接
    // Element Plus 的 el-link 渲染为 generic 元素而非 link role，故用 .el-link 类定位
    await page.locator('.el-link').filter({ hasText: 'wf-001' }).click()

    // 应跳转到详情页
    await expect(page).toHaveURL(/\/workflows\/wf-001$/)
  })

  test('工作流详情显示步骤', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows/wf-001')

    await expect(page.getByText('工作流详情').first()).toBeVisible()

    // 基础信息
    await expect(page.getByText('wf-001').first()).toBeVisible()
    await expect(page.getByText('2026-07-08').first()).toBeVisible()
    // 详情页有 1 个工作流状态 tag + 5 个步骤状态 tag 都可能显示"成功"，存在 strict mode 冲突，取第一个即可
    await expect(page.locator('.el-tag').filter({ hasText: '成功' }).first()).toBeVisible()

    // 5 个步骤标签应出现在进度条中
    // 详情页步骤名同时出现在 el-step 标题、表格单元格、tooltip 等多处，getByText 会命中多个节点触发 strict mode，取 .first()
    await expect(page.getByText('爬虫采集').first()).toBeVisible()
    await expect(page.getByText('LLM改写').first()).toBeVisible()
    await expect(page.getByText('语音合成').first()).toBeVisible()
    await expect(page.getByText('音频拼接').first()).toBeVisible()
    await expect(page.getByText('创建审核').first()).toBeVisible()

    // 步骤详情表格也应展示这些步骤名
    const crawlCells = page.locator('td').filter({ hasText: '爬虫采集' })
    await expect(crawlCells.first()).toBeVisible()
  })
})
