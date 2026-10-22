/**
 * 播放队列页：展示当前队列、当前播放高亮、清空队列
 *
 * V1.3 新增（FR-SUP-05）
 */
const {
  getQueue, getQueueIndex, clearQueue, removeQueueAt, moveQueueItem,
  onQueueChange, playQueueAt,
} = require('../../services/audio');
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
    // 用 playQueueAt 同步更新 queueIndex，避免连播顺序错乱（与详情页一致）
    playQueueAt(idx);
    wx.navigateBack();
  },

  /**
   * 移除单项（J77）：只删这一首，不碰其余队列
   */
  onRemoveItem(e) {
    const idx = Number(e.currentTarget.dataset.index);
    const episode = this.data.queue[idx];
    if (!episode) return;
    wx.showModal({
      title: '移出队列',
      content: `确定把「${episode.title || '该节目'}」移出播放队列？`,
      confirmColor: '#B0554A',
      success: (res) => {
        if (!res.confirm) return;
        const result = removeQueueAt(idx);
        trackEvent('queue', 'remove_item', 'episode_' + episode.id);
        if (result && result.removedCurrent) {
          wx.showToast({ title: '已移出队列，当前音频继续播放', icon: 'none' });
        }
      },
    });
  },

  /**
   * 上移/下移（J77）：小屏上比拖拽可靠，且不依赖手势发现性
   */
  onMoveItem(e) {
    const { index, dir } = e.currentTarget.dataset;
    const from = Number(index);
    const to = from + Number(dir);
    if (moveQueueItem(from, to)) {
      trackEvent('queue', 'move_item');
    }
  },

  /**
   * 清空队列
   */
  onClear() {
    if (this.data.queue.length === 0) return;
    wx.showModal({
      title: '清空队列',
      content: '确定清空当前播放队列？',
      confirmColor: '#B0554A',
      success: (res) => {
        if (res.confirm) {
          clearQueue();
          trackEvent('queue', 'clear');
        }
      },
    });
  },
});
