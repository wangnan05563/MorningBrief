import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02608（H19）重命名 / 移动覆盖确认 E2E
 *
 * 口径：同级重命名走的是服务端 copy_object，而 copy 是「目标存在即换掉」。
 * 所以同名与否、覆盖几条都必须以服务端 move-preview 的实测为准——本页列表只是
 * 进入目录时的快照，分页外和子层级里的同名对象根本不在视野内。
 * 未确认不得发移动请求；检测失败不得盲发；服务端 409 不能被显示成成功。
 */
const NAV_TIMEOUT = 30000

const fileRow = {
  key: 'a.txt', name: 'a.txt', size: 1024,
  last_modified: 'Wed, 15 Oct 2026 08:00:00 GMT', content_type: 'text/plain',
}

const listResponse = (folders = []) => ({
  code: 0,
  message: 'success',
  data: {
    prefix: '',
    folders,
    files: folders.length ? [] : [fileRow],
  },
})

const previewResponse = (conflicts, { isPrefix = false, moved = 1 } = {}) => ({
  code: 0, message: 'ok',
  data: {
    source_key: conflicts.length ? 'src' : '',
    dest_key: 'dst',
    is_prefix: isPrefix,
    moved,
    conflict_count: conflicts.length,
    conflicts,
    conflicts_truncated: false,
  },
})

const mockCos = (page, {
  folders = [],
  preview = previewResponse([]),
  previewFails = false,
  moveAlwaysRejects = false,
} = {}) =>
  page.route('**/admin/api/v1/cos**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()

    if (url.includes('/cos/status')) {
      return route.fulfill({ json: { code: 0, message: 'ok', data: { configured: true, bucket: 'bkt', region: 'ap-guangzhou', cdn_domain: '' } } })
    }
    if (url.includes('/cos/objects')) {
      return route.fulfill({ json: listResponse(folders) })
    }
    if (url.includes('/cos/move-preview')) {
      if (previewFails) {
        return route.fulfill({ status: 500, json: { code: 500, message: 'COS 服务不可用', data: null } })
      }
      return route.fulfill({ json: preview })
    }
    if (method === 'POST' && url.includes('/cos/move')) {
      const overwrite = JSON.parse(route.request().postData() || '{}').overwrite
      // 服务端按自己的实测把关：有同名而没带 overwrite=true 就拒绝（409）
      const hasConflict = (preview.data?.conflict_count ?? 0) > 0
      if (moveAlwaysRejects || (hasConflict && overwrite !== true)) {
        return route.fulfill({
          json: {
            code: 409,
            message: '目标位置已有 b.txt（2.0 KB，更新于 Wed, 15 Oct 2026 08:00:00 GMT）；'
              + '移动「a.txt」会把它们换掉。已拒绝移动，请确认后再以覆盖方式重做',
            data: null,
          },
        })
      }
      return route.fulfill({
        json: {
          code: 0, message: '移动成功，已覆盖 1 个同名对象，旧对象已备份到 .backup/ 目录',
          data: { moved: 1, overwritten: 1, backup_keys: ['.backup/20261018-160000/b.txt'] },
        },
      })
    }
    return route.fulfill({ json: { code: 0, message: 'ok', data: null } })
  })

// 打开重命名弹窗并填入新名字
const startRename = async (page, newName) => {
  await page.getByRole('button', { name: /重命名/ }).first().click()
  const dialog = page.locator('.el-dialog', { hasText: '重命名 / 移动' })
  await expect(dialog).toBeVisible({ timeout: NAV_TIMEOUT })
  await dialog.getByPlaceholder('新文件名').fill(newName)
  await dialog.getByRole('button', { name: /确定/ }).click()
}

test.describe('云端存储重命名覆盖确认', () => {
  test('同名重命名先弹覆盖确认，未确认前不发移动请求', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, {
      preview: previewResponse([{ dest_key: 'b.txt', size: 2048, last_modified: 'Wed, 15 Oct 2026 08:00:00 GMT' }]),
    })
    const moves = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/move')) moves.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.txt').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await startRename(page, 'b.txt')

    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(box.getByText('重命名并覆盖同名对象')).toBeVisible()
    await expect(box.getByText(/云端已存在同名对象（2\.0 KB，更新于/)).toBeVisible()
    await expect(box.getByText(/覆盖前旧对象自动备份到 \/\.backup\/<时间戳>\/b\.txt/)).toBeVisible()
    await box.getByRole('button', { name: '确认覆盖重命名' }).click()
    await expect(box.getByText('请逐字输入 覆盖')).toBeVisible({ timeout: NAV_TIMEOUT })
    expect(moves).toHaveLength(0)
  })

  test('输入确认词后按 overwrite=true 移动，成功提示点名覆盖条数', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, {
      preview: previewResponse([{ dest_key: 'b.txt', size: 2048, last_modified: '' }]),
    })
    const moveRequests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/move')) moveRequests.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.txt').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await startRename(page, 'b.txt')

    const box = page.locator('.el-message-box')
    await box.locator('input').fill('覆盖')
    await box.getByRole('button', { name: '确认覆盖重命名' }).click()

    await expect.poll(() => moveRequests.length, { timeout: NAV_TIMEOUT }).toBe(1)
    const body = JSON.parse(moveRequests[0].postData())
    expect(body).toMatchObject({ source_key: 'a.txt', dest_key: 'b.txt', overwrite: true })
    await expect(page.getByText('已覆盖 1 个同名对象').first()).toBeVisible({ timeout: NAV_TIMEOUT })
  })

  test('目标空闲时不弹确认，按 overwrite=false 直发', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page)
    const moveRequests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/move')) moveRequests.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.txt').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await startRename(page, 'b.txt')

    await expect.poll(() => moveRequests.length, { timeout: NAV_TIMEOUT }).toBe(1)
    expect(JSON.parse(moveRequests[0].postData()).overwrite).toBe(false)
    await expect(page.locator('.el-message-box')).toHaveCount(0)
    await expect(page.getByText('重命名成功').first()).toBeVisible({ timeout: NAV_TIMEOUT })
  })

  test('同名检测失败时中止重命名并说明原因', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { previewFails: true })
    const moves = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/move')) moves.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.txt').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await startRename(page, 'b.txt')

    await expect(page.getByText('同名检测失败，已取消重命名').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    expect(moves).toHaveLength(0)
  })

  test('服务端拒绝覆盖（409）时不得提示重命名成功', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, {
      preview: previewResponse([{ dest_key: 'b.txt', size: 2048, last_modified: '' }]),
      moveAlwaysRejects: true,
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.txt').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await startRename(page, 'b.txt')

    const box = page.locator('.el-message-box')
    await box.locator('input').fill('覆盖')
    await box.getByRole('button', { name: '确认覆盖重命名' }).click()

    await expect(page.getByText('已拒绝移动').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(page.getByText(/^重命名成功/)).toHaveCount(0)
  })

  test('文件夹批量：覆盖条数取服务端预览，本页看不见同名对象也照样报', async ({ page }) => {
    await setLoginState(page, 'admin')
    // 列表里只有 old/ 一个目录，new/ 下的同名对象完全不在视野内
    await mockCos(page, {
      folders: ['old/'],
      preview: previewResponse(
        [
          { dest_key: 'new/a.txt', size: 5, last_modified: '' },
          { dest_key: 'new/b.txt', size: 7, last_modified: '' },
          { dest_key: 'new/c.txt', size: 9, last_modified: '' },
        ],
        { isPrefix: true, moved: 3 },
      ),
    })
    const moveRequests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/move')) moveRequests.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('old').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await page.getByRole('button', { name: /重命名/ }).first().click()
    const dialog = page.locator('.el-dialog', { hasText: '重命名 / 移动' })
    await dialog.getByPlaceholder('新文件夹名（不含 /）').fill('new')
    await dialog.getByRole('button', { name: /确定/ }).click()

    const box = page.locator('.el-message-box')
    await expect(box.getByText('目标位置已有 3 个同名对象，移动整个文件夹会把它们逐个换掉')).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(box.getByText('将被覆盖的样例：new/a.txt、new/b.txt、new/c.txt')).toBeVisible()

    await box.locator('input').fill('覆盖')
    await box.getByRole('button', { name: '确认覆盖重命名' }).click()
    await expect.poll(() => moveRequests.length, { timeout: NAV_TIMEOUT }).toBe(1)
    expect(JSON.parse(moveRequests[0].postData())).toMatchObject({ source_key: 'old/', dest_key: 'new/', overwrite: true })
  })

  test('取消确认后不发任何移动请求，对象保持原样', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, {
      preview: previewResponse([{ dest_key: 'b.txt', size: 2048, last_modified: '' }]),
    })
    const moves = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/move')) moves.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.txt').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await startRename(page, 'b.txt')

    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
    await box.getByRole('button', { name: '取消' }).click()
    await expect(box).toBeHidden({ timeout: NAV_TIMEOUT })
    expect(moves).toHaveLength(0)
    await expect(page.getByText('a.txt').first()).toBeVisible({ timeout: NAV_TIMEOUT })
  })
})
