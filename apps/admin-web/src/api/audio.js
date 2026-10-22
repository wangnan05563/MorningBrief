/**
 * 音频文件管理 API 封装
 *
 * 对应后端 /admin/api/v1/workflows/{id}/audio/* 路由
 * 音频流式播放需 JWT，下载 blob 后创建 ObjectURL 供 <audio> 使用
 *
 * 为什么用 fetch 而不是 axios：Chromium 把网络响应直接物化为 Blob 时（XHR blob /
 * res.blob()）有 10MB 内存缓冲上限，超出部分被截断并在恰好 10MiB 处报 net::ERR_FAILED，
 * axios 底层是 XHR，成品音频（10MB+）必现「Network Error」；
 * 因此这里读成 ArrayBuffer 再手动 new Blob()（内存构造不受此限，实测 14.4MB 完整）。
 * 同源请求 fetch 默认携带 HttpOnly Cookie（admin_token），鉴权行为与 axios 一致。
 */
import api from '../api'

// blob 下载超时：音频文件较大（成品可达 10MB+），全局 15s 不够，放宽到 60s
const BLOB_TIMEOUT_MS = 60000

const ERROR_NETWORK = '音频加载失败，请检查网络或服务状态后重试'
const ERROR_TIMEOUT = '音频下载超时，请重试'

/**
 * 下载音频并返回 blob URL
 * 网络层错误自动重试一次（重试仍失败给出友好提示）；
 * HTTP 错误响应解析后端 JSON 的 message 抛出（如 404「成品音频尚未生成」）
 */
async function fetchBlobUrl(path, params = null) {
  let url = `${api.defaults.baseURL}${path}`
  if (params) {
    url += `?${new URLSearchParams(params).toString()}`
  }

  const doFetch = () => fetch(url, { signal: AbortSignal.timeout(BLOB_TIMEOUT_MS) })

  let res
  try {
    res = await doFetch()
  } catch (e) {
    if (e.name === 'TimeoutError') throw new Error(ERROR_TIMEOUT)
    try {
      res = await doFetch()
    } catch {
      throw new Error(ERROR_NETWORK)
    }
  }

  if (!res.ok) {
    let message = '音频文件请求失败'
    try {
      message = (await res.json()).message || message
    } catch { /* 非 JSON 错误体，保留默认提示 */ }
    throw new Error(message)
  }

  // 不用 res.blob()：网络响应直转 Blob 同样命中 Chromium 的 10MB 上限，
  // 需先读入内存再手动构造，并带上原响应的 Content-Type 供 <audio> 识别
  const contentType = res.headers.get('content-type') || 'audio/mpeg'
  const blob = new Blob([await res.arrayBuffer()], { type: contentType })
  return URL.createObjectURL(blob)
}

// 列出工作流的音频文件（TTS 片段 + 成品）
export const listAudioFiles = (workflowId) =>
  api.get(`/workflows/${workflowId}/audio`)

// 代理播放远端（COS / CDN）音频：后端鉴权拉取后以 blob 回传，规避浏览器 CORS / 私有桶问题
// 打包态（COS 已配置）下 TTS 片段 / 成品仅存云端，本地 audio_cache 为空，必须走代理
export function getAudioProxyUrl(workflowId, remoteUrl) {
  return fetchBlobUrl(`/workflows/${workflowId}/audio/proxy`, { url: remoteUrl })
}

// 获取 TTS 音频 blob URL（供 <audio src> 播放）
// remoteUrl 非空时（打包态 COS 对象）走代理，否则走本地 audio_cache 端点
export function getTtsAudioUrl(workflowId, filename, remoteUrl = null) {
  return remoteUrl
    ? fetchBlobUrl(`/workflows/${workflowId}/audio/proxy`, { url: remoteUrl })
    : fetchBlobUrl(`/workflows/${workflowId}/audio/tts/${filename}`)
}

// 获取成品音频 blob URL
// 传入 remoteUrl 时（打包态 COS 对象）走代理，否则走本地 endpoint
export function getEpisodeAudioUrl(workflowId, remoteUrl = null) {
  return remoteUrl
    ? fetchBlobUrl(`/workflows/${workflowId}/audio/proxy`, { url: remoteUrl })
    : fetchBlobUrl(`/workflows/${workflowId}/audio/episode`)
}

// 删除单个 TTS 音频
export const deleteTtsAudio = (workflowId, filename) =>
  api.delete(`/workflows/${workflowId}/audio/tts/${filename}`)

// 删除成品音频
export const deleteEpisodeAudio = (workflowId) =>
  api.delete(`/workflows/${workflowId}/audio/episode`)
