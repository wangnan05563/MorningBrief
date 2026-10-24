/**
 * API 封装：axios 实例 + JWT 请求拦截 + 统一响应/错误处理
 *
 * 设计要点：
 * - 请求拦截器自动注入 Bearer token，无需每个调用处手动添加
 * - 响应拦截器解包 { code, message, data }，调用方直接拿到 data
 * - 401 自动跳转登录，403 提示无权限，其他错误统一 ElMessage 提示
 */
import axios from 'axios'
import { ElMessage, markAuthExpired, setAuthExpiredHandler } from '../utils/message'
import { resolveLoginTarget } from '../utils/loginTarget'
import { API_BASE_URL } from '../utils/appPath'

const api = axios.create({
  // 前缀统一由 utils/appPath 提供（T02633）：生产 Tailscale Funnel 剥掉 /news 转发后端，
  // 本地由 Vite proxy 的 rewrite 去掉 /news
  baseURL: API_BASE_URL,
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

/**
 * 会话失效：清除本地非敏感状态（admin_token 已存 HttpOnly Cookie，JS 不可清除），
 * 并按当前端跳转到对应登录页。
 *
 * @returns {boolean} 是否真的发生了跳转；已在登录页时返回 false
 */
function _redirectToLogin() {
  const target = resolveLoginTarget()
  localStorage.removeItem('admin_username')
  localStorage.removeItem('admin_role')
  if (target.onLoginPage) return false
  globalThis.location.href = target.redirectUrl
  return true
}

// T02614：隐藏期间丢弃的 401 由 message 的恢复窗口在切回前台后回调这里补跳。
// 注册放在模块顶层：只要用过 api 实例，这条恢复路径就与拦截器同源可用。
setAuthExpiredHandler(_redirectToLogin)

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
      err.code = code
      // INT-UX-01：业务错误信封的 data 位带结构化明细（如敏感列哨兵被拒时的
      // { errors: [{ field, message }] }）。原先这里只留 message 就把明细丢了，
      // 页面拿不到「哪个字段错了」，只能把一句中文 toast 出来。
      err.payload = data
      if (!response.config?.silent) {
        ElMessage.error(message || '请求失败')
        _markNotified(err)
      }
      return Promise.reject(err)
    }
    return data
  },
  (error) => {
    // T02833：window-guard 主动丢弃的请求从未离开浏览器，不是网络故障。
    // 恢复保护期内的请求已在 guard 侧挂起、就绪后原样重放，走不到这里；
    // 能到这里的只有「页面隐藏期」的请求——用户看不到也点不了，静默收尾即可，
    // 否则会弹成一条自造的 Network Error，还会被反馈队列留到回前台补发。
    if (error.request?.__guardAborted || error.__guardAborted) {
      return Promise.reject(_markNotified(error))
    }
    // 页面隐藏时不再整体静默丢弃提示：401 维持「不跳转、不清本地态」（避免后台标签页把人踢下线），
    // 其余错误交给 ElMessage 安全包装器入队、恢复后聚合补发（FR-UX-301）
    if (error.response?.status === 401 && document.hidden) {
      // T02614：只记标记，切回前台由恢复窗口补跳登录页；否则隐藏期间的 401 被彻底丢掉，
      // 用户回到前台后还停在已过期的会话上，直到下一次请求才被踢。
      markAuthExpired()
      return Promise.reject(error)
    }
    if (error.response?.status === 401) {
      // T02511（FR-UX-602）：redirect 带上「用户原本在哪一页（含 query）」，登录后可回到原处；
      // 计算口径与隐藏期补跳共用 utils/loginTarget，避免两条路径落到不同地址。
      if (!_redirectToLogin() && !error.config?.silent) {
        // 已经在登录页时，401 不能是静默失败：
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
