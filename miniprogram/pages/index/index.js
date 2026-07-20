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
const { fetchTodayEpisode, fetchEpisodeScript, checkFavorite, addFavorite, removeFavorite, fetchChannels, fetchPlayProgress, fetchRecentPlaylogs } = require('../../services/api');
const { playEpisode, getPlaybackRate, setPlaybackRate, getSleepStatus, startSleepTimer, stopSleepTimer, onSleepChange, onError, getCurrentEpisode, onPlaybackChange } = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

const app = getApp();

// 倍速选项：循环切换顺序
const RATE_OPTIONS = [1.0, 1.25, 1.5, 0.75, 2.0];

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
    // 任务4：首页本地展开文稿
    showScript: false,
    scriptLoaded: false,
    scriptLoading: false,
    script: '',
    segments: [],
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
    // 等 app onLaunch 完成（登录拿 token），避免需鉴权的请求 401
    await getApp().readyPromise;
    this.initData();
    this.loadChannels();
    this.loadLastPlayed();
  },

  onUnload() {
    if (this._unsubSleep) this._unsubSleep();
    if (this._unsubError) this._unsubError();
    if (this._unsubPlayback) this._unsubPlayback();
    this._unsubPlayback = null;
    // 解绑播放器事件，防止 reLaunch 后 onLoad 重复绑定导致回调叠加
    const player = app.globalData.player;
    if (player) {
      player.offPlay?.(this._onPlay);
      player.offPause?.(this._onPause);
      player.offTimeUpdate?.(this._onTimeUpdate);
      player.offEnded?.(this._onEnded);
    }
  },

  onShow() {
    // 每次显示页面时同步播放器状态（从其他页返回时播放状态可能已变化）
    this.syncPlayerState();
    this.setData({ currentRate: getPlaybackRate() });
    // 从详情页返回时可能改了收藏态，需重新检查
    if (this.data.episode) this.checkFavorited(this.data.episode.id);
    // 订阅播放/暂停即时通知：节目行播放按钮图标实时切换
    if (!this._unsubPlayback) {
      this._unsubPlayback = onPlaybackChange(() => this.syncPlayerState());
    }
  },

  /**
   * 下拉刷新：重新拉取今日节目（空状态时也能用，给用户重新尝试的入口）
   */
  async onPullDownRefresh() {
    try {
      // 频道切换时也通过这里刷新，确保下拉始终刷新当前频道
      const episode = await fetchTodayEpisode(this.data.currentChannelId);
      this.setData({ episode, loading: false, error: '' });
      if (!this.data.currentChannelId) {
        app.globalData.todayEpisode = episode;
      }
      if (episode) this.checkFavorited(episode.id);
    } catch (err) {
      this.setData({ error: err.message || '今日节目暂未上线' });
    } finally {
      wx.stopPullDownRefresh();
    }
  },

  /**
   * 加载频道列表（用于顶部频道切换胶囊）
   */
  async loadChannels() {
    try {
      const res = await fetchChannels();
      // 第一个选项为"全部"，后接频道列表
      const channels = [{ id: null, name: '全部' }, ...(res.list || [])];
      this.setData({ channels });
    } catch (err) {
      console.log('加载频道列表失败:', err.message);
    }
  },

  /**
   * 切换频道：重新拉取该频道今日节目
   */
  async onSwitchChannel(e) {
    // 用严格判断避免 id=0 被误判为 falsy（虽然频道 id 通常从 1 开始，但防御性编程）
    const rawId = e.currentTarget.dataset.id;
    const channelId = (rawId !== undefined && rawId !== null && rawId !== '') ? rawId : null;
    if (channelId === this.data.currentChannelId) return;
    trackEvent('index', 'switch_channel', '', channelId || 0);
    // 先立即清空旧数据和详情状态，避免上一频道的节目残留在 UI 上（用户反馈"全部和科技前沿内容一样"）
    this.setData({
      currentChannelId: channelId,
      todayList: [],
      episode: null,
      showScript: false,
      scriptLoaded: false,
      scriptLoading: false,
      script: '',
      segments: [],
      error: '',
    });
    app.globalData.currentChannelId = channelId;
    app.globalData.todayList = [];
    await this.initData(true);
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
      // 任务1：统一为列表模式，单频道也包装成 list，点击跳转 detail 页
      const list = channelId === null
        ? (Array.isArray(data) ? data : [])
        : (data ? [data] : []);
      const enriched = list.map(ep => this._enrichEpisode(ep));
      this.setData({
        todayList: enriched,
        todayDateText: this._formatDateZh(new Date()),
        loading: false,
        episode: null,
      });
      app.globalData.todayList = enriched;
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '今日节目暂未上线',
      });
    }
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
   * 优先用 storage 缓存，缺失时回退到后端
   */
  async loadLastPlayed() {
    try {
      const cached = wx.getStorageSync('lastPlayedEpisode');
      if (cached && cached.id && cached.currentTime > 0) {
        this.setData({ lastPlayedEpisode: cached });
        // 异步补齐节目元信息（title/channel_name），不影响首屏
        fetchPlayProgress(cached.id).then((remote) => {
          if (remote && remote.current_time > 0) {
            const enriched = { ...cached, currentTime: remote.current_time };
            this.setData({ lastPlayedEpisode: enriched });
            wx.setStorageSync('lastPlayedEpisode', enriched);
          }
        }).catch(() => {});
        return;
      }
      // storage 无缓存时，拉最近播放记录的第一条
      // 原误用 fetchPlayProgress(null) 导致 URL 拼成 /progress/null 返回 400
      const recent = await fetchRecentPlaylogs(1, 1);
      const recentItem = (recent && (recent.list || recent.items || []))[0];
      if (recentItem && recentItem.episode_id && recentItem.current_time > 0) {
        const list = this.data.todayList;
        const ep = list.find(e => e.id === recentItem.episode_id) || {
          id: recentItem.episode_id,
          title: recentItem.title || '上次的节目',
        };
        const last = { ...ep, currentTime: recentItem.current_time };
        this.setData({ lastPlayedEpisode: last });
        wx.setStorageSync('lastPlayedEpisode', last);
      }
    } catch (err) {
      // 静默失败：续播按钮非核心功能
    }
  },

  /**
   * 检查当前节目是否已收藏
   */
  async checkFavorited(episodeId) {
    if (!episodeId) return;
    try {
      const res = await checkFavorite(episodeId);
      this.setData({ favorited: !!(res && res.favorited) });
    } catch (err) {
      this.setData({ favorited: false });
    }
  },

  /**
   * 收藏/取消收藏当前节目
   */
  async onToggleFavorite() {
    const { episode, favorited } = this.data;
    if (!episode) return;
    try {
      if (favorited) {
        await removeFavorite(episode.id);
        this.setData({ favorited: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
        trackEvent('index', 'unfavorite', 'episode_' + episode.id);
      } else {
        await addFavorite(episode.id);
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
   * 回调引用存到实例属性，供 onUnload 精确解绑
   */
  bindPlayerEvents() {
    const player = app.globalData.player;
    if (!player) return;

    this._onPlay = () => {
      const ep = getCurrentEpisode();
      this.setData({ isPlaying: true, currentEpisodeId: ep ? ep.id : null });
    };
    this._onPause = () => { this.setData({ isPlaying: false }); };
    this._onTimeUpdate = () => {
      // 节流：onTimeUpdate 每秒约触发 5 次，频繁 setData 会阻塞渲染导致卡顿
      const now = Date.now();
      if (this._lastTimeUpdateTs && now - this._lastTimeUpdateTs < 800) return;
      this._lastTimeUpdateTs = now;
      const currentTime = Math.floor(player.currentTime);
      const duration = Math.floor(player.duration);
      // 仅在值变化时 setData，进一步减少渲染
      if (currentTime !== this.data.currentTime || duration !== this.data.duration) {
        this.setData({ currentTime, duration });
      }
      // 任务3：每 5s 同步续播缓存（用 currentTime 整数秒，节流）
      const ep = this.data.episode;
      if (ep && currentTime > 0 && currentTime % 5 === 0) {
        try {
          const last = { ...ep, currentTime };
          wx.setStorageSync('lastPlayedEpisode', last);
          if (!this.data.lastPlayedEpisode) {
            this.setData({ lastPlayedEpisode: last });
          }
        } catch (e) {}
      }
    };
    this._onEnded = () => {
      this.setData({ isPlaying: false, currentTime: 0, currentEpisodeId: null });
    };

    player.onPlay(this._onPlay);
    player.onPause(this._onPause);
    player.onTimeUpdate(this._onTimeUpdate);
    player.onEnded(this._onEnded);
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
    player.seek(position);
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
      player.play();
      wx.navigateTo({ url: '/pages/detail/detail?id=' + id });
      return;
    }
    // 切换到新节目
    playEpisode(ep);
    try {
      wx.setStorageSync('lastPlayedEpisode', { ...ep, currentTime: 0 });
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
      player.play();
      wx.navigateTo({ url: '/pages/detail/detail?id=' + last.id });
      return;
    }
    // 切换到新节目：先播放，再 seek 到上次位置
    playEpisode(last);
    const targetTime = last.currentTime || 0;
    if (targetTime > 0 && player) {
      const onCanplay = () => {
        try { player.seek(targetTime); } catch (e) {}
        player.offCanplay?.(onCanplay);
      };
      player.onCanplay(onCanplay);
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
