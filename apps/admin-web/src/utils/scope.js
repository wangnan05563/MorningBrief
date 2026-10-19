/**
 * 累计口径工具（T02508 / FR-UX-503）。
 *
 * 解决的问题：像「触发率」「连续失败次数」这类指标存在进程内存里，服务重启就归零。
 * 页面只写数字时，运维无法判断这是"今天的"还是"攒了半个月的"，样本量大小也读不出来。
 * 后端为此回传 started_at / pid（见 backend/app/core/runtime.py），这里负责把它们
 * 变成一句人话，两个页面（LLM 指标页 / RSS 健康度页）共用一份文案规则，避免各写各的。
 *
 * 诚实原则：后端没给 started_at（老版本）时不拿当前时间冒充起点——
 * 一句「后端未返回累计起点时间」比一个看起来很精确的假日期安全得多。
 */
import dayjs from 'dayjs'

/**
 * 解析后端返回的累计起点。
 * @param {string|null} raw 本地 naive 的 "YYYY-MM-DDTHH:mm:ss"
 * @returns {object|null} 合法则返回 dayjs 对象，否则 null
 */
export function parseStartedAt(raw) {
  if (!raw) return null
  const d = dayjs(raw)
  return d.isValid() ? d : null
}

/**
 * 生成「累计自 x 时间，重启清零」文案（PRD ACC-UX-501 要求明确显示）。
 * @param {{startedAt?: string|null, pid?: number|null, subject?: string}} opts
 *        subject 是这句口径修饰的对象名，如「触发率与重试计数」
 * @returns {string}
 */
export function cumulativeScopeText({ startedAt, pid, subject = '以下指标' } = {}) {
  const started = parseStartedAt(startedAt)
  if (!started) {
    return `${subject}自服务进程启动累计，服务重启后清零（后端未返回累计起点时间）`
  }
  const pidText = pid ? `（PID ${pid}）` : ''
  return `${subject}累计自 ${started.format('YYYY-MM-DD HH:mm:ss')}${pidText}，服务重启后清零`
}

/**
 * 生成「已运行多久」文案，用来判断累计样本攒了多长时间。
 * @param {{startedAt?: string|null, now?: object}} opts now 为 dayjs 对象（取数时刻，不做定时器）
 * @returns {string} 空串表示无起点、不显示
 */
export function uptimeText({ startedAt, now } = {}) {
  const started = parseStartedAt(startedAt)
  if (!started || !now) return ''
  const minutes = Math.max(0, Math.floor(now.diff(started, 'minute')))
  if (minutes < 60) return `${minutes} 分钟`
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  if (days > 0) return `${days} 天 ${hours} 小时`
  return `${hours} 小时 ${minutes % 60} 分钟`
}
