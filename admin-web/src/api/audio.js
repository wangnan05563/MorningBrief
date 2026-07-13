/**
 * 音频文件管理 API 封装
 *
 * 对应后端 /admin/api/v1/workflows/{id}/audio/* 路由
 * 音频流式播放需 JWT，用 axios 下载 blob 后创建 ObjectURL 供 <audio> 使用
 */
import api from '../api'

// 列出工作流的音频文件（TTS 片段 + 成品）
export const listAudioFiles = (workflowId) =>
  api.get(`/workflows/${workflowId}/audio`)

// 获取 TTS 音频 blob URL（供 <audio src> 播放）
export async function getTtsAudioUrl(workflowId, filename) {
  const res = await api.get(
    `/workflows/${workflowId}/audio/tts/${filename}`,
    { responseType: 'blob' },
  )
  return URL.createObjectURL(res)
}

// 获取成品音频 blob URL
export async function getEpisodeAudioUrl(workflowId) {
  const res = await api.get(
    `/workflows/${workflowId}/audio/episode`,
    { responseType: 'blob' },
  )
  return URL.createObjectURL(res)
}

// 删除单个 TTS 音频
export const deleteTtsAudio = (workflowId, filename) =>
  api.delete(`/workflows/${workflowId}/audio/tts/${filename}`)

// 删除成品音频
export const deleteEpisodeAudio = (workflowId) =>
  api.delete(`/workflows/${workflowId}/audio/episode`)
