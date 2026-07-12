/**
 * 埋点模块（MVP 阶段）
 *
 * 设计原因：埋点调用点分散在各页面，若直接写 console.log 后续接入第三方
 * （如神策/友盟）需逐页修改。统一入口后，切换第三方 SDK 只需改本文件。
 *
 * 当前阶段仅输出到控制台，便于开发调试；上线前替换 sendToVendor 为真实上报。
 */

/**
 * 通用埋点：记录任意事件及其属性
 * @param {string} event - 事件名，如 'play_btn_click'
 * @param {Object} [properties] - 事件属性键值对
 */
function track(event, properties) {
  // 统一加 [tracker] 前缀，便于在控制台日志中过滤业务埋点
  console.log('[tracker]', event, properties || {});
}

/**
 * 页面浏览埋点：页面 onLoad/onShow 时调用
 * @param {string} pagePath - 页面路径，如 'pages/index/index'
 */
function trackPageView(pagePath) {
  track('page_view', { page_path: pagePath });
}

/**
 * 通用事件埋点：按 category/action/label/value 四段式记录交互
 * 采用四段式是为了与多数第三方分析平台字段命名对齐，降低迁移成本
 * @param {string} category - 事件类别，如 'player'
 * @param {string} action - 行为，如 'seek'
 * @param {string} [label] - 标签，如 'episode_123'
 * @param {number} [value] - 数值，如拖动到的秒数
 */
function trackEvent(category, action, label, value) {
  track('event', {
    category,
    action,
    label,
    value,
  });
}

module.exports = {
  track,
  trackPageView,
  trackEvent,
};
