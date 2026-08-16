/**
 * 课程主页（FR-MC-03 / FR-MC-04 / FR-MC-11）
 *
 * 复用既有内核，仅做「类型分支 + 课程语义 UI」：
 * - 章节列表：复用 GET /episodes/history?channel_id=&sort_order=asc（正序即章节序）
 * - 播放/连播：复用 services/audio（setQueue + playEpisode），不另起播放引擎
 * - 学习状态：基于本地 playlogs 进度聚合（position/duration ≥ 0.95 或 completed → 已学完）
 * - 合规提示：按频道 disclaimer_level 展示 AI 生成提示条（FR-MC-11）
 *
 * 进入条件：频道 channel_type 为 course / audiobook（由首页胶囊或频道管理页路由跳转）
 */

const {
  fetchChannels,
  fetchHistory,
  getChannelMeta,
  fetchCourseProgress,
  subscribeChannel,
  unsubscribeChannel,
  requestSubscribeMessageByType,
  fetchMySubscriptions,
  channelType,
} = require('../../services/api');
// localData 封装进度双写（本地+后端），按 openid 隔离
const localData = require('../../services/local-data');
const { playEpisode, setQueue, downloadEpisode, cancelDownload } = require('../../services/audio');
// 离线下载存储（FR-MC-09）：按 openid 持久化已下载章节
const downloadStore = require('../../services/download');
const { trackPageView, trackEvent } = require('../../utils/tracker');
const skin = require('../../utils/skin');

// 章节「已学完」判定阈值：统一收敛到 services/constants（与后端 _COMPLETE_RATIO 保持一致）
const { COURSE_COMPLETE_RATIO } = require('../../services/constants');

Page({
  data: {
    channelId: null,
    channel: null,            // 频道元信息（含 name/description/cover_url/disclaimer_level）
    coverUrl: '',             // 课程封面（频道封面优先，否则皮肤默认图）
    chapters: [],             // 章节列表（每章一期 episode，含 index/status/duration_label）
    loading: true,
    error: '',
    learnedCount: 0,          // 已学完章节数
    totalCount: 0,            // 章节总数
    percent: 0,               // 课程完成度百分比
    disclaimerText: '',       // 合规提示文案（空串不展示）
    isSubscribed: false,      // 当前用户是否已订阅该课程频道（FR-MC-06）
    subLoading: false,        // 订阅/取消订阅按钮防抖
    downloadedCount: 0,       // 已下载章节数（FR-MC-09）
    batchDownloading: false,  // 整课批量下载进行中（FR-MC-09）
    batchProgress: 0,         // 整课批量下载进度百分比（FR-MC-09）
  },

  onLoad(options) {
    trackPageView('pages/course/course');
    // FR-MC-10：课程浏览埋点（SRS §4.10 course_view）
    trackEvent('course', 'view', 'channel_' + (options.channelId || ''));
    const channelId = options.channelId;
    if (!channelId) {
      this.setData({ loading: false, error: '缺少课程参数' });
      return;
    }
    this.setData({ channelId });
    this.loadChannelMeta(channelId);
    this.loadChapters(channelId);
    this.loadSubState(channelId);
  },

  /**
   * 加载订阅状态（FR-MC-06）：通过「我的订阅频道」列表判定是否已订阅。
   * 未登录 / 接口失败时回退为未订阅（不影响浏览）。
   */
  async loadSubState(channelId) {
    try {
      const res = await fetchMySubscriptions();
      const list = (res && res.list) || [];
      const subscribed = list.some((c) => String(c.id) === String(channelId));
      this.setData({ isSubscribed: subscribed });
    } catch (e) {
      this.setData({ isSubscribed: false });
    }
  },

  /**
   * 订阅 / 取消订阅课程频道（FR-MC-06）
   * 订阅成功后按课程类型请求订阅消息授权（拒绝不影响频道订阅关系）。
   */
  async onToggleSubscribe() {
    if (this.data.subLoading) return;
    const id = this.data.channelId;
    const subscribing = !this.data.isSubscribed;
    this.setData({ subLoading: true });
    try {
      if (subscribing) {
        await subscribeChannel(id);
        this.setData({ isSubscribed: true });
        wx.showToast({ title: '订阅成功', icon: 'success' });
        // FR-MC-10：课程订阅埋点（SRS §4.10 course_subscribe）
        trackEvent('course', 'course_subscribe', 'channel_' + id);
        // 按课程类型请求订阅消息授权（拒绝不影响频道订阅）
        requestSubscribeMessageByType(channelType(id) || 'course');
      } else {
        await unsubscribeChannel(id);
        this.setData({ isSubscribed: false });
        wx.showToast({ title: '已取消订阅', icon: 'none' });
        // FR-MC-10：课程取消订阅埋点（对齐 course_subscribe 命名）
        trackEvent('course', 'course_unsubscribe', 'channel_' + id);
      }
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    } finally {
      this.setData({ subLoading: false });
    }
  },

  /**
   * 加载频道元信息：优先用已缓存的归一化频道对象，缺失时从接口拉取
   * 同时设置封面与合规提示文案（FR-MC-11）
   */
  async loadChannelMeta(channelId) {
    let meta = getChannelMeta(channelId);
    if (!meta) {
      try {
        const res = await fetchChannels();
        meta = (res.list || []).find((c) => String(c.id) === String(channelId)) || null;
      } catch (e) {
        meta = null;
      }
    }
    if (meta) {
      this.setData({
        channel: meta,
        coverUrl: meta.cover_url || skin.getSkin(meta.channel_type).defaultCover,
        disclaimerText: skin.getDisclaimerText(meta.disclaimer_level),
      });
      wx.setNavigationBarTitle({ title: meta.name || '课程' });
    }
  },

  /**
   * 加载章节列表并聚合学习状态
   * 章节顺序以 published_at 升序（API sort_order=asc），即课程章节顺序
   */
  async loadChapters(channelId) {
    this.setData({ loading: true, error: '' });
    try {
      const res = await fetchHistory(1, 50, channelId, 'asc');
      const list = (res && res.list) || [];
      const chapters = await Promise.all(
        list.map(async (ep, idx) => {
          let status = 'new'; // new | learning | finished
          try {
            const p = await localData.getProgress(ep.id);
            if (p) {
              const ratio = p.duration ? p.position / p.duration : 0;
              if (p.completed || ratio >= COURSE_COMPLETE_RATIO) status = 'finished';
              else if (p.position > 0) status = 'learning';
            }
          } catch (e) {
            // 进度读取失败不影响章节展示
          }
          return {
            ...ep,
            index: idx + 1,
            status,
            duration_label: this._fmtDur(ep.duration),
            cover_url: ep.cover_url || '',
            // FR-MC-09：下载状态（默认未下载/未在下载）
            downloaded: downloadStore.isDownloaded(ep.id),
            downloading: false,
            progress: 0,
          };
        })
      );

      const downloadedCount = chapters.filter((c) => c.downloaded).length;
      const learnedCount = chapters.filter((c) => c.status === 'finished').length;
      const totalCount = chapters.length;
      this.setData({
        chapters,
        downloadedCount,
        learnedCount,
        totalCount,
        percent: totalCount ? Math.round((learnedCount / totalCount) * 100) : 0,
        loading: false,
      });

      // P1：若后端提供课程进度聚合（GET /courses/{id}/progress），刷新精度（失败忽略）
      fetchCourseProgress(channelId)
        .then((prog) => {
          if (prog && typeof prog.percent === 'number') {
            this.setData({
              totalCount: prog.total || totalCount,
              learnedCount: prog.learned || learnedCount,
              percent: prog.percent,
            });
          }
        })
        .catch(() => {});
    } catch (err) {
      this.setData({ loading: false, error: err.message || '课程章节加载失败' });
    }
  },

  /**
   * 点击章节：设置整课播放队列（从点击章开始，便于自动连播），跳转详情页
   */
  onTapChapter(e) {
    const { id, index } = e.currentTarget.dataset;
    const chapter = this.data.chapters.find((c) => c.id === id);
    if (!chapter) return;
    const total = this.data.chapters.length;
    // FR-MC-10：章节播放埋点（SRS §4.10 chapter_play）
    trackEvent('course', 'chapter_play', 'episode_' + id);
    setQueue(this.data.chapters, Number(index));
    wx.navigateTo({
      url:
        '/pages/detail/detail?id=' + id +
        '&channelId=' + this.data.channelId +
        '&chapterIndex=' + (Number(index) + 1) +
        '&chapterTotal=' + total,
    });
  },

  /**
   * 继续学习：跳到首个未学完章节并续播
   */
  onContinue() {
    const chapters = this.data.chapters;
    if (!chapters.length) return;
    const target = chapters.find((c) => c.status !== 'finished') || chapters[0];
    const idx = chapters.indexOf(target);
    trackEvent('course', 'continue_learn', 'channel_' + this.data.channelId);
    // FR-MC-10：继续学习即开始播放目标章节（SRS §4.10 chapter_play）
    trackEvent('course', 'chapter_play', 'episode_' + target.id);
    setQueue(chapters, idx);
    playEpisode(target);
    wx.navigateTo({
      url:
        '/pages/detail/detail?id=' + target.id +
        '&channelId=' + this.data.channelId +
        '&chapterIndex=' + (idx + 1) +
        '&chapterTotal=' + chapters.length,
    });
  },

  /**
   * 从头播放：从第一章开始
   */
  onPlayFromStart() {
    const chapters = this.data.chapters;
    if (!chapters.length) return;
    trackEvent('course', 'play_from_start', 'channel_' + this.data.channelId);
    // FR-MC-10：从头播放即开始播放第一章（SRS §4.10 chapter_play）
    trackEvent('course', 'chapter_play', 'episode_' + chapters[0].id);
    setQueue(chapters, 0);
    playEpisode(chapters[0]);
    wx.navigateTo({
      url:
        '/pages/detail/detail?id=' + chapters[0].id +
        '&channelId=' + this.data.channelId +
        '&chapterIndex=1' +
        '&chapterTotal=' + chapters.length,
    });
  },

  /**
   * 点击章节下载按钮（catchtap，不触发卡片跳转）
   * 状态分支：已下载→提示；下载中→取消；未下载→开始下载（FR-MC-09）
   */
  onTapDownloadChapter(e) {
    const { id } = e.currentTarget.dataset;
    const idx = this.data.chapters.findIndex((c) => c.id === id);
    if (idx < 0) return;
    const chapter = this.data.chapters[idx];
    if (chapter.downloaded) {
      wx.showToast({ title: '已下载，可在「我的下载」管理', icon: 'none' });
      return;
    }
    if (chapter.downloading) {
      cancelDownload(id);
      this.setData({
        ['chapters[' + idx + '].downloading']: false,
        ['chapters[' + idx + '].progress']: 0,
      });
      return;
    }
    this._startDownloadChapter(idx, chapter);
  },

  /**
   * 下载单章并实时更新该章状态（FR-MC-09）
   */
  _startDownloadChapter(idx, chapter) {
    if (downloadStore.isDownloaded(chapter.id)) return;
    this.setData({
      ['chapters[' + idx + '].downloading']: true,
      ['chapters[' + idx + '].progress']: 0,
    });
    downloadEpisode(chapter, {
      onProgress: (p) => {
        this.setData({ ['chapters[' + idx + '].progress']: p });
      },
      onState: (s) => {
        if (s === 'done') {
          this.setData({
            ['chapters[' + idx + '].downloading']: false,
            ['chapters[' + idx + '].downloaded']: true,
            ['chapters[' + idx + '].progress']: 100,
          });
          this._refreshDownloadedCount();
        }
      },
    }).catch((err) => {
      this.setData({
        ['chapters[' + idx + '].downloading']: false,
        ['chapters[' + idx + '].progress']: 0,
      });
      if (err && err.message === '下载进行中') return;
      wx.showToast({ title: err.message || '下载失败', icon: 'none' });
    });
  },

  /**
   * 整课批量下载：依次下载所有未下载章节，实时刷新总进度（FR-MC-09）
   * 单章失败不中断整课流程，继续后续章节
   */
  async onDownloadAll() {
    if (this.data.batchDownloading) return;
    const todo = this.data.chapters.filter((c) => !c.downloaded);
    if (!todo.length) {
      wx.showToast({ title: '已全部下载', icon: 'none' });
      return;
    }
    this.setData({ batchDownloading: true, batchProgress: 0 });
    wx.showLoading({ title: '下载中 0/' + todo.length });
    let done = 0;
    for (const ch of todo) {
      const idx = this.data.chapters.findIndex((c) => c.id === ch.id);
      try {
        await downloadEpisode(ch);
        if (idx >= 0) {
          this.setData({
            ['chapters[' + idx + '].downloaded']: true,
            ['chapters[' + idx + '].downloading']: false,
            ['chapters[' + idx + '].progress']: 100,
          });
        }
      } catch (err) {
        // 已下载/其它错误：不阻断整课，仅记录
        if (!(err && err.message === '已下载')) {
          console.warn('[course] 批量下载单章失败:', err && err.message);
        }
      }
      done++;
      const pct = Math.round((done / todo.length) * 100);
      this.setData({ batchProgress: pct });
      wx.showLoading({ title: '下载中 ' + done + '/' + todo.length });
    }
    wx.hideLoading();
    this._refreshDownloadedCount();
    this.setData({ batchDownloading: false });
    wx.showToast({ title: '整课下载完成', icon: 'success' });
  },

  _refreshDownloadedCount() {
    const count = this.data.chapters.filter((c) => c.downloaded).length;
    this.setData({ downloadedCount: count });
  },

  _fmtDur(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
  },

  onShareAppMessage() {
    const ch = this.data.channel || {};
    return {
      title: ch.name || '课程',
      path: '/pages/course/course?channelId=' + this.data.channelId,
    };
  },
});
