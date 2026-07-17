/**
 * 个人中心：用户信息 + 收听统计 + 功能入口
 *
 * V1.3：
 * - 接入 /users/stats 接口获取真实收听统计（累计时长/期数/完播数/收藏数）
 * - 新增"最近播放"、"我的收藏"、"我的频道"、"意见反馈"等功能入口
 * - 接入埋点（FR-SUP-10）
 */
const { logout, getUser, login } = require('../../services/auth');
const { fetchUserStats } = require('../../services/api');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    userInfo: null,
    totalListenDuration: 0,   // 累计收听秒数
    totalListenCount: 0,      // 累计收听期数
    completedCount: 0,        // 完播期数
    favoriteCount: 0,         // 收藏数
    durationLabel: '0分钟',   // 格式化后的收听时长
  },

  onShow() {
    trackPageView('pages/profile/profile');
    // 每次展示都刷新，确保登录态/统计为最新
    const app = getApp();
    const userInfo = app.globalData.userInfo || getUser();
    this.setData({ userInfo });

    if (userInfo) {
      this.loadStats();
    }
  },

  /**
   * 从后端加载用户统计
   * 接口失败时回退到 globalData 兜底，避免页面空白
   */
  async loadStats() {
    try {
      const stats = await fetchUserStats();
      if (!stats) {
        // 接口失败或未登录：兜底读 globalData
        const app = getApp();
        const localStats = app.globalData.listenStats || {};
        this.applyStats({
          total_listen_seconds: localStats.totalListenDuration || 0,
          total_listen_episodes: localStats.totalListenCount || 0,
          completed_episodes: 0,
          favorite_count: 0,
        });
        return;
      }
      this.applyStats(stats);
    } catch (err) {
      console.error('加载用户统计失败:', err);
    }
  },

  applyStats(stats) {
    const totalListenDuration = stats.total_listen_seconds || 0;
    const totalListenCount = stats.total_listen_episodes || 0;
    const completedCount = stats.completed_episodes || 0;
    const favoriteCount = stats.favorite_count || 0;
    this.setData({
      totalListenDuration,
      totalListenCount,
      completedCount,
      favoriteCount,
      durationLabel: this.formatDuration(totalListenDuration),
    });
  },

  /**
   * 未登录时引导登录：重试静默登录流程
   */
  async onLogin() {
    wx.showLoading({ title: '登录中...' });
    try {
      const { user } = await login();
      getApp().globalData.userInfo = user;
      this.setData({ userInfo: user });
      this.loadStats();
      trackEvent('profile', 'login_success');
    } catch (err) {
      console.error('登录失败:', err);
      wx.showToast({ title: '登录失败，请稍后重试', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  /**
   * 秒 → "X小时Y分钟"，用于收听时长展示
   */
  formatDuration(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '0分钟';
    const m = Math.floor(sec / 60);
    if (m < 60) return `${m}分钟`;
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? `${h}小时${rest}分钟` : `${h}小时`;
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      confirmColor: '#FF6B8A',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await logout();
        } catch (err) {
          // 接口失败也继续清理本地态，避免卡在失效 token
          console.error('退出登录失败:', err);
        }
        const app = getApp();
        app.globalData.userInfo = null;
        app.globalData.token = null;
        trackEvent('profile', 'logout');
        // reLaunch 清空页面栈后回到首页 tab
        wx.reLaunch({ url: '/pages/index/index' });
      },
    });
  },

  /**
   * 点击列表项跳转
   * 各功能页统一通过 navigateTo 进入（非 tab 页）
   * 失败时降级为 reLaunch：避免页面栈满 10 层或 navigateTo 静默失败导致"无反应"
   */
  onTapSetting(e) {
    const key = e.currentTarget.dataset.key;
    if (key === 'logout') {
      this.onLogout();
      return;
    }
    trackEvent('profile', 'tap_menu', key);

    const routeMap = {
      favorites: '/pages/favorites/favorites',
      recent: '/pages/recent/recent',
      channels: '/pages/channels/channels',
      feedback: '/pages/feedback/feedback',
      settings: '/pages/settings/settings',
      about: '/pages/about/about',
      agreement: '/pages/agreement/agreement',
      privacy: '/pages/privacy/privacy',
    };
    const url = routeMap[key];
    if (!url) return;

    // navigateTo 失败（页面栈满/页面未注册等）时降级为 reLaunch，确保用户能进入目标页
    wx.navigateTo({
      url,
      fail: (err) => {
        console.warn('navigateTo 失败，降级为 reLaunch:', err);
        wx.reLaunch({ url });
      },
    });
  },
});
