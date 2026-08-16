/**
 * 节目详情页：展示节目元数据 + 播放控制 + 稿件懒加载
 *
 * V1.3 新增：
 * - 收藏按钮（FR-SUP-02）
 * - 倍速控制（FR-SUP-06）
 * - 上一首/下一首（FR-SUP-05）- 依赖播放队列
 * - 睡眠定时器入口（FR-SUP-08）
 * - 节目来源展示（FR-SUP-12）- sources 字段
 * - 埋点（FR-SUP-10）
 */
const {
  fetchEpisodeDetail,
  fetchEpisodeScript,
  fetchComments,
  postComment,
  likeComment,
  unlikeComment,
  getChannelMeta,
  channelType,
} = require('../../services/api');
// localData 封装收藏的双写（本地+后端），按 openid 隔离
const localData = require('../../services/local-data');
const {
  playEpisode, playNext, playPrev, playQueueAt, getQueue, getQueueIndex, getCurrentEpisode, setQueue,
  getPlaybackRate, setPlaybackRate, resumePlay, setPendingSeek, seek,
  getSleepStatus, startSleepTimer, stopSleepTimer, onSleepChange, onError, clearQueue,
  onPlaybackChange,
  onWaitingChange, offWaitingChange,
  onTimeUpdateChange, offTimeUpdateChange,
} = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');
const { copySourceUrl } = require('../../utils/clipboard');
const skin = require('../../utils/skin');

const RATE_OPTIONS = [0.75, 1.0, 1.25, 1.5, 2.0];
const SLEEP_PRESETS = [
  { label: '关闭', value: 0 },
  { label: '15 分钟', value: 900 },
  { label: '30 分钟', value: 1800 },
  { label: '45 分钟', value: 2700 },
  { label: '60 分钟', value: 3600 },
];

Page({
  data: {
    episode: null,
    script: '',            // 稿件全文（向后兼容，旧稿件无 segments 时展示）
    segments: [],          // 稿件分段（含 cover_url，新稿件按段渲染图文）
    scriptLoaded: false,
    scriptLoading: false,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    currentTimeText: '00:00',
    durationText: '00:00',
    durationLabel: '',
    loading: true,
    error: '',
    // 音频缓冲中：onWaiting 触发时显示菊花，onCanplay/onPlay 解除
    isWaiting: false,
    // V1.3 新增
    favorited: false,
    currentRate: 1.0,
    sources: [],          // 节目来源（稿件加载后填充）
    hasPrev: false,       // 队列中是否有上一首
    hasNext: false,       // 队列中是否有下一首
    sleepActive: false,
    sleepLabel: '',
    playError: '',         // 播放错误文案（音频文件丢失等情况，持久显示在播放卡片上）
    seekTimestamp: 0,          // seek后500ms内忽略onTimeUpdate覆盖
    lastProgressSaveTs: 0,     // 上次上报后端进度的节流时间戳（5s 节流），防止每次 onTimeUpdate 都打网络
    lastListenStartTs: 0,      // 本次播放周期起点（用于计算 listened_seconds 增量）
    // 课程章节语义（FR-MC-04）：从课程主页跳转时携带，用于显示「第X章/共Y章」
    isCourse: false,
    courseChannelId: '',
    courseName: '',
    chapterLabel: '',
    // FR-MC-11 合规提示：按频道 disclaimer_level 展示 AI 生成提示条（空串不展示）
    disclaimerText: '',
    disclaimerLevel: '',
    // 任务8：评论区
    comments: [],
    commentsTotal: 0,
    commentLoading: false,
    commentText: '',
    postingComment: false,
    // 任务10：背景虚化图（取自 segments 第一张 cover_url）
    bgCoverUrl: '',
    // 播放队列弹窗
    showQueueModal: false,
    queue: [],
    currentIndex: -1,
  },

  onLoad(options) {
    trackPageView('pages/detail/detail');
    const id = options.id;
    if (!id) {
      this.setData({ loading: false, error: '缺少节目参数' });
      return;
    }
    // 课程章节语义（FR-MC-04）：从课程主页跳转时携带 channelId/chapterIndex/chapterTotal
    // 仅当频道类型为 course/audiobook 时启用，news 频道无此语义（向后兼容）
    const channelId = options.channelId;
    if (channelId && channelType(channelId) !== 'news') {
      const chapterIndex = Number(options.chapterIndex) || 0;
      const chapterTotal = Number(options.chapterTotal) || 0;
      const meta = getChannelMeta(channelId);
      // FR-MC-11：合规提示文案按频道 disclaimer_level 分级（none 不展示）
      const level = (meta && meta.disclaimer_level) || 'none';
      this.setData({
        isCourse: true,
        courseChannelId: channelId,
        courseName: (meta && meta.name) || '',
        chapterLabel: (chapterIndex && chapterTotal)
          ? ('第 ' + chapterIndex + ' 章 / 共 ' + chapterTotal + ' 章')
          : '',
        disclaimerLevel: level,
        disclaimerText: skin.getDisclaimerText(level),
      });
    }
    this._unsubSleep = onSleepChange((status) => {
      this.setData({
        sleepActive: status.active,
        sleepLabel: status.active ? this.formatSleepLabel(status.remaining) : '',
      });
    });
    // 播放错误时重置 UI：加载失败不会触发 onPause，需订阅 onError 否则按钮卡死
    // audio.js 已重置 currentEpisode=null，此处仅同步页面态并展示持久错误提示
    this._unsubError = onError((err) => {
      // errCode 10001 是 MEDIA_ERR_SRC_NOT_SUPPORTED，通常是 URL 404/503 导致
      const tip = (err && err.errCode === 10001)
        ? '音频文件已被清理或暂时不可访问'
        : '音频加载失败，请稍后重试';
      this.setData({ isPlaying: false, playError: tip });
    });
    // 订阅播放状态变化：监听 currentEpisode 切换 + 播放/暂停状态同步（任务6）
    // 当播放器切换到与本页不同的节目时，自动同步页面到新节目。
    // 节目未变化时同步 isPlaying 状态：解决 player.onPlay/onPause 与 onPlaybackChange
    // 两套事件源时序不一致导致按钮卡在"播放中"的问题。
    this._unsubPlayback = onPlaybackChange((evt) => {
      const cur = getCurrentEpisode();
      // 播放器无当前节目（错误/停止）：不处理，留给 onError
      if (!cur) return;
      // 节目未变化：仅同步播放状态（evt.paused 来自 audio.js notifyPlaybackListeners）
      if (this.data.episode && this.data.episode.id === cur.id) {
        if (typeof evt.paused === 'boolean') {
          this.setData({ isPlaying: !evt.paused });
        }
        // ended：重置进度条 UI + 刷新队列状态
        // audio.js 的 onEnded 已处理 playNext 自动连播 + saveProgress + addHistory，
        // 此处仅同步 UI（不直接注册 player.onEnded，避免覆盖 audio.js 的 onEnded 回调）
        if (evt.type === 'ended') {
          this.setData({ currentTime: 0, currentTimeText: '00:00' });
          this.refreshQueueState();
          // FR-MC-10：课程章节完播埋点（SRS §4.10 chapter_finish）
          // 仅当本页是课程章节时上报，避免污染资讯类完播数据
          if (this.data.isCourse) {
            const chId = Number(this.data.courseChannelId) || 0;
            trackEvent('course', 'chapter_finish', 'episode_' + cur.id, chId || undefined);
          }
        }
        // play：更新 durationText（onCanplay 后 duration 才有准确值）
        if (evt.type === 'play') {
          const player = getApp().globalData.player;
          if (player) this.setData({ durationText: this.formatTime(player.duration) });
        }
        return;
      }
      // 节目已变化：切换页面到新节目（标题/文稿/评论/收藏态都需刷新）
      this._syncToEpisode(cur);
    });
    // 订阅音频 loading 状态：onWaiting 显示菊花，onCanplay/onPlay 解除
    // 不在 _syncToEpisode 内重置：避免切换页面时清掉了刚到的 waiting=true
    this._onWaitingChange = (waiting) => {
      this.setData({ isWaiting: !!waiting });
    };
    onWaitingChange(this._onWaitingChange);
    this.bindPlayerEvents();
    this.loadDetail(id);
    this.checkFavorited(id);
    this.refreshQueueState();
    this.loadComments(id);
    this.setData({ currentRate: getPlaybackRate() });
  },

  onUnload() {
    if (this._unsubSleep) this._unsubSleep();
    if (this._unsubError) this._unsubError();
    if (this._unsubPlayback) this._unsubPlayback();
    // 取消 waiting 订阅：避免页面销毁后回调仍触发 setData 报错
    if (this._onWaitingChange) {
      offWaitingChange(this._onWaitingChange);
      this._onWaitingChange = null;
    }
    // 取消 timeUpdate 订阅：避免页面销毁后回调仍触发 setData 报错
    if (this._onTimeUpdateChange) {
      offTimeUpdateChange(this._onTimeUpdateChange);
      this._onTimeUpdateChange = null;
    }
    // 清理 _calcListenDelta 内部状态：避免页面销毁后 setData 引用泄漏
    this._lastListenDeltaInited = false;
  },

  /**
   * 任务5：每次显示页面时同步倍速设置（其他页面修改倍速后会反映到本页）
   * 进度持久化已在 audio.js startProgressReport + playEpisode 的 fetchPlayProgress
   * 中实现，此处只需同步 UI 显示的倍速值
   */
  onShow() {
    this.setData({ currentRate: getPlaybackRate() });
    // 若当前播放的就是本页节目，同步一次进度状态
    if (this.isCurrentEpisode()) {
      this.syncPlayingState();
    }
  },

  async loadDetail(id) {
    try {
      const episode = await fetchEpisodeDetail(id);
      this.setData({
        episode,
        loading: false,
        durationLabel: this.formatDuration(episode.duration),
        // 任务10：先用 episode 自带的 cover_url 作为背景，避免等 loadScript 才显示
        // 后续 onLoadScript 加载完后会用 segments 第一张 cover 覆盖（更精确）
        bgCoverUrl: episode.cover_url || '',
      });
      this.syncPlayingState();
    } catch (err) {
      this.setData({ loading: false, error: err.message || '加载失败' });
    }
  },

  /**
   * 检查收藏态（优先本地，本地无时从后端读取）
   */
  async checkFavorited(id) {
    try {
      const res = await localData.checkFavoriteLocal(id);
      this.setData({ favorited: !!(res && res.favorited) });
    } catch (err) {
      this.setData({ favorited: false });
    }
  },

  /**
   * 收藏/取消收藏（双写本地+后端）
   */
  async onToggleFavorite() {
    const ep = this.data.episode;
    if (!ep) return;
    try {
      if (this.data.favorited) {
        await localData.removeFavorite(ep.id);
        this.setData({ favorited: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
        trackEvent('detail', 'unfavorite', 'episode_' + ep.id);
      } else {
        // addFavorite 需要完整 episode 对象（用于本地列表展示）
        await localData.addFavorite(ep);
        this.setData({ favorited: true });
        wx.showToast({ title: '已收藏', icon: 'success' });
        trackEvent('detail', 'favorite', 'episode_' + ep.id);
      }
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  /**
   * 刷新上一首/下一首可用状态
   * 根据当前队列索引判断
   */
  refreshQueueState() {
    const idx = getQueueIndex();
    const queue = getQueue();
    this.setData({
      hasPrev: idx > 0,
      hasNext: idx >= 0 && idx < queue.length - 1,
    });
  },

/**
   * 加载节目列表（用于队列弹窗自动填充）
   * 为什么用 fetchTodayEpisode（不带 s）：services/api 只导出此函数（返回单个对象或数组），
   * 历史代码误用 fetchTodayEpisodes（带 s，未定义）会被 catch 吞掉降级为 [episode]，
   * 导致队列只有 1 项、playNext 直接判定"已是最后一首"
   */
  async fetchEpisodeList() {
    const episode = this.data.episode;
    if (!episode) return [];
    // 尝试从今日接口获取同频道全部节目
    try {
      const { fetchTodayEpisode } = require("../../services/api");
      const res = await fetchTodayEpisode();
      const episodes = Array.isArray(res) ? res : (res && res.list) || [];
      // 过滤掉无效的
      return episodes.filter(x => x && x.audio_url);
    } catch (err) {
      console.log("加载节目列表失败，降级为单条:", err.message);
      return [episode];
    }
  },

  bindPlayerEvents() {
    // 不直接在 BackgroundAudioManager 上注册 onPlay/onPause/onTimeUpdate/onEnded
    // 原因：BackgroundAudioManager.onXxx 是覆盖式注册，会覆盖 audio.js initPlayer 中
    // 注册的回调（含 playNext 自动连播、startProgressReport、applyPlaybackRate 等核心逻辑），
    // 导致自动连播失效、进度不上报、倍速丢失等问题。
    // 改为通过 audio.js 的订阅接口（onPlaybackChange/onTimeUpdateChange）监听事件。

    this._onTimeUpdateChange = (ct, du) => {
      if (!this.isCurrentEpisode()) return;
      // seek后1500ms内忽略timeUpdate回调，防止重缓冲把进度重置为0
      // 真机重缓冲（尤其弱网）常需 1-3s，500ms 防抖不足
      if (Date.now() - (this.data.seekTimestamp || 0) < 1500) return;
      // audio.js 的 onTimeUpdate 已做 800ms 节流，此处不再重复节流
      if (ct !== this.data.currentTime || du !== this.data.duration) {
        this.setData({
          currentTime: ct,
          duration: du,
          currentTimeText: this.formatTime(ct),
          durationText: this.formatTime(du),
        });
      }
      // 5s 节流上报后端进度
      // listened_seconds 取本周期实际播放增量（不包含暂停/缓冲时间），
      // 用于累加 User.total_listen_duration
      const now = Date.now();
      if (now - (this.data.lastProgressSaveTs || 0) >= 5000) {
        this.setData({ lastProgressSaveTs: now });
        const listenDelta = this._calcListenDelta(ct);
        localData.saveProgress(this.data.episode.id, ct, du, false, listenDelta).catch(() => {});
      }
    };
    onTimeUpdateChange(this._onTimeUpdateChange);
  },

  /**
   * 任务2：判断当前页面展示的节目是否就是播放器正在播放的节目
   * 旧实现用 player.episodeId 自定义属性，但 onError 触发时 currentEpisode 会被
   * 置空而 episodeId 字段不会同步清空，导致 isCurrentEpisode 误判为 true，
   * 进而 _onTimeUpdate 持续写过期值，进度条卡住不动。
   * 改用 getCurrentEpisode() 比较 id 更可靠。
   */
  isCurrentEpisode() {
    const ep = this.data.episode;
    const cur = getCurrentEpisode();
    return !!(ep && cur && cur.id === ep.id);
  },

  syncPlayingState() {
    const player = getApp().globalData.player;
    if (!player) return;
    const cur = getCurrentEpisode();
    if (!cur) return;
    // 任务2：episode 未加载完时也允许同步 isPlaying（继续播放跳转场景）
    // 旧实现要求 !player.duration 才同步，但缓冲中 duration=0 会导致 isPlaying 不更新
    if (this.data.episode && this.data.episode.id !== cur.id) return;
    this.setData({
      isPlaying: !player.paused,
      currentTime: Math.floor(player.currentTime) || 0,
      duration: Math.floor(player.duration) || 0,
      currentTimeText: this.formatTime(player.currentTime),
      durationText: this.formatTime(player.duration),
    });
  },

  onPlay() {
    const ep = this.data.episode;
    if (!ep) return;
    playEpisode(ep);
    trackEvent('detail', 'play', 'episode_' + ep.id);
  },

  onTogglePlay() {
    const player = getApp().globalData.player;
    const ep = this.data.episode;
    if (!player || !ep) return;
    // 重新发起播放时清空上次的播放错误提示
    if (this.data.playError) this.setData({ playError: '' });
    if (this.isCurrentEpisode()) {
      player.paused ? player.play() : player.pause();
      // 即时反馈：player.play/pause 是异步的，onPlay/onPause 回调可能有延迟，
      // 先用 player.paused 当前值更新 UI，避免用户点击后按钮无反应（任务6）
      this.setData({ isPlaying: !player.paused });
    } else {
      playEpisode(ep);
      trackEvent('detail', 'play', 'episode_' + ep.id);
    }
  },

  // bindinput：拖动中仅更新 UI 预览，不触发实际 seek
  onSeekInput(e) {
    const pos = e.detail.value;
    this.setData({ currentTime: pos, currentTimeText: this.formatTime(pos) });
  },

  onSeek(e) {
    const player = getApp().globalData.player;
    if (!player || !this.isCurrentEpisode()) return;
    const pos = e.detail.value;
    // 调用 services/audio 的 seek 函数：处理暂停状态下 seek 不生效的问题
    seek(pos);
    // 记录seek时间点，onTimeUpdate会忽略seek后1500ms内的回调，
    // 防止重缓冲期间 onTimeUpdate 把进度拉回旧值或 0（真机重缓冲常需 1-3s）
    this.setData({
      currentTime: pos,
      currentTimeText: this.formatTime(pos),
      isPlaying: true,
      seekTimestamp: Date.now()
    });
  },

  /**
   * 上一首/下一首：依赖 audio.js 队列
   * 队列未设置时 getQueueIndex 返回 -1，按钮自动隐藏
   *
   * 切换后页面的同步由 onPlaybackChange 订阅统一处理：
   * playNext/playPrev 调用后 playEpisode 是异步的（缺 audio_url 时要先 fetch 详情），
   * 此处同步读 getCurrentEpisode 会拿到旧值，故不再手动 setData episode。
   */
  onPrev() {
    if (playPrev()) {
      trackEvent('detail', 'play_prev');
      // 刷新队列状态由订阅回调统一处理，避免重复 setData
    }
  },

  onNext() {
    if (playNext()) {
      trackEvent('detail', 'play_next');
      // 刷新队列状态由订阅回调统一处理，避免重复 setData
    }
  },

  /**
   * 同步页面到指定节目（下一首/上一首/自动连播/队列点击共用）
   * 重置稿件/评论/收藏态，重新拉取新节目详情。
   * @param {Object} ep - 新节目对象（可能为摘要，缺 audio_url，loadDetail 会补齐）
   */
  _syncToEpisode(ep) {
    if (!ep || !ep.id) return;
    this.setData({
      episode: ep,
      script: '',
      segments: [],
      scriptLoaded: false,
      comments: [],
      commentsTotal: 0,
      bgCoverUrl: ep.cover_url || '',
      playError: '',          // 切换节目时清空上次的播放错误
      currentTime: 0,         // 重置进度条，避免显示旧节目进度
      currentTimeText: '00:00',
      duration: 0,
      durationText: '00:00',
      seekTimestamp: 0,       // 清空 seek 防抖标记，避免新节目 onTimeUpdate 被误忽略
    });
    // 切歌时重置 listenedSeconds 基准：下一首首次 _calcListenDelta 仅记录新 position
    // 而非沿用上一首的 lastListenStartTs，避免跨节目累加
    this._lastListenDeltaInited = false;
    this.loadDetail(ep.id);
    this.checkFavorited(ep.id);
    this.loadComments(ep.id);
    this.refreshQueueState();
  },

  /**
   * 倍速循环切换
   */
  onCycleRate() {
    const current = getPlaybackRate();
    const idx = RATE_OPTIONS.indexOf(current);
    const next = RATE_OPTIONS[(idx + 1) % RATE_OPTIONS.length];
    setPlaybackRate(next);
    this.setData({ currentRate: next });
    wx.showToast({ title: next + 'x 倍速', icon: 'none' });
    trackEvent('detail', 'change_rate', '', next);
  },

  /**
   * 睡眠定时器
   */
  onSleepTimer() {
    wx.showActionSheet({
      itemList: SLEEP_PRESETS.map((p) => p.label),
      success: (res) => {
        const preset = SLEEP_PRESETS[res.tapIndex];
        if (preset.value === 0) {
          stopSleepTimer();
          wx.showToast({ title: '已关闭睡眠定时', icon: 'none' });
        } else {
          startSleepTimer(preset.value);
          wx.showToast({ title: '睡眠定时 ' + preset.label, icon: 'none' });
          trackEvent('detail', 'sleep_timer_on', '', preset.value);
        }
      },
    });
  },

  /**
   * 懒加载稿件：用户点击"查看完整文稿"才请求
   * V1.3：稿件接口返回 sources 字段，展示版权溯源
   */
  async onLoadScript() {
    if (this.data.scriptLoaded || this.data.scriptLoading) return;
    const ep = this.data.episode;
    if (!ep) return;

    this.setData({ scriptLoading: true });
    try {
      const res = await fetchEpisodeScript(ep.id);
      const content = typeof res === 'string'
        ? res
        : (res && (res.script || res.content)) || '';
      const sources = (res && res.sources) || [];
      // segments 含 cover_url，按段渲染图文；旧稿件无 segments 时降级为纯文本
      const segments = (res && Array.isArray(res.segments)) ? res.segments : [];
      this.setData({
        script: content,
        segments,
        scriptLoaded: true,
        scriptLoading: false,
        sources,
      });
      // 任务10：取 segments 第一张 cover_url 作为详情页虚化背景
      const firstCover = segments.find(s => s && s.cover_url);
      if (firstCover) {
        this.setData({ bgCoverUrl: firstCover.cover_url });
      }
    } catch (err) {
      console.error('加载文稿失败:', err);
      this.setData({ scriptLoading: false });
      wx.showToast({ title: '文稿加载失败', icon: 'none' });
    }
  },

  // ==================== 任务8：评论区 ====================

  /**
   * 加载评论列表
   */
  async loadComments(episodeId) {
    if (!episodeId) return;
    this.setData({ commentLoading: true });
    try {
      const res = await fetchComments(episodeId);
      const list = (res && (res.list || res.items)) || [];
      this.setData({
        comments: list,
        commentsTotal: (res && res.total) || list.length,
        commentLoading: false,
      });
    } catch (err) {
      this.setData({ commentLoading: false });
      // 评论加载失败不影响节目浏览，静默处理
      console.log('评论加载失败:', err.message || err);
    }
  },

  /**
   * 输入评论内容
   */
  onInputComment(e) {
    this.setData({ commentText: e.detail.value || '' });
  },

  /**
   * 发布评论
   *
   * 任务5：附带当前登录用户的 user_name/user_avatar 作为兜底
   * 即使用户从未进 profile 页（User 表没存头像昵称），评论也能正确显示
   * 后端优先用前端值、否则从 User 表读
   */
  async onPostComment() {
    const { episode, commentText, postingComment } = this.data;
    if (postingComment) return;
    const content = (commentText || '').trim();
    if (!content) {
      wx.showToast({ title: '请输入评论内容', icon: 'none' });
      return;
    }
    if (!episode) return;
    this.setData({ postingComment: true });
    try {
      const app = getApp();
      const ui = app.globalData.userInfo || {};
      await postComment({
        episode_id: episode.id,
        content,
        // 兼容多种字段名（fetchWxProfile 返回 avatar/nickname，wx.login 可能返回 avatarUrl/nickName）
        user_name: ui.nickname || ui.nickName || undefined,
        user_avatar: ui.avatar || ui.avatarUrl || undefined,
      });
      this.setData({ commentText: '', postingComment: false });
      wx.showToast({ title: '评论成功', icon: 'success' });
      trackEvent('detail', 'post_comment', 'episode_' + episode.id);
      // 刷新评论列表
      this.loadComments(episode.id);
    } catch (err) {
      this.setData({ postingComment: false });
      wx.showToast({ title: err.message || '评论失败', icon: 'none' });
    }
  },

  /**
   * 点赞评论
   */
  async onLikeComment(e) {
    const { id, index } = e.currentTarget.dataset;
    const item = this.data.comments[index];
    if (!item) return;
    try {
      if (item.liked) {
        await unlikeComment(id);
      } else {
        await likeComment(id);
      }
      // 局部更新避免整列重新渲染
      const newList = this.data.comments.map((c, i) => {
        if (i === index) {
          return {
            ...c,
            liked: !c.liked,
            like_count: (c.like_count || 0) + (c.liked ? -1 : 1),
          };
        }
        return c;
      });
      this.setData({ comments: newList });
      trackEvent('detail', item.liked ? 'unlike_comment' : 'like_comment', 'comment_' + id);
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  /**
   * 预览评论用户头像大图
   */
  onPreviewAvatar(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    wx.previewImage({ urls: [url] });
  },

  /**
   * 计算本周期实际播放增量（秒），用于累加 User.total_listen_duration
   *
   * 实现思路（与 services/audio.js#startProgressReport 内部 lastReportedPosition 思路一致）：
   * - 首次调用：仅记录当前 ct 作为下次基准，return 0
   *   避免 detail 页打开时进度已 > 0（断点续播）被误算为收听增量
   * - 后续调用：delta = ct - lastListenStartTs
   *   - delta > 0：正常前进，作为 listenSeconds 透传 saveProgress
   *   - delta <= 0：用户 seek 后退或未前进（缓冲中），return 0 避免负累加
   *
   * 用闭包标志 _lastListenDeltaInited 区分"首次调用"——data 字段 lastListenStartTs
   * 初始值 0 本身就是合法 position，不能用作哨兵。
   *
   * @param {number} ct - 当前播放位置（秒）
   * @returns {number} 本周期收听增量（秒，非负）
   */
  _calcListenDelta(ct) {
    if (!this._lastListenDeltaInited) {
      this._lastListenDeltaInited = true;
      this.setData({ lastListenStartTs: ct });
      return 0;
    }
    const last = this.data.lastListenStartTs;
    this.setData({ lastListenStartTs: ct });
    return ct > last ? ct - last : 0;
  },

  /**
   * 封面图加载失败回调：原站防盗链/删图时自然降级，隐藏 <image> 占位
   * 通过设置该段 cover_url 为空触发 wxml 条件渲染切换
   */
  onCoverError(e) {
    const seq = e.currentTarget.dataset.seq;
    const segments = this.data.segments.map((seg) =>
      seg.seq === seq ? { ...seg, cover_url: '' } : seg
    );
    this.setData({ segments });
  },

  formatTime(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  },

  formatDuration(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '0分钟';
    const m = Math.floor(sec / 60);
    if (m < 60) return m + '分钟';
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? h + '小时' + rest + '分钟' : h + '小时';
  },

  /**
   * 定时文案缩短（v2）：
   * - "1时30分"（4 字符）会在窄屏溢出 action-chip，改为 "1时半"（3 字符）
   * - 其余分支保持：< 60 分用 "X分"，整点小时用 "X时"
   * - iOS 风格 "X分"/"X时半" 比 "X分钟后停止" 更符合倒计时认知
   */
  formatSleepLabel(sec) {
    if (sec <= 0) return '';
    const m = Math.floor(sec / 60);
    if (m < 60) return m + '分';
    const h = Math.floor(m / 60);
    const rest = m % 60;
    if (rest === 0) return h + '时';
    if (rest === 30) return h + '时半';
    return h + '时' + rest + '分';
  },

  /**
   * 点击节目来源标题：直接复制链接并引导去浏览器打开
   *
   * 为什么不用 ActionSheet + "在小程序内打开"：
   * web-view 组件只能加载已在微信公众平台后台配置的业务域名，节目来源域名（如 ithome.com）
   * 不在白名单内，"在小程序内打开"必然失败→显示 fallback 界面，用户体验等于"无法显示页面"。
   * 直接复制链接 + modal 引导去浏览器是唯一可行路径。
   *
   * copySourceUrl 内部已处理：
   * - 复制成功 → 弹 modal 引导用户去浏览器粘贴打开
   * - 复制失败 → 跳转 webview fallback 页展示链接供手动复制
   */
  onTapSource(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    trackEvent('detail', 'tap_source', '', url);
    copySourceUrl(url);
  },


  /**
   * 打开播放队列弹窗（页内弹出，不跳转新页面）
   */
  /**
   * 打开播放队列弹窗：优先显示已有队列，队列为空时自动加载今日/历史列表
   */
  async onOpenQueue() {
    const queue = getQueue();
    const currentIndex = getQueueIndex();
    if (queue.length > 0) {
      // 已有队列：直接显示
      this.setData({ queue, currentIndex, showQueueModal: true });
      return;
    }
    // 队列未设置（如从分享链接直接进入详情页）：加载当日列表作为队列
    try {
      this.setData({ loading: true });
      const episodes = await this.fetchEpisodeList();
      if (episodes && episodes.length > 0) {
        setQueue(episodes);
        this.setData({
          queue: episodes,
          currentIndex: episodes.findIndex(x => x.id === this.data.episode?.id),
          showQueueModal: true,
        });
        trackEvent('detail', 'auto_queue_loaded', '', episodes.length);
      } else {
        this.setData({ showQueueModal: true });
      }
    } catch (err) {
      console.error('加载队列失败:', err.message);
      this.setData({ showQueueModal: true });
    } finally {
      this.setData({ loading: false });
    }
  },

  /**
   * 关闭播放队列弹窗
   */
  onCloseQueueModal() {
    this.setData({ showQueueModal: false });
  },

  /**
   * 阻止事件冒泡（点击弹窗内部不会触发遮罩层关闭）
   */
  stopPropagation() {
    // 空方法，仅用于 catchtap 阻止冒泡
  },

  /**
   * 防止滚动穿透
   */
  preventTouchMove() {
    // 空方法，仅用于 catchtouchmove 阻止滚动穿透
  },

  /**
   * 点击队列项：跳到该索引播放（同步更新 queueIndex）
   * 为什么用 playQueueAt 而非 playEpisode：
   * playEpisode 不更新 queueIndex，onEnded→playNext 时会从旧索引+1 播放，
   * 导致连播顺序错乱（用户点第3项后播完会跳到第2首而非第4首）
   */
  onQueueItemClick(e) {
    const { index } = e.currentTarget.dataset;
    const idx = Number(index);
    const episode = this.data.queue[idx];
    if (!episode) return;
    trackEvent('queue', 'tap_item', 'episode_' + episode.id);
    playQueueAt(idx);
    this.setData({ showQueueModal: false });
  },

  /**
   * 清空队列
   */
  onClearQueue() {
    clearQueue();
    trackEvent('queue', 'clear');
    this.setData({ queue: [], currentIndex: -1 });
  },

  onShareAppMessage() {
    const ep = this.data.episode || {};
    // 课程章节分享用课程名而非「今日要闻」（FR-MC-08 文案通用化）
    const title = this.data.isCourse
      ? (this.data.courseName || ep.title || '课程')
      : (ep.title || '今日要闻');
    return {
      title,
      path: '/pages/detail/detail?id=' + (ep.id || ''),
    };
  },

  onBackHome() {
    wx.switchTab({ url: '/pages/index/index' });
  },
});