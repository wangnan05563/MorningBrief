/**
 * 收藏列表页：展示用户收藏的节目，点击跳详情，长按取消收藏
 *
 * V1.3 优化：
 * - 后端 /favorites 已 LEFT JOIN episode 详情，前端无需 N+1 拉取
 * - 兼容旧响应字段：优先用 list，回退到 items
 * - 接入埋点（FR-SUP-10）
 */
const { getFavorites, removeFavorite } = require('../../services/api');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    list: [],          // 已拼装详情的收藏列表
    loading: true,     // 首次加载态
    removing: false,   // 删除请求中（防重复）
  },

  onLoad() {
    trackPageView('pages/favorites/favorites');
    this._firstShow = true;
    this.loadFavorites();
  },

  /**
   * 下拉刷新：重新拉取收藏列表
   */
  onPullDownRefresh() {
    this.loadFavorites().then(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 从 detail 页返回时刷新，确保新增收藏能即时显示
   * 首次 onShow 由 onLoad 已覆盖，跳过；后续 onShow 静默刷新
   */
  onShow() {
    if (this._firstShow) {
      this._firstShow = false;
      return;
    }
    this.loadFavorites(true);
  },

  /**
   * 加载收藏列表
   * 后端已 join episode 详情，前端直接使用，无需逐个拉详情
   * @param {boolean} silent - 静默刷新（不展示 loading 遮罩）
   */
  async loadFavorites(silent) {
    if (!silent) this.setData({ loading: true });
    try {
      const res = await getFavorites();
      // 兼容 list / items 两种字段名（旧版后端用 items）
      const items = (res && (res.list || res.items)) || [];

      this.setData({ list: items, loading: false });
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    }
  },

  /**
   * 点击列表项跳转详情页
   */
  onTapItem(e) {
    const { id } = e.currentTarget.dataset;
    if (!id) return;
    trackEvent('favorites', 'tap_item', 'episode_' + id);
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
  },

  /**
   * 长按列表项弹出取消收藏选项
   */
  onLongPressItem(e) {
    if (this.data.removing) return;
    const { id, title } = e.currentTarget.dataset;
    if (!id) return;

    wx.showActionSheet({
      itemList: ['取消收藏'],
      itemColor: '#FF6B8A',
      success: (res) => {
        if (res.tapIndex === 0) this.removeFavorite(id, title);
      },
    });
  },

  /**
   * 调用接口移除收藏并更新本地列表
   * 本地直接过滤掉目标项，避免再次全量拉取
   */
  async removeFavorite(episodeId, title) {
    this.setData({ removing: true });
    wx.showLoading({ title: '取消中...' });
    try {
      await removeFavorite(episodeId);
      const newList = this.data.list.filter((it) => it.episode_id !== episodeId && it.id !== episodeId);
      this.setData({ list: newList, removing: false });
      wx.hideLoading();
      wx.showToast({ title: '已取消收藏', icon: 'none' });
      trackEvent('favorites', 'remove', 'episode_' + episodeId);
    } catch (err) {
      this.setData({ removing: false });
      wx.hideLoading();
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },
});
