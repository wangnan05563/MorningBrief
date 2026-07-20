/**
 * 全局配置中心：集中管理 API、COS、分页、音频、反馈等可调参数
 *
 * 设计原因：原 api.js 内硬编码 BASE_URL，audio/profile 等页面各自维护魔法数；
 * 修改时需多处查找。集中后仅需改此文件，降低漏改风险。
 *
 * 使用方式：const { CONFIG } = require('../utils/config'); 或通过 globalData.config 访问
 */

// 引用 api.js 的 BASE_URL，避免两处重复维护开发环境地址
// 真机调试时改 api.js 一处即可，此处自动同步
const { BASE_URL } = require('../services/api');

const CONFIG = {
  // API 基础地址：直接引用 api.js 的 BASE_URL，避免双源维护漂移
  apiBaseUrl: BASE_URL,

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