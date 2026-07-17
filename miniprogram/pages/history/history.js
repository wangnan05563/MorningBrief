/**
 * 历史列表页：分页加载往期节目，点击跳转详情页播放
 *
 * V1.3 新增：
 * - 频道过滤（FR-SUP-03）：顶部胶囊切换频道
 * - 搜索入口（FR-SUP-04）
 * - 播放队列：点击节目时设置队列，支持自动连播
 * - 埋点（FR-SUP-10）
 *
 * 分页：上拉加载更多（onReachBottom）+ 下拉刷新（onPullDownRefresh）
 */
const { fetchHistory, fetchChannels } = require('../../services/api');
const { setQueue } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    list: [],
    page: 1,
    size: 20,
    total: 0,
    loading: false,
    hasMore: true,
    // V1.3 新增
    channels: [],
    currentChannelId: null,
  },

  onLoad() {
    trackPageView('pages/history/history');
    this.loadChannels();
    this.loadHistory(true);
  },

  /**
   * 加载频道列表
   */
  async loadChannels() {
    try {
      const res = await fetchChannels();
      const channels = [{ id: null, name: '全部' }, ...(res.list || [])];
      this.setData({ channels });
    } catch (err) {
      console.log('加载频道列表失败:', err.message);
    }
  },

  /**
   * 切换频道：重新拉取该频道历史
   */
  async onSwitchChannel(e) {
    const channelId = e.currentTarget.dataset.id || null;
    if (channelId === this.data.currentChannelId) return;
    this.setData({ currentChannelId: channelId });
    trackEvent('history', 'switch_channel', '', channelId || 0);
    await this.loadHistory(true);
  },

  /**
   * 分页加载历史列表
   * @param {boolean} first - true=重置第1页（下拉刷新/首次），false=加载下一页
   */
  async loadHistory(first) {
    if (this.data.loading) return;
    if (first) {
      this.setData({ list: [], page: 1, hasMore: true });
    }
    if (!this.data.hasMore && !first) return;

    this.setData({ loading: true });

    try {
      const res = await fetchHistory(this.data.page, this.data.size, this.data.currentChannelId);
      const items = res.list || res.items || [];
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
      wx.showToast({
        title: err.message || '加载失败',
        icon: 'none',
      });
    }
  },

  onReachBottom() {
    this.loadHistory(false);
  },

  onPullDownRefresh() {
    this.loadHistory(true).then(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 点击节目：设置播放队列（自动连播）+ 跳转详情页
   * 队列从当前列表当前项开始，便于顺序连播后续节目
   */
  onPlay(e) {
    const { id, index } = e.currentTarget.dataset;
    const idx = Number(index) || 0;
    // 设置队列：从点击项开始，后续节目自动连播
    if (this.data.list.length > 0) {
      setQueue(this.data.list, idx);
    }
    trackEvent('history', 'play', 'episode_' + id);
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`,
    });
  },

  /**
   * 跳转搜索页
   */
  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' });
    trackEvent('history', 'tap_search');
  },
});
