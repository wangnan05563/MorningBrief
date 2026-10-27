/**
 * 设置：播放设置 + 通知设置 + 缓存管理
 *
 * V1.3：
 * - 倍速与自动连播变更时同步到 audio.js 全局播放器，立即生效
 * - 通知设置触发订阅消息授权（一次性模板，用户每次需重新授权）
 * - 接入埋点
 */
// T02513 / J99：设置 key 单源；T02787 起单源是 services/storage-keys.js（tracker.js 读同一个 key）
const { STATIC: STORAGE_KEYS, clearCacheKeys } = require('../../services/storage-keys');
const STORAGE_KEY_SETTINGS = STORAGE_KEYS.SETTINGS;
const { setPlaybackRate, setAutoPlayNext, setWifiOnlyAutoPlay, setTransitionEnabled } = require('../../services/audio');
const { trackPageView, trackEvent, setTrackingEnabled } = require('../../utils/tracker');
const {
  requestSubscribeMessageByType,
  fetchMyDataSummary,
  purgeMyData,
} = require('../../services/api');
const { getToken, getUser, clearToken } = require('../../services/auth');
const localData = require('../../services/local-data');
const downloadStore = require('../../services/download');

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

// T02787 / J80 续：清除缓存改为**正向白名单**——只删 services/storage-keys.js 里
// 归入 CACHE_KEYS 的可再生项，收藏、播放进度与历史、偏爱频道、下载索引、上次播放项、
// 搜索历史、反馈历史、待补报队列一律不动。
// 原先这里是黑名单（KEEP_KEYS 只列 3 个，循环删掉其余全部），所以 key 名一旦散在各模块
// 且按 openid 动态拼接，静态列不全，黑名单就永远漏——漏掉的那一类就是被抹掉的用户数据。
// 认不出的 key（新版本残留、别人新加的）同样不删：宁可少清，不可多抹。

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
   * 本机 storage 占用（KB）：currentSize 是 storage 总量，含收藏/进度这些不会被清掉的数据，
   * 所以它只代表「本机存了多少」，不代表「清除缓存能释放多少」——行下文案按这个口径说。
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
   * 清除缓存：只删可再生项，用户数据一律不动
   *
   * T02513 / J80 把话说实话（文案逐类点名会被抹掉的东西）；T02787 才是真修：
   * 删哪些由 services/storage-keys.js 的 CACHE_KEYS 白名单决定，
   * 收藏、播放进度与历史、偏爱频道、下载索引、上次播放项、搜索历史、反馈历史、
   * 待补报收听队列都在 USER_DATA_KEYS 里，清缓存碰不到；登录态与设置在 KEEP_KEYS 里。
   * 因此这个动作不再需要红色「仍要清除」的警告级确认——它不再毁掉任何东西，
   * 但也不能反过来冒充「能释放很多空间」：删了几项如实播报，0 项就说没有可清除的缓存。
   */
  onClearCache() {
    wx.showModal({
      title: '清除缓存',
      content:
        '只清可再生的技术缓存（例如上次探测到的服务地址）。\n' +
        '不会清除：收藏、播放进度与历史、偏爱频道、下载索引、上次播放项、搜索与反馈记录。\n' +
        '保留：登录信息、播放与通知设置。\n' +
        '本机存的基本都是你的数据，清缓存不会释放多少空间；只影响本机，不删除服务器数据。\n' +
        '想彻底删除服务端数据请走意见反馈提出请求。',
      confirmText: '清除',
      success: (res) => {
        if (!res.confirm) return;
        try {
          const info = wx.getStorageInfoSync();
          const removed = clearCacheKeys(info.keys, (key) => wx.removeStorageSync(key));
          this.updateCacheSize();
          wx.showToast({
            title: removed.length ? `已清除 ${removed.length} 项缓存` : '本机没有可清除的缓存',
            icon: 'none',
          });
          trackEvent('settings', 'clear_cache', String(removed.length));
        } catch (err) {
          console.error('清除缓存失败', err);
          wx.showToast({ title: '清除失败', icon: 'none' });
        }
      },
    });
  },

  /**
   * T02788 / J98：删除我的数据（服务端 + 本机）。
   *
   * 顺序讲究：
   * 1. 先取预览条数——「将删除收藏 3 条、播放记录 8 条…」比「确定删除？」更能说明后果，
   *    条数与备份保留期都由后端返回，前端不写死数字（写死就会随配置调整变成第二处谎）；
   * 2. 确认框用破坏性配色，并写明不可恢复；
   * 3. 删除成功后只清本机登录态，绝不调 logout()——服务端已把这 token 拉黑，
   *    logout 的 401 自动重登会把刚删掉的账号立刻重新注册出来。
   */
  async onPurgeMyData() {
    if (!getToken()) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    let summary = null;
    try {
      summary = await fetchMyDataSummary();
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '获取删除范围失败', icon: 'none' });
      return;
    }

    const counts = (summary && summary.counts) || {};
    const retention = (summary && summary.retention) || {};
    const detail = [
      ['收藏', counts.favorite],
      ['评论', counts.comment],
      ['点赞', counts.comment_like],
      ['播放记录', counts.play_log],
      ['播放进度', counts.play_progress],
      ['频道订阅', counts.channel_subscription],
      ['消息订阅', counts.subscription],
    ]
      .filter(([, n]) => n > 0)
      .map(([label, n]) => `${label} ${n} 条`)
      .join('、');
    const scope = detail ? `将删除：${detail}。` : '服务器上没有查到您名下的数据。';
    const keepDays = retention.db_backup_keep_days || 7;
    const cosKeep = retention.cos_backup_keep_count || 5;

    wx.showModal({
      title: '删除我的数据',
      content:
        `${scope}\n` +
        '同时清除本机登录态与离线副本；意见反馈记录不在删除范围内。\n' +
        `数据库备份按 ${keepDays} 天保留周期自然过期，云端备份最多保留 ${cosKeep} 份，因此无法立即彻底抹除。\n` +
        '此操作不可恢复。',
      confirmText: '删除',
      confirmColor: '#B0554A',
      success: async (res) => {
        if (!res.confirm) return;
        // 先取 openid 再清登录态：本机数据按 openid 分区，登出后取不到
        const user = getUser();
        const openid = (user && user.openid) || '';
        wx.showLoading({ title: '删除中...', mask: true });
        try {
          await purgeMyData();
        } catch (err) {
          wx.hideLoading();
          wx.showToast({ title: (err && err.message) || '删除失败，请稍后重试', icon: 'none' });
          return;
        }
        wx.hideLoading();
        if (openid) {
          localData.clearByOpenid(openid);
          downloadStore.clearByOpenid(openid);
        }
        clearToken();
        const app = getApp();
        if (app && app.globalData) {
          app.globalData.userInfo = null;
          app.globalData.token = null;
        }
        trackEvent('settings', 'purge_my_data');
        wx.showToast({ title: '已删除', icon: 'none' });
        wx.reLaunch({ url: '/pages/index/index' });
      },
    });
  },

  /**
   * 手动检查更新（B6）：主动触发版本检测，弥补 onLaunch 仅 release 自动弹、无手动入口的问题。
   * 有更新时弹重启确认；无更新明确提示「已是最新」；弱网/失败时降级提示。
   */
  onCheckUpdate() {
    const updateManager = wx.getUpdateManager();
    // J81（FR-UX-704）：反馈必须等真实回调。此前固定 2s 后无条件 toast「已是最新版本」，
    // 弱网下真有更新也先报最新，用户会以为功能坏了。
    let settled = false;
    wx.showLoading({ title: '检查中...' });
    updateManager.onCheckForUpdate((res) => {
      if (settled) return;
      settled = true;
      wx.hideLoading();
      if (res.hasUpdate) {
        wx.showToast({ title: '发现新版本，正在下载…', icon: 'none' });
        trackEvent('settings', 'check_update', 'has_update');
      } else {
        wx.showToast({ title: '已是最新版本', icon: 'none' });
      }
    });
    updateManager.onUpdateReady(() => {
      wx.hideLoading();
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
      settled = true;
      wx.hideLoading();
      wx.showToast({ title: '更新失败，请稍后重试', icon: 'none' });
    });
    // 仅当检查回调迟迟不来时兜底，并且如实说「超时」，不再冒充「已是最新」
    setTimeout(() => {
      if (settled) return;
      settled = true;
      wx.hideLoading();
      wx.showToast({ title: '检查超时，请稍后重试', icon: 'none' });
    }, 8000);
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
