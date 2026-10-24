/**
 * 登录跳转目标的单一来源（T02614）
 *
 * 401 现在有两条落地路径：前台请求由 axios 拦截器立即跳转；隐藏期间被丢弃的 401
 * 由 message 的恢复窗口在切回前台后补跳（见 utils/message.js）。两条路径必须按同一口径
 * 计算「哪一端的登录页」和 `?redirect=`，否则同一会话过期会因触发时机不同落到不同地址。
 */

/**
 * @param {Location} [location] 便于单测注入；默认取当前页面
 * @returns {{isMobile: boolean, loginPath: string, onLoginPage: boolean, appPath: string, redirectUrl: string}}
 */
export function resolveLoginTarget(location = globalThis.location) {
  const pathname = location?.pathname || '/'
  const search = location?.search || ''
  const isMobile = pathname.includes('/m/')
  // 前缀取 vite base：dev 下是 ''、生产是 '/news'
  const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  const loginPath = `${base}/${isMobile ? 'm/' : ''}login`
  // 只看末段是否登录页：base 前缀在 dev / 生产下不同，按后缀判定两端一致（FR-UX-304）
  const onLoginPage = pathname.endsWith(`${isMobile ? '/m' : ''}/login`)
  // redirect 用**去掉 vite base 前缀**的应用内路径，与 route.fullPath 同口径；
  // 登录页侧再经 sanitizeRedirect 校验（只接受站内绝对路径，见 T02511）
  const appPath = (pathname.slice(base.length) || '/') + search
  return {
    isMobile,
    loginPath,
    onLoginPage,
    appPath,
    redirectUrl: `${loginPath}?redirect=${encodeURIComponent(appPath)}`,
  }
}
