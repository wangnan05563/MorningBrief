/**
 * 应用路径前缀的唯一来源（T02633 / FR-UX-304）
 *
 * 为什么不从 `import.meta.env.BASE_URL` 推导：vite dev base 是 `/`（让 Playwright 能从
 * 根路径导航、静态资源也按根路径直出），而应用本身——vue-router 的 history base、
 * 后端入口、SSE、静态代理——在生产与 dev 下都固定挂在 `/news` 上：
 *   生产：Tailscale Funnel `--set-path /news/` 路由；
 *   dev：Vite proxy 的 `rewrite` 去掉 `/news` 前缀再转发后端。
 * 用 BASE_URL 推导会把 dev 的「应用内路径」算成带 `/news` 的形式，`?redirect=` 里于是
 * 留下 `/news/...`，登录后按 route 口径拼成 `/news/news/...`（T02614 实测到过）。
 * 静态资源（`public/` 下的图）确实跟随 BASE_URL，因此仍单独使用，不要混进这里。
 */
export const APP_PREFIX = '/news'
export const APP_BASE = `${APP_PREFIX}/`

/**
 * 给绝对路径补应用前缀；已带前缀时原样返回（幂等，DB 里存的旧值可能已带前缀）。
 * @param {string} path 以 `/` 开头的应用内路径
 */
export function withAppPrefix(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  if (p === APP_PREFIX || p.startsWith(`${APP_PREFIX}/`)) return p
  return `${APP_PREFIX}${p}`
}

/**
 * 去掉应用前缀，得到 vue-router 口径的路径（`route.path` / `route.fullPath`）。
 * @param {string} pathname
 */
export function stripAppPrefix(pathname) {
  const p = pathname || '/'
  if (p === APP_PREFIX) return '/'
  return p.startsWith(`${APP_PREFIX}/`) ? p.slice(APP_PREFIX.length) : p
}

/**
 * 当前地址对应的应用内路径（含 query），用于 `?redirect=` 与 `?from=`。
 * @param {string} pathname
 * @param {string} [search] 形如 `?tab=approved`
 */
export function appPathOf(pathname, search = '') {
  return stripAppPrefix(pathname) + search
}

/**
 * 是否停在登录页（PC 或移动端）。只认末段，`/login-help` 之类不算，
 * 避免把帮助页误判成登录页而让 401 补跳变成 no-op。
 * @param {string} pathname
 */
export function isLoginPath(pathname) {
  const p = stripAppPrefix(pathname).replace(/\/+$/, '')
  return p === '/login' || p === '/m/login'
}

// 后端入口：axios / EventSource / 就绪探针 / 交互式文档，均与前端同源同前缀
export const API_BASE_URL = withAppPrefix('/admin/api/v1')
export const SSE_ENDPOINT = withAppPrefix('/admin/api/v1/events/stream')
export const READY_PATH = withAppPrefix('/api/health/ready')
export const API_DOCS_PATH = withAppPrefix('/docs')
