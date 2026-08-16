/**
 * 终端用户管理 API 封装（SRS M5 FR-M501 / FR-M502）
 *
 * 对应后端 /admin/api/v1/users/* 路由（仅 admin）。
 * 复用全局 api 实例（自动注入 JWT + 解包 {code,message,data}）。
 */
import api from '../api'

// 分页检索终端用户：支持 keyword（昵称/openid 模糊）、disabled 状态筛选
export const listUsers = (params = {}) => api.get('/users', { params })

// 禁用 / 启用终端用户：disabled=1 禁用，0 启用（受控 + 审计由后端保证）
export const toggleUserStatus = (userId, disabled) =>
  api.post(`/users/${userId}/toggle-status`, { disabled })
