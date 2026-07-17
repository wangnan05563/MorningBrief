/**
 * 搜索页：按关键词搜索节目
 *
 * V1.3 新增（FR-SUP-04）
 * - 输入关键词后实时搜索（300ms 防抖）
 * - 搜索历史保存到 localStorage（最多 10 条）
 * - 点击结果跳转详情页并设置播放队列
 */
const { searchEpisodes } = require('../../services/api');
const { setQueue } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

const STORAGE_KEY_HISTORY = 'search_history';
const DEBOUNCE_MS = 300;

Page({
  data: {
    keyword: '',
    results: [],
    loading: false,
    history: [],         // 搜索历史
    showHistory: true,   // 是否展示搜索历史（输入时隐藏）
    page: 1,
    hasMore: false,
  },

  onLoad() {
    trackPageView('pages/search/search');
    this.loadHistory();
  },

  /**
   * 加载本地搜索历史
   */
  loadHistory() {
    try {
      const list = wx.getStorageSync(STORAGE_KEY_HISTORY) || [];
      this.setData({ history: list });
    } catch (e) {
      this.setData({ history: [] });
    }
  },

  /**
   * 保存搜索关键词到本地历史（去重 + 最多 10 条）
   */
  saveHistory(keyword) {
    if (!keyword) return;
    let list = wx.getStorageSync(STORAGE_KEY_HISTORY) || [];
    list = list.filter((k) => k !== keyword);
    list.unshift(keyword);
    if (list.length > 10) list = list.slice(0, 10);
    wx.setStorageSync(STORAGE_KEY_HISTORY, list);
    this.setData({ history: list });
  },

  onInput(e) {
    const keyword = (e.detail.value || '').trim();
    this.setData({ keyword, showHistory: !keyword });
    // 防抖：避免每次按键都发请求
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    if (!keyword) {
      this.setData({ results: [], hasMore: false });
      return;
    }
    this._debounceTimer = setTimeout(() => {
      this.doSearch(keyword, 1);
    }, DEBOUNCE_MS);
  },

  /**
   * 执行搜索
   * @param {string} keyword
   * @param {number} page - 1 表示首页，>1 表示加载更多
   */
  async doSearch(keyword, page) {
    this.setData({ loading: true });
    try {
      const res = await searchEpisodes(keyword, page, 20);
      const items = res.list || [];
      const newList = page === 1 ? items : this.data.results.concat(items);
      this.setData({
        results: newList,
        loading: false,
        page,
        hasMore: newList.length < (res.total || 0),
      });
      // 仅首页搜索时保存到历史
      if (page === 1 && items.length > 0) {
        this.saveHistory(keyword);
      }
    } catch (err) {
      this.setData({ loading: false });
      wx.showToast({ title: err.message || '搜索失败', icon: 'none' });
    }
  },

  /**
   * 点击搜索历史项：填充关键词并立即搜索
   */
  onTapHistory(e) {
    const keyword = e.currentTarget.dataset.keyword;
    this.setData({ keyword, showHistory: false });
    this.doSearch(keyword, 1);
    trackEvent('search', 'tap_history', keyword);
  },

  /**
   * 清空搜索历史
   */
  onClearHistory() {
    wx.showModal({
      title: '清空搜索历史',
      content: '确定清空所有搜索历史？',
      confirmColor: '#FF6B8A',
      success: (res) => {
        if (res.confirm) {
          wx.removeStorageSync(STORAGE_KEY_HISTORY);
          this.setData({ history: [] });
        }
      },
    });
  },

  /**
   * 点击搜索结果：设置队列并跳转详情
   */
  onTapResult(e) {
    const { id, index } = e.currentTarget.dataset;
    const idx = Number(index) || 0;
    if (this.data.results.length > 0) {
      setQueue(this.data.results, idx);
    }
    trackEvent('search', 'tap_result', 'episode_' + id);
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
  },

  /**
   * 上拉加载更多
   */
  onReachBottom() {
    if (!this.data.hasMore || this.data.loading) return;
    this.doSearch(this.data.keyword, this.data.page + 1);
  },
});
