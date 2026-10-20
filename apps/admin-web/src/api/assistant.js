/**
 * 智能助手 API 封装
 *
 * 对应后端 /admin/api/v1/assistant/* 路由。
 * 复用全局 axios 实例（已注入 JWT + 解包响应）。
 *
 * 定位：把管理员的自然语言调度指令解析为系统菜单可执行的动作草稿，
 * 管理员在会话内确认后再落地（本次先支持「新增频道」闭环）。
 */
import api from '../api'
import { AI_CHAT_TIMEOUT_MS } from './aiChat'

/** 获取可调度动作注册表（字段 schema），供前端动态渲染确认表单 */
export const listAssistantActions = () => api.get('/assistant/actions')

/**
 * 解析用户的自然语言调度指令为动作草稿
 * @param {string} message 用户指令，如「帮我新增一个 AI 咨询频道」
 * @param {string} model 可选，指定使用的模型
 */
export const planAssistantAction = (message, model = '') =>
  // T02515 顺带纠口径：/assistant/plan 在服务层走的是同一个 chat_with_model，
  // 该函数现在的超时是 LLM_CHAT_TIMEOUT_SEC=120s。原来这里写 120000 与后端相等，
  // 两边同时到点时谁先判失败不确定；问答那对契约要求「后端先到点」，
  // 所以这里复用 AI_CHAT_TIMEOUT_MS（130s），让失败永远以服务端那句可读提示呈现。
  api.post('/assistant/plan', { message, model }, { timeout: AI_CHAT_TIMEOUT_MS })

/**
 * 落地一个经管理员确认的动作草稿
 * @param {string} actionId 动作标识，如 create_channel
 * @param {object} fields 字段 key:value 字典
 */
export const executeAssistantAction = (actionId, fields) =>
  api.post('/assistant/execute', { action_id: actionId, fields }, { timeout: AI_CHAT_TIMEOUT_MS })