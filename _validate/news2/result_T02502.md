# T02502 回传：引导锚点契约化 + 跳过记账 + 帮助页重放（FR-UX-403）

## 根因

三条独立成因，共同表现为「引导指错地方 / 关掉就再也打不开」：

1. **锚点契约缺失**。`guideConfig.js` 的选择器里混着三类不可靠写法：引用 tooltip 文案当 aria-label（`[aria-label="立即触发一期工作流"]`，页面上根本没有这个标签）、组合位置兜底（`.top-bar .el-button`）、以及实例数不受约束的裸类（`.el-table`）。`GuideOverlay.resolveTarget()` 是「按顺序取第一个命中的元素」，静态扫描只看「代码里有没有这个标签」，看不到「这一页运行时渲染出来没有」——于是真实锚点缺失时静默退到兜底选择器，高亮落到工具栏第一个按钮（刷新），气泡文案却写着「手动触发」。
2. **一步多选择器的兜底链掩盖错误**。上一步指错了，下一步因为兜底链存在照样「成功」，缺陷在配置层不可见，只有人工盯着屏幕才能发现。
3. **跳过语义与记账脱节**。`skip()` 只关浮层不写 localStorage，而首访判定是 `!isDone(path)`——「跳过」表达的是「我不要这个菜单的引导」，却不记账，等于每次进入该页再弹一次；反过来引导一旦记过账，除了清 localStorage 没有任何入口再看第二遍（帮助页只讲操作，不能唤起引导）。

## 影响范围

- 全站 27 条菜单路由的引导浮层命中目标与文案一致性（59 步）。
- 引导状态机：`useGuide` 的记账/跳过/重放语义、`Layout.vue` 的首访判定与落地重放。
- 帮助页（`Help.vue`）新增「菜单引导重放」跨菜单入口与「清除引导记录」出口。
- 构建期门禁 `validate-nav.mjs` 被 `vite.config.js` 以 `apply:'build'` + `buildStart()` 硬失败接入，锚点契约从此是编译前提而非评审约定。
- 26 个视图文件被插入 `data-guide` 显式锚点（55 处）；不改任何业务逻辑与数据流。

## 修复（绝对路径 + 改动点）

**显式锚点落地**
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\**`（26 个视图）：给被引导的页面容器、tab、表格、分页、卡片、按钮补 `data-guide="..."`，共 55 个锚点。例如 `WorkflowList.vue` 的触发按钮、`ReviewList.vue` 的 `review-page/review-tabs/review-table/review-pagination`、`LlmMetrics.vue` 的 `llm-metrics-rates`。
- `D:\code\otherProjects\20_News\apps\admin-web\src\guide\guideConfig.js`：59 步全部改为单选择器显式锚点；文件头写成 5 条约定（首选 data-guide / 允许 aria-label / 禁止位置兜底 / 一步一个选择器 / 文案必须与被锚定元素一致）。`/help` 新增一步指向重放区块。仅 `/materials` 两步因并发会话占用视图文件暂用白名单裸类（已建派生单 T02645 收口）。

**构建期门禁（静态可证的部分）**
- `D:\code\otherProjects\20_News\apps\admin-web\scripts\validate-nav.mjs`：新增 `dataGuides` 事实抽取（同一次视图遍历）与 `anchorProblem()`——按「data-guide 必须存在于视图 / aria-label 必须存在于代码 / 含空格或 `>` 的组合选择器直接拒绝 / 裸类只允许 `PAGE_UNIQUE_CLASSES` 全页唯一布局类」判定；`checkFacts()` 加「一步只允许一个选择器」检查。错误文案带路由、选择器与步骤标题，可直接定位。
- `D:\code\otherProjects\20_News\apps\admin-web\scripts\validate-nav.test.mjs`：fixture 改用合法 data-guide 锚点并补 `dataGuides` 字段，新增 4 条契约用例（多选择器 / 不存在的 data-guide / 组合选择器与多实例裸类 / 全页唯一类放行）+ 1 条「真实仓库锚点事实非空」用例，防止门禁因抽取失效而恒过。

**运行时审计（静态证不了的部分）**
- `D:\code\otherProjects\20_News\apps\admin-web\scripts\guide-anchor-audit.mjs`（新增）：用 Playwright 驱动 Chrome 逐条走 `/workflows?guide=demo` 这类路由，记录每步实际命中元素与 `data-guide-missing` 落空标记，输出 `_validate/news2/guide_anchor_audit.json`。其中 `FIXTURES` 表针对「空态走 `el-empty`、被引导卡片不渲染」的数据依赖锚点回最小 fixture——否则审计会把视图的空态分支误判成锚点缺失（首轮 `/stats/llm-metrics` 的未命中即由此而来）。
- `D:\code\otherProjects\20_News\apps\admin-web\package.json`：`validate:nav`、`test:nav`（显式文件名，Windows 下 `node --test scripts/` 会 MODULE_NOT_FOUND）。

**跳过记账与重放**
- `D:\code\otherProjects\20_News\apps\admin-web\src\guide\useGuide.js`：`skip()` 改为 `markDone(currentPath)` 后关闭（与 `finish()` 同记账）；新增 `markUndone(path)`、`requestReplay(path)` / `takeReplay(path)`（只登记目标路径，等目标页挂载后由 Layout 消费，避免锚点还没渲染就开浮层）；`open()` 支持 `opts.force`——用户主动点「播放引导」是明确意图，不受自动化环境守卫拦截（否则 e2e 无法验证「引导可从帮助页重新唤起」）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\layouts\Layout.vue`：`maybeGuide()` 先消费重放请求（落地后 `force` 打开），否则维持「未记账才弹首访」；常驻按钮 `openGuide()` 走 force。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\help\Help.vue`：新增 `data-guide="help-replay"` 区块——按 `GUIDE_STEPS` 列出可重放菜单（与侧栏同一可见性口径，过滤 `requireRole==='admin'` 对运营角色的隐藏项）、已记账项打勾、点一下 `markUndone + requestReplay + router.push`；再挂「清除引导记录」按钮，走 `ElMessageBox.confirm` 二次确认后批量 `markUndone`。文案与浮层沿用项目 `utils/message` 安全封装，未直接引 `element-plus`。

## 验证

全部为本轮实测，非推断：

- **锚点契约单测**：`npm run test:nav` → `tests 11 / pass 11 / fail 0`（含 4 条新契约用例 + 真实仓库非空断言）。
- **引导 e2e**：`PW_CHANNEL=chrome npx playwright test tests/guide-replay.spec.js tests/guide-target.spec.js` → `6 passed (27.3s)`。覆盖：跳过会写记账、帮助页点击跳转并重放且高亮元素带 `data-guide="review-page"`、已跳过菜单仍可重放、清除引导记录后恢复首访口径、运营角色看不到 admin 专属菜单、工作流引导第二步高亮的 `aria-label` 确为「手动触发」（修复前该步指到刷新按钮）。
- **运行时锚点审计**：27 路由 / 59 步 / **未命中 0 / 标题漂移 0**，证据 `D:\code\otherProjects\20_News\_validate\news2\guide_anchor_audit.json`。为排除长驻 dev server 的模块缓存假象，另在 5199 端口起了全新 vite 复跑一次，结果一致。
- **构建门禁生效性**：`npm run build` 通过；把选择器改成不存在的 aria-label 后 `npm run validate:nav` 会报出该步骤（门禁不是恒过）。
- **全量回归**：整套 e2e `141 passed / 4 failed`，4 条失败已由 T02628 证实为本单之前的存量失败（与本单改动无交集），未在本单内伪装修复。

## 本次回写

- **T02645**（新建，已按最终设计校正标题与描述）：素材录入页补 `data-guide` 锚点并从 `PAGE_UNIQUE_CLASSES` 移除裸类例外。本单唯一未收敛的锚点例外由此单收口——白名单留着会退化成兜底通道。
- **T02656**（新建）：数据依赖的引导步骤在空态会落空（`/stats/llm-metrics` 等指向数据渲染区的步骤），本单只在审计脚本里用 fixture 绕过，产品侧「落空即跳过该步」的正解留给该单。
- **T02636**（复用）：把 `guide-anchor-audit.mjs` 从「手动命令」接入强制检查点（CI / 发布前置）的既有待办，本单已交付脚本与证据口径，收口在 T02636。
- **T02628**（复用）：全量 e2e 的 4 条存量失败归属该单跟踪，未新建重复单。

## 下一步建议

1. 把运行时锚点审计接进 CI / 发布前置命令（目前靠手动执行，靠人不靠流程必然漏跑）→ **已建派生单：T02636**。
2. 素材录入页 `data-guide` 锚点落地并清空 `PAGE_UNIQUE_CLASSES`，让门禁只认显式锚点 → **已建派生单：T02645**。
3. 数据依赖锚点在空态（新装/清库实例）会静默落空，正解是让浮层「落空即跳过该步」并把说明性步骤与缺陷性落空区分开；本单仅用 fixture 让审计跑通 → **已建派生单：T02656**。
4. 人工抽查项（GUI 视觉，代码层已证、观感仍需肉眼确认）：① 各菜单气泡的高亮框是否贴住目标元素边缘（重点 `Stats`、`Tunnel`、`Help`）；② 帮助页重放区块在 220px 侧栏宽度下的 chip 换行与勾标位置；③ 「清除引导记录」确认框文案是否与预期一致。
