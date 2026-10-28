/**
 * 跨端自动切换的可撤销提示（T02544 切片 6 / I59，口径见 T02336 §4.3）
 *
 * 背景：手机视口打开 PC 深链（或反之）时，router 守卫会直接换到对面同名页——
 * 地址和页面都变了，用户却只看到「点进来不是我要的那页」。I59 原建议是「改成弹窗确认」，
 * 评审后驳回：重定向方向本身是对的（`App.vue` 里 `?mode=` 已经实现了手动选端），
 * 缺的只是「告诉你换了」和「一键回原页面」。
 *
 * 本文件刻意不 import vue：storage 由调用方注入，`node --test` 可以直接断言序列化与失效规则。
 * 与 vue 的绑定在 `components/CrossEndNotice.vue`。
 */
import { isMobilePath } from './urlState.js'

export const CROSS_END_NOTICE_KEY = 'admin_cross_end_notice'

/** query 统一收敛成字符串值（vue-router 的 query 可能是数组/null，存进 sessionStorage 前先定形） */
function normalizeQuery(query) {
  const out = {}
  const src = query && typeof query === 'object' ? query : {}
  for (const [k, v] of Object.entries(src)) {
    if (v === undefined || v === null) continue
    out[k] = Array.isArray(v) ? String(v[0] ?? '') : String(v)
  }
  return out
}

/**
 * 由一次跨端重定向构造提示。
 *
 * @param {string} fromPath 用户原本要访问的路径（重定向前）
 * @param {object} fromQuery 原始 query
 * @param {string} landedPath 实际落地的路径（用于「导航走了就自动消失」）
 * @returns {null|{fromPath:string, fromQuery:object, landedPath:string, mode:'mobile'|'desktop'}}
 *
 * `mode` 是**原页面所属端**：回链必须显式带上它，否则守卫会按当前会话模式
 * 把用户再切一次——点了「回原页面」却回到同一页，提示就成了摆设。
 */
export function buildCrossEndNotice(fromPath, fromQuery, landedPath) {
  const p = String(fromPath || '')
  // 只接受站内绝对路径（与 sanitizeRedirect 同一条底线），否则宁可不提示
  if (!p.startsWith('/') || p.startsWith('//')) return null
  return {
    fromPath: p,
    fromQuery: normalizeQuery(fromQuery),
    landedPath: String(landedPath || ''),
    mode: isMobilePath(p) ? 'mobile' : 'desktop',
  }
}

export function serializeCrossEndNotice(notice) {
  if (!notice || typeof notice !== 'object') return ''
  return JSON.stringify(notice)
}

/** 解析存储内容；任何字段不合法都当作「没有提示」，绝不让坏数据把整条链路打断 */
export function parseCrossEndNotice(raw) {
  if (typeof raw !== 'string' || !raw) return null
  let obj
  try {
    obj = JSON.parse(raw)
  } catch {
    return null
  }
  if (!obj || typeof obj !== 'object') return null
  const fromPath = typeof obj.fromPath === 'string' ? obj.fromPath : ''
  if (!fromPath.startsWith('/') || fromPath.startsWith('//')) return null
  const mode =
    obj.mode === 'mobile' || obj.mode === 'desktop'
      ? obj.mode
      : isMobilePath(fromPath)
        ? 'mobile'
        : 'desktop'
  return {
    fromPath,
    fromQuery: normalizeQuery(obj.fromQuery),
    landedPath: typeof obj.landedPath === 'string' ? obj.landedPath : '',
    mode,
  }
}

export function saveCrossEndNotice(storage, notice) {
  const text = serializeCrossEndNotice(notice)
  if (!text) return
  try {
    storage.setItem(CROSS_END_NOTICE_KEY, text)
  } catch {
    /* sessionStorage 不可用（隐私模式/配额满）时静默：提示是锦上添花，不能挡住导航 */
  }
}

export function readCrossEndNotice(storage) {
  try {
    return parseCrossEndNotice(storage.getItem(CROSS_END_NOTICE_KEY))
  } catch {
    return null
  }
}

export function clearCrossEndNotice(storage) {
  try {
    storage.removeItem(CROSS_END_NOTICE_KEY)
  } catch {
    /* 同上 */
  }
}

/**
 * 导航到落点以外的路径后，提示自动失效（守卫每次导航调用）。
 * 只比 path 不比 query：落点页自己重写筛选参数（移动端审核列表就会）时提示仍然成立。
 */
export function shouldClearCrossEndNotice(notice, path) {
  if (!notice) return false
  return String(path || '') !== notice.landedPath
}

/** 「仍要查看原页面」的导航目标：原路径 + 原 query + 显式端模式 */
export function crossEndNoticeLink(notice) {
  if (!notice) return null
  return { path: notice.fromPath, query: { ...notice.fromQuery, mode: notice.mode } }
}
