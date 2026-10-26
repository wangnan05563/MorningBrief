import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * T02609（FR-COS 快照恢复）E2E
 *
 * 口径：
 * ① `.backup` 目录里的对象是旧版本，列表必须带「快照」语义标注，避免被当普通文件删掉；
 * ② 「恢复」会用快照内容换掉线上对象，确认框必须点名源/目标 Key，
 *    并说明「恢复前会先备份当前对象」或「保留份数为 0、不可回退」；
 * ③ 恢复失败（预览读不到 / 服务端 409）不得提示成功；取消不得发请求。
 */
const NAV_TIMEOUT = 30000

const STAMP = '20260101-120000'
const SNAP_KEY = `audio/.backup/${STAMP}/a.mp3`
const LIVE_KEY = 'audio/a.mp3'

const LIST = {
  '': { prefix: '', folders: ['audio/'], files: [], is_snapshot_dir: false },
  'audio/': {
    prefix: 'audio/',
    folders: ['.backup/'],
    files: [{ key: LIVE_KEY, name: 'a.mp3', size: 2048, last_modified: 'Tue, 20 Oct 2026 10:00:00 GMT', is_snapshot: false }],
    is_snapshot_dir: false,
  },
  'audio/.backup/': {
    prefix: 'audio/.backup/',
    folders: [`${STAMP}/`],
    files: [],
    is_snapshot_dir: true,
  },
  [`audio/.backup/${STAMP}/`]: {
    prefix: `audio/.backup/${STAMP}/`,
    folders: [],
    files: [{ key: SNAP_KEY, name: 'a.mp3', size: 1024, last_modified: 'Thu, 01 Jan 2026 12:00:00 GMT', is_snapshot: true }],
    is_snapshot_dir: true,
  },
}

const previewResponse = ({ keep = 5, targetExists = true } = {}) => ({
  code: 0, message: 'ok',
  data: {
    backup_key: SNAP_KEY,
    target_key: LIVE_KEY,
    snapshot: { size: 1024, last_modified: 'Thu, 01 Jan 2026 12:00:00 GMT' },
    target_exists: targetExists,
    target: targetExists ? { size: 2048, last_modified: 'Tue, 20 Oct 2026 10:00:00 GMT' } : null,
    backup_keep_count: keep,
  },
})

const mockCos = (page, {
  keep = 5,
  preview = previewResponse({ keep }),
  previewFails = false,
  restoreRejects = false,
} = {}) =>
  page.route('**/admin/api/v1/cos**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()

    if (url.pathname.endsWith('/cos/status')) {
      return route.fulfill({ json: {
        code: 0, message: 'ok',
        data: { configured: true, bucket: 'bkt-1250000000', region: 'ap-guangzhou', cdn_domain: '', backup_keep_count: keep },
      } })
    }
    if (url.pathname.endsWith('/cos/restore-preview')) {
      if (previewFails) {
        return route.fulfill({ status: 500, json: { code: 500, message: 'COS 服务不可用', data: null } })
      }
      return route.fulfill({ json: preview })
    }
    if (method === 'POST' && url.pathname.endsWith('/cos/restore')) {
      if (restoreRejects) {
        return route.fulfill({ json: {
          code: 409,
          message: `目标对象已存在：${LIVE_KEY}（2.0 KB）；已拒绝恢复该快照，请确认后再以覆盖方式恢复`,
          data: null,
        } })
      }
      return route.fulfill({ json: {
        code: 0, message: '已从快照恢复',
        data: {
          restored_from: SNAP_KEY, target_key: LIVE_KEY, overwritten: true,
          backup_key: `audio/.backup/20261026-130000/a.mp3`, size: 1024,
          last_modified: 'Thu, 01 Jan 2026 12:00:00 GMT', backup_keep_count: keep,
        },
      } })
    }
    if (url.pathname.endsWith('/cos/objects')) {
      const prefix = url.searchParams.get('prefix') || ''
      return route.fulfill({ json: { code: 0, message: 'ok', data: LIST[prefix] || { prefix, folders: [], files: [], is_snapshot_dir: false } } })
    }
    return route.fulfill({ json: { code: 0, message: 'ok', data: null } })
  })

const table = (page) => page.locator('[data-guide="cos-files-table"]')

const enterSnapshotFile = async (page) => {
  await page.goto('/cos-files')
  await expect(table(page).getByText('audio', { exact: true })).toBeVisible({ timeout: NAV_TIMEOUT })
  await table(page).getByText('audio', { exact: true }).click()
  await expect(table(page).getByText('.backup', { exact: true })).toBeVisible({ timeout: NAV_TIMEOUT })
  await table(page).getByText('.backup', { exact: true }).click()
  await expect(page.locator('[data-guide="cos-snapshot-notice"]')).toBeVisible({ timeout: NAV_TIMEOUT })
  await table(page).getByText(STAMP, { exact: true }).click()
  await expect(table(page).getByText('a.mp3', { exact: true })).toBeVisible({ timeout: NAV_TIMEOUT })
}

test.describe('COS 快照恢复', () => {
  test('快照目录给出语义提示与「快照」标签，且不提供重命名', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page)
    await enterSnapshotFile(page)

    const notice = page.locator('[data-guide="cos-snapshot-notice"]')
    await expect(notice).toContainText('当前位于 .backup 快照目录')
    await expect(notice).toContainText('删除后无法找回')
    await expect(table(page).locator('.snapshot-tag')).toHaveText('快照')
    // 快照对象不可重命名（避免改名后与原对象失去对应关系）
    await expect(table(page).getByRole('button', { name: '重命名' })).toHaveCount(0)
    await expect(table(page).getByRole('button', { name: '恢复' })).toHaveCount(1)
  })

  test('恢复确认框点名源/目标并说明可回退，确认后按真实 Key 提交', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page)
    const requests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/restore')) requests.push(r)
    })

    await enterSnapshotFile(page)
    await table(page).getByRole('button', { name: '恢复' }).click()

    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(box).toContainText('从快照恢复文件')
    await expect(box).toContainText(`${SNAP_KEY} → ${LIVE_KEY}`)
    await expect(box).toContainText('快照内容：1.0 KB')
    await expect(box).toContainText('恢复前会先把当前对象备份到 .backup/<时间戳>/，保留最近 5 份')
    expect(requests).toHaveLength(0)

    await box.getByRole('button', { name: '确认恢复' }).click()
    await expect.poll(() => requests.length, { timeout: NAV_TIMEOUT }).toBe(1)
    expect(JSON.parse(requests[0].postData())).toMatchObject({
      backup_key: SNAP_KEY,
      target_key: LIVE_KEY,
      overwrite: true,
    })
    await expect(page.getByText(`已从快照恢复 ${LIVE_KEY}`).first()).toBeVisible({ timeout: NAV_TIMEOUT })
  })

  test('保留份数为 0 时确认框必须点名「不可找回」', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { keep: 0 })
    await enterSnapshotFile(page)
    await table(page).getByRole('button', { name: '恢复' }).click()

    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(box).toContainText('当前「快照保留份数」为 0：不会为当前对象留备份，恢复后旧内容不可找回')
    await expect(box).toContainText('本次恢复会直接换掉当前对象且无法回退')
  })

  test('快照信息读取失败时中止恢复，不发请求', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { previewFails: true })
    const requests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/restore')) requests.push(r)
    })

    await enterSnapshotFile(page)
    await table(page).getByRole('button', { name: '恢复' }).click()

    await expect(page.getByText('快照信息读取失败，已取消恢复').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(page.locator('.el-message-box')).toHaveCount(0)
    expect(requests).toHaveLength(0)
  })

  test('服务端拒绝恢复（409）时不得提示成功', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page, { restoreRejects: true })
    await enterSnapshotFile(page)
    await table(page).getByRole('button', { name: '恢复' }).click()

    const box = page.locator('.el-message-box')
    await box.getByRole('button', { name: '确认恢复' }).click()
    await expect(page.getByText('已拒绝恢复该快照').first()).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(page.getByText(/^已从快照恢复/)).toHaveCount(0)
  })

  test('取消确认后不发恢复请求', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockCos(page)
    const requests = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes('/cos/restore')) requests.push(r)
    })

    await enterSnapshotFile(page)
    await table(page).getByRole('button', { name: '恢复' }).click()

    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible({ timeout: NAV_TIMEOUT })
    await box.getByRole('button', { name: '取消' }).click()
    await expect(box).toBeHidden({ timeout: NAV_TIMEOUT })
    expect(requests).toHaveLength(0)
  })

  test('配置页回填并提交「快照保留份数」', async ({ page }) => {
    await setLoginState(page, 'admin')
    let saved = null
    await page.route('**/admin/api/v1/cos**', async (route) => {
      const url = new URL(route.request().url())
      const method = route.request().method()
      if (url.pathname.endsWith('/cos/config') && method === 'GET') {
        return route.fulfill({ json: { code: 0, message: 'ok', data: {
          secret_id: '****abcd', secret_key: '****wxyz',
          region: 'ap-guangzhou', bucket: 'bkt-1250000000', cdn_domain: '',
          backup_keep_count: 7, loaded: true, load_error: null,
          updated_at: '2026-10-20T10:00:00', fallback_fields: [],
        } } })
      }
      if (url.pathname.endsWith('/cos/config') && method === 'PUT') {
        saved = JSON.parse(route.request().postData() || '{}')
        return route.fulfill({ json: { code: 0, message: 'ok', data: null } })
      }
      if (url.pathname.endsWith('/cos/status')) {
        return route.fulfill({ json: { code: 0, message: 'ok', data: {
          configured: true, bucket: 'bkt-1250000000', region: 'ap-guangzhou', cdn_domain: '', backup_keep_count: 7,
        } } })
      }
      return route.fulfill({ json: { code: 0, message: 'ok', data: null } })
    })

    await page.goto('/cos-config')
    const input = page.locator('.el-input-number input').last()
    await expect(input).toHaveValue('7', { timeout: NAV_TIMEOUT })
    await input.fill('3')
    await page.getByRole('button', { name: '保存配置' }).click()

    await expect.poll(() => saved, { timeout: NAV_TIMEOUT }).not.toBeNull()
    expect(saved.backup_keep_count).toBe(3)
  })
})
