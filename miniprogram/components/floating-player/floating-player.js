/**
 * 全局浮动播放按钮（任务9）
 *
 * 设计原因：
 * - tabBar 切换页面时，BackgroundAudioManager 仍在播放但页面无入口可见
 * - 此组件挂在主要页面（index/history/profile）底部，点击跳转到当前节目的详情页继续收听
 * - currentEpisode 为空（从未播放过）时隐藏，避免误触
 * - 通过 onShow 周期查询 currentEpisode，避免与播放器状态强耦合
 */
const { getCurrentEpisode, resumePlay, onPlaybackChange } = require('../../services/audio');

Component({
  data: {
    visible: false,
    episode: null,
    isPlaying: false,
  },

  lifetimes: {
    attached() {
      this._refresh();
      // 订阅播放状态变更：实现即时切换，无需轮询
      this._unsubPlayback = onPlaybackChange((evt) => {
        const player = getApp().globalData.player;
        const isPlaying = !!(player && !player.paused);
        this.setData({ isPlaying });
      });
    },
    detached() {
      if (this._unsubPlayback) this._unsubPlayback();
    },
  },

  methods: {
    _refresh() {
      const ep = getCurrentEpisode();
      const visible = !!(ep && ep.id);
      const app = getApp();
      const player = app.globalData.player;
      const isPlaying = !!(player && !player.paused);
      const prev = this.data;
      // 简化：任何字段变化都 setData，确保图标能及时切换
      // 之前的代码有 3 个分支判断同一类条件，重复且不可读
      const episodeChanged = !!(prev.episode && ep && prev.episode.id !== ep.id);
      if (visible !== prev.visible || isPlaying !== prev.isPlaying || episodeChanged) {
        this.setData({ visible, episode: ep, isPlaying });
      }
    },

    onTap() {
      const ep = this.data.episode;
      if (!ep || !ep.id) {
        wx.showToast({ title: '暂无正在播放的节目', icon: 'none' });
        return;
      }
      const app = getApp();
      if (app.globalData.player && app.globalData.player.paused) {
        resumePlay();
      }
      wx.navigateTo({
        url: '/pages/detail/detail?id=' + ep.id,
      });
    },
  },
});
