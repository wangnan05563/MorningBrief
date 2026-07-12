/**
 * 关于我们：展示应用版本、功能、开发者与联系方式
 *
 * 版本号与构建日期从 globalData 读取，
 * 便于后续构建脚本统一注入，无需改动页面代码。
 */
const app = getApp();

Page({
  data: {
    version: '',
    buildDate: '',
    description: '用耳朵听新闻，让信息获取更轻松。',
    // 功能列表：图标 + 标题 + 描述，wxml 通过 wx:for 渲染
    features: [
      { icon: '📰', title: '每日要闻', desc: '精选每日重要新闻' },
      { icon: '🎙️', title: 'AI 播报', desc: '自然语音合成播报' },
      { icon: '⏱️', title: '断点续播', desc: '自动记录上次进度' },
      { icon: '⚡', title: '倍速播放', desc: '支持多种倍速切换' },
      { icon: '📥', title: '离线收听', desc: '下载后无网络也能听' },
    ],
    author: '20News 团队',
    contact: 'support@20news.example.com',
  },

  onLoad() {
    // 从全局数据读取版本信息，构建脚本注入时无需改页面
    const { version, buildDate } = app.globalData;
    this.setData({
      version: version || '1.0.0',
      buildDate: buildDate || '',
    });
  },

  /**
   * 复制邮箱到剪贴板：降低用户反馈门槛
   */
  onCopyContact() {
    wx.setClipboardData({
      data: this.data.contact,
      success: () => {
        wx.showToast({ title: '邮箱已复制', icon: 'success' });
      },
    });
  },
});
