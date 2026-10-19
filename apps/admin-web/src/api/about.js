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
 * @property {string} python - Python 版本（X.Y.Z）
 * @property {string} platform - 平台（windows/linux/darwin）
 * @property {string} repo_url - 代码仓库地址（REPO_URL）；空串表示未配置，
 *   关于页的项目类外链入口据此显隐（FR-UX-404）
 * @property {boolean} docs_enabled - 后端是否挂载了交互式 API 文档（仅 development）
 */

/**
 * 检查更新响应
 * @typedef {Object} UpdateCheckResult
 * @property {string} current - 当前版本
 * @property {string} latest - 最新版本
 * @property {boolean} has_update - 是否有更新
 * @property {string} release_url - Release 跳转 URL
 * @property {string} checked_at - 检查时间（ISO 8601）
 * @property {'local'|'remote'} source - 数据来源：local=未能确认（不等于无更新），remote=实际查询
 * @property {string} [published_at] - 发布时间（仅 source=remote 时）
 * @property {string} [reason] - 降级原因（仅 source=local 时）：repo_not_configured |
 *   no_release | rate_limited | network | bad_response
 * @property {string} [error] - 降级原因的用户可读文案（仅 source=local 时）
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

/**
 * 触发一键升级（桌面端：下载更新包并自动替换重启）
 * @returns {Promise<UpgradeState>}
 */
export function startUpgrade() {
  return api.post('/about/upgrade')
}

/**
 * 轮询升级进度
 * @returns {Promise<UpgradeState>}
 */
export function getUpgradeStatus() {
  return api.get('/about/upgrade/status')
}
