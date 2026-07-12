/**
 * 爬虫素材 API 封装
 *
 * 对应后端 /admin/api/v1/materials/* 路由
 * 供工作流产物查看使用，需 B 端 admin 鉴权
 */
import api from './index'

/**
 * 按 workflow_id 分页查询素材列表
 * @param {Object} params - { workflow_id, page, size }
 * @returns {Promise<{total, list}>}
 */
export function getMaterials(params) {
  return api.get('/materials', { params })
}

/**
 * 查询单条素材详情（含 content 全文）
 * @param {number} id - 素材 ID
 */
export function getMaterialDetail(id) {
  return api.get(`/materials/${id}`)
}
