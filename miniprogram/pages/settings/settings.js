/**
 * 设置：播放设置 + 通知设置 + 缓存管理
 *
 * V1.3：
 * - 倍速与自动连播变更时同步到 audio.js 全局播放器，立即生效
 * - 通知设置触发订阅消息授权（一次性模板，用户每次需重新授权）
 * - 接入埋点
 */
const STORAGE_KEY_SETTINGS = 'news_settings';
const { setPlaybackRate, setAutoPlayNext } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');
const { requestSubscribeMessageByType } = require('../../services/api');

// 默认设置：用户首次进入时使用，避免空值导致 switch 显示异常
const DEFAULT_SETTINGS = {
  defaultRate: 1.0,
  autoPlayNext: true,
  wifiOnlyAutoPlay: false,
  notifyNewEpisode: true,
};

// 清除缓存时保留的 key：登录态 + 用户设置
const KEEP_KEYS = ['news_token', 'news_user', STORAGE_KEY_SETTINGS];

Page({
  data: {
    defaultRate: 1.0,
    autoPlayNext: true,
    wifiOnlyAutoPlay: false,
    notifyNewEpisode: true,
    rateOptions: [0.75, 1.0, 1.25, 1.5, 2.0],
    rateIndex: 1,
    cacheSize: '0 KB',
  },

  onLoad() {
    trackPageView('pages/settings/settings');
    this.loadSettings();
    this.updateCacheSize();
  },

  /**
   * 从 storage 读取设置：合并默认值，保证字段完整
   */
  loadSettings() {
    const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
    const settings = { ...DEFAULT_SETTINGS, ...saved };
    const rateIndex = this.data.rateOptions.indexOf(settings.defaultRate);
    this.setData({
      defaultRate: settings.defaultRate,
      autoPlayNext: settings.autoPlayNext,
      wifiOnlyAutoPlay: settings.wifiOnlyAutoPlay,
      notifyNewEpisode: settings.notifyNewEpisode,
      rateIndex: rateIndex >= 0 ? rateIndex : 1,
    });
  },

  /**
   * 增量保存设置：避免覆盖其他字段
   */
  saveSettings(patch) {
    const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
    // 非关键写入（偏好设置）：改异步避免阻塞主线程，失败仅告警不影响 UI
    wx.setStorage({
      key: STORAGE_KEY_SETTINGS,
      data: { ...saved, ...patch },
      fail: (e) => console.warn('[settings] 设置写入失败:', e && e.errMsg),
    });
  },

  onRateChange(e) {
    const index = Number(e.detail.value);
    const rate = this.data.rateOptions[index];
    this.setData({ rateIndex: index, defaultRate: rate });
    this.saveSettings({ defaultRate: rate });
    // 立即同步到全局播放器（当前正在播放的节目也会即时变速）
    setPlaybackRate(rate);
    trackEvent('settings', 'change_rate', '', rate);
  },

  onAutoPlayNextChange(e) {
    const value = e.detail.value;
    this.setData({ autoPlayNext: value });
    this.saveSettings({ autoPlayNext: value });
    // 同步到 audio.js 全局开关（影响 onEnded 自动连播行为）
    setAutoPlayNext(value);
    trackEvent('settings', 'change_auto_play_next', '', value ? 1 : 0);
  },

  onWifiOnlyChange(e) {
    const value = e.detail.value;
    this.setData({ wifiOnlyAutoPlay: value });
    this.saveSettings({ wifiOnlyAutoPlay: value });
    trackEvent('settings', 'change_wifi_only', '', value ? 1 : 0);
  },

  onNotifyChange(e) {
    const value = e.detail.value;
    this.setData({ notifyNewEpisode: value });
    this.saveSettings({ notifyNewEpisode: value });
    // 开启通知需请求订阅消息授权（一次性模板，FR-MC-06：news 类型模板由后端下发）
    // 用户拒绝授权时回滚开关（与 V1.3 原逻辑一致）；频道订阅关系不在此处处理
    if (value) {
      requestSubscribeMessageByType('news', {
        onRejected: () => {
          this.setData({ notifyNewEpisode: false });
          this.saveSettings({ notifyNewEpisode: false });
        },
      });
    }
    trackEvent('settings', 'change_notify', '', value ? 1 : 0);
  },

  /**
   * 读取当前缓存占用：currentSize 单位为 KB
   */
  updateCacheSize() {
    try {
      const info = wx.getStorageInfoSync();
      this.setData({ cacheSize: info.currentSize + ' KB' });
    } catch (err) {
      console.error('获取缓存大小失败', err);
    }
  },

  /**
   * 清除缓存：保留登录态与用户设置，移除其余缓存
   */
  onClearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '将清除本地缓存（保留登录信息与设置），确定继续？',
      confirmColor: '#FF6B8A',
      success: (res) => {
        if (!res.confirm) return;
        try {
          const info = wx.getStorageInfoSync();
          info.keys.forEach((key) => {
            if (KEEP_KEYS.indexOf(key) === -1) {
              wx.removeStorageSync(key);
            }
          });
          this.updateCacheSize();
          wx.showToast({ title: '已清除', icon: 'success' });
          trackEvent('settings', 'clear_cache');
        } catch (err) {
          console.error('清除缓存失败', err);
          wx.showToast({ title: '清除失败', icon: 'none' });
        }
      },
    });
  },
});
