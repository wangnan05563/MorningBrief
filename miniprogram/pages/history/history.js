/**
 * 历史列表页：分页加载往期节目，点击跳转详情页播放
 *
 * 分页：上拉加载更多（onReachBottom）+ 下拉刷新（onPullDownRefresh）
 */
const { fetchHistory } = require('../../services/api');

Page({
  data: {
    list: [],          // 历史节目列表
    page: 1,           // 当前页码（下次请求的页）
    size: 20,          // 每页条数
    total: 0,          // 总条数
    loading: false,    // 加载中（防止重复请求）
    hasMore: true,     // 是否还有更多
  },

  onLoad() {
    this.loadHistory(true);
  },

  /**
   * 分页加载历史列表
   * @param {boolean} first - true=重置第1页（下拉刷新/首次），false=加载下一页
   */
  async loadHistory(first) {
    // 防止重复请求（上拉和下拉同时触发）
    if (this.data.loading) return;

    // 重置第1页：清空列表 + 回到第1页
    if (first) {
      this.setData({ list: [], page: 1, hasMore: true });
    }

    // 非首次且没有更多数据时不再请求
    if (!this.data.hasMore && !first) return;

    this.setData({ loading: true });

    try {
      const res = await fetchHistory(this.data.page, this.data.size);
      // 兼容 list / items 两种返回字段名
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

  /**
   * 上拉加载更多
   */
  onReachBottom() {
    this.loadHistory(false);
  },

  /**
   * 下拉刷新：重置第1页
   */
  onPullDownRefresh() {
    this.loadHistory(true).then(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 点击节目跳转详情页播放
   */
  onPlay(e) {
    const { id } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`,
    });
  },
});
