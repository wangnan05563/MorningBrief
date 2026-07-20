/**
 * 全局入口：登录、全局播放器初始化、预加载今日节目
 *
 * V1.3 增强：
 * - 注入 version/buildDate（构建脚本可覆盖，about 页读取展示）
 * - 隐私授权检查（__usePrivacyCheck__: true 开启后需主动引导用户同意）
 * - 小程序版本更新检测（wx.getUpdateManager）
 *
 * onLaunch 执行顺序：
 * 1. 版本信息注入
 * 2. 检查小程序更新（冷启动时）
 * 3. 静默登录（wx.login → 后端换 token，失败时不阻断启动）
 * 4. 初始化全局播放器（BackgroundAudioManager 单例）
 * 5. 预加载今日节目元数据（首屏加速）
 * 6. 监听网络变化（弱网时进度上报降频）
 * 7. 隐私授权检查（涉及用户信息接口前需先同意）
 */
const { login } = require('./services/auth');
const { initPlayer } = require('./services/audio');
const { fetchTodayEpisode } = require('./services/api');

// 构建脚本可在编译期注入 VERSION / BUILD_DATE 全局变量覆盖默认值
const VERSION = (typeof __VERSION__ !== 'undefined' && __VERSION__) || '1.3.0';
const BUILD_DATE = (typeof __BUILD_DATE__ !== 'undefined' && __BUILD_DATE__) || '';

App({
  globalData: {
    userInfo: null,
    token: null,
    player: null,           // 全局音频播放器单例
    todayEpisode: null,     // 预加载的今日节目
    networkType: 'wifi',    // 网络类型（弱网降频用）
    listenStats: null,      // 收听统计（profile 页兜底读取，后续接入 stats 接口）
    version: VERSION,       // 应用版本（about 页展示）
    buildDate: BUILD_DATE,  // 构建日期（about 页展示）
    privacyAuthorized: false, // 隐私协议是否已授权
    currentChannelId: null,   // 当前选中的频道 ID（多频道切换用，null 表示全部）
  },

  /**
   * 启动就绪 Promise：onLaunch 内完成登录与预加载后 resolve
   *
   * 为什么需要这个：
   * 小程序框架不会 await App.onLaunch，页面 onLoad 可能在登录完成前执行，
   * 导致需鉴权的请求（如 /playlogs/recent）拿到空 token 触发 401。
   * 页面 onLoad 中 await getApp().readyPromise 可确保登录完成后才发请求。
   */
  readyPromise: null,

  async onLaunch() {
    this.readyPromise = (async () => {
      // 1. 检查小程序更新（冷启动时，仅 release 模式生效）
      this.checkUpdate();

      // 2. 静默登录（无需用户点击，失败时不阻断启动）
      try {
        const { token, user } = await login();
        this.globalData.token = token;
        this.globalData.userInfo = user;
        console.log('登录成功');
      } catch (err) {
        console.log('登录未执行（可忽略，不影响播放）:', err.message);
      }

      // 3. 初始化全局播放器（单例，所有页面共享）
      this.globalData.player = initPlayer();

      // 4. 预加载今日节目元数据（不含稿件，首屏加速）
      try {
        this.globalData.todayEpisode = await fetchTodayEpisode();
        console.log('预加载今日节目成功:', this.globalData.todayEpisode?.title);
      } catch (err) {
        console.log('预加载今日节目失败:', err.message);
      }

      // 5. 监听网络变化（弱网时进度上报降频）
      wx.onNetworkStatusChange((res) => {
        this.globalData.networkType = res.networkType;
      });

      // 6. 隐私授权检查：__usePrivacyCheck__ 开启后，调用涉及用户信息的 API 前需先同意
      this.checkPrivacy();
    })();
    return this.readyPromise;
  },

  /**
   * 检查小程序版本更新
   * 仅 release 模式生效（开发版不需要弹窗提示）
   */
  checkUpdate() {
    if (typeof __wxConfig !== 'undefined' && __wxConfig.envVersion !== 'release') return;
    const updateManager = wx.getUpdateManager();
    updateManager.onCheckForUpdate((res) => {
      if (res.hasUpdate) console.log('检测到新版本');
    });
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已就绪，是否重启应用？',
        confirmColor: '#FF6B8A',
        success: (res) => {
          if (res.confirm) updateManager.applyUpdate();
        },
      });
    });
    updateManager.onUpdateFailed(() => {
      wx.showToast({ title: '更新失败，请稍后重试', icon: 'none' });
    });
  },

  /**
   * 隐私授权检查
   * 2026 年起微信要求所有涉及用户信息的小程序必须接入隐私协议
   * 用户未同意前，调用 wx.getUserProfile/chooseMedia 等 API 会失败
   */
  checkPrivacy() {
    if (typeof wx.getPrivacySetting === 'undefined') {
      // 旧版基础库无此 API，直接标记为已授权以兼容
      this.globalData.privacyAuthorized = true;
      return;
    }
    wx.getPrivacySetting({
      success: (res) => {
        if (res.needAuthorization) {
          // 需要授权：监听全局隐私弹窗确认事件
          wx.onNeedPrivacyAuthorization && wx.onNeedPrivacyAuthorization((resolve) => {
            wx.showModal({
              title: '隐私保护提示',
              content: '为了向您提供更好的服务，我们需要您同意《用户协议》和《隐私政策》',
              confirmText: '同意',
              confirmColor: '#FF6B8A',
              cancelText: '拒绝',
              success: (modalRes) => {
                if (modalRes.confirm) {
                  this.globalData.privacyAuthorized = true;
                  resolve({ event: 'agree', buttonId: 'agree' });
                } else {
                  resolve({ event: 'disagree' });
                }
              },
            });
          });
        } else {
          this.globalData.privacyAuthorized = true;
        }
      },
      fail: () => {
        // 查询失败默认不阻断主流程
        this.globalData.privacyAuthorized = true;
      },
    });
  },
});
