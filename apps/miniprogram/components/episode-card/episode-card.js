/**
 * 节目信息卡片组件
 *
 * 抽取原因：index 与 detail 两页各自维护 .episode-card 结构与样式，
 * 标题字号、日期颜色等细节漂移。统一后保证两页视觉一致，修改仅需改组件。
 *
 * 时长格式化用 WXS 而非 JS：WXS 在模板层计算，避免 observer 中 setData 抖动
 */
Component({
  properties: {
    // 节目对象 { id, title, date, duration, audio_url, source, channel, categories }
    episode: {
      type: Object,
      value: null,
    },
    // 是否显示底部“播放/详情”操作按钮：列表场景需要，详情页内嵌时不需要
    showActions: {
      type: Boolean,
      value: false,
    },
  },

  methods: {
    onPlay() {
      // catchtap 阻止冒泡，避免与父容器 tap 冲突
      this.triggerEvent('play', { episode: this.data.episode });
    },
    onViewDetail() {
      this.triggerEvent('view-detail', { episode: this.data.episode });
    },
  },
});
