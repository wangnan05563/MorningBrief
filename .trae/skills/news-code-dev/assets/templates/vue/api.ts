/**
 * {module} API 模块
 * 
 * 该模块封装了 {description} 相关的 API 调用。
 * 所有请求通过 axios 拦截器统一处理错误和认证。
 */
import request from '@/utils/request'
import type { XxxItem, XxxCreate, XxxUpdate, PaginatedResponse } from '@/types'

/**
 * 获取 {entity} 列表（分页）
 * @param params - 查询参数
 * @returns 分页响应
 */
export function getXxxList(params: {
  page: number
  page_size: number
  category?: string
  status?: string
}): Promise<PaginatedResponse<XxxItem>> {
  return request.get('/{module}/', { params })
}

/**
 * 获取 {entity} 详情
 * @param id - {entity} ID
 * @returns {entity} 数据
 */
export function getXxxDetail(id: number): Promise<XxxItem> {
  return request.get(`/{module}/${id}`)
}

/**
 * 创建 {entity}
 * @param data - {entity} 创建数据
 * @returns 创建结果
 */
export function createXxx(data: XxxCreate): Promise<XxxItem> {
  return request.post('/{module}/', data)
}

/**
 * 更新 {entity}
 * @param id - {entity} ID
 * @param data - 更新数据
 * @returns 更新结果
 */
export function updateXxx(id: number, data: XxxUpdate): Promise<XxxItem> {
  return request.put(`/{module}/${id}`, data)
}

/**
 * 删除 {entity}
 * @param id - {entity} ID
 * @returns 删除结果
 */
export function deleteXxx(id: number): Promise<void> {
  return request.delete(`/{module}/${id}`)
}
