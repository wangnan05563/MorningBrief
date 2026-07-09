/**
 * API 封装：token 注入、401 自动重登、统一响应格式处理
 *
 * 所有接口均返回 Promise，成功时 resolve(data)，失败时 reject(Error)
 */

// 按环境切换 BASE_URL：release 为正式版编译产物，其余（develop/trial）走开发环境
const BASE_URL = (typeof __wxConfig !== 'undefined' && __wxConfig.envVersion === 'release')
  ? 'https://api.example.com/api/v1'  // 生产环境域名（部署时替换）
  : 'http://localhost:8000/api/v1';   // 开发环境

/**
 * 统一请求函数
 * @param {Object} options - { url, method, data, header }
 * @returns {Promise<any>} - resolve(data) 或 reject(Error)
 */
function request(options) {
  const { url, method = 'GET', data, header = {} } = options;

  // 延迟 require 避免循环依赖：auth.js 加载时需要 request，若在顶部 require 会拿不到 getToken
  const { getToken, refreshToken } = require('./auth');

  // 注入 token
  const token = getToken();
  if (token) {
    header.Authorization = `Bearer ${token}`;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + url,
      method,
      data,
      header: { 'Content-Type': 'application/json', ...header },
      success: async (res) => {
        // 401 自动重登一次（避免用户感知 token 失效）
        if (res.statusCode === 401) {
          try {
            await refreshToken();
            // 重试原请求
            const retry = await request(options);
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

// === 各接口封装 ===

/** 今日节目（不含稿件，首屏加速） */
const fetchTodayEpisode = () => request({ url: '/episodes/today' });

/** 节目详情 */
const fetchEpisodeDetail = (id) => request({ url: `/episodes/${id}` });

/** 节目稿件（懒加载） */
const fetchEpisodeScript = (id) => request({ url: `/episodes/${id}/script` });

/** 历史列表分页 */
const fetchHistory = (page, size = 20) =>
  request({ url: '/episodes/history', data: { page, size } });

/** 上报播放进度 */
const reportPlayProgress = (data) =>
  request({ url: '/playlogs/progress', method: 'POST', data });

/** 查询某节目播放进度（断点续播） */
const fetchPlayProgress = (episodeId) =>
  request({ url: `/playlogs/progress/${episodeId}` });

module.exports = {
  request,
  fetchTodayEpisode,
  fetchEpisodeDetail,
  fetchEpisodeScript,
  fetchHistory,
  reportPlayProgress,
  fetchPlayProgress,
};
