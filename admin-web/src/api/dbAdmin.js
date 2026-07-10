/**
 * 数据库维护 API 封装
 *
 * 对应后端 /admin/api/v1/db-admin/* 路由
 * 所有接口需 admin 角色（axios 拦截器自动注入 Bearer token）
 */
import api from './index'

// 危险操作确认令牌，须与后端 DB_ADMIN_CONFIRM_TOKEN 一致
export const CONFIRM_TOKEN = 'CONFIRM_DELETE'

// ---- 表浏览 ----

/** 列出所有白名单表及行数 */
export function listTables() {
  return api.get('/db-admin/tables')
}

/** 获取表结构（列信息） */
export function getTableSchema(table) {
  return api.get(`/db-admin/tables/${table}/schema`)
}

// ---- 行级查询 ----

/** 分页查询表数据 */
export function listRows(table, params = {}) {
  return api.get(`/db-admin/tables/${table}/rows`, { params })
}

// ---- 行 CRUD ----

/** 新增一行 */
export function createRow(table, values) {
  return api.post(`/db-admin/tables/${table}/rows`, { values })
}

/** 更新一行（主键不可更新） */
export function updateRow(table, pkValue, values) {
  return api.patch(`/db-admin/tables/${table}/rows/${pkValue}`, { values })
}

/** 删除一行（含级联，需 confirm_token） */
export function deleteRow(table, pkValue) {
  return api.delete(`/db-admin/tables/${table}/rows/${pkValue}`, {
    params: { confirm_token: CONFIRM_TOKEN },
  })
}

/** 批量删除（需 confirm_token） */
export function batchDelete(table, ids) {
  return api.post(`/db-admin/tables/${table}/rows/batch-delete`, {
    ids,
    confirm_token: CONFIRM_TOKEN,
  })
}

// ---- 级联预览 ----

/** 预览级联删除影响范围 */
export function cascadePreview(table, ids) {
  return api.post(`/db-admin/tables/${table}/cascade-preview`, { ids })
}

// ---- 导出 ----

/** 导出表数据（返回 Blob，触发下载） */
export async function exportRows(table, format = 'csv') {
  const response = await api.get(`/db-admin/tables/${table}/export`, {
    params: { format },
    responseType: 'blob',
  })
  // 触发浏览器下载
  const url = URL.createObjectURL(response)
  const link = document.createElement('a')
  link.href = url
  link.download = `${table}_export.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// ---- 导入 ----

/** 导入数据（需 confirm_token） */
export function importRows(table, rows, mode = 'insert') {
  return api.post(`/db-admin/tables/${table}/import`, {
    rows,
    mode,
    confirm_token: CONFIRM_TOKEN,
  })
}

// ---- 审计日志 ----

/** 查询数据库维护审计日志 */
export function listAuditLogs(limit = 100) {
  return api.get('/db-admin/audit-log', { params: { limit } })
}
