import { test, expect } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { setLoginState, useMobileViewport } from './helpers/mock'

/**
 * T02909：模块页旁边的「最近操作审计」必须真读得到、读不到要说清楚。
 *
 * 缺陷形状是「写了一直有，读没有」：30+ 处审计写入覆盖 15 类操作，统一读口原先只放行
 * db_admin 与移动端停服两类，出事以后「刚才那次是谁做的」得手工捞表。本单把只读接口
 * 开给全量管理员（工单裁决），并在动作发生的页面旁挂出最近几条。
 *
 * 这里守四件在 mock 里可判定的事：
 * 1. 请求带本模块 category，不会串到别的桶（接错对象最常见的形态）；
 * 2. 渲染出「谁 / 做了什么 / 为什么」，长尾明细截断而不是丢掉整行；
 * 3. 读取失败走 ListLoadError（含重试），绝不说成「该模块暂无审计记录」（T02496 口径），
 *    且因为是 silent 请求，不额外抢一条全局 toast；
 * 4. 后端脱敏后的 `***` 原样呈现，前端不再自行猜测哪些算敏感。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

const auditRow = (overrides = {}) => ({
  id: 1,
  category: 'maintenance',
  action: 'cleanup',
  target: 'old_playlogs',
  operator: 'admin',
  detail: { days: 7, count: 3 },
  created_at: '2026-10-26T16:00:00',
  ...overrides,
})

const auditList = (rows) => ok({ items: rows, total: rows.length, page: 1, page_size: 5 })

function auditRoute(page, handler) {
  return page.route(`${API}/audit-logs*`, (route) => handler(route))
}

test.describe('系统清理 · 最近操作审计（T02909）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('审计块按本模块 category 取数并呈现谁/做了什么/为什么', async ({ page }) => {
    const asked = []
    await auditRoute(page, (route) => {
      asked.push(new URL(route.request().url()).searchParams.toString())
      return route.fulfill({ json: auditList([
        auditRow(),
        auditRow({ id: 2, action: 'restore', target: 'snapshot-01', operator: 'ops01',
          detail: { reason: '误删书单后回滚' } }),
      ]) })
    })

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block).toContainText('admin')
    await expect(block).toContainText('cleanup · old_playlogs')
    await expect(block).toContainText('days=7 · count=3')
    await expect(block).toContainText('ops01')
    await expect(block.getByText('reason=误删书单后回滚')).toBeVisible()
    await expect(block).toContainText('2026-10-26 16:00:00')

    expect(asked.length).toBeGreaterThanOrEqual(1)
    for (const qs of asked) {
      expect(qs).toContain('category=maintenance')
      expect(qs).toContain('page_size=5')
    }
    await expect(block.getByText('该模块暂无审计记录')).toHaveCount(0)
  })

  test('读取失败：说「加载失败」并给重试，不说成暂无记录，也不抢全局 toast', async ({ page }) => {
    let fail = true
    await auditRoute(page, (route) =>
      route.fulfill({ json: fail ? { code: 50000, message: '审计日志读取失败', data: null } : auditList([auditRow()]) }))

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText('加载失败：审计日志读取失败')).toBeVisible()
    await expect(block.getByText('请求未成功，数据并未加载')).toBeVisible()
    await expect(block.getByText('该模块暂无审计记录')).toHaveCount(0)
    // silent 请求：失败只体现在组件自己的失败态里
    await expect(page.locator('.el-message')).toHaveCount(0)

    fail = false
    await block.getByRole('button', { name: '重试' }).click()
    await expect(block.getByText('cleanup · old_playlogs')).toBeVisible()
    await expect(block.getByText('加载失败：审计日志读取失败')).toHaveCount(0)
  })

  test('刷新按钮重新取数（不靠整页刷新）', async ({ page }) => {
    let calls = 0
    await auditRoute(page, (route) => {
      calls += 1
      return route.fulfill({
        json: auditList([auditRow({ id: calls, action: calls === 1 ? 'cleanup' : 'restore' })]),
      })
    })

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText('cleanup · old_playlogs')).toBeVisible()
    expect(calls).toBe(1)

    await block.getByRole('button', { name: '刷新' }).click()
    await expect(block.getByText('restore · old_playlogs')).toBeVisible()
    expect(calls).toBe(2)
  })

  test('后端脱敏值原样呈现，前端不再自行判断敏感字段', async ({ page }) => {
    await auditRoute(page, (route) =>
      route.fulfill({ json: auditList([auditRow({
        action: 'update_config',
        target: 'cos_config',
        detail: { secret_id: '***', secret_key: '***', bucket: 'news-prod' },
      })]) }))

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText(/\*\*\*/)).toBeVisible()
    await expect(block).not.toContainText('AKIA')
  })

  test('真·无记录才说暂无（与失败态是两件事）', async ({ page }) => {
    await auditRoute(page, (route) => route.fulfill({ json: auditList([]) }))

    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.getByText('该模块暂无审计记录')).toBeVisible()
    await expect(block.getByText('加载失败')).toHaveCount(0)
  })
})

test.describe('审核页审计块只读自己的 category（T02909）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('审核页请求 category=review，不串到 maintenance', async ({ page }) => {
    const asked = []
    await auditRoute(page, (route) => {
      asked.push(new URL(route.request().url()).searchParams.get('category'))
      return route.fulfill({ json: auditList([auditRow({ category: 'review', action: 'approve', target: 'wf-001' })]) })
    })

    await page.goto('/review')
    const block = page.locator('[data-guide="review-audit"]')
    await expect(block.getByText('approve · wf-001')).toBeVisible()
    expect(asked.every((c) => c === 'review')).toBe(true)
    expect(asked).not.toContain('maintenance')
  })
})

/**
 * T03670：嵌套审计详情不得渲染成 [object Object]。
 *
 * 现场形态（生产库快照的真实一行，非造数）：
 *   2026-08-20 21:54:34 batch_approve · review_id=wf-20260820-0008 result=[object Object]…
 * summarize() 用模板串取 `${detail[k]}`，k 命中 result/before/after 这类结构化值时
 * JS 默认转成 [object Object]，值班唯一速读入口整行失效，且串起来能撑宽布局。
 */
const NESTED_ROWS = [
  auditRow({
    id: 11,
    category: 'review',
    action: 'batch_approve',
    target: 'review_id=wf-20260820-0008',
    operator: 'admin',
    detail: { review_id: 'wf-20260820-0008', result: [{ ok: true, episode: 12 }, { ok: true, episode: 13 }] },
  }),
  auditRow({
    id: 12,
    action: 'update',
    target: 'admin_user',
    detail: { before: { nickname: 'old', role: 'admin' }, after: { nickname: 'new', role: 'admin' } },
  }),
]

// 现场另一形态：reason 是一段人写的长说明，拍平后仍应受行宽约束
const LONG_ROW = auditRow({
  id: 13,
  action: 'cleanup',
  target: 'old_playlogs',
  detail: { reason: '清理旧播放记录并同步书单缓存，涉及 12 个频道，快照已归档至 COS 并生成校验和。'.repeat(6) },
})

/**
 * 中文长句靠 CJK 天然可断行，带连字符的 URL 也有断行机会，overflow-wrap 有没有都
 * 测不出来（实测两条腿都绿）；真正撑破容器的是「无断行机会的长 ASCII 串」——
 * 校验和 / base64 这类值拍平后正是这种。这一行是给布局量测用的：
 * 没有 overflow-wrap: anywhere 时它必须溢出。
 */
const ASCII_ROW = auditRow({
  id: 14,
  action: 'cleanup',
  target: 'snapshot',
  detail: { checksum: `sha256_${'ab'.repeat(96)}` },
})

test.describe('审计摘要的嵌套值与行宽（T03670）', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('数组/对象值拍平成紧凑形态，整块不再出现 [object Object]', async ({ page }) => {
    await auditRoute(page, (route) => route.fulfill({ json: auditList(NESTED_ROWS) }))

    await page.goto('/review')
    const block = page.locator('[data-guide="review-audit"]')
    await expect(block.getByText('batch_approve · review_id=wf-20260820-0008')).toBeVisible()
    await expect(block).not.toContainText('[object Object]')
    // 结构化值要"可读"而不是"被抹掉"：能看到 result 里到底有什么
    await expect(block.getByText(/result=\[/)).toBeVisible()
    await expect(block.getByText(/before=\{nickname:old/)).toBeVisible()
  })

  test('超长摘要被截断且行不溢出容器', async ({ page }) => {
    await auditRoute(page, (route) => route.fulfill({ json: auditList([LONG_ROW]) }))

    await page.goto('/maintenance')
    const why = page.locator('[data-guide="maintenance-audit"] .audit-trail__why').first()
    const text = (await why.textContent()) || ''
    expect(text.length).toBeLessThanOrEqual(200)
    expect(text).toContain('…')

    const overflow = await why.evaluate((el) => {
      const item = el.closest('.audit-trail__item')
      return {
        selfOverflow: el.scrollWidth - el.clientWidth,
        escapesItem: el.getBoundingClientRect().right > item.getBoundingClientRect().right + 0.5,
      }
    })
    expect(overflow.selfOverflow).toBeLessThanOrEqual(0)
    expect(overflow.escapesItem).toBe(false)
  })

  test('移动端复用同一组件：启停审计同样不出现 [object Object]', async ({ page }) => {
    await useMobileViewport(page)
    await auditRoute(page, (route) => route.fulfill({ json: auditList([
      auditRow({ id: 21, category: 'user', action: 'toggle_status', detail: { result: { disabled: true, sessions: [1, 2, 3] } },
      }),
    ]) }))

    await page.goto('/m/manage/users')
    const block = page.locator('[data-guide="user-audit"]')
    await expect(block.getByText('toggle_status')).toBeVisible()
    await expect(block).not.toContainText('[object Object]')
    await expect(block.getByText(/result=\{disabled:true,sessions:\[1,2,3\]\}/)).toBeVisible()
  })

  /**
   * 验收 3：6 套主题下这行都不溢出容器，且摘要字色在实底上达标。
   *
   * 复用既有主题门禁的做法（tests/tag-contrast.spec.js 同款）：在真浏览器里切
   * data-theme 量 computed style，而不是只在源码层算 token——拍平后这一行变成了
   * `result=[{ok:true,…}]` 这种「长而无空格」的串，只有 overflow-wrap 真的生效
   * 才不会撑破容器，这事源码层看不出来。
   */
  const THEMES = ['macaron', 'enterprise', 'creative', 'showcase', 'commerce', 'portfolio']

  test('6 套主题：长摘要不溢出容器，且对比度 ≥ 4.5:1', async ({ page }) => {
    await auditRoute(page, (route) => route.fulfill({ json: auditList([...NESTED_ROWS, LONG_ROW, ASCII_ROW]) }))
    await page.goto('/maintenance')
    const block = page.locator('[data-guide="maintenance-audit"]')
    await expect(block.locator('.audit-trail__item')).toHaveCount(4)

    const rows = []
    for (const theme of THEMES) {
      await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
      const measured = await block.evaluate((el, name) => {
        const lum = ([r, g, b]) => {
          const [rs, gs, bs] = [r, g, b].map((v) => {
            const s = v / 255
            return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
          })
          return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs
        }
        const rgbOf = (text) => {
          const m = /rgba?\(([^)]+)\)/.exec(text)
          if (!m) return null
          return m[1].split(',').slice(0, 3).map((v) => Number(v.trim()))
        }
        // 背景逐层上溯到第一个不透明的祖先，拿「实际落底」而不是声明值
        const bottomOf = (node) => {
          for (let cur = node; cur; cur = cur.parentElement) {
            const c = rgbOf(getComputedStyle(cur).backgroundColor)
            if (c && getComputedStyle(cur).backgroundColor !== 'rgba(0, 0, 0, 0)') return c
          }
          return [255, 255, 255]
        }
        const wrap = el.getBoundingClientRect()
        const out = { theme: name, pageScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth, items: [] }
        for (const why of el.querySelectorAll('.audit-trail__item')) {
          const cell = why.querySelector('.audit-trail__why')
          const box = cell.getBoundingClientRect()
          const fg = rgbOf(getComputedStyle(cell).color)
          const bg = bottomOf(el)
          const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a)
          out.items.push({
            chars: (cell.textContent || '').length,
            selfOverflow: cell.scrollWidth - cell.clientWidth,
            escapesBlock: box.right > wrap.right + 0.5,
            ratio: +((hi + 0.05) / (lo + 0.05)).toFixed(2),
          })
        }
        return out
      }, theme)
      rows.push(measured)
      await expect(block).not.toContainText('[object Object]')
    }

    const table = rows.map((r) => `${r.theme}: page溢出=${r.pageScroll} · ${r.items.map((i) => `${i.chars}字 自身溢出=${i.selfOverflow} 越界=${i.escapesBlock} 对比度=${i.ratio}:1`).join(' / ')}`)
    if (process.env.T03670_EVIDENCE) {
      const dir = fileURLToPath(new URL('../../../_validate/news2/t03670/', import.meta.url))
      mkdirSync(dir, { recursive: true })
      writeFileSync(`${dir}/theme_layout.json`, JSON.stringify({ label: process.env.T03670_EVIDENCE, measured_at: new Date().toISOString(), table, rows }, null, 2))
    }
    for (const r of rows) {
      expect(r.pageScroll, `切到 ${r.theme} 后页面出现横向滚动：\n${table.join('\n')}`).toBeLessThanOrEqual(0)
      for (const item of r.items) {
        expect(item.selfOverflow, `切到 ${r.theme} 后摘要自身被裁切：\n${table.join('\n')}`).toBeLessThanOrEqual(0)
        expect(item.escapesBlock, `切到 ${r.theme} 后摘要撑出审计块：\n${table.join('\n')}`).toBe(false)
        expect(item.ratio, `切到 ${r.theme} 后摘要字色不达 AA：\n${table.join('\n')}`).toBeGreaterThanOrEqual(4.5)
      }
    }
  })
})


