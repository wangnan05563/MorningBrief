import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'
import { statsMetricMeta } from './helpers/statsMeta'

/**
 * T02539 / ACC-UX-501 #1：抽查 3 天数据，平均收听显示值必须等于
 * play_log.duration 的秒值 × meta.factor（1/60），并按 meta.precision 保留 1 位。
 *
 * 三天用三份不同的后端原始值分别跑：整分钟（360 秒）、带小数（512 秒）、
 * 跨小时（750 秒）。断言成对——换好的分钟数在卡片上，原始秒值不在。
 * 若有人把后端预换算成分钟（或前端把秒直接贴上「分钟」），这三条会按天分别红。
 */

const API = '**/admin/api/v1'
const ok = (data) => ({ code: 0, message: 'success', data })

const THREE_DAYS = [
  { date: '2026-07-01', durations: [300, 420], completed: [1, 0], minutes: '6.0', rate: '50.0' },
  { date: '2026-07-02', durations: [512, 512], completed: [0, 0], minutes: '8.5', rate: '0.0' },
  { date: '2026-07-03', durations: [600, 900], completed: [1, 1], minutes: '12.5', rate: '100.0' },
]

const avg = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length

test.describe('ACC-UX-501 指标单位与刻度一致', () => {

  for (const day of THREE_DAYS) {
    const seconds = avg(day.durations)
    test(`${day.date}：平均收听 ${seconds} 秒显示为 ${day.minutes} 分钟`, async ({ page }) => {
      await setLoginState(page, 'admin')
      await page.route(`${API}/stats/overview*`, (route) =>
        route.fulfill({
          json: ok({
            dau: day.durations.length,
            play_count: day.durations.length,
            completion_rate: avg(day.completed),
            avg_listen_duration: seconds,
            ad_impression: day.durations.length * 3,
            meta: statsMetricMeta,
          }),
        })
      )
      await page.route(`${API}/stats/trend*`, (route) =>
        route.fulfill({
          json: ok({
            dates: [day.date],
            values: [seconds],
            metric: 'dau',
            meta: { dau: statsMetricMeta.dau },
          }),
        })
      )
      await page.goto('/stats')

      const cards = page.locator('[data-guide="stats-metric-card"]')
      const listen = cards.filter({ hasText: '平均收听' })
      // 全量并发跑时 /stats 首屏可能晚于默认 5s（vite 冷编译 + 双 worker）；这只放开首屏那一条
      await expect(listen).toHaveCount(1, { timeout: 30_000 })
      await expect(listen.locator('.metric-label')).toHaveText('平均收听(分钟)')
      await expect(listen.locator('.metric-value')).toHaveText(day.minutes)
      // 原始秒值不得以「分钟」的身份出现
      await expect(listen).not.toContainText(String(seconds))

      const rate = cards.filter({ hasText: '完播率(%)' })
      await expect(rate.locator('.metric-label')).toHaveText('完播率(%)')
      await expect(rate.locator('.metric-value')).toHaveText(day.rate)
    })
  }
})
