/**
 * 首页/播放页：展示今日节目 + 播放控制
 *
 * V1.3 新增：
 * - 频道切换（FR-SUP-03）：顶部胶囊切换不同频道今日节目
 * - 搜索入口（FR-SUP-04）：右上角搜索图标跳转搜索页
 * - 倍速控制（FR-SUP-06）：点击倍速按钮循环切换
 * - 睡眠定时器（FR-SUP-08）：预设时长快捷启动
 * - 收藏（FR-SUP-02）：收藏/取消收藏当前节目
 * - 埋点（FR-SUP-10）
 *
 * 数据流：globalData.todayEpisode（预加载）→ 页面 data → WXML 渲染
 * 播放器：使用 app.globalData.player（全局单例），页面只负责 UI 状态同步
 */
const { fetchTodayEpisode, fetchEpisodeScript, fetchChannels } = require('../../services/api');
// localData 封装收藏/进度/历史的双写（本地+后端），按 openid 隔离
const localData = require('../../services/local-data');
const { playEpisode, safePlay, setQueue, setPendingSeek, seek, getPlaybackRate, setPlaybackRate, getSleepStatus, startSleepTimer, stopSleepTimer, onSleepChange, onError, getCurrentEpisode, onPlaybackChange, onTimeUpdateChange, offTimeUpdateChange } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');
// 带 TTL 的 storage 工具：lastPlayedEpisode 是续播缓存，7 天后自动过期清理
const { setWithTTL, getWithTTL } = require('../../utils/storage');

// lastPlayedEpisode 缓存有效期：7 天
// 为什么：用户长期不打开 app 后，旧节目的续播进度已无意义，过期清理避免 storage 膨胀
const LAST_PLAYED_TTL_MS = 7 * 24 * 3600 * 1000;

const app = getApp();

// 倍速选项：循环切换顺序
const RATE_OPTIONS = [0.75, 1.0, 1.25, 1.5, 2.0];

// 睡眠定时器预设（秒）
const SLEEP_PRESETS = [
  { label: '关闭', value: 0 },
  { label: '15 分钟', value: 900 },
  { label: '30 分钟', value: 1800 },
  { label: '45 分钟', value: 2700 },
  { label: '60 分钟', value: 3600 },
];

Page({
  data: {
    episode: null,      // 今日节目对象 { id, title, date, category, duration, audio_url, channel_name }
    isPlaying: false,   // 播放状态
    currentTime: 0,     // 当前播放位置（秒）
    duration: 0,        // 总时长（秒，播放后由播放器填入）
    loading: true,      // 加载中
    error: '',          // 错误信息（今日节目未发布等）
    // V1.3 新增字段
    channels: [],         // 频道列表
    currentChannelId: null, // 当前选中频道（null 表示全部）
    favorited: false,     // 当前节目是否已收藏
    currentRate: 1.0,     // 当前倍速
    sleepActive: false,   // 睡眠定时器是否激活
    sleepRemaining: 0,    // 睡眠剩余秒数
    sleepLabel: '',       // 睡眠定时器展示文案
    playError: '',        // 播放错误文案（音频丢失时持久显示在播放卡片上）
    // 全部模式（任务3）：多频道节目列表
    todayList: [],        // 今日各频道节目列表
    todayDateText: '',    // 今日日期中文显示（"7月20日"）
    // 续播（任务3续播）
    lastPlayedEpisode: null, // 上次播放过的节目（含 currentTime）
    // 当前正在播放的节目 ID（用于节目行内播放/暂停图标切换）
    currentEpisodeId: null,
    // 已播放过的节目 id 集合（{ [id]: true }），用于列表行渲染"已播放"视觉标注
    playedSet: {},
    // 任务4：首页本地展开文稿
    showScript: false,
    scriptLoaded: false,
    scriptLoading: false,
    script: '',
    segments: [],
    // "我的偏爱"模式：channel-pill 末尾的"我的偏爱"项用特殊 id 'preferred' 标识
    // 切换到该项时 isPreferredMode=true，currentChannelId 同步设为 'preferred'（仅用于 pill 高亮）
    // 数据拉取走 loadPreferred()：拉全部频道今日节目 + 本地按 preferredIds 过滤
    isPreferredMode: false,
    preferredIds: [],       // 用户偏爱的频道 ID 数组（本地存储镜像，便于快速过滤）
    preferredEmpty: false,  // 偏爱频道未设置时为 true，用于显示引导设置提示
  },

  async onLoad() {
    trackPageView('pages/index/index');
    this._unsubSleep = onSleepChange((status) => {
      this.setData({
        sleepActive: status.active,
        sleepRemaining: status.remaining,
        sleepLabel: status.active ? this.formatSleepLabel(status.remaining) : '',
      });
    });
    // 播放错误时重置 UI：BackgroundAudioManager 加载失败不会触发 onPause，
    // 若不订阅 onError，isPlaying 会一直停留在 true 导致按钮卡死
    this._unsubError = onError((err) => {
      const tip = (err && err.errCode === 10001)
        ? '音频文件已被清理或暂时不可访问'
        : '音频加载失败，请稍后重试';
      this.setData({ isPlaying: false, currentTime: 0, playError: tip });
    });
    this.bindPlayerEvents();

    // 首屏加速：若 onLaunch 已预加载今日节目（globalData.todayEpisode），
    // 立即用其渲染今日列表，避免空白等待 readyPromise（登录拿 token）完成。
    // 后续 initData 会重新拉取覆盖；fetchTodayEpisode 有 60s 缓存，重复请求走缓存不浪费 RTT。
    const cached = app.globalData.todayEpisode;
    if (cached) {
      this._applyTodayData(cached);
    }

    // 等 app onLaunch 完成（登录拿 token），避免需鉴权的请求 401
    await getApp().readyPromise;
    // readyPromise 完成后再补充需要 token 的请求：
    // - initData：重新拉取最新今日节目覆盖缓存（确保最新）
    // - loadChannels：频道列表带 is_subscribed 字段，需 token
    // - loadLastPlayed / loadPlayedHistory：本地无缓存时从后端拉取，需 token
    this.initData();
    this.loadChannels();
    this.loadLastPlayed();
    // 拉取最近播放记录标记已播放节目（与 initData 并行，互不阻塞首屏）
    this.loadPlayedHistory();
    // 首次登录后引导设置偏爱频道：app.js 登录成功且未引导过时置 true
    // 放在 readyPromise 之后：确保 openid 已就绪，弹窗后用户去设置能正确保存
    this.maybeShowOnboarding();
    // 镜像本地偏爱频道 ID 到 data，便于"我的偏爱"模式下快速过滤
    this.setData({ preferredIds: localData.getPreferredChannels() });
  },

  onUnload() {
    if (this._unsubSleep) this._unsubSleep();
    if (this._unsubError) this._unsubError();
    if (this._unsubPlayback) this._unsubPlayback();
    this._unsubPlayback = null;
    // 取消 timeUpdate 订阅：避免页面销毁后回调仍触发 setData 报错
    if (this._onTimeUpdateChange) {
      offTimeUpdateChange(this._onTimeUpdateChange);
      this._onTimeUpdateChange = null;
    }
  },

  /**
   * 页面隐藏时统一把内存中累积的播放进度刷入 storage
   * 避免 onTimeUpdate 期间频繁写 storage 阻塞主线程
   */
  onHide() {
    this._flushLastPlayed();
  },

  async onShow() {
    // 等待 onLaunch 完成（后端发现 + 登录 + 预加载），避免 baseUrl 未就绪时请求打到 localhost
    await getApp().readyPromise;
    // 每次显示页面时同步播放器状态（从其他页返回时播放状态可能已变化）
    this.syncPlayerState();
    this.setData({ currentRate: getPlaybackRate() });
    // 从详情页返回时可能改了收藏态，需重新检查
    if (this.data.episode) this.checkFavorited(this.data.episode.id);
    // 从详情页返回时刷新已播放标记（详情页可能播完了新节目）
    // 节流由 services/api.js 的 fetchRecentPlaylogs throttle 统一处理，
    // 页面层不再维护各自的 30s 时间戳，避免 tab 切换时多页面节流状态不一致
    this.loadPlayedHistory();
    // 订阅播放/暂停即时通知：节目行播放按钮图标实时切换
    if (!this._unsubPlayback) {
      this._unsubPlayback = onPlaybackChange(() => this.syncPlayerState());
    }
    // 每次 onShow 都从 localData 同步最新的偏爱频道 ID：
    // - 从其他 tab 切换回来时，localData 可能已被其他页面更新（如 profile 页调了设置接口）
    // - 刚从 preferred-settings 返回时，也能拿到最新值
    const latestPreferredIds = localData.getPreferredChannels();
    const app = getApp();
    // 判断是否需要重新加载"我的偏爱"数据：
    // 条件1：偏爱频道设置时间戳变化（刚从 settings 页保存返回）
    // 条件2：当前在偏爱模式下，preferredIds 与最新值不一致（其他页面修改了偏爱）
    // 条件3：当前在偏爱模式下，todayList 可能包含非偏爱频道的数据（切 tab 回来时需要重新过滤）
    const preferredChangedByTs = this._lastPreferredTs && this._lastPreferredTs !== app.globalData.preferredChannelsChanged;
    const preferredIdsDiffers = JSON.stringify(this.data.preferredIds) !== JSON.stringify(latestPreferredIds);
    if (preferredChangedByTs || preferredIdsDiffers) {
      this.setData({ preferredIds: latestPreferredIds });
    }
    // 偏爱模式下每次切回都要刷新：
    // 为什么：从其他tab切换回来时，todayList 可能残留了全部频道数据（onLoad预渲染或上次切换的残留），
    // 必须按最新的 preferredIds 重新过滤，否则会展示所有频道导致"偏爱模式显示全部频道"的问题
    if (this.data.isPreferredMode) {
      this.loadPreferred();
    }
    this._lastPreferredTs = app.globalData.preferredChannelsChanged;
  },

  /**
   * 下拉刷新：重新拉取今日节目（空状态时也能用，给用户重新尝试的入口）
   */
  async onPullDownRefresh() {
    try {
      // 偏爱模式下走专用刷新路径：拉全部频道今日节目 + 本地过滤
      if (this.data.isPreferredMode) {
        await this.loadPreferred();
      } else {
        // 频道切换时也通过这里刷新，确保下拉始终刷新当前频道
        const episode = await fetchTodayEpisode(this.data.currentChannelId);
        this.setData({ episode, loading: false, error: '' });
        if (!this.data.currentChannelId) {
          app.globalData.todayEpisode = episode;
        }
        if (episode) this.checkFavorited(episode.id);
      }
    } catch (err) {
      this.setData({ error: err.message || '今日节目暂未上线' });
    } finally {
      wx.stopPullDownRefresh();
    }
  },

  /**
   * 加载频道列表（用于顶部频道切换胶囊）
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
      console.log('加载频道列表失败:', err.message);
    }
  },

  /**
   * 切换频道：重新拉取该频道今日节目
   * 'preferred' 是特殊值，进入"我的偏爱"模式（拉全部 + 本地过滤）
   */
  async onSwitchChannel(e) {
    // 用严格判断避免 id=0 被误判为 falsy（虽然频道 id 通常从 1 开始，但防御性编程）
    const rawId = e.currentTarget.dataset.id;
    const channelId = (rawId !== undefined && rawId !== null && rawId !== '') ? rawId : null;
    if (channelId === this.data.currentChannelId) return;
    trackEvent('index', 'switch_channel', '', String(channelId || ''));
    // 先立即清空旧数据和详情状态，避免上一频道的节目残留在 UI 上（用户反馈"全部和科技前沿内容一样"）
    this.setData({
      currentChannelId: channelId,
      // 'preferred' 模式标志：与 currentChannelId 并存，便于 initData/loadPreferred 判断
      isPreferredMode: channelId === 'preferred',
      todayList: [],
      episode: null,
      showScript: false,
      scriptLoaded: false,
      scriptLoading: false,
      script: '',
      segments: [],
      error: '',
      preferredEmpty: false,
    });
    app.globalData.currentChannelId = channelId === 'preferred' ? null : channelId;
    app.globalData.todayList = [];
    if (channelId === 'preferred') {
      await this.loadPreferred();
    } else {
      await this.initData(true);
    }
  },

  /**
   * "我的偏爱"模式专用：拉取全部频道今日节目 + 本地按 preferredIds 过滤
   * 未设置偏爱频道时显示引导设置提示（preferredEmpty=true）
   * 同步更新 app.globalData.todayList，保证播放队列也是过滤后的列表
   */
  async loadPreferred() {
    // 从 localData 读取最新的偏爱频道 ID：
    // 为什么不用 this.data.preferredIds：onShow 与 loadPreferred 之间可能存在状态异步更新窗口，
    // 直接读本地存储确保拿到的是最新值，避免"刚设置偏爱却仍显示空列表"的问题
    const preferredIds = localData.getPreferredChannels();
    // 同步 data 中的镜像，确保 wxml 渲染使用最新值
    if (JSON.stringify(this.data.preferredIds) !== JSON.stringify(preferredIds)) {
      this.setData({ preferredIds });
    }
    this.setData({ loading: true, error: '' });
    if (preferredIds.length === 0) {
      // 未设置偏爱频道：展示引导设置提示，不发起请求
      // 同时清空 todayList 和 globalData.todayList，避免残留上次加载的全部频道数据
      this.setData({
        loading: false,
        todayList: [],
        preferredEmpty: true,
      });
      app.globalData.todayList = [];
      return;
    }
    try {
      const data = await fetchTodayEpisode(null);
      const list = Array.isArray(data) ? data : [];
      const idSet = new Set(preferredIds);
      const filtered = list.filter(ep => idSet.has(ep.channel_id));
      this._applyTodayData(filtered);
      // 偏爱模式下过滤后为空，preferredEmpty=true 让 wxml 走"偏爱频道暂无今日节目"分支
      this.setData({ preferredEmpty: filtered.length === 0 });
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '今日节目暂未上线',
      });
    }
  },

  /**
   * 首次登录后引导设置偏爱频道
   * - 读取 app.globalData.needsPreferredOnboarding 标志
   * - 弹窗询问"去设置"/"暂不"，用户任一选择都清除标志避免重复弹窗
   * - 选"去设置"跳到 preferred-settings 页（带 from=onboarding 显示"暂不设置"按钮）
   */
  maybeShowOnboarding() {
    const app = getApp();
    if (!app.globalData.needsPreferredOnboarding) return;
    // 立即清除标志：避免用户多次进出页面被重复弹窗
    app.globalData.needsPreferredOnboarding = false;
    wx.showModal({
      title: '设置偏爱频道',
      content: '勾选你喜爱的频道，"我的偏爱"将只展示这些频道的节目。',
      confirmText: '去设置',
      cancelText: '暂不',
      confirmColor: '#5BA89B',
      success: (res) => {
        if (res.confirm) {
          wx.navigateTo({ url: '/pages/preferred-settings/preferred-settings?from=onboarding' });
          trackEvent('preferred', 'onboarding_accept');
        } else {
          // 暂不也视为已完成引导，下次启动不再弹窗
          localData.markPreferredChannelsOnboarded();
          trackEvent('preferred', 'onboarding_skip');
        }
      },
    });
  },

  /**
   * 加载今日节目
   * 全部模式：拉取所有频道的今日节目（每个频道最新一期）
   * 单频道模式：拉取指定频道的今日节目
   * @param {boolean} force - 强制刷新（频道切换时）
   */
  async initData(force) {
    this.setData({ loading: true, error: '' });
    const channelId = this.data.currentChannelId;
    // 切换频道/强制刷新时清空旧文稿与状态，避免新节目详情仍残留上一节目的文稿和图片
    // 任务1+2+10：节目详情、文稿、分段封面图需随频道切换同步刷新
    if (force) {
      this.setData({
        showScript: false,
        scriptLoaded: false,
        scriptLoading: false,
        script: '',
        segments: [],
      });
    }
    try {
      const data = await fetchTodayEpisode(channelId);
      this._applyTodayData(data);
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '今日节目暂未上线',
      });
    }
  },

  /**
   * 将今日节目数据应用到 UI（onLoad 预渲染 与 initData 拉取后共用）
   * 抽离此方法是为了让 onLoad 能在 readyPromise 完成前用 globalData.todayEpisode
   * 立即渲染首屏，避免空白等待，同时保证两处渲染逻辑一致
   */
  _applyTodayData(data) {
    const channelId = this.data.currentChannelId;
    // 任务1：统一为列表模式，单频道也包装成 list，点击跳转 detail 页
    // "我的偏爱"模式（channelId === 'preferred'）也走数组分支：
    // loadPreferred 已传入过滤后的数组，此处直接用即可
    const isListMode = channelId === null || channelId === 'preferred';
    let list = isListMode
      ? (Array.isArray(data) ? data : [])
      : (data ? [data] : []);

    // 偏爱模式下二次按 preferredIds 过滤：
    // 为什么：onLoad 时 globalData.todayEpisode 预渲染可能传入的是全部频道数据（当时还没切换到偏爱模式），
    // 后续 onShow 切换到偏爱模式重新渲染时如果调用了 _applyTodayData，需要确保只保留偏爱频道的节目
    if (channelId === 'preferred' && list.length > 0) {
      const preferredIds = localData.getPreferredChannels();
      if (preferredIds.length > 0) {
        const idSet = new Set(preferredIds);
        list = list.filter(ep => idSet.has(ep.channel_id));
      } else {
        // preferredIds 为空时，偏爱模式应该显示引导卡片，清空列表避免显示全部频道
        list = [];
      }
    }

    const enriched = list.map(ep => this._enrichEpisode(ep));
    this.setData({
      todayList: enriched,
      todayDateText: this._formatDateZh(new Date()),
      loading: false,
      episode: null,
    });
    app.globalData.todayList = enriched;
  },

  /**
   * 节目对象增强：补充 date_label、duration_label、channel_name
   * 任务1：当 title 退化为 "X月X日 · 今日要闻" 这种无辨识度文案时，改为日期+频道名
   * 后端 _episode_to_dict 可能未补 channel_name，前端按需回退
   */
  _enrichEpisode(ep) {
    if (!ep) return ep;
    const dateLabel = ep.date ? this._formatDateZh(ep.date) : '';
    const durationSec = ep.duration || 0;
    let channelName = ep.channel_name || '';
    if (!channelName) {
      const ch = this.data.channels.find(c => c.id === ep.channel_id);
      channelName = ch ? ch.name : '';
    }
    // 标题优化：若标题是模板化的"X月X日 · 今日要闻"形式（不含频道名），自动改为日期+频道
    const title = this._normalizeTitle(ep.title, dateLabel, channelName);
    return {
      ...ep,
      title,
      channel_name: channelName,
      date_label: dateLabel,
      duration_label: this._formatDuration(durationSec),
      // 已播放标记：playedSet 中存在的 id 标为已播放，供 wxml 渲染视觉标注
      played: !!this.data.playedSet[ep.id],
    };
  },

  /**
   * 标题规范化：
   * - 包含"今日要闻"且没有频道名 → 替换为 "7月20日 · 科技前沿"
   * - 已有频道名 → 保持原样
   * - 空标题 → 用 date_label + 频道名兜底
   */
  _normalizeTitle(title, dateLabel, channelName) {
    const looksGeneric = !title
      || title.includes('今日要闻')
      || /^X月X日/.test(title)
      || /^\d+月\d+日\s*[·•・]\s*今日要闻?$/.test(title)
      || /^\d+月\d+日\s*今日要闻?$/.test(title);
    if (looksGeneric && channelName) {
      return (dateLabel || '') + (dateLabel ? ' · ' : '') + channelName;
    }
    return title || ((dateLabel || '') + (dateLabel && channelName ? ' · ' : '') + (channelName || '今日节目'));
  },

  /**
   * 日期格式化为中文 "7月20日"
   * 接受 Date 或 'YYYY-MM-DD' 字符串
   */
  _formatDateZh(d) {
    if (!d) return '';
    const date = d instanceof Date ? d : new Date(d);
    if (Number.isNaN(date.getTime())) return String(d);
    return (date.getMonth() + 1) + '月' + date.getDate() + '日';
  },

  /**
   * 秒数 → mm:ss
   */
  _formatDuration(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
  },

  /**
   * 加载上次播放进度：用于"继续播放"按钮
   * 优先用本地存储缓存，缺失时从后端拉取
   */
  async loadLastPlayed() {
    try {
      const cached = getWithTTL('lastPlayedEpisode');
      if (cached && cached.id && cached.currentTime > 0) {
        this.setData({ lastPlayedEpisode: cached });
        // 异步从后端补齐进度（localData.getProgress 优先本地，本地无时从后端读）
        localData.getProgress(cached.id).then((progress) => {
          if (progress && progress.position > 0) {
            const enriched = { ...cached, currentTime: progress.position };
            this.setData({ lastPlayedEpisode: enriched });
            setWithTTL('lastPlayedEpisode', enriched, LAST_PLAYED_TTL_MS);
          }
        }).catch(() => {});
        return;
      }
      // 本地无缓存：从本地历史列表取第一条（localData.getHistory 优先本地，缺失时读后端）
      const recent = await localData.getHistory(1, 1);
      const recentItem = (recent.list || [])[0];
      if (recentItem && recentItem.id) {
        // 取该节目的进度
        const progress = await localData.getProgress(recentItem.id);
        const currentTime = (progress && progress.position) || recentItem.position || 0;
        if (currentTime > 0) {
          const list = this.data.todayList;
          const ep = list.find(e => e.id === recentItem.id) || {
            id: recentItem.id,
            title: recentItem.title || '上次的节目',
          };
          const last = { ...ep, currentTime };
          this.setData({ lastPlayedEpisode: last });
          setWithTTL('lastPlayedEpisode', last, LAST_PLAYED_TTL_MS);
        }
      }
    } catch (err) {
      // 静默失败：续播按钮非核心功能
    }
  },

  /**
   * 拉取最近播放记录，构造已播放 id 集合（playedSet），并刷新今日列表的 played 标记
   * 用于在今日列表行上展示"已播放"视觉反馈
   * 优先本地历史，本地无时从后端读取
   */
  async loadPlayedHistory() {
    try {
      const playedIds = await localData.getPlayedHistorySet();
      const playedSet = {};
      playedIds.forEach(id => { playedSet[id] = true; });
      this.setData({ playedSet });
      // 已播放集合就绪后，重新 enrich 今日列表以填充 played 字段
      if (this.data.todayList.length > 0) {
        const enriched = this.data.todayList.map(ep => this._enrichEpisode(ep));
        this.setData({ todayList: enriched });
        app.globalData.todayList = enriched;
      }
    } catch (err) {
      // 静默失败：已播放标记非核心功能
    }
  },

  /**
   * 检查当前节目是否已收藏（优先本地，本地无时从后端读取）
   */
  async checkFavorited(episodeId) {
    if (!episodeId) return;
    try {
      const res = await localData.checkFavoriteLocal(episodeId);
      this.setData({ favorited: !!(res && res.favorited) });
    } catch (err) {
      this.setData({ favorited: false });
    }
  },

  /**
   * 收藏/取消收藏当前节目（双写本地+后端）
   */
  async onToggleFavorite() {
    const { episode, favorited } = this.data;
    if (!episode) return;
    try {
      if (favorited) {
        await localData.removeFavorite(episode.id);
        this.setData({ favorited: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
        trackEvent('index', 'unfavorite', 'episode_' + episode.id);
      } else {
        await localData.addFavorite(episode);
        this.setData({ favorited: true });
        wx.showToast({ title: '已收藏', icon: 'success' });
        trackEvent('index', 'favorite', 'episode_' + episode.id);
      }
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  /**
   * 绑定全局播放器事件，实时同步播放进度和状态到页面
   *
   * 为什么用订阅接口而非直接 player.onXxx：
   * BackgroundAudioManager.onXxx 是覆盖式注册，直接注册会覆盖 audio.js initPlayer 中
   * 注册的回调（含 playNext 自动连播、startProgressReport、applyPlaybackRate 等核心逻辑），
   * 导致自动连播失效、进度不上报、倍速丢失等问题。
   * 改为通过 audio.js 的订阅接口（onPlaybackChange/onTimeUpdateChange）监听事件。
   */
  bindPlayerEvents() {
    // 播放/暂停/结束状态变更：同步 UI + 落盘续播进度
    this._unsubPlayback = onPlaybackChange((evt) => {
      const ep = getCurrentEpisode();
      this.setData({ isPlaying: !evt.paused, currentEpisodeId: ep ? ep.id : null });

      // 暂停/结束时统一写入一次进度，替代 onTimeUpdate 中每 5s 写 storage
      if (evt.paused) {
        this._flushLastPlayed();
      }
      // 结束时重置进度条 UI
      if (evt.type === 'ended') {
        this.setData({ currentTime: 0 });
      }
    });

    // 时间更新：同步进度条 + 每 5s 缓存续播进度到内存
    this._onTimeUpdateChange = (currentTime, duration) => {
      // 仅在值变化时 setData，减少渲染
      if (currentTime !== this.data.currentTime || duration !== this.data.duration) {
        this.setData({ currentTime, duration });
      }
      // 每 5s 仅在内存中累积续播进度，避免频繁 wx.setStorageSync 阻塞主线程
      // 真正写入 storage 由 _flushLastPlayed 在 onPause/onEnded/onHide 时统一处理
      const ep = this.data.episode;
      if (ep && currentTime > 0 && currentTime % 5 === 0) {
        this._pendingLastPlayed = { ...ep, currentTime };
        if (!this.data.lastPlayedEpisode) {
          this.setData({ lastPlayedEpisode: { ...ep, currentTime } });
        }
      }
    };
    onTimeUpdateChange(this._onTimeUpdateChange);
  },

  /**
   * 把 onTimeUpdate 期间累积在内存的播放进度批量写入 storage
   * 设计意图：onTimeUpdate 每秒触发多次，原实现每 5s 写一次 storage 会阻塞主线程；
   * 改为只在内存累积，由 onPause/onEnded/onHide 三个低频时机统一落盘
   */
  _flushLastPlayed() {
    if (!this._pendingLastPlayed) return;
    // 关键写入（保持同步）：onPause/onEnded/onHide 时需立即落盘，避免 app 被杀时进度丢失
    // 同时叠加 7 天 TTL，过期后自动清理
    try {
      setWithTTL('lastPlayedEpisode', this._pendingLastPlayed, LAST_PLAYED_TTL_MS);
    } catch (e) {}
    this._pendingLastPlayed = null;
  },

  syncPlayerState() {
    const player = app.globalData.player;
    if (!player) return;
    const ep = getCurrentEpisode();
    this.setData({
      isPlaying: !player.paused,
      currentTime: Math.floor(player.currentTime || 0),
      duration: Math.floor(player.duration || 0),
      currentEpisodeId: ep ? ep.id : null,
    });
  },

  onTogglePlay() {
    const { episode, isPlaying } = this.data;
    if (!episode) return;
    const player = app.globalData.player;
    if (!player) return;
    // 重新发起播放时清空上次的播放错误提示
    if (this.data.playError) this.setData({ playError: '' });
    if (isPlaying) {
      player.pause();
    } else {
      playEpisode(episode);
      trackEvent('index', 'play', 'episode_' + episode.id);
    }
  },

  onSeek(e) {
    const player = app.globalData.player;
    if (!player) return;
    const position = e.detail.value;
    // 调用 services/audio 的 seek 函数：处理暂停状态下 seek 不生效的问题
    seek(position);
    this.setData({ currentTime: position });
  },

  onViewScript() {
    // 任务1：首页本地展开文稿
    // setData 异步，先计算目标态再触发，避免读取 this.data.showScript 仍是旧值导致漏加载
    const { episode, showScript, scriptLoaded } = this.data;
    if (!episode) return;
    trackEvent('index', 'view_script', 'episode_' + episode.id);
    const willShow = !showScript;
    this.setData({ showScript: willShow });
    if (willShow && !scriptLoaded) {
      this.loadScript();
    }
  },

  /**
   * 任务3：打开播放队列页
   */
  onOpenQueue() {
    trackEvent('index', 'open_queue');
    wx.navigateTo({ url: '/pages/queue/queue' });
  },

  async loadScript() {
    const { episode } = this.data;
    if (!episode) return;
    this.setData({ scriptLoading: true });
    try {
      const res = await fetchEpisodeScript(episode.id);
      const content = typeof res === 'string'
        ? res
        : (res && (res.script || res.content)) || '';
      const segments = (res && Array.isArray(res.segments)) ? res.segments : [];
      this.setData({
        script: content,
        segments,
        scriptLoaded: true,
        scriptLoading: false,
      });
    } catch (err) {
      this.setData({ scriptLoading: false });
      wx.showToast({ title: '文稿加载失败', icon: 'none' });
    }
  },

  /**
   * 全部模式：点击节目行 → 跳转到详情页（与历史页一致）
   * 任务1：统一详细播放页面布局，首页不再内嵌渲染播放卡片
   */
  onTapEpisode(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    const ep = this.data.todayList.find(x => x.id === id);
    if (!ep) return;
    trackEvent('index', 'tap_episode', 'episode_' + id);
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id });
  },

  /**
   * 全部模式：点行尾播放按钮 → 立即播放并跳转到详情页
   * 任务1：统一布局，播放后跳转 detail 页
   */
  onPlayEpisode(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    const ep = this.data.todayList.find(x => x.id === id);
    if (!ep) return;
    trackEvent('index', 'play_row', 'episode_' + id);
    this.setData({ playError: '' });
    const player = app.globalData.player;
    const current = getCurrentEpisode();
    // 正在播放的就是该节目：暂停
    if (current && current.id === id && player && !player.paused) {
      player.pause();
      return;
    }
    // 暂停中的就是该节目：继续播放
    if (current && current.id === id && player && player.paused) {
      safePlay();
      wx.navigateTo({ url: '/pages/detail/detail?id=' + id });
      return;
    }
    // 切换到新节目：先把当前列表设为播放队列（从点击项开始，便于后续自动连播）
    const idx = this.data.todayList.findIndex(x => x.id === id);
    if (idx >= 0) {
      setQueue(this.data.todayList, idx);
    }
    playEpisode(ep);
    try {
      setWithTTL('lastPlayedEpisode', { ...ep, currentTime: 0 }, LAST_PLAYED_TTL_MS);
      this.setData({ lastPlayedEpisode: { ...ep, currentTime: 0 } });
    } catch (e) {}
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id });
  },

  /**
   * 点击"继续播放"：从 lastPlayedEpisode.currentTime 继续
   * 任务1+2：播放后跳转到详情页，让用户看到统一的播放界面和播放状态
   */
  onTapContinue() {
    const last = this.data.lastPlayedEpisode;
    if (!last) return;
    trackEvent('index', 'continue_play', 'episode_' + last.id);
    this.setData({ playError: '' });
    const player = app.globalData.player;
    const current = getCurrentEpisode();
    // 当前正在播放的就是该节目：暂停
    if (current && current.id === last.id && player && !player.paused) {
      player.pause();
      return;
    }
    // 暂停中的就是该节目：继续播放，并跳转详情页
    if (current && current.id === last.id && player && player.paused) {
      safePlay();
      wx.navigateTo({ url: '/pages/detail/detail?id=' + last.id });
      return;
    }
    // 切换到新节目：先把今日列表从该节目开始设为队列，再播放并 seek 到上次位置
    const list = this.data.todayList;
    const idx = list.findIndex(x => x.id === last.id);
    if (idx >= 0 && list.length > 0) {
      setQueue(list, idx);
    }
    playEpisode(last);
    // 用 pendingSeek 标志位代替 onCanplay 注册（R80）：
    // audio.js 内部 onCanplay 会自动 seek 并清零，避免页面层重复注册回调累积
    const targetTime = last.currentTime || 0;
    if (targetTime > 0) {
      setPendingSeek(targetTime);
    }
    // 跳转到详情页，详情页 onShow 会同步 isPlaying 状态
    wx.navigateTo({ url: '/pages/detail/detail?id=' + last.id });
  },

  /**
   * 跳转搜索页
   */
  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' });
    trackEvent('index', 'tap_search');
  },

  /**
   * 跳转偏爱频道设置页（"我的偏爱"未设置时的引导按钮）
   */
  onTapPreferredSettings() {
    wx.navigateTo({ url: '/pages/preferred-settings/preferred-settings' });
    trackEvent('index', 'tap_preferred_settings');
  },

  /**
   * 倍速循环切换：1.0 → 1.25 → 1.5 → 0.75 → 2.0 → 1.0
   */
  onCycleRate() {
    const current = getPlaybackRate();
    const idx = RATE_OPTIONS.indexOf(current);
    const next = RATE_OPTIONS[(idx + 1) % RATE_OPTIONS.length];
    setPlaybackRate(next);
    this.setData({ currentRate: next });
    wx.showToast({ title: next + 'x 倍速', icon: 'none' });
    trackEvent('index', 'change_rate', '', next);
  },

  /**
   * 睡眠定时器：弹出 ActionSheet 选择预设时长
   */
  onSleepTimer() {
    const labels = SLEEP_PRESETS.map((p) => p.label);
    const status = getSleepStatus();
    // 已激活时第一个选项显示"关闭"，与预设中的 value=0 对应
    wx.showActionSheet({
      itemList: labels,
      success: (res) => {
        const preset = SLEEP_PRESETS[res.tapIndex];
        if (preset.value === 0) {
          stopSleepTimer();
          wx.showToast({ title: '已关闭睡眠定时', icon: 'none' });
          trackEvent('index', 'sleep_timer_off');
        } else {
          startSleepTimer(preset.value);
          wx.showToast({ title: '睡眠定时 ' + preset.label, icon: 'none' });
          trackEvent('index', 'sleep_timer_on', '', preset.value);
        }
      },
    });
  },

  /**
   * 秒 → "X分钟" 或 "X小时Y分钟"
   */
  formatSleepLabel(sec) {
    if (sec <= 0) return '';
    const m = Math.floor(sec / 60);
    if (m < 60) return m + ' 分钟后停止';
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? h + '小时' + rest + '分钟后停止' : h + '小时后停止';
  },
});
