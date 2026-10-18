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

// ===== T00730 频道图标：上传 / AI 生成 =====
export const uploadChannelIcon = (id, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/channels/${id}/icon`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const generateChannelIcon = (id, prompt) =>
  api.post(`/channels/${id}/icon/ai-generate`, { prompt }, { timeout: 180000 })

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

/** 列出 book_rss.yaml 中所有可用的书籍 RSS 预制源，供 audiobook 频道配置选择 */
export const listBookRssSources = () => api.get('/channels/book-rss/sources')

/**
 * AI 推荐频道 RSS 源与关键词（根据频道定位从可用源中选择最匹配的子集 + 生成关键词）
 * LLM 推荐耗时与 BGM 推荐相当，超时设为 60s 与 recommendChannelBgm 保持一致
 */
export const recommendChannelSources = (id) => api.post(`/channels/${id}/recommend-sources`, {}, { timeout: 60000 })

// ===== T00731 预制频道封面 =====

/**
 * 列出服务端预制封面（/channel-assets 下的 channel_{id}.{jpg|png|webp}）
 * 供「编辑频道」页直接选图，避免手输 URL
 * @returns {Promise<Array<{channel_id:number,name:string,url:string,size_kb:number,mtime:number}>>} mtime=文件修改时间（秒），供缩略图加 ?v= 版本号
 */
export const listCoverPresets = () => api.get('/channels/cover-presets')

// 删除影响面预览（T02490 / FR-UX-202 C10）：确认框必须给出真实连带后果
// silent 由调用方决定：页面 catch 会弹「无法获取删除影响面预览，已禁止删除：xxx」
// 这种带后果说明的完整文案，若此处不静默，拦截器会再弹一条原文造成二次提示（FR-UX-303）
export const deleteChannelPreview = (id, config) => api.get(`/channels/${id}/delete-preview`, config)
