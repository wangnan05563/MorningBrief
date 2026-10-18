/**
 * 登录失败原因的可读化（T02498：FR-UX-304 登录失败可见）
 *
 * 后端把「用户名不存在」与「密码错误」统一成同一句「用户名或密码错误」以防账号枚举，
 * 但 BizError 默认 http_status=200、错误码在响应体里，前端拦截器对 401 又是「跳转而不提示」，
 * 于是登录页最常见的一类失败曾经既拿不到文案、也没有落点。这里把三种来源统一成一句人话：
 * - 业务错误：拦截器 reject 的是 new Error(message)，message 即后端文案；
 * - HTTP 401/403：AuthError 走响应体 { code, message } 但 http_status 非 200，只能从 error.response.data 取；
 * - 连不上后端：axios 给的是 'Network Error' / 'timeout of 15000ms exceeded'，对用户没有信息量。
 */

/** 从各种错误形态里取出后端给的真实原因文案 */
function backendMessage(err) {
  return err?.response?.data?.message || err?.message || ''
}

export function describeLoginError(err) {
  const status = err?.response?.status
  const msg = backendMessage(err)
  if (status === 403 || msg.includes('禁用')) {
    return msg || '账号已被禁用，请联系管理员'
  }
  if (status === 401) {
    return msg || '用户名或密码错误'
  }
  if (err?.code === 'ECONNABORTED' || /timeout of/i.test(msg)) {
    return '登录请求超时，请稍后重试或检查网络'
  }
  if (/network error/i.test(msg) || /err_connection|failed to fetch/i.test(msg)) {
    return '无法连接服务器，请确认后端服务已启动、地址配置正确'
  }
  return msg || '登录失败，请稍后重试'
}
