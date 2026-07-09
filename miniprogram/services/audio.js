/**
 * 全局音频播放器：基于 wx.getBackgroundAudioManager 单例
 *
 * 特性：
 * - 锁屏播放（requiredBackgroundModes: ['audio']）
 * - 断点续播（查询上次进度自动 seek）
 * - 进度上报（每 5 秒一次）
 * - 来电暂停（系统自动处理，onPause 上报当前位置）
 */
const { reportPlayProgress, fetchPlayProgress } = require('./api');

let audioManager = null;
let progressTimer = null;     // 进度上报定时器
let currentEpisode = null;    // 当前播放的节目

/**
 * 初始化播放器（单例，app.js onLaunch 时调用一次）
 * @returns {BackgroundAudioManager}
 */
function initPlayer() {
  if (audioManager) return audioManager;

  audioManager = wx.getBackgroundAudioManager();

  // 播放结束：标记完播 + 上报 + 停止定时器
  audioManager.onEnded(() => {
    if (currentEpisode) {
      reportPlayProgress({
        episode_id: currentEpisode.id,
        position: audioManager.duration,
        duration: audioManager.duration,
        completed: true,
      });
    }
    stopProgressReport();
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
      });
    }
  });

  // 播放恢复：重启进度上报
  audioManager.onPlay(() => {
    startProgressReport();
  });

  // 播放错误：提示用户
  audioManager.onError((err) => {
    console.error('播放错误', err);
    wx.showToast({ title: '音频加载失败', icon: 'none' });
  });

  return audioManager;
}

/**
 * 播放指定节目（自动断点续播）
 * @param {Object} episode - 节目对象 { id, title, audio_url }
 */
async function playEpisode(episode) {
  currentEpisode = episode;

  // 查询上次播放进度（断点续播）
  let startPosition = 0;
  try {
    const progress = await fetchPlayProgress(episode.id);
    if (progress && progress.position > 0 && !progress.completed) {
      startPosition = progress.position;
    }
  } catch (err) {
    console.warn('获取播放进度失败，从开头播放', err);
  }

  // 设置播放源（title 必填，否则锁屏不显示标题）
  // episodeId 用于页面/组件精确判断当前播放节目，避免标题重复误判
  audioManager.title = episode.title;
  audioManager.epname = episode.title;
  audioManager.episodeId = episode.id;
  audioManager.src = episode.audio_url;

  // 跳转到上次位置（需等待音频元数据加载完成）
  // 使用命名回调 + off 自清理，避免每次 playEpisode 累积 onCanplay 监听器
  if (startPosition > 0) {
    const onCanplay = () => {
      audioManager.seek(startPosition);
      audioManager.offCanplay?.(onCanplay);
    };
    audioManager.onCanplay(onCanplay);
  }
}

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
      });
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
};
