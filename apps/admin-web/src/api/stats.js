/**
 * 统计 API 封装
 *
 * 对应后端 /admin/api/v1/stats/* 路由，是统计路径的唯一入口：
 * 视图层不得再出现 '/stats/*' 字面量，避免拼出后端不存在的端点。
 */
import api from '../api'

// 概览：按日期查询核心指标（DAU、播放量、完播率、平均收听时长等）
export const getOverview = (date) =>
  api.get('/stats/overview', { params: { date } })

// 趋势：按指标 + 区间（7d/30d/90d）查询时序
export const getTrend = (metric, range = '7d') =>
  api.get('/stats/trend', { params: { metric, range } })

// 频道健康：按天数区间聚合各频道指标
export const getChannelHealth = (rangeDays) =>
  api.get('/stats/channel-health', { params: { range_days: rangeDays } })

// RSS 健康：refresh=true 触发立即巡检，耗时较长需放宽超时
export const getRssHealth = (options = {}) =>
  api.get('/stats/rss-health', options)

// LLM 重试指标：服务端自进程启动以来累计
export const getLlmMetrics = () => api.get('/stats/llm-metrics')
