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
const { fetchHistory, fetchChannels } = require('../../services/api');
// localData 封装播放进度/历史的双写（本地+后端），按 openid 隔离
const localData = require('../../services/local-data');
const { setQueue, playEpisode, setPendingSeek, safePlay, getCurrentEpisode, onPlaybackChange } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');
// T00599：加载态控制器（最短骨架展示 + 慢加载提示 + 超时重试）
const { createLoadingController } = require('../../utils/loading');
// T02510：切回底部导航时刷新「历史」tab 的队列待播角标
const { refreshTabBadge } = require('../../utils/tab-badge');

// 分页渲染步长：每次 onReachBottom 增量渲染的项数
// 选 20 与 size 对齐：单次分页加载的数据量与单次渲染增量一致，
// 既能让新加载的 20 条立即可见，又能把单次 setData 的渲染量控制在 20 项以内
const RENDER_STEP = 20;

Page({
  data: {
    // list 保留完整数据（用于 setQueue 等需要完整列表的场景），但渲染时只取 renderList
    list: [],
    // 实际传给 wxml 渲染的子集 = list.slice(0, renderCount)
    // 避免几百条数据一次性进入渲染层导致卡顿
    renderList: [],
    renderCount: RENDER_STEP,
    page: 1,
    size: 20,
    total: 0,
    loading: false,
    // T00599：分级加载态（由 utils/loading.js 控制器维护；仅首屏骨架期有效）
    loadingSlow: false,
    loadingTimedOut: false,
    hasMore: true,
    // V1.3 新增
    channels: [],
    currentChannelId: null,
    // 任务7：排序，'desc' = 倒序（默认），'asc' = 正序
    sortOrder: 'desc',
    // 任务6：上次播放（用于"继续播放"按钮）
    lastPlayedEpisode: null,
    // 已播放过的节目 id 集合（{ [id]: true }），用于列表行渲染"已播放"视觉标注
    playedSet: {},
    // T00767：列表过滤模式（单按钮循环）all=全部 / unplayed=未播 / played=已播
    filterMode: 'all',
    // T00767：过滤模式下无匹配（全量列表有数据但视图为空），wxml 据此展示专用空态
    filterEmpty: false,
    // "我的偏爱"模式：channel-pill 末尾的"我的偏爱"项用特殊 id 'preferred' 标识
    // 切换到该项时 isPreferredMode=true，currentChannelId 同步设为 'preferred'（仅用于 pill 高亮）
    // 数据拉取走 loadHistory 内的本地过滤分支：fetchHistory 拉全部频道，再按 preferredIds 过滤
    isPreferredMode: false,
    preferredIds: [],       // 用户偏爱的频道 ID 数组（本地存储镜像）
    preferredEmpty: false,  // 偏爱频道未设置时为 true，用于显示引导设置提示
    // 播放状态镜像（与悬浮播放器同步）：onPlaybackChange 订阅后实时更新
    // 为什么需要：历史页顶部的'继续播放'卡片图标需随播放/暂停切换，与悬浮玩家保持一致
    isPlaying: false,
    currentEpisodeId: null,
  },

  onLoad() {
    // T00599：加载态控制器（onUnload 需 cancel）
    this._lc = createLoadingController({ setData: this.setData.bind(this) });
    trackPageView('pages/history/history');
    this.loadChannels();
    this.loadHistory(true);
    this.loadLastPlayed();
    // 拉取最近播放记录标记已播放节目（与 loadHistory 并行，互不阻塞首屏）
    this.loadPlayedHistory();
    // 镜像本地偏爱频道 ID 到 data，便于"我的偏爱"模式下快速过滤
    this.setData({ preferredIds: localData.getPreferredChannels() });
    // 订阅播放状态变更（只订阅一次，与 index 页同款）：
    // 为什么放 onLoad 而非 onShow：onShow 每次切 tab 都触发，重复订阅会导致回调叠加
    this._unsubPlayback = onPlaybackChange(() => this.syncPlayerState());
  },

  onShow() {
    // 进入页面时立即同步一次播放状态，避免从详情页返回时图标状态滞后
    this.syncPlayerState();
    // T02510：「历史」tab 正是队列角标的挂载位，回到本页时立刻校准
    refreshTabBadge();
    // 从详情页返回时重新读取续播缓存，确保"继续播放"卡片反映最新进度（评审 MEDIUM A6）
    this.loadLastPlayed();
    // 从详情页返回时刷新已播放标记（详情页可能播完了新节目）
    // 节流由 services/api.js 的 fetchRecentPlaylogs throttle 统一处理，
    // 页面层不再维护各自的 30s 时间戳，避免 tab 切换时多页面节流状态不一致
    this.loadPlayedHistory();
    // 每次 onShow 都从 localData 同步最新的偏爱频道 ID：
    // - 从其他 tab 切换回来时，localData 可能已被其他页面更新
    // - 刚从 preferred-settings 返回时，也能拿到最新值
    const latestPreferredIds = localData.getPreferredChannels();
    const app = getApp();
    // 判断是否需要重新加载"我的偏爱"数据：
    // 条件1：偏爱频道设置时间戳变化（刚从 settings 页保存返回）
    // 条件2：preferredIds 与最新值不一致（其他页面修改了偏爱）
    const preferredChangedByTs = this._lastPreferredTs && this._lastPreferredTs !== app.globalData.preferredChannelsChanged;
    const preferredIdsDiffers = JSON.stringify(this.data.preferredIds) !== JSON.stringify(latestPreferredIds);
    if (preferredChangedByTs || preferredIdsDiffers) {
      this.setData({ preferredIds: latestPreferredIds });
    }
    // 偏爱模式下每次切回都要刷新：
    // 为什么：从其他tab切换回来时，list/renderList 可能残留了非偏爱频道的数据，
    // 或者 preferredIds 刚从空变为有值，必须重新加载才能正确展示
    if (this.data.isPreferredMode) {
      this.loadHistory(true);
    }
    this._lastPreferredTs = app.globalData.preferredChannelsChanged;
  },

  /**
   * 加载频道列表
   * 「我的偏爱」前置到首位：用户期望最显眼位置，置于「全部」之前
   * id 用字符串 'preferred' 标识，与数字频道 id 区分
   */
  async loadChannels() {
    try {
      const res = await fetchChannels();
      const channels = [
        { id: 'preferred', name: '我的偏爱' },
        { id: null, name: '全部' },
        ...(res.list || []),
      ];
      this.setData({ channels });
    } catch (err) {
      console.warn('加载频道列表失败:', err.message);
    }
  },

  /**
   * 切换频道：重新拉取该频道历史
   * 'preferred' 是特殊值，进入"我的偏爱"模式（拉全部 + 本地过滤）
   * 切换时必须清空关联状态（list/lastPlayedEpisode），避免旧频道数据残留（R83）
   */
  async onSwitchChannel(e) {
    const rawId = e.currentTarget.dataset.id;
    const channelId = (rawId !== undefined && rawId !== null && rawId !== '') ? rawId : null;
    if (channelId === this.data.currentChannelId) return;
    // 先清空关联状态再 fetch，避免旧频道列表与续播卡片残留造成视觉串台
    // renderList/renderCount 同步重置，否则旧频道的渲染子集会残留
    this._allList = []; // T00767：全量列表同步清空，防旧频道数据串入过滤视图
    this.setData({
      currentChannelId: channelId,
      isPreferredMode: channelId === 'preferred',
      list: [],
      renderList: [],
      renderCount: RENDER_STEP,
      lastPlayedEpisode: null,
      page: 1,
      hasMore: true,
      preferredEmpty: false,
    });
    trackEvent('history', 'switch_channel', '', String(channelId || ''));
    await this.loadHistory(true);
  },

  /**
   * 分页加载历史列表
   * @param {boolean} first - true=重置第1页（下拉刷新/首次），false=加载下一页
   *
   * "我的偏爱"模式（isPreferredMode=true）下的过滤策略：
   * - 后端 fetchHistory 拉全部频道（channelId=null），本地按 preferredIds 过滤
   * - 由于过滤会导致每页有效条数减少，简单方案：单次拉取一页过滤后渲染，
   *   允许页面显示较少项；用户上拉加载更多时会自动拉取下一页继续过滤
   * - 未设置偏爱频道（preferredIds.length===0）时直接显示引导设置提示，不请求
   */
  async loadHistory(first) {
    if (this.data.loading) return;

    // 从 localData 读取最新的偏爱频道 ID：
    // 为什么不用 this.data.preferredIds：onShow 与 loadHistory 之间可能存在状态异步更新窗口，
    // 直接读本地存储确保拿到的是最新值，避免"设置了偏爱但仍显示空列表"的问题
    const preferredIds = this.data.isPreferredMode ? localData.getPreferredChannels() : this.data.preferredIds;
    // 同步 data 中的镜像，确保 wxml 渲染也使用最新值
    if (JSON.stringify(this.data.preferredIds) !== JSON.stringify(preferredIds)) {
      this.setData({ preferredIds });
    }

    // 偏爱模式 + 未设置偏爱频道：直接展示引导提示，不发请求
    if (this.data.isPreferredMode && preferredIds.length === 0) {
      this._allList = []; // T00767：全量列表同步清空
      this.setData({
        list: [],
        renderList: [],
        renderCount: RENDER_STEP,
        page: 1,
        hasMore: false,
        preferredEmpty: true,
        filterEmpty: false,
      });
      // 本地即刻决策、无网络等待：不留最短展示时长
      this._lc.finish(true);
      return;
    }

    if (first) {
      // 重置渲染状态：renderList 清空、renderCount 回到初始步长
      this._allList = []; // T00767：首屏重置同步清空全量列表
      this.setData({ list: [], renderList: [], renderCount: RENDER_STEP, page: 1, hasMore: true, preferredEmpty: false, filterEmpty: false });
    }
    if (!this.data.hasMore && !first) return;

    // T00599：start() 置加载态并启动分级计时（首屏骨架期生效）
    this._lc.start();

    try {
      // 偏爱模式下传 channelId=null 拉全部频道，本地再按 preferredIds 过滤
      const fetchChannelId = this.data.isPreferredMode ? null : this.data.currentChannelId;
      const res = await fetchHistory(this.data.page, this.data.size, fetchChannelId, this.data.sortOrder);
      let items = res.list || res.items || [];

      // 偏爱模式本地过滤：保留 channel_id 在 preferredIds 中的项
      if (this.data.isPreferredMode && items.length > 0 && preferredIds.length > 0) {
        const idSet = new Set(preferredIds);
        items = items.filter(ep => idSet.has(ep.channel_id));
      }

      // 任务1：补充 channel_name + 规范化 title（历史节目也可能没有频道名）
      const enriched = items.map(ep => this._enrichEpisode(ep));
      // T00767：全量列表存 _allList（不进 data，避免整表渲染）；list 仅存按过滤模式
      // 过滤后的视图，渲染子集由 _applyFilter 统一计算
      const newList = first ? enriched : (this._allList || []).concat(enriched);
      this._allList = newList;

      this.setData({
        total: res.total || 0,
        // 偏爱模式下 hasMore 不能用 newList.length < total 判断（total 是未过滤的总数）
        // 改用本次是否拉到完整一页 + 后端是否还有更多来判断
        hasMore: this.data.isPreferredMode
          ? ((res.list || []).length >= this.data.size && newList.length < (res.total || 0))
          : newList.length < (res.total || 0),
        page: this.data.page + 1,
        // 偏爱模式下过滤后为空，显示"偏爱频道暂无历史节目"空状态（preferredEmpty=false时走通用空态）
        preferredEmpty: this.data.isPreferredMode && newList.length === 0,
      });
      // T00767：视图列表/渲染子集/过滤空态统一由 _applyFilter 计算
      this._applyFilter();
      // T00599：首屏走最短展示保护（消除骨架一闪）；上拉加载更多无骨架，立即收起
      this._lc.finish(!first);
    } catch (err) {
      this._lc.fail();
      wx.showToast({
        title: err.message || '加载失败',
        icon: 'none',
      });
    }
  },

  /** T00599：慢加载超时后的重试入口（骨架下方"重试"按钮） */
  onRetryLoad() {
    this.loadHistory(true);
  },

  /**
   * T00767：按过滤模式（all/unplayed/played）重算视图列表
   * 全量数据存 this._allList（不进 data），list 仅存过滤后的视图；
   * 渲染子集策略与原实现一致（renderList = list.slice(0, renderCount)，步长 RENDER_STEP）
   */
  _applyFilter() {
    const all = this._allList || [];
    const mode = this.data.filterMode;
    const played = this.data.playedSet || {};
    const view = mode === 'all'
      ? all
      : all.filter(ep => (mode === 'played' ? !!played[ep.id] : !played[ep.id]));
    const renderCount = Math.min(RENDER_STEP, view.length);
    this.setData({
      list: view,
      renderList: view.slice(0, renderCount),
      renderCount,
      filterEmpty: mode !== 'all' && all.length > 0 && view.length === 0,
    });
  },

  /**
   * T00767：过滤按钮——单按钮循环 全部 → 未播 → 已播 → 全部
   * 切换后本地过滤已加载数据；上拉到底自动拉下一页补充（onReachBottom 链路不变）
   */
  onToggleFilter() {
    const next = this.data.filterMode === 'all' ? 'unplayed'
      : this.data.filterMode === 'unplayed' ? 'played' : 'all';
    this.setData({ filterMode: next });
    trackEvent('history', 'filter', '', next);
    this._applyFilter();
  },

  onReachBottom() {
    // 分页渲染优化：先消耗已加载但未渲染的尾部数据，避免每次到底部都触发网络请求
    // 例如 loadHistory(false) 一次拉 20 条但 renderCount 可能只 +20，二者步长对齐时基本走 else 分支
    if (this.data.renderCount < this.data.list.length) {
      const nextCount = Math.min(this.data.renderCount + RENDER_STEP, this.data.list.length);
      this.setData({
        renderCount: nextCount,
        renderList: this.data.list.slice(0, nextCount),
      });
      // 渲染已耗尽已加载项，且后端还有更多：预加载下一页，减少下次到底部的等待
      if (nextCount >= this.data.list.length && this.data.hasMore) {
        this.loadHistory(false);
      }
      return;
    }
    // 已渲染项已耗尽 list，触发分页加载
    this.loadHistory(false);
  },

  onPullDownRefresh() {
    this.loadHistory(true).then(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 点击节目：设置播放队列（自动连播）+ 立即播放 + 跳转详情页
   *
   * 队列从当前列表当前项开始，便于顺序连播后续节目。
   * playEpisode 内部会查询上次进度并断点续播（pendingSeek 机制）。
   */
  onPlay(e) {
    const { id, index } = e.currentTarget.dataset;
    const idx = Number(index) || 0;
    // 设置队列：从点击项开始，后续节目自动连播
    if (this.data.list.length > 0) {
      setQueue(this.data.list, idx);
    }
    // 立即播放该节目（playEpisode 会自动处理断点续播）
    const ep = this.data.list.find(x => x.id === id);
    if (ep) {
      playEpisode(ep);
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
      // 已播放标记：playedSet 中存在的 id 标为已播放，供 wxml 渲染视觉标注
      played: !!this.data.playedSet[ep.id],
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
   * 跳转偏爱频道设置页（"我的偏爱"未设置时的引导按钮）
   */
  onTapPreferredSettings() {
    wx.navigateTo({ url: '/pages/preferred-settings/preferred-settings' });
    trackEvent('history', 'tap_preferred_settings');
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
   * 优先用本地缓存（含 currentTime），缺失时从后端读取
   * localData 优先本地，本地无时自动从后端读取并缓存
   */
  async loadLastPlayed() {
    try {
      const cached = wx.getStorageSync('lastPlayedEpisode');
      if (cached && cached.id) {
        this.setData({ lastPlayedEpisode: cached });
        // 异步从后端补齐进度（localData.getProgress 优先本地，本地无时从后端读）
        localData.getProgress(cached.id).then((progress) => {
          if (progress && progress.position > 0) {
            const enriched = { ...cached, currentTime: progress.position };
            this.setData({ lastPlayedEpisode: enriched });
            // 非关键写入（续播缓存）：改异步避免阻塞主线程，失败仅告警
            wx.setStorage({
              key: 'lastPlayedEpisode',
              data: enriched,
              fail: (e) => console.warn('[history] lastPlayed 写入失败:', e && e.errMsg),
            });
          }
        }).catch(() => {});
        return;
      }
      // 本地无缓存：从本地历史列表取第一条（localData 优先本地，缺失时读后端）
      const recent = await localData.getHistory(1, 1);
      const recentItem = (recent.list || [])[0];
      if (recentItem && recentItem.id) {
        const progress = await localData.getProgress(recentItem.id);
        const currentTime = (progress && progress.position) || recentItem.position || 0;
        if (currentTime > 0) {
          // 从当前列表中查找匹配项，否则用 recentItem 兜底
          const list = this.data.list;
          const matched = list.find(e => e.id === recentItem.id);
          const last = {
            ...(matched || { id: recentItem.id, title: recentItem.title || '上次的节目' }),
            currentTime,
          };
          this.setData({ lastPlayedEpisode: last });
          // 非关键写入（续播缓存）：改异步避免阻塞主线程，失败仅告警
          wx.setStorage({
            key: 'lastPlayedEpisode',
            data: last,
            fail: (e) => console.warn('[history] lastPlayed 写入失败:', e && e.errMsg),
          });
        }
      }
    } catch (err) {
      // 静默失败：续播按钮非核心
    }
  },

  /**
   * 拉取最近播放记录，构造已播放 id 集合（playedSet），并刷新历史列表的 played 标记
   * 用于在历史列表行上展示"已播放"视觉反馈
   * 优先本地历史，本地无时从后端读取
   */
  async loadPlayedHistory() {
    try {
      const playedIds = await localData.getPlayedHistorySet();
      const playedSet = {};
      playedIds.forEach(id => { playedSet[id] = true; });
      this.setData({ playedSet });
      // 已播放集合就绪后，重新 enrich 全量列表以填充 played 字段，再按过滤模式重算视图
      // （T00767：过滤视图的已播/未播判定直接依赖 playedSet，必须联动刷新）
      if (this._allList && this._allList.length > 0) {
        this._allList = this._allList.map(ep => this._enrichEpisode(ep));
      }
      if (this._allList) {
        this._applyFilter();
      }
    } catch (err) {
      // 静默失败：已播放标记非核心
    }
  },

  /**
   * 任务6：点击继续播放——把历史列表从该节目开始设为队列，跳转到详情页
   * 历史页与今日页区别：可以按顺序播放新闻历史
   *
   * 必须调用 playEpisode 触发实际播放（R84），否则用户跳转后看到详情页未播放，
   * 需要再点一次播放按钮，与"继续播放"的语义不符。
   */
  onTapContinue() {
    const last = this.data.lastPlayedEpisode;
    if (!last) return;
    trackEvent('history', 'continue_play', 'episode_' + last.id);
    const player = getApp().globalData.player;
    const current = getCurrentEpisode();
    // 当前正在播放的就是该节目：暂停（与悬浮玩家按钮一致，避免点击继续播放反而重启）
    if (current && current.id === last.id && player && !player.paused) {
      player.pause();
      return;
    }
    // 暂停中的就是该节目：恢复播放，不跳转详情页（让用户继续浏览历史列表）
    if (current && current.id === last.id && player && player.paused) {
      safePlay();
      return;
    }
    // 切换到新节目：从历史列表中找到该节目，从其位置开始建立播放队列
    const list = this.data.list;
    const idx = list.findIndex(e => e.id === last.id);
    if (idx >= 0 && list.length > 0) {
      setQueue(list, idx);
    }
    // 触发实际播放：playEpisode 内部会自动 fetchPlayProgress 断点续播
    playEpisode(last);
    // 跳转到详情页，详情页 onShow 会同步 isPlaying 状态
    wx.navigateTo({
      url: `/pages/detail/detail?id=${last.id}`,
    });
  },

  /**
   * 同步播放器状态到 data（由 onPlaybackChange 订阅触发）
   * 与 index 页 syncPlayerState 同款：仅镜像 isPlaying + currentEpisodeId，
   * 用于 continue-card 图标随播放/暂停切换
   */
  syncPlayerState() {
    const player = getApp().globalData.player;
    if (!player) return;
    const ep = getCurrentEpisode();
    this.setData({
      isPlaying: !player.paused,
      currentEpisodeId: ep ? ep.id : null,
    });
  },

  onUnload() {
    // T00599：清理加载态计时器，避免页面销毁后仍 setData
    if (this._lc) this._lc.cancel();
    if (this._unsubPlayback) {
      this._unsubPlayback();
      this._unsubPlayback = null;
    }
  },
});
