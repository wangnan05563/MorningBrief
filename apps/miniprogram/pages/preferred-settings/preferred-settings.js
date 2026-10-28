/**
 * 偏爱频道设置页：多选频道，筛选"我的偏爱"tab 展示内容
 *
 * 与 channels 页的区别：
 * - channels 页管理订阅（推送通知用）
 * - 本页管理偏爱（节目筛选用），独立于订阅状态
 *
 * 数据流：localData.getPreferredChannels → 页面勾选态 → localData.setPreferredChannels
 * 保存后通过 globalData 事件通知今日/历史页刷新
 */
const { fetchChannels } = require('../../services/api');
const localData = require('../../services/local-data');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    channels: [],       // 全部频道列表（含 selected 字段）
    loading: true,
    selectedCount: 0,   // 已选数量（底部按钮显示用）
    // 首次引导模式：从 query.from=onboarding 进入时为 true，显示"暂不设置"按钮
    // 为什么单独一个标志：避免普通入口（profile → 偏爱频道设置）也出现跳过按钮
    isOnboarding: false,
    // J106：取数失败与「暂无可用频道」是两件事（失败态由 load-error 渲染并自带重试）
    loadError: '',
    // J64：底部栏要有「全选/全不选」文字，判定必须覆盖全部频道而不是只看第一项
    allSelected: false,
  },

  onLoad(query) {
    trackPageView('pages/preferred-settings/preferred-settings');
    this.setData({ isOnboarding: query && query.from === 'onboarding' });
    this.loadChannels();
  },

  async loadChannels() {
    this.setData({ loading: true, loadError: '' });
    try {
      const res = await fetchChannels();
      const allChannels = (res && res.list) || [];
      // 读取本地已保存的偏爱频道 ID 列表
      const preferredIds = localData.getPreferredChannels();
      const idSet = new Set(preferredIds);
      // 标记每个频道是否已选
      const channels = allChannels.map((ch) => ({
        ...ch,
        selected: idSet.has(ch.id),
      }));
      this.setData({
        channels,
        loading: false,
        selectedCount: preferredIds.length,
        allSelected: this.computeAllSelected(channels),
        loadError: '',
      });
    } catch (err) {
      // J106：失败态自带重试；不再 toast 一句后落到「暂无可用频道」
      this.setData({ loading: false, loadError: err.message || '加载失败' });
    }
  },

  /** J106：失败态的重试入口 */
  onRetryLoad() {
    this.loadChannels();
  },

  /**
   * 切换频道选中态
   */
  onToggleChannel(e) {
    const { index } = e.currentTarget.dataset;
    const idx = Number(index);
    const channel = this.data.channels[idx];
    if (!channel) return;
    const newSelected = !channel.selected;
    this.setData({
      [`channels[${idx}].selected`]: newSelected,
      selectedCount: newSelected ? this.data.selectedCount + 1 : this.data.selectedCount - 1,
      allSelected: this.data.channels.every((ch, i) => (i === idx ? newSelected : ch.selected)),
    });
  },

  /** J64：「全选/全不选」文案要反映真实全选态（空列表不算已全选） */
  computeAllSelected(channels) {
    return channels.length > 0 && channels.every((ch) => ch.selected);
  },

  /**
   * 保存偏爱频道设置
   * 全量覆盖本地存储，并通过 globalData 通知今日/历史页刷新
   */
  onSave() {
    const selectedIds = this.data.channels
      .filter((ch) => ch.selected)
      .map((ch) => ch.id);
    // A5：未登录时 setPreferredChannels 返回 false（openid 缺失，存储无目标 key）。
    // J63：只 toast 一句会把从首启引导进来的新用户卡死——这里说清为什么必须登录，
    // 并给出直达「我的」登录的按钮，而不是让用户自己找底部 tab。
    const saved = localData.setPreferredChannels(selectedIds);
    if (!saved) {
      trackEvent('preferred', 'save_blocked_login');
      wx.showModal({
        title: '需要先登录',
        content: '偏爱频道保存在你的账号里，换设备后也能恢复。未登录时无法保存，请先到「我的」完成登录再回来设置。',
        confirmText: '去登录',
        cancelText: '留在此页',
        confirmColor: '#3F6C8F',
        success: (res) => {
          if (res.confirm) {
            trackEvent('preferred', 'save_goto_login');
            wx.switchTab({ url: '/pages/profile/profile' });
          }
        },
      });
      return;
    }
    // 标记已完成首次引导（即使用户选0个也视为已完成）
    localData.markPreferredChannelsOnboarded();
    // 通过 globalData 事件通知今日/历史页刷新偏爱筛选
    const app = getApp();
    app.globalData.preferredChannelsChanged = Date.now();
    trackEvent('preferred', 'save', 'count_' + selectedIds.length);
    wx.showToast({ title: '已保存', icon: 'success' });
    setTimeout(() => wx.navigateBack(), 800);
  },

  /**
   * 全选/全不选
   */
  onSelectAll() {
    // J64：以 data.allSelected 为单一判定源，避免 wxml 里另算一套（此前只看第一项的写法是错的）
    const newSelected = !this.data.allSelected;
    const channels = this.data.channels.map((ch) => ({ ...ch, selected: newSelected }));
    this.setData({
      channels,
      selectedCount: newSelected ? channels.length : 0,
      allSelected: this.computeAllSelected(channels),
    });
  },

  /**
   * 首次引导模式专用：跳过设置直接返回
   * 仅 isOnboarding=true 时可见
   * 仍需 markOnboarded：避免下次启动再次触发引导，否则用户每次都被弹窗骚扰
   */
  onSkip() {
    localData.markPreferredChannelsOnboarded();
    trackEvent('preferred', 'skip_onboarding');
    wx.navigateBack();
  },

  /**
   * T02513 / J48：反向入口——从「偏爱」指回「频道订阅」，与 channels 页的 tip-link 成对。
   * 已经是从频道页点进来的就直接退回，不再往页面栈里塞第二份频道页（小程序栈深 10 层，
   * 两页来回点几次就会把栈占满，之后任何 navigateTo 都会静默失败）。
   */
  onGoChannels() {
    const pages = getCurrentPages();
    const prev = pages[pages.length - 2];
    if (prev && prev.route === 'pages/channels/channels') {
      wx.navigateBack();
    } else {
      wx.navigateTo({ url: '/pages/channels/channels' });
    }
    trackEvent('preferred', 'open_channels', 'channels');
  },
});
