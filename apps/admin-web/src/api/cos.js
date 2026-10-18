/**
 * 云端 COS 配置与管理 API 封装
 *
 * 对应后端 /admin/api/v1/cos/* 路由（已在 main.py 挂载 b_cos_router）
 * 所有接口需管理员权限，401/403 由全局拦截器统一处理。
 *
 * 设计要点：
 * - GET /cos/status 无需 DB，前端管理页进入时快速判断「是否已配置」
 * - PUT /cos/config 的 secret_id/secret_key 若传脱敏值（**** 开头）视为未修改
 * - POST /cos/upload 用 multipart/form-data（file + prefix 表单字段）
 */
import api from '../api'

// 获取 COS 配置（SecretId/SecretKey 脱敏）
export const getCosConfig = () => api.get('/cos/config')

// 保存 COS 配置（热更新 Settings + 重置客户端缓存）
export const saveCosConfig = (payload) => api.put('/cos/config', payload)

// 测试 COS 连接（列举桶根验证凭证与 Bucket 可达性）
export const testCosConnection = () => api.post('/cos/test-connection')

// COS 配置就绪状态（前端管理页快速判断，无需 DB）
export const getCosStatus = () => api.get('/cos/status')

// 列举某前缀下的目录与文件（模拟目录树）
export const listCosObjects = (prefix = '') =>
  api.get('/cos/objects', { params: { prefix } })

// 上传文件（multipart）：file 为 File 对象，prefix 为目标目录（以 / 结尾）
// overwrite=false 时后端对同名对象返回业务码 409（拒绝静默覆盖，FR-UX-205）
export const uploadCosFile = (file, prefix = '', { overwrite = false } = {}) => {
  const formData = new FormData()
  formData.append('file', file)
  if (prefix) formData.append('prefix', prefix)
  formData.append('overwrite', overwrite ? 'true' : 'false')
  return api.post('/cos/upload', formData, {
    timeout: 60000,
  })
}

// 对象存在性检查（上传/移动前的同名检测）
// silent：检测失败由调用方给出「已取消上传」的针对性提示，避免拦截器二次弹错
export const checkCosObject = (key) =>
  api.get('/cos/exists', { params: { key }, silent: true })

// 获取对象下载地址（CDN 直链优先，否则预签名）
export const getCosDownloadUrl = (key, expired = 300) =>
  api.get('/cos/download', { params: { key, expired } })

// 删除单个对象
export const deleteCosObject = (key) =>
  api.delete('/cos/object', { params: { key } })

// 新建文件夹（上传占位对象）
export const createCosFolder = (prefix) =>
  api.post('/cos/folder', { prefix })

// 删除文件夹（递归删除前缀下所有对象）
export const deleteCosFolder = (prefix) =>
  api.delete('/cos/folder', { params: { prefix } })

// 重命名 / 移动对象或文件夹（source_key 以 / 结尾视为文件夹）
export const moveCosObject = (sourceKey, destKey) =>
  api.post('/cos/move', { source_key: sourceKey, dest_key: destKey })

// 获取对象元数据（大小 / 最后修改 / 类型 / ETag）
export const getCosMetadata = (key) =>
  api.get('/cos/metadata', { params: { key } })
