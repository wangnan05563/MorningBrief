/**
 * T02138 管理端 UI 实测：发送日志页「逐渠道明细」展开行 + failed_capped 状态标签。
 *
 * 通道按本环境实测可用方案：Playwright 驱动系统 Chrome（内置 Browser 无视口，无法点击/截图）。
 * 后端 = 隔离实例 :8010（APP_ROLE=api，不起调度器），库 = news.db 副本（t02138_uisetup.py 注入 4 行）。
 * 只读验证渲染，不发真实通知、不写生产库。
 */
import { chromium } from 'file:///D:/code/otherProjects/20_News/apps/admin-web/node_modules/playwright/index.mjs'

const BASE = 'http://127.0.0.1:8010'
const OUT = 'D:/code/otherProjects/20_News/_validate/t02138_ui'
const log = (...a) => console.log(...a)

const login = await (await fetch(`${BASE}/admin/api/v1/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin123' }),
})).json()
const token = login.data.token

const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
})
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } })
await ctx.addCookies([{ name: 'admin_token', value: token, url: BASE }])
await ctx.addInitScript(() => { localStorage.setItem('admin_role', 'admin') })
const page = await ctx.newPage()
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })

const items = () => page.locator('.el-select-dropdown:visible .el-select-dropdown__item')

async function openLogsTab() {
  await page.goto(`${BASE}/news/notification`, { waitUntil: 'domcontentloaded' })
  await page.locator('.el-tabs__item', { hasText: '发送日志' }).first().click()
  await page.waitForSelector('.filter-bar .el-select', { timeout: 20000 })
  await page.waitForTimeout(1000)
}

const eventSel = () => page.locator('.filter-bar .el-select').nth(0)
const statusSel = () => page.locator('.filter-bar .el-select').nth(1)

await openLogsTab()

// 1. 两个下拉的选项集合（打开→读→选定，避免误点到另一个已关闭的下拉）
await eventSel().click()
await page.waitForTimeout(500)
const eventOpts = (await items().allInnerTexts()).map((s) => s.trim())
await page.screenshot({ path: `${OUT}_1_event_options.png` })
log('事件下拉:', JSON.stringify(eventOpts))

await items().filter({ hasText: '停摆告警' }).first().click()
await page.waitForTimeout(1600)
let rows = await page.locator('.el-table__body tr.el-table__row').allInnerTexts()
log('\n=== 筛「事件=停摆告警」行数:', rows.length, ' 首行:',
  JSON.stringify((rows[0] || '').replace(/\s+/g, ' ').slice(0, 140)))

await statusSel().click()
await page.waitForTimeout(500)
const statusOpts = (await items().allInnerTexts()).map((s) => s.trim())
await page.screenshot({ path: `${OUT}_2_status_options.png` })
log('状态下拉:', JSON.stringify(statusOpts))
log('判定 → 含「失败达上限」:', statusOpts.includes('失败达上限'), '| 含「停摆告警」:', eventOpts.includes('停摆告警'))

// 2. 叠加状态=失败达上限
await items().filter({ hasText: '失败达上限' }).first().click()
await page.waitForTimeout(1600)
rows = await page.locator('.el-table__body tr.el-table__row').allInnerTexts()
log('\n=== + 状态=失败达上限：行数', rows.length, '===')
rows.forEach((r, i) => log(` 行${i}:`, JSON.stringify(r.replace(/\s+/g, ' ').slice(0, 140))))
log('判定 → 每行都显示中文标签「失败达上限」:', rows.length > 0 && rows.every((r) => r.includes('失败达上限')))
await page.screenshot({ path: `${OUT}_3_capped.png` })

// 3. 重载清空筛选 → 每页 100 → 展开各行看逐渠道明细
await openLogsTab()
const sizeSel = page.locator('.el-pagination .el-select').first()
if (await sizeSel.count()) {
  await sizeSel.click()
  await page.waitForTimeout(500)
  await items().filter({ hasText: '100' }).first().click()
  await page.waitForTimeout(2000)
}

async function expandRowById(id) {
  // 按「ID 列文本精确等于 id」定位行（hasText 正则会误命中时间等其他列）
  const idx = await page.locator('.el-table__body tr.el-table__row').evaluateAll((trs, want) => {
    return trs.findIndex((tr) => {
      const cells = Array.from(tr.querySelectorAll('td')).map((t) => t.innerText.trim())
      return cells.includes(String(want))
    })
  }, id)
  if (idx < 0) return { found: false }
  const row = page.locator('.el-table__body tr.el-table__row').nth(idx)
  const icon = row.locator('.el-table__expand-icon').first()
  if (!(await icon.count())) return { found: true, rendered: false }
  await icon.click()
  await page.waitForTimeout(1000)
  // 展开内容紧随其后的 tr，避免多次展开后取错明细
  const detail = row.locator('xpath=following-sibling::tr[1]').locator('.log-detail')
  if (!(await detail.count())) return { found: true, rendered: false }
  const text = (await detail.innerText()).replace(/\s+/g, ' ')
  const chanRows = (await detail.locator('.el-table__body tr').allInnerTexts())
    .map((c) => c.replace(/\s+/g, ' ').trim())
  return { found: true, rendered: true, text, chanRows }
}

for (const id of [344, 345, 346, 342]) {
  const r = await expandRowById(id)
  log(`\n=== ID ${id} 展开 ===`)
  if (!r.found) { log('  行未找到（不在当前页）'); continue }
  if (!r.rendered) { log('  明细区未渲染'); continue }
  log('  明细文本:', r.text.slice(0, 260))
  log('  逐渠道子表行数:', r.chanRows.length)
  r.chanRows.forEach((c) => log('   -', c))
  await page.screenshot({ path: `${OUT}_4_detail_${id}.png` })
}

const bodyText = await page.locator('.el-table').first().innerText()
log('\n异常占位 undefined/NaN/[object Object]:',
  JSON.stringify(['undefined', 'NaN', '[object Object]'].filter((s) => bodyText.includes(s))))
log('前端 console error 数:', errors.length, JSON.stringify(errors.slice(0, 5)))

await browser.close()
log('[ok] UI 实测完成')
