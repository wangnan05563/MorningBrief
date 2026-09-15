/**
 * 隐私授权弹窗组件（T00609）
 *
 * 为什么需要组件而非 wx.showModal：
 * 按钮触发的隐私接口（chooseAvatar 等）要求授权动作通过**官方按钮**完成——
 * `<button open-type="agreePrivacyAuthorization" id="agree-btn">`，且
 * `resolve({event:'agree', buttonId:'agree-btn'})` 中的 buttonId 必须与按钮 id 一致。
 * wx.showModal 的「同意」无法满足该要求，会报：
 *   chooseAvatar:fail privacy permission is not authorized or buttonId is wrong
 *
 * 用法：
 * 1. 页面 json 注册组件，wxml 放置 `<privacy-modal />`；
 * 2. 组件 attached 时向 app 注册自己（app.registerPrivacyUI），
 *    app.js 的 onNeedPrivacyAuthorization handler 会调用 show() 弹出；
 * 3. 用户点「同意并继续」（官方按钮）→ 回调 onAgree → app.agreePrivacyViaButton('agree-btn')；
 *    用户点「拒绝」→ app.rejectPrivacy()。
 */
const THEME_CONFIRM = '#3F6C8F';

Component({
  data: {
    visible: false,
  },

  lifetimes: {
    attached() {
      const app = getApp();
      if (app && typeof app.registerPrivacyUI === 'function') {
        app.registerPrivacyUI(this);
      }
    },
    detached() {
      const app = getApp();
      // 仅在仍是当前 UI 时注销，避免误删后来者的注册
      if (app && app._privacyUI === this) {
        app.registerPrivacyUI(null);
      }
    },
  },

  methods: {
    /** 由 app.js 的 onNeedPrivacyAuthorization handler 调用 */
    show() {
      this.setData({ visible: true });
    },

    hide() {
      this.setData({ visible: false });
    },

    /** 官方 agreePrivacyAuthorization 按钮回调：带 buttonId 收尾所有挂起的授权 */
    onAgree() {
      this.hide();
      const app = getApp();
      if (app && typeof app.agreePrivacyViaButton === 'function') {
        app.agreePrivacyViaButton('agree-btn');
      }
    },

    /** 拒绝：按 disagree 放行（各隐私 API 由框架自行 fail） */
    onReject() {
      this.hide();
      const app = getApp();
      if (app && typeof app.rejectPrivacy === 'function') {
        app.rejectPrivacy();
      }
    },

    /** 查看隐私协议全文（官方能力：拉起隐私协议小程序页面） */
    onOpenContract() {
      if (typeof wx.openPrivacyContract === 'function') {
        wx.openPrivacyContract({});
      }
    },

    /** 阻断冒泡，防止点面板内容关闭弹窗 */
    stopPropagation() {},
  },
});
