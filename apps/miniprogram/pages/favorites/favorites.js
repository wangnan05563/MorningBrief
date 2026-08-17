/**
 * 收藏列表页：展示用户收藏的节目，点击跳详情，长按取消收藏
 *
 * V1.3 优化：
 * - 后端 /favorites 已 LEFT JOIN episode 详情，前端无需 N+1 拉取
 * - 兼容旧响应字段：优先用 list，回退到 items
 * - 接入埋点（FR-SUP-10）
 */
// localData 封装收藏的双写（本地+后端），按 openid 隔离，读取优先本地
const localData = require('../../services/local-data');
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
   * 加载收藏列表（优先本地，本地无时从后端读取并缓存）
   * @param {boolean} silent - 静默刷新（不展示 loading 遮罩）
   */
  async loadFavorites(silent) {
    if (!silent) this.setData({ loading: true });
    try {
      const items = await localData.getFavoriteList();
      // 本地收藏项存的是 id（见 local-data.addFavorite），后端项带 episode_id；
      // 而 wxml 的 data-id 与 wx:key 都绑 item.episode_id，本地项 episode_id 缺失会导致
      // 点击/长按整行失效、列表 key 不稳定（评审 HIGH #2）。统一归一化 episode_id。
      const list = items.map((it) => ({ ...it, episode_id: it.episode_id ?? it.id }));
      this.setData({ list, loading: false });
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
   * 调用接口移除收藏并更新本地列表（双写本地+后端）
   * 本地直接过滤掉目标项，避免再次全量拉取
   */
  async removeFavorite(episodeId, title) {
    this.setData({ removing: true });
    wx.showLoading({ title: '取消中...' });
    try {
      await localData.removeFavorite(episodeId);
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
