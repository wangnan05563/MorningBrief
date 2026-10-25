/**
 * 移动端审核详情「语音内容」的播放源判定（B12 / T02757）。
 *
 * 真实库里 review.audio_url 有两种形态（81 条审核记录实测：33 条 COS 绝对地址、48 条 /audio/... 相对路径）：
 * - 绝对 http(s)：COS 私有桶 + 浏览器 CORS，直接塞进 <audio src> 只会 403/静默失败，
 *   必须走后端 /workflows/{id}/audio/proxy（JWT 由后端持有凭证拉取）；
 * - 相对 /audio/...：后端静态挂载目录里的成品音频，同源可直接播，不必也不该走代理；
 * - 只有 hls_url（m3u8）：桌面 Chrome 的 <audio> 不支持 HLS，塞进去就是一条永远不响的音轨。
 *
 * 返回 { mode, url }：mode 为 remote / local / hls / none。
 */
const ABSOLUTE_URL = /^(https?:)?\/\//i

export function resolveReviewAudio(detail) {
  const audioUrl = typeof detail?.audio_url === 'string' ? detail.audio_url.trim() : ''
  if (ABSOLUTE_URL.test(audioUrl)) {
    // 协议相对地址（//host/path）补成 https，proxy 只接受绝对 http(s) URL
    return { mode: 'remote', url: audioUrl.startsWith('//') ? `https:${audioUrl}` : audioUrl }
  }
  if (audioUrl.startsWith('/')) {
    return { mode: 'local', url: audioUrl }
  }
  if (detail?.hls_url) return { mode: 'hls', url: '' }
  return { mode: 'none', url: '' }
}
