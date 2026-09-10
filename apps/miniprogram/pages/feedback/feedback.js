/**
 * 意见反馈：分类选择 + 内容输入 + 联系方式（选填）
 *
 * 字数与分类阈值统一从 config.js 读取，避免与后端校验口径不一致。
 */
const { CONFIG } = require('../../utils/config');
const { submitFeedback } = require('../../services/api');
const { trackPageView, trackEvent } = require('../../utils/tracker');

// 内容最小长度：低于此值视为信息不足，难以定位问题
const MIN_LENGTH = 10;
// 本地反馈历史 key（仅本机可见，便于用户回溯已发送记录）
const STORAGE_KEY_FEEDBACK_HISTORY = 'news_feedback_history';
// 历史最多保留条数，避免无限增长
const MAX_HISTORY = 20;

/**
 * 时间格式化（B7）：时间戳 -> "YYYY-MM-DD HH:mm"
 * 小程序无原生 Intl 稳定保证，手写补齐，避免 timeLabel 显示为空
 */
function formatTime(ts) {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '';
  const pad = (n) => (n < 10 ? '0' + n : '' + n);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * 给历史条目补全 timeLabel（B7）：优先用已有 timeLabel，否则由 time 推导。
 * 兼容旧版本仅存 time 的历史记录，保证 wxml 的 {{item.timeLabel}} 恒有值。
 */
function decorateHistory(list) {
  if (!Array.isArray(list)) return [];
  return list.map((it) => ({
    ...it,
    timeLabel: it.timeLabel || (it.time ? formatTime(it.time) : ''),
  }));
}

Page({
  data: {
    categories: CONFIG.feedbackConfig.categories,
    maxLength: CONFIG.feedbackConfig.maxLength,
    selectedCategory: '',   // 空串表示未选，提交前必校验
    content: '',
    contact: '',
    submitting: false,      // 防止重复提交
    history: [],            // 已发送反馈本地列表（B7）
  },

  onLoad() {
    trackPageView('pages/feedback/feedback');
    this.loadHistory();
  },

  /**
   * 读取本地反馈历史（B7）：页面返回后仍能看到已发送记录
   */
  loadHistory() {
    try {
      const raw = wx.getStorageSync(STORAGE_KEY_FEEDBACK_HISTORY) || [];
      this.setData({ history: decorateHistory(raw) });
    } catch (err) {
      console.warn('[feedback] 读取历史失败:', err && err.errMsg);
    }
  },

  onCategoryTap(e) {
    const { category } = e.currentTarget.dataset;
    this.setData({ selectedCategory: category });
    trackEvent('feedback', 'select_category', category);
  },

  onContentInput(e) {
    const value = e.detail.value || '';
    // 超长截断：textarea 已设 maxlength，此处二次兜底，防止输入法组合态溢出
    const truncated = value.length > this.data.maxLength
      ? value.slice(0, this.data.maxLength)
      : value;
    this.setData({ content: truncated });
  },

  onContactInput(e) {
    this.setData({ contact: e.detail.value || '' });
  },

  async onSubmit() {
    if (this.data.submitting) return;

    const { selectedCategory, content, contact } = this.data;

    // 校验顺序遵循"先必选、后长度"，提示更贴近用户真实卡点
    if (!selectedCategory) {
      wx.showToast({ title: '请选择反馈分类', icon: 'none' });
      return;
    }
    if (!content.trim()) {
      wx.showToast({ title: '请输入反馈内容', icon: 'none' });
      return;
    }
    if (content.trim().length < MIN_LENGTH) {
      wx.showToast({ title: `内容至少 ${MIN_LENGTH} 个字`, icon: 'none' });
      return;
    }

    this.setData({ submitting: true });
    try {
      await submitFeedback({
        category: selectedCategory,
        content: content.trim(),
        contact: contact.trim(),
      });
      trackEvent('feedback', 'submit_success', selectedCategory);
      wx.showToast({ title: '反馈已提交，感谢支持', icon: 'success' });
      // 写入本地历史（B7）：不存联系方式，仅分类 + 内容摘要 + 时间，便于回溯
      const newItem = {
        category: selectedCategory,
        summary: content.trim().slice(0, 50),
        time: Date.now(),
      };
      newItem.timeLabel = formatTime(newItem.time);
      this.appendHistory(newItem);
      // 延迟返回，让 success toast 完整展示后再退栈，避免被瞬间覆盖
      setTimeout(() => {
        this.resetForm();
        wx.navigateBack();
      }, 800);
    } catch (err) {
      console.error('提交反馈失败:', err);
      wx.showToast({ title: err.message || '提交失败，请稍后重试', icon: 'none' });
    } finally {
      this.setData({ submitting: false });
    }
  },

  // 提交成功后清空表单，避免返回上一页时残留态被误以为未提交
  resetForm() {
    this.setData({
      selectedCategory: '',
      content: '',
      contact: '',
    });
  },

  /**
   * 追加一条反馈到本地历史（B7）：最新在前，超 MAX_HISTORY 截断
   */
  appendHistory(item) {
    const history = decorateHistory([item, ...this.data.history]).slice(0, MAX_HISTORY);
    this.setData({ history });
    try {
      wx.setStorageSync(STORAGE_KEY_FEEDBACK_HISTORY, history);
    } catch (err) {
      console.warn('[feedback] 历史写入失败:', err && err.errMsg);
    }
  },
});
