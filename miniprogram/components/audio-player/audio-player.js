/**
 * 可复用音频播放器组件
 *
 * 设计原因：detail 页与未来其他页面都需要内嵌播放控制，
 * 抽成组件复用同一套全局 BackgroundAudioManager 单例，
 * 避免每个页面重复绑定事件与维护播放状态。
 *
 * 关键点：组件不持有播放器实例，仅监听全局 player 事件，
 * 并通过比较 player.title 判断“当前播放的是否是本组件的节目”，
 * 从而在多页面共享同一个播放器时仍能正确反映本组件的播放态。
 */
const { playEpisode } = require('../../services/audio');

Component({
  properties: {
    // 节目对象 { id, title, audio_url }
    episode: {
      type: Object,
      value: null,
    },
  },

  data: {
    isPlaying: false,
    currentTime: 0,            // 当前播放位置（秒）
    duration: 0,               // 总时长（秒）
    currentTimeText: '00:00',  // 预格式化文本，避免在 WXML 中调用方法
    durationText: '00:00',
  },

  observers: {
    // 父组件异步拿到节目后传入，此时需重新同步“正在播放”的进度
    episode(ep) {
      if (ep) this.syncFromPlayer();
    },
  },

  lifetimes: {
    attached() {
      this.bindPlayerEvents();
      this.syncFromPlayer();
    },
    detached() {
      // 显式 off 本组件注册的回调：组件 onPlay 等注册的是自身闭包，
      // 与 audio.js 内部注册的回调是不同引用，off 不会误删全局监听
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
  },

  methods: {
    /**
     * 绑定全局 player 事件以同步本组件 UI
     * 全局 player 是单例，事件对所有页面触发，
     * 故每次回调都需校验是否为当前节目，避免串扰
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
     * 从全局播放器同步初始态（页面切入时节目可能已在播放）
     */
    syncFromPlayer() {
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
   * 判断全局播放器当前播放的是否是本组件的节目
   * 依据 player.episodeId（audio.js 在 playEpisode 时已赋值），避免标题重复误判
   */
  isCurrentEpisode() {
    const player = getApp().globalData.player;
    const ep = this.properties.episode;
    return !!(player && ep && player.episodeId != null && player.episodeId === ep.id);
  },

    onTogglePlay() {
      const player = getApp().globalData.player;
      const ep = this.properties.episode;
      if (!player || !ep) return;
      if (this.isCurrentEpisode()) {
        // 同一节目：在播放则暂停，已暂停则继续
        player.paused ? player.play() : player.pause();
      } else {
        // 不同节目：交给 playEpisode 处理断点续播与切源
        playEpisode(ep);
      }
    },

    onSeek(e) {
      const player = getApp().globalData.player;
      if (!player || !this.isCurrentEpisode()) return;
      // slider 的 detail.value 即拖动落点（秒）
      const pos = e.detail.value;
      player.seek(pos);
      this.setData({ currentTime: pos, currentTimeText: this.formatTime(pos) });
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
  },
});
