/**
 * 本地数据存储服务：播放进度、收藏、播放历史
 *
 * 设计原则：
 * - 按 openid 隔离：不同微信用户数据互不干扰，切换账号自动隔离
 * - 本地为主 + 后端备份：写入时双写本地和后端，后端失败不影响本地
 * - 读取优先本地：离线可用，后端异步同步最新值
 *
 * 存储格式：
 * - news_progress_{openid}: { [episodeId]: { position, duration, completed, updated_at } }
 * - news_favorites_{openid}: [ { id, title, audio_url, cover_url, duration, ..., favorited_at }, ... ]
 * - news_history_{openid}:   [ { id, title, audio_url, cover_url, duration, ..., played_at, position }, ... ]
 *   history 按 played_at 倒序，最多保留 100 条
 *
 * 注意：调用方需确保登录完成后才调用（openid 已就绪），
 * app.js readyPromise 机制保证页面 onLoad 可 await 登录完成。
 */
const {
  reportPlayProgress,
  fetchPlayProgress,
  fetchRecentPlaylogs,
  getFavorites,
  addFavorite: apiAddFavorite,
  removeFavorite: apiRemoveFavorite,
  checkFavorite: apiCheckFavorite,
} = require('./api');
// 章节「已学完」判定阈值：统一收敛到 services/constants（与后端 _COMPLETE_RATIO 保持一致）
const { COURSE_COMPLETE_RATIO } = require('./constants');

// ==================== openid 获取 ====================

/**
 * 获取当前登录用户的 openid
 * 未登录时返回空字符串，本地存储退化为不写入（仅后端可用）
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

function progressKey(openid) { return `news_progress_${openid}`; }
function favoritesKey(openid) { return `news_favorites_${openid}`; }
function historyKey(openid) { return `news_history_${openid}`; }

// 历史记录最大条数，超出按最旧优先淘汰
const HISTORY_MAX = 100;

// 非关键 storage 异步写入辅助：统一 fail 回调，避免重复样板代码
// 为什么：local-data 中本地缓存（收藏/历史/进度同步覆盖）非关键，可异步写不阻塞主线程；
// 注意：saveProgress 中的当前播放进度写入是关键路径（onPause/onEnded 时立即落盘），
// 仍用 wx.setStorageSync 同步写入，不经过此辅助函数。
function setStorageAsync(key, data) {
  wx.setStorage({
    key,
    data,
    fail: (e) => console.warn('[local-data] storage 异步写入失败:', key, e && e.errMsg),
  });
}

// ==================== 播放进度 ====================

/**
 * 保存播放进度（双写本地 + 后端）
 * @param {number} episodeId
 * @param {number} position - 当前播放位置（秒）
 * @param {number} duration - 总时长（秒）
 * @param {boolean} completed - 是否完播
 * @param {number} [listenedSeconds=0] - 本次上报周期内实际收听时长增量（秒），
 *   后端累加到 User.total_listen_duration；不传或 <=0 时不累加
 */
function saveProgress(episodeId, position, duration, completed, listenedSeconds) {
  const openid = getOpenid();
  // 1. 本地写入：按 episodeId 索引，便于快速查询断点续播
  if (openid) {
    const key = progressKey(openid);
    try {
      const all = wx.getStorageSync(key) || {};
      all[episodeId] = {
        position: Math.floor(position || 0),
        duration: Math.floor(duration || 0),
        completed: !!completed,
        updated_at: Date.now(),
      };
      wx.setStorageSync(key, all);
    } catch (e) {
      console.warn('[local-data] 保存进度到本地失败:', e.message);
    }
  }
  // 2. 后端写入：异步，失败不影响本地（reportPlayProgress 内部已 catch）
  // listened_seconds 透传给后端累加 User.total_listen_duration（任务7）
  return reportPlayProgress({
    episode_id: episodeId,
    position: Math.floor(position || 0),
    duration: Math.floor(duration || 0),
    completed: !!completed,
    listened_seconds: Math.floor(listenedSeconds || 0),
  });
}

/**
 * 获取播放进度（优先本地，本地无时从后端读取并缓存）
 * @param {number} episodeId
 * @returns {Promise<{position, duration, completed}|null>}
 */
async function getProgress(episodeId) {
  const openid = getOpenid();
  // 1. 优先本地读取
  if (openid) {
    const key = progressKey(openid);
    try {
      const all = wx.getStorageSync(key) || {};
      if (all[episodeId]) {
        // 异步从后端同步：若后端进度更新（position 更大），覆盖本地
        // 不阻塞当前返回，避免断点续播等待网络
        fetchPlayProgress(episodeId).then((serverProgress) => {
          if (!serverProgress) return;
          try {
            const localAll = wx.getStorageSync(key) || {};
            const local = localAll[episodeId];
            // 后端 position 更大说明在别的设备播放过更多，取后端值
            if (local && serverProgress.position > local.position) {
              localAll[episodeId] = {
                position: serverProgress.position,
                duration: serverProgress.duration || local.duration,
                completed: serverProgress.completed || local.completed,
                updated_at: Date.now(),
              };
              setStorageAsync(key, localAll);
            }
          } catch (e) { /* 同步失败忽略 */ }
        });
        return all[episodeId];
      }
    } catch (e) {
      console.warn('[local-data] 读取本地进度失败:', e.message);
    }
  }
  // 2. 本地无：从后端读取并缓存到本地
  const serverProgress = await fetchPlayProgress(episodeId);
  if (serverProgress && openid) {
    try {
      const key = progressKey(openid);
      const all = wx.getStorageSync(key) || {};
      all[episodeId] = {
        position: serverProgress.position || 0,
        duration: serverProgress.duration || 0,
        completed: !!serverProgress.completed,
        updated_at: Date.now(),
      };
      // 非关键写入（后端进度同步缓存）：改异步避免阻塞主线程
      setStorageAsync(key, all);
    } catch (e) { /* 缓存失败忽略 */ }
  }
  return serverProgress;
}

// ==================== 收藏 ====================

/**
 * 添加收藏（双写本地 + 后端）
 * @param {Object} episode - 完整节目对象（含 id/title/audio_url 等，用于本地展示）
 */
async function addFavorite(episode) {
  if (!episode || !episode.id) return;
  const openid = getOpenid();
  // 后端写入（先调后端，成功后再写本地，避免后端失败时本地与后端不一致）
  await apiAddFavorite(episode.id);
  // 本地写入
  if (openid) {
    const key = favoritesKey(openid);
    try {
      const list = wx.getStorageSync(key) || [];
      // 幂等：已存在则跳过
      if (list.some((item) => item.id === episode.id)) return;
      list.unshift({ ...episode, favorited_at: Date.now() });
      // 非关键写入（本地收藏缓存）：改异步避免阻塞主线程
      setStorageAsync(key, list);
    } catch (e) {
      console.warn('[local-data] 添加本地收藏失败:', e.message);
    }
  }
}

/**
 * 取消收藏（双写本地 + 后端）
 * @param {number} episodeId
 */
async function removeFavorite(episodeId) {
  if (!episodeId) return;
  const openid = getOpenid();
  // 后端删除
  await apiRemoveFavorite(episodeId);
  // 本地删除
  if (openid) {
    const key = favoritesKey(openid);
    try {
      const list = wx.getStorageSync(key) || [];
      const newList = list.filter((item) => item.id !== episodeId);
      // 非关键写入（本地收藏缓存删除）：改异步避免阻塞主线程
      setStorageAsync(key, newList);
    } catch (e) {
      console.warn('[local-data] 删除本地收藏失败:', e.message);
    }
  }
}

/**
 * 获取收藏列表（优先本地，本地无时从后端读取并缓存）
 * @returns {Promise<Array>}
 */
async function getFavoriteList() {
  const openid = getOpenid();
  // 优先本地
  if (openid) {
    const key = favoritesKey(openid);
    try {
      const localList = wx.getStorageSync(key);
      if (localList && localList.length > 0) {
        // 异步从后端同步最新值（不阻塞返回）
        _syncFavoritesFromServer(openid);
        return localList;
      }
    } catch (e) { /* 读取失败走后端 */ }
  }
  
  // 本地无：从后端读取并缓存
  try {
    const res = await getFavorites();
    const list = (res && (res.list || res.items)) || [];
    if (openid && list.length > 0) {
      try {
        // 非关键写入（收藏列表后端同步缓存）：改异步避免阻塞主线程
        setStorageAsync(favoritesKey(openid), list);
      } catch (e) { /* 缓存失败忽略 */ }
    }
    return list;
  } catch (e) {
    return [];
  }
}

/**
 * 检查是否已收藏（优先本地）
 * @param {number} episodeId
 * @returns {Promise<{favorited: boolean}>}
 */
async function checkFavoriteLocal(episodeId) {
  const openid = getOpenid();
  // 优先本地
  if (openid) {
    const key = favoritesKey(openid);
    try {
      const list = wx.getStorageSync(key) || [];
      if (list.length > 0) {
        return { favorited: list.some((item) => item.id === episodeId) };
      }
    } catch (e) { /* 读取失败走后端 */ }
  }
  // 本地无：从后端读取
  try {
    const res = await apiCheckFavorite(episodeId);
    return { favorited: !!(res && res.favorited) };
  } catch (e) {
    return { favorited: false };
  }
}

/**
 * 异步从后端同步收藏列表到本地（不阻塞主流程）
 * 用于本地有数据时后台刷新最新值
 */
function _syncFavoritesFromServer(openid) {
  getFavorites().then((res) => {
    const list = (res && (res.list || res.items)) || [];
    if (list.length > 0) {
      try {
        // 非关键写入（收藏列表后端同步缓存）：改异步避免阻塞主线程
        setStorageAsync(favoritesKey(openid), list);
      } catch (e) { /* 同步失败忽略 */ }
    }
  }).catch(() => {});
}

// ==================== 播放历史 ====================

/**
 * 添加播放历史（双写本地 + 后端）
 *
 * 后端的播放历史通过 reportPlayProgress 自动记录（后端 playlog 表），
 * 本地单独维护一份历史列表用于离线展示，按 played_at 倒序，最多 100 条。
 *
 * @param {Object} episode - 完整节目对象
 * @param {number} position - 当前播放位置（秒，可选）
 */
function addHistory(episode, position) {
  if (!episode || !episode.id) return;
  const openid = getOpenid();
  if (!openid) return; // 未登录不写本地历史
  const key = historyKey(openid);
  try {
    const list = wx.getStorageSync(key) || [];
    // 去重：移除已存在的同一节目记录
    const filtered = list.filter((item) => item.id !== episode.id);
    // 添加到头部
    filtered.unshift({
      id: episode.id,
      title: episode.title,
      audio_url: episode.audio_url,
      cover_url: episode.cover_url,
      duration: episode.duration,
      channel_id: episode.channel_id,
      channel_name: episode.channel_name,
      published_at: episode.published_at,
      played_at: Date.now(),
      position: position || 0,
    });
    // 限制最大条数
    const trimmed = filtered.slice(0, HISTORY_MAX);
    // 关键写入（已播放标记依赖本地 history 立即可读）：用同步写入
    // 为什么不用 setStorageAsync：playEpisode 调 addHistory 后用户可能立即返回上一页，
    // loadPlayedHistory 读取本地 history 时若异步写入未完成会读到空列表，
    // 导致刚播过的节目 played 标记为 false，与"已播放"状态不一致
    wx.setStorageSync(key, trimmed);
  } catch (e) {
    console.warn('[local-data] 添加本地历史失败:', e.message);
  }
}

/**
 * 获取播放历史（优先本地，本地无时从后端读取并缓存）
 * @param {number} page - 页码，从 1 开始
 * @param {number} size - 每页条数
 * @returns {Promise<{list: Array, total: number}>}
 */
async function getHistory(page = 1, size = 20) {
  const openid = getOpenid();
  // 优先本地
  if (openid) {
    const key = historyKey(openid);
    try {
      const localList = wx.getStorageSync(key);
      if (localList && localList.length > 0) {
        // 异步从后端同步最新值
        _syncHistoryFromServer(openid);
        // 本地分页
        const total = localList.length;
        const start = (page - 1) * size;
        const end = start + size;
        const pageList = localList.slice(start, end);
        return { list: pageList, total };
      }
    } catch (e) { /* 读取失败走后端 */ }
  }
  if (!openid) { return { list: [], total: 0 }; }
  // 本地无：从后端读取并缓存
  try {
    const res = await fetchRecentPlaylogs(page, size);
    const list = (res && res.list) || [];
    const total = (res && res.total) || list.length;
    // 后端返回的是当前页，不全量缓存到本地
    // 仅当是第一页且数据量小时缓存，避免覆盖本地完整列表
    if (openid && page === 1 && list.length > 0) {
      try {
        const key = historyKey(openid);
        const existing = wx.getStorageSync(key) || [];
        // 合并后端数据到本地（去重）
        const merged = [...list, ...existing.filter((e) => !list.some((l) => l.id === e.id))];
        // 非关键写入（历史列表后端同步缓存）：改异步避免阻塞主线程
        setStorageAsync(key, merged.slice(0, HISTORY_MAX));
      } catch (e) { /* 缓存失败忽略 */ }
    }
    return { list, total };
  } catch (e) {
    return { list: [], total: 0 };
  }
}

/**
 * 获取所有已播放过的节目 ID 集合（用于历史页标记"已播"状态）
 * 优先本地，本地无时从后端读取
 * @returns {Promise<Set<number>>}
 */
async function getPlayedHistorySet() {
  const openid = getOpenid();
  // 优先本地
  if (openid) {
    const key = historyKey(openid);
    try {
      const localList = wx.getStorageSync(key);
      if (localList && localList.length > 0) {
        return new Set(localList.map((item) => item.id));
      }
    } catch (e) { /* 读取失败走后端 */ }
  }
  // 无 token 时直接返回空集合，避免对未认证接口发无意义请求
  const { getToken } = require('./auth');
  if (!getToken()) { return new Set(); }
  // 本地无：从后端读取（拉取较大批量构建集合）
  try {
    const res = await fetchRecentPlaylogs(1, 100);
    const list = (res && res.list) || [];
    return new Set(list.map((item) => item.id));
  } catch (e) {
    return new Set();
  }
}

/**
 * 异步从后端同步播放历史到本地（不阻塞主流程）
 */
function _syncHistoryFromServer(openid) {
  fetchRecentPlaylogs(1, 100).then((res) => {
    const list = (res && res.list) || [];
    if (list.length === 0) return;
    try {
      const key = historyKey(openid);
      const existing = wx.getStorageSync(key) || [];
      // 合并：后端数据优先，本地有但后端没有的保留
      const existingIds = new Set(existing.map((e) => e.id));
      const serverIds = new Set(list.map((l) => l.id));
      // 后端列表放前面，本地独有的追加到后面
      const merged = [...list, ...existing.filter((e) => !serverIds.has(e.id))];
      // 非关键写入（历史列表后端同步缓存）：改异步避免阻塞主线程
      setStorageAsync(key, merged.slice(0, HISTORY_MAX));
    } catch (e) { /* 同步失败忽略 */ }
  }).catch(() => {});
}

// ==================== 偏爱频道 ====================

/**
 * 偏爱频道存储：用户勾选的偏爱频道 ID 数组
 * 用于"我的偏爱"tab 筛选节目
 *
 * 与后端订阅（subscribeChannel）的区别：
 * - 订阅是推送通知用，is_subscribed 字段
 * - 偏爱是节目筛选用，独立存储，不依赖订阅状态
 * 两者可独立使用，互不影响
 */
function preferredChannelsKey(openid) { return `news_preferred_channels_${openid}`; }

// 首次引导标记 key（不按 openid 隔离，全局只引导一次）
const ONBOARDED_KEY = 'preferred_channels_onboarded';

/**
 * 获取偏爱频道 ID 列表
 * @returns {Array<number>} 偏爱频道 ID 数组（未设置或未登录时返回空数组）
 */
function getPreferredChannels() {
  const openid = getOpenid();
  if (!openid) return [];
  try {
    return wx.getStorageSync(preferredChannelsKey(openid)) || [];
  } catch (e) {
    return [];
  }
}

/**
 * 设置偏爱频道（全量覆盖）
 * @param {Array<number>} channelIds - 偏爱频道 ID 数组
 */
function setPreferredChannels(channelIds) {
  const openid = getOpenid();
  if (!openid) return;
  const ids = (channelIds || []).filter((id) => id != null);
  try {
    wx.setStorageSync(preferredChannelsKey(openid), ids);
  } catch (e) {
    console.warn('[local-data] 保存偏爱频道失败:', e.message);
  }
}

/**
 * 检查是否已完成首次偏爱频道引导
 * @returns {boolean}
 */
function isPreferredChannelsOnboarded() {
  try {
    return !!wx.getStorageSync(ONBOARDED_KEY);
  } catch (e) {
    return false;
  }
}

/**
 * 标记已完成首次偏爱频道引导
 */
function markPreferredChannelsOnboarded() {
  try {
    wx.setStorageSync(ONBOARDED_KEY, true);
  } catch (e) { /* 忽略 */ }
}

// ==================== 清理（切换账号时调用） ====================

/**
 * 清除指定 openid 的所有本地数据
 * 用于退出登录时清理当前用户的本地缓存
 */
function clearByOpenid(openid) {
  if (!openid) return;
  try {
    wx.removeStorageSync(progressKey(openid));
    wx.removeStorageSync(favoritesKey(openid));
    wx.removeStorageSync(historyKey(openid));
    wx.removeStorageSync(preferredChannelsKey(openid));
  } catch (e) {
    console.warn('[local-data] 清理本地数据失败:', e.message);
  }
}

/**
 * 本地收听统计聚合（离线兜底，FR-MC-10 修复 GAP-11 统计恒为 0）
 *
 * 后端 /users/stats 聚合未就绪时常返回全 0，导致「我的」页统计恒为 0。
 * 此处基于本地进度/收藏聚合出真实统计，纯本地读取不依赖网络：
 * - total_listen_seconds：累计收听秒数（完播记 duration，未完播记已播 position，均不超过 duration）
 * - total_listen_episodes：有播放进度的节目期数（position > 0 的去重数）
 * - completed_episodes：完播期数（completed 或 进度占比 ≥ COURSE_COMPLETE_RATIO）
 * - favorite_count：本地收藏数
 * @returns {{total_listen_seconds:number,total_listen_episodes:number,completed_episodes:number,favorite_count:number}}
 */
function getLocalStats() {
  const openid = getOpenid();
  if (!openid) {
    return { total_listen_seconds: 0, total_listen_episodes: 0, completed_episodes: 0, favorite_count: 0 };
  }
  try {
    const progressAll = wx.getStorageSync(progressKey(openid)) || {};
    const entries = Object.keys(progressAll).map((k) => progressAll[k]).filter(Boolean);
    let listenedSeconds = 0;
    let totalListenEpisodes = 0;
    let completedEpisodes = 0;
    for (const e of entries) {
      const duration = Math.floor(e.duration || 0);
      const position = Math.floor(e.position || 0);
      const completed = !!e.completed || (duration > 0 && position / duration >= COURSE_COMPLETE_RATIO);
      if (position > 0) totalListenEpisodes += 1;
      if (completed) completedEpisodes += 1;
      const listened = completed ? duration : Math.min(position, duration);
      listenedSeconds += Math.max(0, Math.floor(listened));
    }
    const favorites = wx.getStorageSync(favoritesKey(openid)) || [];
    const favoriteCount = Array.isArray(favorites) ? favorites.length : 0;
    return {
      total_listen_seconds: listenedSeconds,
      total_listen_episodes: totalListenEpisodes,
      completed_episodes: completedEpisodes,
      favorite_count: favoriteCount,
    };
  } catch (e) {
    console.warn('[local-data] 本地统计聚合失败:', e && e.message);
    return { total_listen_seconds: 0, total_listen_episodes: 0, completed_episodes: 0, favorite_count: 0 };
  }
}

module.exports = {
  saveProgress,
  getProgress,
  addFavorite,
  removeFavorite,
  getFavoriteList,
  checkFavoriteLocal,
  addHistory,
  getHistory,
  getPlayedHistorySet,
  getLocalStats,
  clearByOpenid,
  // 偏爱频道
  getPreferredChannels,
  setPreferredChannels,
  isPreferredChannelsOnboarded,
  markPreferredChannelsOnboarded,
};
