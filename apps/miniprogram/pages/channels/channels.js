/**
 * 频道管理页：浏览所有频道、订阅/取消订阅
 *
 * V1.3 新增（FR-SUP-01）
 * 频道订阅后，未来该频道发布新节目时可推送订阅消息
 */
const { fetchChannels, subscribeChannel, unsubscribeChannel, channelType, requestSubscribeMessageByType } = require('../../services/api');
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
        // FR-MC-06：订阅后按频道类型请求订阅消息授权（拒绝不影响已完成的频道订阅）
        requestSubscribeMessageByType(channelType(id));
      }
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  /**
   * 点击频道卡片：
   * - 课程/有声书频道 → 跳课程主页（FR-MC-02/03/06）
   * - 资讯频道 → 切换首页 today 列表（跳转首页 tab）
   */
  onTapChannel(e) {
    const { id } = e.currentTarget.dataset;
    if (id && channelType(id) !== 'news') {
      wx.navigateTo({ url: '/pages/course/course?channelId=' + id });
      trackEvent('channels', 'open_course', 'channel_' + id);
      return;
    }
    const app = getApp();
    app.globalData.currentChannelId = id;
    wx.switchTab({ url: '/pages/index/index' });
    trackEvent('channels', 'switch', 'channel_' + id);
  },
});
