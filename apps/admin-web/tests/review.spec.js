import { test, expect } from '@playwright/test'
import {
  setLoginState,
  reviewListResponse,
  reviewApprovedListResponse,
  reviewRejectedListResponse,
  reviewDetailResponse,
  reviewActionSuccessResponse,
  reviewBatchActionSuccessResponse,
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
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

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

    // 批量审核操作接口：路径含 batch-action，需在通配符路由之前注册
    await page.route('**/admin/api/v1/reviews/batch-action', async (route) => {
      await route.fulfill({ json: reviewBatchActionSuccessResponse })
    })
  })

  test('审核列表页加载', async ({ page }) => {
    await page.goto('/review')

    // 等待列表加载完成
    await expect(page.getByRole('tab', { name: '待审核' })).toBeVisible({ timeout: 30000 })
    // 表格应显示 mock 的两条数据
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('wf-002')).toBeVisible({ timeout: 30000 })
    // 状态标签
    await expect(page.getByText('待审核').first()).toBeVisible({ timeout: 30000 })
  })

  test('tab 切换加载不同状态列表', async ({ page }) => {
    await page.goto('/review')

    // 默认待审核 tab
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })

    // 切换到已通过 tab
    await page.getByRole('tab', { name: '已通过' }).click()
    await expect(page.getByText('wf-003')).toBeVisible({ timeout: 30000 })

    // 切换到已打回 tab
    await page.getByRole('tab', { name: '已打回' }).click()
    await expect(page.getByText('wf-004')).toBeVisible({ timeout: 30000 })
  })

  test('点击审核跳转详情页', async ({ page }) => {
    await page.goto('/review')

    // 点击第一行的审核按钮
    await page.getByRole('button', { name: '审核' }).first().click()

    // 应跳转到详情页
    await expect(page).toHaveURL(/\/review\/1$/, { timeout: 30000 })
  })

  test('审核详情页显示稿件和音频', async ({ page }) => {
    await page.goto('/review/1')

    // 头部信息
    await expect(page.getByText('2026-07-08').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })

    // 稿件全文卡片
    await expect(page.getByText('稿件全文')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('这是第一条稿件内容。')).toBeVisible({ timeout: 30000 })

    // 引用素材链接
    await expect(page.getByRole('link', { name: 'https://source1.com' })).toBeVisible({ timeout: 30000 })

    // 音频试听卡片
    await expect(page.getByText('音频试听')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('audio')).toBeVisible({ timeout: 30000 })

    // 审核操作卡片
    await expect(page.getByText('审核操作')).toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('radio', { name: '通过' })).toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('radio', { name: '打回' })).toBeVisible({ timeout: 30000 })
  })

  test('通过审核操作', async ({ page }) => {
    await page.goto('/review/1')

    // 默认选中"通过"
    await expect(page.getByRole('radio', { name: '通过' })).toBeChecked({ timeout: 30000 })

    // 点击提交，触发确认弹窗
    await page.getByRole('button', { name: '提交' }).click()

    // ElMessageBox 二次确认（项目未配置中文 locale，默认按钮文本为 OK）
    await page.getByRole('button', { name: 'OK' }).click()

    // 操作成功后应跳回列表页
    await expect(page).toHaveURL(/\/review$/, { timeout: 30000 })
    // 应显示成功提示
    await expect(page.locator('.el-message').getByText('操作成功')).toBeVisible({ timeout: 30000 })
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
    await expect(page).toHaveURL(/\/review$/, { timeout: 30000 })
    await expect(page.locator('.el-message').getByText('操作成功')).toBeVisible({ timeout: 30000 })
  })

  // ============ 批量审批测试 ============

  test('批量通过：勾选后显示批量操作栏', async ({ page }) => {
    await page.goto('/review')

    // 等待列表加载
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })

    // 批量操作栏在待审核 tab 下应可见
    await expect(page.getByText('批量通过')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('批量打回')).toBeVisible({ timeout: 30000 })

    // 初始未选中时按钮 disabled
    await expect(page.getByRole('button', { name: '批量通过' })).toBeDisabled({ timeout: 30000 })

    // 勾选第一行（el-table selection checkbox）
    await page.locator('.el-table__body .el-checkbox').first().click()

    // 已选数量显示
    await expect(page.getByText('已选 1 条')).toBeVisible({ timeout: 30000 })

    // 按钮变为可用
    await expect(page.getByRole('button', { name: '批量通过' })).toBeEnabled({ timeout: 30000 })
  })

  test('批量通过：成功提交后显示统计提示', async ({ page }) => {
    await page.goto('/review')

    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })

    // 勾选两行
    await page.locator('.el-table__body .el-checkbox').nth(0).click()
    await page.locator('.el-table__body .el-checkbox').nth(1).click()

    await expect(page.getByText('已选 2 条')).toBeVisible({ timeout: 30000 })

    // 点击批量通过
    await page.getByRole('button', { name: '批量通过' }).click()

    // ElMessageBox 二次确认
    await expect(page.getByText('批量通过确认')).toBeVisible({ timeout: 30000 })
    await page.getByRole('button', { name: '确定' }).click()

    // 成功提示：mock 返回 2 条成功
    await expect(page.locator('.el-message').getByText(/批量通过完成/)).toBeVisible({ timeout: 30000 })
  })

  test('批量打回：需填写理由后才能提交', async ({ page }) => {
    await page.goto('/review')

    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })

    // 勾选第一行
    await page.locator('.el-table__body .el-checkbox').first().click()

    // 点击批量打回
    await page.getByRole('button', { name: '批量打回' }).click()

    // 弹出 prompt 输入理由
    await expect(page.getByText('批量打回确认')).toBeVisible({ timeout: 30000 })

    // 输入理由
    await page.getByPlaceholder('请输入打回理由').fill('批量打回：内容质量不达标')

    // 点击确定
    await page.getByRole('button', { name: '确定' }).click()

    // 成功提示
    await expect(page.locator('.el-message').getByText(/批量打回完成/)).toBeVisible({ timeout: 30000 })
  })

  test('切换到非待审核 tab 时不显示批量操作栏', async ({ page }) => {
    await page.goto('/review')

    // 默认在待审核 tab，批量按钮可见
    await expect(page.getByRole('button', { name: '批量通过' })).toBeVisible({ timeout: 30000 })

    // 切换到已通过 tab
    await page.getByRole('tab', { name: '已通过' }).click()

    // 等待列表加载
    await expect(page.getByText('wf-003')).toBeVisible({ timeout: 30000 })

    // 已通过 tab 不应显示批量按钮
    await expect(page.getByRole('button', { name: '批量通过' })).toBeHidden({ timeout: 30000 })
    await expect(page.getByRole('button', { name: '批量打回' })).toBeHidden({ timeout: 30000 })
  })
})
