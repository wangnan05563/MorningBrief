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
 */
export const triggerWorkflow = (channelId) =>
  api.post('/workflows/trigger', channelId ? { channel_id: channelId } : {})

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
