import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02928：频道级最短时长（min_duration_sec）管理端入口
 *
 * 这条字段驱动自动扩稿与拼接下限，但改前管理端 0 处命中：创建/编辑表单都没有输入项，
 * 后端 `ChannelUpdateRequest` 也不声明该字段——只能在数据库维护页手改。
 *
 * 本 spec 用真实浏览器走一遍运营动作：改值 → 保存 → **重开弹窗**，断言显示的是新值
 * （防「前端回显旧列表对象」），并断言「取消勾选 = 显式提交 null」的清除语义。
 */

const CHANNEL = {
  id: 7,
  name: '听书频道',
  description: '有声读物',
  is_active: 1,
  channel_type: 'audiobook',
  min_duration_sec: null,
}

async function mockChannels(page, row) {
  const state = { row: { ...row } }
  await page.route('**/admin/api/v1/channels**', async (route) => {
    const req = route.request()
    if (req.method() === 'GET') {
      await route.fulfill({ json: { code: 0, message: 'success', data: [state.row] } })
      return
    }
    if (req.method() === 'PUT') {
      state.row = { ...state.row, ...JSON.parse(req.postData() || '{}') }
      await route.fulfill({ json: { code: 0, message: 'success', data: state.row } })
      return
    }
    await route.fulfill({ json: { code: 0, message: 'success', data: state.row } })
  })
  return state
}

function minDurationItem(dialog) {
  return dialog.locator('.el-form-item').filter({ hasText: '最短时长（秒）' })
}

async function openAudioTab(page) {
  await page.getByRole('button', { name: '编辑' }).first().click()
  const dialog = page.locator('.el-dialog').filter({ hasText: '编辑频道' })
  await expect(dialog).toBeVisible({ timeout: 30000 })
  await dialog.locator('.el-tabs__item').filter({ hasText: '音频与 BGM' }).click()
  return dialog
}

test.describe('频道最短时长（T02928）', () => {
  test.use({ expect: { timeout: 30000 } })

  test('编辑填 900 → 保存 → 重开显示 900', async ({ page }) => {
    const state = await mockChannels(page, CHANNEL)
    await setLoginState(page, 'admin')
    await page.goto('/channels')
    await expect(page.getByText('听书频道')).toBeVisible({ timeout: 30000 })

    const dialog = await openAudioTab(page)
    const item = minDurationItem(dialog)
    // 未配置的频道：不勾选「自定义」时不渲染输入框，提示必须说清留空会发生什么
    await expect(item.getByText('自定义最短时长')).toBeVisible()
    await expect(item.getByRole('spinbutton')).toHaveCount(0)
    await expect(item.getByText(/留空\/取消勾选 = 按频道类型动态默认/)).toBeVisible()

    await item.getByText('自定义最短时长').click()
    await item.getByRole('spinbutton').fill('900')

    const putRequest = page.waitForRequest(
      (req) => req.url().includes('/channels/') && req.method() === 'PUT'
    )
    await page.getByRole('button', { name: '确认' }).click()
    expect(JSON.parse((await putRequest).postData()).min_duration_sec).toBe(900)
    await expect(page.locator('.el-message').getByText('已更新')).toBeVisible()
    await expect(dialog).toBeHidden()

    // 重开：列表已刷新，表单必须回填新值而不是空白
    const reopened = await openAudioTab(page)
    const reopenedItem = minDurationItem(reopened)
    await expect(reopenedItem.getByRole('spinbutton')).toHaveValue('900')
    await expect(reopenedItem.locator('.el-checkbox').first()).toHaveClass(/is-checked/)
    expect(state.row.min_duration_sec).toBe(900)
  })

  test('取消勾选 → 显式提交 null（清除覆盖），重开显示未配置', async ({ page }) => {
    const state = await mockChannels(page, { ...CHANNEL, min_duration_sec: 900 })
    await setLoginState(page, 'admin')
    await page.goto('/channels')
    await expect(page.getByText('听书频道')).toBeVisible({ timeout: 30000 })

    const dialog = await openAudioTab(page)
    const item = minDurationItem(dialog)
    await expect(item.getByRole('spinbutton')).toHaveValue('900')

    await item.getByText('自定义最短时长').click()
    await expect(item.getByRole('spinbutton')).toHaveCount(0)
    const putRequest = page.waitForRequest(
      (req) => req.url().includes('/channels/') && req.method() === 'PUT'
    )
    await page.getByRole('button', { name: '确认' }).click()
    const body = JSON.parse((await putRequest).postData())
    expect(body).toHaveProperty('min_duration_sec', null)
    await expect(page.locator('.el-message').getByText('已更新')).toBeVisible()

    const reopened = await openAudioTab(page)
    const reopenedItem = minDurationItem(reopened)
    await expect(reopenedItem.getByRole('spinbutton')).toHaveCount(0)
    await expect(reopenedItem.locator('.el-checkbox').first()).not.toHaveClass(/is-checked/)
    expect(state.row.min_duration_sec).toBeNull()
  })

  test('新增表单同样可配置（POST 携带 min_duration_sec）', async ({ page }) => {
    await mockChannels(page, CHANNEL)
    await setLoginState(page, 'admin')
    await page.goto('/channels')

    await page.getByRole('button', { name: '新增频道' }).click()
    const dialog = page.locator('.el-dialog').filter({ hasText: '新增频道' })
    await expect(dialog).toBeVisible({ timeout: 30000 })
    await page.getByPlaceholder('请输入频道名称').fill('新听书频道')
    await dialog.locator('.el-tabs__item').filter({ hasText: '音频与 BGM' }).click()

    const item = minDurationItem(dialog)
    // 新增模式默认不勾选 → 提交 null，与提示一致
    await expect(item.getByText('自定义最短时长')).toBeVisible()
    await item.getByText('自定义最短时长').click()
    await item.getByRole('spinbutton').fill('1200')

    const postRequest = page.waitForRequest(
      (req) => req.url().endsWith('/channels') && req.method() === 'POST'
    )
    await page.getByRole('button', { name: '确认' }).click()
    expect(JSON.parse((await postRequest).postData()).min_duration_sec).toBe(1200)
    await expect(page.locator('.el-message').getByText('已创建')).toBeVisible()
  })
})
