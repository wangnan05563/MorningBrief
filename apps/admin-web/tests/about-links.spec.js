import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 关于页外链与更新态可信（T02503 / FR-UX-404、M94、M101、ACC-UX-401）
 *
 * 覆盖三件运行时才会暴露的事：
 * 1. 链接入口来自后端下发的仓库地址（REPO_URL）——未配置就不显示，
 *    而不是留着 5 条 example.com 占位外链原样出厂；
 * 2. API 文档入口只在后端真的挂了 /docs 时出现（生产 docs_url=None，点了是 404）；
 * 3. 检查更新降级（source=local）时显示「无法确认」+ 原因 + 重试，
 *    绝不显示绿色「已是最新」——那是对着没查成的结果谎报状态。
 *
 * window.open 用初始化脚本拦截记账：断言的是「打开的 URL 是什么」，
 * 不真去访问外网（沙箱里 github.com 的 HTML 不可达，只有 api.github.com 可达）。
 */

const ABOUT = '**/admin/api/v1/about/check-update**'
const ABOUT_INFO = '**/admin/api/v1/about**'

const ok = (data) => ({ code: 0, message: 'ok', data })

const REPO = 'https://github.com/wangnan05563/MorningBrief'

const baseInfo = {
  product: 'MorningBrief',
  version: 'v1.0.20260921.003',
  build_date: '2026-09-21',
  git_sha: 'abc1234',
  python: '3.12.0',
  platform: 'windows',
  repo_url: REPO,
  docs_enabled: false,
}

async function mockAbout(page, { info = {}, check }) {
  // 宽匹配先注册、精确路由后注册：Playwright 里后注册的处理器优先，
  // 若反过来，`/about` 会把 `/about/check-update` 一起吃掉
  await page.route(
    ABOUT_INFO,
    (route) => route.fulfill({ status: 200, json: ok({ ...baseInfo, ...info }) }),
  )
  await page.route(ABOUT, (route) => route.fulfill({ status: 200, json: ok(check) }))
}

const labelOf = (page, text) => page.locator('.menu-item', { hasText: text })

// vite 首次编译 /about 那条懒加载 chunk 可能超过默认 5s 断言超时（本文件第一条用例最容易踩），
// 因此先等链接卡片区出现，再逐条断言
async function openAbout(page) {
  await page.goto('/about', { waitUntil: 'load' })
  await expect(page.locator('.menu-card')).toBeVisible({ timeout: 30000 })
}

test.describe('帮助页 · API 文档入口按后端实况决定', () => {
  const apiBtn = (page) => page.getByRole('button', { name: 'API 文档', exact: true })

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
      Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
      window.__opened = []
      window.open = (url) => {
        window.__opened.push(url)
        return null
      }
    })
  })

  test('运营角色不显示入口：/about 是 admin 专属接口，点了只会报权限', async ({ page }) => {
    await setLoginState(page, 'operator')
    await page.goto('/help', { waitUntil: 'load' })
    await expect(apiBtn(page)).toHaveCount(0)
  })

  test('后端未挂载交互式文档：给出说明而不是打开 404 死链', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(ABOUT_INFO, (route) =>
      route.fulfill({ status: 200, json: ok({ ...baseInfo, docs_enabled: false }) }),
    )
    await page.goto('/help', { waitUntil: 'load' })
    await apiBtn(page).click()
    await expect(page.getByText('当前环境未开放交互式 API 文档')).toBeVisible()
    expect(await page.evaluate(() => window.__opened)).toEqual([])
  })

  test('后端开放了文档才真的打开 /news/docs', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(ABOUT_INFO, (route) =>
      route.fulfill({ status: 200, json: ok({ ...baseInfo, docs_enabled: true }) }),
    )
    await page.goto('/help', { waitUntil: 'load' })
    await apiBtn(page).click()
    await expect.poll(() => page.evaluate(() => window.__opened), { timeout: 10000 }).toEqual([
      '/news/docs',
    ])
  })
})

test.describe('关于页 · 外链来源与更新态', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(document, 'hidden', { get: () => false, configurable: true })
      Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true })
      window.__opened = []
      // 不真开窗口：外链在沙箱不可达，断言只需要「被打开的 URL 列表」
      window.open = (url) => {
        window.__opened.push(url)
        return null
      }
    })
    await setLoginState(page, 'admin')
  })

  test('仓库已配置：三条派生外链出现且地址正确，页面无 example.com', async ({ page }) => {
    await mockAbout(page, {
      check: { current: 'v1.0.20260921.003', latest: 'v1.0.20260921.003', has_update: false, release_url: `${REPO}/releases`, checked_at: '2026-10-19T10:00:00', source: 'remote', published_at: '2026-09-21T00:00:00' },
    })
    await openAbout(page)

    await expect(labelOf(page, '项目主页')).toBeVisible()
    await expect(labelOf(page, '版本发布')).toBeVisible()
    await expect(labelOf(page, '报告问题')).toBeVisible()
    // 站内两项始终存在
    await expect(labelOf(page, '帮助文档')).toBeVisible()
    await expect(labelOf(page, '开源软件声明')).toBeVisible()

    await labelOf(page, '项目主页').click()
    await labelOf(page, '版本发布').click()
    await labelOf(page, '报告问题').click()
    expect(await page.evaluate(() => window.__opened)).toEqual([
      REPO,
      `${REPO}/releases`,
      `${REPO}/issues`,
    ])

    const body = await page.locator('body').innerText()
    expect(body).not.toContain('example.com')
    // 未开放交互式文档时不提供死链入口
    expect(body).not.toContain('API 文档')
  })

  test('仓库未配置：仓库类外链整组隐藏，而不是留占位地址', async ({ page }) => {
    await mockAbout(page, {
      info: { repo_url: '' },
      check: { current: 'v1.0.20260921.003', latest: 'v1.0.20260921.003', has_update: false, release_url: 'https://github.com', checked_at: '2026-10-19T10:00:00', source: 'local', reason: 'repo_not_configured', error: '未配置代码仓库地址（REPO_URL），已跳过更新检查' },
    })
    await openAbout(page)
    await expect(labelOf(page, '帮助文档')).toBeVisible()
    await expect(labelOf(page, '项目主页')).toHaveCount(0)
    await expect(labelOf(page, '版本发布')).toHaveCount(0)
    await expect(labelOf(page, '报告问题')).toHaveCount(0)
    const body = await page.locator('body').innerText()
    expect(body).not.toContain('example.com')
  })

  test('后端开放了交互式文档才出现 API 文档入口，且指向 /news/docs', async ({ page }) => {
    await mockAbout(page, {
      info: { docs_enabled: true },
      check: { current: 'v1', latest: 'v1', has_update: false, release_url: `${REPO}/releases`, checked_at: '2026-10-19T10:00:00', source: 'remote', published_at: '2026-09-21T00:00:00' },
    })
    await openAbout(page)
    await expect(labelOf(page, 'API 文档')).toBeVisible()
    await labelOf(page, 'API 文档').click()
    expect(await page.evaluate(() => window.__opened)).toEqual(['/news/docs'])
  })

  test('检查降级：显示原因与重试入口，绝不显示「已是最新」（M94）', async ({ page }) => {
    await mockAbout(page, {
      check: { current: 'v1.0.20260921.003', latest: 'v1.0.20260921.003', has_update: false, release_url: `${REPO}/releases`, checked_at: '2026-10-19T10:00:00', source: 'local', reason: 'rate_limited', error: '更新服务访问受限（GitHub 频率限制），请稍后重试' },
    })
    await openAbout(page)
    await page.getByRole('button', { name: '检查更新', exact: true }).click()

    await expect(page.getByRole('button', { name: '无法确认，点击重试', exact: true })).toBeVisible()
    await expect(page.locator('.update-hint')).toHaveText('更新服务访问受限（GitHub 频率限制），请稍后重试')
    await expect(page.getByRole('button', { name: '已是最新', exact: true })).toHaveCount(0)
  })

  test('远端确认最新才显示「已是最新」', async ({ page }) => {
    await mockAbout(page, {
      check: { current: 'v1.0.20260921.003', latest: 'v1.0.20260921.003', has_update: false, release_url: `${REPO}/releases`, checked_at: '2026-10-19T10:00:00', source: 'remote', published_at: '2026-09-21T00:00:00' },
    })
    await openAbout(page)
    await page.getByRole('button', { name: '检查更新', exact: true }).click()
    await expect(page.getByRole('button', { name: '已是最新', exact: true })).toBeVisible()
  })
})
