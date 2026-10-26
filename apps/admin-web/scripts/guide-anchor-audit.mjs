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
 *   node scripts/guide-anchor-audit.mjs [--out=../../../_validate/news2/guide_anchor_audit.json] [--routes=/review,/workflows] [--empty]
 *
 * T02656：页面现在会按数据可用性跳过步骤（`skipWhenEmpty`），所以审计不能再按配置下标
 * 盲点「下一步」，而是读浮层进度条上的真实步骤号，把中间的步骤记为「空态跳过」。
 * 落空原因分三级：missing="broken" 才算未命中；missing="text" 是设计性居中；
 * skipped 是数据空态下的正常跳过。--empty 会把所有接口回成空壳，
 * 用来验收「空态实例上不出现对着空气的说明」。
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
const EMPTY = argv.includes('--empty')
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
  ['/stats/channel-health', {
    channels: [{
      channel_id: 1, name: '科技频道', is_active: true, health_status: 'healthy',
      today_pending: 0, range_total: 12,
      daily_trend: [{ date: '2026-10-20', count: 3 }],
    }],
    summary: { healthy: 1, warning: 0, critical: 0, total: 1 },
  }],
]
await page.route('**/admin/api/v1/**', (route) => {
  const url = route.request().url()
  // --empty：模拟新装/刚清库的实例，所有接口都回空壳（T02656 验收口径）
  const hit = EMPTY ? null : FIXTURES.find(([p]) => url.includes(p))
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

  const skipped = (index) => ({
    index,
    stepTitle: steps[index].t,
    selectors: steps[index].s || [],
    skipWhenEmpty: steps[index].skipWhenEmpty || null,
    renderedTitle: null,
    hit: null,
    missing: null,
    skipped: 'empty',
  })

  // 按「浮层真实显示的步骤号」推进：中间的步骤号缺口就是被 skipWhenEmpty 跳过的
  let recorded = 0
  for (let guard = 0; guard < steps.length + 2 && recorded < steps.length; guard += 1) {
    if (!(await bubble.isVisible().catch(() => false))) break
    const info = await page.evaluate(() => {
      const hit = document.querySelector('.mb-guide-highlight')
      const b = document.querySelector('.mb-guide-bubble')
      const progress = b?.querySelector('.mb-guide-progress')?.textContent || ''
      return {
        stepNo: Number(progress.match(/第\s*(\d+)\s*\//)?.[1]) || 0,
        missing: b?.dataset?.guideMissing ?? null,
        missingTarget: b?.dataset?.guideTarget ?? null,
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
    const shown = info.stepNo > 0 ? Math.min(info.stepNo - 1, steps.length - 1) : recorded
    for (let i = recorded; i < shown; i += 1) entry.steps.push(skipped(i))
    entry.steps.push({
      index: shown,
      stepTitle: steps[shown].t,
      renderedTitle: info.title,
      selectors: steps[shown].s || [],
      hit: info.hit,
      missing: info.missing,
      missingTarget: info.missingTarget,
    })
    if (info.title !== steps[shown].t) {
      entry.titleDrift = `${entry.titleDrift || ''} [步${shown}] 配置「${steps[shown].t}」≠ 渲染「${info.title}」`
    }
    recorded = shown + 1
    if (shown === steps.length - 1) break
    await bubble.getByRole('button', { name: /^(下一步|完成)$/ }).click()
    // 让浮层重渲染（或跳到最后一步时关闭）；关闭时下一轮 isVisible 为 false
    await page.waitForTimeout(120)
  }
  // 浮层提前关闭/最后一步被跳过：剩下的步骤同样是空态跳过
  for (let i = recorded; i < steps.length; i += 1) entry.steps.push(skipped(i))
  report.push(entry)
}
await browser.close()

const flat = report.flatMap((r) =>
  (r.steps || []).map((s) => ({ route: r.route, ...s })),
)
// T02656：三种落空分开统计——只有 broken 是缺陷；text 是设计；skipped 是空态正常跳过
const missing = flat.filter((s) => s.missing === 'broken')
const textOnly = flat.filter((s) => s.missing === 'text')
const skippedSteps = flat.filter((s) => s.skipped)
const drifted = report.filter((r) => r.titleDrift)
const summary = {
  generatedAt: new Date().toISOString(),
  empty: EMPTY,
  routes: report.length,
  steps: flat.length,
  missingSteps: missing.length,
  textOnlySteps: textOnly.length,
  skippedSteps: skippedSteps.length,
  titleDrift: drifted.map((r) => ({ route: r.route, drift: r.titleDrift })),
  hits: flat.map((s) => ({
    route: s.route,
    step: s.stepTitle,
    selector: s.selectors[0],
    hit: s.skipped
      ? `（空态跳过：${s.skipWhenEmpty}）`
      : s.hit
        ? `${s.hit.tag}[aria-label=${s.hit.ariaLabel || '-'}][data-guide=${s.hit.dataGuide || '-'}] "${s.hit.text}"`
        : s.missing === 'text'
          ? '（设计性居中：无目标元素）'
          : '（未命中）',
  })),
}
fs.writeFileSync(path.resolve(import.meta.dirname, OUT), JSON.stringify({ summary, report }, null, 2))
console.log(
  `[guide-audit] 路由 ${summary.routes} · 步骤 ${summary.steps} · 未命中 ${summary.missingSteps}` +
    ` · 设计性居中 ${summary.textOnlySteps} · 空态跳过 ${summary.skippedSteps}` +
    ` · 标题漂移 ${summary.titleDrift.length}${EMPTY ? ' · 空态模式' : ''}`,
)
for (const h of summary.hits) console.log(`  ${h.route} · ${h.step} → ${h.selector} ⇒ ${h.hit}`)
for (const m of missing) console.log(`  ✗ 未命中：${m.route} · ${m.stepTitle} · 选择器 ${m.selectors.join(' , ')}`)
console.log(`报告已写入 ${OUT}`)
