/**
 * T02028 管理端 UI 实测：审核列表「时长」列与「凑时 Ns」标记。
 *
 * 通道按本环境实测可用方案：Playwright 驱动系统 Chrome（内置 Browser 无视口，无法点击/截图）。
 * 后端指向 news.db 副本（生产库历史行按设计全为 NULL，验不出标记）。
 */
import { chromium } from 'file:///D:/code/otherProjects/20_News/apps/admin-web/node_modules/playwright/index.mjs'

const BASE = 'http://127.0.0.1:8000'
const OUT = 'D:/code/otherProjects/20_News/_validate/t02028_ui'

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

await page.goto(`${BASE}/news/review`, { waitUntil: 'networkidle' })
await page.waitForSelector('.el-table__row', { timeout: 20000 })

const header = (await page.locator('.el-table__header th').allInnerTexts())
  .map((h) => h.trim())
console.log('表头:', JSON.stringify(header))
const durIdx = header.findIndex((h) => h.includes('时长'))
console.log('时长列位置(含勾选列):', durIdx)

// 逐行取单元格，按列位置定位「时长」
const rows = await page.locator('.el-table__body tr.el-table__row').all()
const parsed = []
for (const r of rows) {
  const cells = (await r.locator('td').allInnerTexts()).map((c) => c.trim())
  parsed.push(cells)
}
const withDur = parsed.filter((c) => c[durIdx] && c[durIdx] !== '—')
console.log('有时长值的行数:', withDur.length)
console.log('样例:', JSON.stringify(withDur[0]))
const dashes = parsed.filter((c) => c[durIdx] === '—').length
console.log('历史行显示为 — 的数量:', dashes, '/', parsed.length)

const target = withDur[0]
console.log('时长单元格文本:', JSON.stringify(target[durIdx]))

// tooltip 内容
const rowLoc = page.locator('.el-table__body tr.el-table__row')
  .filter({ hasText: '凑时' }).first()
const tipTrigger = rowLoc.locator(`td:nth-child(${durIdx + 1}) .el-tag`)
console.log('凑时标记 tag class:', await tipTrigger.getAttribute('class'))
await tipTrigger.hover()
await page.waitForTimeout(800)
const tips = (await page.locator('.el-popper:visible').allInnerTexts())
  .map((t) => t.trim()).filter(Boolean)
console.log('tooltip:', JSON.stringify(tips))

await page.screenshot({ path: `${OUT}_list.png` })

const bodyText = await page.locator('.el-table').innerText()
console.log('异常占位:', JSON.stringify(['undefined', 'NaN', 'null'].filter((s) => bodyText.includes(s))))

for (const tab of ['已通过', '已打回']) {
  await page.locator('.el-tabs__item', { hasText: tab }).first().click()
  await page.waitForTimeout(1500)
  const h = (await page.locator('.el-table__header th').allInnerTexts()).map((x) => x.trim())
  const idx = h.findIndex((x) => x.includes('时长'))
  const cells = await page.locator('.el-table__body tr.el-table__row td:nth-child(' + (idx + 1) + ')').allInnerTexts()
  console.log(`${tab}: 时长列存在=${idx >= 0} 行数=${cells.length} 全为—=${cells.every((c) => c.trim() === '—')}`)
}
await page.screenshot({ path: `${OUT}_tabs.png` })

await browser.close()
console.log('[ok] UI 实测完成')
