import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02927（D24 派生）投放重叠裁决
 *
 * 裁决为「同一广告位同一时段只允许一条启用中的投放」。本 spec 验证两件事：
 * - 新建被后端拒绝时，表单里必须点名冲突的素材与区间，不能只剩一句通用报错；
 * - 把旧的重新启用同样会被拒，开关回弹且提示里点名在投的那条。
 */

function materialsResponse() {
  return {
    code: 0,
    message: 'success',
    data: {
      total: 1,
      list: [
        {
          id: 1,
          name: '品牌广告A',
          description: '品牌宣传音频',
          duration: 15,
          file_url: 'https://example.com/ads/a.mp3',
          is_default: true,
        },
      ],
    },
  }
}

function placementsResponse() {
  return {
    code: 0,
    message: 'success',
    data: {
      total: 2,
      list: [
        {
          id: 1,
          material_id: 1,
          material_name: '品牌广告A',
          position: 'head',
          start_date: '2026-07-01',
          end_date: '2026-07-31',
          enabled: 1,
          status: 'active',
        },
        {
          id: 2,
          material_id: 2,
          material_name: '促销广告B',
          position: 'head',
          start_date: '2026-07-10',
          end_date: '2026-07-20',
          enabled: 0,
          status: 'disabled',
        },
      ],
    },
  }
}

const CONFLICT_MESSAGE =
  '该广告位在所选区间内已有启用中的投放：「品牌广告A」（#1，2026-07-01 ~ 2026-07-31）；请先停用或调整日期区间'

function conflictEnvelope() {
  return {
    code: 400,
    message: CONFLICT_MESSAGE,
    data: {
      errors: [{ field: 'dateRange', message: CONFLICT_MESSAGE }],
      conflicts: [
        {
          id: 1,
          material_id: 1,
          material_name: '品牌广告A',
          position: 'head',
          start_date: '2026-07-01',
          end_date: '2026-07-31',
        },
      ],
    },
  }
}

test.describe('投放重叠裁决（T02927）', () => {

  test('新建与在投投放重叠：表单内点名冲突素材与区间，弹窗不关闭', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/ads/materials*', (route) =>
      route.fulfill({ json: materialsResponse() })
    )
    let postCount = 0
    await page.route('**/admin/api/v1/ads/placements**', (route) => {
      if (route.request().method() === 'POST') {
        postCount += 1
        return route.fulfill({ json: conflictEnvelope() })
      }
      return route.fulfill({ json: placementsResponse() })
    })

    await page.goto('/ads/placements')
    await page.getByRole('button', { name: '新建投放' }).click()
    const dlg = page.locator('.el-dialog').filter({ hasText: '新建投放' })

    // 选素材
    await dlg.locator('.el-select').first().click()
    await dlg.locator('.el-select__input').first().fill('品牌广告A')
    await page.locator('.el-select-dropdown__item').filter({ hasText: '品牌广告A' }).first().click()
    // 选广告位（开头）
    await dlg.locator('.el-select').nth(1).click()
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    // 选与在投投放重叠的日期
    await dlg.getByPlaceholder('开始日期').fill('2026-07-10')
    await dlg.getByPlaceholder('结束日期').fill('2026-07-20')
    await page.keyboard.press('Enter')

    await dlg.getByRole('button', { name: '确定' }).click()

    const alert = dlg.locator('[data-guide="ads-placement-conflict"]')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('无法保存')
    // 点名冲突对象，而不是「保存失败」四个字
    await expect(alert).toContainText('品牌广告A')
    await expect(alert).toContainText('#1')
    await expect(alert).toContainText('2026-07-01')
    await expect(alert).toContainText('2026-07-31')
    await expect(alert).toContainText('请先停用')

    // 失败不关窗：运营可以直接改日期重提
    await expect(dlg).toBeVisible()
    expect(postCount).toBe(1)
  })

  test('重新启用与在投投放重叠：提示点名冲突素材，开关回弹', async ({ page }) => {
    await setLoginState(page, 'admin')
    let putCount = 0
    await page.route('**/admin/api/v1/ads/placements**', (route) => {
      if (route.request().method() === 'PUT') {
        putCount += 1
        return route.fulfill({ json: conflictEnvelope() })
      }
      return route.fulfill({ json: placementsResponse() })
    })

    await page.goto('/ads/placements')
    const row = page.locator('.el-table__row').filter({ hasText: '促销广告B' })
    await expect(row).toBeVisible()
    await row.locator('.el-switch').click()
    await page.getByRole('dialog').getByRole('button', { name: '确认启用' }).click()

    await expect.poll(() => putCount, { timeout: 30000 }).toBe(1)
    // 拦截器弹的提示必须点名在投的那条，不能只说「启用失败」
    await expect(page.locator('.el-message').getByText(/品牌广告A/).first()).toBeVisible()
    // 未写回 row.enabled → 开关回到停用态，不出现假成功
    await expect(row.locator('.el-switch:not(.is-checked)')).toBeVisible()
    await expect(page.locator('.el-message').getByText('已启用')).toBeHidden()
  })
})
