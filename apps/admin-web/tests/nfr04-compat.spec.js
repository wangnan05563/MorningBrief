import { test, expect } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { setLoginState, MOBILE_VIEWPORT } from './helpers/mock'

/**
 * NFR-UX-04 兼容性截图验收（T02522）
 *
 * PRD 把这一条的验收方式写成「截图验收」，但人眼看截图有两个坑：
 * 看不清 1.54:1 的字到底差不达标，也看不出「这块白是不是故意的」。
 * 所以这里把验收拆成三个可判定的量，截图只作为附带产物：
 *
 *   1) 白底孤岛 —— 暗色主题下自身背景接近纯白、且面积可观的块；
 *   2) 文字对比度 —— 文字颜色与它**实际落底背景**（沿祖先找第一个不透明背景）的
 *      WCAG 比值，正文 < 4.5、大字 < 3 判不达标；
 *   3) 375px 横向溢出 —— documentElement.scrollWidth 超出视口的像素数。
 *
 * 覆盖范围：暗色主题取 6 套里唯一的 `isDark` 主题 showcase；
 * 375px 取 NFR-UX-04 写明的验收宽度。
 *
 * 移动端 H5（`/m/*`）也曾整层硬编码浅色、零主题变量，暗色主题对它不生效；
 * 现已由 T02839 收口：外壳与 12 个视图统一走 `--m-*` 语义 token，
 * 暗色下的孤岛/对比度按「必须为零」判定（下面第三条移动端用例）。
 *
 * 截图证据：`COMPAT_SHOTS=1 npx playwright test tests/nfr04-compat.spec.js`
 * 会把整页截图写到 `_validate/news2/`（gitignore 内，不入库）。
 */

const SHOT_DIR = process.env.COMPAT_SHOTS
  ? new URL('../../../_validate/news2/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')
  : null
if (SHOT_DIR) mkdirSync(SHOT_DIR, { recursive: true })

/** 6 套主题里唯一 isDark 的：见 src/stores/theme.js */
const DARK_THEME = 'showcase'

const PC_PAGES = [
  '/review',
  '/queue',
  '/workflows',
  '/channels',
  '/stats/channel-health',
  '/stats/llm-metrics',
  '/stats/rss-health',
  '/db-admin',
  '/help',
  '/about',
]
const M_PAGES = ['/m/home', '/m/review', '/m/message', '/m/mine', '/m/manage', '/m/manage/users', '/m/manage/alert']

/**
 * 移动端（T02839）：外壳与 12 个视图已改用 themes/variables 的 --m-* token，
 * 暗色下不再有白底孤岛；次级文字取 --color-text-secondary（浅色主题 ≥ 4.5:1）。
 * 这里不再保留「基线天花板」——任何一块孤岛或一处不达标文字都直接红。
 */

async function mockShell(page) {
  // 就绪探针不 mock 的话 splash 要等 2s 网络失败才收起，量到的会是启动画面本身
  await page.route('**/api/health/ready', (route) => route.fulfill({ status: 200, json: { status: 'ok' } }))
  await page.route('**/admin/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/events/stream')) {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: 'event: connected\ndata: {"type":"connected","data":{},"timestamp":0}\n\n',
      })
    }
    if (path.endsWith('/m/dashboard-summary')) {
      return route.fulfill({
        json: { code: 0, message: 'success', data: { today: 2, pending_review: 3, unread_message: 5 } },
      })
    }
    return route.fulfill({ json: { code: 0, message: 'success', data: { items: [], list: [], total: 0 } } })
  })
}

/** 进页后必须等 splash 真正移除，否则量到的是启动画面 */
async function gotoReady(page, path) {
  await page.goto(path, { waitUntil: 'networkidle' })
  await page.waitForSelector('#app-splash', { state: 'detached', timeout: 30000 })
  // 基线数值是在「splash 收起后再等 1.2s」的同一条件下测出来的，缩短会让计数抖动
  await page.waitForTimeout(1200)
}

/**
 * 页内测量：返回白底孤岛、对比度不达标文字、横向溢出像素。
 * 只统计视口内、面积可观的元素——屏外与 1px 装饰线不参与判定。
 */
function measure() {
  const parse = (s) => {
    const m = /rgba?\(([^)]+)\)/.exec(s)
    if (!m) return null
    const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number)
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }
  }
  const lum = (c) => {
    const f = (v) => {
      v /= 255
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
    }
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
  }
  const ratio = (a, b) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
    return (hi + 0.05) / (lo + 0.05)
  }
  const label = (el) => {
    const g = el.getAttribute('data-guide')
    if (g) return `[data-guide=${g}]`
    const chain = []
    let n = el
    while (n && n.nodeType === 1 && chain.length < 3) {
      const c = (n.className || '').toString().split(/\s+/).filter(Boolean)[0]
      chain.unshift(c ? `${n.tagName.toLowerCase()}.${c}` : n.tagName.toLowerCase())
      n = n.parentElement
    }
    return chain.join('>')
  }
  const bgOf = (el) => {
    let n = el
    while (n && n.nodeType === 1) {
      const c = parse(getComputedStyle(n).backgroundColor)
      if (c && c.a >= 0.9) return c
      n = n.parentElement
    }
    return { r: 255, g: 255, b: 255, a: 1 }
  }

  const pageBg = parse(getComputedStyle(document.body).backgroundColor)
  const rootDark = pageBg ? lum(pageBg) < 0.2 : false
  const islands = []
  const lowContrast = []
  for (const el of Array.from(document.querySelectorAll('body *'))) {
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue
    const r = el.getBoundingClientRect()
    if (r.width < 3 || r.height < 3) continue
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue

    const own = parse(cs.backgroundColor)
    if (rootDark && own && own.a >= 0.9 && lum(own) > 0.75 && r.width * r.height > 900) {
      islands.push({ sel: label(el), bg: cs.backgroundColor, size: `${Math.round(r.width)}x${Math.round(r.height)}` })
    }
    const hasText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim().length > 0)
    if (!hasText) continue
    const fg = parse(cs.color)
    if (!fg || fg.a < 0.9) continue
    const bg = bgOf(el)
    const cr = ratio(fg, bg)
    const px = parseFloat(cs.fontSize)
    const need = px >= 24 || (px >= 18.66 && +cs.fontWeight >= 700) ? 3 : 4.5
    if (cr < need) {
      lowContrast.push({
        sel: label(el),
        text: el.textContent.trim().slice(0, 20),
        cr: +cr.toFixed(2),
        need,
        color: cs.color,
        bg: `rgb(${bg.r},${bg.g},${bg.b})`,
      })
    }
  }
  return {
    theme: document.documentElement.getAttribute('data-theme'),
    overflowX: document.documentElement.scrollWidth - innerWidth,
    islands,
    lowContrast,
  }
}

/** 主题靠 localStorage 在 Vue 挂载前落定（src/main.js:76），所以必须用 addInitScript */
async function useTheme(page, theme) {
  await page.addInitScript(([t]) => localStorage.setItem('admin_theme', t), [theme])
}

const fmt = (rows) =>
  rows.map((x) => `${x.sel} cr=${x.cr}<${x.need} ${x.color} on ${x.bg}「${x.text}」`).join('\n      ')

test.describe('暗色主题（showcase）· PC 全页面', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await useTheme(page, DARK_THEME)
    await mockShell(page)
  })

  test('10 个 PC 页无白底孤岛、正文对比度达 AA', async ({ page }) => {
    const offenders = []
    for (const path of PC_PAGES) {
      await gotoReady(page, path)
      const m = await page.evaluate(measure)
      expect(m.theme, `${path} 暗色主题没生效（data-theme 不是 ${DARK_THEME}）`).toBe(DARK_THEME)
      if (m.islands.length || m.lowContrast.length) {
        offenders.push(`${path}\n      孤岛: ${fmt(m.islands) || '-'}\n      对比度: ${fmt(m.lowContrast) || '-'}`)
      }
      if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/_shot_t02522_dark_pc_${path.replace(/\W+/g, '_')}.png`, fullPage: true })
    }
    expect(offenders, '暗色主题下这些页面有白斑或读不清的字：\n      ' + offenders.join('\n      ')).toEqual([])
  })

  test('压在主色实底上的文字吃 --on-primary（头像不再是白字压在亮青上）', async ({ page }) => {
    // 修前实测：壳层头像白字 on #00E5FF = 1.54:1，每一页都中招（Element Plus 写死白色）
    await gotoReady(page, '/review')
    const avatar = page.locator('.user-info .el-avatar').first()
    await expect(avatar).toBeVisible()
    await expect(avatar).toHaveCSS('color', 'rgb(10, 10, 15)')
    const m = await page.evaluate(measure)
    expect(m.lowContrast, '壳层仍有不达标文字：\n      ' + fmt(m.lowContrast)).toEqual([])
  })

  test('暗色下空列表插画不再是白斑（截图肉眼抓到的，两类自动指标都盖不住）', async ({ page }) => {
    // 那幅纸盒 SVG 既没有 background-color 也没有文字：白底孤岛检测与对比度检测都看不见它，
    // 但它是暗色整页截图里最刺眼的一块。这里按「有效不透明度」钉住，防止后续有人把插画提亮。
    await gotoReady(page, '/review')
    const img = page.locator('.el-empty__image').first()
    await expect(img).toBeVisible()
    // 量的是真正被画出来的那一层（内层 svg/img）：容器自身 opacity 恒为 1，
    // 压暗规则落在子节点上，量容器会得到 1.00 的假失败（第一版踩的就是这个）
    const effective = await img.evaluate((el) => {
      const target = el.querySelector('svg, img') || el
      let a = 1
      for (let n = target; n && n.nodeType === 1; n = n.parentElement) a *= +getComputedStyle(n).opacity
      return a
    })
    expect(effective, `插画在暗色下仍然太亮（有效不透明度 ${effective.toFixed(2)}）`).toBeLessThan(0.4)
  })

  test('浅色主题不受该覆盖影响（马卡龙头像仍是它自己的 --on-primary）', async ({ page }) => {
    await gotoReady(page, '/review')
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'macaron')
    })
    const color = await page.locator('.user-info .el-avatar').first().evaluate((el) => getComputedStyle(el).color)
    expect(color).not.toBe('rgb(10, 10, 15)')
  })
})

test.describe('375px 移动宽度', () => {
  test.use({ viewport: MOBILE_VIEWPORT })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockShell(page)
  })

  test('移动端 7 页无横向溢出', async ({ page }) => {
    const overflow = []
    for (const path of M_PAGES) {
      await gotoReady(page, path)
      // 外壳必须真的按视口分流到移动端（否则量的是重定向后的 PC 页）
      await expect(page.locator('.m-app'), `${path} 没落在移动端外壳`).toBeVisible()
      const m = await page.evaluate(measure)
      if (m.overflowX > 0) overflow.push(`${path} 溢出 ${m.overflowX}px`)
      if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/_shot_t02522_m375_${path.replace(/\W+/g, '_')}.png`, fullPage: true })
    }
    expect(overflow, '375px 下这些页面出现横向滚动：\n      ' + overflow.join('\n      ')).toEqual([])
  })

  test('PC 路由在 375px 下按视口分流到移动端外壳（不会拿 1280 的表来挤 375）', async ({ page }) => {
    await gotoReady(page, '/review')
    expect(page.url()).toContain('/m/review')
    await gotoReady(page, '/queue')
    expect(page.url()).toContain('/m/manage/queue')
  })

  test('移动端暗色无白底孤岛、正文对比度达 AA（T02839）', async ({ page }) => {
    await useTheme(page, DARK_THEME)
    for (const path of M_PAGES) {
      await gotoReady(page, path)
      const m = await page.evaluate(measure)
      expect(m.theme, `${path} 暗色主题没生效`).toBe(DARK_THEME)
      expect(
        m.islands,
        `${path} 暗色下仍有白底孤岛：\n      ${fmt(m.islands)}`,
      ).toEqual([])
      expect(
        m.lowContrast,
        `${path} 暗色下仍有不达标文字：\n      ${fmt(m.lowContrast)}`,
      ).toEqual([])
      if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/_shot_t02839_dark_m375_${path.replace(/\W+/g, '_')}.png`, fullPage: true })
    }
  })

  // 对比度这条与暗色无关：次级文字 #8a8f99 on #fff 只有 3.25:1，默认马卡龙主题下就不达标
  test('移动端浅色主题正文对比度达 AA（T02839）', async ({ page }) => {
    for (const path of M_PAGES) {
      await gotoReady(page, path)
      const m = await page.evaluate(measure)
      expect(m.theme, `${path} 没落在默认浅色主题`).toBe('macaron')
      expect(
        m.lowContrast,
        `${path} 浅色主题下有不达标文字：\n      ${fmt(m.lowContrast)}`,
      ).toEqual([])
      if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/_shot_t02839_light_m375_${path.replace(/\W+/g, '_')}.png`, fullPage: true })
    }
  })
})
