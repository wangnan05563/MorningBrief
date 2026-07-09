/**
 * 全局入口：登录、全局播放器初始化、预加载今日节目
 *
 * onLaunch 执行顺序：
 * 1. 静默登录（wx.login → 后端换 token）
 * 2. 初始化全局播放器（BackgroundAudioManager 单例）
 * 3. 预加载今日节目元数据（首屏加速）
 * 4. 监听网络变化（弱网时进度上报降频）
 */
const { login } = require('./services/auth');
const { initPlayer } = require('./services/audio');
const { fetchTodayEpisode } = require('./services/api');

App({
  globalData: {
    userInfo: null,
    token: null,
    player: null,           // 全局音频播放器单例
    todayEpisode: null,     // 预加载的今日节目
    networkType: 'wifi',    // 网络类型（弱网降频用）
    listenStats: null,      // 收听统计（profile 页兜底读取，后续接入 stats 接口）
  },

  async onLaunch() {
    // 1. 静默登录（无需用户点击，失败时在用户操作时重试）
    try {
      const { token, user } = await login();
      this.globalData.token = token;
      this.globalData.userInfo = user;
    } catch (err) {
      console.error('登录失败，将在用户操作时重试', err);
    }

    // 2. 初始化全局播放器（单例，所有页面共享）
    this.globalData.player = initPlayer();

    // 3. 预加载今日节目元数据（不含稿件，首屏加速）
    try {
      this.globalData.todayEpisode = await fetchTodayEpisode();
    } catch (err) {
      console.error('预加载今日节目失败', err);
    }

    // 4. 监听网络变化（弱网时进度上报降频）
    wx.onNetworkStatusChange((res) => {
      this.globalData.networkType = res.networkType;
    });
  },
});
