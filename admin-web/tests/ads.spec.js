import { test, expect } from '@playwright/test'
import {
  setLoginState,
  adMaterialsListResponse,
  adMaterialCreateSuccessResponse,
  adPlacementsListResponse,
  adPlacementCreateSuccessResponse,
  adScheduleResponse,
} from './helpers/mock'

/**
 * 广告管理 E2E 测试
 *
 * 覆盖：
 * - 素材列表
 * - 新建素材对话框
 * - 投放规则列表
 * - 新建投放对话框
 * - 排期日历
 */
test.describe('广告管理', () => {
  // 并行执行时 vite 首次编译各路由组件较慢，5s 默认超时不足
  test.use({ expect: { timeout: 15000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')

    // 素材列表：列表页和新建投放对话框都会调用
    await page.route('**/admin/api/v1/ads/materials*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ json: adMaterialsListResponse })
      } else if (route.request().method() === 'POST') {
        await route.fulfill({ json: adMaterialCreateSuccessResponse })
      } else {
        await route.continue()
      }
    })

    // 投放规则列表
    await page.route('**/admin/api/v1/ads/placements*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ json: adPlacementsListResponse })
      } else if (route.request().method() === 'POST') {
        await route.fulfill({ json: adPlacementCreateSuccessResponse })
      } else {
        await route.continue()
      }
    })

    // 排期日历
    await page.route('**/admin/api/v1/ads/schedule*', async (route) => {
      await route.fulfill({ json: adScheduleResponse })
    })
  })

  test('素材列表加载', async ({ page }) => {
    await page.goto('/ads/materials')

    await expect(page.getByRole('heading', { name: '广告素材管理' })).toBeVisible()
    // 表格应展示 mock 数据
    await expect(page.getByText('品牌广告A')).toBeVisible()
    await expect(page.getByText('促销广告B')).toBeVisible()
    // 默认素材应有"默认"标签
    await expect(page.locator('.el-tag').filter({ hasText: '默认' })).toBeVisible()
  })

  test('新建素材对话框', async ({ page }) => {
    await page.goto('/ads/materials')

    await page.getByRole('button', { name: '新增素材' }).click()

    // 对话框打开
    await expect(page.getByRole('dialog', { name: '新增素材' })).toBeVisible()
    await expect(page.getByPlaceholder('请输入素材名称')).toBeVisible()
    await expect(page.getByPlaceholder('音频文件的访问地址')).toBeVisible()

    // 填写表单
    await page.getByPlaceholder('请输入素材名称').fill('新广告素材')
    await page.getByPlaceholder('音频文件的访问地址').fill('https://example.com/new.mp3')

    // 提交
    await page.getByRole('button', { name: '确定' }).click()

    // 应显示成功提示
    await expect(page.locator('.el-message').getByText('创建成功')).toBeVisible()
  })

  test('投放规则列表', async ({ page }) => {
    await page.goto('/ads/placements')

    await expect(page.getByRole('heading', { name: '投放规则管理' })).toBeVisible()
    // 表格展示 mock 数据
    await expect(page.getByText('品牌广告A')).toBeVisible()
    await expect(page.getByText('促销广告B')).toBeVisible()
    // 广告位标签
    await expect(page.locator('.el-tag').filter({ hasText: '开头' })).toBeVisible()
    await expect(page.locator('.el-tag').filter({ hasText: '中间' })).toBeVisible()
  })

  test('新建投放对话框', async ({ page }) => {
    await page.goto('/ads/placements')

    await page.getByRole('button', { name: '新建投放' }).click()

    // 对话框打开
    await expect(page.getByRole('dialog', { name: '新建投放' })).toBeVisible()
    // 表单字段存在
    // Element Plus 的 el-select / el-date-picker 将 placeholder 渲染为文本节点而非 input 的 placeholder 属性，
    // 故不能用 getByPlaceholder；这里用 combobox role + accessible name（label 文本）来定位
    await expect(page.getByRole('combobox', { name: '* 素材' })).toBeVisible()
    await expect(page.getByRole('combobox', { name: '* 广告位' })).toBeVisible()
    await expect(page.getByRole('combobox', { name: '* 日期范围' })).toBeVisible()
  })

  test('排期日历显示', async ({ page }) => {
    await page.goto('/ads/schedule')

    await expect(page.getByRole('heading', { name: '排期日历' })).toBeVisible()

    // 图例显示
    await expect(page.getByText('开头（head）')).toBeVisible()
    await expect(page.getByText('中间（mid）')).toBeVisible()
    await expect(page.getByText('结尾（tail）')).toBeVisible()

    // el-calendar 渲染后应能看到月份标题
    await expect(page.locator('.el-calendar__title')).toBeVisible()

    // mock 数据中"品牌广告A"覆盖整个月，应在日历单元格中显示
    await expect(page.locator('.slot-name').filter({ hasText: '品牌广告A' }).first()).toBeVisible()
  })
})
