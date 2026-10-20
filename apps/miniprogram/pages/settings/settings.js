/**
 * 设置：播放设置 + 通知设置 + 缓存管理
 *
 * V1.3：
 * - 倍速与自动连播变更时同步到 audio.js 全局播放器，立即生效
 * - 通知设置触发订阅消息授权（一次性模板，用户每次需重新授权）
 * - 接入埋点
 */
// T02513 / J99：设置 key 收敛到 services/constants 单源（tracker.js 也按同一个 key 读开关）
const { STORAGE_KEY_SETTINGS } = require('../../services/constants');
const { setPlaybackRate, setAutoPlayNext, setWifiOnlyAutoPlay, setTransitionEnabled } = require('../../services/audio');
const { trackPageView, trackEvent, setTrackingEnabled } = require('../../utils/tracker');
const { requestSubscribeMessageByType } = require('../../services/api');

// 默认设置：用户首次进入时使用，避免空值导致 switch 显示异常
const DEFAULT_SETTINGS = {
  defaultRate: 1.0,
  autoPlayNext: true,
  wifiOnlyAutoPlay: false,
  transitionEnabled: false, // T00774：无缝过渡开关，默认关
  notifyNewEpisode: true,
  // T02513 / J99：使用记录统计开关（隐私政策第七条第 4 条指向的就是它，默认开）
  usageTracking: true,
};

// 清除缓存时保留的 key：登录态 + 用户设置
// ⚠ 这里的每一项都必须在 onClearCache 的确认文案里被如实描述到——
// 本单修掉的正是「文案说只留登录信息与设置，实际把收藏/进度/偏爱一起抹掉」的撒谎（J80）。
// storage key 命名尚未收敛（downloadKey(openid)/preferredChannelsKey(openid) 等是按 openid 动态拼的，
// 静态列不全），因此「只清缓存类、不动用户数据」的改造留给派生单，本单先把话说实话。
const KEEP_KEYS = ['news_token', 'news_user', STORAGE_KEY_SETTINGS];

Page({
  data: {
    defaultRate: 1.0,
    autoPlayNext: true,
    wifiOnlyAutoPlay: false,
    transitionEnabled: false,
    notifyNewEpisode: true,
    usageTracking: true,
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
      transitionEnabled: settings.transitionEnabled,
      notifyNewEpisode: settings.notifyNewEpisode,
      usageTracking: settings.usageTracking,
      rateIndex: rateIndex >= 0 ? rateIndex : 1,
    });
    // T02513 / J99：把设置里的开关同步给 tracker 单例——
    // 冷启动后第一个页面可能在设置页从未渲染过，靠这里读一次才能让「已关闭」真正生效。
    setTrackingEnabled(settings.usageTracking);
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
    // 同步到 audio.js 全局开关：让「仅 WiFi 自动播放」真正生效（A3 接线）
    setWifiOnlyAutoPlay(value);
    trackEvent('settings', 'change_wifi_only', '', value ? 1 : 0);
  },

  // T00774：无缝过渡开关——开启后预加载下一首详情+音频，连播/切歌零等待
  onTransitionChange(e) {
    const value = e.detail.value;
    this.setData({ transitionEnabled: value });
    this.saveSettings({ transitionEnabled: value });
    // 同步到 audio.js 全局开关：开启时立即预热当前队列的下一首
    setTransitionEnabled(value);
    trackEvent('settings', 'change_transition', '', value ? 1 : 0);
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
   * T02513 / J99：使用记录统计开关。
   * 顺序讲究：先落盘 + 先让 tracker 生效，再尝试记一条变更事件——
   * 关掉统计时这条事件本身就不该被记（否则「关闭」这个动作反而产生了一条记录）。
   */
  onTrackingChange(e) {
    const value = e.detail.value;
    this.setData({ usageTracking: value });
    this.saveSettings({ usageTracking: value });
    setTrackingEnabled(value);
    trackEvent('settings', 'change_usage_tracking', '', value ? 1 : 0);
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
   *
   * T02513 / J80：确认文案原先写「将清除本地缓存（保留登录信息与设置）」，
   * 而 KEEP_KEYS 之外被抹掉的其实是收藏、播放进度、播放历史、偏爱频道、下载索引、
   * 上次播放项、搜索历史、反馈历史 —— 用户以为清的是图片缓存，结果收藏清空、续听进度归零。
   * 现在逐类如实列出，并把「哪些能自动回来、哪些回不来」说清楚（依据：
   * 收藏与进度走 local-data 的双写，服务端有备份；偏爱频道只有本机一份）。
   * 确认键改成「仍要清除」，让这个动作在视觉上不等同于普通的「确定」。
   */
  onClearCache() {
    wx.showModal({
      title: '清除缓存',
      content:
        '会清掉本机存的：收藏、播放进度与历史、偏爱频道、下载/搜索/反馈记录。\n' +
        '保留：登录信息、播放与通知设置。\n' +
        '收藏和进度服务端有备份，会重新同步回来；偏爱频道只有本机一份，清掉不可恢复。\n' +
        '只影响本机，不删除服务器数据。',
      confirmText: '仍要清除',
      confirmColor: '#B0554A',
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

  /**
   * 手动检查更新（B6）：主动触发版本检测，弥补 onLaunch 仅 release 自动弹、无手动入口的问题。
   * 有更新时弹重启确认；无更新明确提示「已是最新」；弱网/失败时降级提示。
   */
  onCheckUpdate() {
    const updateManager = wx.getUpdateManager();
    wx.showLoading({ title: '检查中...' });
    updateManager.onCheckForUpdate((res) => {
      wx.hideLoading();
      if (res.hasUpdate) {
        trackEvent('settings', 'check_update', 'has_update');
      }
    });
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已就绪，是否重启应用？',
        confirmColor: '#3F6C8F',
        success: (r) => {
          if (r.confirm) updateManager.applyUpdate();
        },
      });
    });
    updateManager.onUpdateFailed(() => {
      wx.hideLoading();
      wx.showToast({ title: '更新失败，请稍后重试', icon: 'none' });
    });
    // 兜底：若干时间内无任何回调（如已是最新且 onCheckForUpdate 未触发），给出明确反馈
    setTimeout(() => {
      wx.hideLoading();
      wx.showToast({ title: '已是最新版本', icon: 'none' });
    }, 2000);
  },

  /**
   * 跳转关于页（B6）：设置页新增入口，避免在设置与关于间反复切换 tab
   */
  onOpenAbout() {
    wx.navigateTo({ url: '/pages/about/about' });
  },

  /**
   * T02513 / J99：隐私政策在「设置」里也要有入口。
   * 原先只有「我的 → 隐私政策」一条路，而隐私政策第七条第 4 条把用户往设置页指
   * （「关闭某些数据收集（在设置中操作）」），设置页却回不到隐私政策——两头互相指认却没有链接。
   */
  onOpenPrivacy() {
    wx.navigateTo({ url: '/pages/privacy/privacy' });
  },
});
