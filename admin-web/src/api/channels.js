/**
 * 频道管理 API 封装
 *
 * 对应后端 /admin/api/v1/channels/* 路由
 * 复用全局 axios 实例（已注入 JWT + 解包响应）
 */
import api from '../api'

export const listChannels = (activeOnly) => api.get('/channels', { params: { active_only: activeOnly } })
export const createChannel = (data) => api.post('/channels', data)
export const updateChannel = (id, data) => api.put(`/channels/${id}`, data)
export const deleteChannel = (id) => api.delete(`/channels/${id}`)

/**
 * AI 自动生成频道提示词
 * 调用 LLM 根据频道 name + description 生成 intro/outro/constraint/template
 * LLM 生成耗时较长，超时设为 120s（覆盖后端 LLM_TIMEOUT_SEC 默认 30s + 重试时间）
 */
export const generateChannelPrompts = (id) => api.post(`/channels/${id}/generate-prompts`, {}, { timeout: 120000 })

// ===== BGM 管理 =====

/** 列出所有可用 BGM 文件（预制 + 用户上传） */
export const listBgmFiles = () => api.get('/channels/bgm/list')

/**
 * 上传 BGM 文件
 * @param {File} file 音频文件（mp3/wav/m4a/aac/ogg）
 * @param {(percent: number) => void} onProgress 上传进度回调
 */
export const uploadBgmFile = (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/channels/bgm/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
}

/** 删除自定义 BGM 文件（仅允许删除 custom/ 下的） */
export const deleteBgmFile = (path) => api.delete(`/channels/bgm/${path}`)

/** AI 推荐频道 BGM（根据频道定位从可用列表中选择最匹配的） */
export const recommendChannelBgm = (id) => api.post(`/channels/${id}/recommend-bgm`, {}, { timeout: 60000 })

// ===== RSS 源管理 =====

/** 列出 rss.yaml 中所有可用的 RSS 源，供频道配置选择 */
export const listRssSources = () => api.get('/channels/rss/sources')
