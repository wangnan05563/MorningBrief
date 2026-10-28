/**
 * 加载失败态组件（J4/J16/J38/J39/J47/J106）
 *
 * 与 empty-state 是两件事：空态说「确实没有」，失败态说「这次没取到」。
 * 两者混用会让用户拿「没有内容」的结论去处理网络问题，而失败态必须自带重试。
 *
 * 用法：
 *   <load-error wx:if="{{loadError}}" message="{{loadError}}" bind:retry="onRetryLoad" />
 */
Component({
  properties: {
    // 失败原因：直接透传接口抛出的文案（「网络异常」「请求超时」「登录失败，部分功能不可用」）
    message: {
      type: String,
      value: '',
    },
    // 补充说明：默认把「不是内容问题」说清楚，避免用户以为内容被删
    description: {
      type: String,
      value: '内容没有加载出来，可能与网络或服务有关，稍后点「重试」再试一次',
    },
    // 没有可重试的动作时（如缺少页面参数）关掉按钮，避免点了仍失败
    retry: {
      type: Boolean,
      value: true,
    },
  },

  methods: {
    onRetry() {
      this.triggerEvent('retry');
    },
  },
});
