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
