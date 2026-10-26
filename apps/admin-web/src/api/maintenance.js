/**
 * 系统清理 API 封装
 *
 * 对应后端 /admin/api/v1/maintenance/* 路由
 * 所有接口需 admin 角色
 */
import api from './index'
import { LONG_TASK_TIMEOUT_MS } from '../utils/requestTimeout'

/** 查询存储状态（数据库大小 / 日志文件 / 缓存占用） */
export function getStatus() {
  return api.get('/maintenance/status')
}

/**
 * 清理数据库旧数据或 VACUUM 压缩
 * @param {string} target - 清理目标：blacklist | dedup | ai_usage | playlog | vacuum
 * @param {number} days - 保留天数（0 用配置默认值）
 * @param {boolean} dryRun - 预览模式
 */
export function cleanupDatabase(target, days = 0, dryRun = false) {
  // 显式长超时：VACUUM / 批量 DELETE 是分钟级操作，沿用全局 15s 会在后端正常干活时
  // 先报「请求失败」，用户据此重复提交反而把写锁排队搞得更长（M62 / FR-UX-702）。
  return api.post(
    '/maintenance/database',
    { target, days, dry_run: dryRun },
    { timeout: LONG_TASK_TIMEOUT_MS },
  )
}

/**
 * 清理日志文件
 * @param {string} target - 清理目标：old_logs | large_logs
 * @param {number} days - 保留天数
 * @param {boolean} dryRun - 预览模式
 */
export function cleanupLogs(target, days = 7, dryRun = false) {
  // 同上：按大小清理（large_logs）可能扫到上百个文件，15s 不是合理上界
  return api.post(
    '/maintenance/logs',
    { target, days, dry_run: dryRun },
    { timeout: LONG_TASK_TIMEOUT_MS },
  )
}

/**
 * 清理缓存目录
 * @param {string} target - 清理目标：ttlcache | pycache | temp | all
 * @param {boolean} dryRun - 预览模式
 */
export function cleanupCache(target = 'pycache', dryRun = false) {
  return api.post(
    '/maintenance/cache',
    { target, dry_run: dryRun },
    { timeout: LONG_TASK_TIMEOUT_MS },
  )
}

/**
 * 查询清理任务状态（T02799）
 *
 * 非预览的清理改为后台任务：POST 立刻返回 task_id，进度从这里取。
 * 这是任务态轮询，替代的是原来那条挂 300s 的请求，不是「额外的轮询」。
 * @param {string} taskId - POST 返回的 task_id
 */
export function getMaintenanceTask(taskId) {
  return api.get(`/maintenance/tasks/${encodeURIComponent(taskId)}`)
}
