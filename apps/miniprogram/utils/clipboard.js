/**
 * 剪贴板复制工具：封装 wx.setClipboardData，提供可测试的纯逻辑接口
 *
 * 抽离为独立模块的原因：
 * 1. detail 与 webview 两个页面均需复制来源链接，逻辑重复
 * 2. Page 内方法难以直接单元测试，独立模块可用 mock wx 进行测试
 * 3. 统一处理复制失败兜底，避免各页面各自实现导致行为不一致
 *
 * ⚠️ T00618 关键约束（微信强制，此前实现踩坑）：
 * `wx.setClipboardData` **必须在用户手势的同步调用链内发起**——由 bindtap/bindlongpress
 * 直接或同步链式调用；在 `await`/`setTimeout`/网络回调之后再调用会被拒绝（表现就是"复制失败"）。
 * 旧实现「先 await requirePrivacyAuthorize → 授权后再复制 / 延迟 300ms 重试」恰好把所有调用
 * 都挪到了手势链之外，因此**已授权照样失败**；延迟重试还会掩盖真实原因。
 *
 * 正确策略：
 * 1. **同步直接复制**（不 await 任何前置条件）——已授权场景一步成功；
 * 2. 失败且属隐私未授权（errCode 104 / api scope is not declared）时，把"复制"登记为
 *    **授权后动作**（app.registerPostPrivacyAction）并触发一次授权弹窗；
 *    用户点官方 `<button open-type="agreePrivacyAuthorization">`「同意并继续」时，
 *    框架回调本身处于该按钮的手势链内 → 立刻同步执行登记的复制动作 → 成功；
 * 3. 用户拒绝 / 动作再次失败 → 返回 false，由调用方给**可操作**的兜底（长按文本手动复制）。
 */

/**
 * 判断是否为"隐私未授权/未声明"类失败（可经授权流程解决）
 * 104 = 隐私未授权；文案含 privacy agreement/scope = 后台未声明该隐私类型
 */
function isPrivacyFailure(err) {
  if (!err) return false;
  const code = err.errCode ?? err.errno;
  const msg = String(err.errMsg || '');
  return code === 104 || /privacy|scope is not declared/i.test(msg);
}

/**
 * 单次写入剪贴板（不重试）
 * @param {string} text 待复制文本
 * @returns {Promise<{ok: boolean, err?: object}>} 结果与原始错误（供上方判定是否属隐私类失败）
 */
function _setClipboardOnce(text) {
  return new Promise((resolve) => {
    wx.setClipboardData({
      data: text,
      success: () => resolve({ ok: true }),
      fail: (err) => {
        // 记录 errCode 辅助诊断：104=隐私未授权；scope 未声明=后台缺「剪切板」声明
        console.warn('[clipboard] setClipboardData fail:', err && err.errCode, err && err.errMsg);
        resolve({ ok: false, err });
      },
    });
  });
}

/**
 * 确保隐私授权已同意（仅在"同步复制失败且判定为隐私原因"后才调用）
 * @returns {Promise<boolean>} 是否已获授权
 */
function ensurePrivacyAuthorized() {
  const app = typeof getApp === 'function' ? getApp() : null;
  if (app && app.globalData && app.globalData.privacyAuthorized) {
    return Promise.resolve(true);
  }
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
 * 复制文本（手势安全的隐私授权流程）
 *
 * @param {string} text 待复制文本
 * @returns {Promise<boolean>} 成功 true；失败 false（不抛错，调用方负责兜底提示）
 */
async function copyText(text) {
  const app = typeof getApp === 'function' ? getApp() : null;
  if (!text) return false;

  // 1) 同步复制（仍在本次点击的手势链内）
  const first = await _setClipboardOnce(text);
  if (first.ok) return true;

  // 系统异常（非隐私原因）：再授权也解决不了，直接失败，避免无意义弹窗
  if (!isPrivacyFailure(first.err)) return false;

  // 2) 隐私未授权/未声明 → 登记"授权后复制"并弹一次隐私授权（官方按钮手势链会执行该动作）
  if (!app || typeof app.registerPostPrivacyAction !== 'function') return false;
  const viaAction = app.registerPostPrivacyAction(() => _setClipboardOnce(text).then((r) => r.ok));
  const agreed = await ensurePrivacyAuthorized();
  if (!agreed) {
    if (app.clearPostPrivacyActions) app.clearPostPrivacyActions();
    return false;
  }
  // 3) 授权流程已结束：动作已在官方「同意并继续」按钮的手势链内执行，这里等它的结果。
  //    注意：**不能**在这里再发起新的复制调用（已脱离手势链会被微信拒绝）。
  return !!(await viaAction);
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
      confirmColor: '#3F6C8F',
    });
    return true;
  }
  // 复制失败（隐私未授权 / 后台未声明剪切板 / 系统异常）：跳转 fallback 页展示链接供手动复制
  const encoded = encodeURIComponent(url);
  wx.navigateTo({
    url: `/pages/webview/webview?url=${encoded}&fallback=1`,
  });
  return false;
}

module.exports = { copyText, copySourceUrl, ensurePrivacyAuthorized, isPrivacyFailure };
