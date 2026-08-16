/**
 * 系统清理 API 封装
 *
 * 对应后端 /admin/api/v1/maintenance/* 路由
 * 所有接口需 admin 角色
 */
import api from './index'

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
  return api.post('/maintenance/database', {
    target,
    days,
    dry_run: dryRun,
  })
}

/**
 * 清理日志文件
 * @param {string} target - 清理目标：old_logs | large_logs
 * @param {number} days - 保留天数
 * @param {boolean} dryRun - 预览模式
 */
export function cleanupLogs(target, days = 7, dryRun = false) {
  return api.post('/maintenance/logs', {
    target,
    days,
    dry_run: dryRun,
  })
}

/**
 * 清理缓存目录
 * @param {string} target - 清理目标：ttlcache | pycache | temp | all
 * @param {boolean} dryRun - 预览模式
 */
export function cleanupCache(target = 'pycache', dryRun = false) {
  return api.post('/maintenance/cache', {
    target,
    dry_run: dryRun,
  })
}
