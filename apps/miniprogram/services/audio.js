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
const { fetchEpisodeDetail, fetchTodayEpisode } = require('./api');
// local-data 封装了播放进度/历史的双写（本地+后端），按 openid 隔离
const localData = require('./local-data');
// 离线下载存储（FR-MC-09）：持久化已下载章节的本地路径
const downloadStore = require('./download');
const { isDevTools } = require('../utils/server-discovery');

const STORAGE_KEY_SETTINGS = 'news_settings';
const DEFAULT_RATE = 1.0;

let audioManager = null;
let progressTimer = null;      // 进度上报定时器
let progressReporting = false; // 进度上报进行中标志（防弱网下请求堆积）
let currentEpisode = null;     // 当前播放的节目
let currentProtocol = '';      // 当前播放协议：'audio' / 'hls'（onError 时判断是否需 fallback）
let playQueue = [];            // 播放队列（自动连播用）
let queueIndex = -1;           // 当前播放节目在队列中的索引（-1 表示不在队列中）
let sleepTimer = null;         // 睡眠定时器句柄
let sleepRemaining = 0;        // 睡眠定时器剩余秒数（UI 显示用）
let sleepTickTimer = null;     // 睡眠倒计时滴答定时器（每 5 秒触发以更新 UI）
let sleepListeners = [];       // 睡眠定时器状态变更监听器（页面订阅用）
let queueListeners = [];       // 队列变更监听器
let errorListeners = [];       // 播放错误监听器（页面订阅用，重置 isPlaying 等状态）
let autoPlayNext = true;       // 自动连播开关（从 settings 读取）
let lastAppliedRate = null;    // 上次已应用的倍速（避免 onPlay 重复写入触发重新缓冲）
let pendingSeek = 0;            // 待 seek 的目标位置（onCanplay 触发后清零，防止重复 seek）
// 正在加载的节目 ID + URL：防止短时间内重复 playEpisode 导致 src 被覆盖清空
// BackgroundAudioManager 在 src 加载中再次赋值会触发清空，最终 errCode:0 src:null
let loadingEpisodeId = null;
let loadingEpisodeUrl = null;
// 音频 loading 状态：暴露给 UI 显示菊花，避免 onWaiting 仅打 log 用户无感知
let isWaiting = false;
let waitingListeners = [];
// 预加载的下一首详情：onEnded→playNext 同步路径中避免 await fetchEpisodeDetail 阻塞
let _preloadedNextEpisode = null;
// 时间更新订阅：统一外部 onTimeUpdate 监听，避免每个页面各自监听导致多次 setData
// （audio-player / detail / index 原本各自 player.onTimeUpdate 闭包内 setData，叠加渲染开销）
let currentTimeListeners = [];
let lastTimeUpdateTs = 0;        // 上次 onTimeUpdate 通知时间戳（800ms 节流用）
// 睡眠定时器尾段精确计时句柄：剩余 < 5 秒时改用 setTimeout 等待，避免到点延迟最多 4 秒
let sleepTailTimer = null;
// 上次上报的 position（用于计算本次上报周期内的收听时长增量，任务7）
// -1 表示待初始化：切歌/播放开始时重置，首次上报 tick 时初始化为当前 position，
// 避免断点续播的 pendingSeek 位置被误算为收听增量
let lastReportedPosition = -1;
// fallback 超时保护句柄：HLS→mp3 fallback 后，若 8s 内 onPlay 未触发则判定 mp3 也失败
// 为什么需要：NotSupportedError 是浏览器媒体元素的未捕获 Promise rejection，
// 不触发 BackgroundAudioManager.onError，用户无任何反馈
let fallbackTimeoutTimer = null;
// HLS 静默重试次数：会话首次播放时 BackgroundAudioManager 的 HLS 协议栈冷启动，
// 偶发 errCode:0 src:null 的加载失败（第二集同链路却成功，证明是冷启动而非硬故障）。
// 立即静默重试一次即可命中，避免"先弹失败又播放成功"的割裂体验；
// 重试仍失败再降级 mp3（MAX_HLS_RETRY 控制重试上限，防无限循环）。
let hlsRetryCount = 0;
const MAX_HLS_RETRY = 1;

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

  // 播放结束：标记完播 + 上报 + 停止定时器 + 自动连播 + 通知订阅者
  // 合并到单一 onEnded：避免重复注册导致 stopProgressReport 被调用两次及回调顺序不可控
  audioManager.onEnded(() => {
    if (currentEpisode) {
      // 计算本次会话最后一段收听增量：duration - lastReportedPosition
      // lastReportedPosition < 0 表示从未上报过（极短音频），delta 丢弃
      const finalPos = Math.floor(audioManager.duration || 0);
      let listenedSeconds = 0;
      if (lastReportedPosition >= 0) {
        const delta = finalPos - lastReportedPosition;
        if (delta > 0) listenedSeconds = delta;
      }
      lastReportedPosition = finalPos;
      // 完播进度双写：本地+后端（localData.saveProgress 内部已处理）
      // 透传 listened_seconds 让后端累加 User.total_listen_duration（任务7）
      localData.saveProgress(
        currentEpisode.id,
        finalPos,
        finalPos,
        true,
        listenedSeconds
      );
      // 播放历史双写：完播时记录到本地历史
      localData.addHistory(currentEpisode, finalPos);
    }
    stopProgressReport();
    notifyPlaybackListeners({ type: 'ended', episode: currentEpisode, paused: true });
    // 自动连播：未开启睡眠定时器且开关打开时，播放队列下一首
    // sleepTimer 变量声明后从未赋值（实际操作的是 sleepTickTimer/sleepTailTimer），
    // 旧代码 !sleepTimer 永远为 true，导致开了睡眠定时器仍会自动连播
    if (autoPlayNext && !sleepTickTimer && !sleepTailTimer) {
      playNext();
    }
  });

  // 播放暂停：停止进度上报 + 立即上报当前位置
  audioManager.onPause(() => {
    stopProgressReport();
    if (currentEpisode) {
      // 计算暂停前的收听增量：currentTime - lastReportedPosition
      const currentPos = Math.floor(audioManager.currentTime || 0);
      let listenedSeconds = 0;
      if (lastReportedPosition >= 0) {
        const delta = currentPos - lastReportedPosition;
        if (delta > 0) listenedSeconds = delta;
      }
      lastReportedPosition = currentPos;
      // 暂停时进度双写：本地+后端
      // 透传 listened_seconds 让后端累加 User.total_listen_duration（任务7）
      localData.saveProgress(
        currentEpisode.id,
        currentPos,
        Math.floor(audioManager.duration || 0),
        false,
        listenedSeconds
      );
    }
    notifyPlaybackListeners({ type: 'pause', episode: currentEpisode, paused: true });
  });

  // 播放恢复：重启进度上报 + 重新应用倍速（切歌后部分基础库会重置倍速）
  audioManager.onPlay(() => {
    // 清除加载标记：播放已开始，下次 playEpisode 同一节目可正常触发
    loadingEpisodeId = null;
    loadingEpisodeUrl = null;
    // 清除 fallback 超时定时器：mp3 已成功播放，无需超时保护
    if (fallbackTimeoutTimer) {
      clearTimeout(fallbackTimeoutTimer);
      fallbackTimeoutTimer = null;
    }
    // 真正开始播放即代表 loading 结束：onWaiting 的卡顿状态在此处解除
    setWaiting(false);
    startProgressReport();
    applyPlaybackRate();
    notifyPlaybackListeners({ type: 'play', episode: currentEpisode, paused: false });
  });

  // 注意：onError 中的 HLS→mp3 fallback 依赖 currentEpisode 和 currentProtocol，
  // 故 onError 中 fallback 路径不清空 currentEpisode（仅清空 loading 标记），
  // fallback 失败或其他错误场景才清空 currentEpisode 和 currentProtocol

  // 播放错误：重置内部状态并通知所有订阅页面（避免按钮卡在"播放中"）
  // BackgroundAudioManager 在 src 加载失败时不会触发 onPause，仅触发 onError，
  // 若不在此处重置状态，UI 上的 isPlaying 会一直停留在 true
  audioManager.onError((err) => {
    stopProgressReport();
    // 清除加载标记：错误后允许重新播放
    loadingEpisodeId = null;
    loadingEpisodeUrl = null;

    // HLS 链路：会话首次播放时 HLS 协议栈冷启动偶发失败（errCode:0 src:null），
    // 第二集同链路却成功，证明是冷启动而非硬故障。
    // 处理策略：先静默重试一次 HLS（命中则用户无感知）；重试仍失败再降级 mp3；
    // 二者均非"致命错误"——不打 error 级日志、不弹失败 toast，避免割裂体验。
    if (currentProtocol === 'hls' && currentEpisode && currentEpisode.hls_url) {
      if (hlsRetryCount < MAX_HLS_RETRY) {
        hlsRetryCount += 1;
        console.warn('[audio] HLS 首次加载失败，静默重试一次:', currentEpisode.hls_url,
          '| err:', JSON.stringify(err));
        _retryHls(currentEpisode);
        return;
      }
      console.warn('[audio] HLS 重试仍失败，降级到 mp3 整文件:', currentEpisode.audio_url);
      _fallbackToMp3(currentEpisode);
      return;
    }

    // 真正致命的播放错误（非 HLS / HLS 无 mp3 兜底源）：重置状态并通知页面
    console.error('[audio] 播放错误:', JSON.stringify(err), '| protocol:', currentProtocol);
    // 错误发生时 loading 必然结束，避免菊花残留
    setWaiting(false);
    currentEpisode = null;
    currentProtocol = '';
    notifyErrorListeners(err);
    wx.showToast({ title: '音频加载失败，请稍后重试', icon: 'none' });
  });

  audioManager.onWaiting(() => {
    console.debug('[audio] 音频加载中...');
    // 通知 UI 显示 loading 菊花：用户感知到正在缓冲
    setWaiting(true);
  });

  audioManager.onCanplay(() => {
    console.debug('[audio] 音频可播放了, duration:', audioManager.duration);
    // 缓冲足够：解除 loading 菊花
    setWaiting(false);
    // 重新应用倍速：部分基础库（如 3.3.4）在 canplay 后会重置 playbackRate 为 1.0，
    // 此处再次写入确保新缓冲段使用正确倍速（lastAppliedRate 已在 setPlaybackRate
    // 中重置为 null，故 applyPlaybackRate 会实际写入；其他场景会跳过避免重复）
    applyPlaybackRate();
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

  // 时间更新：内部单一监听 + 800ms 节流后广播给订阅者
  // 原本 audio-player / detail / index 各自 player.onTimeUpdate 内 setData，
  // 同一时刻 3 次 setData 叠加阻塞渲染；统一到 audio.js 后只触发一次广播，
  // 订阅者各自决定是否 setData，且节流后总频率从 ~5 次/秒降到 ~1 次/秒
  audioManager.onTimeUpdate(() => {
    // 节流：onTimeUpdate 每秒约触发 5 次，800ms 节流既保证进度条流畅又避免渲染阻塞
    const now = Date.now();
    if (now - lastTimeUpdateTs < 800) return;
    lastTimeUpdateTs = now;
    const currentTime = Math.floor(audioManager.currentTime || 0);
    const duration = Math.floor(audioManager.duration || 0);
    notifyTimeUpdateListeners(currentTime, duration);
  });

  return audioManager;
}

/**
 * 应用当前倍速到播放器
 * 兼容旧版基础库：playbackRate 属性不存在时静默降级
 *
 * 缓存上次已应用的倍速，值未变化时跳过写入，
 * 避免部分基础库在重复赋值时触发重新缓冲。
 * 写入成功后更新 lastAppliedRate，确保下次相同倍速不会重复写入。
 * setPlaybackRate 会主动重置 lastAppliedRate=null 强制重新写入。
 */
function applyPlaybackRate() {
  if (!audioManager || typeof audioManager.playbackRate === 'undefined') return;
  const settings = loadSettings();
  const rate = settings.defaultRate;
  if (rate === lastAppliedRate) return;  // 倍速未变化，跳过
  try {
    audioManager.playbackRate = rate;
    // 写入成功后更新缓存：避免 onPlay/onCanplay 重复写入触发不必要重缓冲
    // setPlaybackRate 主动修改倍速时会重置此值为 null 强制下次重新写入
    lastAppliedRate = rate;
  } catch (e) {
    // 旧版基础库写入 playbackRate 可能抛错，忽略即可
  }
}

/**
 * 设置倍速并持久化
 * @param {number} rate - 0.75 / 1.0 / 1.25 / 1.5 / 2.0
 *
 * 实现策略：
 * 1. 持久化到 settings 并重置 lastAppliedRate 缓存
 * 2. 直接赋值 playbackRate（基础库 2.41.0+ 支持运行时修改）
 * 3. 播放中时通过 seek(currentTime) 触发 onCanplay，
 *    onCanplay 中调用 applyPlaybackRate 确保新缓冲段使用正确倍速
 *
 * 不更新 lastAppliedRate：让 onPlay/onCanplay 中的 applyPlaybackRate 统一管理缓存，
 * 避免基础库在 play 后重置 playbackRate 为 1.0 时因缓存命中而跳过重新写入。
 *
 * 不使用 pause/play/seek 组合：play() 是异步的，pause 后立即 play 会触发
 * 重缓冲，且 200ms 后 seek 时机不可靠，部分基础库会因此把进度重置为 0。
 */
function setPlaybackRate(rate) {
  const saved = wx.getStorageSync(STORAGE_KEY_SETTINGS) || {};
  // 非关键写入（偏好设置）：改异步避免阻塞主线程，失败仅告警不影响播放
  wx.setStorage({
    key: STORAGE_KEY_SETTINGS,
    data: { ...saved, defaultRate: rate },
    fail: (e) => console.warn('[audio] 设置写入失败:', e && e.errMsg),
  });
  if (!audioManager) return;

  // 重置缓存：强制下次 applyPlaybackRate（onPlay/onCanplay 触发）重新写入
  // 即使下面直接赋值成功，也不更新 lastAppliedRate，保证 play 后基础库若
  // 重置 playbackRate 为 1.0 时，onPlay 回调能再次写入正确倍速
  lastAppliedRate = null;

  // 直接赋值：基础库 2.41.0+ 支持运行时修改，播放中赋值立即生效
  try { audioManager.playbackRate = rate; } catch(e) {}

  // 播放中通过 seek 当前位置触发重缓冲，onCanplay 中 applyPlaybackRate 会
  // 重新写入倍速，确保新缓冲段使用正确倍速（部分基础库 canplay 后重置为 1.0）
  if (!audioManager.paused && audioManager.currentTime > 0) {
    const pos = audioManager.currentTime;
    try { audioManager.seek(pos); } catch(e) {}
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
  // 非关键写入（偏好设置）：改异步避免阻塞主线程，失败仅告警不影响播放
  wx.setStorage({
    key: STORAGE_KEY_SETTINGS,
    data: { ...saved, autoPlayNext },
    fail: (e) => console.warn('[audio] 设置写入失败:', e && e.errMsg),
  });
}

/**
 * 安全调用 audioManager.play()
 *
 * play() 返回 Promise，若在 resolve 前被 pause() 打断会抛 DOMException：
 * "The play() request was interrupted by a call to pause()"
 * 此函数统一 catch 该异常，供页面层调用避免控制台报错。
 */
function safePlay() {
  if (!audioManager) return;
  try {
    const p = audioManager.play();
    if (p && typeof p.catch === 'function') {
      p.catch((err) => {
        console.debug('[audio] safePlay() 被中断（可忽略）:', err && err.message);
      });
    }
  } catch (e) {
    console.debug('[audio] safePlay() 同步异常（可忽略）:', e && e.message);
  }
}

/**
 * 选择最佳播放源
 *
 * 优先级（V1.3 HLS 支持后调整）：
 * 1. localPath（预下载的本地 mp3 文件，首帧最快，完全无网络延迟）
 * 2. hls_url（HLS m3u8 分片流，仅需下载首个 ts 分片即可起播，
 *            首字延迟从 mp3 整文件下载的 300-1000ms 降到 200-500ms）
 * 3. audio_url（mp3 整文件网络播放，回退兜底）
 *
 * 为什么 localPath 优先于 hls_url：localPath 是已完整下载到本地的 mp3，
 * seek 与起播均无网络依赖，体验优于 HLS 分片流（仍需网络下载分片）。
 * 仅在预下载未命中时才用 HLS，作为网络播放的最优选择。
 *
 * 开发者工具例外：BackgroundAudioManager 在开发者工具中不支持 HLS 协议
 * （errCode 10001），直接跳过 hls_url 使用 audio_url，避免 HLS→mp3 fallback
 * 周期中 NotSupportedError 未捕获 Promise rejection 污染控制台。
 *
 * @param {Object} episode - 节目对象
 * @returns {{url: string, protocol: string}} - 播放 URL + 协议标识
 *   protocol: 'audio'（本地/网络 mp3）/ 'hls'（HLS 分片流）
 */
function _pickPlayableUrl(episode) {
  if (episode.localPath) {
    return { url: episode.localPath, protocol: 'audio' };
  }
  // FR-MC-09：离线下载命中 → 优先用已下载本地文件，实现离线播放
  // 课程页/下载管理页跳转播放时 episode 对象无 localPath，需查下载表
  const dlPath = downloadStore.getDownloadLocalPath(episode.id);
  if (dlPath) {
    return { url: dlPath, protocol: 'audio' };
  }
  // 开发者工具不支持 HLS：跳过 hls_url 直接用 mp3，避免 fallback 周期中的未捕获错误
  if (episode.hls_url && !isDevTools()) {
    return { url: episode.hls_url, protocol: 'hls' };
  }
  return { url: episode.audio_url, protocol: 'audio' };
}

/**
 * 安全地设置 BackgroundAudioManager.protocol（基础库 2.41.0+ 支持 HLS）
 * 旧版基础库无该属性时 try-catch 静默忽略，回退到 URL 后缀自动识别。
 * 抽成独立函数避免 playEpisode / _retryHls / _fallbackToMp3 三处重复。
 * @param {string} protocol - 'audio' / 'hls'
 */
function _applyProtocol(protocol) {
  if (typeof audioManager.protocol !== 'undefined') {
    try { audioManager.protocol = protocol; } catch (e) {
      console.debug('[audio] protocol 设置失败（旧版基础库可忽略）:', e && e.message);
    }
  }
}

/**
 * HLS 静默重试一次（应对会话首次播放的协议栈冷启动偶发失败）
 *
 * 为什么需要：真机首播 HLS 偶发 errCode:0 src:null，但同一会话后续 HLS 播放稳定成功，
 * 说明是冷启动而非 HLS 硬故障。onError 中先调用本函数重试一次，命中则用户无感知；
 * 4s 内 onPlay 仍未触发（HLS 真不可用或卡死）再降级 mp3。
 *
 * onPlay 触发时会清空 fallbackTimeoutTimer，故定时器能走到回调即说明 HLS 仍未起播。
 * @param {Object} episode - 当前节目（需含 hls_url）
 */
function _retryHls(episode) {
  currentProtocol = 'hls';
  _applyProtocol('hls');
  // 保持 loading 菊花连续，避免重试瞬间闪烁让用户误以为失败了
  setWaiting(true);
  audioManager.src = episode.hls_url;
  const p = audioManager.play();
  if (p && typeof p.catch === 'function') {
    p.catch((e) => console.debug('[audio] retry HLS play() 被中断（可忽略）:', e && e.message));
  }
  clearTimeout(fallbackTimeoutTimer);
  fallbackTimeoutTimer = setTimeout(() => {
    // 已切到别的节目则忽略本次超时，避免覆盖新的播放
    if (currentEpisode !== episode) return;
    console.warn('[audio] HLS 重试超时，降级到 mp3');
    _fallbackToMp3(episode);
  }, 4000);
}

/**
 * 降级到 mp3 整文件播放（HLS 重试耗尽或不可用时的最终兜底）
 *
 * 无 audio_url 时可降级源耗尽，按真正致命错误处理（通知页面 + 失败 toast）。
 * 有 audio_url 时切换协议并重新设置 src；8s 内 onPlay 未触发则判定 mp3 也失败，
 * 给明确反馈而非无限等待（NotSupportedError 不触发 onError，需要此保护）。
 * @param {Object} episode - 当前节目
 */
function _fallbackToMp3(episode) {
  // 无 mp3 兜底源：真正失败
  if (!episode || !episode.audio_url) {
    setWaiting(false);
    currentEpisode = null;
    currentProtocol = '';
    notifyErrorListeners({ errCode: -1, errMsg: '音频加载失败' });
    wx.showToast({ title: '音频加载失败，请稍后重试', icon: 'none' });
    return;
  }
  currentProtocol = 'audio';
  _applyProtocol('audio');
  setWaiting(true);
  audioManager.src = episode.audio_url;
  const fallbackPlay = audioManager.play();
  if (fallbackPlay && typeof fallbackPlay.catch === 'function') {
    fallbackPlay.catch((e) => console.debug('[audio] fallback play() 被中断（可忽略）:', e && e.message));
  }
  // 超时保护：mp3 也可能加载失败（NotSupportedError 不触发 onError）
  // 8s 内 onPlay 未触发则判定失败，给用户明确反馈而非无限等待
  clearTimeout(fallbackTimeoutTimer);
  fallbackTimeoutTimer = setTimeout(() => {
    // onPlay 已触发时 loadingEpisodeId 已被清空，此处检查避免误报
    if (loadingEpisodeId === episode.id) {
      console.error('[audio] mp3 fallback 超时：8s 内未开始播放');
      loadingEpisodeId = null;
      loadingEpisodeUrl = null;
      setWaiting(false);
      currentEpisode = null;
      currentProtocol = '';
      notifyErrorListeners({ errCode: -1, errMsg: '音频加载超时，请检查网络后重试' });
      wx.showToast({ title: '音频加载超时，请检查网络后重试', icon: 'none' });
    }
  }, 8000);
}

/**
 * 播放指定节目（自动断点续播）
 * @param {Object} episode - 节目对象 { id, title, audio_url, hls_url? }
 *
 * 队列里的 episode 可能是历史列表的摘要对象（无 audio_url 字段），
 * 此处按需 fetch 详情补齐，并将完整对象回写队列避免下次切换时重复请求。
 */
async function playEpisode(episode) {
  // 缺 audio_url 时先拉详情补齐（来自历史/搜索列表的摘要对象）
  // 注意：hls_url 是可选字段，不能用作判定条件（旧节目可能没有 HLS）
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

  // 防重入：同一节目同一 URL 正在加载中时跳过，避免 BackgroundAudioManager
  // 在 src 加载中再次赋值导致 src 被清空（errCode:0 src:null）
  // 真机上页面跳转/快速点击可能多次触发 playEpisode
  // 用实际播放 URL（localPath/hls_url/audio_url 三选一）作为去重 key，
  // 否则 hls_url 场景下 episode.audio_url 不变会被误判为重复调用
  const picked = _pickPlayableUrl(episode);
  if (loadingEpisodeId === episode.id && loadingEpisodeUrl === picked.url) {
    console.debug('[audio] 节目正在加载中，跳过重复调用:', episode.title);
    return;
  }
  loadingEpisodeId = episode.id;
  loadingEpisodeUrl = picked.url;
  // 重置 HLS 静默重试计数：每首新节目都拥有完整的重试预算
  hlsRetryCount = 0;

  console.debug('[audio] playEpisode called:', episode.title, 'src:', picked.url, 'protocol:', picked.protocol);
  currentEpisode = episode;
  // 记录当前协议：onError 时用于判断是否需要 HLS→mp3 fallback
  currentProtocol = picked.protocol;
  // 重置倍速缓存：切歌后部分基础库会重置 playbackRate 为 1.0，
  // 此处强制下次 applyPlaybackRate 重新写入，保证倍速不丢
  lastAppliedRate = null;
  // 重置待 seek 标志：避免上一首的 seek 残留
  pendingSeek = 0;
  // 重置收听增量基准：切歌时清空，首次进度上报 tick 时重新初始化为当前 position，
  // 避免上一首的 position 影响本首的收听时长增量计算（任务7）
  lastReportedPosition = -1;

  // 立即开始播放，不等 fetchPlayProgress（真机上 async 等待会导致点击播放无响应）
  audioManager.title = episode.title;
  audioManager.epname = episode.title;
  audioManager.episodeId = episode.id;
  // URL 编码：后端 content_service 已用 urllib.quote 对中文路径编码，
  // 前端不再二次 encodeURI，否则 % 会被编码成 %25 导致 404
  //
  // V1.3：HLS 协议标识（基础库 2.41.0+ 支持 protocol 属性）
  // 显式声明 protocol 让播放器按 HLS 协议处理 m3u8，避免部分基础库
  // 因 URL 后缀识别失败而走 mp3 整文件下载路径。旧版基础库无 protocol
  // 属性时 try-catch 静默忽略，回退到自动识别（仍可正常播放 m3u8）
  _applyProtocol(picked.protocol);
  audioManager.src = picked.url;
  // play() 返回 Promise，若未 resolve 就被 pause() 打断会抛 DOMException
  // （"The play() request was interrupted by a call to pause()"）
  // 这里 catch 掉该异常，避免未捕获的 promise rejection 污染控制台
  const playPromise = audioManager.play();
  if (playPromise && typeof playPromise.catch === 'function') {
    playPromise.catch((err) => {
      console.debug('[audio] play() 被中断（可忽略）:', err && err.message);
    });
  }

  // 查询上次播放进度（断点续播），在后台异步进行，不阻塞播放
  // localData.getProgress 优先本地读取，本地无时从后端读取
  try {
    const progress = await localData.getProgress(episode.id);
    if (progress && progress.position > 0 && !progress.completed) {
      // 用 pendingSeek 标志位代替 onCanplay 回调注册：
      // onCanplay 可能多次触发（缓冲恢复/seek 后再 canplay），
      // 旧实现每次都 seek 会造成重复缓冲卡顿。
      // 这里仅在 pendingSeek > 0 时 seek 一次，seek 完成立即清零。
      pendingSeek = progress.position;
    }
  } catch (err) {
    console.debug('获取播放进度失败，从开头播放:', err.message);
  }
  // 记录播放历史：开始播放即记入本地历史（后端历史由 progress 上报自动记录）
  localData.addHistory(episode, 0);
  // 队列为空时自动补全：从分享链接/收藏页直接进入详情页时队列未设置，
  // onEnded→playNext 会因队列空而无法自动连播。异步拉取当日列表作为队列，
  // 不阻塞当前播放，拉取失败时静默降级为单条播放（任务4）
  if (playQueue.length === 0) {
    _autoFillQueue(episode);
  }
  // 预加载下一首详情：onEnded→playNext 是同步路径，若下一首缺 audio_url
  // 会触发 await fetchEpisodeDetail 造成卡顿。此处提前拉取并缓存，
  // playNext 时优先消费 _preloadedNextEpisode，避免阻塞
  _preloadNextEpisode();
}

/**
 * 队列为空时自动补全：拉取当日列表作为播放队列
 *
 * 为什么需要：从分享链接/收藏页直接进入详情页时 playQueue 为空，
 * onEnded→playNext 会直接返回"已是最后一首"，自动连播失效。
 * 拉取全部频道今日节目作为队列，找到当前节目位置作为起始索引。
 *
 * 异常处理：
 * - 拉取失败：静默降级为单条播放，不阻断当前播放
 * - 当前节目不在当日列表（历史节目）：仍用列表作为队列，起始索引 0
 * - 队列补全后触发 _preloadNextEpisode 预加载下一首
 *
 * @param {Object} currentEp - 当前正在播放的节目
 */
async function _autoFillQueue(currentEp) {
  if (!currentEp || !currentEp.id) return;
  try {
    const data = await fetchTodayEpisode(null);
    const list = Array.isArray(data) ? data : (data ? [data] : []);
    if (list.length === 0) return;
    // 找到当前节目在列表中的位置作为队列起始索引
    // 未找到（历史节目）：仍用列表作为队列，起始索引 0，用户可手动切下一首
    const idx = list.findIndex((ep) => ep && ep.id === currentEp.id);
    setQueue(list, idx >= 0 ? idx : 0);
    // 队列补全后预加载下一首：_preloadNextEpisode 依赖 queueIndex，
    // 补全前 queueIndex=-1 会直接 return，补全后需手动触发一次
    _preloadNextEpisode();
  } catch (err) {
    // 拉取失败静默降级：不阻断当前播放，仅无法自动连播
    console.debug('[audio] 自动补全队列失败（可忽略）:', err.message);
  }
}

/**
 * 预加载队列下一首节目详情
 * 仅在队列非末尾时触发，结果存入 _preloadedNextEpisode 供 playNext 消费
 * 失败时静默：playNext 会回退到 playEpisode 内的 fetch 路径
 */
async function _preloadNextEpisode() {
  // 队列未初始化或已是末尾：无需预加载
  if (queueIndex < 0 || queueIndex >= playQueue.length - 1) return;
  const nextEp = playQueue[queueIndex + 1];
  if (!nextEp || !nextEp.id) return;
  // 已有完整 audio_url：无需 fetch，直接缓存引用并触发音频文件预下载
  if (nextEp.audio_url) {
    _preloadedNextEpisode = nextEp;
    _preloadNextAudio(nextEp);
    return;
  }
  try {
    const detail = await fetchEpisodeDetail(nextEp.id);
    // 详情回写到队列，避免下次切到该节目时再次 fetch
    const fullEp = { ...nextEp, ...detail };
    if (queueIndex + 1 < playQueue.length) {
      playQueue[queueIndex + 1] = fullEp;
    }
    _preloadedNextEpisode = fullEp;
    // 详情就绪后触发音频文件预下载，playEpisode 时可命中本地路径加速首帧
    _preloadNextAudio(fullEp);
  } catch (err) {
    // 预加载失败不影响主流程，下次 playNext 会重新 fetch
    console.debug('[audio] 预加载下一首失败（可忽略）:', err.message);
  }
}

/**
 * 预下载下一首音频文件到本地持久化目录
 *
 * 为什么：_preloadNextEpisode 仅预加载了 episode 详情（避免 playNext 同步路径中 await fetch），
 * 但音频文件本身仍需在 playEpisode 设置 src 后由 BackgroundAudioManager 网络下载，
 * 首帧缓冲仍会卡顿。此处提前 downloadFile + saveFile，命中后 playEpisode 直接用本地路径。
 *
 * 失败处理：预下载失败仅 console.warn，不设置 localPath，playEpisode 仍用 audio_url 网络播放。
 * BackgroundAudioManager.src 支持 wxfile:// 本地路径（基础库 2.0.0+），命中时首帧更快。
 *
 * @param {Object} episode - 已含 audio_url 的节目对象
 */
function _preloadNextAudio(episode) {
  if (!episode || !episode.audio_url) return;
  // 已有 localPath 的不重复下载，避免同一节目多次预下载浪费带宽
  if (episode.localPath) return;

  wx.downloadFile({
    url: episode.audio_url,
    success: (res) => {
      if (res.statusCode !== 200) {
        console.warn('[audio] 预下载下一首失败，HTTP', res.statusCode);
        return;
      }
      // 保存到本地持久化目录：临时文件会在小程序退出/7 天后清理，saveFile 后持久保留
      wx.getFileSystemManager().saveFile({
        tempFilePath: res.tempFilePath,
        success: (saveRes) => {
          // 路径同时写入预加载缓存与队列当前项，playEpisode/playNext 均可消费
          if (_preloadedNextEpisode && _preloadedNextEpisode.id === episode.id) {
            _preloadedNextEpisode.localPath = saveRes.savedFilePath;
          }
          if (queueIndex + 1 < playQueue.length && playQueue[queueIndex + 1].id === episode.id) {
            playQueue[queueIndex + 1].localPath = saveRes.savedFilePath;
          }
        },
        fail: (err) => {
          console.warn('[audio] saveFile 失败（可忽略）:', err.errMsg);
        },
      });
    },
    fail: (err) => {
      console.warn('[audio] 预下载下一首失败（可忽略）:', err.errMsg);
    },
  });
}

// ==================== 离线下载（FR-MC-09） ====================

// 进行中的下载任务，key=episodeId，value=wx.downloadFile 返回的 task（支持取消）
const _activeDownloads = {};

/**
 * 下载单集音频到本地持久目录（FR-MC-09）
 * @param {Object} episode - 节目对象（需含 id / audio_url / title 等）
 * @param {Object} [opts] - { onProgress(percent0-100), onState(stateStr) }
 *   onState 回调状态：'downloading' | 'saving' | 'done'
 * @returns {Promise<{localPath, size, episodeId, cached}>}
 *   已下载则直接 resolve（幂等，cached=true）；成功返回 saveFile 的持久路径
 */
function downloadEpisode(episode, opts) {
  opts = opts || {};
  if (!episode || !episode.id) {
    return Promise.reject(new Error('无效的下载节目'));
  }
  // 幂等：已下载则直接返回，避免重复下载浪费流量
  if (downloadStore.isDownloaded(episode.id)) {
    const rec = downloadStore.getDownload(episode.id);
    return Promise.resolve({
      localPath: rec.localPath,
      size: rec.size,
      episodeId: episode.id,
      cached: true,
    });
  }
  // 进行中：避免并发重复触发（页面连续点击 / 整课批量下载）
  if (_activeDownloads[episode.id]) {
    return Promise.reject(new Error('下载进行中'));
  }
  // 选择下载源：优先本地已解析、其次 mp3、最后 HLS（开发者工具不支持 HLS）
  const url = episode.localPath
    || episode.audio_url
    || (episode.hls_url && !isDevTools() ? episode.hls_url : '');
  if (!url) {
    return Promise.reject(new Error('无可用音频源'));
  }
  if (opts.onState) opts.onState('downloading');
  return new Promise((resolve, reject) => {
    const task = wx.downloadFile({
      url,
      success: (res) => {
        delete _activeDownloads[episode.id];
        if (res.statusCode !== 200) {
          reject(new Error('下载失败 HTTP ' + res.statusCode));
          return;
        }
        let size = 0;
        // 取文件大小用于占用统计；失败不阻断下载流程
        try {
          wx.getFileSystemManager().getFileInfo({
            filePath: res.tempFilePath,
            success: (info) => { size = (info && info.size) || 0; doSave(size); },
            fail: () => { doSave(0); },
          });
        } catch (e) {
          doSave(0);
        }
        function doSave(sz) {
          if (opts.onState) opts.onState('saving');
          // 持久化保存：临时文件会被清理，saveFile 后长期保留
          wx.getFileSystemManager().saveFile({
            tempFilePath: res.tempFilePath,
            success: (saveRes) => {
              const savedPath = saveRes.savedFilePath;
              downloadStore.addDownload(episode, savedPath, sz);
              if (opts.onState) opts.onState('done');
              resolve({ localPath: savedPath, size: sz, episodeId: episode.id, cached: false });
            },
            fail: (err) => {
              reject(new Error('保存失败：' + ((err && err.errMsg) || '')));
            },
          });
        }
      },
      fail: (err) => {
        delete _activeDownloads[episode.id];
        reject(new Error('下载失败：' + ((err && err.errMsg) || '')));
      },
    });
    if (task && typeof task.onProgressUpdate === 'function') {
      task.onProgressUpdate((p) => {
        if (opts.onProgress) opts.onProgress(Math.floor((p && p.progress) || 0));
      });
    }
    _activeDownloads[episode.id] = task;
  });
}

/**
 * 取消进行中的下载（FR-MC-09）
 * @param {number} episodeId
 */
function cancelDownload(episodeId) {
  const task = _activeDownloads[episodeId];
  if (task && typeof task.abort === 'function') {
    try { task.abort(); } catch (e) { /* 忽略 */ }
  }
  delete _activeDownloads[episodeId];
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
 *
 * 优先消费 _preloadedNextEpisode：onEnded→playNext 是同步路径，
 * 若直接 await fetchEpisodeDetail 会阻塞 onEnded 回调导致用户感知卡顿。
 * 预加载未命中时退回 playEpisode 内部按需 fetch 的原逻辑。
 */
function playNext() {
  if (queueIndex < 0 || queueIndex >= playQueue.length - 1) {
    // 队列末端：仅提示，不强制停止当前播放（用户可能想重听）
    wx.showToast({ title: '已是最后一首', icon: 'none' });
    return false;
  }
  queueIndex += 1;
  // 优先使用预加载结果：命中时 episode 已含 audio_url，playEpisode 内部跳过 fetch
  const next = _preloadedNextEpisode || playQueue[queueIndex];
  // 消费后立即清空：避免跨节目残留旧值
  _preloadedNextEpisode = null;
  // 回写队列当前项：预加载命中时已是完整对象，保证下次切回不再 fetch
  if (next) playQueue[queueIndex] = next;
  notifyQueueListeners();
  playEpisode(next);
  return true;
}

/**
 * 跳到队列中指定索引的节目播放
 * 为什么需要这个接口：onQueueItemClick 直接调 playEpisode 不会更新 queueIndex，
 * 导致 onEnded→playNext 时 queueIndex 仍是旧值，连播顺序错乱
 * （用户点第3项后播完会跳到第2首而非第4首）
 * @param {number} index - 目标索引
 * @returns {boolean} 是否成功切换
 */
function playQueueAt(index) {
  if (index < 0 || index >= playQueue.length) return false;
  queueIndex = index;
  // 清掉旧的预加载缓存：避免下次 playNext 误用上一首的预加载结果
  _preloadedNextEpisode = null;
  notifyQueueListeners();
  const ep = playQueue[queueIndex];
  if (ep) playEpisode(ep);
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

// 滴答间隔：每 5 秒更新一次剩余时间（每秒触发 60 分钟会产生 3600 次 setData，
// 5 秒级精度用户感知不到差异，故降频以减少 UI 渲染开销）
const SLEEP_TICK_INTERVAL = 5;

/**
 * 启动睡眠定时器
 * @param {number} seconds - 倒计时秒数
 */
function startSleepTimer(seconds) {
  stopSleepTimer();
  if (!seconds || seconds <= 0) return;

  sleepRemaining = seconds;
  notifySleepListeners({ remaining: sleepRemaining, active: true });

  // 滴答定时器：每 5 秒更新剩余时间，供 UI 显示
  // 60 分钟定时器从 3600 次 setData 降到 720 次，显著降低渲染开销
  sleepTickTimer = setInterval(() => {
    sleepRemaining -= SLEEP_TICK_INTERVAL;
    if (sleepRemaining <= 0) {
      // 到点：暂停播放并清理
      if (audioManager && !audioManager.paused) audioManager.pause();
      stopSleepTimer();
      wx.showToast({ title: '睡眠定时已结束', icon: 'none' });
    } else if (sleepRemaining < SLEEP_TICK_INTERVAL) {
      // 尾段精确到秒：剩余 < 5 秒时，5 秒滴答会跨过到点时间最多 4 秒
      // 改用 setTimeout 等待剩余时间，保证到点暂停的精确性
      const tail = sleepRemaining;
      // 先清掉主定时器，避免与尾段 setTimeout 同时触发
      clearInterval(sleepTickTimer);
      sleepTickTimer = null;
      sleepRemaining = 0;
      sleepTailTimer = setTimeout(() => {
        // 触发后走与到点一致的路径：sleepRemaining 已为 0，直接暂停并清理
        if (audioManager && !audioManager.paused) audioManager.pause();
        stopSleepTimer();
        wx.showToast({ title: '睡眠定时已结束', icon: 'none' });
      }, tail * 1000);
    } else {
      notifySleepListeners({ remaining: sleepRemaining, active: true });
    }
  }, SLEEP_TICK_INTERVAL * 1000);
}

/**
 * 停止睡眠定时器
 */
function stopSleepTimer() {
  if (sleepTickTimer) {
    clearInterval(sleepTickTimer);
    sleepTickTimer = null;
  }
  // 尾段精确计时也需清理：用户手动取消定时器时若已切换到尾段 setTimeout，
  // 不清掉会在到点后误触发暂停
  if (sleepTailTimer) {
    clearTimeout(sleepTailTimer);
    sleepTailTimer = null;
  }
  sleepRemaining = 0;
  notifySleepListeners({ remaining: 0, active: false });
}

/**
 * 获取睡眠定时器状态
 */
function getSleepStatus() {
  // active 判断需同时考虑主定时器与尾段 setTimeout，否则尾段期间会误报为 inactive
  return { remaining: sleepRemaining, active: !!(sleepTickTimer || sleepTailTimer) };
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

// ==================== 音频 loading 状态通知 ====================

/**
 * 修改 waiting 状态并通知所有订阅者
 * 仅在状态变化时触发回调，避免重复通知造成 UI 抖动
 */
function setWaiting(waiting) {
  const next = !!waiting;
  if (isWaiting === next) return;
  isWaiting = next;
  waitingListeners.forEach((l) => {
    try { l(isWaiting); } catch (e) { console.error(e); }
  });
}

/**
 * 订阅 waiting 状态变化（页面用来切换 loading 菊花显隐）
 * @param {Function} callback - 回调 (waiting: boolean) => void
 */
function onWaitingChange(callback) {
  if (typeof callback === 'function') waitingListeners.push(callback);
}

/**
 * 取消订阅 waiting 状态变化
 * @param {Function} callback - 之前注册的回调引用
 */
function offWaitingChange(callback) {
  waitingListeners = waitingListeners.filter((l) => l !== callback);
}

/**
 * 查询当前 waiting 状态（页面初始化时拉取当前值用）
 */
function isWaitingNow() {
  return isWaiting;
}

// ==================== 时间更新通知 ====================

/**
 * 订阅时间更新事件（与 onPlaybackChange / onWaitingChange 模式一致）
 * 内部 onTimeUpdate 已节流到 800ms 一次，订阅者收到的回调频率上限约 1 次/秒
 * @param {Function} callback - 回调 (currentTime: number, duration: number) => void
 */
function onTimeUpdateChange(callback) {
  if (typeof callback === 'function') currentTimeListeners.push(callback);
}

/**
 * 取消订阅时间更新事件
 * @param {Function} callback - 之前注册的回调引用
 */
function offTimeUpdateChange(callback) {
  currentTimeListeners = currentTimeListeners.filter((l) => l !== callback);
}

function notifyTimeUpdateListeners(currentTime, duration) {
  currentTimeListeners.forEach((l) => {
    try { l(currentTime, duration); } catch (e) { console.error(e); }
  });
}

/**
 * 查询当前播放位置（秒，整数）
 * 页面初始化时拉取当前值用，避免直接访问 audioManager.currentTime
 */
function getCurrentTime() {
  return audioManager ? Math.floor(audioManager.currentTime || 0) : 0;
}

/**
 * 查询当前音频总时长（秒，整数）
 */
function getDuration() {
  return audioManager ? Math.floor(audioManager.duration || 0) : 0;
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
    // 不再因 duration<=0 直接 return：
    // BackgroundAudioManager 在 HLS/流式加载下 duration 会延迟填充，
    // 若在此期间硬性跳过上报，listened_seconds 永远累加为 0，
    // 直接导致"我的"页面累计收听时长永久显示 0 分钟。
    // listened_seconds 基于 currentTime 增量计算，不依赖 duration；
    // duration 字段传 0 时后端 Field(ge=0) 可接受，等填充后再带正确值即可。
    if (!currentEpisode || !audioManager) return;

    progressReporting = true;
    try {
      const currentPos = Math.floor(audioManager.currentTime);
      // 计算本次上报周期内的收听时长增量（任务7）
      // - lastReportedPosition < 0：首次 tick，初始化基准，不计算增量
      //   避免断点续播的 pendingSeek 位置被误算为收听增量
      // - delta > 0：正常前进，作为 listened_seconds 透传后端累加 User.total_listen_duration
      // - delta <= 0：用户 seek 后退或未前进，丢弃本次增量（避免负累加）
      let listenedSeconds = 0;
      if (lastReportedPosition < 0) {
        lastReportedPosition = currentPos;
      } else {
        const delta = currentPos - lastReportedPosition;
        if (delta > 0) listenedSeconds = delta;
        lastReportedPosition = currentPos;
      }
      // 双写：本地+后端（localData.saveProgress 内部已处理两路写入）
      await localData.saveProgress(
        currentEpisode.id,
        currentPos,
        Math.floor(audioManager.duration),
        false,
        listenedSeconds
      );
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

/**
 * 跳转到指定播放位置
 *
 * BackgroundAudioManager.seek() 在 paused 状态下不生效（微信官方限制），
 * 必须先调用 play() 进入播放状态后才能 seek。
 * 此函数封装该逻辑：暂停状态下先 play 并设置 pendingSeek，
 * onCanplay 回调会读取 pendingSeek 自动 seek 到目标位置。
 *
 * @param {number} position - 目标位置（秒）
 */
function seek(position) {
  if (!audioManager) return;
  if (typeof position !== 'number' || Number.isNaN(position) || position < 0) return;

  // 上限保护：超过 duration 的 seek 会触发 onEnded，导致误判播放完成
  const duration = audioManager.duration || 0;
  const targetPos = duration > 0 ? Math.min(position, Math.max(0, duration - 1)) : position;

  if (audioManager.paused) {
    // 暂停状态下 seek 不生效：先 play 触发加载，pendingSeek 由 onCanplay 处理
    // onCanplay 在 canplay 后会自动 seek 到 pendingSeek 位置
    pendingSeek = targetPos;
    try {
      const p = audioManager.play();
      if (p && typeof p.catch === 'function') {
        p.catch((err) => console.debug('[audio] seek->play() 被中断（可忽略）:', err && err.message));
      }
    } catch (e) {
      console.warn('[audio] seek 时 play 失败:', e && e.message);
    }
  } else {
    // 播放中：直接 seek 即可
    try { audioManager.seek(targetPos); } catch (e) {
      console.warn('[audio] seek 失败:', e && e.message);
    }
  }
}

/**
 * 设置待 seek 的目标位置（供页面层调用，替代直接注册 onCanplay）
 *
 * 页面层调用此函数后，audio.js 内部 onCanplay 会自动 seek 并清零，
 * 避免页面层重复注册 onCanplay 导致回调累积与 seek 时机不可控（R80）。
 * @param {number} position - 目标位置（秒）
 */
function setPendingSeek(position) {
  pendingSeek = position;
}

module.exports = {
  initPlayer,
  playEpisode,
  safePlay,
  stopProgressReport,
  resumePlay,
  seek,
  setPendingSeek,
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
  playQueueAt,
  onQueueChange,
  // 离线下载（FR-MC-09）
  downloadEpisode,
  cancelDownload,
  // 睡眠定时器
  startSleepTimer,
  stopSleepTimer,
  getSleepStatus,
  onSleepChange,
  // 播放错误
  onError,
  // 播放/暂停状态变更（实时通知，替代轮询）
  onPlaybackChange,
  // 音频 loading 状态（waiting 菊花显隐）
  onWaitingChange,
  offWaitingChange,
  isWaiting: isWaitingNow,
  // 时间更新订阅（统一 onTimeUpdate 监听，替代页面层各自订阅）
  onTimeUpdateChange,
  offTimeUpdateChange,
  getCurrentTime,
  getDuration,
  // 当前节目
  getCurrentEpisode,
};
