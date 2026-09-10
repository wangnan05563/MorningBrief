/**
 * 离线下载存储服务（FR-MC-09）
 *
 * 持久化已下载章节：
 *   news_downloads_{openid}: {
 *     [episodeId]: {
 *       episodeId, channelId, channelName,
 *       title, audio_url, cover_url, duration,
 *       localPath, size, savedAt
 *     }
 *   }
 *
 * 设计原则（与 local-data 一致）：
 * - 按 openid 隔离：不同微信用户下载互不干扰
 * - 本地存储仅（V1.2 单机约束）：文件走 wx.saveFile 持久目录，无后端同步
 * - 幂等：addDownload 重复调用只覆盖，不重复落盘
 * - 删除联动物理文件：removeDownload / clearByChannel / clearAll 同时清理 wxfile://
 *
 * 注意：调用方需确保登录完成后才调用（openid 已就绪）。
 */
function getOpenid() {
  try {
    const { getUser } = require('./auth');
    const user = getUser();
    return (user && user.openid) || '';
  } catch (e) {
    return '';
  }
}

function downloadKey(openid) { return `news_downloads_${openid}`; }

// 当前 openid 下载表的内存缓存，避免每次读 storage（下载列表通常不大）
let _cache = null;
let _cacheOpenid = null;

function _getCache(openid) {
  if (_cacheOpenid !== openid || _cache === null) {
    try {
      _cache = wx.getStorageSync(downloadKey(openid)) || {};
    } catch (e) {
      _cache = {};
    }
    _cacheOpenid = openid;
  }
  return _cache;
}

function _setCache(openid, map) {
  _cache = map;
  _cacheOpenid = openid;
  try {
    wx.setStorageSync(downloadKey(openid), map);
  } catch (e) {
    console.warn('[download] 写入下载表失败:', e.message);
  }
}

/**
 * 是否已下载某集（localPath 存在才视为可用）
 * @param {number} episodeId
 * @returns {boolean}
 */
function isDownloaded(episodeId) {
  const openid = getOpenid();
  if (!openid) return false;
  const map = _getCache(openid);
  return !!(map[episodeId] && map[episodeId].localPath);
}

/**
 * 取某集下载记录（含 localPath），未下载返回 null
 */
function getDownload(episodeId) {
  const openid = getOpenid();
  if (!openid) return null;
  const map = _getCache(openid);
  return map[episodeId] || null;
}

/**
 * 取某集已下载的本地播放路径（供 _pickPlayableUrl 离线播放用）
 * @returns {string} 本地路径，未下载返回空串
 */
function getDownloadLocalPath(episodeId) {
  const rec = getDownload(episodeId);
  return rec ? rec.localPath : '';
}

/**
 * 写入一条下载记录（localPath 必需）
 * @param {Object} episode - 节目对象（id/title/audio_url/cover_url/channel_id/channel_name/duration）
 * @param {string} localPath - wx.saveFile 返回的持久路径
 * @param {number} size - 文件字节数
 * @returns {Object|null} 写入的记录
 */
function addDownload(episode, localPath, size) {
  const openid = getOpenid();
  if (!openid || !episode || !episode.id || !localPath) return null;
  const map = _getCache(openid);
  const rec = {
    episodeId: episode.id,
    channelId: episode.channel_id || 0,
    channelName: episode.channel_name || '',
    title: episode.title || '',
    audio_url: episode.audio_url || '',
    cover_url: episode.cover_url || '',
    duration: episode.duration || 0,
    localPath,
    size: size || 0,
    savedAt: Date.now(),
  };
  map[episode.id] = rec;
  _setCache(openid, map);
  return rec;
}

/**
 * 删除单条下载（同时删除物理文件）
 * @returns {boolean} 是否删除成功
 */
function removeDownload(episodeId) {
  const openid = getOpenid();
  if (!openid) return false;
  const map = _getCache(openid);
  const rec = map[episodeId];
  if (!rec) return false;
  _removeFile(rec.localPath);
  delete map[episodeId];
  _setCache(openid, map);
  return true;
}

/**
 * 按频道清空（删除该频道下所有下载 + 物理文件）
 * @returns {number} 删除条数
 */
function clearByChannel(channelId) {
  const openid = getOpenid();
  if (!openid) return 0;
  const map = _getCache(openid);
  let removed = 0;
  Object.keys(map).forEach((k) => {
    if (map[k].channelId === channelId) {
      _removeFile(map[k].localPath);
      delete map[k];
      removed++;
    }
  });
  _setCache(openid, map);
  return removed;
}

/**
 * 清空全部（删除所有物理文件）
 * @returns {number} 删除条数
 */
function clearAll() {
  const openid = getOpenid();
  if (!openid) return 0;
  const map = _getCache(openid);
  let removed = 0;
  Object.keys(map).forEach((k) => {
    _removeFile(map[k].localPath);
    removed++;
  });
  _setCache(openid, {});
  return removed;
}

/**
 * 列出下载（可按 channelId 过滤），按 savedAt 倒序
 * @param {number} [channelId]
 * @returns {Array}
 */
function listDownloads(channelId) {
  const openid = getOpenid();
  if (!openid) return [];
  const map = _getCache(openid);
  let arr = Object.keys(map).map((k) => map[k]);
  if (channelId) arr = arr.filter((r) => r.channelId === channelId);
  arr.sort((a, b) => (b.savedAt || 0) - (a.savedAt || 0));
  return arr;
}

/**
 * 计算总占用字节数
 * @returns {number}
 */
function computeTotalSize() {
  const openid = getOpenid();
  if (!openid) return 0;
  const map = _getCache(openid);
  return Object.keys(map).reduce((sum, k) => sum + (map[k].size || 0), 0);
}

/**
 * 切换账号时清理该用户全部下载（供 profile 退出登录调用）
 * 直接读 storage（不依赖当前缓存），确保跨 openid 也能清干净
 * @returns {number} 删除条数
 */
function clearByOpenid(openid) {
  if (!openid) return 0;
  let map = {};
  try {
    map = wx.getStorageSync(downloadKey(openid)) || {};
  } catch (e) {
    map = {};
  }
  let removed = 0;
  Object.keys(map).forEach((k) => {
    _removeFile(map[k].localPath);
    removed++;
  });
  try {
    wx.removeStorageSync(downloadKey(openid));
  } catch (e) { /* 忽略 */ }
  if (_cacheOpenid === openid) {
    _cache = null;
    _cacheOpenid = null;
  }
  return removed;
}

/**
 * 安全删除物理文件（wxfile:// 持久文件），失败仅告警
 */
function _removeFile(localPath) {
  if (!localPath) return;
  try {
    wx.getFileSystemManager().removeSavedFile({ filePath: localPath });
  } catch (e) {
    console.warn('[download] 删除物理文件失败（可忽略）:', e.message);
  }
}

// ==================== 以标题命名导出（T00387） ====================

// Windows/Android 文件名非法字符 + 控制字符（iOS 另禁冒号，统一处理）
const _ILLEGAL_CHARS = /[/\\:*?"<>|\u0000-\u001f]/g;
// 允许的音频扩展名（从 audio_url 推断，未命中回退 .mp3）
const _AUDIO_EXTS = ['mp3', 'm4a', 'aac', 'wav', 'ogg'];
const _MAX_NAME_LEN = 80; // 文件名（不含扩展名）长度上限，避免超长标题撑爆路径

/**
 * 由节目标题生成合法文件名：标题.mp3
 * 规则（T00387）：以标题命名；标题为空/全非法字符时回退 audio_时间戳.mp3
 * @param {string} title
 * @param {string} [audioUrl] - 用于推断扩展名
 * @returns {string} 如 "2026-09-10 早报.mp3"
 */
function buildTitleFilename(title, audioUrl) {
  let ext = '.mp3';
  if (audioUrl) {
    const m = String(audioUrl).split('?')[0].match(/\.([a-z0-9]+)$/i);
    if (m && _AUDIO_EXTS.indexOf(m[1].toLowerCase()) >= 0) ext = '.' + m[1].toLowerCase();
  }
  let base = String(title || '')
    .replace(_ILLEGAL_CHARS, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^[.\s]+|[.\s]+$/g, '');
  if (base.length > _MAX_NAME_LEN) base = base.slice(0, _MAX_NAME_LEN).trim();
  if (!base) base = 'audio_' + Date.now();
  return base + ext;
}

/**
 * 把已下载的本地文件复制为「以标题命名」的导出副本
 *
 * 为什么需要副本：wx.saveFile 落盘的是自动命名文件（wxfile://usr/xxx），
 * 用户看不到标题；复制到 USER_DATA_PATH/标题.mp3 后文件名即标题，
 * 供 wx.shareFileMessage 导出（fileName 也会带上该名字）。
 *
 * 注意：导出副本独立于下载记录（removeDownload 只删 wxfile:// 原件），
 * 同名标题重复导出会覆盖同一文件，不会无限膨胀。
 *
 * @param {string} localPath - downloadEpisode 返回的持久路径
 * @param {string} title - 节目标题
 * @param {string} [audioUrl] - 用于推断扩展名
 * @returns {Promise<string>} 导出副本完整路径
 */
function exportWithTitle(localPath, title, audioUrl) {
  if (!localPath) {
    return Promise.reject(new Error('无本地文件可导出'));
  }
  const fs = wx.getFileSystemManager();
  const dest = wx.env.USER_DATA_PATH + '/' + buildTitleFilename(title, audioUrl);
  // 先 unlink 旧副本（copyFile 不覆盖已存在文件）；不存在时 fail 走 complete，无副作用
  return new Promise((resolve) => {
    fs.unlink({ filePath: dest, complete: () => resolve() });
  }).then(
    () =>
      new Promise((resolve, reject) => {
        fs.copyFile({
          srcPath: localPath,
          destPath: dest,
          success: () => resolve(dest),
          fail: (err) => reject(new Error('导出失败：' + ((err && err.errMsg) || ''))),
        });
      })
  );
}

/**
 * 通过微信文件会话把音频文件导出到手机（用户在聊天中另存）
 * 必须在用户点击回调链路中调用；失败仅告警（部分环境不支持分享文件）
 * @param {string} filePath - USER_DATA_PATH 下的文件路径
 * @param {string} fileName - 展示给用户的文件名（含扩展名）
 * @returns {Promise<void>}
 */
function shareAudioFile(filePath, fileName) {
  return new Promise((resolve, reject) => {
    if (typeof wx.shareFileMessage !== 'function') {
      reject(new Error('当前微信版本不支持分享文件'));
      return;
    }
    wx.shareFileMessage({
      filePath,
      fileName,
      success: () => resolve(),
      fail: (err) => reject(new Error(((err && err.errMsg) || '分享取消'))),
    });
  });
}

module.exports = {
  isDownloaded,
  getDownload,
  getDownloadLocalPath,
  addDownload,
  removeDownload,
  clearByChannel,
  clearAll,
  listDownloads,
  computeTotalSize,
  clearByOpenid,
  buildTitleFilename,
  exportWithTitle,
  shareAudioFile,
};
