/**
 * 队列管理 API 封装
 *
 * 对应后端 /admin/api/v1/queue/* 路由
 * 复用全局 axios 实例（已注入 JWT + 解包响应）
 */
import api from '../api'

// 静默请求：轮询/统计类接口不弹错误提示，避免最小化时积压 ElMessage 激活窗口
export const getQueueStats = () => api.get('/queue/stats', { silent: true })
export const listQueueTasks = (params) => api.get('/queue/tasks', { params, silent: true })
export const cancelTask = (id) => api.post(`/queue/tasks/${id}/cancel`)
export const updatePriority = (id, priority) => api.put(`/queue/tasks/${id}/priority`, { priority })
export const retryTask = (id) => api.post(`/queue/tasks/${id}/retry`)
// 批量删除队列任务：委托后端 WorkflowService 事务级联删除（running/queued 拒绝）
export const batchDeleteTasks = (workflowIds) =>
  api.post('/queue/tasks/batch-delete', { workflow_ids: workflowIds })
export const getQueueConfig = () => api.get('/queue/config')
export const updateQueueConfig = (data) => api.put('/queue/config', data)
