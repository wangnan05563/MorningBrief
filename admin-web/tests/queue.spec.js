import { test, expect } from '@playwright/test'
import {
  setLoginState,
  queueStatsResponse,
  queueConfigResponse,
  queueTasksResponse,
  queueActionSuccessResponse,
  channelsListResponse,
} from './helpers/mock'

/**
 * 队列管理页 E2E 测试
 *
 * 覆盖 SRS 10.2 要求：
 * - 页面加载（统计卡片 + 任务列表 + 配置面板）
 * - 筛选（状态/频道/优先级）
 * - 取消排队任务
 * - 改优先级
 * - 重试失败任务
 * - 保存配置
 * - 详情抽屉
 * - RBAC：operator 仅可查看详情
 */
test.describe('队列管理', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    // mock SSE 连接：QueueManagement 会发起 SSE 连接，后端未运行时 ECONNREFUSED 导致 flaky
    await page.route('**/admin/api/v1/events/stream**', async (route) => {
      // SSE 返回空的事件流，避免连接错误
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: '',
      })
    })
    // 队列统计
    await page.route('**/admin/api/v1/queue/stats', async (route) => {
      await route.fulfill({ json: queueStatsResponse })
    })
    // 队列配置
    await page.route('**/admin/api/v1/queue/config', async (route) => {
      await route.fulfill({ json: queueConfigResponse })
    })
    // 任务列表（含查询参数）
    await page.route('**/admin/api/v1/queue/tasks*', async (route) => {
      await route.fulfill({ json: queueTasksResponse })
    })
    // 频道列表（筛选下拉用）
    await page.route('**/admin/api/v1/channels*', async (route) => {
      await route.fulfill({ json: channelsListResponse })
    })
    // 队列操作（取消/改优先级/重试）路径为 tasks/{id}/{action}，
    // glob 需用 ** 匹配多级子路径
    await page.route('**/admin/api/v1/queue/tasks/**', async (route) => {
      await route.fulfill({ json: queueActionSuccessResponse })
    })
  })

  test('页面加载显示统计与任务列表', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 统计卡片：等待中 3 / 执行中 1 / 已完成 10 / 失败 2
    await expect(page.locator('.stat-queued .stat-value')).toHaveText('3', { timeout: 30000 })
    await expect(page.locator('.stat-running .stat-value')).toHaveText('1', { timeout: 30000 })
    await expect(page.locator('.stat-success .stat-value')).toHaveText('10', { timeout: 30000 })
    await expect(page.locator('.stat-failed .stat-value')).toHaveText('2', { timeout: 30000 })

    // 任务表格应展示 mock 数据：channel_name 列应显示频道名（验证字段对齐）
    await expect(page.getByText('科技频道').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('财经频道').first()).toBeVisible({ timeout: 30000 })
    // 状态标签
    await expect(page.locator('.el-tag').filter({ hasText: '等待中' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.el-tag').filter({ hasText: '失败' })).toBeVisible({ timeout: 30000 })
  })

  test('配置面板加载默认串行模式', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 串行模式 radio 选中
    await expect(page.locator('input[value="serial"]')).toBeChecked({ timeout: 30000 })
    // 并行模式未选中
    await expect(page.locator('input[value="parallel"]')).not.toBeChecked({ timeout: 30000 })
    // 串行模式下不显示并发数 slider
    await expect(page.locator('.concurrency-slider')).toHaveCount(0, { timeout: 30000 })
  })

  test('切换并行模式显示并发数滑块', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 切换到并行
    await page.locator('label').filter({ hasText: '并行' }).click()
    // 并发数 slider 应出现
    await expect(page.locator('.concurrency-slider')).toBeVisible({ timeout: 30000 })
  })

  test('保存配置调用正确接口', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 切换并行 + 设置并发数
    await page.locator('label').filter({ hasText: '并行' }).click()

    // 捕获 PUT 请求体
    const configRequest = page.waitForRequest(
      (req) => req.url().includes('/queue/config') && req.method() === 'PUT'
    )
    await page.getByRole('button', { name: '保存配置' }).click()
    const request = await configRequest
    const body = JSON.parse(request.postData())
    // 验证前端发送的字段名与后端期望一致（execution_mode / max_concurrent）
    expect(body.execution_mode).toBe('parallel')
    expect(body.max_concurrent).toBeDefined()

    // 成功提示
    await expect(page.locator('.el-message').getByText('配置已保存')).toBeVisible({ timeout: 30000 })
  })

  test('取消排队任务', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 第一行是 queued 状态，应有取消按钮
    await page.getByRole('button', { name: '取消' }).first().click()
    // ElMessageBox 确认
    await page.getByRole('button', { name: 'OK' }).click()

    // 成功提示
    await expect(page.locator('.el-message').getByText('已取消')).toBeVisible({ timeout: 30000 })
  })

  test('改优先级', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 点击改优先级按钮打开 popover（每行都有，用 first）
    await page.getByRole('button', { name: '改优先级' }).first().click()
    // popover 内确定按钮：用 visible 过滤避免匹配未打开的 popover
    await page.locator('.priority-popover button', { hasText: '确定' }).first().click()

    // 成功提示
    await expect(page.locator('.el-message').getByText('优先级已更新')).toBeVisible({ timeout: 30000 })
  })

  test('重试失败任务', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 第二行是 failed 状态，重试按钮
    await page.getByRole('button', { name: '重试' }).click()
    // ElMessageBox 确认
    await page.getByRole('button', { name: 'OK' }).click()

    // 成功提示：QueueManagement.vue handleRetry 实际文案
    await expect(page.locator('.el-message').getByText('已从失败步骤断点续跑，原工作流已重新入队')).toBeVisible({ timeout: 30000 })
  })

  test('详情抽屉显示任务信息', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/queue')

    // 点击详情按钮
    await page.getByRole('button', { name: '详情' }).first().click()

    // 抽屉应可见
    await expect(page.locator('.el-drawer')).toBeVisible({ timeout: 30000 })
    // 抽屉标题
    await expect(page.locator('.el-drawer__title')).toHaveText('任务详情', { timeout: 30000 })
    // 任务 ID 应显示在描述列表中
    await expect(page.locator('.el-descriptions').getByText('wf-20260708-0001')).toBeVisible({ timeout: 30000 })
  })

  test('operator 仅可查看详情，无操作按钮', async ({ page }) => {
    await setLoginState(page, 'operator')
    await page.goto('/queue')

    // operator 不应看到取消/改优先级/重试按钮
    await expect(page.getByRole('button', { name: '取消' })).toHaveCount(0, { timeout: 30000 })
    await expect(page.getByRole('button', { name: '改优先级' })).toHaveCount(0, { timeout: 30000 })
    await expect(page.getByRole('button', { name: '重试' })).toHaveCount(0, { timeout: 30000 })
    // 但应看到详情按钮
    await expect(page.getByRole('button', { name: '详情' }).first()).toBeVisible({ timeout: 30000 })
  })
})
