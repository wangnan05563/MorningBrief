/**
 * 频道管理 API 封装
 *
 * 对应后端 /admin/api/v1/channels/* 路由
 * 复用全局 axios 实例（已注入 JWT + 解包响应）
 */
import api from '../api'

export const listChannels = (activeOnly) => api.get('/channels', { params: { active_only: activeOnly } })
export const createChannel = (data) => api.post('/channels', data)
export const updateChannel = (id, data) => api.put(`/channels/${id}`, data)
export const deleteChannel = (id) => api.delete(`/channels/${id}`)
