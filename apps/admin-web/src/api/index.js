/**
 * API 封装：axios 实例 + JWT 请求拦截 + 统一响应/错误处理
 *
 * 设计要点：
 * - 请求拦截器自动注入 Bearer token，无需每个调用处手动添加
 * - 响应拦截器解包 { code, message, data }，调用方直接拿到 data
 * - 401 自动跳转登录，403 提示无权限，其他错误统一 ElMessage 提示
 */
import axios from 'axios'
import { ElMessage } from '../utils/message'

const api = axios.create({
  // baseURL 带 /news 前缀：通过 Tailscale Funnel 访问时，
  // Funnel 自动去除 /news/ 前缀转发给后端，后端收到 /admin/api/v1/...
  // 本地开发时 Vite proxy 的 rewrite 去除 /news 前缀
  baseURL: '/news/admin/api/v1',
  timeout: 15000,
  // NFR-M103：鉴权 token 存于 HttpOnly Cookie，需随请求自动携带（同源部署自动发送）
  withCredentials: true,
})

/**
 * 标记「这条失败已经由拦截器弹过提示」。
 *
 * 为什么要标记而不只靠文案去重：页面 catch 里常写
 * `ElMessage.error('删除预览失败：' + e.message)` 这类带上下文的文案，与拦截器
 * 弹的原文并不相同，按文案去重合不起来，用户就会看到同一件事两条 toast。
 * 页面改用 notifyErrorOnce(e, ...) 即可让「谁先弹过」成为唯一判据。
 * silent 请求不标记——拦截器根本没弹，页面当然还要提示。
 */
function _markNotified(err) {
  try {
    err.__uiNotified = true
  } catch {
    // 极少数冻结对象无法附加标记：退化为只做文案去重，不影响主流程
  }
  return err
}

// 请求拦截：鉴权 token 由 HttpOnly Cookie 自动携带（NFR-M103），
// 非浏览器 API 客户端仍可经 Authorization 头调用（后端双通道兼容）。
api.interceptors.request.use((config) => {
  return config
})

// 响应拦截：解包统一响应格式 + 错误处理
// 请求配置中可通过 silent: true 跳过全局 ElMessage 提示（适用于后台轮询等静默请求）
api.interceptors.response.use(
  (response) => {
    // blob 响应（音频流式下载）直接返回原始数据，不走 { code, message, data } 解构
    // 否则 Blob 没有 code 字段，解构得 undefined，!== 0 触发误报"请求失败"
    if (response.config?.responseType === 'blob') {
      return response.data
    }
    const { code, message, data } = response.data
    // code !== 0 表示业务错误（如参数校验失败），统一提示
    if (code !== 0) {
      const err = new Error(message)
      if (!response.config?.silent) {
        ElMessage.error(message || '请求失败')
        _markNotified(err)
      }
      return Promise.reject(err)
    }
    return data
  },
  (error) => {
    // 页面隐藏时不再整体静默丢弃提示：401 维持「不跳转、不清本地态」（避免后台标签页把人踢下线），
    // 其余错误交给 ElMessage 安全包装器入队、恢复后聚合补发（FR-UX-301）
    if (error.response?.status === 401 && document.hidden) {
      return Promise.reject(error)
    }
    if (error.response?.status === 401) {
      // token 失效：清除本地非敏感状态（admin_token 已存 HttpOnly Cookie，JS 不可清除）
      localStorage.removeItem('admin_username')
      localStorage.removeItem('admin_role')
      // 按端（PC / 移动）跳转对应登录页；前缀取 vite base，dev 下是 '/'、生产是 '/news/'。
      // 原先硬编码 '/news' 前缀：dev 下 pathname 永远不等于 loginPath，「已在登录页」
      // 判不出来，于是登录失败会被 location.href 刷走页面，错误提示根本没机会显示（FR-UX-304）
      const pathname = globalThis.location.pathname
      const isMobile = pathname.includes('/m/')
      const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
      const loginPath = `${base}/${isMobile ? 'm/' : ''}login`
      // 只看末段是否登录页：base 前缀在 dev / 生产下不同，按后缀判定两端一致
      const onLoginPage = pathname.endsWith(`${isMobile ? '/m' : ''}/login`)
      if (!document.hidden && !onLoginPage) {
        globalThis.location.href = loginPath
      } else if (!error.config?.silent) {
        // 已经在登录页（或页面隐藏不便跳转）时，401 不能是静默失败：
        // 用户点了「登录」却毫无反应，只会反复重试同一个错密码（FR-UX-304）
        ElMessage.error(error.response?.data?.message || '用户名或密码错误')
        _markNotified(error)
      }
    } else if (!error.config?.silent) {
      // silent 请求（如后台轮询）不弹 ElMessage，避免最小化时积压错误提示
      if (error.response?.status === 403) {
        ElMessage.error('无权限执行此操作')
      } else {
        ElMessage.error(error.response?.data?.message || error.message || '请求失败')
      }
      _markNotified(error)
    }
    return Promise.reject(error)
  }
)

export default api
