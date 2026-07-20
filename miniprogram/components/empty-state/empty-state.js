/**
 * 空状态组件：统一各页面“无数据/加载失败”的视觉
 *
 * 抽取原因：detail/history/index 三页各自重复写 <view class="empty-state">，
 * 样式与结构漂移风险高。统一后修改空状态样式只需改组件。
 */
Component({
  properties: {
    // 图标：支持 emoji 字符（如 '📰'）或图片路径（搭配 icon-type=image），为空则不显示
    icon: {
      type: String,
      value: '',
    },
    // 图标类型：'text'（默认，emoji 字符）或 'image'（PNG 图标路径）
    // 当为 image 时使用 image 标签渲染，避免 emoji 跨平台渲染不一致
    iconType: {
      type: String,
      value: 'text',
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
