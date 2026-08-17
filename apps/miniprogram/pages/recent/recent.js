/**
 * 最近播放页：按播放时间倒序展示，点击断点续播
 *
 * V1.3 新增（FR-SUP-13）
 * 后端 /playlogs/recent 已按 episode 去重（每个 episode 仅展示最新一条）
 */
// localData 封装播放历史的双写（本地+后端），按 openid 隔离，读取优先本地
const localData = require('../../services/local-data');
const { setQueue } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    list: [],
    page: 1,
    total: 0,
    loading: true,
    hasMore: true,
  },

  onLoad() {
    trackPageView('pages/recent/recent');
    this.loadRecent(true);
  },

  async loadRecent(first) {
    if (this.data.loading && !first) return;
    if (first) {
      this.setData({ list: [], page: 1, hasMore: true });
    }
    if (!this.data.hasMore && !first) return;

    this.setData({ loading: true });
    try {
      // localData.getHistory 优先本地，本地无时从后端读取
      const res = await localData.getHistory(this.data.page, 20);
      // 本地历史项存的是 id，wxml 的 data-id 与 wx:key 绑 item.episode_id，缺失会导致
      // 点击跳转失败（评审 HIGH #2）。统一归一化 episode_id 后再拼接。
      const items = (res.list || []).map((it) => ({ ...it, episode_id: it.episode_id ?? it.id }));
      const newList = first ? items : this.data.list.concat(items);
      this.setData({
        list: newList,
        total: res.total || 0,
        hasMore: newList.length < (res.total || 0),
        page: this.data.page + 1,
        loading: false,
      });
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    }
  },

  onReachBottom() {
    this.loadRecent(false);
  },

  onPullDownRefresh() {
    this.loadRecent(true).then(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 点击最近播放项：设置队列并跳转详情页（断点续播）
   */
  onTapItem(e) {
    const { id, index } = e.currentTarget.dataset;
    const idx = Number(index) || 0;
    // 队列设置为最近播放列表（按 episode 简化结构）
    const queueEpisodes = this.data.list.map((it) => ({
      id: it.episode_id,
      title: it.title,
      audio_url: it.audio_url,
    }));
    if (queueEpisodes.length > 0) {
      setQueue(queueEpisodes, idx);
    }
    trackEvent('recent', 'tap_item', 'episode_' + id);
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
  },
});
