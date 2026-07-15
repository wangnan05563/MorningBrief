/**
 * 通知管理 API 封装
 *
 * 对应后端 /admin/api/v1/notification/* 路由
 * 包含三块能力：基础配置（开关+钉钉凭证+base_url）、消息模板（CRUD+预览）、发送日志（列表+重发）
 */
import api from '../api'

// ===== 基础配置 =====

// 获取通知配置（包含全局开关、场景开关、钉钉 webhook/secret、admin base_url）
export const getNotificationConfig = () => api.get('/notification/config')

// 保存通知配置（webhook/secret 脱敏值 "******" 会被后端忽略，不覆盖原值）
export const saveNotificationConfig = (config) => api.put('/notification/config', config)

// 发送测试通知（验证 webhook 配置是否正确）
export const sendTestNotification = () => api.post('/notification/test')

// ===== 消息模板 =====

// 获取所有模板列表（含禁用模板，附带 variables 字段标识可用变量）
export const listNotificationTemplates = () => api.get('/notification/templates')

// 更新单条模板（name/title_template/body_template/enabled）
export const updateNotificationTemplate = (id, payload) =>
  api.put(`/notification/templates/${id}`, payload)

// 预览模板渲染效果（传入 variables 字典，返回 {title, body} 渲染文本）
export const previewNotificationTemplate = (id, variables = {}) =>
  api.post(`/notification/templates/${id}/preview`, { variables })

// ===== 发送日志 =====

// 分页查询发送日志（可按 event_type/status/workflow_id 过滤）
export const listNotificationLogs = (params = {}) =>
  api.get('/notification/logs', { params })

// 重发某条日志（用日志中记录的 payload 重新渲染并发送）
export const resendNotificationLog = (id) => api.post(`/notification/logs/${id}/resend`)
