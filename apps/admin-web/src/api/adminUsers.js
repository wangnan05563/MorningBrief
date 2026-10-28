/**
 * 后台账号管理 API（T03439）
 *
 * 对应后端 /admin/api/v1/auth/users/*（仅 admin）。
 * 与终端用户 API（api/users.js）分开：这里管的是能登录后台的管理员/运营账号。
 */
import api from './index'

export const listAdminUsers = (params = {}) => api.get('/auth/users', { params })

export const createAdminUser = (payload) => api.post('/auth/users', payload)

export const updateAdminUser = (id, payload) => api.put(`/auth/users/${id}`, payload)

export const deleteAdminUser = (id, reason = '') =>
  api.delete(`/auth/users/${id}`, { params: reason ? { reason } : {} })
