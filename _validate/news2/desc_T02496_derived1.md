来源：T02496（FR-UX-302 错误态与重试）

T02496 只覆盖了需求点名的主列表页（队列/频道/工作流/数据管理/统计 + 移动端队列 + 小程序详情）。仍有 13 个页面在请求失败时把数据置空、界面显示「暂无数据」，用户无法区分「真的没有」和「接口挂了」：
ReviewList、ReviewDetail、WorkflowDetail、MaterialLibrary、BookPoolPanel、CosFiles、BookFinder、AdMaterials、AdPlacements、ChannelHealth、LlmMetrics、RssHealth、AutoReviewConfig。

优先级说明：审核列表/审核详情是运营每日主用页面，失败显示「暂无待审」会让漏审被误读成「今天没内容」，必须先做。

落地要点：
1. 复用 apps/admin-web/src/components/ListLoadError.vue（注意：显隐由使用方 v-if 决定，组件内不再有 visible 门控）与 useLoadState 三态封装，不要各页自造文案。
2. 失败时必须保留上一次成功加载的行（不清空数组），否则「stale」提示无从谈起；空态 el-empty 加 v-if="!listError"。
3. 有编辑/删除/审核提交入口的页面，失败态要一并禁用这些按钮（参照 DatabaseAdmin 的做法：列信息缺失时弹空表单等于用空对象覆盖该行）。
4. 每接完一个页面在 apps/admin-web/tests/list-error-state.spec.js 里加一条用例（首次 route.abort() 断言 .list-load-error 可见，点重试断言横幅消失）。
5. 顺手统一：把这些页面各自的 loading ref 收敛到 useLoadState，让 stale 由 composable 产出（T02496 结果「下一步建议」第 3 条）。
