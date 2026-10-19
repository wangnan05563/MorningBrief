/**
 * 通用格式化工具
 */

/**
 * 将 ISO 时间字符串格式化到秒（去掉毫秒和时区后缀）。
 *
 * 后端返回的时间多为 ISO 格式带微秒（如 2026-07-14T17:00:13.299787），
 * 前端显示到秒即可，毫秒精度对运维无意义且占用列宽。
 *
 * 仅做字符串截断而非 Date 解析，避免本地时区转换导致与后端时间偏差。
 * 后端已统一返回本地时间（utcnow_naive），字符串截断可保持原值不变。
 *
 * @param {string|null|undefined} t ISO 时间字符串
 * @returns {string} 格式化后的时间（YYYY-MM-DDTHH:mm:ss）或 '-'
 */
export function formatTime(t) {
  if (!t) return '-'
  return String(t).replace('T', ' ').substring(0, 19)
}

/**
 * 指标格式化（FR-UX-501 / T02506）。
 *
 * 数值与单位换算一律取自接口随数据下发的 `meta`
 * （后端唯一来源 `backend/app/services/stats_metrics.py`），页面不再各写一份
 * 「(分钟)」「(%)」和 `*100`——那正是「平均收听标签写分钟、值是秒」的成因。
 * meta 缺失时返回 '-'：宁可空着，也不猜单位把秒当分钟显示。
 *
 * @param {{label?:string, display?:{unit?:string, factor?:number, precision?:number}}} meta
 */
export function metricLabel(meta) {
  if (!meta) return '-'
  const unit = meta.display?.unit
  return unit ? `${meta.label}(${unit})` : meta.label
}

/**
 * 换算后的**数值**（图表/坐标轴用它，文案用 `metricValue`）。
 *
 * FR-UX-502 / T02507：趋势曲线要和卡片同一个刻度，就不能各乘各的 100——
 * 把「按 meta 换算」收敛成这一个出口，格式化只是给它加千分位和小数位。
 * 不可换算（缺 meta / 非数）返回 null，调用方按「没有数据」处理，不返回 0。
 */
export function metricNumber(raw, meta) {
  if (raw === null || raw === undefined || raw === '') return null
  const n = Number(raw)
  if (!Number.isFinite(n) || !meta) return null
  const precision = meta.display?.precision ?? 0
  const value = n * (meta.display?.factor ?? 1)
  return precision > 0 ? Number(value.toFixed(precision)) : Math.round(value)
}

export function metricValue(raw, meta) {
  const value = metricNumber(raw, meta)
  if (value === null) return '-'
  const precision = meta.display?.precision ?? 0
  // 0 位小数按千分位分组（DAU/播放量常上万），带小数的（完播率、分钟）保留定点格式
  return precision > 0 ? value.toFixed(precision) : value.toLocaleString('zh-CN')
}

/**
 * 带单位的展示文案（趋势图峰值、tooltip 用它，与卡片同源不同形）。
 *
 * `%` 按中文排版惯例紧跟数字（65.0%），其余单位加空格（8.5 分钟）。
 */
export function metricText(raw, meta) {
  const v = metricValue(raw, meta)
  const unit = meta?.display?.unit
  if (v === '-' || !unit) return v
  return unit === '%' ? `${v}${unit}` : `${v} ${unit}`
}
