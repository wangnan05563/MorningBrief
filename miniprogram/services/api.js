/**
 * API 封装：token 注入、401 自动重登、统一响应格式处理
 *
 * 所有接口均返回 Promise，成功时 resolve(data)，失败时 reject(Error)
 */

// 按编译环境切换 API 域名：release 为正式版编译产物，其余（develop/trial）走开发环境
// 真机测试时需确保手机与电脑在同一局域网，后端服务可被手机访问
const IS_RELEASE = typeof __wxConfig !== 'undefined' && __wxConfig.envVersion === 'release';

/**
 * 开发环境后端地址。
 *
 * 历史实现曾尝试通过 wx.getSystemInfoSync().ip 自动检测局域网 IP，
 * 但新版基础库已废弃该 API（拆分为 getDeviceInfo/getWindowInfo/getAppBaseInfo 等，
 * 均不再暴露 ip 字段），自动检测实际上拿不到有效 IP。
 *
 * 真机调试时请在下方常量中手动填入电脑局域网 IP（与后端 .env 的 AUDIO_BASE_URL 保持一致）。
 */
const DEV_API_BASE_URL = 'http://192.168.1.65:8000/api/v1';

const BASE_URL = IS_RELEASE
  ? 'https://api.example.com/api/v1'  // 生产环境域名（部署时替换）
  : DEV_API_BASE_URL;  // 开发环境（真机调试时改为局域网 IP，如 http://192.168.x.x:8000/api/v1）

/**
 * 统一请求函数
 * @param {Object} options - { url, method, data, header, _retried }
 * @returns {Promise<any>} - resolve(data) 或 reject(Error)
 *
 * 401 重试保护：
 * - /auth/login 请求本身不触发 401 重试（否则 login -> 401 -> refreshToken -> login 无限循环）
 * - 其他请求 401 时仅重试一次（_retried 标记防止 token 仍无效时无限递归）
 */
function request(options) {
  const { url, method = 'GET', data, header = {}, _retried = false } = options;

  // 延迟 require 避免循环依赖：auth.js 加载时需要 request，若在顶部 require 会拿不到 getToken
  const { getToken, refreshToken } = require('./auth');

  // 注入 token
  const token = getToken();
  if (token) {
    header.Authorization = 'Bearer ' + token;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + url,
      method,
      data,
      header: { 'Content-Type': 'application/json', ...header },
      success: async (res) => {
        // 401 自动重登一次：排除登录接口本身，且仅重试一次
        if (res.statusCode === 401 && !url.startsWith('/auth/') && !_retried) {
          try {
            await refreshToken();
            // 重试原请求，标记 _retried 防止再次进入 401 分支
            const retry = await request({ ...options, _retried: true });
            resolve(retry);
          } catch (e) {
            console.error('刷新 token 失败:', e);
            reject(new Error('登录已失效，请重新打开小程序'));
          }
          return;
        }
        // 业务错误（code != 0）
        if (res.data.code !== 0) {
          reject(new Error(res.data.message || '请求失败'));
          return;
        }
        resolve(res.data.data);
      },
      fail: (err) => reject(new Error('网络异常')),
    });
  });
}

// === 节目接口 ===

/** 今日节目（不含稿件，首屏加速）。channel_id 可选，用于多频道过滤 */
const fetchTodayEpisode = (channelId) =>
  request({ url: '/episodes/today', data: channelId ? { channel_id: channelId } : {} });

/** 节目详情 */
const fetchEpisodeDetail = (id) => request({ url: '/episodes/' + id });

/** 节目稿件（懒加载） */
const fetchEpisodeScript = (id) => request({ url: '/episodes/' + id + '/script' });

/**
 * 历史列表分页。channel_id 可选，用于按频道过滤
 * 任务7：sort_order 可选 'desc'（默认）/ 'asc'，控制日期正序/倒序
 */
const fetchHistory = (page, size = 20, channelId, sortOrder) => {
  const data = { page, size };
  if (channelId) data.channel_id = channelId;
  if (sortOrder) data.sort_order = sortOrder;
  return request({ url: '/episodes/history', data });
};

/** 节目搜索（按标题模糊匹配） */
const searchEpisodes = (keyword, page = 1, size = 20) =>
  request({ url: '/episodes/search', data: { keyword, page, size } });

// === 播放日志接口 ===

/** 上报播放进度（允许失败，不影响播放） */
const reportPlayProgress = (data) =>
  request({ url: '/playlogs/progress', method: 'POST', data }).catch(() => {});

/** 查询某节目播放进度（断点续播，允许失败）*/
const fetchPlayProgress = (episodeId) =>
  request({ url: '/playlogs/progress/' + episodeId }).catch(() => null);

/** 最近播放记录（按 episode 去重） */
const fetchRecentPlaylogs = (page = 1, size = 20) =>
  request({ url: '/playlogs/recent', data: { page, size } });

// === 收藏接口 ===

/** 收藏列表（后端已 join episode 详情，前端无需再 N+1 拉详情） */
const getFavorites = () => request({ url: '/favorites' });

/** 添加收藏（幂等） */
const addFavorite = (episodeId) =>
  request({ url: '/favorites', method: 'POST', data: { episode_id: episodeId } });

/** 取消收藏（幂等） */
const removeFavorite = (episodeId) =>
  request({ url: '/favorites/' + episodeId, method: 'DELETE' });

/** 检查是否已收藏（详情页按钮态用） */
const checkFavorite = (episodeId) =>
  request({ url: '/favorites/check/' + episodeId }).catch(() => ({ favorited: false }));

// === 反馈接口 ===

/** 提交意见反馈 */
const submitFeedback = (data) =>
  request({ url: '/feedbacks', method: 'POST', data });

// === 评论接口（任务8） ===

/** 获取节目评论列表 */
const fetchComments = (episodeId) =>
  request({ url: '/comments', data: { episode_id: episodeId } }).catch(() => ({ list: [], total: 0 }));

/** 发布评论 */
const postComment = (data) =>
  request({ url: '/comments', method: 'POST', data });

/** 点赞评论（幂等） */
const likeComment = (commentId) =>
  request({ url: '/comments/' + commentId + '/like', method: 'POST' });

/** 取消点赞（幂等） */
const unlikeComment = (commentId) =>
  request({ url: '/comments/' + commentId + '/like', method: 'DELETE' });

// === 频道接口 ===

/** 获取已启用频道列表（带 is_subscribed 字段） */
const fetchChannels = () => request({ url: '/channels' });

// === 订阅接口 ===

/** 记录订阅消息授权（一次性模板） */
const recordSubscribeMessage = (templateId) =>
  request({
    url: '/subscriptions/message',
    method: 'POST',
    data: { template_id: templateId },
  });

/** 订阅频道 */
const subscribeChannel = (channelId) =>
  request({ url: '/subscriptions/channels/' + channelId, method: 'POST' });

/** 取消订阅频道 */
const unsubscribeChannel = (channelId) =>
  request({ url: '/subscriptions/channels/' + channelId, method: 'DELETE' });

// === 用户中心接口 ===

/** 用户统计（累计收听时长/期数/完播数/收藏数） */
const fetchUserStats = () => request({ url: '/users/stats' }).catch(() => null);

/** 更新用户资料（昵称/头像） */
const updateUserProfile = (data) =>
  request({ url: '/users/profile', method: 'PUT', data });

module.exports = {
  request,
  BASE_URL,
  // 节目
  fetchTodayEpisode,
  fetchEpisodeDetail,
  fetchEpisodeScript,
  fetchHistory,
  searchEpisodes,
  // 播放日志
  reportPlayProgress,
  fetchPlayProgress,
  fetchRecentPlaylogs,
  // 收藏
  getFavorites,
  addFavorite,
  removeFavorite,
  checkFavorite,
  // 反馈
  submitFeedback,
  // 评论
  fetchComments,
  postComment,
  likeComment,
  unlikeComment,
  // 频道
  fetchChannels,
  // 订阅
  recordSubscribeMessage,
  subscribeChannel,
  unsubscribeChannel,
  // 用户中心
  fetchUserStats,
  updateUserProfile,
};