import { test, expect } from '@playwright/test'
import { setLoginState, MOBILE_VIEWPORT } from './helpers/mock'

/**
 * 应急停服可用性与状态可信（T02489 / FR-UX-201，来源建议 I54、I55）
 *
 * - I55：状态读取失败此前被 `.catch(() => ({ enabled: false }))` 当成「生产运行正常」
 *   渲染绿色横幅 → 现在必须是「维护态未知」警示态，且不给出停服/恢复入口
 * - I54：stop() 里 `reason = v.trim()` 作用域错误抛 ReferenceError，被外层 catch 吞掉，
 *   停服请求从未发出 → 现在必须真实提交原因并进入停服态
 * - 停服态显示已停服时长并每秒递增（口径：已停服时长，不会自动到期恢复）
 */

const NAV_TIMEOUT = 30000
const STATUS = '**/admin/api/v1/m/maintenance-status**'
const STOP = '**/admin/api/v1/m/emergency/stop**'
const RESUME = '**/admin/api/v1/m/emergency/resume**'

const ok = (data) => ({ code: 0, message: 'ok', data })
const FAIL = { code: 500, message: '后端服务不可用（测试注入）', data: null }

const OFF = { enabled: false, reason: null, by: null, at: null }

// 后端存的是本地 naive ISO，测试里也必须按本地时钟生成（toISOString 是 UTC，会偏一个时区）
function localIso(d) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

async function mockMobile(page, { status, stop, resume, requests }) {
  await page.route(STATUS, (route) =>
    status.fail
      ? route.fulfill({ status: 200, json: FAIL })
      : route.fulfill({ status: 200, json: ok(status.data) }),
  )
  await page.route(STOP, (route) => {
    requests.push({ url: route.request().url(), body: route.request().postData() })
    return route.fulfill({ status: 200, json: ok(stop.data) })
  })
  await page.route(RESUME, (route) => {
    requests.push({ url: route.request().url(), body: null })
    return route.fulfill({ status: 200, json: ok(resume.data) })
  })
}

// getByRole 的 name 默认按子串匹配，'应急停服' 会命中 '解除应急停服'，故一律 exact
const btn = (page, name) => page.getByRole('button', { name, exact: true })

test.describe('应急停服 · 状态可信与可用性', () => {
  // 本组全部是移动端外壳页面（`/m/manage/alert`）：视口必须是手机宽度，
  // 否则按 IDD-M104 的跨端策略会被换到 PC 侧，断言落在错误的页面上（T02511 口径）
  test.use({ viewport: MOBILE_VIEWPORT })

  test.beforeEach(async ({ page }) => {
    // 页面隐藏时 axios 会静默丢弃 ElMessage，headless 下需覆盖
    await page.addInitScript(() => {
      Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
      Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
    })
    await setLoginState(page, 'admin')
  })

  test('状态读取失败：显示「维护态未知」且不暴露停服/恢复入口', async ({ page }) => {
    const requests = []
    await mockMobile(page, { status: { fail: true }, stop: { data: OFF }, resume: { data: OFF }, requests })
    await page.goto('/m/manage/alert')

    const banner = page.locator('.m-alert__banner')
    await expect(banner).toBeVisible({ timeout: NAV_TIMEOUT })
    await expect(banner).toContainText('维护态未知')
    await expect(banner).toContainText('后端服务不可用（测试注入）')
    await expect(banner).toHaveClass(/m-alert__banner--unknown/)
    // 关键：不得再给出「生产运行正常」这种误导结论
    await expect(page.getByText('生产运行正常')).toHaveCount(0)

    await expect(btn(page, '重新读取状态')).toBeVisible()
    await expect(btn(page, '应急停服')).toHaveCount(0)
    await expect(btn(page, '解除应急停服')).toHaveCount(0)
  })

  test('重试成功后恢复可操作：正常态 + 应急停服按钮出现', async ({ page }) => {
    const requests = []
    await mockMobile(page, { status: { fail: true }, stop: { data: OFF }, resume: { data: OFF }, requests })
    await page.goto('/m/manage/alert')
    await expect(page.locator('.m-alert__banner')).toContainText('维护态未知', { timeout: NAV_TIMEOUT })

    // 后注册的 route 优先：用它接管状态接口，模拟后端恢复
    await page.route(STATUS, (route) => route.fulfill({ status: 200, json: ok(OFF) }))
    await btn(page, '重新读取状态').click()

    await expect(page.locator('.m-alert__banner')).toContainText('生产运行正常')
    await expect(btn(page, '应急停服')).toBeVisible()
  })

  test('填写原因后停服请求真实发出（I54 回归）', async ({ page }) => {
    const stopped = { enabled: true, reason: '上游 TTS 全部超时', by: 'admin', at: localIso(new Date()), already: false }
    const requests = []
    await mockMobile(page, { status: { data: OFF }, stop: { data: stopped }, resume: { data: OFF }, requests })
    await page.goto('/m/manage/alert')
    await expect(btn(page, '应急停服')).toBeVisible({ timeout: NAV_TIMEOUT })

    await btn(page, '应急停服').click()
    const box = page.locator('.el-message-box')
    await expect(box).toBeVisible()
    await box.locator('textarea').fill('  上游 TTS 全部超时  ')
    await box.getByRole('button', { name: '确认停服' }).click()

    await expect.poll(() => requests.length).toBe(1)
    expect(requests[0].url).toContain('/m/emergency/stop')
    // 原因必须去掉首尾空格后原样提交（此前 ReferenceError 让这一步从未发生）
    expect(JSON.parse(requests[0].body)).toEqual({ reason: '上游 TTS 全部超时' })

    const banner = page.locator('.m-alert__banner')
    await expect(banner).toContainText('系统处于维护 / 应急停服态')
    await expect(banner).toContainText('原因：上游 TTS 全部超时')
    await expect(banner.locator('.m-alert__elapsed')).toHaveText(/已停服：\d+ 秒/)
    await expect(page.locator('.el-message', { hasText: '已应急停服' })).toBeVisible()
  })

  test('原因为空时不提交', async ({ page }) => {
    const requests = []
    await mockMobile(page, { status: { data: OFF }, stop: { data: OFF }, resume: { data: OFF }, requests })
    await page.goto('/m/manage/alert')
    await expect(btn(page, '应急停服')).toBeVisible({ timeout: NAV_TIMEOUT })

    await btn(page, '应急停服').click()
    const box = page.locator('.el-message-box')
    await box.locator('textarea').fill('   ')
    await box.getByRole('button', { name: '确认停服' }).click()
    await expect(box.getByText('原因不能为空')).toBeVisible()
    await expect.poll(() => requests.length, { timeout: 2000 }).toBe(0)
  })

  test('停服态：无重复停服入口 + 已停服时长每秒递增', async ({ page }) => {
    const at = localIso(new Date(Date.now() - 65_000))
    const stopped = { enabled: true, reason: '磁盘写满', by: 'admin', at, already: false }
    const requests = []
    await mockMobile(page, { status: { data: stopped }, stop: { data: stopped }, resume: { data: OFF }, requests })
    await page.goto('/m/manage/alert')

    const banner = page.locator('.m-alert__banner')
    await expect(banner).toContainText('系统处于维护 / 应急停服态', { timeout: NAV_TIMEOUT })
    // 停服态只留恢复入口；重复触发由后端幂等兜底（already），前端不再给按钮
    await expect(btn(page, '解除应急停服')).toBeVisible()
    await expect(btn(page, '应急停服')).toHaveCount(0)

    const elapsed = banner.locator('.m-alert__elapsed')
    await expect(elapsed).toHaveText(/已停服：1 分 \d+ 秒/)
    const before = await elapsed.innerText()
    await page.waitForTimeout(2100)
    expect(await elapsed.innerText()).not.toBe(before)
    await expect(page.getByText('停服不会自动到期恢复')).toBeVisible()
  })

  test('恢复：确认后调用 resume 并回到正常态', async ({ page }) => {
    const stopped = { enabled: true, reason: '磁盘写满', by: 'admin', at: localIso(new Date()), already: false }
    const requests = []
    await mockMobile(page, { status: { data: stopped }, stop: { data: stopped }, resume: { data: OFF }, requests })
    await page.goto('/m/manage/alert')
    await expect(btn(page, '解除应急停服')).toBeVisible({ timeout: NAV_TIMEOUT })

    await btn(page, '解除应急停服').click()
    await page.locator('.el-message-box').getByRole('button', { name: '确认恢复' }).click()

    await expect.poll(() => requests.length).toBe(1)
    expect(requests[0].url).toContain('/m/emergency/resume')
    await expect(page.locator('.m-alert__banner')).toContainText('生产运行正常')
  })
})
