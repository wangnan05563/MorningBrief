/**
 * 登录鉴权：wx.login → 后端换 token → 本地缓存
 *
 * 静默登录流程：用户无感知，onLaunch 时自动执行
 */
const { request } = require('./api');

const STORAGE_KEY_TOKEN = 'news_token';
const STORAGE_KEY_USER = 'news_user';

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
 * 登录：wx.login 获取 code → 调后端 /auth/login 换 token
 * @returns {Promise<{token, user}>}
 */
function login() {
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
          resolve(data);
        } catch (err) {
          reject(err);
        }
      },
      fail: (err) => reject(err),
    });
  });
}

/**
 * 刷新 token（401 时自动调用，实际是重新 wx.login）
 */
async function refreshToken() {
  clearToken();
  const { token, user } = await login();
  return { token, user };
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
};
