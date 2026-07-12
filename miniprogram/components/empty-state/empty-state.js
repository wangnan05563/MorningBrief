/**
 * 空状态组件：统一各页面“无数据/加载失败”的视觉
 *
 * 抽取原因：detail/history/index 三页各自重复写 <view class="empty-state">，
 * 样式与结构漂移风险高。统一后修改空状态样式只需改组件。
 */
Component({
  properties: {
    // 图标：支持 emoji 字符（如 '📰'）或图片路径，为空则不显示
    icon: {
      type: String,
      value: '',
    },
    // 主标题文字
    title: {
      type: String,
      value: '',
    },
    // 描述文字（可选，显示在标题下方）
    description: {
      type: String,
      value: '',
    },
  },
});
