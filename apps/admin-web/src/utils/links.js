/**
 * 对外链接的单一来源（FR-UX-404 / M101）
 *
 * 为什么集中在此：曾经把这些地址硬编码在 About.vue 里，其中 5 条是
 * example.com 占位符——占位符会原样出厂，用户点开的是与自己无关的保留域名。
 * 现在项目类链接一律由后端 /about 下发的 repo_url 拼装：
 * 未配置仓库时前端直接隐藏这些入口，而不是留一个假地址。
 */

// 交互式 API 文档路径：dev 经 Vite 代理去掉 /news 前缀打到后端 /docs；
// 生产 Funnel 只路由 /news/*，而后端仅在 development 挂载 docs_url，
// 因此入口显隐由 /about 的 docs_enabled 决定（见 About.vue）。
export const API_DOCS_PATH = '/news/docs'

/**
 * 由仓库地址派生项目类外链。
 * @param {string} repoUrl 后端下发的 REPO_URL（形如 https://github.com/owner/repo）
 * @returns {Array<{key: string, label: string, href: string, external: boolean}>}
 */
export function buildRepoLinks(repoUrl) {
  if (!repoUrl) return []
  const base = String(repoUrl).trim().replace(/\/+$/, '')
  if (!/^https?:\/\//i.test(base)) return []
  return [
    { key: 'repo', label: '项目主页', href: base, external: true },
    { key: 'releases', label: '版本发布', href: `${base}/releases`, external: true },
    // 指向 issue 列表而非 /issues/new：新建 issue 需要登录，未登录时这里
    // 会跳到 GitHub 的登录页，反而是「打不开就让我登录」的死链体验。
    { key: 'report', label: '报告问题', href: `${base}/issues`, external: true },
  ]
}
