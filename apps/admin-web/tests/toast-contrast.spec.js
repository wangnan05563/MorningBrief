import { test, expect } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { setLoginState } from './helpers/mock'

/**
 * 全局提示（ElMessage / ElMessageBox / ElAlert）对比度门禁（T03330）
 *
 * 缺陷面：variables.scss 把 `--el-color-success/warning/danger/info` 直接指向主题的
 * 粉彩色（#B5EAD7 等），而 Element Plus 的 `.el-message--success` 用
 * `--el-color-success` 当**正文色**、light-9（#f0f9eb）当**底色**。
 * 两者都是浅色：T03304 实测 success 1.24:1、warning 1.14:1，正文几乎不可见。
 *
 * 这里不靠肉眼：直接取 `.el-message__content` 的 computed color 与实际落底背景
 * （往祖先找第一个不透明背景），按 WCAG 公式算比值；6 套主题 × 4 类逐一量。
 * 暗色主题（showcase）另加一条：toast 底色必须也是深的，否则就是暗色页里一块白斑。
 *
 * 同一套「粉彩当正文」的映射还出现在：
 *   - `.el-alert--*.is-light`：容器 color 与 description 都取 --el-color-*；
 *   - `.el-message-box__status.el-message-box-icon--*`：图标取 --el-color-*（非文字 3:1）。
 * 两者都在本用例里用真实页面/真实组件量，避免只修 toast 留着同源缺陷。
 *
 * 证据落盘：`T03330_EVIDENCE=before|after npx playwright test tests/toast-contrast.spec.js`
 * 会把实测表写到 `_validate/news2/T03330_run/toast_contrast_<label>.json`（gitignore 内）。
 */

const THEMES = ['macaron', 'enterprise', 'creative', 'showcase', 'commerce', 'portfolio']
const DARK_THEME = 'showcase'
const TYPES = ['success', 'warning', 'error', 'info']

const EVIDENCE_LABEL = process.env.T03330_EVIDENCE
const EVIDENCE_DIR = fileURLToPath(new URL('../../../_validate/news2/T03330_run/', import.meta.url))

/**
 * 每个用例各写各的文件：fullyParallel 下同一文件的用例可能落在不同 worker，
 * 共用一个 afterAll 写同一个文件会互相覆盖（后写完的把先写完的冲掉）。
 */
function saveEvidence(name, rows) {
  if (!EVIDENCE_LABEL) return
  mkdirSync(EVIDENCE_DIR, { recursive: true })
  writeFileSync(
    `${EVIDENCE_DIR}/${name}_${EVIDENCE_LABEL}.json`,
    JSON.stringify({ label: EVIDENCE_LABEL, measured_at: new Date().toISOString(), rows }, null, 2),
  )
}

async function mockShell(page) {
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
    return route.fulfill({ json: { code: 0, message: 'success', data: { items: [], list: [], total: 0 } } })
  })
}

async function gotoReady(page, path) {
  await page.goto(path, { waitUntil: 'networkidle' })
  await page.waitForSelector('#app-splash', { state: 'detached', timeout: 30000 })
  // 与 nfr04 同口径：splash 收起后再等一拍，避免量到入场动画中间的透明度
  await page.waitForTimeout(1200)
}

async function useTheme(page, theme) {
  await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
  const applied = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
  expect(applied, `主题 ${theme} 没落到 data-theme 上`).toBe(theme)
}

async function clearToasts(page) {
  await page.evaluate(() => globalThis.__safeMessage.reset())
  await page.waitForFunction(() => document.querySelectorAll('.el-message').length === 0)
}

/** 页内测量：按 WCAG 2.x 相对亮度算对比度，返回前景/背景与比值 */
function measureToastInPage(type) {
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
  const bgOf = (el) => {
    let n = el
    while (n && n.nodeType === 1) {
      const c = parse(getComputedStyle(n).backgroundColor)
      if (c && c.a >= 0.9) return c
      n = n.parentElement
    }
    return { r: 255, g: 255, b: 255, a: 1 }
  }
  const hex = (c) => '#' + [c.r, c.g, c.b].map((v) => v.toString(16).padStart(2, '0')).join('')

  const boxes = [...document.querySelectorAll(`.el-message--${type}`)]
  const box = boxes[boxes.length - 1]
  if (!box) return null
  const content = box.querySelector('.el-message__content')
  const icon = box.querySelector('[class*="el-message-icon--"]')
  const close = box.querySelector('.el-message__closeBtn')
  const bg = bgOf(content)
  const fg = parse(getComputedStyle(content).color)
  const iconColor = icon ? parse(getComputedStyle(icon).color) : null
  const closeColor = close ? parse(getComputedStyle(close).color) : null
  return {
    fg: hex(fg),
    bg: hex(bg),
    contrast: +ratio(fg, bg).toFixed(2),
    bgLum: +lum(bg).toFixed(3),
    text: content.textContent.trim(),
    icon: iconColor ? { color: hex(iconColor), contrast: +ratio(iconColor, bg).toFixed(2) } : null,
    close: closeColor ? { color: hex(closeColor), contrast: +ratio(closeColor, bg).toFixed(2) } : null,
    theme: document.documentElement.getAttribute('data-theme'),
  }
}

async function showToast(page, type, text) {
  await page.evaluate(
    ([t, s]) => globalThis.__safeMessage.show(t, s),
    [type, text],
  )
  await page.waitForFunction(
    (s) => [...document.querySelectorAll('.el-message__content')].some((e) => e.textContent === s),
    text,
  )
}

test.describe('全局 toast 四类 × 六主题', () => {
  test('正文对比度 ≥ 4.5:1，暗色 toast 不得是浅底', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockShell(page)
    await gotoReady(page, '/review')

    const failures = []
    const rows = []
    for (const theme of THEMES) {
      await useTheme(page, theme)
      for (const type of TYPES) {
        await clearToasts(page)
        const text = `对比度实测-${theme}-${type}`
        await showToast(page, type, text)
        const m = await page.evaluate(measureToastInPage, type)
        expect(m, `${theme}/${type} 的 toast 没渲染出来，这条等于没量`).not.toBeNull()
        rows.push({ kind: 'message', theme, type, ...m })
        if (m.contrast < 4.5) {
          failures.push(`${theme}/${type} 正文 ${m.fg} on ${m.bg} = ${m.contrast}:1`)
        }
        if (theme === DARK_THEME && m.bgLum > 0.2) {
          failures.push(`${theme}/${type} 底色 ${m.bg} 仍是浅色（亮度 ${m.bgLum}），暗色页里是一块白斑`)
        }
        if (m.close && m.close.contrast < 3) {
          failures.push(`${theme}/${type} 关闭按钮 ${m.close.color} = ${m.close.contrast}:1（非文字需 3:1）`)
        }
      }
    }
    await clearToasts(page)
    saveEvidence('toast_messages', rows)
    expect(failures, '这些 toast 的文字/底色组合不达 WCAG：\n      ' + failures.join('\n      ')).toEqual([])
  })
})

/** 页内测量消息框：正文/标题文字需 4.5:1，状态图标按非文字 3:1 */
function measureMessageBoxInPage() {
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
  const hex = (c) => '#' + [c.r, c.g, c.b].map((v) => v.toString(16).padStart(2, '0')).join('')
  const box = document.querySelector('.el-message-box')
  if (!box) return null
  const bg = parse(getComputedStyle(box).backgroundColor)
  const title = box.querySelector('.el-message-box__title')
  const body = box.querySelector('.el-message-box__message')
  const icon = box.querySelector('.el-message-box__status')
  const read = (el) => (el ? { color: hex(parse(getComputedStyle(el).color)), contrast: +ratio(parse(getComputedStyle(el).color), bg).toFixed(2) } : null)
  return {
    bg: hex(bg),
    bgLum: +lum(bg).toFixed(3),
    title: read(title),
    body: read(body),
    icon: read(icon),
    theme: document.documentElement.getAttribute('data-theme'),
  }
}

test.describe('ElMessageBox 状态图标与文字', () => {
  for (const theme of ['macaron', DARK_THEME]) {
    test(`${theme}：四类消息框文字 ≥4.5、图标 ≥3`, async ({ page }) => {
      await setLoginState(page, 'admin')
      await mockShell(page)
      await gotoReady(page, '/review')
      await useTheme(page, theme)

      const failures = []
      const rows = []
      for (const type of TYPES) {
        const text = `消息框对比度-${theme}-${type}`
        await page.evaluate(async ([t, s]) => {
          const m = await import('/src/utils/message.js')
          m.ElMessageBox.alert(s, '对比度实测', { type: t, confirmButtonText: '知道了' })
        }, [type, text])
        await page.waitForSelector('.el-message-box')
        await page.waitForTimeout(200)
        const m = await page.evaluate(measureMessageBoxInPage)
        expect(m, `${theme}/${type} 的消息框没渲染出来`).not.toBeNull()
        rows.push({ kind: 'messagebox', theme, type, ...m })
        for (const key of ['title', 'body']) {
          if (m[key] && m[key].contrast < 4.5) {
            failures.push(`${theme}/${type} ${key} ${m[key].color} on ${m.bg} = ${m[key].contrast}:1`)
          }
        }
        if (m.icon && m.icon.contrast < 3) {
          failures.push(`${theme}/${type} 状态图标 ${m.icon.color} on ${m.bg} = ${m.icon.contrast}:1（非文字需 3:1）`)
        }
        // alert 形态默认不响应 Esc，直接点确认按钮收掉
        await page.locator('.el-message-box__btns .el-button--primary').click()
        await page.waitForSelector('.el-message-box', { state: 'detached' })
      }
      saveEvidence(`toast_messagebox_${theme}`, rows)
      expect(failures, '消息框这些组合不达 WCAG：\n      ' + failures.join('\n      ')).toEqual([])
    })
  }
})

/** 页内测量 el-alert：标题/描述与容器底色 */
function measureAlertInPage(selector) {
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
  const hex = (c) => '#' + [c.r, c.g, c.b].map((v) => v.toString(16).padStart(2, '0')).join('')
  /** 沿祖先收集半透明背景并自下而上合成：showcase 的 .el-alert 是 rgba 叠在深底上 */
  const bgOf = (el) => {
    const stack = []
    let n = el
    while (n && n.nodeType === 1) {
      const c = parse(getComputedStyle(n).backgroundColor)
      if (c && c.a > 0) {
        stack.push(c)
        if (c.a >= 0.999) break
      }
      n = n.parentElement
    }
    let base = { r: 255, g: 255, b: 255, a: 1 }
    for (let i = stack.length - 1; i >= 0; i--) {
      const top = stack[i]
      base = {
        r: top.r * top.a + base.r * (1 - top.a),
        g: top.g * top.a + base.g * (1 - top.a),
        b: top.b * top.a + base.b * (1 - top.a),
        a: 1,
      }
    }
    return base
  }
  const box = document.querySelector(selector)
  if (!box) return null
  const bg = bgOf(box)
  const title = box.querySelector('.el-alert__title')
  const desc = box.querySelector('.el-alert__description')
  const read = (el) => (el ? { color: hex(parse(getComputedStyle(el).color)), contrast: +ratio(parse(getComputedStyle(el).color), bg).toFixed(2) } : null)
  return {
    bg: hex(bg),
    bgLum: +lum(bg).toFixed(3),
    title: read(title),
    description: read(desc),
    theme: document.documentElement.getAttribute('data-theme'),
  }
}

test.describe('ElAlert 通知条（is-light）', () => {
  test('warning（投放深链修正）与 error（配置加载失败）在浅/暗主题都达 AA', async ({ page }) => {
    await setLoginState(page, 'admin')
    // 后注册的 route 优先，所以宽口径要先挂、具体接口后挂
    await mockShell(page)
    await page.route('**/admin/api/v1/ads/placements*', (route) =>
      route.fulfill({ json: { code: 0, message: 'success', data: { total: 45, list: [] } } }),
    )
    await gotoReady(page, '/ads/placements?enabled=2&page=abc&size=7')
    await expect(page.locator('[data-guide="ads-url-corrected"]')).toBeVisible()

    const failures = []
    const rows = []
    for (const theme of ['macaron', DARK_THEME]) {
      await useTheme(page, theme)
      const m = await page.evaluate(measureAlertInPage, '[data-guide="ads-url-corrected"]')
      rows.push({ kind: 'alert', alert: 'warning', theme, ...m })
      for (const key of ['title', 'description']) {
        if (m[key] && m[key].contrast < 4.5) {
          failures.push(`${theme}/warning ${key} ${m[key].color} on ${m.bg} = ${m[key].contrast}:1`)
        }
      }
      if (theme === DARK_THEME && m.bgLum > 0.2) failures.push(`warning 暗色下底色 ${m.bg} 仍是浅色`)
    }

    // 配置加载失败：真实页面里的 ConfigLoadError（type=error 的 el-alert）
    await page.unroute('**/admin/api/v1/**')
    await page.route('**/admin/api/v1/**', (route) =>
      route.fulfill({ status: 500, json: { code: 500, message: '配置读取失败', data: null } }),
    )
    await gotoReady(page, '/cos-config')
    await expect(page.locator('.config-load-error')).toBeVisible()
    for (const theme of ['macaron', DARK_THEME]) {
      await useTheme(page, theme)
      const m = await page.evaluate(measureAlertInPage, '.config-load-error')
      rows.push({ kind: 'alert', alert: 'error', theme, ...m })
      for (const key of ['title', 'description']) {
        if (m[key] && m[key].contrast < 4.5) {
          failures.push(`${theme}/error ${key} ${m[key].color} on ${m.bg} = ${m[key].contrast}:1`)
        }
      }
      if (theme === DARK_THEME && m.bgLum > 0.2) failures.push(`error 暗色下底色 ${m.bg} 仍是浅色`)
    }

    expect(failures, '通知条这些组合不达 WCAG：\n      ' + failures.join('\n      ')).toEqual([])
    saveEvidence('toast_alerts', rows)
  })
})
