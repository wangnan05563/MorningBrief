/**
 * 讲书稿模式与素材池 API 封装（T00656）
 *
 * 对应后端 /admin/api/v1/channels/{id}/script-mode 与 /book-pool/*
 */
import api from '../api'

/** 模式状态（开关 + 进度 + 池量 + 当前书源） */
export const getScriptMode = (channelId) => api.get(`/channels/${channelId}/script-mode`)

/** 切换讲书稿模式（幂等；开启时后端快照并清空频道书源，关闭时按快照恢复） */
export const setScriptMode = (channelId, enabled) =>
  api.put(`/channels/${channelId}/script-mode`, { enabled })

/** 取书调度：间隔天数（每日/每 N 天）+ 末尾是否循环 */
export const updateBookPoolSchedule = (channelId, data) =>
  api.put(`/channels/${channelId}/script-mode/schedule`, data)

/** 池列表（按取书顺序）+ 进度 */
export const listBookPool = (channelId) => api.get(`/channels/${channelId}/book-pool`)

/** 加入书籍（按书为单位：book_sources＝书名/素材 source，末尾追加，幂等） */
export const addBooksToPool = (channelId, bookSources) =>
  api.post(`/channels/${channelId}/book-pool/items`, { book_sources: bookSources })

/** 移出池 */
export const removeBookFromPool = (channelId, itemId) =>
  api.delete(`/channels/${channelId}/book-pool/items/${itemId}`)

/** 上移/下移一格（direction: 'up' | 'down'） */
export const moveBookInPool = (channelId, itemId, direction) =>
  api.post(`/channels/${channelId}/book-pool/items/${itemId}/move`, null, { params: { direction } })

/** 批量重排（前端拖拽/整体排序后保存） */
export const reorderBookPool = (channelId, itemIds) =>
  api.put(`/channels/${channelId}/book-pool/order`, { item_ids: itemIds })

/** 重置进度（从头开始取书） */
export const resetBookPoolProgress = (channelId) =>
  api.post(`/channels/${channelId}/book-pool/progress/reset`)

/** 可选书候选（来自素材库） */
export const listBookCandidates = (channelId, params) =>
  api.get(`/channels/${channelId}/book-pool/candidates`, { params })

/** 预览下一次将生成哪本书（只读） */
export const previewNextBook = (channelId) =>
  api.post(`/channels/${channelId}/book-pool/pick-preview`)
