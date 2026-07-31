/**
 * 关于我们：展示应用版本、功能、开发者与联系方式
 *
 * 版本号与构建日期从 globalData 读取，
 * 便于后续构建脚本统一注入，无需改动页面代码。
 *
 * 隐藏入口：连续点击版本号 5 次（1.5s 内）触发后端地址手动配置。
 * 用于自动探测失败时的兜底（如设备与后端不在同一网段、网段候选未覆盖等）。
 */
const app = getApp();
const { trackPageView, trackEvent } = require('../../utils/tracker');
const { getManualBaseUrl, setManualBaseUrl, normalizeBaseUrl } = require('../../utils/server-discovery');

// 版本号连点触发手动配置的阈值与时间窗口
const TAP_THRESHOLD = 5;
const TAP_RESET_MS = 1500;

Page({
  data: {
    version: '',
    buildDate: '',
    description: '用耳朵听新闻，让信息获取更轻松。',
    // 功能列表：图标 + 标题 + 描述，wxml 通过 wx:for 渲染
    // 图标使用 PNG 资源（来自 Tabler Icons 开源库），避免 emoji 跨平台渲染不一致
    features: [
      { icon: '/images/icons/newspaper.png', title: '每日要闻', desc: '精选每日重要新闻' },
      { icon: '/images/icons/headphones.png', title: 'AI 播报', desc: '自然语音合成播报' },
      { icon: '/images/icons/duration.png', title: '断点续播', desc: '自动记录上次进度' },
      { icon: '/images/icons/play.png', title: '倍速播放', desc: '支持多种倍速切换' },
      { icon: '/images/icons/play-mini.png', title: '离线收听', desc: '下载后无网络也能听' },
    ],
    author: 'MorningBrief 团队',
    contact: 'support@MorningBrief.example.com',
    currentServerUrl: '',  // 当前生效的后端地址（展示用）
  },

  // 版本号点击计数器（非响应式，无需放入 data）
  _versionTapCount: 0,
  _versionTapTimer: null,

  onLoad() {
    trackPageView('pages/about/about');
    // 从全局数据读取版本信息，构建脚本注入时无需改页面
    const { version, buildDate } = app.globalData;
    this.setData({
      version: version || '1.0.0',
      buildDate: buildDate || '',
      // 展示当前后端地址：优先手动配置，其次自动发现的 globalData.baseUrl
      currentServerUrl: getManualBaseUrl() || app.globalData.baseUrl || '(未配置)',
    });
  },

  /**
   * 版本号点击：连点 5 次触发后端地址手动配置
   * 用于自动探测失效时的兜底（如设备与后端跨网段、候选未覆盖等）
   */
  onVersionTap() {
    this._versionTapCount += 1;
    if (this._versionTapTimer) clearTimeout(this._versionTapTimer);
    this._versionTapTimer = setTimeout(() => {
      this._versionTapCount = 0;
    }, TAP_RESET_MS);

    if (this._versionTapCount >= TAP_THRESHOLD) {
      this._versionTapCount = 0;
      this._versionTapTimer = null;
      this.showServerUrlEditor();
    }
  },

  /**
   * 弹出手动配置后端地址的输入框
   * 接受多种格式：192.168.1.65:8000 / http://192.168.1.65:8000 / http://192.168.1.65:8000/api/v1
   * 由 normalizeBaseUrl 统一规范化
   */
  showServerUrlEditor() {
    const current = getManualBaseUrl() || app.globalData.baseUrl || '';
    wx.showModal({
      title: '配置后端地址',
      content: '自动探测失败时使用。留空则恢复自动探测。\n格式：192.168.1.65:8000',
      editable: true,
      placeholderText: current || 'http://192.168.x.x:8000',
      confirmText: '保存',
      confirmColor: '#FF6B8A',
      success: (res) => {
        if (!res.confirm) return;
        const input = (res.content || '').trim();
        if (!input) {
          // 留空：清除手动配置，恢复自动探测
          setManualBaseUrl('');
          wx.showToast({ title: '已恢复自动探测，请重启小程序', icon: 'none', duration: 2000 });
          trackEvent('about', 'server_url_reset');
          return;
        }
        const normalized = normalizeBaseUrl(input);
        setManualBaseUrl(normalized);
        wx.showToast({ title: '已保存，请重启小程序生效', icon: 'none', duration: 2000 });
        trackEvent('about', 'server_url_manual_set');
      },
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
        trackEvent('about', 'copy_contact');
      },
    });
  },
});
