/**
 * API 封装：token 注入、401 自动重登、统一响应格式处理
 *
 * V1.4 性能优化：
 * - 请求超时：wx.request 显式传 timeout: 10000，fail 中识别 timeout
 * - inflight 去重：相同 method+url+data 的并发请求复用同一 Promise（避免短时间重复请求）
 * - TTL 缓存层：GET 请求可选 { cache: true, cacheTTL: 60 }，命中缓存直接 resolve
 * - 网络异常重试：fail 时（非业务错误）指数退避重试 1 次（间隔 1s）
 *
 * 所有接口均返回 Promise，成功时 resolve(data)，失败时 reject(Error)
 */

const { PROD_API_BASE_URL, isRelease } = require('../utils/server-discovery');

// 按编译环境切换 API 域名：release 为正式版编译产物，其余（develop/trial）走开发环境
// 真机测试时需确保手机与电脑在同一局域网，后端服务可被手机访问
const IS_RELEASE = isRelease();

// 模块级 inflight 请求 Map：key -> Promise
// 用途：相同 method+url+data 的并发请求复用同一 Promise，避免短时间重复发请求
// 典型场景：首页 onLoad 预渲染 + initData 同时调 fetchTodayEpisode，去重后只发一次
const _inflightMap = new Map();

// 模块级响应缓存 Map：key -> { data, expiresAt }
// 用途：GET 请求结果按 TTL 缓存，减少弱网/频繁切换时的请求量
const _cacheMap = new Map();

// 模块级节流 Map：key -> { promise, expiresAt }
// 用途：相同 key 的请求在 ttl 时间窗内复用同一 Promise，避免 tab 切换等场景短时间重复发请求
// 与 cache 的语义区别：cache 命中后立即返回缓存数据，throttle 命中后等待同一 Promise 完成
const _throttleMap = new Map();

// 请求默认超时：10 秒覆盖大部分正常请求，弱网下避免无限等待卡死 UI
const REQUEST_TIMEOUT_MS = 10000;
// 网络异常重试间隔：1 秒（指数退避首次间隔）
const NETWORK_RETRY_DELAY_MS = 1000;

// 开发环境兜底地址（仅作为 getBaseUrl() 无法读取 globalData 时的回退）
// 实际地址由 app.js onLaunch 调用 discoverServer() 自动发现后注入 globalData.baseUrl
const DEV_FALLBACK_BASE_URL = 'http://127.0.0.1:8000/api/v1';

/**
 * 获取当前生效的 API 基础地址
 *
 * 动态读取 globalData.baseUrl（由 app.js 启动时通过 discoverServer() 注入），
 * 避免硬编码 IP 在切换 WiFi/路由器后失效。
 *
 * release 版本：使用生产域名常量（Tailscale Funnel 公网地址）
 * develop/trial：优先用 globalData.baseUrl（自动发现），兜底用 localhost
 */
function getBaseUrl() {
  if (IS_RELEASE && PROD_API_BASE_URL) return PROD_API_BASE_URL;
  try {
    const app = getApp();
    if (app && app.globalData && app.globalData.baseUrl) {
      return app.globalData.baseUrl;
    }
  } catch (e) {
    // getApp() 在 App 还未初始化时返回 undefined，忽略并走兜底
  }
  return DEV_FALLBACK_BASE_URL;
}

/**
 * 构造请求缓存/inflight key
 * key 包含 method+url+data，确保不同参数的请求不会互相命中
 * JSON.stringify 在小程序环境中足够稳定：同一调用方构造的对象属性顺序一致
 */
function _buildKey(method, url, data) {
  const dataStr = data ? JSON.stringify(data) : '';
  return method + ' ' + url + ' ' + dataStr;
}

/**
 * 节流封装：相同 key 的请求在 ttl 时间窗内复用同一 Promise
 *
 * 用途：onShow、tab 切换等频繁触发的场景下，避免短时间内重复请求同一接口
 * 与 cache 的区别：cache 命中后立即返回缓存数据，throttle 命中后等待同一 Promise 完成
 *
 * @param {string} key - 节流 key（通常为接口名+参数）
 * @param {number} ttl - 节流时间窗（毫秒）
 * @param {Function} fn - 实际发起请求的函数，返回 Promise
 * @returns {Promise} ttl 内返回缓存的 Promise，过期后重新调用 fn
 */
function throttle(key, ttl, fn) {
  const entry = _throttleMap.get(key);
  const now = Date.now();
  if (entry && entry.expiresAt > now) {
    return entry.promise;
  }
  if (entry) _throttleMap.delete(key);
  // 用 Promise.resolve().then 包一层，确保 fn 异常也能被 catch 捕获并清理缓存
  const promise = Promise.resolve().then(() => fn()).catch((err) => {
    // 失败时立即清理，让下次调用能重试，避免失败结果被节流缓存
    _throttleMap.delete(key);
    throw err;
  });
  _throttleMap.set(key, { promise, expiresAt: now + ttl });
  return promise;
}

/**
 * 统一请求函数（入口）
 * @param {Object} options - { url, method, data, header, _retried, cache, cacheTTL, _allowRetry }
 * @returns {Promise<any>} - resolve(data) 或 reject(Error)
 *
 * 三层加速策略（按优先级）：
 * 1. 缓存命中：GET 且 cache=true 且非重试请求，直接 resolve 缓存数据
 * 2. inflight 去重：相同 method+url+data 的并发请求复用同一 Promise
 * 3. 实际发起：调用 _rawRequest，包含 401 重试 + 网络异常重试
 *
 * 缓存只对 GET 且非 _retried 请求生效：
 * - 重试请求是因之前失败，不应读缓存（缓存里没有或就是失败前的旧值）
 * - POST/PUT/DELETE 不缓存（写操作需实时生效）
 *
 * 401 重试保护：
 * - /auth/login 请求本身不触发 401 重试（否则 login -> 401 -> refreshToken -> login 无限循环）
 * - 其他请求 401 时仅重试一次（_retried 标记防止 token 仍无效时无限递归）
 */
function request(options) {
  const { url, method = 'GET', data, _retried = false, cache = false, cacheTTL = 60 } = options;

  // 1. 缓存命中检查：仅 GET 且 cache=true 且非重试请求
  // 重试请求不走缓存：避免读到失败前的旧值或与正在 inflight 的原请求冲突
  if (cache && method === 'GET' && !_retried) {
    const cacheKey = _buildKey(method, url, data);
    const cached = _cacheMap.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      return Promise.resolve(cached.data);
    }
    // 过期缓存清理，避免 Map 无限增长
    if (cached) _cacheMap.delete(cacheKey);
  }

  // 2. inflight 去重：相同 method+url+data 的并发请求复用同一 Promise
  // key 追加 [retry] 标记：让 401 重试请求与原请求使用不同 key，
  // 否则重试请求会命中原请求的 inflight Promise 导致无限递归
  const inflightKey = _buildKey(method, url, data) + (_retried ? ' [retry]' : '');
  const existing = _inflightMap.get(inflightKey);
  if (existing) return existing;

  const promise = _rawRequest(options).then(
    (result) => {
      _inflightMap.delete(inflightKey);
      // 写入缓存：仅 GET 且 cache=true 且非重试请求
      // 重试请求不写缓存：避免缓存被重试结果污染（重试可能因 token 失效拿到不同结果）
      if (cache && method === 'GET' && !_retried) {
        const cacheKey = _buildKey(method, url, data);
        _cacheMap.set(cacheKey, { data: result, expiresAt: Date.now() + cacheTTL * 1000 });
      }
      return result;
    },
    (err) => {
      _inflightMap.delete(inflightKey);
      throw err;
    }
  );

  _inflightMap.set(inflightKey, promise);
  return promise;
}

/**
 * 实际发起 wx.request 的内部函数（不含缓存/inflight 去重）
 * 保留原 401 自动重登逻辑，新增 10s 超时 + 网络异常重试 1 次
 *
 * 网络异常重试直接调 _rawRequest 而非 request：
 * 重试是同一请求的延续，不应与其他并发请求共享 inflight 去重，
 * 否则会与原请求的 inflight Promise 冲突导致无限递归
 */
function _rawRequest(options) {
  const { url, method = 'GET', data, header = {}, _retried = false, _netRetried = false } = options;

  // 延迟 require 避免循环依赖：auth.js 加载时需要 request，若在顶部 require 会拿不到 getToken
  const { getToken, refreshToken } = require('./auth');

  // 注入 token
  const token = getToken();
  if (token) {
    header.Authorization = 'Bearer ' + token;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: getBaseUrl() + url,
      method,
      data,
      header: { 'Content-Type': 'application/json', ...header },
      timeout: REQUEST_TIMEOUT_MS,
      success: async (res) => {
        // 401 自动重登一次：排除登录接口本身、且仅重试一次、且请求允许重试
        // 进度上报/播放进度查询已放开 _allowRetry 限制，auth.js 的并发+冷却保护
        // 可防止频繁 login，无需在调用方层面禁用重试
        if (res.statusCode === 401 && !url.startsWith('/auth/') && !_retried && options._allowRetry !== false) {
          try {
            await refreshToken();
            // 重试原请求走 request 入口：享受 inflight 去重（多个并发 401 复用同一 retry Promise）
            // _retried=true 标记防止再次进入 401 分支
            const retry = await request({ ...options, _retried: true });
            resolve(retry);
          } catch (e) {
            console.error('刷新 token 失败:', e);
            // 登录失败时给出更准确的错误信息，便于排查
            reject(new Error('登录失败，部分功能不可用'));
          }
          return;
        }
        // 401 但已重试过或本身就是登录接口或请求不允许重试：直接走错误分支
        if (res.statusCode === 401) {
          reject(new Error('未登录'));
          return;
        }
        // 响应体可能为空（如网络中断后返回空 body），防御性检查避免 TypeError
        const resData = res.data || {};
        // 业务错误（code != 0）
        if (resData.code !== 0) {
          reject(new Error(resData.message || '请求失败'));
          return;
        }
        resolve(resData.data);
      },
      fail: (err) => {
        // 网络异常重试：仅对非业务错误（fail 回调）重试 1 次，指数退避 1s
        // _netRetried 标记防止重试无限递归；业务错误（success 中 code!=0）不重试
        if (!_netRetried) {
          setTimeout(() => {
            // 直接调 _rawRequest 绕过 request 的 inflight 去重：
            // 重试是原请求的延续，复用原请求的 inflight Promise 即可
            _rawRequest({ ...options, _netRetried: true }).then(resolve, reject);
          }, NETWORK_RETRY_DELAY_MS);
          return;
        }
        // 识别超时：wx.request timeout 时 errMsg 包含 "timeout" 字样
        const isTimeout = err && err.errMsg && err.errMsg.indexOf('timeout') !== -1;
        reject(new Error(isTimeout ? '请求超时' : '网络异常'));
      },
    });
  });
}

// === 节目接口 ===

/** 今日节目（不含稿件，首屏加速）。channel_id 可选，用于多频道过滤
 * 60s 缓存：首页 onLoad 预渲染 + initData + 下拉刷新短时间内可能多次调用，
 * 缓存避免重复请求；节目发布后变更频率低，60s 足够新鲜
 * 30s 节流：与 cache 配合，cache 走数据缓存，throttle 走请求去重，
 * 避免频首切换/下拉刷新等短时间内重复发请求
 */
const fetchTodayEpisode = (channelId) =>
  throttle('today_episode_' + (channelId || 'all'), 30000, () =>
    request({
      url: '/episodes/today',
      data: channelId ? { channel_id: channelId } : {},
      cache: true,
      cacheTTL: 60,
    })
  );

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

/** 上报播放进度（允许失败，不影响播放）
 * 不放 _allowRetry=false：token 过期时也需要触发 refreshToken，
 * 否则进度上报持续 401 且永远不会恢复（auth.js 已有并发+冷却保护，不会频繁 login） */
const reportPlayProgress = (data) =>
  request({ url: '/playlogs/progress', method: 'POST', data }).catch(() => {});

/** 查询某节目播放进度（断点续播，允许失败）
 * 不放 _allowRetry=false：与 reportPlayProgress 同理，token 过期时需能触发 refreshToken */
const fetchPlayProgress = (episodeId) =>
  request({ url: '/playlogs/progress/' + episodeId }).catch(() => null);

/** 最近播放记录（按 episode 去重；首页展示用，401 时不重试避免刷屏 invalid code）
 * 30s 节流 + 30s 缓存：throttle 保证 tab 切换短时间内不重复发请求，
 * cache 进一步在节流窗口内命中已缓存数据，双重保险减少后端压力
 */
const fetchRecentPlaylogs = (page = 1, size = 20) =>
  throttle('recent_playlogs_' + page + '_' + size, 30000, () =>
    request({
      url: '/playlogs/recent',
      data: { page, size },
      _allowRetry: false,
      cache: true,
      cacheTTL: 30,
    })
  );

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

/** 获取已启用频道列表（带 is_subscribed 字段）
 * 60s 缓存 + 30s 节流：频道列表极少变化，首页 onLoad + 切换频道胶囊可能多次调用，
 * cache 走数据缓存，throttle 走请求去重，避免 tab 切换短时间内重复请求
 */
const fetchChannels = () =>
  throttle('channels', 30000, () =>
    request({ url: '/channels', cache: true, cacheTTL: 60 })
  );

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

/**
 * 向后端申请 COS 上传预签名凭证（C 端）
 *
 * COS 未配置时后端返回 { cos_enabled: false }，本函数返回 null，
 * 调用方据此回退到后端代理上传（legacyUploadAvatar）。
 *
 * @param {{ filename: string, content_type?: string }} data
 * @returns {Promise<Object|null>} { cos_enabled, upload_url, object_url, key, content_type } 或 null
 */
const presignCosUpload = (data) =>
  request({ url: '/cos/presign-upload', method: 'POST', data }).catch(() => null);

/**
 * 把本地临时文件直传到 COS（PUT 预签名 URL）
 *
 * 微信 wx.uploadFile 仅支持 POST，无法直接 PUT 预签名 URL，故用
 * wx.getFileSystemManager().readFile 读出 ArrayBuffer，再 wx.request PUT。
 * COS 预签名 URL 自带鉴权，无需额外 token。
 *
 * @param {string} filePath 本地临时路径（wxfile://tmp_xxx）
 * @param {string} uploadUrl PUT 预签名 URL
 * @param {string} contentType 上传 Content-Type（COS 未签入签名，可自由带）
 * @returns {Promise<void>} 成功 resolve；失败 reject（由调用方决定回退）
 */
function putFileToCos(filePath, uploadUrl, contentType) {
  return new Promise((resolve, reject) => {
    const fs = wx.getFileSystemManager();
    fs.readFile({
      filePath,
      success: (readRes) => {
        wx.request({
          url: uploadUrl,
          method: 'PUT',
          data: readRes.data, // ArrayBuffer
          header: { 'Content-Type': contentType || 'image/jpeg' },
          timeout: REQUEST_TIMEOUT_MS,
          success: (res) => {
            // COS PUT 成功返回 200（body 为空或 XML）
            if (res.statusCode >= 200 && res.statusCode < 300) {
              resolve();
            } else {
              reject(new Error('COS 上传失败: HTTP ' + res.statusCode));
            }
          },
          fail: (err) => reject(new Error((err && err.errMsg) || 'COS 上传失败')),
        });
      },
      fail: (err) => reject(new Error((err && err.errMsg) || '读取头像文件失败')),
    });
  });
}

/**
 * 从临时路径推断一个合法图片文件名（仅用于后端扩展名白名单校验）
 * wx.chooseAvatar 返回的临时路径通常无扩展名，回退为 .jpg。
 */
function _cosFileName(filePath) {
  const m = /\.(jpg|jpeg|png|webp|gif)$/i.exec(filePath || '');
  return m ? 'avatar' + m[1].toLowerCase() : 'avatar.jpg';
}

/**
 * 旧路径：头像经后端代理上传到 data/avatars 磁盘，返回可访问完整 URL
 *
 * @param {string} filePath 本地临时路径
 * @param {string} hostRoot 后端 host root（去掉 /api/v1）
 * @param {string} token 登录 token（Bearer）
 * @returns {Promise<string>} 头像完整 URL（如 http://host/avatars/1_1740000000.jpg）
 */
function legacyUploadAvatar(filePath, hostRoot, token) {
  const url = hostRoot + '/api/v1/users/avatar';
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url,
      filePath,
      name: 'file',
      header: {
        Authorization: 'Bearer ' + (token || ''),
      },
      success: (res) => {
        try {
          const body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
          if (body && body.code === 0 && body.data && body.data.url) {
            resolve(hostRoot + body.data.url);
          } else {
            reject(new Error((body && body.message) || '头像上传失败'));
          }
        } catch (e) {
          reject(new Error('头像上传响应解析失败'));
        }
      },
      fail: (err) => reject(new Error((err && err.errMsg) || '头像上传失败')),
    });
  });
}

/**
 * 上传用户头像，返回可访问的完整 URL
 *
 * 优先走 COS 直传（流量不经后端磁盘代理）：
 *   1. 向后端申请 PUT 预签名 URL（COS 已配置时）
 *   2. 小程序读文件二进制 PUT 直传到 COS
 *   3. 上传成功返回 COS/CDN 公开直链 object_url
 *
 * 以下情况回退到后端代理上传（legacyUploadAvatar，保证功能不中断）：
 *   - COS 未配置（后端返回 cos_enabled=false）
 *   - 预签名申请失败 / 直传失败（网络抖动等）
 *
 * @param {string} filePath - wx.chooseAvatar 返回的临时文件路径（wxfile://tmp_xxx）
 * @returns {Promise<string>} 头像完整 URL
 */
function uploadAvatar(filePath) {
  // 延迟 require：api.js 加载时 auth 模块可能尚未就绪，运行时再拿 getToken
  const { getToken } = require('./auth');
  const hostRoot = getBaseUrl().replace(/\/api\/v1\/?$/, '');
  const token = getToken() || '';

  return (async () => {
    // 1) 申请 COS 预签名（COS 未配置时返回 null -> 直接走回退）
    let ticket = null;
    try {
      ticket = await presignCosUpload({
        filename: _cosFileName(filePath),
        content_type: 'image/jpeg',
      });
    } catch (e) {
      ticket = null;
    }

    // 2) COS 直传（仅当后端声明已配置且返回了上传 URL）
    if (ticket && ticket.cos_enabled && ticket.upload_url) {
      try {
        await putFileToCos(
          filePath,
          ticket.upload_url,
          ticket.content_type || 'image/jpeg'
        );
        // 上传成功后返回公开可访问地址（CDN/cos 直链）
        if (ticket.object_url) return ticket.object_url;
      } catch (e) {
        console.warn('COS 直传失败，回退后端代理上传:', e);
      }
    }

    // 3) 回退：后端代理上传（旧路径，开发态/未配置 COS 时使用）
    return legacyUploadAvatar(filePath, hostRoot, token);
  })();
}


module.exports = {
  request,
  getBaseUrl,
  throttle,
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
  uploadAvatar,
};