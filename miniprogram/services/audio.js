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
const { reportPlayProgress, fetchPlayProgress } = require('./api');

const STORAGE_KEY_SETTINGS = 'news_settings';
const DEFAULT_RATE = 1.0;

let audioManager = null;
let progressTimer = null;      // 进度上报定时器
let currentEpisode = null;     // 当前播放的节目
let playQueue = [];            // 播放队列（自动连播用）
let queueIndex = -1;           // 当前播放节目在队列中的索引（-1 表示不在队列中）
let sleepTimer = null;         // 睡眠定时器句柄
let sleepRemaining = 0;        // 睡眠定时器剩余秒数（UI 显示用）
let sleepTickTimer = null;     // 睡眠倒计时滴答定时器（每秒触发以更新 UI）
let sleepListeners = [];       // 睡眠定时器状态变更监听器（页面订阅用）
let queueListeners = [];       // 队列变更监听器
let autoPlayNext = true;       // 自动连播开关（从 settings 读取）

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
  });

  // 播放恢复：重启进度上报 + 重新应用倍速（切歌后部分基础库会重置倍速）
  audioManager.onPlay(() => {
    startProgressReport();
    applyPlaybackRate();
  });

  // 播放错误：提示用户
  audioManager.onError((err) => {
    console.error('[audio] 播放错误:', JSON.stringify(err));
    wx.showToast({ title: '音频加载失败', icon: 'none' });
  });

  audioManager.onWaiting(() => {
    console.log('[audio] 音频加载中...');
  });

  audioManager.onCanplay(() => {
    console.log('[audio] 音频可播放了, duration:', audioManager.duration);
  });

  return audioManager;
}

/**
 * 应用当前倍速到播放器
 * 兼容旧版基础库：playbackRate 属性不存在时静默降级
 */
function applyPlaybackRate() {
  if (!audioManager || typeof audioManager.playbackRate === 'undefined') return;
  const settings = loadSettings();
  try {
    audioManager.playbackRate = settings.defaultRate;
  } catch (e) {
    // 旧版基础库写入 playbackRate 可能抛错，忽略即可
  }
}

/**
 * 设置倍速并持久化
 * @param {number} rate - 0.75 / 1.0 / 1.25 / 1.5 / 2.0
 */
function setPlaybackRate(rate) {
  const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
  wx.setStorageSync(STORAGE_KEY_SETTINGS, { ...saved, defaultRate: rate });
  applyPlaybackRate();
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
 */
async function playEpisode(episode) {
  console.log('[audio] playEpisode called:', episode.title, 'src:', episode.audio_url);
  currentEpisode = episode;

  // 立即开始播放，不等 fetchPlayProgress（真机上 async 等待会导致点击播放无响应）
  audioManager.title = episode.title;
  audioManager.epname = episode.title;
  audioManager.episodeId = episode.id;
  audioManager.src = episode.audio_url;
  audioManager.play();

  // 查询上次播放进度（断点续播），在后台异步进行，不阻塞播放
  try {
    const progress = await fetchPlayProgress(episode.id);
    if (progress && progress.position > 0 && !progress.completed) {
      // 等音频加载完成后跳转断点
      const onCanplay = () => {
        audioManager.seek(progress.position);
        audioManager.offCanplay?.(onCanplay);
      };
      audioManager.onCanplay(onCanplay);
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

// ==================== 进度上报 ====================

/**
 * 启动进度上报（每 5 秒一次）
 * 弱网时降频到 15 秒一次
 */
function startProgressReport() {
  stopProgressReport();
  const app = getApp();
  const interval = app?.globalData.networkType === 'wifi' ? 5000 : 15000;

  progressTimer = setInterval(() => {
    if (currentEpisode && audioManager.duration > 0) {
      reportPlayProgress({
        episode_id: currentEpisode.id,
        position: Math.floor(audioManager.currentTime),
        duration: Math.floor(audioManager.duration),
        completed: false,
      }).catch(() => {});
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
}

module.exports = {
  initPlayer,
  playEpisode,
  stopProgressReport,
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
};
