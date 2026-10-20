/**
 * 频道管理页：浏览所有频道、订阅/取消订阅
 *
 * V1.3 新增（FR-SUP-01）
 * 频道订阅后，未来该频道发布新节目时可推送订阅消息
 */
const { fetchChannels, subscribeChannel, unsubscribeChannel, channelType, requestSubscribeMessageByType } = require('../../services/api');
const { trackPageView, trackEvent } = require('../../utils/tracker');
// T00599：加载态控制器（最短骨架展示 + 慢加载提示 + 超时重试）
const { createLoadingController } = require('../../utils/loading');

Page({
  data: {
    channels: [],
    loading: true,
    // T00599：分级加载态（由 utils/loading.js 控制器维护）
    loadingSlow: false,
    loadingTimedOut: false,
  },

  onLoad() {
    // T00599：加载态控制器（onUnload 需 cancel）
    this._lc = createLoadingController({ setData: this.setData.bind(this) });
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
    // T00599：start() 置骨架态并启动分级计时；成功走 finish()（最短展示保护），失败 fail() 立即收起
    this._lc.start();
    try {
      const res = await fetchChannels();
      this.setData({ channels: res.list || [] });
      this._lc.finish();
    } catch (err) {
      // 失败：立即收起骨架（toast 提示），不被最短展示时长拖住
      this._lc.fail();
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    }
  },

  /** T00599：慢加载超时后的重试入口（骨架下方"重试"按钮） */
  onRetryLoad() {
    this.loadChannels();
  },

  /** T00599：清理加载态计时器，避免页面销毁后仍 setData */
  onUnload() {
    if (this._lc) this._lc.cancel();
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
    // T02513 / J46：原先只写 currentChannelId 就 switchTab，首页从不读取该值 →
    // 用户点完频道回到首页看到的还是原样（评审原话「在用户视角没反应」）。
    // 现在再留一份一次性请求，由首页 onShow / loadChannels 消费并给出 toast 反馈。
    app.globalData.pendingChannelId = id;
    wx.switchTab({ url: '/pages/index/index' });
    trackEvent('channels', 'switch', 'channel_' + id);
  },

  /**
   * T02513 / J48：把「订阅」与「偏爱」两条路分开指清楚——本页只管订阅，
   * 排序偏好在 preferred-settings 页，用户不必自己猜哪一页才是他要改的那个开关。
   */
  onGoPreferred() {
    // T02513 / J48：与 preferred-settings 页的 onGoChannels 成对——
    // 已经在偏爱页时（从那边点反向入口进来的）直接退回，避免同一页面在栈里叠两份。
    const pages = getCurrentPages();
    const prev = pages[pages.length - 2];
    if (prev && prev.route === 'pages/preferred-settings/preferred-settings') {
      wx.navigateBack();
    } else {
      wx.navigateTo({ url: '/pages/preferred-settings/preferred-settings' });
    }
    trackEvent('channels', 'open_preferred', 'preferred_settings');
  },
});
