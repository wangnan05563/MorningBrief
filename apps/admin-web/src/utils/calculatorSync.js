/**
 * 「参数计算器 → AI 配置」的取值映射（T02534 / M2）。
 *
 * 为什么要单独成一个纯模块：这条链路的缺陷表征是**静默夹取**——计算器页允许时长 60–1800s、
 * 倍率 0.5–2.5x，而 AI 配置页的滑杆只吃 180–1200s 与 -50%~+100%。此前换算后的值原样写进表单、
 * toast 却仍报「已从参数计算器同步：目标时长、语速倍率」，用户以为按自己填的值带过去了。
 * 夹取本身没错（滑杆范围就是后端可存范围的子集，越界值存下去反而不可用），
 * 错的是**不声明**。把区间判定写在这里，测试可以直接断言行为，而不是抓 .vue 里的字符串。
 */

export const DURATION_RANGE = { min: 180, max: 1200 }

// edge_rate 存的是「语速偏移百分比」，与倍率换算：1.0x → 0%、2.0x → +100%、0.5x → -50%
export const RATE_PERCENT_RANGE = { min: -50, max: 100 }

export function formatRatePercent(percent) {
  if (!percent) return ''
  return percent > 0 ? `+${percent}%` : `${percent}%`
}

export function parseDuration(raw) {
  const sec = parseInt(raw, 10)
  if (Number.isNaN(sec)) return null
  const value = Math.max(DURATION_RANGE.min, Math.min(DURATION_RANGE.max, sec))
  return {
    requested: sec,
    value,
    clamped: value !== sec,
    range: DURATION_RANGE,
  }
}

export function parseRate(raw) {
  const rate = parseFloat(raw)
  if (Number.isNaN(rate)) return null
  const percent = Math.round((rate - 1) * 100)
  const value = Math.max(RATE_PERCENT_RANGE.min, Math.min(RATE_PERCENT_RANGE.max, percent))
  return {
    requested: rate,
    percent,
    value,
    clamped: value !== percent,
    range: RATE_PERCENT_RANGE,
    edge_rate: formatRatePercent(value),
  }
}

/**
 * 被夹取时必须说出来。返回的每条文案都带「请求值 → 实际落值 → 为什么」三段，
 * 只说「已同步」等于把差异藏起来（这正是 M2 的原始缺陷）。
 */
export function buildSyncNotices(duration, rate) {
  const notices = []
  if (duration?.clamped) {
    notices.push(
      `目标时长 ${duration.requested}s 超出本页可设范围 ${DURATION_RANGE.min}–${DURATION_RANGE.max}s，已按 ${duration.value}s 填入`,
    )
  }
  if (rate?.clamped) {
    notices.push(
      `语速倍率 ${rate.requested}x 换算为 ${formatRatePercent(rate.percent)}，超出本页可设范围 ${formatRatePercent(RATE_PERCENT_RANGE.min)}~${formatRatePercent(RATE_PERCENT_RANGE.max)}，已按 ${formatRatePercent(rate.value) || '0%（不调节）'} 填入`,
    )
  }
  return notices
}
