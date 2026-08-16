/**
 * 稿件管理 API 封装
 *
 * 对应后端 /admin/api/v1/scripts/* 路由
 */
import api from '../api'

// 按 workflow_id 查稿件（一个工作流只有一份稿件）
export const getScriptByWorkflow = (workflowId) =>
  api.get('/scripts', { params: { workflow_id: workflowId } })

export const getScript = (id) => api.get(`/scripts/${id}`)

// 覆盖式更新分段（增删改 segment）
export const updateSegments = (id, segments) =>
  api.put(`/scripts/${id}/segments`, { segments })

export const deleteScript = (id) => api.delete(`/scripts/${id}`)
