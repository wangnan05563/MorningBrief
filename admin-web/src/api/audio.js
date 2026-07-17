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
 *
 * Network Error 处理：当 err.response 为 undefined（连接被重置/传输中断）时，
 * 浏览器 XHR onerror 返回固定文案 "Network Error"，需给出友好提示并自动重试一次
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

/**
 * 统一处理 blob 请求错误
 * - err.response.data 是 Blob：解析 JSON 错误消息（后端返回 404/500 等）
 * - err.response 为 undefined：网络层错误（连接重置/传输中断），自动重试一次
 * - 其他：透传原始错误
 */
async function handleBlobError(err, retryFn) {
  const blob = err.response?.data
  if (blob instanceof Blob) {
    const msg = await parseBlobError(blob)
    throw new Error(msg)
  }
  // err.response 为 undefined 表示网络层错误（未收到 HTTP 响应）
  // 浏览器 XHR onerror 固定返回 "Network Error"，需重试或给出友好提示
  if (!err.response) {
    if (retryFn) {
      // 自动重试一次：BaseHTTPMiddleware 对 FileResponse 的缓冲冲突可能导致连接重置
      return await retryFn()
    }
    throw new Error('音频加载失败，请检查网络或服务状态后重试')
  }
  throw err
}

// 列出工作流的音频文件（TTS 片段 + 成品）
export const listAudioFiles = (workflowId) =>
  api.get(`/workflows/${workflowId}/audio`)

// 获取 TTS 音频 blob URL（供 <audio src> 播放）
export async function getTtsAudioUrl(workflowId, filename) {
  const fetch = () => api.get(
    `/workflows/${workflowId}/audio/tts/${filename}`,
    BLOB_CONFIG,
  )
  try {
    const res = await fetch()
    return URL.createObjectURL(res)
  } catch (err) {
    // 网络层错误时重试一次，重试仍失败则由 handleBlobError 抛出友好提示
    return await handleBlobError(err, async () => {
      const res = await fetch()
      return URL.createObjectURL(res)
    })
  }
}

// 获取成品音频 blob URL
export async function getEpisodeAudioUrl(workflowId) {
  const fetch = () => api.get(
    `/workflows/${workflowId}/audio/episode`,
    BLOB_CONFIG,
  )
  try {
    const res = await fetch()
    return URL.createObjectURL(res)
  } catch (err) {
    // 成品音频较大（10MB+），BaseHTTPMiddleware 缓冲更易导致连接重置
    // 网络层错误时重试一次，重试仍失败则由 handleBlobError 抛出友好提示
    return await handleBlobError(err, async () => {
      const res = await fetch()
      return URL.createObjectURL(res)
    })
  }
}

// 删除单个 TTS 音频
export const deleteTtsAudio = (workflowId, filename) =>
  api.delete(`/workflows/${workflowId}/audio/tts/${filename}`)

// 删除成品音频
export const deleteEpisodeAudio = (workflowId) =>
  api.delete(`/workflows/${workflowId}/audio/episode`)
