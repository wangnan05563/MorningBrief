/**
 * 收藏列表页：展示用户收藏的节目，点击跳详情，长按取消收藏
 *
 * 数据流：
 * - getFavorites 仅返回 [{episode_id, created_at}]，需逐个拉详情拼装展示
 * - 收藏数通常较小（几十量级），用 Promise.all 并发拉详情，避免串行等待
 *
 * 与 detail 页的同步：detail 页 onShow 会重新拉取收藏态，
 * 故此处取消收藏后跳转/返回 detail 页时按钮文案会自动同步
 */
const { getFavorites, removeFavorite, fetchEpisodeDetail } = require('../../services/api');

Page({
  data: {
    list: [],          // 已拼装详情的收藏列表
    loading: true,     // 首次加载态
    removing: false,   // 删除请求中（防重复）
  },

  onLoad() {
    // 标记首次 onShow 由 onLoad 触发的加载覆盖，避免重复请求
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
   * 加载收藏列表并拼装节目详情
   * @param {boolean} silent - 静默刷新（不展示 loading 遮罩）
   */
  async loadFavorites(silent) {
    if (!silent) this.setData({ loading: true });
    try {
      const res = await getFavorites();
      const items = (res && res.items) || [];

      // 并发拉取每个节目的详情；单个失败时不影响其他项展示
      const details = await Promise.all(
        items.map((it) =>
          fetchEpisodeDetail(it.episode_id)
            .then((ep) => ({
              ...ep,
              favorited_at: it.created_at,
            }))
            .catch(() => ({
              // 详情拉取失败（如节目已下架）也保留条目，便于用户取消收藏
              id: it.episode_id,
              title: '节目信息加载失败',
              favorited_at: it.created_at,
              _unavailable: true,
            }))
        )
      );

      this.setData({ list: details, loading: false });
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
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
  },

  /**
   * 长按列表项弹出取消收藏选项
   * 用 actionSheet 而非左滑组件：实现简单且符合小程序惯例交互
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
      const newList = this.data.list.filter((it) => it.id !== episodeId);
      this.setData({ list: newList, removing: false });
      wx.hideLoading();
      wx.showToast({ title: '已取消收藏', icon: 'none' });
    } catch (err) {
      this.setData({ removing: false });
      wx.hideLoading();
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },
});
