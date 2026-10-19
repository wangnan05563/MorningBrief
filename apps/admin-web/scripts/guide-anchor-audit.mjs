/**
 * 引导锚点运行时审计（T02502）
 *
 * 为什么需要它：构建期门禁（validate-nav）只能证明「选择器写的东西在源码里存在」，
 * 证明不了「引导真的指到了它想指的那个元素」——T02500 抓到的那条就是选择器存在、
 * 但因为 tooltip 文案恰好等于 aria-label 的兄弟元素而指错。
 * 本脚本按 GUIDE_STEPS 逐页逐步真跑一遍，记录每步命中的元素（标签 / aria-label /
 * 可见文案 / 类名）与是否落空居中，产出 JSON 供人工核对文案与界面是否一致。
 *
 * 用法（需 dev server 在 5181）：
 *   node scripts/guide-anchor-audit.mjs [--out=../../../_validate/news2/guide_anchor_audit.json] [--routes=/review,/workflows]
 */
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
import { GUIDE_STEPS } from '../src/guide/guideConfig.js'

const argv = process.argv.slice(2)
const arg = (name, dflt) => {
  const hit = argv.find((a) => a.startsWith(`--${name}=`))
  return hit ? hit.split('=').slice(1).join('=') : dflt
}
const BASE = arg('base', 'http://localhost:5181')
const OUT = arg('out', '../../../_validate/news2/guide_anchor_audit.json')
const only = arg('routes', '')
const routes = only ? only.split(',') : Object.keys(GUIDE_STEPS)

function describe(el) {
  if (!el) return null
  const text = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40)
  return {
    tag: el.tagName.toLowerCase(),
    ariaLabel: el.getAttribute('aria-label') || null,
    cls: el.className?.baseVal ?? (typeof el.className === 'string' ? el.className : ''),
    text,
  }
}

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || 'chrome' })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
// 注入登录态：路由守卫以 localStorage 的 admin_role 作为已登录代理
await ctx.addInitScript(() => {
  localStorage.setItem('admin_role', 'admin')
  localStorage.setItem('admin_username', 'audit')
})
const page = await ctx.newPage()
// 后端不要求在线：所有接口回空壳，审计只关心静态骨架与锚点命中
// 数据依赖锚点：视图在空态会走 el-empty 分支，被引导的卡片/表格根本不渲染。
// 对这类接口回「足以渲染骨架」的最小 fixture，其余接口仍回空壳。
const FIXTURES = [
  ['/stats/llm-metrics', {
    total_calls: 120, triggered: 60, improved: 30, not_improved: 30,
    trigger_rate: 50, improve_rate: 50, not_improve_rate: 50,
  }],
]
await page.route('**/admin/api/v1/**', (route) => {
  const url = route.request().url()
  const hit = FIXTURES.find(([p]) => url.includes(p))
  return route.fulfill({
    json: { code: 0, message: 'ok', data: hit ? hit[1] : { total: 0, list: [], items: [] } },
  })
})

const report = []
for (const route of routes) {
  const steps = GUIDE_STEPS[route] || []
  await page.goto(`${BASE}${route}?guide=demo`, { waitUntil: 'domcontentloaded' })
  const bubble = page.locator('.mb-guide-bubble')
  const entry = { route, steps: [] }
  try {
    await bubble.waitFor({ timeout: 15000 })
  } catch {
    entry.error = '引导未弹出（该路由可能不在 GUIDE_STEPS 生效路径上）'
    report.push(entry)
    continue
  }
  for (let i = 0; i < steps.length; i += 1) {
    const step = steps[i]
    const info = await page.evaluate(() => {
      const hit = document.querySelector('.mb-guide-highlight')
      const b = document.querySelector('.mb-guide-bubble')
      return {
        missing: b?.dataset?.guideMissing ?? null,
        title: b?.querySelector('.mb-guide-title')?.textContent?.trim() ?? null,
        hit: hit
          ? {
              tag: hit.tagName.toLowerCase(),
              ariaLabel: hit.getAttribute('aria-label'),
              dataGuide: hit.getAttribute('data-guide'),
              cls: typeof hit.className === 'string' ? hit.className : '',
              text: (hit.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40),
            }
          : null,
      }
    })
    entry.steps.push({
      index: i,
      stepTitle: step.t,
      renderedTitle: info.title,
      selectors: step.s,
      hit: info.hit,
      missing: info.missing,
    })
    if (info.title !== step.t) entry.titleDrift = `${entry.titleDrift || ''} [步${i}] 配置「${step.t}」≠ 渲染「${info.title}」`
    const next = bubble.getByRole('button', { name: /^(下一步|完成)$/ })
    if (i < steps.length - 1) await next.click()
  }
  report.push(entry)
}
await browser.close()

const flat = report.flatMap((r) =>
  (r.steps || []).map((s) => ({ route: r.route, ...s })),
)
const missing = flat.filter((s) => s.missing)
const drifted = report.filter((r) => r.titleDrift)
const summary = {
  generatedAt: new Date().toISOString(),
  routes: report.length,
  steps: flat.length,
  missingSteps: missing.length,
  titleDrift: drifted.map((r) => ({ route: r.route, drift: r.titleDrift })),
  hits: flat.map((s) => ({
    route: s.route,
    step: s.stepTitle,
    selector: s.selectors[0],
    hit: s.hit ? `${s.hit.tag}[aria-label=${s.hit.ariaLabel || '-'}][data-guide=${s.hit.dataGuide || '-'}] "${s.hit.text}"` : '（未命中）',
  })),
}
fs.writeFileSync(path.resolve(import.meta.dirname, OUT), JSON.stringify({ summary, report }, null, 2))
console.log(`[guide-audit] 路由 ${summary.routes} · 步骤 ${summary.steps} · 未命中 ${summary.missingSteps} · 标题漂移 ${summary.titleDrift.length}`)
for (const h of summary.hits) console.log(`  ${h.route} · ${h.step} → ${h.selector} ⇒ ${h.hit}`)
for (const m of missing) console.log(`  ✗ 未命中：${m.route} · ${m.stepTitle} · 选择器 ${m.selectors.join(' , ')}`)
console.log(`报告已写入 ${OUT}`)
