/**
 * 隐私授权协调器（T00609）
 *
 * 背景：`<button open-type="chooseAvatar">` 触发隐私授权时，微信框架要求授权动作
 * 通过 **官方 `<button open-type="agreePrivacyAuthorization">` 按钮** 完成——
 * 自定义弹窗里用 `wx.showModal` 的「同意」按钮 + `resolve({event:'agree'})`（不带 buttonId）
 * 会被框架判定为「授权未完成」，报：
 *   `chooseAvatar:fail privacy permission is not authorized or buttonId is wrong`
 *
 * 因此授权 UI 分两条路径：
 * - **组件路径（首选）**：自定义弹窗内放官方按钮（id 与 resolve 的 buttonId 一致），
 *   resolve 带 `{event:'agree', buttonId}` → 所有隐私接口（含 chooseAvatar）都能过；
 * - **兜底路径**：`wx.showModal` 原生弹窗（无法承载官方按钮）→ `resolve({event:'agree'})`
 *   不带 buttonId —— 对剪贴板等**非按钮触发**的隐私接口可用，但 chooseAvatar 会失败，
 *   故按钮类接口所在页面必须挂载 privacy-modal 组件。
 *
 * 本模块只管**待决 resolve 队列与扇出**（纯逻辑，可单测），UI 由调用方（app.js）注入。
 */

/**
 * @param {object} opts
 * @returns 隐私授权协调器
 */
function createPrivacyCoordinator() {
  let pending = [];   // 挂起的 resolve 回调（并发隐私 API 调用共用一次授权）
  let showing = false;

  return {
    /**
     * 新的隐私授权请求进入队列。
     * @returns {{shown: boolean}} shown=false 表示已有弹窗在展示、本次仅排队（防重入）
     */
    needPrivacy(resolve) {
      pending.push(resolve);
      if (showing) return { shown: false };
      showing = true;
      return { shown: true };
    },

    /** 是否有弹窗正在展示（防重入判断用） */
    isShowing() {
      return showing;
    },

    /** 排队中的请求数 */
    pendingCount() {
      return pending.length;
    },

    /**
     * 用户点击官方 agreePrivacyAuthorization 按钮（组件路径）。
     * resolve 全部挂起请求，**必须带 buttonId**（与按钮 id 一致），框架才认可授权完成。
     * @returns {number} 本次 resolve 的请求数
     */
    agreeViaButton(buttonId) {
      showing = false;
      const all = pending.splice(0);
      all.forEach((r) => r({ event: 'agree', buttonId: buttonId || 'agree-btn' }));
      return all.length;
    },

    /**
     * 兜底路径同意（wx.showModal，无官方按钮）。
     * resolve 不带 buttonId：对非按钮触发的隐私 API（剪贴板等）可用；
     * chooseAvatar 等 button 触发的接口会失败 —— 页面须改用 privacy-modal 组件。
     */
    agreeFallback() {
      showing = false;
      const all = pending.splice(0);
      all.forEach((r) => r({ event: 'agree' }));
      return all.length;
    },

    /** 用户拒绝 / 弹窗展示失败：全部按 disagree 放行（各隐私 API 由框架自行 fail） */
    reject() {
      showing = false;
      const all = pending.splice(0);
      all.forEach((r) => r({ event: 'disagree' }));
      return all.length;
    },
  };
}

module.exports = { createPrivacyCoordinator };
