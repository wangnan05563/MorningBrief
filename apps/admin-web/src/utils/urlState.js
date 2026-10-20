/**
 * URL 状态读写纯逻辑（T02511 / FR-UX-602）
 *
 * 为什么存在：PC 列表页的 tab / page / size 此前只活在组件内存里，刷新即丢、
 * 无法分享、无法前进后退（深链诉求 ACC-UX-601#3「刷新 /review?tab=approved&page=3 仍在原状态」）。
 * 各页各写一份 `route.query.xxx` 解析会散成十份口径不一的代码，且**参数校验**
 * （C68 那类「非法 channelId 静默按空池渲染」）最容易在复制中丢失。
 *
 * 本文件**刻意不 import vue / vue-router**：纯函数可以直接被 `node --test` 拉起
 * （admin-web 没有 vitest，只有 Playwright e2e 与 `scripts/*.test.mjs` 这套 node 测试），
 * 校验规则因此有真实断言可跑，而不是只能靠 e2e 顺带覆盖。
 * 与 vue 的绑定在 `composables/useUrlState.js`。
 *
 * 三条设计约定（都是踩过的坑）：
 * 1. **非法值回落默认值并如实报告**，绝不「按空值渲染」——`?page=abc` 要回到第 1 页
 *    并让调用方知道参数被丢弃过（C68 的根因就是「不校验即赋值 + 空态文案引错」）；
 * 2. **等于默认值时不写进 URL**：`/review?tab=pending&page=1&size=10` 这种地址没有分享价值，
 *    只会把地址栏弄脏并让「是否用户显式选择」变得不可读；
 * 3. **不认识的 query 键原样保留**：页面之间会往 URL 上挂额外参数（如 `channel_name`、`mode`），
 *    写回时整表替换会把别人的状态抹掉。
 */

/** 整数（含下限/可选上限）；非整数、NaN、越界都算非法 */
function parseInteger(raw, spec) {
  if (typeof raw !== 'string' && typeof raw !== 'number') return { ok: false, reason: '类型不支持' }
  const text = String(raw).trim()
  if (!/^-?\d+$/.test(text)) return { ok: false, reason: `不是整数：${text}` }
  const n = Number(text)
  const min = spec.min ?? 1
  if (n < min) return { ok: false, reason: `小于下限 ${min}：${n}` }
  // 上限可动态传入（如按 total 算出的最大页码）；给定时越界回落到上限而不是默认值，
  // 因为「最后一页」几乎总是用户真正想看的东西，回到第 1 页会让人以为数据丢了
  if (typeof spec.max === 'number' && Number.isFinite(spec.max) && spec.max >= min) {
    if (n > spec.max) return { ok: true, value: spec.max, clamped: `超过上限 ${spec.max}：${n}` }
  }
  return { ok: true, value: n }
}

/** 枚举白名单：大小写与空白敏感（tab 值直接进接口参数，宽松匹配会查出意料外的数据） */
function parseEnum(raw, spec) {
  const text = typeof raw === 'string' ? raw : String(raw ?? '')
  if (!spec.enum.includes(text)) return { ok: false, reason: `不在允许值 ${spec.enum.join('/')} 中：${text}` }
  return { ok: true, value: text }
}

/** 字符串（存在性校验交给调用方的 validator，如「频道必须真实存在」） */
function parseString(raw, spec) {
  const text = typeof raw === 'string' ? raw.trim() : String(raw ?? '').trim()
  if (!text) return { ok: false, reason: '为空' }
  if (spec.maxLength && text.length > spec.maxLength) return { ok: false, reason: `长度超过 ${spec.maxLength}` }
  if (typeof spec.pattern === 'string') {
    const re = new RegExp(spec.pattern)
    if (!re.test(text)) return { ok: false, reason: `格式不符 ${spec.pattern}` }
  }
  if (typeof spec.validator === 'function') {
    const r = spec.validator(text)
    if (r !== true) return { ok: false, reason: (r && String(r)) || '校验未通过' }
  }
  return { ok: true, value: text }
}

/** 单值解析：按 spec 形态选解析器（enum > int > string） */
function parseOne(raw, spec) {
  if (Array.isArray(spec.enum)) return parseEnum(raw, spec)
  if (spec.type === 'int' || typeof spec.min === 'number' || typeof spec.max === 'number') {
    return parseInteger(raw, spec)
  }
  return parseString(raw, spec)
}

/**
 * 从 query 读出状态。
 * @param {Record<string, unknown>} query vue-router 的 route.query（值可能是 string / string[] / null）
 * @param {Record<string, object>} specs  `{ tab: {enum:[...], default:'pending'}, page:{type:'int',default:1} }`
 * @returns {{values: object, invalid: Array<{key:string, raw:string, reason:string}>}}
 *
 * 数组形态（`?tag=a&tag=b`，浏览器手改 URL 常见）取第一个，不报错——
 * 但会在 invalid 里留痕，便于页面上提示「参数被修正过」。
 */
export function readUrlState(query, specs) {
  const values = {}
  const invalid = []
  const src = query && typeof query === 'object' ? query : {}
  for (const [key, spec] of Object.entries(specs)) {
    const raw = src[key]
    if (raw === undefined || raw === null || raw === '') {
      values[key] = spec.default
      continue
    }
    const single = Array.isArray(raw) ? raw[0] : raw
    if (Array.isArray(raw) && raw.length > 1) {
      invalid.push({ key, raw: String(raw.join(',')), reason: '同一参数出现多次，取第一个' })
    }
    const r = parseOne(single, spec)
    if (r.ok) {
      values[key] = r.value
      if (r.clamped) invalid.push({ key, raw: String(single), reason: r.clamped })
    } else {
      values[key] = spec.default
      invalid.push({ key, raw: String(single), reason: r.reason })
    }
  }
  return { values, invalid }
}

/**
 * 把状态写回 query 对象（不直接调路由，便于单测与「只算不改」的复用）。
 * 等于默认值的键会被删除；其他键原样保留。
 * @returns {Record<string, string>} 新对象（不修改入参）
 */
export function writeUrlQuery(currentQuery, specs, values) {
  const out = {}
  const src = currentQuery && typeof currentQuery === 'object' ? currentQuery : {}
  for (const [key, rawVal] of Object.entries(src)) {
    if (Object.prototype.hasOwnProperty.call(specs, key)) continue
    if (rawVal === undefined || rawVal === null) continue
    out[key] = Array.isArray(rawVal) ? String(rawVal[0] ?? '') : String(rawVal)
  }
  for (const [key, spec] of Object.entries(specs)) {
    if (!(key in values)) continue
    const v = values[key]
    if (v === undefined || v === null) continue
    if (String(v) === String(spec.default)) {
      delete out[key]
      continue
    }
    out[key] = String(v)
  }
  return out
}

/** 判断状态相对当前 URL 是否真的需要写回（避免 replace 抖动与无意义的历史记录） */
export function isQueryDirty(currentQuery, specs, values) {
  const a = writeUrlQuery(currentQuery, specs, values)
  const b = currentQuery && typeof currentQuery === 'object' ? currentQuery : {}
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  for (const k of keys) {
    if (String(a[k] ?? '') !== String(b[k] ?? '')) return true
  }
  return false
}

/**
 * 跨端（PC ↔ 移动端）重定向时的目标计算（T02511 的「跨端重定向保留 path 与 query」）。
 *
 * 背景：App.vue 早先在「视口是手机宽度但路由在 PC 命名空间」时直接 `replace('/m/home')`，
 * 于是手机上打开 `/queue?status=failed` 会被抹平成移动端首页——深链与筛选状态一起丢。
 * 反向（PC 视口访问 /m/xxx）同理。这里做的是：能对上等价表的换到对面同名页，
 * 对不上的回到对面首页，**query 永远带过去**。
 *
 * @param {string} path 当前路径（含 /news base 之后的部分，与 route.path 同口径）
 * @param {object} query 当前 query
 * @param {'mobile'|'desktop'} to 目标端
 * @returns {{path: string, query: object}}
 */
export function crossEndTarget(path, query, to) {
  const clean = stripModeQuery(query)
  const p = String(path || '/')
  if (to === 'mobile') {
    if (isMobilePath(p)) return { path: null, query: clean }
    const mapped = PC_TO_MOBILE[exactSegment(p)]
    return { path: mapped || '/m/home', query: mapped ? clean : withFrom(clean, p) }
  }
  if (isMobilePath(p)) {
    const mapped = MOBILE_TO_PC[exactSegment(p)]
    return { path: mapped || '/review', query: mapped ? clean : withFrom(clean, p) }
  }
  return { path: null, query: clean }
}

/**
 * 这一条路径属于移动端命名空间吗？
 *
 * ⚠ 不能用 `path.startsWith('/m')`：PC 侧的 `/materials`（素材录入）与 `/maintenance`（维护中心）
 * 同样以 `/m` 开头，用前缀判断会把它们当成移动端路径——桌面打开素材录入会被重定向到 `/review`，
 * 手机打开则再被算成「已在移动端」而不换端，两头都错（实测把 page-layout-padding 素材录入用例打红过）。
 * 移动端命名空间是 `/m` 本身与 `/m/…` 子路径，仅此两种形态。
 */
export function isMobilePath(path) {
  const p = String(path || '')
  return p === '/m' || p.startsWith('/m/')
}

/** `mode=mobile|desktop|auto` 是端模式覆盖开关，跨端跳转时必须丢掉，否则会立刻再被反向判定切回去 */
export function stripModeQuery(query) {
  const out = {}
  const src = query && typeof query === 'object' ? query : {}
  for (const [k, v] of Object.entries(src)) {
    if (k === 'mode') continue
    out[k] = Array.isArray(v) ? v[0] : v
  }
  return out
}

/** 取第一段（`/queue/123` → `queue`、`/m/manage/queue` → `manage`），用于等价表命中；未知段返回原串 */
function exactSegment(path) {
  const p = String(path || '')
  // 只在**确认是移动端命名空间**时才剥掉 `/m` 前缀，否则 `/materials` 会被削成 `aterials`
  const rest = isMobilePath(p) ? p.slice(2) : p
  return rest.replace(/^\//, '').split('/')[0] || ''
}

/** 对不上等价表时把原路径留在 `from` 里：至少用户可以被告知/自己回到原来那一页 */
function withFrom(query, path) {
  return { ...query, from: path }
}

const PC_TO_MOBILE = {
  review: '/m/review',
  queue: '/m/manage/queue',
  channels: '/m/manage/channels',
  ads: '/m/manage/ads',
}
const MOBILE_TO_PC = {
  '': '/review',
  home: '/review',
  review: '/review',
  message: '/review',
  mine: '/about',
  manage: '/queue',
}

/**
 * 校验 `?redirect=` 参数（T02511「重定向保留 path 与 query」的收口环节）。
 *
 * 只接受**站内绝对路径**：`/review?tab=approved` 可以，`//evil.com` 与
 * `https://evil.com` 不行——浏览器会把 `//host` 当协议相对 URL 跳转出去，
 * 登录页的 redirect 参数是最经典的开放重定向入口，不能只判「以 / 开头」。
 */
export function sanitizeRedirect(raw) {
  const text = Array.isArray(raw) ? String(raw[0] ?? '') : String(raw ?? '')
  if (!text.startsWith('/')) return null
  if (text.startsWith('//')) return null
  if (/^\/(?:m\/)?login\b/.test(text)) return null // 防自我循环
  return text
}
