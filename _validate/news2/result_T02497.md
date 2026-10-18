## 根因

提示「一件事弹好几条」有两个互不相同的来源，只做其中一个都治不好：

1. **并行请求风暴**：队列页 onMounted 同时发 stats / config / tasks 三个请求，后端挂了时拦截器为**每个请求各弹一条**同样的「服务暂不可用 / Network Error」——一次页面加载 3 条同样的 toast 叠在一起。此前 `utils/message.js` 只在「页面隐藏」时对**入队**做同文案去重，可见状态下完全不合并。
2. **拦截器与页面各弹一次**：拦截器弹 `error.response.data.message` 后 `Promise.reject(error)`，页面 catch 里又 `ElMessage.error(e?.message || 'xx失败')`。两边文案经常相同（业务错误分支甚至就是同一个字符串），但没有去重，于是同一件事两条。而像 `deleteChannelPreview` 失败时页面弹的是**带后果说明的合成文案**（「无法获取删除影响面预览，已禁止删除：xxx」），与拦截器原文不同，**按文案合并根本合不起来**——这种情况只能靠「谁已经为这个错误弹过」的事实来判断。
3. **单一出口有旁路**：`views/system/AutoReviewConfig.vue:322` 直接 `import { ElMessage, ElMessageBox } from 'element-plus'`，绕开了包装器——该页的提示既不受隐藏期守卫（FR-UX-301）也不受新加的去重约束，属于「约定了唯一出口但没守住」。

## 影响范围

- 全局提示层：`apps/admin-web/src/utils/message.js`（新增 2 秒同类型同文案去重 + `notifyErrorOnce` + DEV 语义探针）。
- API 层：`apps/admin-web/src/api/index.js`（凡拦截器真的弹过提示的失败，给错误对象打 `__uiNotified` 标记；`silent` 请求不标记，因为它根本没弹，页面当然还要提示）。
- 收口旁路：`views/system/AutoReviewConfig.vue` 改回从 `../../utils/message` 导入。
- 站点收敛：`views/ai/KnowledgeQA.vue`（生成草稿/创建两处）改用 `notifyErrorOnce`；`views/channel/ChannelManagement.vue` + `api/channels.js` 把删除影响面预览改为 `silent: true`，让「已禁止删除」这条更完整的话成为唯一提示（而不是被拦截器抢先弹一条半截话）。
- **有意保留**的双弹位点：`AIConfig.vue` 试音、`WorkflowDetail.vue` 音频加载 —— 它们用的是 blob + `silent: true` 请求，拦截器不弹，页面那条是唯一提示，改成 `notifyErrorOnce` 反而会被误判吞掉。全仓 46 处 `ElMessage.error(` 未逐条核实 silent 归属，剩余审计建派生单（见「下一步建议」）。
- 行为变更风险：真实需要「同文案连续提示」的场景（如连点两次同一操作、两次独立失败）在 2 秒内只会看到一条。这是 FR-UX-303 要的语义；窗口锚定首次展示且不顺延，持续失败每 2 秒仍会再提醒。

## 修复（绝对路径与改动点）

- `D:\code\otherProjects\20_News\apps\admin-web\src\utils\message.js`：新增 `_DEDUPE_MS = 2000` 与 `_recent: Map<'类型|文案', 首次展示时刻>`；`_suppressDuplicate(type, text, now)` 先清理过期键再判断，命中窗口返回 true（调用方放弃弹），未命中登记本次时刻；展示路径（`safeElMessage(options)` 与 `_typed(type)`）与隐藏入队路径 `_enqueue` 都接入——入队也去重，否则一次隐藏里 5 个并行失败会占满 5 个队列槽位，补发的「共积压 N 条」变成虚报。`loading` 不参与去重（调用方要持有返回 handler 去 close，吞掉会得到 undefined）；`ElMessageBox` 不参与（确认框被吞等于替用户做决定）。`closeAll` 一并清空 `_recent`。新增导出 `notifyErrorOnce(err, text)`：`err.__uiNotified` 为真时直接返回。DEV 全局 `__safeMessage` 增 `recentKeys/dedupeMs/show/notifyOnce/reset` 供 e2e 断言。
- `D:\code\otherProjects\20_News\apps\admin-web\src\api\index.js`：新增 `_markNotified(err)`（用 try 包，冻结对象附加失败时退回纯文案去重）；业务错误分支改为先建 `const err = new Error(message)`，弹过提示后标记再 reject；HTTP 错误分支在 403/通用提示后 `_markNotified(error)`；401 分支不标记（没弹提示）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\api\channels.js:84`：`deleteChannelPreview(id, config)` 透传 config，并注释说明为什么由调用方决定 silent。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\channel\ChannelManagement.vue:1106`：预览请求带 `{ silent: true }`。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\ai\KnowledgeQA.vue:273,347,374`：导入并改用 `notifyErrorOnce`。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\system\AutoReviewConfig.vue:322`：`ElMessage/ElMessageBox` 改从 `../../utils/message` 导入（消除旁路）。
- 新增 `D:\code\otherProjects\20_News\apps\admin-web\tests\message-dedupe.spec.js`（7 条）：同类型同文案 3 连弹只 1 条 / 同文案不同类型不互吞 / 不同文案各弹 / 窗口过期后可再提醒 / 队列页三个并行请求全失败时只 1 条 / `notifyErrorOnce` 对已标记错误不弹且未标记错误按调用方文案弹 / **源码扫描断言全仓无 `import { ElMessage } from 'element-plus'` 旁路**（排除包装器本体，`@element-plus/icons-vue` 不误报）。
- 提交：`10e5a62`（path-limited，7 个文件；并发会话的 `api/audio.js`、`CourseMaterials.vue`、`rewriter.py`、`style_library.py`、`VERSION`、`package.json`、`scripts/jmeter_test/*` 等 WIP 未裹挟）。

## 验证（实测证据）

- **新增 e2e 全绿**：`PW_CHANNEL=chrome npx playwright test tests/message-dedupe.spec.js` → **7 passed (19.1s)**。
- **全量 e2e**：`npx playwright test` → **127 passed, 4 failed (2.9m)**。4 条失败为 `page-layout-padding.spec.js` 的 3 条内边距断言与 `review.spec.js`「详情页展示采集图片并可放大预览」。**已用 `git worktree` 在基线提交 `0808419`（本单改动之前）复跑同一组 spec → 同样失败（且基线是 7 条失败）**，证实与本单无关，属既有缺陷；已建派生单 T02628 归位（见「本次回写」）。
- **回归确认**：T02496 的 `list-error-state.spec.js`（8 条）、以及队列/频道/工作流/统计/配置页守卫等 spec 均在这 127 条内通过，说明 `useConfigLoad`/提示层改动没有回退既有断言。
- **构建**：`npm run build` → **✓ built in 19.17s**。
- **本环境局限**：去重语义已通过 DEV 探针 + DOM 计数实测，但「隐藏期间聚合补发 × 2 秒去重」的组合路径只在 `document.hidden` 覆写下测过，真实最小化窗口的行为仍需真人复验（与 T02495 的派生单 T02615 同一件事，不重复建单）。故本单 `verified` 标 false，人工抽查建议：
  1. 停掉后端 → 打开队列页，确认只出现 1 条错误提示而不是 3 条；
  2. 频道页点删除 → 预览接口失败时只出现 1 条「已禁止删除」提示（不再先来一条半截话）；
  3. 系统设置 → 自动审核配置页保存失败，确认提示与全站一致（该页此前是旁路，隐藏期间会唤醒窗口）。

## 本次回写

- 建派生单 **T02628**：`page-layout-padding`（素材库管理/素材录入/讲书稿素材池 内边距 16px < 22px）与 `review.spec` 采集图片预览 4 条 e2e 失败的修复——本单基线复跑确认为既有缺陷，非本单引入。
- 建派生单 **T02629**：全仓 46 处 `ElMessage.error(` 逐条核实「请求是否 silent」并收敛到 `notifyErrorOnce`，把「拦截器已弹不二次弹」从点到面收干净。
- 提示：`__safeMessage` 探针只在 `import.meta.env.DEV` 存在，生产构建不含（e2e 依赖 dev server，勿在生产页面上断言）。

## 下一步建议

- 剩余 `ElMessage.error` 站点的 silent 归属审计与收敛——**已建派生单 T02629**。
- 4 条既有 e2e 失败（布局内边距 + 采集图片预览）需要修复，否则全站 e2e 无法作为绿门——**已建派生单 T02628**。
- 真实窗口最小化下「补发 × 去重」的复验沿用 T02615（不重复建单，仅观察）。
