/**
 * 节目详情页：展示节目元数据 + 播放控制 + 稿件懒加载
 *
 * 设计要点：
 * - 稿件体积大，仅在用户点击“查看完整文稿”时加载，首屏更快
 * - 播放状态来自全局 BackgroundAudioManager 单例（app.globalData.player），
 *   通过 player.title 比较确认“当前播放的即本页节目”，避免与其他页面串扰
 */
const { fetchEpisodeDetail, fetchEpisodeScript } = require('../../services/api');
const { playEpisode } = require('../../services/audio');

Page({
  data: {
    episode: null,
    script: '',            // 稿件全文
    scriptLoaded: false,   // 稿件是否已加载完成
    scriptLoading: false,  // 稿件加载中（防重复点击）
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    currentTimeText: '00:00',
    durationText: '00:00',
    durationLabel: '',     // 节目元数据时长（“X分钟”），与播放器实际时长区分
    loading: true,         // 详情加载态
    error: '',             // 详情加载错误信息
  },

  onLoad(options) {
    const id = options.id;
    if (!id) {
      this.setData({ loading: false, error: '缺少节目参数' });
      return;
    }
    this.bindPlayerEvents();
    this.loadDetail(id);
  },

  onUnload() {
    // 显式 off 监听器：每次进入页面都会重新 onPlay，若不 off 会累积监听
    // 导致内存泄漏与多组回调同时 setData 引发 UI 串扰
    const player = getApp().globalData.player;
    if (player && this._onPlay) {
      player.offPlay(this._onPlay);
      player.offPause(this._onPause);
      player.offTimeUpdate(this._onTimeUpdate);
      player.offEnded(this._onEnded);
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
      // 详情到达后若该节目正在播放，同步进度
      this.syncPlayingState();
    } catch (err) {
      this.setData({ loading: false, error: err.message || '加载失败' });
    }
  },

  /**
   * 绑定全局播放器事件以同步本页播放 UI
   * 全局 player 单例会对所有页面触发事件，
   * 故每次回调都需校验是否为当前节目
   */
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
      this.setData({ isPlaying: false, currentTime: 0, currentTimeText: '00:00' });
    };

    player.onPlay(this._onPlay);
    player.onPause(this._onPause);
    player.onTimeUpdate(this._onTimeUpdate);
    player.onEnded(this._onEnded);
  },

  /**
   * 判断全局播放器当前播放的是否是本页节目
   * 依据 player.episodeId（audio.js 在 playEpisode 时已赋值），避免标题重复误判
   */
  isCurrentEpisode() {
    const player = getApp().globalData.player;
    const ep = this.data.episode;
    return !!(player && ep && player.episodeId != null && player.episodeId === ep.id);
  },

  /**
   * 详情到达后同步正在播放的进度（如从历史页跳入正在播放的节目）
   */
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

  /**
   * 显式开始播放（节目未在播放时调用）
   */
  onPlay() {
    const ep = this.data.episode;
    if (!ep) return;
    playEpisode(ep);
  },

  /**
   * 播放/暂停切换：同一节目就地切换，否则切到本节目并断点续播
   */
  onTogglePlay() {
    const player = getApp().globalData.player;
    const ep = this.data.episode;
    if (!player || !ep) return;
    if (this.isCurrentEpisode()) {
      player.paused ? player.play() : player.pause();
    } else {
      playEpisode(ep);
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
   * 懒加载稿件：用户点击“查看完整文稿”才请求
   * scriptLoading 防重复请求，scriptLoaded 防重复加载
   */
  async onLoadScript() {
    if (this.data.scriptLoaded || this.data.scriptLoading) return;
    const ep = this.data.episode;
    if (!ep) return;

    this.setData({ scriptLoading: true });
    try {
      // 兼容后端返回纯字符串、{ script } 或 { content } 三种结构
      // 字段优先级：script（当前后端实际字段）> content（历史兼容）
      const res = await fetchEpisodeScript(ep.id);
      const content = typeof res === 'string'
        ? res
        : (res && (res.script || res.content)) || '';
      this.setData({ script: content, scriptLoaded: true, scriptLoading: false });
    } catch (err) {
      console.error('加载文稿失败:', err);
      this.setData({ scriptLoading: false });
      wx.showToast({ title: '文稿加载失败', icon: 'none' });
    }
  },

  /**
   * 秒 → "mm:ss"，供进度条两侧展示
   */
  formatTime(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
  },

  /**
   * 秒 → “X小时Y分钟”，用于节目信息卡片展示元数据时长
   */
  formatDuration(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '0分钟';
    const m = Math.floor(sec / 60);
    if (m < 60) return `${m}分钟`;
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? `${h}小时${rest}分钟` : `${h}小时`;
  },

  onShareAppMessage() {
    const ep = this.data.episode || {};
    return {
      title: ep.title || '今日要闻',
      path: `/pages/detail/detail?id=${ep.id || ''}`,
    };
  },

  onBackHome() {
    wx.switchTab({ url: '/pages/index/index' });
  },
});
