/**
 * 审核 API 封装
 *
 * 对应后端 /admin/api/v1/reviews/* 路由
 */
import api from '../api'

// 审核列表（可按 workflow_id 过滤）
export const listReviews = (params = {}) =>
  api.get('/reviews', { params })

export const getReview = (id) => api.get(`/reviews/${id}`)

// 审核操作：approve/reject/replace
export const handleReviewAction = (id, action, reason = null, segmentId = null) =>
  api.post(`/reviews/${id}/action`, { action, reason, segment_id: segmentId })
