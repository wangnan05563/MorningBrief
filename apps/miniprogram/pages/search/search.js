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
// 频道类型 → 文案/皮肤映射（FR-MC-08）：搜索结果类型标签按类型取值
const skin = require('../../utils/skin');

const STORAGE_KEY_HISTORY = 'search_history';
const DEBOUNCE_MS = 300;

// 类型筛选选项（FR-MC-07）：全部 / 资讯 / 课程
// audiobook 并入课程类展示（与首页分组一致）
const FILTER_OPTIONS = [
  { type: 'all', label: '全部' },
  { type: 'news', label: '资讯' },
  { type: 'course', label: '课程' },
];

Page({
  data: {
    keyword: '',
    results: [],
    loading: false,
    history: [],         // 搜索历史
    showHistory: true,   // 是否展示搜索历史（输入时隐藏）
    page: 1,
    hasMore: false,
    filterType: 'all',   // 当前类型筛选（FR-MC-07）
    filterOptions: FILTER_OPTIONS,
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
    // 非关键写入（搜索历史缓存）：改异步避免阻塞主线程，失败仅告警
    wx.setStorage({
      key: STORAGE_KEY_HISTORY,
      data: list,
      fail: (e) => console.warn('[search] 搜索历史写入失败:', e && e.errMsg),
    });
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
      // FR-MC-07：按当前类型筛选透传后端 channel_type（全部则不传）
      const chType = this.data.filterType === 'all' ? null : this.data.filterType;
      const res = await searchEpisodes(keyword, page, 20, chType);
      const items = (res.list || []).map((it) => ({
        ...it,
        // 类型标签：未知/缺失回退资讯（防御式兜底，与 skin 一致）
        type_label: skin.getChannelTypeLabel(it.channel_type),
      }));
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
   * 切换类型筛选（FR-MC-07）：重置分页后重新搜索
   */
  onFilterType(e) {
    const type = e.currentTarget.dataset.type;
    if (type === this.data.filterType) return;
    this.setData({ filterType: type });
    trackEvent('search', 'filter_type', type);
    // 有搜索词时立即按新类型重搜；无词时仅更新筛选态（结果区仍隐藏）
    if (this.data.keyword) {
      this.doSearch(this.data.keyword, 1);
    }
  },

  /**
   * 点击搜索结果：设置队列并跳转
   * FR-MC-07：课程类结果跳转课程主页（复用既有课程链路），资讯类跳详情页
   */
  onTapResult(e) {
    const { id, index } = e.currentTarget.dataset;
    const idx = Number(index) || 0;
    const item = this.data.results[idx] || {};
    if (this.data.results.length > 0) {
      setQueue(this.data.results, idx);
    }
    trackEvent('search', 'tap_result', 'episode_' + id);
    const type = item.channel_type || 'news';
    if (type !== 'news' && item.channel_id) {
      // 课程/有声书：跳课程主页（频道级 chapters 聚合页）
      wx.navigateTo({ url: '/pages/course/course?channelId=' + item.channel_id });
    } else {
      wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
    }
  },

  /**
   * 上拉加载更多
   */
  onReachBottom() {
    if (!this.data.hasMore || this.data.loading) return;
    this.doSearch(this.data.keyword, this.data.page + 1);
  },
});
