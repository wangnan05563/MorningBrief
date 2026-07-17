/**
 * 首页/播放页：展示今日节目 + 播放控制
 *
 * V1.3 新增：
 * - 频道切换（FR-SUP-03）：顶部胶囊切换不同频道今日节目
 * - 搜索入口（FR-SUP-04）：右上角搜索图标跳转搜索页
 * - 倍速控制（FR-SUP-06）：点击倍速按钮循环切换
 * - 睡眠定时器（FR-SUP-08）：预设时长快捷启动
 * - 收藏（FR-SUP-02）：收藏/取消收藏当前节目
 * - 埋点（FR-SUP-10）
 *
 * 数据流：globalData.todayEpisode（预加载）→ 页面 data → WXML 渲染
 * 播放器：使用 app.globalData.player（全局单例），页面只负责 UI 状态同步
 */
const { fetchTodayEpisode, checkFavorite, addFavorite, removeFavorite, fetchChannels } = require('../../services/api');
const { playEpisode, getPlaybackRate, setPlaybackRate, getSleepStatus, startSleepTimer, stopSleepTimer, onSleepChange } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

const app = getApp();

// 倍速选项：循环切换顺序
const RATE_OPTIONS = [1.0, 1.25, 1.5, 0.75, 2.0];

// 睡眠定时器预设（秒）
const SLEEP_PRESETS = [
  { label: '关闭', value: 0 },
  { label: '15 分钟', value: 900 },
  { label: '30 分钟', value: 1800 },
  { label: '45 分钟', value: 2700 },
  { label: '60 分钟', value: 3600 },
];

Page({
  data: {
    episode: null,      // 今日节目对象 { id, title, date, category, duration, audio_url }
    isPlaying: false,   // 播放状态
    currentTime: 0,     // 当前播放位置（秒）
    duration: 0,        // 总时长（秒，播放后由播放器填入）
    loading: true,      // 加载中
    error: '',          // 错误信息（今日节目未发布等）
    // V1.3 新增字段
    channels: [],         // 频道列表
    currentChannelId: null, // 当前选中频道（null 表示全部）
    favorited: false,     // 当前节目是否已收藏
    currentRate: 1.0,     // 当前倍速
    sleepActive: false,   // 睡眠定时器是否激活
    sleepRemaining: 0,    // 睡眠剩余秒数
    sleepLabel: '',       // 睡眠定时器展示文案
  },

  onLoad() {
    trackPageView('pages/index/index');
    this._unsubSleep = onSleepChange((status) => {
      this.setData({
        sleepActive: status.active,
        sleepRemaining: status.remaining,
        sleepLabel: status.active ? this.formatSleepLabel(status.remaining) : '',
      });
    });
    this.bindPlayerEvents();
    this.initData();
    this.loadChannels();
  },

  onUnload() {
    if (this._unsubSleep) this._unsubSleep();
    // 解绑播放器事件，防止 reLaunch 后 onLoad 重复绑定导致回调叠加
    const player = app.globalData.player;
    if (player) {
      player.offPlay?.(this._onPlay);
      player.offPause?.(this._onPause);
      player.offTimeUpdate?.(this._onTimeUpdate);
      player.offEnded?.(this._onEnded);
    }
  },

  onShow() {
    // 每次显示页面时同步播放器状态（从其他页返回时播放状态可能已变化）
    this.syncPlayerState();
    this.setData({ currentRate: getPlaybackRate() });
    // 从详情页返回时可能改了收藏态，需重新检查
    if (this.data.episode) this.checkFavorited(this.data.episode.id);
  },

  /**
   * 加载频道列表（用于顶部频道切换胶囊）
   */
  async loadChannels() {
    try {
      const res = await fetchChannels();
      // 第一个选项为"全部"，后接频道列表
      const channels = [{ id: null, name: '全部' }, ...(res.list || [])];
      this.setData({ channels });
    } catch (err) {
      console.log('加载频道列表失败:', err.message);
    }
  },

  /**
   * 切换频道：重新拉取该频道今日节目
   */
  async onSwitchChannel(e) {
    // 用严格判断避免 id=0 被误判为 falsy（虽然频道 id 通常从 1 开始，但防御性编程）
    const rawId = e.currentTarget.dataset.id;
    const channelId = (rawId !== undefined && rawId !== null && rawId !== '') ? rawId : null;
    if (channelId === this.data.currentChannelId) return;
    this.setData({ currentChannelId: channelId });
    app.globalData.currentChannelId = channelId;
    trackEvent('index', 'switch_channel', '', channelId || 0);
    await this.initData(true);
  },

  /**
   * 加载今日节目
   * 优先用 globalData 预加载的数据，避免重复请求 + 首屏加速
   * @param {boolean} force - 强制刷新（频道切换时）
   */
  async initData(force) {
    // 非强制刷新时优先用 globalData 缓存
    if (!force && app.globalData.todayEpisode && !this.data.currentChannelId) {
      this.setData({ episode: app.globalData.todayEpisode, loading: false });
      this.checkFavorited(app.globalData.todayEpisode.id);
      return;
    }

    this.setData({ loading: true, error: '' });
    try {
      const episode = await fetchTodayEpisode(this.data.currentChannelId);
      this.setData({ episode, loading: false });
      if (!this.data.currentChannelId) {
        app.globalData.todayEpisode = episode;
      }
      this.checkFavorited(episode.id);
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '今日节目暂未上线',
      });
    }
  },

  /**
   * 检查当前节目是否已收藏
   */
  async checkFavorited(episodeId) {
    if (!episodeId) return;
    try {
      const res = await checkFavorite(episodeId);
      this.setData({ favorited: !!(res && res.favorited) });
    } catch (err) {
      this.setData({ favorited: false });
    }
  },

  /**
   * 收藏/取消收藏当前节目
   */
  async onToggleFavorite() {
    const { episode, favorited } = this.data;
    if (!episode) return;
    try {
      if (favorited) {
        await removeFavorite(episode.id);
        this.setData({ favorited: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
        trackEvent('index', 'unfavorite', 'episode_' + episode.id);
      } else {
        await addFavorite(episode.id);
        this.setData({ favorited: true });
        wx.showToast({ title: '已收藏', icon: 'success' });
        trackEvent('index', 'favorite', 'episode_' + episode.id);
      }
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  /**
   * 绑定全局播放器事件，实时同步播放进度和状态到页面
   * 回调引用存到实例属性，供 onUnload 精确解绑
   */
  bindPlayerEvents() {
    const player = app.globalData.player;
    if (!player) return;

    this._onPlay = () => { this.setData({ isPlaying: true }); };
    this._onPause = () => { this.setData({ isPlaying: false }); };
    this._onTimeUpdate = () => {
      this.setData({
        currentTime: Math.floor(player.currentTime),
        duration: Math.floor(player.duration),
      });
    };
    this._onEnded = () => {
      this.setData({ isPlaying: false, currentTime: 0 });
    };

    player.onPlay(this._onPlay);
    player.onPause(this._onPause);
    player.onTimeUpdate(this._onTimeUpdate);
    player.onEnded(this._onEnded);
  },

  syncPlayerState() {
    const player = app.globalData.player;
    if (!player) return;
    this.setData({
      isPlaying: !player.paused,
      currentTime: Math.floor(player.currentTime || 0),
      duration: Math.floor(player.duration || 0),
    });
  },

  onTogglePlay() {
    const { episode, isPlaying } = this.data;
    if (!episode) return;
    const player = app.globalData.player;
    if (!player) return;
    if (isPlaying) {
      player.pause();
    } else {
      playEpisode(episode);
      trackEvent('index', 'play', 'episode_' + episode.id);
    }
  },

  onSeek(e) {
    const player = app.globalData.player;
    if (!player) return;
    const position = e.detail.value;
    player.seek(position);
    this.setData({ currentTime: position });
  },

  onViewScript() {
    const { episode } = this.data;
    if (!episode) return;
    wx.navigateTo({
      url: '/pages/detail/detail?id=' + episode.id,
    });
  },

  /**
   * 跳转搜索页
   */
  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' });
    trackEvent('index', 'tap_search');
  },

  /**
   * 倍速循环切换：1.0 → 1.25 → 1.5 → 0.75 → 2.0 → 1.0
   */
  onCycleRate() {
    const current = getPlaybackRate();
    const idx = RATE_OPTIONS.indexOf(current);
    const next = RATE_OPTIONS[(idx + 1) % RATE_OPTIONS.length];
    setPlaybackRate(next);
    this.setData({ currentRate: next });
    wx.showToast({ title: next + 'x 倍速', icon: 'none' });
    trackEvent('index', 'change_rate', '', next);
  },

  /**
   * 睡眠定时器：弹出 ActionSheet 选择预设时长
   */
  onSleepTimer() {
    const labels = SLEEP_PRESETS.map((p) => p.label);
    const status = getSleepStatus();
    // 已激活时第一个选项显示"关闭"，与预设中的 value=0 对应
    wx.showActionSheet({
      itemList: labels,
      success: (res) => {
        const preset = SLEEP_PRESETS[res.tapIndex];
        if (preset.value === 0) {
          stopSleepTimer();
          wx.showToast({ title: '已关闭睡眠定时', icon: 'none' });
          trackEvent('index', 'sleep_timer_off');
        } else {
          startSleepTimer(preset.value);
          wx.showToast({ title: '睡眠定时 ' + preset.label, icon: 'none' });
          trackEvent('index', 'sleep_timer_on', '', preset.value);
        }
      },
    });
  },

  /**
   * 秒 → "X分钟" 或 "X小时Y分钟"
   */
  formatSleepLabel(sec) {
    if (sec <= 0) return '';
    const m = Math.floor(sec / 60);
    if (m < 60) return m + ' 分钟后停止';
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? h + '小时' + rest + '分钟后停止' : h + '小时后停止';
  },
});
