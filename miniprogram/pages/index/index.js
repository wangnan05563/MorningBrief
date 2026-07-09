/**
 * 首页/播放页：展示今日节目 + 播放控制
 *
 * 数据流：globalData.todayEpisode（预加载）→ 页面 data → WXML 渲染
 * 播放器：使用 app.globalData.player（全局单例），页面只负责 UI 状态同步
 */
const { fetchTodayEpisode } = require('../../services/api');
const { playEpisode } = require('../../services/audio');

const app = getApp();

Page({
  data: {
    episode: null,      // 今日节目对象 { id, title, date, category, duration, audio_url }
    isPlaying: false,   // 播放状态
    currentTime: 0,     // 当前播放位置（秒）
    duration: 0,        // 总时长（秒，播放后由播放器填充）
    loading: true,      // 加载中
    error: '',          // 错误信息（今日节目未发布等）
  },

  onLoad() {
    this.initData();
    this.bindPlayerEvents();
  },

  onShow() {
    // 每次显示页面时同步播放器状态（从其他页返回时播放状态可能已变化）
    this.syncPlayerState();
  },

  /**
   * 加载今日节目
   * 优先用 globalData 预加载的数据，避免重复请求 + 首屏加速
   */
  async initData() {
    if (app.globalData.todayEpisode) {
      this.setData({ episode: app.globalData.todayEpisode, loading: false });
      return;
    }

    this.setData({ loading: true, error: '' });
    try {
      const episode = await fetchTodayEpisode();
      this.setData({ episode, loading: false });
      // 缓存到 globalData，避免下次再请求
      app.globalData.todayEpisode = episode;
    } catch (err) {
      // 今日节目未发布时后端返回错误，给用户友好提示
      this.setData({
        loading: false,
        error: err.message || '今日节目暂未上线',
      });
    }
  },

  /**
   * 绑定全局播放器事件，实时同步播放进度和状态到页面
   * BackgroundAudioManager 的 onXxx 支持多监听器，与 audio.js 内部监听共存不冲突
   */
  bindPlayerEvents() {
    const player = app.globalData.player;
    if (!player) return;

    // 时间更新：刷新进度条 + 时间显示（播放时约每 250ms 触发一次）
    player.onTimeUpdate(() => {
      this.setData({
        currentTime: Math.floor(player.currentTime),
        duration: Math.floor(player.duration),
      });
    });

    player.onPlay(() => {
      this.setData({ isPlaying: true });
    });

    // 暂停含来电等系统中断场景
    player.onPause(() => {
      this.setData({ isPlaying: false });
    });

    // 播放结束：重置进度到起点
    player.onEnded(() => {
      this.setData({ isPlaying: false, currentTime: 0 });
    });
  },

  /**
   * 同步播放器当前状态（从其他页面返回时调用）
   */
  syncPlayerState() {
    const player = app.globalData.player;
    if (!player) return;
    this.setData({
      isPlaying: !player.paused,
      currentTime: Math.floor(player.currentTime || 0),
      duration: Math.floor(player.duration || 0),
    });
  },

  /**
   * 播放/暂停切换
   * 暂停直接调 player.pause()；播放走 playEpisode 以触发断点续播逻辑
   */
  onTogglePlay() {
    const { episode, isPlaying } = this.data;
    if (!episode) return;

    const player = app.globalData.player;
    if (!player) return;

    if (isPlaying) {
      player.pause();
    } else {
      playEpisode(episode);
    }
  },

  /**
   * 拖动进度条跳转（bindchange：用户松手后触发）
   */
  onSeek(e) {
    const player = app.globalData.player;
    if (!player) return;
    const position = e.detail.value;
    player.seek(position);
    this.setData({ currentTime: position });
  },

  /**
   * 查看文稿：跳转详情页
   */
  onViewScript() {
    const { episode } = this.data;
    if (!episode) return;
    wx.navigateTo({
      url: `/pages/detail/detail?id=${episode.id}`,
    });
  },
});
