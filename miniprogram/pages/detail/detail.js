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
const { fetchEpisodeDetail, fetchEpisodeScript, checkFavorite, addFavorite, removeFavorite } = require('../../services/api');
const { fetchComments, postComment, likeComment, unlikeComment } = require('../../services/api');
const {
  playEpisode, playNext, playPrev, getQueue, getQueueIndex, getCurrentEpisode,
  getPlaybackRate, setPlaybackRate, resumePlay,
  getSleepStatus, startSleepTimer, stopSleepTimer, onSleepChange, onError,
} = require('../../services/audio');
const { trackPageView, trackEvent } = require('../../utils/tracker');

const RATE_OPTIONS = [1.0, 1.25, 1.5, 0.75, 2.0];
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
    // V1.3 新增
    favorited: false,
    currentRate: 1.0,
    sources: [],          // 节目来源（稿件加载后填充）
    hasPrev: false,       // 队列中是否有上一首
    hasNext: false,       // 队列中是否有下一首
    sleepActive: false,
    sleepLabel: '',
    playError: '',         // 播放错误文案（音频文件丢失等情况，持久显示在播放卡片上）
    // 任务8：评论区
    comments: [],
    commentsTotal: 0,
    commentLoading: false,
    commentText: '',
    postingComment: false,
    // 任务10：背景虚化图（取自 segments 第一张 cover_url）
    bgCoverUrl: '',
  },

  onLoad(options) {
    trackPageView('pages/detail/detail');
    const id = options.id;
    if (!id) {
      this.setData({ loading: false, error: '缺少节目参数' });
      return;
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
    const player = getApp().globalData.player;
    if (player) {
      player.offPlay?.(this._onPlay);
      player.offPause?.(this._onPause);
      player.offTimeUpdate?.(this._onTimeUpdate);
      player.offEnded?.(this._onEnded);
    }
    this._onPlay = null;
    this._onPause = null;
    this._onTimeUpdate = null;
    this._onEnded = null;
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
   * 检查收藏态
   */
  async checkFavorited(id) {
    try {
      const res = await checkFavorite(id);
      this.setData({ favorited: !!(res && res.favorited) });
    } catch (err) {
      this.setData({ favorited: false });
    }
  },

  /**
   * 收藏/取消收藏
   */
  async onToggleFavorite() {
    const ep = this.data.episode;
    if (!ep) return;
    try {
      if (this.data.favorited) {
        await removeFavorite(ep.id);
        this.setData({ favorited: false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
        trackEvent('detail', 'unfavorite', 'episode_' + ep.id);
      } else {
        await addFavorite(ep.id);
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

  bindPlayerEvents() {
    const player = getApp().globalData.player;
    if (!player) return;

    this._onPlay = () => {
      // 宽松判断：episode 还在加载时也允许设置 isPlaying=true
      // 任务2：从"继续播放"跳转到 detail 页时，episode 可能还没加载完，
      // 此时 onPlay 已触发，应立即显示播放状态（pause 图标）
      const cur = getCurrentEpisode();
      if (!cur) return;
      if (this.data.episode && this.data.episode.id !== cur.id) return;
      this.setData({ isPlaying: true, durationText: this.formatTime(player.duration) });
    };
    this._onPause = () => {
      if (!this.isCurrentEpisode()) return;
      this.setData({ isPlaying: false });
    };
    this._onTimeUpdate = () => {
      if (!this.isCurrentEpisode()) return;
      // 节流：onTimeUpdate 每秒约触发 5 次，频繁 setData 会阻塞渲染导致卡顿
      // 限制为至少 800ms 间隔才 setData 一次，进度条更新足够流畅
      const now = Date.now();
      if (this._lastTimeUpdateTs && now - this._lastTimeUpdateTs < 800) return;
      this._lastTimeUpdateTs = now;
      const ct = Math.floor(player.currentTime) || 0;
      const du = Math.floor(player.duration) || 0;
      // 仅在值变化时 setData，进一步减少渲染
      if (ct !== this.data.currentTime || du !== this.data.duration) {
        this.setData({
          currentTime: ct,
          duration: du,
          currentTimeText: this.formatTime(player.currentTime),
          durationText: this.formatTime(player.duration),
        });
      }
    };
    this._onEnded = () => {
      // 结束后队列索引可能变化，刷新上一首/下一首状态
      this.setData({ isPlaying: false, currentTime: 0, currentTimeText: '00:00' });
      this.refreshQueueState();
    };

    player.onPlay(this._onPlay);
    player.onPause(this._onPause);
    player.onTimeUpdate(this._onTimeUpdate);
    player.onEnded(this._onEnded);
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
    } else {
      playEpisode(ep);
      trackEvent('detail', 'play', 'episode_' + ep.id);
    }
  },

  onSeek(e) {
    const player = getApp().globalData.player;
    if (!player || !this.isCurrentEpisode()) return;
    const pos = e.detail.value;
    player.seek(pos);
    this.setData({ currentTime: pos, currentTimeText: this.formatTime(pos) });
  },

  /**
   * 上一首/下一首：依赖 audio.js 队列
   * 队列未设置时 getQueueIndex 返回 -1，按钮自动隐藏
   */
  onPrev() {
    if (playPrev()) {
      trackEvent('detail', 'play_prev');
      // 切换后需重新加载新节目详情到本页（标题/文稿/评论/收藏态都需刷新）
      const cur = getCurrentEpisode();
      if (cur && cur.id) {
        this.setData({
          episode: cur,
          script: '',
          segments: [],
          scriptLoaded: false,
          comments: [],
          commentsTotal: 0,
          bgCoverUrl: '',
        });
        this.loadDetail(cur.id);
        this.checkFavorited(cur.id);
        this.loadComments(cur.id);
      }
      setTimeout(() => this.refreshQueueState(), 100);
    }
  },

  onNext() {
    if (playNext()) {
      trackEvent('detail', 'play_next');
      // 切换后需重新加载新节目详情到本页（标题/文稿/评论/收藏态都需刷新）
      const cur = getCurrentEpisode();
      if (cur && cur.id) {
        this.setData({
          episode: cur,
          script: '',
          segments: [],
          scriptLoaded: false,
          comments: [],
          commentsTotal: 0,
          bgCoverUrl: '',
        });
        this.loadDetail(cur.id);
        this.checkFavorited(cur.id);
        this.loadComments(cur.id);
      }
      setTimeout(() => this.refreshQueueState(), 100);
    }
  },

  /**
   * 任务3：打开播放队列页
   */
  onOpenQueue() {
    trackEvent('detail', 'open_queue');
    wx.navigateTo({ url: '/pages/queue/queue' });
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

  formatSleepLabel(sec) {
    if (sec <= 0) return '';
    const m = Math.floor(sec / 60);
    if (m < 60) return m + ' 分钟后停止';
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? h + '小时' + rest + '分钟后停止' : h + '小时后停止';
  },

  /**
   * 点击节目来源标题，跳转到 webview 页面加载原文
   * 微信小程序禁止 navigateTo 外链，但可用 <web-view> 组件承载
   * 业务域名需在公众平台后台配置；开发时勾选"不校验业务域名"可临时跳过
   */
  onTapSource(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    trackEvent('detail', 'tap_source', '', url);
    // 业务域名未在小程序后台配置时，<web-view> 会显示微信原生的"无法打开该页面"（用户截图反馈）
    // 即使我们已实现 fallback 页面，微信是在 web-view 加载前直接拦截，binderror 不会触发，fallback 永远不显示
    // 因此改为：弹 ActionSheet 让用户选"复制链接"（不依赖业务域名，100% 可用）
    wx.showActionSheet({
      itemList: ['复制链接', '在小程序内打开'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this._copySourceUrl(url);
        } else {
          const encoded = encodeURIComponent(url);
          wx.navigateTo({
            url: `/pages/webview/webview?url=${encoded}`,
            fail: () => this._copySourceUrl(url),
          });
        }
      },
    });
  },

  /**
   * 复制节目来源 URL 到剪贴板 + 引导用户去浏览器打开
   * 不依赖 web-view 业务域名配置，是唯一 100% 可用的兜底方案
   */
  _copySourceUrl(url) {
    wx.setClipboardData({
      data: url,
      success: () => {
        wx.showModal({
          title: '链接已复制',
          content: '节目来源链接已复制到剪贴板，请到浏览器粘贴打开查看原文。',
          showCancel: false,
          confirmText: '我知道了',
          confirmColor: '#5BA89B',
        });
      },
      fail: () => {
        wx.showToast({ title: '复制链接失败，请手动长按复制', icon: 'none' });
      },
    });
  },

  onShareAppMessage() {
    const ep = this.data.episode || {};
    return {
      title: ep.title || '今日要闻',
      path: '/pages/detail/detail?id=' + (ep.id || ''),
    };
  },

  onBackHome() {
    wx.switchTab({ url: '/pages/index/index' });
  },
});
