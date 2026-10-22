import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * C56（M2 / FR-UX-202 / ACC-UX-201 第 5 条）素材编辑清空预检
 *
 * 原缺陷的用户侧形态：编辑弹窗里把正文（或来源＝书名）删空 → 点保存 →
 * 提示「已保存」→ 弹窗关掉 → 那条素材的正文真的没了。
 * 来源更狠：讲书稿按「来源＝书名」聚合整本书，清空书名等于把整本书从书单候选里抹掉。
 *
 * 本 spec 在真实浏览器里断言的是**提交根本没发生**（PUT 次数为 0）而不只是有提示——
 * 只断言提示文案的话，把提示加在发出请求之后就“通过”了，缺陷还在。
 *
 * 运行：cd apps/admin-web && PW_CHANNEL=chrome npx playwright test tests/material-blanking.spec.js
 */

const MATERIAL = {
  id: 7,
  channel_id: 1,
  title: '第一章 课题分离',
  source: '被讨厌的勇气',
  category: '心理',
  status: 'pending',
  content: '第一章正文内容，长度足够不被当成占位。',
  media_type: 'text',
  media_url: null,
  media_thumb_url: null,
  crawled_at: '2026-10-01T10:00:00',
}

function editDialog(page) {
  return page.locator('.el-dialog').filter({ hasText: '编辑素材' })
}

async function openEditor(page, putCalls) {
  await setLoginState(page)
  await silenceShellRequests(page)
  await page.route('**/admin/api/v1/channels**', (route) =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { list: [{ id: 1, name: '讲书稿' }] } } })
  )
  await page.route('**/admin/api/v1/materials**', async (route) => {
    const req = route.request()
    if (req.method() === 'PUT') {
      putCalls.push(JSON.parse(req.postData() || '{}'))
      return route.fulfill({ json: { code: 0, message: 'ok', data: MATERIAL } })
    }
    if (req.url().includes('/materials/7')) {
      return route.fulfill({ json: { code: 0, message: 'ok', data: MATERIAL } })
    }
    return route.fulfill({ json: { code: 0, message: 'ok', data: { total: 1, list: [MATERIAL] } } })
  })
  await page.goto('/channels/material-library', { waitUntil: 'networkidle' })
  await page.locator('.el-table__row').first().getByRole('button', { name: '编辑' }).click()
  await expect(editDialog(page)).toBeVisible()
}

/** 页壳每几秒探一次 /api/health/ready，后端不在时它自己会弹一条 500 提示，会干扰断言 */
function warning(page, text) {
  return page.locator('.el-message').filter({ hasText: text })
}

async function silenceShellRequests(page) {
  await page.route('**/api/health/ready**', (route) =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { ready: true } } })
  )
  await page.route('**/admin/api/v1/about/check-update**', (route) =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { latest: false, current: 'test' } } })
  )
}

function fieldItem(page, label) {
  return editDialog(page).locator('.el-form-item').filter({ hasText: label }).first()
}

test.describe('素材编辑的清空预检（C56）', () => {
  test.use({ expect: { timeout: 30000 } })

  test('把正文删空后点保存：不发请求，并说明后果', async ({ page }) => {
    const putCalls = []
    await openEditor(page, putCalls)
    await fieldItem(page, '正文').locator('textarea').fill('')
    await editDialog(page).getByRole('button', { name: '保存' }).click()

    await expect(warning(page, '正文不能清空')).toContainText('改写')
    expect(putCalls, '清空正文仍发出了 PUT——预检没挡住').toEqual([])
    // 弹窗必须还开着：否则用户以为保存成功，实际什么都没提交
    await expect(editDialog(page)).toBeVisible()
  })

  test('把来源（书名）删空：不发请求，且提示点出聚合键', async ({ page }) => {
    const putCalls = []
    await openEditor(page, putCalls)
    await fieldItem(page, '来源').locator('input').fill('')
    await editDialog(page).getByRole('button', { name: '保存' }).click()

    await expect(warning(page, '来源不能清空')).toContainText('聚合')
    expect(putCalls).toEqual([])
  })

  test('只填空白字符＝删空，同样拦下', async ({ page }) => {
    const putCalls = []
    await openEditor(page, putCalls)
    await fieldItem(page, '正文').locator('textarea').fill('   \n  ')
    await editDialog(page).getByRole('button', { name: '保存' }).click()

    await expect(warning(page, '正文不能清空')).toBeVisible()
    expect(putCalls).toEqual([])
  })

  test('正常编辑（改分类、正文保持）必须照常提交——预检不能变成保存不了', async ({ page }) => {
    const putCalls = []
    await openEditor(page, putCalls)
    await fieldItem(page, '分类').locator('input').fill('自我成长')
    await editDialog(page).getByRole('button', { name: '保存' }).click()

    await expect
      .poll(() => putCalls.length, { message: '改分类没有发出 PUT' })
      .toBe(1)
    expect(putCalls[0].source).toBe('被讨厌的勇气')
    expect(putCalls[0].content).toBe(MATERIAL.content)
  })

  test('原值本就为空的素材仍可保存空正文（历史数据不该被锁死）', async ({ page }) => {
    const putCalls = []
    const blankRow = { ...MATERIAL, content: '', source: '' }
    await setLoginState(page)
    await silenceShellRequests(page)
    await page.route('**/admin/api/v1/channels**', (route) =>
      route.fulfill({ json: { code: 0, message: 'ok', data: { list: [{ id: 1, name: '讲书稿' }] } } })
    )
    await page.route('**/admin/api/v1/materials**', async (route) => {
      const req = route.request()
      if (req.method() === 'PUT') {
        putCalls.push(JSON.parse(req.postData() || '{}'))
        return route.fulfill({ json: { code: 0, message: 'ok', data: blankRow } })
      }
      if (req.url().includes('/materials/7')) {
        return route.fulfill({ json: { code: 0, message: 'ok', data: blankRow } })
      }
      return route.fulfill({ json: { code: 0, message: 'ok', data: { total: 1, list: [blankRow] } } })
    })
    await page.goto('/channels/material-library', { waitUntil: 'networkidle' })
    await page.locator('.el-table__row').first().getByRole('button', { name: '编辑' }).click()
    await expect(editDialog(page)).toBeVisible()

    await fieldItem(page, '分类').locator('input').fill('补录')
    await editDialog(page).getByRole('button', { name: '保存' }).click()

    await expect
      .poll(() => putCalls.length, { message: '本就为空的行被预检卡住——防护做成了新 bug' })
      .toBe(1)
  })
})
