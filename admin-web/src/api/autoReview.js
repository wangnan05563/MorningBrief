/**
 * 自动审批 API 封装
 *
 * 对应后端 /admin/api/v1/auto-review/* 路由
 */
import api from '../api'

// 获取自动审批配置
export const getAutoReviewConfig = () => api.get('/auto-review/config')

// 更新自动审批配置（仅 admin）
export const updateAutoReviewConfig = (data) => api.put('/auto-review/config', data)

// 获取统计指标（默认近 7 天）
export const getAutoReviewStats = (params = {}) =>
  api.get('/auto-review/stats', { params })

// 获取执行历史（分页，可按成功/失败过滤）
export const listAutoReviewHistory = (params = {}) =>
  api.get('/auto-review/history', { params })

// 重试失败的自动审批（仅 admin）
export const retryFailedAutoReview = (statId) =>
  api.post(`/auto-review/retry/${statId}`)
