/**
 * 节目详情页：展示节目元数据 + 播放控制 + 稿件懒加载
 *
 * V1.3 新增：
 * - 收藏按钮（FR-SUP-02）
 * - 倍速控制（FR-SUP-06）
 * - 上一首/下一首（FR-SUP-05）- 依赖播放队列
 * - 睡眠定时器入口（FR-SUP-08）
 * - 节目来源展示（FR-SUP-12）- sources 字段
 * - 埋点（FR-SUP-10）
 */
const { fetchEpisodeDetail, fetchEpisodeScript, checkFavorite, addFavorite, removeFavorite } = require('../../services/api');
const {
  playEpisode, playNext, playPrev, getQueue, getQueueIndex,
  getPlaybackRate, setPlaybackRate,
  getSleepStatus, startSleepTimer, stopSleepTimer, onSleepChange,
} = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

const RATE_OPTIONS = [1.0, 1.25, 1.5, 0.75, 2.0];
const SLEEP_PRESETS = [
  { label: '关闭', value: 0 },
  { label: '15 分钟', value: 900 },
  { label: '30 分钟', value: 1800 },
  { label: '45 分钟', value: 2700 },
  { label: '60 分钟', value: 3600 },
];

Page({
  data: {
    episode: null,
    script: '',            // 稿件全文
    scriptLoaded: false,
    scriptLoading: false,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    currentTimeText: '00:00',
    durationText: '00:00',
    durationLabel: '',
    loading: true,
    error: '',
    // V1.3 新增
    favorited: false,
    currentRate: 1.0,
    sources: [],          // 节目来源（稿件加载后填充）
    hasPrev: false,       // 队列中是否有上一首
    hasNext: false,       // 队列中是否有下一首
    sleepActive: false,
    sleepLabel: '',
  },

  onLoad(options) {
    trackPageView('pages/detail/detail');
    const id = options.id;
    if (!id) {
      this.setData({ loading: false, error: '缺少节目参数' });
      return;
    }
    this._unsubSleep = onSleepChange((status) => {
      this.setData({
        sleepActive: status.active,
        sleepLabel: status.active ? this.formatSleepLabel(status.remaining) : '',
      });
    });
    this.bindPlayerEvents();
    this.loadDetail(id);
    this.checkFavorited(id);
    this.refreshQueueState();
    this.setData({ currentRate: getPlaybackRate() });
  },

  onUnload() {
    if (this._unsubSleep) this._unsubSleep();
    const player = getApp().globalData.player;
    if (player) {
      player.offPlay?.(this._onPlay);
      player.offPause?.(this._onPause);
      player.offTimeUpdate?.(this._onTimeUpdate);
      player.offEnded?.(this._onEnded);
    }
    this._onPlay = null;
    this._onPause = null;
    this._onTimeUpdate = null;
    this._onEnded = null;
  },

  async loadDetail(id) {
    try {
      const episode = await fetchEpisodeDetail(id);
      this.setData({
        episode,
        loading: false,
        durationLabel: this.formatDuration(episode.duration),
      });
      this.syncPlayingState();
    } catch (err) {
      this.setData({ loading: false, error: err.message || '加载失败' });
    }
  },

  /**
   * 检查收藏态
   */
  async checkFavorited(id) {
    try {
      const res = await checkFavorite(id);
      this.setData({ favorited: !!(res && res.favorited) });
    } catch (err) {
      this.setData({ favorited: false });
    }
  },

  /**
   * 收藏/取消收藏
   */
  async onToggleFavorite() {
    const ep = this.data.episode;
    if (!ep) return;
    try {
      if (this.data.favorited) {
        await removeFavorite(ep.id);
        this.setData({ favorited: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
        trackEvent('detail', 'unfavorite', 'episode_' + ep.id);
      } else {
        await addFavorite(ep.id);
        this.setData({ favorited: true });
        wx.showToast({ title: '已收藏', icon: 'success' });
        trackEvent('detail', 'favorite', 'episode_' + ep.id);
      }
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  /**
   * 刷新上一首/下一首可用状态
   * 根据当前队列索引判断
   */
  refreshQueueState() {
    const idx = getQueueIndex();
    const queue = getQueue();
    this.setData({
      hasPrev: idx > 0,
      hasNext: idx >= 0 && idx < queue.length - 1,
    });
  },

  bindPlayerEvents() {
    const player = getApp().globalData.player;
    if (!player) return;

    this._onPlay = () => {
      if (!this.isCurrentEpisode()) return;
      this.setData({ isPlaying: true, durationText: this.formatTime(player.duration) });
    };
    this._onPause = () => {
      if (!this.isCurrentEpisode()) return;
      this.setData({ isPlaying: false });
    };
    this._onTimeUpdate = () => {
      if (!this.isCurrentEpisode()) return;
      this.setData({
        currentTime: Math.floor(player.currentTime) || 0,
        duration: Math.floor(player.duration) || 0,
        currentTimeText: this.formatTime(player.currentTime),
        durationText: this.formatTime(player.duration),
      });
    };
    this._onEnded = () => {
      // 结束后队列索引可能变化，刷新上一首/下一首状态
      this.setData({ isPlaying: false, currentTime: 0, currentTimeText: '00:00' });
      this.refreshQueueState();
    };

    player.onPlay(this._onPlay);
    player.onPause(this._onPause);
    player.onTimeUpdate(this._onTimeUpdate);
    player.onEnded(this._onEnded);
  },

  isCurrentEpisode() {
    const player = getApp().globalData.player;
    const ep = this.data.episode;
    return !!(player && ep && player.episodeId != null && player.episodeId === ep.id);
  },

  syncPlayingState() {
    const player = getApp().globalData.player;
    if (!player || !this.isCurrentEpisode() || !player.duration) return;
    this.setData({
      isPlaying: !player.paused,
      currentTime: Math.floor(player.currentTime) || 0,
      duration: Math.floor(player.duration) || 0,
      currentTimeText: this.formatTime(player.currentTime),
      durationText: this.formatTime(player.duration),
    });
  },

  onPlay() {
    const ep = this.data.episode;
    if (!ep) return;
    playEpisode(ep);
    trackEvent('detail', 'play', 'episode_' + ep.id);
  },

  onTogglePlay() {
    const player = getApp().globalData.player;
    const ep = this.data.episode;
    if (!player || !ep) return;
    if (this.isCurrentEpisode()) {
      player.paused ? player.play() : player.pause();
    } else {
      playEpisode(ep);
      trackEvent('detail', 'play', 'episode_' + ep.id);
    }
  },

  onSeek(e) {
    const player = getApp().globalData.player;
    if (!player || !this.isCurrentEpisode()) return;
    const pos = e.detail.value;
    player.seek(pos);
    this.setData({ currentTime: pos, currentTimeText: this.formatTime(pos) });
  },

  /**
   * 上一首/下一首：依赖 audio.js 队列
   * 队列未设置时 getQueueIndex 返回 -1，按钮自动隐藏
   */
  onPrev() {
    if (playPrev()) {
      trackEvent('detail', 'play_prev');
      // 切换后需刷新本页节目信息：监听 queueIndex 变化或延迟刷新
      setTimeout(() => this.refreshQueueState(), 100);
    }
  },

  onNext() {
    if (playNext()) {
      trackEvent('detail', 'play_next');
      setTimeout(() => this.refreshQueueState(), 100);
    }
  },

  /**
   * 倍速循环切换
   */
  onCycleRate() {
    const current = getPlaybackRate();
    const idx = RATE_OPTIONS.indexOf(current);
    const next = RATE_OPTIONS[(idx + 1) % RATE_OPTIONS.length];
    setPlaybackRate(next);
    this.setData({ currentRate: next });
    wx.showToast({ title: next + 'x 倍速', icon: 'none' });
    trackEvent('detail', 'change_rate', '', next);
  },

  /**
   * 睡眠定时器
   */
  onSleepTimer() {
    wx.showActionSheet({
      itemList: SLEEP_PRESETS.map((p) => p.label),
      success: (res) => {
        const preset = SLEEP_PRESETS[res.tapIndex];
        if (preset.value === 0) {
          stopSleepTimer();
          wx.showToast({ title: '已关闭睡眠定时', icon: 'none' });
        } else {
          startSleepTimer(preset.value);
          wx.showToast({ title: '睡眠定时 ' + preset.label, icon: 'none' });
          trackEvent('detail', 'sleep_timer_on', '', preset.value);
        }
      },
    });
  },

  /**
   * 懒加载稿件：用户点击"查看完整文稿"才请求
   * V1.3：稿件接口返回 sources 字段，展示版权溯源
   */
  async onLoadScript() {
    if (this.data.scriptLoaded || this.data.scriptLoading) return;
    const ep = this.data.episode;
    if (!ep) return;

    this.setData({ scriptLoading: true });
    try {
      const res = await fetchEpisodeScript(ep.id);
      const content = typeof res === 'string'
        ? res
        : (res && (res.script || res.content)) || '';
      const sources = (res && res.sources) || [];
      this.setData({
        script: content,
        scriptLoaded: true,
        scriptLoading: false,
        sources,
      });
    } catch (err) {
      console.error('加载文稿失败:', err);
      this.setData({ scriptLoading: false });
      wx.showToast({ title: '文稿加载失败', icon: 'none' });
    }
  },

  formatTime(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  },

  formatDuration(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '0分钟';
    const m = Math.floor(sec / 60);
    if (m < 60) return m + '分钟';
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? h + '小时' + rest + '分钟' : h + '小时';
  },

  formatSleepLabel(sec) {
    if (sec <= 0) return '';
    const m = Math.floor(sec / 60);
    if (m < 60) return m + ' 分钟后停止';
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? h + '小时' + rest + '分钟后停止' : h + '小时后停止';
  },

  onShareAppMessage() {
    const ep = this.data.episode || {};
    return {
      title: ep.title || '今日要闻',
      path: '/pages/detail/detail?id=' + (ep.id || ''),
    };
  },

  onBackHome() {
    wx.switchTab({ url: '/pages/index/index' });
  },
});
