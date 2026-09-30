/**
 * 后端服务地址自动发现模块
 *
 * 解决问题：硬编码 IP 在切换 WiFi/路由器后失效，导致小程序"网络异常"。
 * 本模块通过设备局域网 IP 推断候选地址并探测，实现零配置真机调试。
 *
 * 候选优先级（去重后并行探测，第一个可达即采用）：
 * 1. 用户手动配置（about 页连点版本号 5 次触发输入框）
 * 2. 上次成功地址（缓存，二次启动加速）
 * 3. localhost / 127.0.0.1（仅开发者工具）
 * 4. 基于设备局域网 IP 推断的同网段常见 IP（.1/.2/.100-.105/.200）
 * 5. Tailscale Funnel 公网域名（真机跨网络兜底）
 *
 * 探测策略：
 * - 复用 GET /episodes/today 接口探测
 * - 并行发起所有候选请求，第一个成功立即返回
 * - 响应必须包含 API code 字段（过滤路由器等非 API 页面）
 */

const STORAGE_KEY_MANUAL = 'manual_api_base_url';
const STORAGE_KEY_LAST_SUCCESS = 'last_success_api_base_url';
const API_PREFIX = '/api/v1';
const HEALTH_PATH = '/episodes/today';
// 局域网地址探测超时：内网响应快，2 秒足够
const PROBE_TIMEOUT_LAN_MS = 2000;
// 公网域名探测超时：Tailscale Funnel 首次连接需 DNS 解析 + TLS 握手 + Funnel 转发，需更长超时
const PROBE_TIMEOUT_WAN_MS = 6000;
// 强制超时上限：比探测超时多 0.5 秒，确保 fail 回调能先执行
const FORCE_TIMEOUT_EXTRA_MS = 500;
// 总超时：需覆盖公网探测时间，至少与单次公网探测超时一致
const DISCOVER_TOTAL_TIMEOUT_MS = 8000;
const DEFAULT_PORT = 8000;

// 生产环境 API 基础地址：Tailscale Funnel 配置了 /news/ 前缀代理到本地 8000 端口
// 实际转发规则：https://desktop-g10o4nl.tailbca47.ts.net/news/* → http://127.0.0.1:8000/*
// 故 API 路径为 /news/api/v1，音频路径为 /news/audio/...
const PROD_API_BASE_URL = 'https://win-20260220ins.tailbca47.ts.net/news/api/v1';
const COMMON_HOST_SUFFIXES = [1, 2, 3, 10, 100, 101, 102, 103, 104, 105, 200];

function isValidBaseUrl(url) {
  // 正则需匹配 http:// 或 https://（两斜杠），原 /\/\// 误写为三斜杠导致所有正常 URL 被判为非法
  if (!url || !/^https?:\/\//i.test(url)) return false;
  const hostname = url.replace(/^https?:\/\//i, '').split(/[:\/]/)[0];
  const ipRegex = /^\d{1,3}(\.\d{1,3}){3}$/;
  const validHosts = ['localhost', '127.0.0.1', '::1'];
  if (validHosts.includes(hostname)) return true;
  if (ipRegex.test(hostname)) {
    const parts = hostname.split('.').map(Number);
    return parts.every(p => p >= 0 && p <= 255);
  }
  // 允许合法域名（如 Tailscale Funnel 公网域名），排除中文等非法字符
  if (/^[a-z0-9.\-]+$/i.test(hostname) && hostname.includes('.')) return true;
  return false;
}

function getManualBaseUrl() {
  try {
    const url = wx.getStorageSync(STORAGE_KEY_MANUAL) || '';
    // 读取时校验：历史可能存入无效占位符（如 "http://请输入.../api/v1"），无效则忽略
    return isValidBaseUrl(url) ? url : '';
  } catch (e) { return ''; }
}
function setManualBaseUrl(url) {
  // 写入前再次校验，防止调用方绕过 normalizeBaseUrl 直接传入非法值
  // 非关键写入（用户手动配置缓存）：改异步避免阻塞主线程，失败仅告警
  if (url && isValidBaseUrl(url)) {
    wx.setStorage({
      key: STORAGE_KEY_MANUAL,
      data: url,
      fail: (e) => console.warn('[server-discovery] manual url 写入失败:', e && e.errMsg),
    });
  } else { wx.removeStorageSync(STORAGE_KEY_MANUAL); }
}
function getLastSuccessBaseUrl() {
  try {
    const url = wx.getStorageSync(STORAGE_KEY_LAST_SUCCESS) || '';
    return isValidBaseUrl(url) ? url : '';
  } catch (e) { return ''; }
}
function setLastSuccessBaseUrl(url) {
  // 非关键写入（上次成功地址缓存）：改异步避免阻塞主线程，失败仅告警
  // 该缓存仅用于二次启动加速，丢失后走完整发现流程，不影响功能
  if (url && isValidBaseUrl(url)) {
    wx.setStorage({
      key: STORAGE_KEY_LAST_SUCCESS,
      data: url,
      fail: (e) => console.warn('[server-discovery] last success url 写入失败:', e && e.errMsg),
    });
  } else { wx.removeStorageSync(STORAGE_KEY_LAST_SUCCESS); }
}

function normalizeBaseUrl(input) {
  if (!input) return '';
  let url = input.trim();
  // 已带 http(s):// 前缀则不再追加，避免出现 http://http://...
  if (!/^https?:\/\//i.test(url)) { url = 'http://' + url; }
  url = url.replace(/\/+$/, '');
  if (!url.endsWith(API_PREFIX)) { url = url + API_PREFIX; }
  // 最终校验：占位符文字（如"请输入..."）包装后会因 hostname 含中文被拒绝
  return isValidBaseUrl(url) ? url : '';
}

function isDevTools() {
  try {
    if (typeof wx.getDeviceInfo === 'function') return wx.getDeviceInfo().platform === 'devtools';
    return wx.getSystemInfoSync().platform === 'devtools';
  } catch (e) { return false; }
}

function getLocalIPAddress() {
  return new Promise((resolve) => {
    if (typeof wx.getLocalIPAddress !== 'function') { resolve(''); return; }
    wx.getLocalIPAddress({ success: (res) => resolve(res.localIP || ''), fail: () => resolve('') });
  });
}

function getCandidatesFromDeviceIP(deviceIP) {
  if (!deviceIP) return [];
  if (deviceIP.startsWith('127.')) return [];
  const parts = deviceIP.split('.');
  if (parts.length !== 4) return [];
  const prefix = parts.slice(0, 3).join('.');
  return COMMON_HOST_SUFFIXES.map(suffix =>
    `http://${prefix}.${suffix}:${DEFAULT_PORT}${API_PREFIX}`
  );
}

/**
 * 从引导地址（Tailscale 公网域名）拉取后端局域网 IP 列表
 *
 * 为什么需要：真机调试模式下 wx.getLocalIPAddress 常失败，无法推断局域网候选。
 * 后端在开发模式的 /api/health 接口返回 lan_ips（所有局域网 IPv4 地址），
 * 小程序从 Tailscale 引导地址拉取后，用这些 IP 构建候选加入探测列表，
 * 实现自动发现，避免弹窗引导用户手动输入。
 *
 * 前提：手机能访问 Tailscale 网络（手机安装了 Tailscale app 并登录同一账号）。
 * Tailscale 不可达时返回空数组，不影响后续探测流程。
 *
 * @param {string} bootstrapUrl - 引导地址（PROD_API_BASE_URL，如 Tailscale 公网域名）
 * @returns {Promise<string[]>} 局域网 IP 数组，失败返回空数组
 */
function fetchLanIpsFromBootstrap(bootstrapUrl) {
  // 从 bootstrapUrl 推导 health 接口 URL
  // PROD_API_BASE_URL 形如 https://*.ts.net/news/api/v1
  // health 接口路径为 /api/health（后端路由），Tailscale 代理 /news/ 前缀
  // 故 healthUrl = bootstrapUrl 去掉 /api/v1 + /api/health
  const healthUrl = bootstrapUrl.replace(/\/api\/v1\/?$/, '') + '/api/health';
  return new Promise((resolve) => {
    wx.request({
      url: healthUrl,
      method: 'GET',
      timeout: 3000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data) {
          try {
            const data = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
            const lanIps = data?.data?.lan_ips;
            if (Array.isArray(lanIps) && lanIps.length > 0) {
              console.warn('[server-discovery] 从引导地址拉取到局域网 IP:', lanIps);
              resolve(lanIps);
              return;
            }
          } catch (e) {
            // JSON 解析失败，忽略
          }
        }
        resolve([]);
      },
      fail: () => resolve([]),
    });
  });
}

function probeCandidate(url) {
  // 公网域名（https）需要更长超时：Tailscale Funnel 涉及 DNS+TLS+转发
  const isWan = url.startsWith('https://');
  const probeTimeout = isWan ? PROBE_TIMEOUT_WAN_MS : PROBE_TIMEOUT_LAN_MS;
  const forceTimeout = probeTimeout + FORCE_TIMEOUT_EXTRA_MS;
  const requestPromise = new Promise((resolve) => {
    wx.request({
      url: url + HEALTH_PATH,
      method: 'GET',
      timeout: probeTimeout,
      success: (res) => {
        // 验证是后端 API 响应（非路由器管理等页面）
        if ((res.statusCode >= 200 && res.statusCode < 300) || res.statusCode === 401) {
          try {
            const data = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
            if (res.statusCode === 401) {
              console.warn('[server-discovery] 探测成功(401):', url);
              resolve(url);
            } else if (data && typeof data.code === "number" && data.data !== null && typeof data.data === "object") {
              console.warn('[server-discovery] 探测成功:', url, '->', res.statusCode, 'code:', data.code);
              resolve(url);
            } else {
              console.warn('[server-discovery] 非 API 响应，跳过:', url, 'statusCode:', res.statusCode);
              resolve(null);
            }
          } catch (e) {
            console.warn('[server-discovery] 非 JSON 响应，跳过:', url);
            resolve(null);
          }
        } else { resolve(null); }
      },
      fail: () => resolve(null),
    });
  });
  const forceTimer = new Promise((resolve) => { setTimeout(() => resolve(null), forceTimeout); });
  return Promise.race([requestPromise, forceTimer]);
}

/**
 * 获取小程序运行版本（T00571）
 *
 * 三层取值，优先官方 API：
 *   1. wx.getAccountInfoSync().miniProgram.envVersion —— 官方公开 API，返回
 *      'develop'（开发版）/ 'trial'（体验版）/ 'release'（正式版）
 *   2. __wxConfig.envVersion —— 历史内部字段，部分新基础库已不暴露
 *   3. '' —— 都取不到（视为未知，调用方按最保守策略处理）
 *
 * 为什么必须换成官方 API：旧的单一 `__wxConfig.envVersion` 判定一旦取不到就恒为
 * false，会把正式版误判成非正式版，进而掉进「弹窗引导手动输入」分支——这正是
 * T00571「正式版启动弹配置后端地址」的根因。
 * @returns {'develop'|'trial'|'release'|''} 运行版本，未知时为空串
 */
function getEnvVersion() {
  try {
    if (typeof wx.getAccountInfoSync === 'function') {
      const info = wx.getAccountInfoSync();
      const version = info && info.miniProgram && info.miniProgram.envVersion;
      if (version) return version;
    }
  } catch (e) {
    // 旧基础库/异常环境下 getAccountInfoSync 可能抛错，继续走回退
  }
  try {
    if (typeof __wxConfig !== 'undefined' && __wxConfig && __wxConfig.envVersion) {
      return __wxConfig.envVersion;
    }
  } catch (e) {
    // ignore
  }
  return '';
}

function isRelease() {
  return getEnvVersion() === 'release';
}

/**
 * 是否「开发模式」——只有开发模式允许弹出「配置后端地址」引导（T00571）
 *
 * 判定口径：
 *   - envVersion === 'develop'（开发版，含真机调试）→ 允许弹窗；
 *   - 开发者工具（platform === 'devtools'）→ 允许弹窗（工具里跑的就是开发版/体验版调测）；
 *   - 其余（trial / release / 版本未知）→ 不允许弹窗，直接用预置兜底地址。
 *
 * 为什么写成「正向判定开发模式」而不是沿用 `!isRelease() && !isDevTools()`
 * 反推：反推式判定在版本信息缺失时会**默认放行**弹窗，生产环境用户就会莫名被弹框；
 * 正向白名单则在信息缺失时默认不弹，符合「生产模式静默走兜底」的预期。
 * @returns {boolean}
 */
function isDevelopMode() {
  return getEnvVersion() === 'develop' || isDevTools();
}

/**
 * 识别真机调试模式：非 release 且非开发者工具
 *
 * 为什么需要单独识别：
 * 真机调试模式下 wx.getLocalIPAddress 可能失败（权限/网络/系统限制），
 * 此时无法自动推断局域网候选地址，而 Tailscale 兜底在真机未加入 Tailscale
 * 网络时不可达，会导致所有请求失败。真机调试模式下应更积极地引导用户
 * 手动输入开发电脑的局域网 IP，而非依赖 Tailscale 兜底。
 */
function isRealDeviceDebug() {
  return !isRelease() && !isDevTools();
}

async function discoverServer() {
  // T00571：非开发模式（正式版 / 体验版 / 版本信息未知）直接返回预置兜底地址——
  // 跳过全部候选探测与「配置后端地址」手动输入弹窗，生产环境零打扰且启动更快。
  //
  // 为什么改成入口正向门控：原实现是「release 早返回 + 真机调试兜底 + 剩余情况弹窗」
  // 三条分支反推出来的，弹窗分支的隐含条件是 `isRelease() || isDevTools()`。
  // 一旦版本判定失效（旧实现仅依赖未公开的 __wxConfig.envVersion，取不到即恒为 false），
  // 生产环境就会落进弹窗分支被莫名打断。改为「只有明确判定为开发模式才进入发现流程」，
  // 版本未知时默认走兜底，取安全侧默认。
  if (!isDevelopMode()) {
    console.warn('[server-discovery] 非开发模式（envVersion=%s）直接使用预置兜底地址:',
      getEnvVersion() || 'unknown', PROD_API_BASE_URL);
    return PROD_API_BASE_URL;
  }
  console.warn('[server-discovery] 开发模式，开始发现后端地址...');
  const candidates = [];
  const seen = new Set();
  function add(url) { if (url && !seen.has(url)) { seen.add(url); candidates.push(url); } }
  const devTools = isDevTools();
  const realDeviceDebug = isRealDeviceDebug();
  console.warn('[server-discovery] 运行环境:', devTools ? '开发者工具' : (realDeviceDebug ? '真机调试' : '真机'));

  add(getManualBaseUrl());
  add(getLastSuccessBaseUrl());
  if (!devTools) { add(PROD_API_BASE_URL); }
  if (devTools) {
    add(`http://127.0.0.1:${DEFAULT_PORT}${API_PREFIX}`);
    add(`http://localhost:${DEFAULT_PORT}${API_PREFIX}`);
  }
  const deviceIP = await getLocalIPAddress();
  console.warn('[server-discovery] 设备局域网 IP:', deviceIP || '(获取失败)');
  // 真机调试模式下 getLocalIPAddress 失败时给出明确的诊断提示
  // 这是真机调试网络异常的最常见根因：无法推断局域网候选，只剩 Tailscale 兜底
  if (realDeviceDebug && !deviceIP) {
    console.warn('[server-discovery] 真机调试模式下获取局域网 IP 失败，尝试从引导地址拉取后端局域网 IP');
  }
  getCandidatesFromDeviceIP(deviceIP).forEach(add);
  if (deviceIP && !deviceIP.startsWith('127.')) {
    const parts = deviceIP.split('.');
    if (parts.length === 4) {
      const prefix = parts.slice(0, 3).join('.');
      [DEFAULT_PORT, 8000, 8080, 3000, 5173].forEach(port => {
        add(`http://${prefix}.1:${port}${API_PREFIX}`);
        add(`http://${prefix}.2:${port}${API_PREFIX}`);
      });
    }
  }

  // 真机调试模式下，从 Tailscale 引导地址拉取后端局域网 IP 列表
  // 解决 wx.getLocalIPAddress 失败导致无法推断局域网候选的问题：
  // 后端 /api/health 在开发模式返回 lan_ips，小程序拉取后用这些 IP 构建候选
  if (realDeviceDebug && !deviceIP && PROD_API_BASE_URL) {
    const lanIps = await fetchLanIpsFromBootstrap(PROD_API_BASE_URL);
    if (lanIps.length > 0) {
      // 用拉取到的局域网 IP 构建候选地址
      // 覆盖常见端口：8000（默认）、8080、3000
      lanIps.forEach(ip => {
        add(`http://${ip}:${DEFAULT_PORT}${API_PREFIX}`);
        add(`http://${ip}:8080${API_PREFIX}`);
      });
      console.warn('[server-discovery] 从引导地址拉取到局域网 IP，已加入候选:', lanIps);
    }
  }

  console.warn(`[server-discovery] 候选地址 ${candidates.length} 个:`, candidates);
  if (candidates.length === 0) {
    const fallback = `http://127.0.0.1:${DEFAULT_PORT}${API_PREFIX}`;
    console.warn('[server-discovery] 无候选地址，使用兜底:', fallback);
    return fallback;
  }
  const discovered = await raceFirstSuccess(candidates, DISCOVER_TOTAL_TIMEOUT_MS);
  if (discovered) {
    console.warn('[server-discovery] 发现后端地址:', discovered);
    setLastSuccessBaseUrl(discovered);
    return discovered;
  }

  // 真机调试模式：探测全部失败后，直接用 Tailscale 公网域名兜底，不弹窗
  // 为什么：Tailscale Funnel 已验证从公网（含手机 4G）可达，探测失败通常是
  // 首次 DNS/TLS 握手慢超时，或局域网候选不可达。直接用 Tailscale 兜底
  // 能让用户无感连接，避免弹窗打扰。
  // 用户若需手动配置，可通过 about 页连点版本号 5 次触发输入框。
  if (realDeviceDebug && PROD_API_BASE_URL) {
    console.warn('[server-discovery] 真机调试模式，探测失败，直接使用 Tailscale 兜底:', PROD_API_BASE_URL);
    setLastSuccessBaseUrl(PROD_API_BASE_URL);
    return PROD_API_BASE_URL;
  }

  // 至此必然是开发模式（入口已用 isDevelopMode 门控）：探测失败后弹窗引导手动输入，
  // 开发场景需要灵活切换后端地址
  console.warn('[server-discovery] 开发模式下自动发现失败，弹窗引导用户手动输入');
  const userInput = await promptManualInput(realDeviceDebug);
  if (userInput && isValidBaseUrl(userInput)) {
    console.warn('[server-discovery] 用户手动输入有效:', userInput);
    const probed = await probeCandidate(userInput);
    if (probed) {
      console.warn('[server-discovery] 用户输入地址探测成功:', userInput);
      wx.removeStorageSync(STORAGE_KEY_MANUAL);
      setLastSuccessBaseUrl(userInput);
      return userInput;
    }
    console.warn('[server-discovery] 用户输入地址探测失败:', userInput);
    wx.showToast({ title: '该地址不可达，请检查 IP 和网络', icon: 'none', duration: 3000 });
    wx.removeStorageSync(STORAGE_KEY_MANUAL);
  }
  // 兜底优先级（开发者工具/其他）：公网域名 > 首个候选地址 > localhost
  const fallback = PROD_API_BASE_URL || candidates[0] || `http://127.0.0.1:${DEFAULT_PORT}${API_PREFIX}`;
  console.warn('[server-discovery] 用户取消或输入无效，使用兜底:', fallback);
  return fallback;
}

function promptManualInput(realDeviceDebug) {
  // wx.showInputBox 仅开发者工具可用，真机不支持。
  // 改用 wx.showModal 的 editable 模式，真机和开发者工具均可用。
  // 真机调试模式下提示更明确：引导用户输入开发电脑局域网 IP，而非公网兜底。
  return new Promise((resolve) => {
    const title = realDeviceDebug ? '配置开发电脑 IP' : '配置后端地址';
    const content = realDeviceDebug
      ? '无法自动发现后端。请输入电脑 WiFi 网卡 IP:端口\n如 192.168.1.65:8000\n（手机与电脑需在同一 WiFi；电脑多网卡时选 WiFi 网卡 IP）'
      : '自动探测失败。留空使用公网兜底，或输入电脑 IP:端口\n如 192.168.1.65:8000';
    wx.showModal({
      title,
      content,
      editable: true,
      placeholderText: '192.168.1.65:8000',
      confirmText: '保存',
      cancelText: '用兜底',
      success: (res) => {
        if (!res.confirm) {
          console.warn('[server-discovery] 用户取消手动输入，将使用兜底');
          resolve(null);
          return;
        }
        const input = (res.content || '').trim();
        if (!input) {
          // 用户确认但留空：使用兜底
          resolve(null);
          return;
        }
        const normalized = normalizeBaseUrl(input);
        if (normalized && isValidBaseUrl(normalized)) {
          resolve(normalized);
        } else {
          console.warn('[server-discovery] 用户输入无效:', input);
          wx.showToast({ title: '地址格式无效，使用兜底', icon: 'none' });
          resolve(null);
        }
      },
      fail: () => resolve(null),
    });
  });
}

function raceFirstSuccess(candidates, totalTimeoutMs) {
  return new Promise((resolve) => {
    let resolved = false;
    let remaining = candidates.length;
    const totalTimer = setTimeout(() => {
      if (!resolved) { resolved = true; console.warn(`[server-discovery] 总超时 ${totalTimeoutMs}ms 到达`); resolve(null); }
    }, totalTimeoutMs);
    candidates.forEach((url) => {
      probeCandidate(url).then((result) => {
        if (resolved) return;
        if (result) { resolved = true; clearTimeout(totalTimer); resolve(result); }
        else {
          remaining--;
          if (remaining === 0) { resolved = true; clearTimeout(totalTimer); resolve(null); }
        }
      });
    });
  });
}

module.exports = {
  discoverServer,
  getManualBaseUrl,
  setManualBaseUrl,
  getLastSuccessBaseUrl,
  normalizeBaseUrl,
  isValidBaseUrl,
  PROD_API_BASE_URL,
  isRelease,
  isDevTools,
  // T00571：版本判定与「是否开发模式」导出，供单测锁定弹窗门控口径
  getEnvVersion,
  isDevelopMode,
};
