/**
 * 稿件 API 封装
 *
 * 对应后端 /admin/api/v1/scripts/* 路由
 * 供工作流产物查看使用，需 B 端 admin 鉴权
 */
import api from './index'

/**
 * 按 script_id 查询稿件详情
 * @param {number} id - 稿件 ID
 */
export function getScript(id) {
  return api.get(`/scripts/${id}`)
}

/**
 * 按 workflow_id 查询稿件（一个工作流只有一份稿件）
 * @param {string} workflowId - 工作流 ID
 */
export function getScriptByWorkflow(workflowId) {
  return api.get('/scripts', { params: { workflow_id: workflowId } })
}

/**
 * 手动编辑稿件分段（覆盖写入）
 *
 * 传入完整 segments 数组，后端重排 seq、重算 full_text/total_words/estimated_duration。
 * 仅 draft 状态稿件可编辑；敏感词命中返回 warning 但仍保存。
 * @param {number} scriptId - 稿件 ID
 * @param {Array<{title: string, content: string, material_ids?: number[]}>} segments - 完整分段列表
 * @returns {Promise<Object>} 更新后的稿件 + sensitive_warning
 */
export function updateScriptSegments(scriptId, segments) {
  return api.put(`/scripts/${scriptId}/segments`, { segments })
}

