/**
 * 用户反馈管理 API 封装（SRS M5 反馈视图）
 *
 * 对应后端 /admin/api/v1/feedbacks/* 路由（仅 admin）。
 * 复用全局 api 实例（自动注入 JWT + 解包 {code,message,data}）。
 */
import api from '../api'

// 分页查询反馈列表：支持 status 筛选（pending/processed/resolved）
export const listFeedbacks = (params = {}) => api.get('/feedbacks', { params })

// 更新反馈状态：status ∈ {pending, processed, resolved}
export const updateFeedbackStatus = (id, status) =>
  api.put(`/feedbacks/${id}/status`, { status })
