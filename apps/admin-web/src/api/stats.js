/**
 * 统计 API 封装
 *
 * 对应后端 /admin/api/v1/stats/* 路由。
 * 既有统计视图在组件内直接用 api.get 调用，这里收敛为统一模块，便于移动端复用。
 */
import api from '../api'

// 概览：按日期查询核心指标（DAU、播放量、完播率、平均收听时长等）
export const getOverview = (date) =>
  api.get('/stats/overview', { params: { date } })

// 趋势：按指标 + 区间（7d/30d/90d）查询时序
export const getTrend = (metric, range = '7d') =>
  api.get('/stats/trend', { params: { metric, range } })

// 今日关键指标（无需传日期，后端取当天）
export const getToday = () => api.get('/stats/today')
