/**
 * 移动端适配 API 封装（对应后端 /admin/api/v1/m/* 路由，SRS INT-M101~M105）
 *
 * 复用全局 api 实例（自动注入 JWT、统一解包 {code,message,data}）。
 */
import api from '../api'

// 移动首页聚合：今日指标 + 待审数 + 未读数
export const getDashboardSummary = () => api.get('/m/dashboard-summary')

// 运营消息收件箱（分页 + 未读数）
export const getInbox = (params = {}) => api.get('/m/inbox', { params })

// 标记已读：{ message_ids?: number[], mark_all?: boolean }
export const markRead = (body) => api.post('/m/inbox/mark-read', body)

// 设备登记（登录风控 / 绑定）
export const registerDevice = (body) => api.post('/m/device/register', body)

// 推送 token 注册
export const registerPush = (body) => api.post('/m/push/register', body)

// 应急停服（仅超级管理员，需 reason）
export const emergencyStop = (body) => api.post('/m/emergency/stop', body)

// 维护态查询（移动端展示停服横幅）：{ enabled, reason, by, at }
export const getMaintenanceStatus = () => api.get('/m/maintenance-status')

// 解除应急停服（仅超级管理员）
export const emergencyResume = () => api.post('/m/emergency/resume')
