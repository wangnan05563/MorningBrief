import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * T03319（C91）素材录入页：整本上传「跳过已存在章节」必须如实说出口
 *
 * 后端改为整本单事务 + 断点续传后，重复上传整本返回 `count=0, skipped=N`。
 * 修复前的界面只说「解析完成，新增 0 条素材」并弹「上传成功」——
 * 运营无法区分「这本书早就在库里」与「解析失败/什么都没发生」，等于又一次虚报。
 *
 * 每条用例都成对断言：① 如实的那句话渲染出来了；② 与之矛盾的「成功」不在了。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

async function openPage(page, { upload, cos } = {}) {
  await setLoginState(page, 'admin')
  // 页壳健康检查与更新检查会自己弹提示，干扰 .el-message 断言
  await page.route('**/api/health/ready**', (route) =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { ready: true } } })
  )
  await page.route(`${API}/about/check-update**`, (route) =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { latest: false, current: 'test' } } })
  )
  await page.route(`${API}/channels**`, (route) => route.fulfill({ json: channelsListResponse }))
  if (upload) await page.route(`${API}/materials/upload`, (route) => route.fulfill({ json: upload }))
  if (cos) await page.route(`${API}/materials/import-cos`, (route) => route.fulfill({ json: cos }))

  await page.goto('/materials', { waitUntil: 'networkidle' })
  // 选了目标频道上传按钮才可用（否则只验到禁用态）
  await page.locator('.el-select').first().click()
  await page.locator('.el-select-dropdown__item').filter({ hasText: '科技频道' }).first().click()
}

async function pickFile(page) {
  await page.locator('.el-upload input[type=file]').first().setInputFiles({
    name: '测试书.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('# 第一章\n第一章正文', 'utf8'),
  })
}

const resultAlert = (page, text) => page.locator('.el-alert').filter({ hasText: text })
const toast = (page, text) => page.locator('.el-message').filter({ hasText: text })

test.describe('素材录入：整本上传的「跳过」必须如实回报（C91）', () => {
  test('整本均已存在：说清跳过 3 章，不说「上传成功」', async ({ page }) => {
    await openPage(page, {
      upload: ok({ count: 0, skipped: 3, skipped_titles: ['测试书 · 第一章'], list: [] }),
    })
    await pickFile(page)
    await page.getByRole('button', { name: '上传并解析' }).click()

    await expect(
      resultAlert(page, '解析完成：新增 0 条素材，跳过 3 章（频道内已有相同内容）')
    ).toBeVisible()
    await expect(toast(page, '整本已存在：3 章均已在目标频道，未重复入库')).toBeVisible()
    // 修复前这里会弹「上传成功」——全跳过却报成功，正是 C91 要消灭的虚报
    await expect(toast(page, '上传成功')).toHaveCount(0)
  })

  test('部分新增：新增数与跳过数同时出现，并提示上传成功', async ({ page }) => {
    await openPage(page, {
      upload: ok({ count: 2, skipped: 1, skipped_titles: ['测试书 · 第一章'], list: [] }),
    })
    await pickFile(page)
    await page.getByRole('button', { name: '上传并解析' }).click()

    await expect(
      resultAlert(page, '解析完成：新增 2 条素材，跳过 1 章（频道内已有相同内容）')
    ).toBeVisible()
    await expect(toast(page, '上传成功')).toBeVisible()
  })

  test('COS 导入全跳过：同一口径，不说「COS 导入成功」', async ({ page }) => {
    await openPage(page, {
      cos: ok({ count: 0, skipped: 2, skipped_titles: ['第一章'], list: [] }),
    })
    await page.getByRole('tab', { name: '云端存储导入' }).click()
    await page.getByPlaceholder('如 materials/book1.txt').fill('books/测试书.txt')
    await page.getByRole('button', { name: '导入' }).click()

    await expect(
      resultAlert(page, '导入完成：新增 0 条素材，跳过 2 章（频道内已有相同内容）')
    ).toBeVisible()
    await expect(toast(page, '整本已存在：2 章均已在目标频道，未重复入库')).toBeVisible()
    await expect(toast(page, 'COS 导入成功')).toHaveCount(0)
  })
})
