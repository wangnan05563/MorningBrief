/**
 * 素材管理 API 封装
 *
 * 对应后端 /admin/api/v1/materials/* 路由
 */
import api from '../api'

export const listMaterials = (workflowId, page = 1, size = 20) =>
  api.get('/materials', { params: { workflow_id: workflowId, page, size } })

export const getMaterial = (id) => api.get(`/materials/${id}`)

export const createMaterial = (data) => api.post('/materials', data)

export const updateMaterial = (id, data) => api.put(`/materials/${id}`, data)

export const deleteMaterial = (id) => api.delete(`/materials/${id}`)
