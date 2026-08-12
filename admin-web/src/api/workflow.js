/**
 * 工作流 API 封装
 *
 * 对应后端 /admin/api/v1/workflows/* 路由
 * 复用全局 axios 实例（已注入 JWT + 解包响应）
 */
import api from '../api'

/**
 * 手动触发单个频道工作流
 * @param {number|null} channelId 频道 ID，为空时使用默认提示词
 * @param {object} [options]
 * @param {boolean} [options.skipCrawl=false] 跳过爬虫：文档/手动选题场景素材已入库，
 *        工作流从 rewrite 开始（跳过 crawl 步骤）。课程/资料类频道手动触发须开启。
 * @param {string} [options.episodeDate] 节目日期 YYYY-MM-DD，默认今天
 */
export const triggerWorkflow = (channelId, options = {}) => {
  const payload = {}
  if (channelId) payload.channel_id = channelId
  if (options.skipCrawl) payload.skip_crawl = true
  if (options.episodeDate) payload.episode_date = options.episodeDate
  return api.post('/workflows/trigger', payload)
}

/**
 * 全频道触发工作流
 *
 * 后端并发触发所有活跃频道，跳过当日已有运行中工作流的频道。
 * trigger_workflow 仅入队不执行实际工作流，通常 1-3s 内返回。
 * timeout 设为 60s 作为安全余量，覆盖频道数量较多时的并发开销。
 *
 * @returns {Promise<{total: number, triggered: Array, skipped: Array, failed: Array}>}
 */
export const triggerAllWorkflows = () =>
  api.post('/workflows/trigger-all', {}, { timeout: 60000 })
