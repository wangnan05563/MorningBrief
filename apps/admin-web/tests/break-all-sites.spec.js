import { test, expect } from '@playwright/test'
import { setLoginState, useMobileViewport } from './helpers/mock'

/**
 * T03714：其余 break-all 站点逐处复核后的行为守卫。
 *
 * T03702 量出 `word-break: break-all` 的真实代价：中英混排里英文词会被从行尾中间硬拆。
 * 本文件按「这一处承载的是什么内容」分两类守：
 * - 人读文本（停服审计原因 / 清理结果 / 任务错误 / 移动端字段值）：必须 `hardSplits == []`，
 *   且无空格长串仍要断开（lines > 1）——两条缺一，说明要么 break-all 回来了，要么换行失效。
 * - 机器原文（引用素材 URL）：长 URL 本来就该在内部断开，只守「必断开 + 不溢出」，
 *   「不许硬拆英文词」这条对它不成立（一个几百字符的 path 段不可能整词换行）。
 *
 * 量测形状沿用 audit-trail.spec.js 的 measureWhy：逐字符取 rect，top 变化即一次换行；
 * 断点两侧都是裸字母数字、且前一字符不是 - _ . / : 的，记作「从词中间硬拆」。
 *
 * 另外每处都先断言 computed style：T03714 实测发现 CleanupResult / TaskProgress 是
 * 脚本里用 h() 渲染的组件，子元素拿不到本文件的 scoped 属性，写成普通嵌套选择器时
 * `overflow-wrap` 一直是死规则（computed 仍是 normal，199 字符长串撑破结果块 1519px）。
 * 只量布局不量声明的话，这类死规则会因为「CJK 本来就能断」而假绿。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

const MIXED =
  '本次清理涉及 episodeCatalogSnapshot 缓存，bucket=news-prod 的 snapshot-20261030 归档后需要人工 confirm 再回滚，恢复前请勿重复触发同一目标'
const LONG_ASCII = `sha256_${'ab'.repeat(96)}`
const LONG_URL =
  'https://example.com/素材快照/episodeCatalogSnapshot-归档确认后回滚/old_playlogs-backup-part07.tar.gz'

function measureText(el) {
  const node = [...el.childNodes].find((n) => n.nodeType === 3 && n.data.trim())
  if (!node) return { chars: 0, lines: 0, hardSplits: [], selfOverflow: 0 }
  const text = node.data
  const range = document.createRange()
  const starts = []
  let curTop = null
  for (let i = 0; i < text.length; i += 1) {
    range.setStart(node, i)
    range.setEnd(node, i + 1)
    const r = range.getBoundingClientRect()
    if (r.width === 0 && r.height === 0) continue
    const top = Math.round(r.top)
    if (curTop === null || top !== curTop) {
      starts.push(i)
      curTop = top
    }
  }
  const hard = starts.slice(1).filter(
    (idx) => /[A-Za-z0-9]/.test(text[idx - 1]) && /[A-Za-z0-9]/.test(text[idx]) && !/[-_./:]/.test(text[idx - 1]),
  )
  return {
    chars: text.length,
    lines: starts.length,
    hardSplits: hard.map((idx) => `${text.slice(Math.max(0, idx - 12), idx)}|${text.slice(idx, idx + 12)}`),
    selfOverflow: el.scrollWidth - el.clientWidth,
  }
}

// 声明必须先真的落到该元素上：scoped 失配、被覆盖回 normal、或者 break-all 回来，都在这里红
const expectDeclared = async (locator, label) => {
  const cs = await locator.evaluate((el) => {
    const s = getComputedStyle(el)
    return { overflowWrap: s.overflowWrap, wordBreak: s.wordBreak }
  })
  expect(cs.overflowWrap, `${label} 的 overflow-wrap 没落到元素上（被 scoped 掉了或又被覆盖）`).toBe('anywhere')
  expect(cs.wordBreak, `${label} 仍是 word-break: break-all`).not.toBe('break-all')
}

const noHardSplit = (m, label) => {
  expect(m.lines, `${label} 应换行（否则量的是单行，断言空跑）：${JSON.stringify(m)}`).toBeGreaterThan(1)
  expect(m.hardSplits, `${label} 被从词中间硬拆（word-break: break-all 回来了）：${m.hardSplits.join(' / ')}`).toEqual([])
  expect(m.selfOverflow, `${label} 被裁切`).toBeLessThanOrEqual(0)
}

const mustWrap = (m, label) => {
  expect(m.lines, `${label} 未断开成多行（overflow-wrap 没生效）：${JSON.stringify(m)}`).toBeGreaterThan(1)
}

test.describe('T03714 · 断行声明逐处复核', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  })

  test('停服审计原因：不硬拆英文词，长串仍断开', async ({ page }) => {
    await page.route(`${API}/m/maintenance-status`, (route) =>
      route.fulfill({ json: ok({ enabled: true, reason: '演示停服', by: 'admin', at: '2026-10-30T10:00:00' }) }))
    await page.route(`${API}/m/emergency/audit*`, (route) =>
      route.fulfill({ json: ok({ items: [
        { action: 'emergency_stop', operator: 'admin', at: '2026-10-30T10:00:00', reason: MIXED },
      ] }) }))

    await page.goto('/maintenance')
    const reason = page.locator('.m-alert__audit-reason')
    await expect(reason).toContainText('confirm')
    await expectDeclared(reason, '停服审计原因')

    // 宽屏下这段文字正好一行放得下（1600px 实测 1282px，1280px 仍放得下），要换行才能量断点
    for (const width of [1024, 960, 900]) {
      await page.setViewportSize({ width, height: 900 })
      noHardSplit(await reason.evaluate(measureText), `@${width}px 停服审计原因`)
    }
  })

  test('清理结果：人读一句话不硬拆英文词，无空格长串仍断开', async ({ page }) => {
    await page.route(`${API}/maintenance/cache`, (route) =>
      route.fulfill({ json: ok({ cleaned: [MIXED, LONG_ASCII], errors: [] }) }))

    await page.goto('/maintenance')
    await page.getByRole('button', { name: /预览清理/ }).first().click()
    const items = page.locator('.cleanup-result .result-item')
    await expect(items).toHaveCount(2)
    await expectDeclared(items.nth(1), '清理结果长串')

    for (const width of [1600, 1200, 1024]) {
      await page.setViewportSize({ width, height: 900 })
      noHardSplit(await items.nth(0).evaluate(measureText), `@${width}px 清理结果混排行`)
      const ascii = await items.nth(1).evaluate(measureText)
      expect(ascii.lines, `@${width}px 长串未断开：${JSON.stringify(ascii)}`).toBeGreaterThan(1)
      expect(ascii.hardSplits.length, '@' + width + 'px 长串必须有内部断点，否则守卫空跑').toBeGreaterThan(0)
      expect(ascii.selfOverflow, `@${width}px 长串撑破结果块`).toBeLessThanOrEqual(0)
    }
  })

  test('后台任务错误摘要：不硬拆英文词，长串仍断开', async ({ page }) => {
    await page.route(`${API}/maintenance/cache`, (route) =>
      route.fulfill({ json: ok({ task_id: 'task-1', state: 'running' }) }))
    await page.route(`${API}/maintenance/tasks/task-1`, (route) =>
      route.fulfill({ json: ok({ task_id: 'task-1', state: 'failed', error: MIXED }) }))

    await page.goto('/maintenance')
    // 关掉预览开关 → 走「立即执行清理」，才会有后台任务与任务错误摘要
    await page.locator('.cleanup-card').first().locator('.el-switch').click()
    await page.getByRole('button', { name: /立即执行清理/ }).first().click()
    await page.getByPlaceholder('例如：频道下线，素材不再使用').fill('演示原因')
    await page.getByRole('button', { name: '确认执行' }).click()

    const err = page.locator('.task-progress .result-error')
    await expect(err).toBeVisible({ timeout: 15000 })
    await expect(err).toContainText('confirm')
    await expectDeclared(err, '后台任务错误摘要')

    for (const width of [1600, 1200, 1024]) {
      await page.setViewportSize({ width, height: 900 })
      noHardSplit(await err.evaluate(measureText), `@${width}px 任务错误摘要`)
    }
  })

  test('引用素材链接：长 URL 必断开且不溢出', async ({ page }) => {
    await page.route(`${API}/reviews/1`, (route) =>
      route.fulfill({ json: ok({ id: 1, episode_date: '2026-10-30', workflow_id: 'wf-demo', status: 'pending', script: { full_text: '<p>演示</p>', referenced_materials: [LONG_URL], segments: [] } }) }))

    await page.goto('/review/1')
    const link = page.locator('.material-list li a').first()
    await expect(link).toBeVisible()
    await expectDeclared(link, '引用素材链接')

    // 1600px 下这条 URL 放得进一行（实测 723px > 623px），窄一些才有断点可量。
    // 链接是 inline 元素：scrollWidth 恒为 0，溢出要看它有没有越过 li 的右边界。
    for (const width of [1200, 1024, 900]) {
      await page.setViewportSize({ width, height: 900 })
      mustWrap(await link.evaluate(measureText), `@${width}px 引用素材链接`)
      const escape = await link.evaluate((el) => {
        const li = el.closest('li')
        return +(el.getBoundingClientRect().right - li.getBoundingClientRect().right).toFixed(1)
      })
      expect(escape, `@${width}px 引用素材链接越过列表项右边界`).toBeLessThanOrEqual(0.5)
    }
  })

  test('移动端字段值与素材标签：不硬拆 / 必断开', async ({ page }) => {
    await useMobileViewport(page)
    await page.route(`${API}/reviews?*`, (route) =>
      route.fulfill({ json: ok({ list: [{
        id: 1, title: '演示稿件', channel_name: MIXED, channel_type: 'news',
        workflow_id: 'wf-demo', workflow_name: '演示工作流',
      }], total: 1 }) }))
    await page.route(`${API}/reviews/1`, (route) =>
      route.fulfill({ json: ok({ id: 1, status: 'pending', script: { full_text: '<p>演示</p>', categories: [MIXED], referenced_materials: [LONG_URL], segments: [] } }) }))

    await page.goto('/m/review')
    await page.locator('.m-review__title-row').first().click()

    const dd = page.locator('.m-detail__field dd').nth(0)
    await expect(dd).toContainText('confirm')
    await expectDeclared(dd, '移动端字段值')
    noHardSplit(await dd.evaluate(measureText), '移动端字段值')

    // 素材链接 chip 的文本是「素材 N」，长的是 href；会变长的是分类名 chip
    const chip = page.locator('.m-chip2').first()
    await expect(chip).toContainText('confirm')
    await expectDeclared(chip, '移动端分类标签')
    noHardSplit(await chip.evaluate(measureText), '移动端分类标签')
  })
})
