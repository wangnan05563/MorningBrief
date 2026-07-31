/**
 * 全局配置中心：集中管理 COS、分页、音频、反馈等可调参数
 *
 * 设计原因：原 api.js 内硬编码 BASE_URL，audio/profile 等页面各自维护魔法数；
 * 修改时需多处查找。集中后仅需改此文件，降低漏改风险。
 *
 * 注意：API 基础地址已迁移至动态发现机制（utils/server-discovery.js），
 * 由 app.js onLaunch 调用 discoverServer() 注入 globalData.baseUrl，
 * 各模块通过 services/api.js 的 getBaseUrl() 读取，无需在此静态维护。
 *
 * 使用方式：const { CONFIG } = require('../utils/config'); 或通过 globalData.config 访问
 */

const CONFIG = {
  // COS 公开访问基础 URL：用于拼接图片/音频等静态资源公开访问地址
  // 当前项目尚未接入 COS，先用占位符，接入后替换为实际桶域名
  cosBaseUrl: 'https://cos.example.com',

  // 静态图片资源优化建议：
  // images/icons/ 下的图标当前使用 PNG 格式，体积偏大。
  // 推荐后续转换为 WebP（同等质量下体积可减少 30-50%，节省小程序包体积与首屏加载时间）。
  // 转换步骤：
  //   1. 用 cwebp 或在线工具将 .png 批量转为 .webp（保留原文件名仅改后缀）
  //   2. 同步更新所有 wxml 中 image 标签 src 的 .png 后缀为 .webp
  //   3. 小程序基础库 1.0.0+ 已默认支持 WebP，无需额外配置
  // 注意：当前仓库尚未提供 .webp 文件，故 wxml 中仍引用 .png，转换后再统一替换。

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