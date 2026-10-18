## 根因

`apps/admin-web/src/utils/message.js` 的初衷是对的——最小化窗口时绝不插入提示 DOM，避免把用户窗口「弹回来」。但实现只做了「丢弃」这一半，没做「补发」那一半：

1. **隐藏期间的失败原因永久丢失**：`_shouldBlock()` 命中后直接 `return`，`ElMessage.error/warning/...` 的调用结果被无声吞掉。用户切回页面时看到的是一个「一切正常」的界面，而失败早在后台发生并被销毁——D78/A19/E1 三条评审记录的都是这个现象（保存失败看不到原因、后台标签页里的错误永久消失）。
2. **axios 拦截器把网络层错误整个短路**：`src/api/index.js` 的 error 分支第一句就是 `if (document.hidden) return Promise.reject(error)`——HTTP 500/断网这类错误在隐藏时连进入提示层的机会都没有（业务错误 code≠0 走的是另一分支，会被上面的丢弃逻辑吞掉）。
3. **确认框的处置口径混在丢弃里**：`confirm/prompt` 被拦截时 reject（等价「用户取消」）——这个语义必须保留（补发一个错过时机的确认框等于替用户按高危按钮），但此前它与普通提示共用同一条「丢弃」路径，没有任何文档说明两者口径不同，后续改动很容易把 confirm 也「顺手补发」。

## 影响范围

全站提示出口只有这一处包装器（`src/utils/message.js`）+ 拦截器（`src/api/index.js`），本次两处都改了，因此影响面是「所有页面在后台标签页/最小化期间的提示行为」：

- 队列管理、审核、素材库等页面都有轮询/自动刷新；隐藏期间的失败此前静默，现在会积压并在切回时聚合补发 1 条（上限 5 条，TTL 60s 过期即丢）。这是行为变化，但方向与 PRD 一致：切回页面应看到失败，而不是什么都没发生。
- 401 分支刻意维持「隐藏时不跳转、不清本地态」——否则后台标签页会静默把已登录用户踢下线并触发跳转，属回归风险；代价见「下一步建议」第 1 条（已建派生单 T02614）。
- `ElMessageBox.confirm/prompt/alert` 语义不变（reject / resolve，不入队、不回放）。
- `ElMessage.loading` 不入队（补发一个没有对应请求的转圈只会残留）。
- `closeAll` 现在同时清空积压队列：调用方显式「关掉所有提示」时，隐藏期间的积压也应作废，否则会在稍后凭空冒出来。
- 新增 DEV-only 全局 `window.__safeMessage`（size/texts/push/loading）供 e2e 断言队列语义；已实测生产构建不含该标识：`grep -rl "__safeMessage" dist/assets` 无命中（`import.meta.env.DEV` 分支被 vite 在生产构建时摇掉）。

## 修复

- `D:\code\otherProjects\20_News\apps\admin-web\src\utils\message.js`（整文件重写，119 行改动）
  - 新增 `_queue` + `_enqueue(type, text, ts)`：同类型同文案去重（命中则刷新时间戳而非新增），`_MAX_QUEUE = 5` 溢出 `_queue.shift()`（FIFO 丢最旧）。
  - 新增 `_flush()`：`document.hidden` 时直接返回；`_TTL_MS = 60000` 外的条目丢弃；存活条目按 `_RANK`（error>warning>info>success）挑最严重的一条展示，多于 1 条时追加「（页面隐藏期间共积压 N 条提示，已聚合）」，`duration 6000`。
  - `visibilitychange` 恢复可见 → 进入 2s `_isRestoring` 窗口 → 窗口结束的定时器回调里 `_isRestoring = false` 后**再** `_flush()`（对齐 PRD「恢复且 _isRestoring 结束后聚合补发」，避免刚露面就刷弹窗）。
  - `safeElMessage` 及其 `success/error/warning/info` 在 `_shouldBlock()` 时改为 `_enqueue(...)`；`loading` 维持静默丢弃；`closeAll` 先清队列。
  - `safeElMessageBox.confirm/prompt` 保持 reject、`alert` 保持 resolve，并在文件头写明「三者都不入队、不回放」的理由。
- `D:\code\otherProjects\20_News\apps\admin-web\src\api\index.js`
  - 把 `if (document.hidden) return Promise.reject(error)` 收窄为 `if (error.response?.status === 401 && document.hidden) return Promise.reject(error)`；其余隐藏期错误继续走 `ElMessage.error(...)` → 进入队列补发。401 分支补 `return`，不再落入 else-if 的提示分支。
- `D:\code\otherProjects\20_News\apps\admin-web\tests\feedback-queue.spec.js`（新增 5 条）
  - 用 `addInitScript` 提供可翻转的 `document.hidden` + `window.__setHidden()`，并用 `MutationObserver` 统计 `.el-message` / `.el-message-box` 节点插入次数（对应 ACC-UX-301 第 2 条的「页面隐藏期间不产生新 DOM 节点」）。
  - 断言：隐藏期间入队 2 条且 DOM 命中为 0 → 恢复后恰好 1 条聚合 toast（含最严重文案 + 「共积压 2 条」）、队列清零；7 条同类错误去重后只剩最后 5 条（FIFO 丢最旧）且重复项只刷新时间戳；TTL 61s 的条目恢复后不补发（DOM 命中仍为 0）；`loading` 不入队；隐藏时点「应急停服」→ 确认框不出现且不发 `POST /m/emergency/stop`，切回前台 2.7s 后仍不出现、仍不发请求（绝不回放）。

## 验证

- `PW_CHANNEL=chrome npx playwright test tests/feedback-queue.spec.js --reporter=line` → **5 passed (33.2s)**；恢复后再跑 `feedback-queue + cos-upload-rollback` → **10 passed (27.4s)**。
- 全量 e2e：`PW_CHANNEL=chrome npx playwright test` → **112 passed, 4 failed (3.4m)**。4 条失败为**并发会话的工作区改动导致的既有失败**，已用反证确认：把本次两个源文件临时还原为 HEAD 版本后重跑 `page-layout-padding.spec.js + review.spec.js`，失败集合完全相同（讲书稿素材池 / 素材库管理 / 素材录入 内边距、审核详情采集图片预览），随后已还原我的版本（`git diff --stat` 确认两文件仍是本次改动）。
- `npm run build` → **✓ built in 37.44s**，且生产包内无 `__safeMessage`（grep 无命中）。
- 提交：`0808419 feat(admin-web): 可见性感知的反馈队列…`，path-limited 到 `src/utils/message.js`、`src/api/index.js`、`tests/feedback-queue.spec.js`（263 insertions / 27 deletions）。
- 未实测项（如实标注）：
  - 「隐藏」是通过覆写 `document.hidden` 模拟的，非真实最小化窗口；真实最小化时浏览器的可见性事件时序、以及补发瞬间是否会把窗口拉回前台，需要人工用真实窗口验证。
  - ACC-UX-301 第 3 条「断网打开队列页 → 显示『加载失败，重试』而非『暂无数据』」属 FR-UX-302（T02496），本单未实现，队列页目前仍无法区分错误态与空态。
  - 聚合提示的文案形态（展示最严重一条 + 计数，其余仅计入数量不展开明细）未与产品确认。

## 本次回写

- T02495 状态置 done（`verified:false`：队列语义已 e2e 实测，但真实最小化与聚合文案口径待人工/产品确认）。
- 新建派生子任务 2 张（T02614、T02615，均 `derivedFrom=T02495`）。
- 留痕文档：`D:\code\otherProjects\20_News\_validate\news2\result_T02495.md`。

## 下一步建议

1. **隐藏期间的 401 会被完全丢弃**（已建派生单 T02614）：为不把人踢下线，`src/api/index.js` 在 `document.hidden && 401` 时直接 reject，既不提示也不跳转。若用户切回前台后页面恰好没有新请求，就会停在一个「看起来正常但会话已过期」的界面。建议：把 401 也记入队列（用独立标记而非普通提示），恢复可见时优先执行跳转/提示；或订阅 `visibilitychange` 主动做一次鉴权探测。需确认产品口径（后台标签页是否应当保持登录态）。
2. **真实窗口最小化下的补发时机验证**（已建派生单 T02615，标 【缺环境】）：本环境只能用 `Object.defineProperty(document,'hidden')` 覆写，无法覆盖真实最小化/切标签页时的可见性事件与窗口激活行为，而这条恰恰是本需求「保留原意」的核心风险（补发不能把窗口弹回来）。需人工按单里的步骤验证并截图留痕。
3. 与 T02497（FR-UX-303 提示去重与单一出口）口径合流：本次的队列内去重只按「类型 + 文案」，跨来源（拦截器已弹 + 局部 catch 再弹）的重复仍未收敛，属 T02497 既有待办范围，不另建单（仅观察，沿用 T02497）。
