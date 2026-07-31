/**
 * 登录鉴权：wx.login → 后端换 token → 本地缓存
 *
 * 静默登录流程：用户无感知，onLaunch 时自动执行
 */
const { request } = require('./api');

const STORAGE_KEY_TOKEN = 'news_token';
const STORAGE_KEY_USER = 'news_user';

// 防止 refreshToken 并发触发多次 wx.login（开发者工具 wx.login 会缓存 code，
// 短时间内多次调用拿到同一 code，后端第二次使用时报 invalid code）
let _refreshingPromise = null;
// 登录冷却时间戳：refreshToken 失败后 30 秒内不再尝试，避免无效 wx.login 浪费 code
// 微信开发者工具 wx.login 在 5 秒内返回相同 code，连续失败会消耗所有可用 code
let _loginCooldownUntil = 0;
const LOGIN_COOLDOWN_MS = 30000;

function getToken() {
  return wx.getStorageSync(STORAGE_KEY_TOKEN);
}

function getUser() {
  return wx.getStorageSync(STORAGE_KEY_USER);
}

function setToken(token, user) {
  wx.setStorageSync(STORAGE_KEY_TOKEN, token);
  wx.setStorageSync(STORAGE_KEY_USER, user);
}

function clearToken() {
  wx.removeStorageSync(STORAGE_KEY_TOKEN);
  wx.removeStorageSync(STORAGE_KEY_USER);
}

/**
 * 检查当前是否在登录冷却期
 * 冷却期内跳过 refreshToken，避免短时间内重复 wx.login 拿到相同 code
 */
function isLoginCoolingDown() {
  return Date.now() < _loginCooldownUntil;
}

/**
 * 登录：wx.login 获取 code → 调后端 /auth/login 换 token
 *
 * 冷却保护：失败后 30 秒内不再尝试，避免短时间内重复 wx.login 拿到相同 code。
 * 微信开发者工具 wx.login 在 5 秒内返回相同 code，code 只能用一次，
 * 连续失败会消耗所有可用 code 并触发 invalid code 错误。
 * @returns {Promise<{token, user}>}
 */
function login() {
  // 冷却期内直接拒绝，避免无效 wx.login 浪费 code
  if (isLoginCoolingDown()) {
    return Promise.reject(new Error('登录冷却中，请稍后重试'));
  }
  return new Promise((resolve, reject) => {
    wx.login({
      success: async (res) => {
        if (!res.code) {
          reject(new Error('wx.login 未返回 code'));
          return;
        }
        // 调后端 /auth/login（用 code 换 token）
        try {
          const data = await request({
            url: '/auth/login',
            method: 'POST',
            data: { code: res.code },
          });
          setToken(data.token, data.user);
          // 登录成功后清除冷却期（若有）
          _loginCooldownUntil = 0;
          resolve(data);
        } catch (err) {
          // 失败后设置冷却期：避免短时间内重复 wx.login 拿到相同 code
          _loginCooldownUntil = Date.now() + LOGIN_COOLDOWN_MS;
          reject(err);
        }
      },
      fail: (err) => {
        // wx.login 本身失败（如网络问题）：同样设置冷却期
        _loginCooldownUntil = Date.now() + LOGIN_COOLDOWN_MS;
        reject(err);
      },
    });
  });
}

/**
 * 刷新 token（401 时自动调用，实际是重新 wx.login）
 *
 * 并发保护：多个请求同时 401 时只触发一次 refreshToken，其余请求复用其结果。
 * 冷却保护：失败后 30 秒内不再尝试，避免短时间内重复 wx.login 拿到相同 code。
 * 避免开发者工具 wx.login 缓存 code 导致的 invalid code 错误。
 */
async function refreshToken() {
  // 冷却期内直接拒绝，避免无效 wx.login 浪费 code
  if (isLoginCoolingDown()) {
    throw new Error('登录冷却中，请稍后重试');
  }
  // 已有刷新在进行：复用同一个 Promise，避免并发 wx.login 拿到相同 code
  if (_refreshingPromise) return _refreshingPromise;
  _refreshingPromise = (async () => {
    try {
      clearToken();
      const { token, user } = await login();
      return { token, user };
    } catch (err) {
      // 失败后设置冷却期：避免短时间内重复 wx.login 拿到相同 code
      _loginCooldownUntil = Date.now() + LOGIN_COOLDOWN_MS;
      throw err;
    } finally {
      // 无论成功失败都清除标记，下次 401 可再触发（但冷却期仍生效）
      _refreshingPromise = null;
    }
  })();
  return _refreshingPromise;
}

/**
 * 登出（调后端注销 token，V1.2 起后端用 SQLite TTLCache 替代 Redis 黑名单）
 */
async function logout() {
  const token = getToken();
  if (token) {
    try {
      await request({ url: '/auth/logout', method: 'POST' });
    } catch (err) {
      // 登出失败也清除本地状态，避免卡在已失效的 token
      console.error('退出登录失败:', err);
    }
  }
  clearToken();
}

module.exports = {
  getToken,
  getUser,
  setToken,
  clearToken,
  login,
  refreshToken,
  logout,
  isLoginCoolingDown,
};
