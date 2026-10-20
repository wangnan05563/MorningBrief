/**
 * 埋点模块（MVP 阶段）
 *
 * 设计原因：埋点调用点分散在各页面，若直接写 console.log 后续接入第三方
 * （如神策/友盟）需逐页修改。统一入口后，切换第三方 SDK 只需改本文件。
 *
 * 当前阶段仅输出到控制台，便于开发调试；上线前替换 sendToVendor 为真实上报。
 *
 * T02513 / J99：本文件是全站唯一的「使用记录」出口，所以「关闭数据收集」这个承诺
 * 只有挂在这里才成立。隐私政策原先写「关闭某些数据收集（在设置中操作）」，而设置页
 * 根本没有该开关（承诺指向一个不存在的控件）；现在设置页 →「数据与统计」提供开关，
 * 并由下面的 isEnabled() 短路所有事件。
 * 诚实边界：现阶段事件并不出网（只落控制台），开关关掉的实际效果是
 * 「本机不再产生使用记录」——这句话也照原样写进了隐私政策，不夸大成「阻止上传」。
 */
const { STORAGE_KEY_SETTINGS } = require('../services/constants');

/** null = 尚未读过设置；设置页变更时由 setTrackingEnabled 直接覆写，避免每次事件都读 storage */
let _enabled = null;

function _readFromSettings() {
  try {
    const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
    // 缺省视为开启：老用户没有 usageTracking 字段时不应静默关掉统计
    return saved.usageTracking !== false;
  } catch (err) {
    return true;
  }
}

/** 当前是否记录使用事件（设置页开关的读取口径） */
function isEnabled() {
  if (_enabled === null) _enabled = _readFromSettings();
  return _enabled;
}

/** 设置页切换开关时调用：让开关立即生效，不必等下一次冷启动重读 storage */
function setTrackingEnabled(value) {
  _enabled = !!value;
}

/**
 * 通用埋点：记录任意事件及其属性
 * @param {string} event - 事件名，如 'play_btn_click'
 * @param {Object} [properties] - 事件属性键值对
 */
function track(event, properties) {
  if (!isEnabled()) return;
  // 统一加 [tracker] 前缀，便于在控制台日志中过滤业务埋点
  console.warn('[tracker]', event, properties || {});
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
  isEnabled,
  setTrackingEnabled,
};
