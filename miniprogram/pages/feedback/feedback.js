/**
 * 意见反馈：分类选择 + 内容输入 + 联系方式（选填）
 *
 * 字数与分类阈值统一从 config.js 读取，避免与后端校验口径不一致。
 */
const { CONFIG } = require('../../utils/config');
const { submitFeedback } = require('../../services/api');

// 内容最小长度：低于此值视为信息不足，难以定位问题
const MIN_LENGTH = 10;

Page({
  data: {
    categories: CONFIG.feedbackConfig.categories,
    maxLength: CONFIG.feedbackConfig.maxLength,
    selectedCategory: '',   // 空串表示未选，提交前必校验
    content: '',
    contact: '',
    submitting: false,      // 防止重复提交
  },

  onCategoryTap(e) {
    const { category } = e.currentTarget.dataset;
    this.setData({ selectedCategory: category });
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
      wx.showToast({ title: '反馈已提交，感谢支持', icon: 'success' });
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
});
