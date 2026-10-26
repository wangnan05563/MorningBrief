import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * C94（T02803）素材录入页超限静默忽略
 *
 * 原缺陷的用户侧形态：上传区写着「单个文件」，limit=1，但没有 on-exceed。
 * Element Plus 在 `fileList.length + files.length > limit` 时**整批丢弃并直接 return**，
 * 既不触发 on-change 也不改 file-list——用户再选一次文件，界面毫无反应，
 * 只能反复点、或者以为浏览器坏了。
 *
 * 断言两件事，缺一不可：
 * 1) 有一条明确提示，且提示里带被忽略的条数（不是「操作失败」这种空话）；
 * 2) 已选文件不被顶掉、也不被清空——超限是丢弃「新选的」而不是替换，
 *    否则用户会以为自己刚选的那个文件已经进队列了，随后上传的是另一个。
 */

function toast(page) {
  return page.locator('.el-message').filter({ hasText: '本课程素材一次只能上传 1 个文件' })
}

function uploadInput(page) {
  return page.locator('.el-upload input[type=file]').first()
}

function selectedItems(page) {
  return page.locator('.el-upload-list__item')
}

async function openPage(page) {
  await setLoginState(page, 'admin')
  // 页壳健康检查与更新检查会自己弹 500/提示，干扰 .el-message 计数
  await page.route('**/api/health/ready**', (route) =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { ready: true } } })
  )
  await page.route('**/admin/api/v1/about/check-update**', (route) =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { latest: false, current: 'test' } } })
  )
  await page.route('**/admin/api/v1/channels**', (route) => route.fulfill({ json: channelsListResponse }))
  await page.goto('/materials', { waitUntil: 'networkidle' })
  await expect(uploadInput(page)).toBeAttached()
}

test.describe('素材录入：超过单个文件上限时必须给出可读提示（C94）', () => {
  test('已选 1 个后再选 1 个：提示被忽略的条数，已选文件保持不变', async ({ page }) => {
    await openPage(page)

    await uploadInput(page).setInputFiles({
      name: '第一章.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('第一章 正文', 'utf8'),
    })
    await expect(selectedItems(page)).toHaveCount(1)

    // 修复前：这里既没有提示，file-list 也还是 1——用户看不到任何反馈
    await uploadInput(page).setInputFiles({
      name: '第二章.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('第二章 正文', 'utf8'),
    })

    await expect(toast(page)).toBeVisible()
    await expect(toast(page)).toContainText('已忽略本次选择的 1 个')
    await expect(selectedItems(page)).toHaveCount(1)
    await expect(selectedItems(page).first()).toContainText('第一章.txt')
  })

  test('一次选中 2 个：提示 2 个，队列保持空（Element Plus 是整批丢弃）', async ({ page }) => {
    await openPage(page)

    // input 没有 multiple，只能用 DataTransfer 模拟一次选择多个文件
    await page.evaluate(() => {
      const input = document.querySelector('.el-upload input[type=file]')
      const dt = new DataTransfer()
      dt.items.add(new File(['a'], '甲.txt', { type: 'text/plain' }))
      dt.items.add(new File(['b'], '乙.txt', { type: 'text/plain' }))
      input.files = dt.files
      input.dispatchEvent(new Event('change', { bubbles: true }))
    })

    await expect(toast(page)).toContainText('已忽略本次选择的 2 个')
    await expect(selectedItems(page)).toHaveCount(0)
    // 没有文件就不该放行上传（按钮保持禁用，而不是拿空 selectedFile 去发请求）
    await expect(page.getByRole('button', { name: '上传并解析' })).toBeDisabled()
  })
})
