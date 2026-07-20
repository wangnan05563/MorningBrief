/**
 * 历史列表页：分页加载往期节目，点击跳转详情页播放
 *
 * V1.3 新增：
 * - 频道过滤（FR-SUP-03）：顶部胶囊切换频道
 * - 搜索入口（FR-SUP-04）
 * - 播放队列：点击节目时设置队列，支持自动连播
 * - 埋点（FR-SUP-10）
 *
 * 分页：上拉加载更多（onReachBottom）+ 下拉刷新（onPullDownRefresh）
 */
const { fetchHistory, fetchChannels, fetchPlayProgress, fetchRecentPlaylogs } = require('../../services/api');
const { setQueue, playEpisode } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    list: [],
    page: 1,
    size: 20,
    total: 0,
    loading: false,
    hasMore: true,
    // V1.3 新增
    channels: [],
    currentChannelId: null,
    // 任务7：排序，'desc' = 倒序（默认），'asc' = 正序
    sortOrder: 'desc',
    // 任务6：上次播放（用于"继续播放"按钮）
    lastPlayedEpisode: null,
  },

  onLoad() {
    trackPageView('pages/history/history');
    this.loadChannels();
    this.loadHistory(true);
    this.loadLastPlayed();
  },

  /**
   * 加载频道列表
   */
  async loadChannels() {
    try {
      const res = await fetchChannels();
      const channels = [{ id: null, name: '全部' }, ...(res.list || [])];
      this.setData({ channels });
    } catch (err) {
      console.log('加载频道列表失败:', err.message);
    }
  },

  /**
   * 切换频道：重新拉取该频道历史
   */
  async onSwitchChannel(e) {
    const channelId = e.currentTarget.dataset.id || null;
    if (channelId === this.data.currentChannelId) return;
    this.setData({ currentChannelId: channelId });
    trackEvent('history', 'switch_channel', '', channelId || 0);
    await this.loadHistory(true);
  },

  /**
   * 分页加载历史列表
   * @param {boolean} first - true=重置第1页（下拉刷新/首次），false=加载下一页
   */
  async loadHistory(first) {
    if (this.data.loading) return;
    if (first) {
      this.setData({ list: [], page: 1, hasMore: true });
    }
    if (!this.data.hasMore && !first) return;

    this.setData({ loading: true });

    try {
      const res = await fetchHistory(this.data.page, this.data.size, this.data.currentChannelId, this.data.sortOrder);
      const items = res.list || res.items || [];
      // 任务1：补充 channel_name + 规范化 title（历史节目也可能没有频道名）
      const enriched = items.map(ep => this._enrichEpisode(ep));
      const newList = first ? enriched : this.data.list.concat(enriched);

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

  onReachBottom() {
    this.loadHistory(false);
  },

  onPullDownRefresh() {
    this.loadHistory(true).then(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 点击节目：设置播放队列（自动连播）+ 跳转详情页
   * 队列从当前列表当前项开始，便于顺序连播后续节目
   */
  onPlay(e) {
    const { id, index } = e.currentTarget.dataset;
    const idx = Number(index) || 0;
    // 设置队列：从点击项开始，后续节目自动连播
    if (this.data.list.length > 0) {
      setQueue(this.data.list, idx);
    }
    trackEvent('history', 'play', 'episode_' + id);
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`,
    });
  },

  /**
   * 节目对象增强：补充 channel_name / date_label / duration_label
   * 与 index 页 _enrichEpisode 同款逻辑，统一两页的卡片展示字段
   * （如需调整请同步两处）
   */
  _enrichEpisode(ep) {
    if (!ep) return ep;
    let channelName = ep.channel_name || '';
    if (!channelName) {
      const ch = this.data.channels.find(c => c.id === ep.channel_id);
      channelName = ch ? ch.name : '';
    }
    const dateLabel = this._formatDateZh(ep.date);
    const looksGeneric = !ep.title
      || ep.title.includes('今日要闻')
      || /^\d+月\d+日\s*[·•・]\s*今日要闻?$/.test(ep.title)
      || /^\d+月\d+日\s*今日要闻?$/.test(ep.title);
    let title = ep.title;
    if (looksGeneric && channelName) {
      title = dateLabel + (dateLabel ? ' · ' : '') + channelName;
    }
    return {
      ...ep,
      channel_name: channelName,
      date_label: dateLabel,
      title,
      duration_label: this._formatDuration(ep.duration || 0),
    };
  },

  /**
   * 日期格式化为中文 "7月20日"，与 index 页一致
   * 接受 'YYYY-MM-DD' 字符串或 Date 对象
   */
  _formatDateZh(d) {
    if (!d) return '';
    const date = d instanceof Date ? d : new Date(d);
    if (Number.isNaN(date.getTime())) return String(d);
    return (date.getMonth() + 1) + '月' + date.getDate() + '日';
  },

  /**
   * 秒数 → "mm:ss"，与 index 页一致
   */
  _formatDuration(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
  },

  /**
   * 跳转搜索页
   */
  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' });
    trackEvent('history', 'tap_search');
  },

  /**
   * 任务7：切换排序（日期正/倒序）
   * 历史列表默认按日期倒序（最新在前），点击切换为正序（最旧在前）
   */
  onToggleSort() {
    const next = this.data.sortOrder === 'desc' ? 'asc' : 'desc';
    this.setData({ sortOrder: next });
    trackEvent('history', 'toggle_sort', '', next);
    this.loadHistory(true);
  },

  /**
   * 任务6：打开播放队列页
   */
  onOpenQueue() {
    trackEvent('history', 'open_queue');
    wx.navigateTo({ url: '/pages/queue/queue' });
  },

  /**
   * 任务6：加载上次播放进度（用于"继续播放"按钮）
   * 优先用 storage 缓存（含 currentTime），缺失时回退到后端最近一条播放记录
   */
  async loadLastPlayed() {
    try {
      const cached = wx.getStorageSync('lastPlayedEpisode');
      if (cached && cached.id) {
        this.setData({ lastPlayedEpisode: cached });
        // 异步从后端补齐进度（storage 可能不是最新）
        fetchPlayProgress(cached.id).then((remote) => {
          if (remote && remote.current_time > 0) {
            const enriched = { ...cached, currentTime: remote.current_time };
            this.setData({ lastPlayedEpisode: enriched });
            wx.setStorageSync('lastPlayedEpisode', enriched);
          }
        }).catch(() => {});
        return;
      }
      // storage 无缓存：拉最近播放记录
      const recent = await fetchRecentPlaylogs(1, 1);
      const recentItem = (recent && (recent.list || recent.items || []))[0];
      if (recentItem && recentItem.episode_id && recentItem.current_time > 0) {
        // 从当前列表中查找匹配项，否则用 recentItem 兜底
        const list = this.data.list;
        const matched = list.find(e => e.id === recentItem.episode_id);
        const last = {
          ...(matched || { id: recentItem.episode_id, title: recentItem.title || '上次的节目' }),
          currentTime: recentItem.current_time,
        };
        this.setData({ lastPlayedEpisode: last });
        wx.setStorageSync('lastPlayedEpisode', last);
      }
    } catch (err) {
      // 静默失败：续播按钮非核心
    }
  },

  /**
   * 任务6：点击继续播放——把历史列表从该节目开始设为队列，跳转到详情页
   * 历史页与今日页区别：可以按顺序播放新闻历史
   */
  onTapContinue() {
    const last = this.data.lastPlayedEpisode;
    if (!last) return;
    trackEvent('history', 'continue_play', 'episode_' + last.id);
    // 从历史列表中找到该节目，从其位置开始建立播放队列
    const list = this.data.list;
    const idx = list.findIndex(e => e.id === last.id);
    if (idx >= 0 && list.length > 0) {
      setQueue(list, idx);
    }
    wx.navigateTo({
      url: `/pages/detail/detail?id=${last.id}`,
    });
  },
});
