来源：T02497（FR-UX-303 提示去重）

T02497 只把「拦截器已弹不二次弹」落到已确认的几处：KnowledgeQA 两处改 notifyErrorOnce，ChannelManagement 删除影响面预览改 silent。全仓 apps/admin-web/src 里还有 46 处 ElMessage.error(，未逐条核实其请求是不是 silent：
- 非 silent 请求 + 页面又弹 e.message → 现在靠 2 秒文案去重合并（文案相同才合得起来，带上下文的合成文案仍会两条）→ 应当改用 notifyErrorOnce(e, ...) 或把请求改 silent，二者取其一，原则是「同一件事只有一条完整说明」。
- blob + silent 请求（AIConfig 试音、WorkflowDetail 音频/成品音频加载）→ 页面那条是唯一提示，必须保持现状，不能改 notifyErrorOnce 后被标记误吞。

落地要点：
1. 逐条列矩阵：文件:行 / 调用的 api 函数 / 是否 silent / 页面文案是否与拦截器同源 / 处置（notifyErrorOnce、silent、保持）。
2. 改完在 tests/message-dedupe.spec.js 补一条真实链路用例：mock 一个非 silent 接口返回 code:500，断言该页只出现 1 条 .el-message。
3. 顺带把源码扫描断言扩到 ElNotification / MessageBox 之类旁路（当前只查了 ElMessage/ElMessageBox 从 element-plus 直引）。
