import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02493（FR-UX-205）上传可回退 E2E
 *
 * 口径：同名上传必须先检测、再确认，确认框里点名「影响哪个对象 + 旧文件大小 +
 * 覆盖前会自动留 .backup 快照」；检测失败不允许盲传；
 * 服务端 409（绕过页面直接调接口）不能被显示成成功。
 */
const NAV_TIMEOUT = 30000

const objectsResponse = {
  code: 0,
  message: 'success',
  data: {
    prefix: '',
    folders: [],
    files: [{
      key: 'a.mp3', name: 'a.mp3', size: 2048,
      last_modified: 'Wed, 15 Oct 2026 08:00:00 GMT', content_type: 'audio/mpeg',
    }],
  },
}

// multipart body 里取 overwrite 字段的值（FormData 追加顺序固定，字段名后紧跟值）
const overwriteOf = (req) => {
  const m = /name="overwrite"\r\n\r\n(\w+)/.exec(req.postData() || '')
  return m ? m[1] : null
}

const mockCos = (page, { exists = true, existsFails = false, uploadAlwaysRejects = false } = {}) =>
  page.route('**/admin/api/v1/cos**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()

    if (url.includes('/cos/status')) {
      return route.fulfill({ json: { code: 0, message: 'ok', data: { configured: true, bucket: 'bkt', region: 'ap-guangzhou', cdn_domain: '' } } })
    }
    if (url.includes('/cos/objects')) {
      return route.fulfill({ json: objectsResponse })
    }
    if (url.includes('/cos/exists')) {
      if (existsFails) {
        return route.fulfill({ status: 500, json: { code: 500, message: 'COS 服务不可用', data: null } })
      }
      return route.fulfill({
        json: {
          code: 0, message: 'ok',
          data: { key: 'a.mp3', exists, size: exists ? 2048 : 0, last_modified: exists ? 'Wed, 15 Oct 2026 08:00:00 GMT' : '', content_type: exists ? 'audio/mpeg' : '' },
        },
      })
    }
    if (method === 'POST' && url.includes('/cos/upload')) {
      const overwrite = overwriteOf(route.request())
      if (uploadAlwaysRejects || overwrite !== 'true') {
        return route.fulfill({
          json: {
            code: 409,
            message: '同名文件已存在：a.mp3（2.0 KB，更新于 Wed, 15 Oct 2026 08:00:00 GMT）；已拒绝覆盖上传，请确认后再以覆盖方式重传',
            data: null,
          },
        })
      }
      return route.fulfill({
        json: {
          code: 0, message: '已覆盖上传，旧文件已备份至 .backup/20261018-160000/a.mp3',
          data: {
            key: 'a.mp3', size: 4, content_type: 'audio/mpeg',
            overwritten: true, previous: { size: 2048 }, backup_key: '.backup/20261018-160000/a.mp3',
          },
        },
      })
    }
    return route.fulfill({ json: { code: 0, message: 'ok', data: null } })
  })

const chooseFile = (page) =>
  page.setInputFiles('input[type=file]', {
    name: 'a.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('DATA'),
  })

test.describe('云端存储上传可回退', () => {
  test.use({ expect: { timeout: NAV_TIMEOUT } })

  test('同名上传先弹覆盖确认，未确认前不发上传请求', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { exists: true })
    const uploads = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/upload')) uploads.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.mp3').first()).toBeVisible({ timeout: NAV_TIMEOUT })

    await chooseFile(page)
    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(box.getByText('上传并覆盖同名文件：/a.mp3')).toBeVisible()
    await expect(box.getByText(/云端已存在同名对象（2\.0 KB/)).toBeVisible()
    await expect(box.getByText('覆盖前旧文件自动备份到 .backup/<时间戳>/a.mp3，可在文件列表逐层找回')).toBeVisible()
    // 直接点确认但不输入确认词：不得放行
    await box.getByRole('button', { name: '确认覆盖上传' }).click()
    await expect(box.getByText('请逐字输入 覆盖')).toBeVisible({ timeout: NAV_TIMEOUT })
    expect(uploads).toHaveLength(0)
  })

  test('输入确认词后按 overwrite=true 上传，成功提示点名快照位置', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { exists: true })
    const uploadRequests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/upload')) uploadRequests.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.mp3').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await chooseFile(page)

    const box = page.locator('.el-message-box')
    await box.locator('input').fill('覆盖')
    await box.getByRole('button', { name: '确认覆盖上传' }).click()

    await expect.poll(() => uploadRequests.length, { timeout: NAV_TIMEOUT }).toBe(1)
    expect(overwriteOf(uploadRequests[0])).toBe('true')
    await expect(page.getByText('旧文件已备份至 .backup/20261018-160000/a.mp3').first()).toBeVisible({ timeout: NAV_TIMEOUT })
  })

  test('无同名对象时不弹确认，按 overwrite=false 直传', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { exists: false })
    const uploadRequests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/upload')) uploadRequests.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.mp3').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await chooseFile(page)

    await expect.poll(() => uploadRequests.length, { timeout: NAV_TIMEOUT }).toBe(1)
    expect(overwriteOf(uploadRequests[0])).toBe('false')
    await expect(page.locator('.el-message-box')).toHaveCount(0)
  })

  test('同名检测失败时中止上传并说明原因', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { exists: true, existsFails: true })
    const uploads = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/upload')) uploads.push(r)
    })

    await page.goto('/cos-files')
    await expect(page.getByText('a.mp3').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await chooseFile(page)

    await expect(page.getByText('同名检测失败，已取消上传').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    expect(uploads).toHaveLength(0)
  })

  test('服务端拒绝覆盖（409）时不得提示上传成功', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { exists: true, uploadAlwaysRejects: true })

    await page.goto('/cos-files')
    await expect(page.getByText('a.mp3').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await chooseFile(page)

    const box = page.locator('.el-message-box')
    await box.locator('input').fill('覆盖')
    await box.getByRole('button', { name: '确认覆盖上传' }).click()

    await expect(page.getByText('已拒绝覆盖上传').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(page.getByText('已上传 a.mp3')).toHaveCount(0)
    await expect(page.getByText('旧文件已备份至')).toHaveCount(0)
  })
})
