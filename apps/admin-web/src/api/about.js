/**
 * 关于页面 API 封装
 *
 * 对应后端 /admin/api/v1/about/* 路由
 * 所有接口需 admin 角色（axios 拦截器自动注入 Bearer token）
 */
import api from './index'

/**
 * 系统元信息响应
 * @typedef {Object} AboutInfo
 * @property {string} product - 产品名
 * @property {string} version - 版本号
 * @property {string} build_date - 构建日期（YYYY-MM-DD）
 * @property {string} git_sha - Git 短 SHA
 * @property {string} python - Python 版本
 * @property {string} platform - 平台（windows/linux/darwin）
 */

/**
 * 检查更新响应
 * @typedef {Object} UpdateCheckResult
 * @property {string} current - 当前版本
 * @property {string} latest - 最新版本
 * @property {boolean} has_update - 是否有更新
 * @property {string} release_url - Release 跳转 URL
 * @property {string} checked_at - 检查时间（ISO 8601）
 * @property {'local'|'remote'} source - 数据来源：local=降级，remote=实际查询
 * @property {string} [published_at] - 发布时间（仅 source=remote 时）
 * @property {string} [error] - 失败诊断信息（仅 source=local 时）
 */

/**
 * 获取系统元信息
 * @returns {Promise<AboutInfo>}
 */
export function getAbout() {
  return api.get('/about')
}

/**
 * 检查更新
 * @returns {Promise<UpdateCheckResult>}
 */
export function checkUpdate() {
  return api.get('/about/check-update')
}
