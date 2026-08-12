/**
 * 广告投放 API 封装（SRS M7 FR-M702 移动端启停）
 *
 * 对应后端 /admin/api/v1/ads/* 路由。
 * 复用全局 api 实例（自动注入 JWT + 解包 {code,message,data}）。
 */
import api from '../api'

// 投放规则分页列表（带素材名称）
export const listPlacements = (params = {}) => api.get('/ads/placements', { params })

// 投放启停：enabled=1 启用，0 停用（后端仅暴露 enabled 安全开关）
export const updatePlacement = (id, enabled) =>
  api.put(`/ads/placements/${id}`, { enabled })
