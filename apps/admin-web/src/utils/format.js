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
 * 秒 → 人读时长（I5 / T02518）。
 *
 * 原本只有 PC 审核列表 `views/review/ReviewList.vue` 里有一份同名局部函数。
 * 移动端审批卡片要补「成品时长 / 凑时」信号（外勤看不到凑时标记会把凑时长的节目判为合格），
 * 若再抄一份，两端口径就会像历史上那样分叉——所以提到公共工具里共用。
 *
 * @param {number|null|undefined} sec 秒数
 * @returns {string} 如 `45 秒` / `3 分 12 秒` / `1 时 5 分`，无值返回 '-'
 */
export function formatDuration(sec) {
  if (sec == null || sec === '') return '-'
  // 接口把秒数下发成字符串或脏值时不能让页面出现「NaN 时 NaN 分」：
  // 无法转成有限数一律按无值处理（D69 / T02759）。
  const n = Number(sec)
  if (!Number.isFinite(n) || n < 0) return '-'
  if (n < 60) return `${n} 秒`
  if (n < 3600) return `${Math.floor(n / 60)} 分 ${n % 60} 秒`
  return `${Math.floor(n / 3600)} 时 ${Math.floor((n % 3600) / 60)} 分`
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

/**
 * 审计详情摘要（T03670）——从 AuditTrail.vue 抽出，让"拍平"这件事可单测。
 *
 * 原实现只判断顶层是不是对象，取值用模板串 `${detail[k]}`：k 命中 result/before/after
 * 这类结构化值时 JS 默认转成 `[object Object]`，生产库快照里值班速读的那一行整条失效
 * （现场形态：`result=[object Object],[object Object]`）。
 *
 * 口径：
 * - 结构化值递归拍平成紧凑形态（`{k:v,…}` / `[a,b,…]`），任何深度都不落到默认 String()；
 * - 嵌套过深（>3 层）给省略形态 `…`，不为了"全"牺牲可读性；
 * - 整行有字符上限，超出补省略号——摘要区不是 JSON 查看器，长尾看详情弹窗/原始记录。
 */
const AUDIT_SUMMARY_KEYS = ['reason', 'note', 'message', 'days', 'count', 'deleted', 'cleaned_count']
const AUDIT_SUMMARY_MAX_CHARS = 200
const AUDIT_VALUE_MAX_DEPTH = 3
const AUDIT_VALUE_MAX_ITEMS = 3

function clampAuditSummary(text, maxChars) {
  if (text.length <= maxChars) return text
  return `${text.slice(0, Math.max(1, maxChars - 1))}…`
}

function renderAuditValue(value, depth) {
  if (value === null) return 'null'
  const type = typeof value
  if (type === 'string' || type === 'number' || type === 'boolean' || type === 'bigint') {
    return String(value)
  }
  if (type !== 'object') return ''
  if (depth >= AUDIT_VALUE_MAX_DEPTH) return '…'
  if (Array.isArray(value)) {
    if (!value.length) return '[]'
    const head = value.slice(0, AUDIT_VALUE_MAX_ITEMS).map((v) => renderAuditValue(v, depth + 1))
    const tail = value.length > AUDIT_VALUE_MAX_ITEMS ? `,…+${value.length - AUDIT_VALUE_MAX_ITEMS}项` : ''
    return `[${head.join(',')}${tail}]`
  }
  const entries = Object.entries(value)
  if (!entries.length) return '{}'
  const head = entries
    .slice(0, AUDIT_VALUE_MAX_ITEMS)
    .map(([k, v]) => `${k}:${renderAuditValue(v, depth + 1)}`)
  const tail = entries.length > AUDIT_VALUE_MAX_ITEMS ? ',…' : ''
  return `{${head.join(',')}${tail}}`
}

export function summarizeAuditDetail(detail, { maxChars = AUDIT_SUMMARY_MAX_CHARS } = {}) {
  if (detail === undefined || detail === null) return ''
  if (typeof detail !== 'object') return clampAuditSummary(String(detail), maxChars)
  const picked = AUDIT_SUMMARY_KEYS.filter(
    (k) => detail[k] !== undefined && detail[k] !== null && detail[k] !== '',
  )
  const shown = (picked.length ? picked : Object.keys(detail)).slice(0, AUDIT_VALUE_MAX_ITEMS)
  const text = shown.map((k) => `${k}=${renderAuditValue(detail[k], 0)}`).join(' · ')
  return clampAuditSummary(text, maxChars)
}
