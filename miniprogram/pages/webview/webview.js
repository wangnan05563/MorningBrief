/**
 * 外链容器页：承载 web-view 组件加载节目来源原文
 *
 * 使用方式：navigateTo 时携带 url 参数，页面解码后传给 web-view
 * 如 web-view 加载失败（域名未配置），切换到 fallback 界面引导用户复制链接
 */
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

  onCopy() {
    wx.setClipboardData({
      data: this.data.url,
      success: () => {
        wx.showToast({ title: '链接已复制', icon: 'success' });
      },
      fail: () => {
        wx.showToast({ title: '复制失败，请手动长按链接复制', icon: 'none' });
      },
    });
  },

  onBack() {
    wx.navigateBack();
  },
});
