/**
 * 全局配置中心：集中管理 API、COS、分页、音频、反馈等可调参数
 *
 * 设计原因：原 api.js 内硬编码 BASE_URL，audio/profile 等页面各自维护魔法数；
 * 修改时需多处查找。集中后仅需改此文件，降低漏改风险。
 *
 * 使用方式：const { CONFIG } = require('../utils/config'); 或通过 globalData.config 访问
 */

// 按编译环境切换 API 域名：release 为正式版，其余走开发环境
// 与 api.js 中原逻辑保持一致，迁移后 api.js 可改为引用此处
const IS_RELEASE = typeof __wxConfig !== 'undefined' && __wxConfig.envVersion === 'release';

/**
 * 获取开发环境后端地址：自动检测本机局域网 IP
 * - 小程序运行时通过 wx.getSystemInfoSync().ip 获取设备/模拟器 IP
 * - 若 IP 无效则回退到 127.0.0.1
 */
function getDevApiBaseUrl() {
  if (typeof __wxConfig === 'undefined') return 'http://127.0.0.1:8000/api/v1';
  try {
    const sys = wx.getSystemInfoSync();
    const deviceIP = sys.ip || '';
    if (deviceIP && deviceIP !== '0.0.0.0' && deviceIP !== '127.0.0.1') {
      return 'http://' + deviceIP + ':8000/api/v1';
    }
  } catch (e) { /* ignore */ }
  return 'http://127.0.0.1:8000/api/v1';
}

const CONFIG = {
  // API 基础地址：与 api.js 中 BASE_URL 逻辑一致，便于后续 api.js 改为引用此处
  apiBaseUrl: IS_RELEASE
    ? 'https://api.example.com/api/v1'  // 生产环境域名（部署时替换）
    : getDevApiBaseUrl(),   // 开发环境（自动获取本机局域网 IP）
  
  // COS 公开访问基础 URL：用于拼接图片/音频等静态资源公开访问地址
  // 当前项目尚未接入 COS，先用占位符，接入后替换为实际桶域名
  cosBaseUrl: 'https://cos.example.com',

  // 分页默认大小：与 api.js fetchHistory 默认 size 保持一致
  defaultPageSize: 20,

  // 音频播放倍速配置：defaultRate 与全局播放器初始值倍速对齐
  audioConfig: {
    defaultRate: 1.0,
    rates: [0.75, 1.0, 1.25, 1.5, 2.0],
  },

  // 用户反馈配置：maxLength 与后端字段长度校验保持一致，避免提交后被拒
  feedbackConfig: {
    maxLength: 500,
    categories: ['内容错误', '播放问题', '功能建议', '其他'],
  },
};

module.exports = {
  CONFIG,
};