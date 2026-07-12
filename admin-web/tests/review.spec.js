import { test, expect } from '@playwright/test'
import {
  setLoginState,
  reviewListResponse,
  reviewApprovedListResponse,
  reviewRejectedListResponse,
  reviewDetailResponse,
  reviewActionSuccessResponse,
} from './helpers/mock'

/**
 * 审核流程 E2E 测试
 *
 * 覆盖：
 * - 列表加载
 * - tab 切换
 * - 跳转详情
 * - 详情页展示
 * - 通过/打回操作
 */
test.describe('审核流程', () => {
  // 并行执行时 vite 首次编译各路由组件较慢，5s 默认超时不足
  test.use({ expect: { timeout: 15000 } })

  test.beforeEach(async ({ page }) => {
    // 直接注入登录态，跳过登录页，聚焦审核流程本身
    await setLoginState(page, 'admin')

    // 根据 status 查询参数返回不同列表数据，模拟后端按状态过滤
    await page.route('**/admin/api/v1/reviews*', async (route) => {
      const url = new URL(route.request().url())
      const status = url.searchParams.get('status')
      if (status === 'approved') {
        await route.fulfill({ json: reviewApprovedListResponse })
      } else if (status === 'rejected') {
        await route.fulfill({ json: reviewRejectedListResponse })
      } else {
        await route.fulfill({ json: reviewListResponse })
      }
    })

    // 详情页接口
    await page.route('**/admin/api/v1/reviews/1', async (route) => {
      await route.fulfill({ json: reviewDetailResponse })
    })

    // 审核操作接口
    await page.route('**/admin/api/v1/reviews/*/action', async (route) => {
      await route.fulfill({ json: reviewActionSuccessResponse })
    })
  })

  test('审核列表页加载', async ({ page }) => {
    await page.goto('/review')

    // 等待列表加载完成
    await expect(page.getByRole('tab', { name: '待审核' })).toBeVisible({ timeout: 15000 })
    // 表格应显示 mock 的两条数据
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('wf-002')).toBeVisible({ timeout: 15000 })
    // 状态标签
    await expect(page.getByText('待审核').first()).toBeVisible({ timeout: 15000 })
  })

  test('tab 切换加载不同状态列表', async ({ page }) => {
    await page.goto('/review')

    // 默认待审核 tab
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 15000 })

    // 切换到已通过 tab
    await page.getByRole('tab', { name: '已通过' }).click()
    await expect(page.getByText('wf-003')).toBeVisible({ timeout: 15000 })

    // 切换到已打回 tab
    await page.getByRole('tab', { name: '已打回' }).click()
    await expect(page.getByText('wf-004')).toBeVisible({ timeout: 15000 })
  })

  test('点击审核跳转详情页', async ({ page }) => {
    await page.goto('/review')

    // 点击第一行的审核按钮
    await page.getByRole('button', { name: '审核' }).first().click()

    // 应跳转到详情页
    await expect(page).toHaveURL(/\/review\/1$/, { timeout: 15000 })
  })

  test('审核详情页显示稿件和音频', async ({ page }) => {
    await page.goto('/review/1')

    // 头部信息
    await expect(page.getByText('2026-07-08').first()).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 15000 })

    // 稿件全文卡片
    await expect(page.getByText('稿件全文')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('这是第一条稿件内容。')).toBeVisible({ timeout: 15000 })

    // 引用素材链接
    await expect(page.getByRole('link', { name: 'https://source1.com' })).toBeVisible({ timeout: 15000 })

    // 音频试听卡片
    await expect(page.getByText('音频试听')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('audio')).toBeVisible({ timeout: 15000 })

    // 审核操作卡片
    await expect(page.getByText('审核操作')).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('radio', { name: '通过' })).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('radio', { name: '打回' })).toBeVisible({ timeout: 15000 })
  })

  test('通过审核操作', async ({ page }) => {
    await page.goto('/review/1')

    // 默认选中"通过"
    await expect(page.getByRole('radio', { name: '通过' })).toBeChecked({ timeout: 15000 })

    // 点击提交，触发确认弹窗
    await page.getByRole('button', { name: '提交' }).click()

    // ElMessageBox 二次确认（项目未配置中文 locale，默认按钮文本为 OK）
    await page.getByRole('button', { name: 'OK' }).click()

    // 操作成功后应跳回列表页
    await expect(page).toHaveURL(/\/review$/, { timeout: 15000 })
    // 应显示成功提示
    await expect(page.locator('.el-message').getByText('操作成功')).toBeVisible({ timeout: 15000 })
  })

  test('打回审核操作', async ({ page }) => {
    await page.goto('/review/1')

    // 切换到"打回"：Element Plus 的 el-radio input 被 .el-radio__inner 遮挡，
    // 直接 .check() 会因 pointer interception 失败，改点击 label 元素
    await page.locator('.el-radio').filter({ hasText: '打回' }).click()

    // 打回需要填写理由
    await page.getByPlaceholder('请输入理由').fill('内容质量不达标')

    await page.getByRole('button', { name: '提交' }).click()

    // ElMessageBox 二次确认（项目未配置中文 locale，默认按钮文本为 OK）
    await page.getByRole('button', { name: 'OK' }).click()

    // 操作成功跳回列表
    await expect(page).toHaveURL(/\/review$/, { timeout: 15000 })
    await expect(page.locator('.el-message').getByText('操作成功')).toBeVisible({ timeout: 15000 })
  })
})
