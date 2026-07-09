/**
 * 个人中心：用户信息 + 收听统计 + 设置入口
 *
 * 收听统计暂无独立接口，先从 globalData 兜底读取（默认 0），
 * 便于后续接入 stats 接口时无需改动 UI。
 */
const { logout, getUser, login } = require('../../services/auth');

Page({
  data: {
    userInfo: null,
    totalListenDuration: 0,   // 累计收听秒数
    totalListenCount: 0,      // 累计收听期数
    durationLabel: '0分钟',   // 格式化后的收听时长
  },

  onShow() {
    // 每次展示都刷新，确保登录态/统计为最新
    const app = getApp();
    const userInfo = app.globalData.userInfo || getUser();
    this.setData({ userInfo });

    // 收听统计：暂无接口，从 globalData 兜底读取
    const stats = app.globalData.listenStats || {};
    const totalListenDuration = stats.totalListenDuration || 0;
    const totalListenCount = stats.totalListenCount || 0;
    this.setData({
      totalListenDuration,
      totalListenCount,
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
    } catch (err) {
      console.error('登录失败:', err);
      wx.showToast({ title: '登录失败，请稍后重试', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  /**
   * 秒 → “X小时Y分钟”，用于收听时长展示
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
        // reLaunch 清空页面栈后回到首页 tab
        wx.reLaunch({ url: '/pages/index/index' });
      },
    });
  },

  onTapSetting(e) {
    const key = e.currentTarget.dataset.key;
    if (key === 'logout') {
      this.onLogout();
      return;
    }
    // 占位项：播放设置 / 关于我们 暂未实现
    wx.showToast({ title: '敬请期待', icon: 'none' });
  },
});
