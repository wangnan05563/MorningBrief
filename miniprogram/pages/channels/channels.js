/**
 * 频道管理页：浏览所有频道、订阅/取消订阅
 *
 * V1.3 新增（FR-SUP-01）
 * 频道订阅后，未来该频道发布新节目时可推送订阅消息
 */
const { fetchChannels, subscribeChannel, unsubscribeChannel } = require('../../services/api');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    channels: [],
    loading: true,
  },

  onLoad() {
    trackPageView('pages/channels/channels');
    this.loadChannels();
  },

  /**
   * 下拉刷新：重新拉取频道列表
   */
  onPullDownRefresh() {
    this.loadChannels().then(() => {
      wx.stopPullDownRefresh();
    });
  },

  async loadChannels() {
    this.setData({ loading: true });
    try {
      const res = await fetchChannels();
      this.setData({
        channels: res.list || [],
        loading: false,
      });
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    }
  },

  /**
   * 订阅/取消订阅频道
   */
  async onToggleSubscribe(e) {
    const { id, index } = e.currentTarget.dataset;
    const channel = this.data.channels[index];
    if (!channel) return;

    try {
      if (channel.is_subscribed) {
        await unsubscribeChannel(id);
        this.setData({
          [`channels[${index}].is_subscribed`]: false,
        });
        wx.showToast({ title: '已取消订阅', icon: 'none' });
        trackEvent('channels', 'unsubscribe', 'channel_' + id);
      } else {
        await subscribeChannel(id);
        this.setData({
          [`channels[${index}].is_subscribed`]: true,
        });
        wx.showToast({ title: '订阅成功', icon: 'success' });
        trackEvent('channels', 'subscribe', 'channel_' + id);
      }
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  /**
   * 点击频道卡片：切换到该频道今日节目（跳转首页 tab）
   */
  onTapChannel(e) {
    const { id } = e.currentTarget.dataset;
    const app = getApp();
    app.globalData.currentChannelId = id;
    wx.switchTab({ url: '/pages/index/index' });
    trackEvent('channels', 'switch', 'channel_' + id);
  },
});
