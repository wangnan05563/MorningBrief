/**
 * 播放队列页：展示当前队列、当前播放高亮、清空队列
 *
 * V1.3 新增（FR-SUP-05）
 */
const { getQueue, getQueueIndex, clearQueue, onQueueChange } = require('../../services/audio');
const { playEpisode } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    queue: [],
    currentIndex: -1,
  },

  onLoad() {
    trackPageView('pages/queue/queue');
    this.refresh();
    // 订阅队列变更：外部（如 history 页）修改队列时同步刷新
    this._unsub = onQueueChange((queue, index) => {
      this.setData({ queue, currentIndex: index });
    });
  },

  onUnload() {
    if (this._unsub) this._unsub();
  },

  onShow() {
    this.refresh();
  },

  refresh() {
    this.setData({
      queue: getQueue(),
      currentIndex: getQueueIndex(),
    });
  },

  /**
   * 点击队列项：直接播放该节目
   */
  onTapItem(e) {
    const { index } = e.currentTarget.dataset;
    const idx = Number(index);
    const episode = this.data.queue[idx];
    if (!episode) return;
    trackEvent('queue', 'tap_item', 'episode_' + episode.id);
    playEpisode(episode);
    wx.navigateBack();
  },

  /**
   * 清空队列
   */
  onClear() {
    if (this.data.queue.length === 0) return;
    wx.showModal({
      title: '清空队列',
      content: '确定清空当前播放队列？',
      confirmColor: '#FF6B8A',
      success: (res) => {
        if (res.confirm) {
          clearQueue();
          trackEvent('queue', 'clear');
        }
      },
    });
  },
});
