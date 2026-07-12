/**
 * 系统状态 API 封装
 *
 * 对应后端 /admin/api/v1/system/* 路由
 * 所有接口需 admin 角色（axios 拦截器自动注入 Bearer token）
 */
import api from './index'

/**
 * 检测 ffmpeg/ffprobe 可用性
 * @returns {Promise<{available: boolean, ffmpeg_path: string, ffprobe_path: string, version: string, error: string}>}
 */
export function getFFmpegStatus() {
  return api.get('/system/ffmpeg-status')
}

/**
 * 下载安装 ffmpeg/ffprobe（耗时操作）
 *
 * 下载约 30MB + GitHub CDN 跳转，默认 15s 超时不够，
 * 单独放宽到 10 分钟避免安装中途被 axios 截断。
 * @returns {Promise<Object>} check_ffmpeg 结果 + install_message
 */
export function installFFmpeg() {
  return api.post('/system/ffmpeg-install', {}, { timeout: 600000 })
}
