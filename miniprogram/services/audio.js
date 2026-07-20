/**
 * 全局音频播放器：基于 wx.getBackgroundAudioManager 单例
 *
 * V1.3 新增能力：
 * - 倍速播放（playbackRate，需基础库 2.41.0+，降级时静默忽略）
 * - 自动连播（onEnded 自动播放队列下一首）
 * - 睡眠定时器（倒计时结束后暂停并触发回调）
 * - 播放队列管理（setQueue/enqueue/next/prev，配合自动连播）
 *
 * 设计原则：
 * - 队列与 currentEpisode 解耦：currentEpisode 是当前正在播放的节目，
 *   队列是"接下来要播放的节目列表"。自动连播从队列中取下一首。
 * - 倍速需在 src 设置后才能生效（部分基础库会在切歌时重置倍速），
 *   故在 onPlay 回调中再次应用一次，保证倍速不丢。
 * - 睡眠定时器到点后暂停播放并清除定时器，避免重复触发。
 */
const { reportPlayProgress, fetchPlayProgress, fetchEpisodeDetail } = require('./api');

const STORAGE_KEY_SETTINGS = 'news_settings';
const DEFAULT_RATE = 1.0;

let audioManager = null;
let progressTimer = null;      // 进度上报定时器
let progressReporting = false; // 进度上报进行中标志（防弱网下请求堆积）
let currentEpisode = null;     // 当前播放的节目
let playQueue = [];            // 播放队列（自动连播用）
let queueIndex = -1;           // 当前播放节目在队列中的索引（-1 表示不在队列中）
let sleepTimer = null;         // 睡眠定时器句柄
let sleepRemaining = 0;        // 睡眠定时器剩余秒数（UI 显示用）
let sleepTickTimer = null;     // 睡眠倒计时滴答定时器（每秒触发以更新 UI）
let sleepListeners = [];       // 睡眠定时器状态变更监听器（页面订阅用）
let queueListeners = [];       // 队列变更监听器
let errorListeners = [];       // 播放错误监听器（页面订阅用，重置 isPlaying 等状态）
let autoPlayNext = true;       // 自动连播开关（从 settings 读取）
let lastAppliedRate = null;    // 上次已应用的倍速（避免 onPlay 重复写入触发重新缓冲）
let pendingSeek = 0;            // 待 seek 的目标位置（onCanplay 触发后清零，防止重复 seek）

/**
 * 读取用户设置中的默认倍速与自动连播开关
 */
function loadSettings() {
  try {
    const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
    return {
      defaultRate: typeof saved.defaultRate === 'number' ? saved.defaultRate : DEFAULT_RATE,
      autoPlayNext: typeof saved.autoPlayNext === 'boolean' ? saved.autoPlayNext : true,
    };
  } catch (e) {
    return { defaultRate: DEFAULT_RATE, autoPlayNext: true };
  }
}

/**
 * 初始化播放器（单例，app.js onLaunch 时调用一次）
 * @returns {BackgroundAudioManager}
 */
function initPlayer() {
  if (audioManager) return audioManager;

  // 启动时读取设置，初始化自动连播开关
  const settings = loadSettings();
  autoPlayNext = settings.autoPlayNext;

  audioManager = wx.getBackgroundAudioManager();

  // 播放结束：标记完播 + 上报 + 停止定时器 + 自动连播
  audioManager.onEnded(() => {
    if (currentEpisode) {
      reportPlayProgress({
        episode_id: currentEpisode.id,
        position: audioManager.duration,
        duration: audioManager.duration,
        completed: true,
      }).catch(() => {});
    }
    stopProgressReport();
    // 自动连播：未开启睡眠定时器且开关打开时，播放队列下一首
    if (autoPlayNext && !sleepTimer) {
      playNext();
    }
  });

  // 播放暂停：停止进度上报 + 立即上报当前位置
  audioManager.onPause(() => {
    stopProgressReport();
    if (currentEpisode) {
      reportPlayProgress({
        episode_id: currentEpisode.id,
        position: audioManager.currentTime,
        duration: audioManager.duration,
        completed: false,
      }).catch(() => {});
    }
    notifyPlaybackListeners({ type: 'pause', episode: currentEpisode, paused: true });
  });

  // 播放恢复：重启进度上报 + 重新应用倍速（切歌后部分基础库会重置倍速）
  audioManager.onPlay(() => {
    startProgressReport();
    applyPlaybackRate();
    notifyPlaybackListeners({ type: 'play', episode: currentEpisode, paused: false });
  });

  // 播放结束：通知订阅者（用于 UI 重置播放态）
  audioManager.onEnded(() => {
    stopProgressReport();
    notifyPlaybackListeners({ type: 'ended', episode: currentEpisode, paused: true });
  });

  // 播放错误：重置内部状态并通知所有订阅页面（避免按钮卡在"播放中"）
  // BackgroundAudioManager 在 src 加载失败时不会触发 onPause，仅触发 onError，
  // 若不在此处重置状态，UI 上的 isPlaying 会一直停留在 true
  audioManager.onError((err) => {
    console.error('[audio] 播放错误:', JSON.stringify(err));
    stopProgressReport();
    currentEpisode = null;
    notifyErrorListeners(err);
    wx.showToast({ title: '音频加载失败，请稍后重试', icon: 'none' });
  });

  audioManager.onWaiting(() => {
    console.log('[audio] 音频加载中...');
  });

  audioManager.onCanplay(() => {
    console.log('[audio] 音频可播放了, duration:', audioManager.duration);
    // 断点续播：pendingSeek > 0 时 seek 一次后清零
    // onCanplay 可能多次触发，靠 pendingSeek 标志位保证只 seek 一次
    if (pendingSeek > 0 && audioManager.duration > pendingSeek) {
      try {
        audioManager.seek(pendingSeek);
      } catch (e) {
        // 旧版基础库 seek 可能失败，忽略
      }
      pendingSeek = 0;
    }
  });

  return audioManager;
}

/**
 * 应用当前倍速到播放器
 * 兼容旧版基础库：playbackRate 属性不存在时静默降级
 *
 * 优化：缓存上次应用的倍速，值未变化时跳过写入，
 * 避免部分基础库在重复赋值时触发重新缓冲。
 */
function applyPlaybackRate() {
  if (!audioManager || typeof audioManager.playbackRate === 'undefined') return;
  const settings = loadSettings();
  const rate = settings.defaultRate;
  if (rate === lastAppliedRate) return;  // 倍速未变化，跳过
  try {
    audioManager.playbackRate = rate;
    lastAppliedRate = rate;
  } catch (e) {
    // 旧版基础库写入 playbackRate 可能抛错，忽略即可
  }
}

/**
 * 设置倍速并持久化
 * @param {number} rate - 0.75 / 1.0 / 1.25 / 1.5 / 2.0
 *
 * 实测微信基础库 3.7.x：播放中直接赋值 playbackRate 会立即生效，
 * 无需 pause/play。旧版基础库若不支持运行时修改，则下次 onPlay 回调里
 * applyPlaybackRate 会再次写入，保证不丢。
 */
function setPlaybackRate(rate) {
  const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
  wx.setStorageSync(STORAGE_KEY_SETTINGS, { ...saved, defaultRate: rate });
  if (!audioManager) return;
  // 重置应用缓存：onPlay 回调需强制重新写入（部分基础库切歌/重启后会重置倍速）
  // 必须在写入 playbackRate 之前清零，否则 applyPlaybackRate 会因 lastAppliedRate === rate 而跳过
  lastAppliedRate = null;
  try {
    audioManager.playbackRate = rate;
    lastAppliedRate = rate;
  } catch (e) {
    // 旧版基础库写入 playbackRate 可能抛错，忽略即可
  }
  // 任务3修复：播放中切换倍速时，直接写入 playbackRate 在 iOS 上不立即生效
  // 需要 pause + play + seek 强制重新缓冲才能应用新倍速
  // 会有一瞬间中断，但能确保倍速立即生效
  if (!audioManager.paused && audioManager.currentTime > 0) {
    const pos = audioManager.currentTime;
    audioManager.pause();
    // 短延迟后 play，让播放器完全进入暂停状态再恢复
    setTimeout(() => {
      try {
        audioManager.play();
        // 重置缓存：onPlay → applyPlaybackRate 需真正写入新倍速（基础库 pause→play 会重置）
        lastAppliedRate = null;
        // play 后 seek 回原位置（避免从头播放）
        setTimeout(() => {
          try { audioManager.seek(pos); } catch (e) {}
        }, 200);
      } catch (e) {}
    }, 100);
  }
}

/**
 * 获取当前倍速
 */
function getPlaybackRate() {
  return loadSettings().defaultRate;
}

/**
 * 设置自动连播开关
 */
function setAutoPlayNext(enabled) {
  autoPlayNext = !!enabled;
  const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
  wx.setStorageSync(STORAGE_KEY_SETTINGS, { ...saved, autoPlayNext });
}

/**
 * 播放指定节目（自动断点续播）
 * @param {Object} episode - 节目对象 { id, title, audio_url }
 *
 * 队列里的 episode 可能是历史列表的摘要对象（无 audio_url 字段），
 * 此处按需 fetch 详情补齐，并将完整对象回写队列避免下次切换时重复请求。
 */
async function playEpisode(episode) {
  // 缺 audio_url 时先拉详情补齐（来自历史/搜索列表的摘要对象）
  if (!episode || !episode.audio_url) {
    if (!episode || !episode.id) {
      console.error('[audio] playEpisode 收到无效 episode:', episode);
      wx.showToast({ title: '节目信息缺失', icon: 'none' });
      return;
    }
    try {
      const detail = await fetchEpisodeDetail(episode.id);
      episode = { ...episode, ...detail };
      // 回写到队列当前索引位置，避免下次切回时再次 fetch
      if (queueIndex >= 0 && queueIndex < playQueue.length) {
        playQueue[queueIndex] = episode;
      }
    } catch (err) {
      console.error('[audio] 拉取节目详情失败:', err.message);
      wx.showToast({ title: '节目信息加载失败', icon: 'none' });
      notifyErrorListeners({ errCode: -1, errMsg: err.message });
      return;
    }
  }

  console.log('[audio] playEpisode called:', episode.title, 'src:', episode.audio_url);
  currentEpisode = episode;
  // 重置倍速缓存：切歌后部分基础库会重置 playbackRate 为 1.0，
  // 此处强制下次 applyPlaybackRate 重新写入，保证倍速不丢
  lastAppliedRate = null;
  // 重置待 seek 标志：避免上一首的 seek 残留
  pendingSeek = 0;

  // 立即开始播放，不等 fetchPlayProgress（真机上 async 等待会导致点击播放无响应）
  audioManager.title = episode.title;
  audioManager.epname = episode.title;
  audioManager.episodeId = episode.id;
  // URL 编码：后端 content_service 已用 urllib.quote 对中文路径编码，
  // 前端不再二次 encodeURI，否则 % 会被编码成 %25 导致 404
  audioManager.src = episode.audio_url;
  audioManager.play();

  // 查询上次播放进度（断点续播），在后台异步进行，不阻塞播放
  try {
    const progress = await fetchPlayProgress(episode.id);
    if (progress && progress.position > 0 && !progress.completed) {
      // 用 pendingSeek 标志位代替 onCanplay 回调注册：
      // onCanplay 可能多次触发（缓冲恢复/seek 后再 canplay），
      // 旧实现每次都 seek 会造成重复缓冲卡顿。
      // 这里仅在 pendingSeek > 0 时 seek 一次，seek 完成立即清零。
      pendingSeek = progress.position;
    }
  } catch (err) {
    console.log('获取播放进度失败，从开头播放:', err.message);
  }
}

// ==================== 播放队列管理 ====================

/**
 * 设置播放队列并定位到指定节目
 * @param {Array} episodes - 节目列表
 * @param {number} startIndex - 起始播放索引（默认 0）
 */
function setQueue(episodes, startIndex = 0) {
  playQueue = (episodes || []).slice();
  queueIndex = startIndex;
  notifyQueueListeners();
}

/**
 * 追加节目到队列末尾
 * @param {Object|Array} episodeOrList - 单个节目或节目数组
 */
function enqueue(episodeOrList) {
  if (Array.isArray(episodeOrList)) {
    playQueue = playQueue.concat(episodeOrList);
  } else {
    playQueue.push(episodeOrList);
  }
  notifyQueueListeners();
}

/**
 * 清空队列
 */
function clearQueue() {
  playQueue = [];
  queueIndex = -1;
  notifyQueueListeners();
}

/**
 * 获取当前队列快照
 */
function getQueue() {
  return playQueue.slice();
}

/**
 * 获取当前播放索引
 */
function getQueueIndex() {
  return queueIndex;
}

/**
 * 播放队列下一首（自动连播与"下一首"按钮共用）
 * 队列末端时停止播放并提示
 */
function playNext() {
  if (queueIndex < 0 || queueIndex >= playQueue.length - 1) {
    // 队列末端：仅提示，不强制停止当前播放（用户可能想重听）
    wx.showToast({ title: '已是最后一首', icon: 'none' });
    return false;
  }
  queueIndex += 1;
  const next = playQueue[queueIndex];
  notifyQueueListeners();
  playEpisode(next);
  return true;
}

/**
 * 播放队列上一首
 */
function playPrev() {
  if (queueIndex <= 0) {
    wx.showToast({ title: '已是第一首', icon: 'none' });
    return false;
  }
  queueIndex -= 1;
  const prev = playQueue[queueIndex];
  notifyQueueListeners();
  playEpisode(prev);
  return true;
}

/**
 * 订阅队列变更事件
 * @param {Function} listener - 回调 (queue, index) => void
 * @returns {Function} 取消订阅函数
 */
function onQueueChange(listener) {
  queueListeners.push(listener);
  return () => {
    queueListeners = queueListeners.filter((l) => l !== listener);
  };
}

function notifyQueueListeners() {
  queueListeners.forEach((l) => {
    try { l(playQueue.slice(), queueIndex); } catch (e) { console.error(e); }
  });
}

// ==================== 睡眠定时器 ====================

/**
 * 启动睡眠定时器
 * @param {number} seconds - 倒计时秒数
 */
function startSleepTimer(seconds) {
  stopSleepTimer();
  if (!seconds || seconds <= 0) return;

  sleepRemaining = seconds;
  notifySleepListeners({ remaining: sleepRemaining, active: true });

  // 滴答定时器：每秒更新剩余时间，供 UI 显示
  sleepTickTimer = setInterval(() => {
    sleepRemaining -= 1;
    if (sleepRemaining <= 0) {
      // 到点：暂停播放并清理
      if (audioManager && !audioManager.paused) audioManager.pause();
      stopSleepTimer();
      wx.showToast({ title: '睡眠定时已结束', icon: 'none' });
    } else {
      notifySleepListeners({ remaining: sleepRemaining, active: true });
    }
  }, 1000);
}

/**
 * 停止睡眠定时器
 */
function stopSleepTimer() {
  if (sleepTickTimer) {
    clearInterval(sleepTickTimer);
    sleepTickTimer = null;
  }
  sleepRemaining = 0;
  notifySleepListeners({ remaining: 0, active: false });
}

/**
 * 获取睡眠定时器状态
 */
function getSleepStatus() {
  return { remaining: sleepRemaining, active: !!sleepTickTimer };
}

/**
 * 订阅睡眠定时器状态变更
 * @param {Function} listener
 * @returns {Function} 取消订阅
 */
function onSleepChange(listener) {
  sleepListeners.push(listener);
  return () => {
    sleepListeners = sleepListeners.filter((l) => l !== listener);
  };
}

function notifySleepListeners(status) {
  sleepListeners.forEach((l) => {
    try { l(status); } catch (e) { console.error(e); }
  });
}

// ==================== 播放错误通知 ====================

/**
 * 订阅播放错误事件（页面订阅用，用于重置 isPlaying 等状态）
 * @param {Function} listener - 回调 (err) => void
 * @returns {Function} 取消订阅
 */
function onError(listener) {
  errorListeners.push(listener);
  return () => {
    errorListeners = errorListeners.filter((l) => l !== listener);
  };
}

function notifyErrorListeners(err) {
  errorListeners.forEach((l) => {
    try { l(err); } catch (e) { console.error(e); }
  });
}

// ==================== 播放/暂停状态通知 ====================

// 实时通知各订阅组件：用于图标即时切换，避免 1s 轮询的延迟
let playbackListeners = [];

function onPlaybackChange(listener) {
  playbackListeners.push(listener);
  return () => {
    playbackListeners = playbackListeners.filter((l) => l !== listener);
  };
}

function notifyPlaybackListeners(event) {
  // event: { type: 'play'|'pause'|'ended', episode, paused }
  playbackListeners.forEach((l) => {
    try { l(event); } catch (e) { console.error(e); }
  });
}

// ==================== 进度上报 ====================

/**
 * 启动进度上报（每 5 秒一次）
 * 弱网时降频到 15 秒一次
 *
 * 优化：加 progressReporting 标志，前一次请求未完成时跳过本次上报，
 * 避免弱网下请求堆积阻塞主线程网络队列
 */
function startProgressReport() {
  stopProgressReport();
  const app = getApp();
  const interval = app?.globalData.networkType === 'wifi' ? 5000 : 15000;

  progressTimer = setInterval(async () => {
    // 防重叠：上一次请求未完成时跳过本次
    if (progressReporting) return;
    if (!currentEpisode || !audioManager || audioManager.duration <= 0) return;

    progressReporting = true;
    try {
      await reportPlayProgress({
        episode_id: currentEpisode.id,
        position: Math.floor(audioManager.currentTime),
        duration: Math.floor(audioManager.duration),
        completed: false,
      });
    } catch (e) {
      // 静默失败：上报失败不影响播放
    } finally {
      progressReporting = false;
    }
  }, interval);
}

/**
 * 停止进度上报
 */
function stopProgressReport() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  // 重置标志：避免 stopProgressReport 时残留的 progressReporting=true 影响下次启动
  progressReporting = false;
}

/**
 * 获取当前播放节目对象（页面用于判断是否是当前页面展示的节目）
 */
function getCurrentEpisode() {
  return currentEpisode;
}

/**
 * 恢复播放：当前节目存在且播放器处于暂停状态时调用 play()
 * 用于浮动按钮从其他页面跳转回详情页时自动恢复播放
 * @returns {boolean} 是否实际触发了恢复播放
 */
function resumePlay() {
  if (!audioManager || !currentEpisode) return false;
  // BackgroundAudioManager 的 paused 属性反映当前暂停状态
  // 仅在暂停时调用 play()，避免重复调用导致重新缓冲
  if (audioManager.paused) {
    try {
      audioManager.play();
      return true;
    } catch (e) {
      console.warn('[audio] resumePlay 失败:', e);
      return false;
    }
  }
  return false;
}

module.exports = {
  initPlayer,
  playEpisode,
  stopProgressReport,
  resumePlay,
  // 倍速
  setPlaybackRate,
  getPlaybackRate,
  applyPlaybackRate,
  // 自动连播
  setAutoPlayNext,
  // 队列
  setQueue,
  enqueue,
  clearQueue,
  getQueue,
  getQueueIndex,
  playNext,
  playPrev,
  onQueueChange,
  // 睡眠定时器
  startSleepTimer,
  stopSleepTimer,
  getSleepStatus,
  onSleepChange,
  // 播放错误
  onError,
  // 播放/暂停状态变更（实时通知，替代轮询）
  onPlaybackChange,
  // 当前节目
  getCurrentEpisode,
};
