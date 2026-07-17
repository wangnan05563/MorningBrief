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
  baseURL: '/admin/api/v1',
  timeout: 15000,
})

// 请求拦截：注入 token（延迟导入避免循环依赖）
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
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
      if (!response.config?.silent) {
        ElMessage.error(message || '请求失败')
      }
      return Promise.reject(new Error(message))
    }
    return data
  },
  (error) => {
    // 页面隐藏时所有错误静默处理，防止 ElMessage 或跳转激活窗口
    if (document.hidden) {
      return Promise.reject(error)
    }
    if (error.response?.status === 401) {
      // token 失效：清除本地状态
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_username')
      localStorage.removeItem('admin_role')
      // 页面隐藏时跳过跳转：location.href 会激活最小化窗口，
      // 用户恢复后路由守卫基于已清空的 token 自动跳转到登录页，效果一致
      if (!document.hidden && globalThis.location.pathname !== '/login') {
        globalThis.location.href = '/login'
      }
    } else if (!error.config?.silent) {
      // silent 请求（如后台轮询）不弹 ElMessage，避免最小化时积压错误提示
      if (error.response?.status === 403) {
        ElMessage.error('无权限执行此操作')
      } else {
        ElMessage.error(error.response?.data?.message || error.message || '请求失败')
      }
    }
    return Promise.reject(error)
  }
)

export default api
