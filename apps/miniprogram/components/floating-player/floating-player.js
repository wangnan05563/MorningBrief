/**
 * 全局浮动播放按钮（任务9）
 *
 * 设计原因：
 * - tabBar 切换页面时，BackgroundAudioManager 仍在播放但页面无入口可见
 * - 此组件挂在主要页面（index/history/profile）底部，点击跳转到当前节目的详情页继续收听
 * - currentEpisode 为空（从未播放过）时隐藏，避免误触
 * - 纠偏有两条：宿主页面显示时（pageLifetimes.show）重算一次 + 播放状态订阅回调重算一次。
 *   只有订阅没有 show 钩子是 T02323 J5 的根因（tab 页组件常驻，错过事件后浮条永不出现）
 */
const { getCurrentEpisode, resumePlay, onPlaybackChange, onTimeUpdateChange } = require('../../services/audio');

Component({
  data: {
    visible: false,
    episode: null,
    isPlaying: false,
    fpProgressDeg: 0,  // T00722：播放进度环角度（0-360，仅变化时 setData）
  },

  lifetimes: {
    attached() {
      this._refresh();
      // 订阅播放状态变更：实现即时切换，无需轮询
      // T02513 / J5：回调原本只 setData({isPlaying})，从不重算 visible/episode——
      // tab 页组件 attach 一次后常驻，从详情页播完/起播再返回首页时浮条仍是旧 visible=false，
      // 用户失去暂停/续播入口。这里改成走 _refresh()，让三个字段同一口径更新。
      this._unsubPlayback = onPlaybackChange(() => {
        this._refresh();
      });
      // T00722：订阅播放进度，驱动浮条播放键的进度环（audio.js 已 800ms 节流；
      // 仅角度变化时 setData，避免无谓渲染）
      this._unsubTime = onTimeUpdateChange((ct, du) => {
        const deg = du > 0 ? Math.min(360, Math.round((ct / du) * 360)) : 0;
        if (deg !== this.data.fpProgressDeg) {
          this.setData({ fpProgressDeg: deg });
        }
      });
    },
    detached() {
      if (this._unsubPlayback) this._unsubPlayback();
      if (this._unsubTime) this._unsubTime();
    },
  },

  /**
   * T02513 / J5（与 J107 同源）：组件随 tab 页 attach 一次后常驻，「页面重新显示」是
   * 浮条唯一可靠的纠偏时机——从详情页起播/播完再切回首页，订阅回调可能早就错过了
   * （后台音频的 play/pause 事件不一定经过本页订阅链），没有 show 钩子就永远停在旧 visible。
   */
  pageLifetimes: {
    show() {
      this._refresh();
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
