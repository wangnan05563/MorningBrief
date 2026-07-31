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
const { playEpisode, seek, onPlaybackChange, onTimeUpdateChange, offTimeUpdateChange } = require('../../services/audio');

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
    seekTimestamp: 0,          // seek后1500ms内忽略onTimeUpdate覆盖，防止重缓冲把进度重置
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
      // 取消 audio.js 的订阅：避免组件销毁后回调仍触发 setData 报错
      if (this._unsubPlayback) {
        this._unsubPlayback();
        this._unsubPlayback = null;
      }
      if (this._onTimeUpdateChange) {
        offTimeUpdateChange(this._onTimeUpdateChange);
        this._onTimeUpdateChange = null;
      }
    },
  },

  methods: {
    /**
     * 绑定全局 player 事件以同步本组件 UI
     *
     * 为什么用订阅接口而非直接 player.onXxx：
     * BackgroundAudioManager.onXxx 是覆盖式注册，直接注册会覆盖 audio.js initPlayer 中
     * 注册的回调（含 playNext 自动连播、startProgressReport、applyPlaybackRate 等核心逻辑），
     * 导致自动连播失效、进度不上报、倍速丢失等问题。
     * 改为通过 audio.js 的订阅接口（onPlaybackChange/onTimeUpdateChange）监听事件。
     */
    bindPlayerEvents() {
      // 播放/暂停/结束状态变更
      this._unsubPlayback = onPlaybackChange((evt) => {
        if (!this.isCurrentEpisode()) return;
        const player = getApp().globalData.player;
        if (evt.type === 'play') {
          this.setData({ isPlaying: true, durationText: this.formatTime(player.duration) });
        } else if (evt.type === 'pause' || evt.type === 'ended') {
          this.setData({ isPlaying: false });
          if (evt.type === 'ended') {
            this.setData({ currentTime: 0, currentTimeText: '00:00' });
          }
        }
      });

      // 时间更新：同步进度条
      this._onTimeUpdateChange = (currentTime, duration) => {
        if (!this.isCurrentEpisode()) return;
        // seek后1500ms内忽略timeUpdate回调，防止重缓冲把进度重置为0
        if (Date.now() - (this.data.seekTimestamp || 0) < 1500) return;
        this.setData({
          currentTime,
          duration,
          currentTimeText: this.formatTime(currentTime),
          durationText: this.formatTime(duration),
        });
      };
      onTimeUpdateChange(this._onTimeUpdateChange);
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
      // 调用 services/audio 的 seek 函数：处理暂停状态下 seek 不生效的问题
      seek(pos);
      // 记录seek时间点，onTimeUpdate会忽略seek后1500ms内的回调，
      // 防止重缓冲期间 onTimeUpdate 把进度拉回旧值或 0
      this.setData({
        currentTime: pos,
        currentTimeText: this.formatTime(pos),
        seekTimestamp: Date.now(),
      });
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
