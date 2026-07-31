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
  },

  onLoad(query) {
    trackPageView('pages/preferred-settings/preferred-settings');
    this.setData({ isOnboarding: query && query.from === 'onboarding' });
    this.loadChannels();
  },

  async loadChannels() {
    this.setData({ loading: true });
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
      });
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    }
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
    });
  },

  /**
   * 保存偏爱频道设置
   * 全量覆盖本地存储，并通过 globalData 通知今日/历史页刷新
   */
  onSave() {
    const selectedIds = this.data.channels
      .filter((ch) => ch.selected)
      .map((ch) => ch.id);
    localData.setPreferredChannels(selectedIds);
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
    const allSelected = this.data.channels.every((ch) => ch.selected);
    const newSelected = !allSelected;
    const channels = this.data.channels.map((ch) => ({ ...ch, selected: newSelected }));
    this.setData({
      channels,
      selectedCount: newSelected ? channels.length : 0,
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
});
