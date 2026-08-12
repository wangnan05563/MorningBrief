/**
 * 客户端告警上报器（FR-MC-12 后续增强）
 *
 * 解决的问题：skin.normalizeType 等位置检测到「未知 channel_type」等异常时，
 * 仅 console.warn 在真机不可见，运维无法集中发现「后端误下发未知类型」。
 * 本模块将此类告警以 best-effort 方式上报到后端 /api/v1/client/report，
 * 后端集中记录日志，便于监控告警。
 *
 * 设计原则：
 * - 配置化：端点 / 开关 / 节流窗口均集中在 REPORTER_CONFIG，不硬编码散落。
 * - fire-and-forget：失败静默吞掉，绝不影响端上任何 UI / 业务流程。
 * - 节流：同一 (category+message) 在 throttleMs 内仅上报一次，避免刷屏。
 * - 不依赖 api.js（避免循环依赖 api→skin→report→api），baseUrl 自行解析，
 *   与 api.js 的 getBaseUrl 口径一致（release 用 PROD_API_BASE_URL，否则用
 *   globalData.baseUrl，兜底 localhost）。
 */

const { PROD_API_BASE_URL, isRelease } = require('../utils/server-discovery');

const REPORTER_CONFIG = {
  // 默认开启；dev 下 throttleMs 已压住频次，且 best-effort 不影响 UX
  enabled: true,
  // 相对 /api/v1 的路径；完整 URL = resolveBaseUrl() + endpoint
  endpoint: '/client/report',
  // 节流窗口：同一 (category+message) 10 分钟内仅上报一次
  throttleMs: 10 * 60 * 1000,
};

// 节流表：key=(category␀message) -> 上次发送时间戳
const _lastSent = Object.create(null);
const _KEY_SEP = '␀';

function configureReporter(opts) {
  if (opts && typeof opts === 'object') {
    Object.assign(REPORTER_CONFIG, opts);
  }
}

function resolveBaseUrl() {
  if (isRelease() && PROD_API_BASE_URL) return PROD_API_BASE_URL;
  const app = (typeof getApp === 'function') ? getApp() : null;
  if (app && app.globalData && app.globalData.baseUrl) {
    return app.globalData.baseUrl;
  }
  return 'http://127.0.0.1:8000/api/v1';
}

function reportClientWarn(category, message, payload) {
  if (!REPORTER_CONFIG.enabled) return;
  if (!category || !message) return;
  const key = category + _KEY_SEP + message;
  const now = Date.now();
  const last = _lastSent[key] || 0;
  if (now - last < REPORTER_CONFIG.throttleMs) return; // 节流：窗口内跳过
  _lastSent[key] = now; // 先占位，避免失败重试期间刷屏
  try {
    const url = resolveBaseUrl() + REPORTER_CONFIG.endpoint;
    wx.request({
      url,
      method: 'POST',
      timeout: 8000,
      header: { 'content-type': 'application/json' },
      data: {
        category,
        message,
        payload: payload || null,
        client_ts: now,
      },
      // 完全 fire-and-forget：成败都不影响端上逻辑
    });
  } catch (e) {
    // 静默：上报失败绝不抛到业务层
  }
}

module.exports = {
  reportClientWarn,
  configureReporter,
  resolveBaseUrl,
  REPORTER_CONFIG,
};
