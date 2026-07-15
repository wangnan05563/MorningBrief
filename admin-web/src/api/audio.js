/**
 * 音频文件管理 API 封装
 *
 * 对应后端 /admin/api/v1/workflows/{id}/audio/* 路由
 * 音频流式播放需 JWT，用 axios 下载 blob 后创建 ObjectURL 供 <audio> 使用
 *
 * blob 请求需独立超时配置：音频文件较大（成品可达 10MB+），
 * 全局 15s timeout 对大文件下载不够，改为 60s
 *
 * blob 错误处理：后端返回 404/500 时 response.data 也是 Blob，
 * 需读取 Blob 文本解析 JSON 错误消息，否则前端只能显示 "Network Error"
 */
import api from '../api'

// blob 请求专用配置：长超时 + 静默错误（由调用方处理）
const BLOB_CONFIG = {
  responseType: 'blob',
  timeout: 60000,
  silent: true,
}

// 从 Blob 错误响应中解析 JSON 错误消息
// 后端返回 { code, message, data } 但 responseType='blob' 时 data 是 Blob
async function parseBlobError(blob) {
  try {
    const text = await blob.text()
    const json = JSON.parse(text)
    return json.message || '请求失败'
  } catch {
    return '音频文件请求失败'
  }
}

// 列出工作流的音频文件（TTS 片段 + 成品）
export const listAudioFiles = (workflowId) =>
  api.get(`/workflows/${workflowId}/audio`)

// 获取 TTS 音频 blob URL（供 <audio src> 播放）
export async function getTtsAudioUrl(workflowId, filename) {
  try {
    const res = await api.get(
      `/workflows/${workflowId}/audio/tts/${filename}`,
      BLOB_CONFIG,
    )
    return URL.createObjectURL(res)
  } catch (err) {
    // blob 响应的 error.response.data 是 Blob，需解析获取真实错误消息
    const blob = err.response?.data
    if (blob instanceof Blob) {
      const msg = await parseBlobError(blob)
      throw new Error(msg)
    }
    throw err
  }
}

// 获取成品音频 blob URL
export async function getEpisodeAudioUrl(workflowId) {
  try {
    const res = await api.get(
      `/workflows/${workflowId}/audio/episode`,
      BLOB_CONFIG,
    )
    return URL.createObjectURL(res)
  } catch (err) {
    const blob = err.response?.data
    if (blob instanceof Blob) {
      const msg = await parseBlobError(blob)
      throw new Error(msg)
    }
    throw err
  }
}

// 删除单个 TTS 音频
export const deleteTtsAudio = (workflowId, filename) =>
  api.delete(`/workflows/${workflowId}/audio/tts/${filename}`)

// 删除成品音频
export const deleteEpisodeAudio = (workflowId) =>
  api.delete(`/workflows/${workflowId}/audio/episode`)
