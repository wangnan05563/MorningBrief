import { test, expect } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  setLoginState,
  queueStatsResponse,
  queueConfigResponse,
  channelsListResponse,
} from './helpers/mock'

/**
 * 状态标签（el-tag）对比度门禁（T03331）
 *
 * 缺陷面：EP 的 `.el-tag.el-tag--success` 把 --el-color-success（本项目的粉彩）
 * 当正文色，配 light-9 浅底；马卡龙主题实测 success 1.24、warning 1.14、
 * danger 1.82、info 1.42、默认 primary 1.37:1。
 *
 * 单测（tests/unit/tag-contrast.test.mjs）在源码层算 token，这里用真实浏览器
 * 量 computed color / 实际落底，两件事都要过：
 *   1) 真实 /queue 页的状态标签（默认 effect，四类都出现）；
 *   2) 5 类 × default/plain/dark 的夹具：显示色必须等于 --tag-* token，
 *      并逐一算对比度（防止选择器被 EP 按需样式压掉后「看似改了实则没生效」）。
 *
 * 证据落盘：`T03331_EVIDENCE=after npx playwright test tests/tag-contrast.spec.js`
 * 写到 `_validate/news2/T03331_run/tag_contrast_<label>.json`（gitignore 内）。
 */

const THEMES = ['macaron', 'enterprise', 'creative', 'showcase', 'commerce', 'portfolio']
const DARK_THEME = 'showcase'
const TYPES = ['success', 'warning', 'danger', 'info', 'primary']
const VARIANTS = ['default', 'plain', 'dark']

const EVIDENCE_LABEL = process.env.T03331_EVIDENCE
const EVIDENCE_DIR = fileURLToPath(new URL('../../../_validate/news2/T03331_run/', import.meta.url))

/** 每个用例各写各的文件：fullyParallel 下同文件用例可能落在不同 worker，共用文件会互相覆盖 */
function saveEvidence(name, rows) {
  if (!EVIDENCE_LABEL) return
  mkdirSync(EVIDENCE_DIR, { recursive: true })
  writeFileSync(
    `${EVIDENCE_DIR}/${name}_${EVIDENCE_LABEL}.json`,
    JSON.stringify({ label: EVIDENCE_LABEL, measured_at: new Date().toISOString(), rows }, null, 2),
  )
}

const QUEUE_TASKS = {
  code: 0,
  message: 'success',
  data: {
    total: 4,
    items: ['queued', 'running', 'success', 'failed'].map((status, i) => ({
      id: `wf-t03331-000${i + 1}`,
      episode_date: '2026-10-27',
      source: 'cron',
      status,
      channel_id: 1,
      channel_name: '科技频道',
      priority: 5,
      started_at: '2026-10-27T05:00:00',
      finished_at: null,
      error: null,
    })),
  },
}

async function mockQueuePage(page) {
  await page.route('**/api/health/ready', (route) => route.fulfill({ status: 200, json: { status: 'ok' } }))
  // 后注册的 route 优先：宽口径先挂，具体接口后挂
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
  await page.route('**/admin/api/v1/queue/stats', (route) => route.fulfill({ json: queueStatsResponse }))
  await page.route('**/admin/api/v1/queue/config', (route) => route.fulfill({ json: queueConfigResponse }))
  await page.route('**/admin/api/v1/queue/tasks*', (route) => route.fulfill({ json: QUEUE_TASKS }))
  await page.route('**/admin/api/v1/channels*', (route) => route.fulfill({ json: channelsListResponse }))
}

async function gotoReady(page, path) {
  await page.goto(path, { waitUntil: 'networkidle' })
  await page.waitForSelector('#app-splash', { state: 'detached', timeout: 30000 })
  await page.waitForTimeout(1200)
}

async function useTheme(page, theme) {
  await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
  const applied = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
  expect(applied, `主题 ${theme} 没落到 data-theme 上`).toBe(theme)
  // EP 的 .el-table--enable-row-transition 给 td 的 background-color 挂了
  // `transition: background-color .25s 1ms`：切主题后立刻量，拿到的是
  // 「浅色行底 → 暗色行底」的中间帧（仍是不透明的 #FAFAFA），暗色主题的
  // 标签会被误判成压在浅底上。等过渡结束再量（对比度只关心终值）。
  await page.waitForTimeout(500)
}

/**
 * 页内测量：取每个标签的 computed color 与实际落底（沿祖先合成半透明层），
 * 同时用一根探针元素解析 token 的实际色值，证明「显示的就是 token」。
 */
function measureTagsInPage(selector) {
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
const hex = (c) =>
    '#' + [c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')
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
  /** 用探针把自定义属性解析成浏览器归一化后的色值 */
  const tokenColor = (value) => {
    const probe = document.createElement('span')
    probe.style.color = value
    document.body.appendChild(probe)
    const out = getComputedStyle(probe).color
    probe.remove()
    return out
  }
  const TYPE_RE = /(?:^|\s)el-tag--(success|warning|danger|info|primary)(?:\s|$)/
  return [...document.querySelectorAll(selector)].map((el) => {
    const m = TYPE_RE.exec(el.className)
    if (!m) return null
    const type = m[1]
    const variant = el.classList.contains('el-tag--plain')
      ? 'plain'
      : el.classList.contains('el-tag--dark')
        ? 'dark'
        : 'default'
    const cs = getComputedStyle(el)
    const fg = parse(cs.color)
    const bg = bgOf(el)
    const bgToken = variant === 'plain' ? 'var(--el-fill-color-blank)' : `var(--tag-${type}-bg)`
    return {
      type,
      variant,
      fg: hex(fg),
      bg: hex(bg),
      contrast: +ratio(fg, bg).toFixed(2),
      bgLum: +lum(bg).toFixed(3),
      tokenFg: tokenColor(`var(--tag-${type}-fg)`),
      tokenBg: tokenColor(bgToken),
      actualFg: cs.color,
      actualBg: cs.backgroundColor,
      text: el.textContent.trim(),
      theme: document.documentElement.getAttribute('data-theme'),
    }
  }).filter(Boolean)
}

/** 5 类 × 3 变体夹具：真实 EP class 结构，容器用卡片底（标签几乎都长在卡片上） */
async function injectTagFixture(page) {
  await page.evaluate(([types, variants]) => {
    document.querySelector('[data-t03331-fixture]')?.remove()
    const wrap = document.createElement('div')
    wrap.setAttribute('data-t03331-fixture', '')
    wrap.style.cssText =
      'position:fixed;left:12px;top:12px;z-index:9999;display:flex;gap:8px;flex-wrap:wrap;' +
      'padding:12px;background-color:var(--color-bg-card);border:1px solid var(--color-border)'
    for (const type of types) {
      for (const variant of variants) {
        const tag = document.createElement('span')
        const classes = ['el-tag', `el-tag--${type}`]
        if (variant !== 'default') classes.push(`el-tag--${variant}`)
        tag.className = classes.join(' ')
        tag.textContent = `${type}-${variant}`
        wrap.appendChild(tag)
      }
    }
    document.body.appendChild(wrap)
  }, [TYPES, VARIANTS])
}

test.describe('状态标签对比度（T03331）', () => {
  test('真实队列页四类状态标签（默认 effect）在 6 主题下 ≥4.5:1', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockQueuePage(page)
    await gotoReady(page, '/queue')
    await page.waitForSelector('.el-tag--danger', { timeout: 30000 })

    const failures = []
    const rows = []
    for (const theme of THEMES) {
      await useTheme(page, theme)
      const measured = await page.evaluate(measureTagsInPage, '.el-table .el-tag')
      expect(measured.length, `${theme} 的队列页没量到状态标签，这条等于没量`).toBeGreaterThan(0)
      for (const m of measured) {
        rows.push({ kind: 'page', theme, ...m })
        if (m.contrast < 4.5) {
          failures.push(`${theme}/${m.type} 「${m.text}」 ${m.fg} on ${m.bg} = ${m.contrast}:1`)
        }
        if (m.actualFg !== m.tokenFg) {
          failures.push(`${theme}/${m.type} 显示色 ${m.actualFg} 不等于 token ${m.tokenFg}`)
        }
        if (theme === DARK_THEME && m.bgLum > 0.2) {
          failures.push(`${theme}/${m.type} 底色 ${m.bg} 仍是浅色（亮度 ${m.bgLum}）`)
        }
      }
      const seen = new Set(measured.map((m) => m.type))
      for (const type of ['info', 'warning', 'success', 'danger']) {
        if (!seen.has(type)) failures.push(`${theme} 队列页缺少 ${type} 标签，四类没覆盖全`)
      }
    }
    saveEvidence('tag_contrast_page', rows)
    expect(failures, '这些标签组合不达 WCAG：\n      ' + failures.join('\n      ')).toEqual([])
  })

  test('5 类 × default/plain/dark 在 6 主题下 ≥4.5:1，且显示色等于 token', async ({ page }) => {
    await setLoginState(page, 'admin')
    await mockQueuePage(page)
    await gotoReady(page, '/queue')

    const failures = []
    const rows = []
    for (const theme of THEMES) {
      await useTheme(page, theme)
      await injectTagFixture(page)
      const measured = await page.evaluate(measureTagsInPage, '[data-t03331-fixture] .el-tag')
      expect(measured.length, `${theme} 夹具没量到 15 个标签`).toBe(15)
      for (const m of measured) {
        rows.push({ kind: 'fixture', theme, ...m })
        if (m.contrast < 4.5) {
          failures.push(`${theme}/${m.type}/${m.variant} ${m.fg} on ${m.bg} = ${m.contrast}:1`)
        }
        if (m.actualFg !== m.tokenFg) {
          failures.push(`${theme}/${m.type}/${m.variant} 显示色 ${m.actualFg} 不等于 token ${m.tokenFg}`)
        }
        if (m.actualBg !== m.tokenBg) {
          failures.push(`${theme}/${m.type}/${m.variant} 底色 ${m.actualBg} 不等于 token ${m.tokenBg}`)
        }
        if (theme === DARK_THEME && m.variant !== 'plain' && m.bgLum > 0.2) {
          failures.push(`${theme}/${m.type}/${m.variant} 底色 ${m.bg} 仍是浅色（亮度 ${m.bgLum}）`)
        }
      }
    }
    saveEvidence('tag_contrast_fixture', rows)
    expect(failures, '这些标签组合不达 WCAG：\n      ' + failures.join('\n      ')).toEqual([])
  })
})
