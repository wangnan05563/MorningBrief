/**
 * 外链容器页：承载 web-view 组件加载节目来源原文
 *
 * 使用方式：navigateTo 时携带 url 参数，页面解码后传给 web-view
 * - 业务域名已配置：web-view 正常加载原文
 * - 业务域名未配置：binderror 触发 → 显示 fallback 界面引导用户复制链接
 * - fallback=1 参数：跳过 web-view 加载直接显示兜底界面
 *   （用于 detail 页复制失败时跳转，避免微信原生"无法打开该页面"拦截）
 */
const { copyText } = require('../../utils/clipboard');

Page({
  data: {
    url: '',
    error: false,
    // 5s 仍未触发 bindload 时强制显示 fallback：避免某些情况下 binderror 不触发（如 SSL 握手挂起），
    // 用户长时间看到一片白板
    _loadTimer: null,
  },

  onLoad(options) {
    // 参数通过 encodeURIComponent 编码传入，避免特殊字符破坏路由解析
    let url = '';
    try {
      url = options.url ? decodeURIComponent(options.url) : '';
    } catch (e) {
      url = options.url || '';
    }
    // fallback=1：由 detail 页复制失败跳转而来，直接显示兜底界面，不加载 web-view
    // 否则微信会在 web-view 加载前原生拦截并显示"无法打开该页面"
    if (options.fallback === '1') {
      this.setData({ url, error: true });
      return;
    }
    this.setData({ url });
    // 5s 仍未触发 bindload/binderror：兜底显示提示
    this.data._loadTimer = setTimeout(() => {
      if (this.data.url && !this.data.error) {
        // 此时仍未报错也不成功，按"慢/不可达"处理，提示用户
        this.setData({ error: true });
      }
    }, 5000);
  },

  onUnload() {
    if (this.data._loadTimer) {
      clearTimeout(this.data._loadTimer);
      this.data._loadTimer = null;
    }
  },

  /**
   * web-view 加载失败：业务域名未配置或网络不可达
   * 切换到 fallback 界面，提供"复制链接"作为替代入口
   */
  onError() {
    if (this.data._loadTimer) {
      clearTimeout(this.data._loadTimer);
      this.data._loadTimer = null;
    }
    this.setData({ error: true });
  },

  /**
   * web-view 加载成功：隐藏 fallback（若已显示）
   * 必须用独立方法名 onWebviewLoad，避免与 Page 生命周期 onLoad(options) 冲突：
   * 原实现将同名函数写在 Page 对象里，JS 后定义覆盖前定义，导致 options 参数被丢弃、url 永远是空，
   * 这是用户反馈"白板"现象的根本原因。
   */
  onWebviewLoad() {
    if (this.data._loadTimer) {
      clearTimeout(this.data._loadTimer);
      this.data._loadTimer = null;
    }
    if (this.data.error) this.setData({ error: false });
  },

  /**
   * 复制链接按钮：复用 utils/clipboard.copyText 保证与 detail 页一致的行为
   * 复制成功弹 toast 提示（此处未自动弹微信"内容已复制"toast 时才提示，避免重复）
   */
  async onCopy() {
    const ok = await copyText(this.data.url);
    if (ok) {
      wx.showToast({ title: '链接已复制', icon: 'success' });
    } else {
      // 复制失败时提示用户长按上方链接文本手动复制（fallback-url 已开启 user-select:text）
      wx.showToast({ title: '复制失败，请长按上方链接复制', icon: 'none' });
    }
  },

  onBack() {
    wx.navigateBack();
  },
});
