/**
 * 审计日志读口封装（T02909）
 *
 * 后端 GET /admin/api/v1/audit-logs 与 /audit-logs/categories。
 * 权限裁决：全量管理员可读（所有 B 端登录态可读全部 category，不按模块切分）。
 *
 * 两处都用 silent：审计是旁路信息，读取失败不该抢一条 toast 打断用户正在做的操作，
 * 由页面自带的失败态（含重试入口）来说明「这次没读到」，而不是「没有记录」。
 */
import api from './index'

export const listAuditLogs = (params) => api.get('/audit-logs', { params, silent: true })

export const listAuditCategories = () => api.get('/audit-logs/categories', { silent: true })
