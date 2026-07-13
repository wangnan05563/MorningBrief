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

/**
 * AI 自动生成频道提示词
 * 调用 LLM 根据频道 name + description 生成 intro/outro/constraint/template
 * LLM 生成耗时较长，超时设为 120s（覆盖后端 LLM_TIMEOUT_SEC 默认 30s + 重试时间）
 */
export const generateChannelPrompts = (id) => api.post(`/channels/${id}/generate-prompts`, {}, { timeout: 120000 })
