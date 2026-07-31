/**
 * 剪贴板复制工具：封装 wx.setClipboardData，提供可测试的纯逻辑接口
 *
 * 抽离为独立模块的原因：
 * 1. detail 与 webview 两个页面均需复制来源链接，逻辑重复
 * 2. Page 内方法难以直接单元测试，独立模块可用 mock wx 进行测试
 * 3. 统一处理复制失败兜底，避免各页面各自实现导致行为不一致
 */

/**
 * 确保隐私授权已同意
 *
 * 为什么需要：wx.setClipboardData 属于隐私接口，用户未同意隐私协议时会直接 fail
 * （errCode: 104）。app.js checkPrivacy 已在 onLaunch 同步注册 onNeedPrivacyAuthorization，
 * 此函数调 requirePrivacyAuthorize 触发隐私弹窗，用户同意后继续复制。
 *
 * @returns {Promise<boolean>} 是否已获授权（false 表示用户拒绝或 API 不可用）
 */
function ensurePrivacyAuthorized() {
  const app = typeof getApp === 'function' ? getApp() : null;
  if (app && app.globalData && app.globalData.privacyAuthorized) {
    return Promise.resolve(true);
  }
  // 旧版基础库无 requirePrivacyAuthorize：直接放行由 setClipboardData 自行处理
  if (typeof wx.requirePrivacyAuthorize !== 'function') {
    return Promise.resolve(true);
  }
  return new Promise((resolve) => {
    wx.requirePrivacyAuthorize({
      success: () => {
        if (app && app.globalData) app.globalData.privacyAuthorized = true;
        resolve(true);
      },
      fail: () => resolve(false),
    });
  });
}

/**
 * 单次写入剪贴板（不重试）
 * @param {string} text 待复制文本
 * @returns {Promise<boolean>} 成功返回 true，失败返回 false
 */
function _setClipboardOnce(text) {
  return new Promise((resolve) => {
    wx.setClipboardData({
      data: text,
      success: () => resolve(true),
      fail: (err) => {
        // 记录 errCode 辅助诊断：104=隐私未授权，其他=系统异常
        console.warn('[clipboard] setClipboardData fail:', err && err.errCode, err && err.errMsg);
        resolve(false);
      },
    });
  });
}

/**
 * 将文本写入系统剪贴板
 *
 * 复制失败根因与处理（三阶段重试）：
 * 1. 先直接尝试复制 — 已授权场景一步成功，省去 requirePrivacyAuthorize 开销
 * 2. 首次失败后调 ensurePrivacyAuthorized — 触发隐私弹窗引导用户同意，
 *    授权后延迟 200ms 重试（等待基础库内部授权状态生效）
 * 3. 仍失败则延迟 500ms 最后重试 — 覆盖授权刚同意的瞬态竞态
 *
 * 为什么先复制而非先检查授权：
 * - 已授权用户占多数，直接复制省一次 RTT
 * - 部分基础库版本 setClipboardData 不视为隐私接口，直接复制即可成功
 * - ensurePrivacyAuthorized 预检查无法保证 setClipboardData 时授权状态仍有效（竞态），
 *   先复制 + 失败后授权更可靠
 *
 * @param {string} text 待复制文本
 * @returns {Promise<boolean>} 成功返回 true，失败返回 false（不抛错，便于调用方兜底）
 */
async function copyText(text) {
  // 1. 先直接尝试复制（已授权场景一步成功，省去授权检查开销）
  if (await _setClipboardOnce(text)) return true;

  // 2. 首次失败：可能是隐私授权未同意（errCode:104），主动触发授权弹窗
  // app.js onLaunch 已同步注册 onNeedPrivacyAuthorization，此处会弹隐私协议弹窗
  await ensurePrivacyAuthorized();

  // 3. 授权后重试（延迟 200ms 等待授权状态在基础库内部生效）
  await new Promise((r) => setTimeout(r, 200));
  if (await _setClipboardOnce(text)) return true;

  // 4. 仍失败：延迟 500ms 再试一次（覆盖授权刚同意的瞬态竞态）
  await new Promise((r) => setTimeout(r, 500));
  return _setClipboardOnce(text);
}

/**
 * 复制节目来源链接并引导用户在浏览器打开
 *
 * 设计说明：
 * - 复制成功 → 弹 modal 引导用户去浏览器粘贴打开
 *   （不使用 wx.showToast，因 wx.setClipboardData 成功后微信会自动弹"内容已复制"toast，
 *    再叠加 toast 会冲突；用 modal 给出更明确的下一步指引）
 * - 复制失败 → 跳转 webview 页的 fallback 界面展示链接文本，
 *   用户可长按链接手动复制（user-select:text 已在 webview.wxss 配置）
 *   （不弹 toast 了事，因 toast 消失后用户无从获取链接，等于功能完全不可用）
 *
 * @param {string} url 节目来源原文链接
 * @returns {Promise<boolean>} 是否复制成功
 */
async function copySourceUrl(url) {
  const ok = await copyText(url);
  if (ok) {
    wx.showModal({
      title: '链接已复制',
      content: '节目来源链接已复制到剪贴板，请到浏览器粘贴打开查看原文。',
      showCancel: false,
      confirmText: '我知道了',
      confirmColor: '#5BA89B',
    });
    return true;
  }
  // 复制失败（可能是隐私授权未同意或系统异常）：跳转 fallback 页展示链接供手动复制
  // fallback=1 使 webview 页跳过 web-view 加载直接显示兜底界面，避免微信原生"无法打开该页面"拦截
  const encoded = encodeURIComponent(url);
  wx.navigateTo({
    url: `/pages/webview/webview?url=${encoded}&fallback=1`,
  });
  return false;
}

module.exports = { copyText, copySourceUrl, ensurePrivacyAuthorized };
