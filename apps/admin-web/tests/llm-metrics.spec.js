import { test, expect } from '@playwright/test'
import { setLoginState, llmMetricsResponse, llmMetricsLegacyResponse } from './helpers/mock'

/**
 * LLM 字数重试命中率页面 E2E 测试
 *
 * 覆盖：
 * - 派生率卡片显示（trigger_rate / improve_rate / not_improve_rate）
 * - 原始计数卡显示（total_calls / triggered / improved / not_improved）
 * - 漏斗可视化渲染（3 个 stage-bar）
 * - 刷新按钮触发重新加载
 * - 累计口径标注（T02508 / FR-UX-503：起点、PID、重启清零、缺字段退化）
 */
test.describe('LLM 重试指标页面', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s：真要放宽就写在具体断言上（{ timeout: N }）；
  // test.use({ expect: { timeout } }) 在 Playwright 1.61 是空选项，会被静默忽略（T02778）

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      await route.fulfill({ json: llmMetricsResponse })
    })
  })

  test('派生率卡片显示', async ({ page }) => {
    await page.goto('/stats/llm-metrics')

    // T00811：内容区标题已移除，标题改由导航栏展示（meta.title=LLM 重试指标）
    await expect(page.getByText('LLM 重试指标').first()).toBeVisible({ timeout: 30000 })

    // 3 个派生率卡片：触发率 / 改善率 / 未改善率
    await expect(page.getByText('触发率').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('改善率').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('未改善率').first()).toBeVisible({ timeout: 30000 })

    // 派生率数值：mock 数据 30.00% / 66.67% / 33.33%
    await expect(page.locator('.rate-value').filter({ hasText: '30.00' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.rate-value').filter({ hasText: '66.67' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.rate-value').filter({ hasText: '33.33' })).toBeVisible({ timeout: 30000 })
  })

  test('原始计数卡显示', async ({ page }) => {
    await page.goto('/stats/llm-metrics')

    // 4 个原始计数卡：标签与单位取自后端 meta（INT-UX-03：页面不再自带第二套文案）
    await expect(page.getByText('改写调用总数(次)').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('触发重试(次)').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('重试有改善(次)').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('重试未改善(次)').first()).toBeVisible({ timeout: 30000 })

    // 计数数值：mock 数据 100/30/20/10
    await expect(page.locator('.count-value').filter({ hasText: '100' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.count-value').filter({ hasText: '30' })).toBeVisible({ timeout: 30000 })
  })

  test('漏斗可视化渲染', async ({ page }) => {
    await page.goto('/stats/llm-metrics')

    // 漏斗卡片标题
    await expect(page.getByText('重试漏斗')).toBeVisible({ timeout: 30000 })

    // 3 个漏斗阶段：总调用 / 触发重试 / 重试改善
    await expect(page.locator('.stage-label').filter({ hasText: '总调用' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-label').filter({ hasText: '触发重试' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-label').filter({ hasText: '重试改善' })).toBeVisible({ timeout: 30000 })

    // 漏斗数值：mock 数据 100/30/20
    await expect(page.locator('.stage-value').filter({ hasText: '100' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-value').filter({ hasText: '30' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.stage-value').filter({ hasText: '20' })).toBeVisible({ timeout: 30000 })
  })

  test('刷新按钮触发重新加载', async ({ page }) => {
    let callCount = 0
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      callCount++
      await route.fulfill({ json: llmMetricsResponse })
    })

    await page.goto('/stats/llm-metrics')
    await expect(page.getByText('触发率').first()).toBeVisible({ timeout: 30000 })
    const initialCount = callCount

    // 点击刷新按钮
    await page.getByRole('button', { name: /刷新/ }).click()

    // 应触发一次新的 llm-metrics 请求
    await expect.poll(() => callCount).toBe(initialCount + 1)
  })

  // T02508（FR-UX-503）：本页计数全部是进程内累计，重启归零。
  // PRD ACC-UX-501 要求「LLM 指标页明确显示累计自 x 时间，重启清零」，
  // 这里断言的是"起点时间 + PID + 重启清零"三个要素都在页面上，而不只是一句空话
  test('累计口径标注：写明累计起点与重启清零', async ({ page }) => {
    await page.goto('/stats/llm-metrics')
    const note = page.locator('[data-guide="llm-metrics-scope"]')

    await expect(note).toContainText('累计自 2026-07-18 09:30:00', { timeout: 30000 })
    await expect(note).toContainText('PID 4321')
    await expect(note).toContainText('重启后清零')
    // 运行时长让运维判断样本攒了多久（不断言具体天数，测试机时间不固定）
    await expect(note).toContainText('已运行')
  })

  test('后端未升级时不编造起点日期', async ({ page }) => {
    // 后注册的 route 优先命中：用不含 started_at 的老响应覆盖 beforeEach 的 mock
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      await route.fulfill({ json: llmMetricsLegacyResponse })
    })
    await page.goto('/stats/llm-metrics')
    const note = page.locator('[data-guide="llm-metrics-scope"]')

    await expect(note).toContainText('后端未返回累计起点时间', { timeout: 30000 })
    await expect(note).not.toContainText(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/)
    // 口径字段缺失不能连带把数据也弄没
    await expect(page.locator('.count-value').filter({ hasText: '100' })).toBeVisible({
      timeout: 30000,
    })
  })

  test('零调用空态同样标注口径', async ({ page }) => {
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      await route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            total_calls: 0,
            triggered: 0,
            improved: 0,
            not_improved: 0,
            trigger_rate: 0.0,
            improve_rate: 0.0,
            not_improve_rate: 0.0,
            started_at: '2026-07-18T09:30:00',
            pid: 4321,
          },
        },
      })
    })
    await page.goto('/stats/llm-metrics')

    // 空态时"0%"最容易被误读成"问题已修复"，口径必须在这时候也在场
    await expect(page.getByText('暂无 LLM 调用数据')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('[data-guide="llm-metrics-scope"]')).toContainText(
      '累计自 2026-07-18 09:30:00',
    )
  })

  // T02728：漏斗三段曾直接拿主题色当底色 —— 马卡龙主题 --on-primary 与
  // --color-primary-dark 都是 #2D6B5F，末段文字 1.0:1 完全看不见，首段 3.4:1、
  // 中段 2.4:1 也不达 AA。这里不钉具体色值（换色板不该让测试变脆），而是把
  // computed color 与**实际落底背景**读出来算 WCAG 比值，6 套主题都必须 ≥ 4.5:1。
  test('漏斗三段与派生率在 6 套主题下文字对比度达 AA（T02728）', async ({ page }) => {
    // 自备 mock：让 warning / success / danger 三种状态各出现一次。
    // 默认 mock 的 30/66.67/33.33 不含 danger，测不到 is-danger 的文字色。
    await page.route('**/admin/api/v1/stats/llm-metrics*', async (route) => {
      await route.fulfill({
        json: {
          code: 0,
          message: 'success',
          data: {
            ...llmMetricsResponse.data,
            triggered: 40,
            improved: 20,
            not_improved: 24,
            trigger_rate: 40.0,
            improve_rate: 50.0,
            not_improve_rate: 60.0,
          },
        },
      })
    })
    await page.goto('/stats/llm-metrics')
    await expect(page.locator('.stage-bar')).toHaveCount(3, { timeout: 30000 })
    // 三种状态色必须都在场，否则这条用例可能只覆盖到一种颜色
    await expect(page.locator('.rate-card.is-warning')).toHaveCount(1)
    await expect(page.locator('.rate-card.is-success')).toHaveCount(1)
    await expect(page.locator('.rate-card.is-danger')).toHaveCount(1)

    const offenders = []
    for (const theme of ALL_THEMES) {
      // 用「写入 localStorage + 重载」切主题，而不是改 data-theme 属性：
      // el-card 的背景色带 transition，运行时切属性会量到过渡中的中间色。
      // 这条路径也正是 src/main.js 启动时的主题落定方式。
      await page.addInitScript((t) => localStorage.setItem('admin_theme', t), theme)
      await page.reload()
      await expect(page.locator('.stage-bar')).toHaveCount(3, { timeout: 30000 })
      await expect(page.locator('.rate-card.is-warning')).toHaveCount(1)
      await expect(page.locator('.rate-card.is-success')).toHaveCount(1)
      await expect(page.locator('.rate-card.is-danger')).toHaveCount(1)

      const rows = await page.evaluate(() => {
        const parse = (s) => {
          const m = /rgba?\(([^)]+)\)/.exec(s || '')
          if (!m) return null
          const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number)
          return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }
        }
        // 沿祖先找第一个不透明背景：rate-value 自己没有底色，落底的是 el-card
        const bgOf = (el) => {
          let n = el
          while (n && n.nodeType === 1) {
            const c = parse(getComputedStyle(n).backgroundColor)
            if (c && c.a >= 0.9) return c
            n = n.parentElement
          }
          return { r: 255, g: 255, b: 255, a: 1 }
        }
        const collect = (sel, kind) =>
          Array.from(document.querySelectorAll(sel)).map((el) => {
            const bg = bgOf(el)
            return {
              kind,
              text: el.textContent.trim(),
              color: getComputedStyle(el).color,
              bg: `rgb(${bg.r}, ${bg.g}, ${bg.b})`,
            }
          })
        return [...collect('.stage-bar', 'stage-bar'), ...collect('.rate-value', 'rate-value')]
      })

      expect(rows, `${theme} 主题下没量到三段条与三个派生率`).toHaveLength(6)
      for (const row of rows) {
        const ratio = wcagRatio(row.color, row.bg)
        if (ratio < AA_MIN) {
          offenders.push(
            `${theme} ${row.kind}「${row.text}」 ${ratio.toFixed(2)}:1 < ${AA_MIN}（${row.color} on ${row.bg}）`,
          )
        }
      }
    }

    expect(offenders, '以下文字对比度不达 AA：\n      ' + offenders.join('\n      ')).toEqual([])
  })
})

/** 6 套主题与 src/stores/theme.js 的 THEMES 一一对应 */
const ALL_THEMES = ['macaron', 'enterprise', 'creative', 'showcase', 'commerce', 'portfolio']
const AA_MIN = 4.5

/** WCAG 2.x 相对亮度对比度；输入是 getComputedStyle 的 rgb()/rgba() 字符串 */
function wcagRatio(fg, bg) {
  const parse = (s) => {
    const m = /rgba?\(([^)]+)\)/.exec(s || '')
    if (!m) return null
    const [r, g, b] = m[1].split(/[,\s/]+/).filter(Boolean).map(Number)
    return { r, g, b }
  }
  const lum = (c) => {
    const f = (v) => {
      const x = v / 255
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4)
    }
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
  }
  const a = parse(fg)
  const b = parse(bg)
  if (!a || !b) throw new Error(`无法解析颜色：${fg} / ${bg}`)
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

