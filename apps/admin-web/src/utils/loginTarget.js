/**
 * 登录跳转目标的单一来源（T02614）
 *
 * 401 现在有两条落地路径：前台请求由 axios 拦截器立即跳转；隐藏期间被丢弃的 401
 * 由 message 的恢复窗口在切回前台后补跳（见 utils/message.js）。两条路径必须按同一口径
 * 计算「哪一端的登录页」和 `?redirect=`，否则同一会话过期会因触发时机不同落到不同地址。
 *
 * T02633：应用前缀固定取自 utils/appPath，不再按 `import.meta.env.BASE_URL` 推导——
 * dev base 是 `/`、生产是 `/news/`，按 base 算会让 dev 的 redirect 混进 `/news` 前缀。
 */
import { APP_PREFIX, appPathOf, isLoginPath } from './appPath.js'

/**
 * @param {Location} [location] 便于单测注入；默认取当前页面
 * @returns {{isMobile: boolean, loginPath: string, onLoginPage: boolean, appPath: string, redirectUrl: string}}
 */
export function resolveLoginTarget(location = globalThis.location) {
  const pathname = location?.pathname || '/'
  const search = location?.search || ''
  const isMobile = pathname.includes('/m/')
  const loginPath = `${APP_PREFIX}/${isMobile ? 'm/' : ''}login`
  // redirect 用 vue-router 口径的应用内路径（已剥掉 /news），登录页拿它直接 router.push；
  // 合法性由登录页的 sanitizeRedirect 收口（只接受站内绝对路径，见 T02511）
  const appPath = appPathOf(pathname, search)
  return {
    isMobile,
    loginPath,
    onLoginPage: isLoginPath(pathname),
    appPath,
    redirectUrl: `${loginPath}?redirect=${encodeURIComponent(appPath)}`,
  }
}
