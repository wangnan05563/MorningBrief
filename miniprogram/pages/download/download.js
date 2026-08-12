/**
 * 我的下载（FR-MC-09）
 *
 * 离线下载管理页：按课程分组列出已下载章节，显示总占用空间，
 * 支持单条删除、按课程清空、清空全部。点击条目离线播放（detail 页复用 _pickPlayableUrl）。
 */
const downloadStore = require('../../services/download');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    groups: [],          // [{ channelId, channelName, items: [...] }]
    totalSize: 0,        // 字节
    totalSizeLabel: '0 B',
    totalCount: 0,
  },

  onShow() {
    trackPageView('pages/download/download');
    this.refresh();
  },

  refresh() {
    const all = downloadStore.listDownloads();
    // 按频道分组
    const map = {};
    all.forEach((r) => {
      const cid = r.channelId || 0;
      if (!map[cid]) {
        map[cid] = { channelId: cid, channelName: r.channelName || '未命名课程', items: [] };
      }
      map[cid].items.push(r);
    });
    const groups = Object.keys(map).map((k) => map[k]);
    const totalSize = downloadStore.computeTotalSize();
    this.setData({
      groups,
      totalSize,
      totalSizeLabel: this.formatSize(totalSize),
      totalCount: all.length,
    });
  },

  formatSize(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let n = bytes;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }
    return (i === 0 ? n : n.toFixed(1)) + ' ' + units[i];
  },

  _fmtDur(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
  },

  // 点击条目 → 离线播放（detail 页会自动命中下载路径）
  onTapItem(e) {
    const { id, channelId } = e.currentTarget.dataset;
    if (!id) return;
    trackEvent('download', 'tap_item', 'episode_' + id);
    wx.navigateTo({
      url: '/pages/detail/detail?id=' + id + '&channelId=' + channelId,
    });
  },

  onDeleteItem(e) {
    const { id } = e.currentTarget.dataset;
    if (!id) return;
    wx.showModal({
      title: '删除下载',
      content: '确定删除该章节的本地缓存？',
      success: (res) => {
        if (res.confirm) {
          downloadStore.removeDownload(id);
          this.refresh();
          wx.showToast({ title: '已删除', icon: 'none' });
        }
      },
    });
  },

  onClearChannel(e) {
    const { channelId } = e.currentTarget.dataset;
    if (!channelId) return;
    wx.showModal({
      title: '清空本课程',
      content: '删除该课程下全部已下载章节？',
      success: (res) => {
        if (res.confirm) {
          downloadStore.clearByChannel(Number(channelId));
          this.refresh();
          wx.showToast({ title: '已清空', icon: 'none' });
        }
      },
    });
  },

  onClearAll() {
    if (!this.data.totalCount) return;
    wx.showModal({
      title: '清空全部下载',
      content: '将删除全部离线缓存文件，不可恢复。',
      confirmColor: '#FF6B8A',
      success: (res) => {
        if (res.confirm) {
          downloadStore.clearAll();
          this.refresh();
          wx.showToast({ title: '已清空', icon: 'none' });
        }
      },
    });
  },
});
