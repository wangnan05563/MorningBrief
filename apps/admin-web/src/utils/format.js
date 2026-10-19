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

export function metricValue(raw, meta) {
  if (raw === null || raw === undefined || raw === '') return '-'
  const n = Number(raw)
  if (!Number.isFinite(n) || !meta) return '-'
  const precision = meta.display?.precision ?? 0
  const value = n * (meta.display?.factor ?? 1)
  // 0 位小数按千分位分组（DAU/播放量常上万），带小数的（完播率、分钟）保留定点格式
  return precision > 0
    ? value.toFixed(precision)
    : Math.round(value).toLocaleString('zh-CN')
}

export function metricText(raw, meta) {
  const v = metricValue(raw, meta)
  if (v === '-' || !meta?.display?.unit) return v
  return `${v} ${meta.display.unit}`
}
