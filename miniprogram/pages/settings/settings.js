/**
 * 设置：播放设置 + 通知设置 + 缓存管理
 *
 * 所有设置项变更立即写入 localStorage（news_settings），
 * audio.js 通过 getDefaultRate() 读取默认倍速，无需页面间传参。
 */
const STORAGE_KEY_SETTINGS = 'news_settings';

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
    wx.setStorageSync(STORAGE_KEY_SETTINGS, { ...saved, ...patch });
  },

  onRateChange(e) {
    const index = Number(e.detail.value);
    const rate = this.data.rateOptions[index];
    this.setData({ rateIndex: index, defaultRate: rate });
    this.saveSettings({ defaultRate: rate });
  },

  onAutoPlayNextChange(e) {
    const value = e.detail.value;
    this.setData({ autoPlayNext: value });
    this.saveSettings({ autoPlayNext: value });
  },

  onWifiOnlyChange(e) {
    const value = e.detail.value;
    this.setData({ wifiOnlyAutoPlay: value });
    this.saveSettings({ wifiOnlyAutoPlay: value });
  },

  onNotifyChange(e) {
    const value = e.detail.value;
    this.setData({ notifyNewEpisode: value });
    this.saveSettings({ notifyNewEpisode: value });
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
        } catch (err) {
          console.error('清除缓存失败', err);
          wx.showToast({ title: '清除失败', icon: 'none' });
        }
      },
    });
  },
});
