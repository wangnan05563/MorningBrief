/**
 * 素材管理 API 封装（多输入渠道）
 *
 * 对应后端 /admin/api/v1/materials/* 与 /admin/api/v1/channels/* 路由。
 * 覆盖「有声读物 / 课程」素材的多渠道录入：
 *   - RSS（通用） / 书籍 RSS 预制源（audiobook）
 *   - 本地文件上传（list）
 *   - 云端存储导入 COS（cos）
 *   - 手动录入（list）
 *   - API / 网页 URL 拉取（api）
 *   - 二维码 / 链接分享（qrcode，/share 仅预览，正式入库走手动录入）
 */
import api from '../api'

// ===== 素材 CRUD =====
export const listMaterials = (params) => api.get('/materials', { params })
export const getMaterial = (id) => api.get(`/materials/${id}`)
export const createMaterial = (payload) => api.post('/materials', payload)
export const updateMaterial = (id, payload) => api.put(`/materials/${id}`, payload)
export const deleteMaterial = (id) => api.delete(`/materials/${id}`)
// 按书名（source）批量删除整本书的章节素材（T00895，素材库「按书聚合」视图用）
export const deleteMaterialsBySource = (source, channelId) =>
  api.delete('/materials', { params: { source, channel_id: channelId } })

// T02517（FR-UX-703 / C52）：一次事务内按素材 ID / 书名批量删除（素材库勾选批量删）
// payload: { ids?: number[], sources?: string[], channel_id?: number|null }，两者至少给一个
export const batchDeleteMaterials = (payload) => api.post('/materials/batch-delete', payload)

// ===== 多输入渠道 =====

// 本地文件上传：file 为 File 对象，channel_id / source / category 为表单字段
export const uploadMaterialFile = (file, { channelId, source = '文档上传', category = '' }) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('channel_id', channelId)
  formData.append('source', source)
  if (category) formData.append('category', category)
  return api.post('/materials/upload', formData, { timeout: 60000 })
}

// 云端存储导入（COS）：按对象 key 取回后解析为章节素材
export const importFromCos = (payload) => api.post('/materials/import-cos', payload)

// API / 网页 URL 拉取：source_type 默认 api，分享场景传 qrcode
export const importFromUrl = (payload) => api.post('/materials/import-url', payload)

// 二维码 / 链接分享预览（不直接入库，返回 title/content 供手动录入门户预填）
export const sharePreview = (payload) => api.post('/materials/share', payload)
