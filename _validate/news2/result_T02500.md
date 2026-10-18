# T02500 回传文档（FR-UX-401 导航一致性：菜单/路由/引导/帮助引用同源）

## 根因

导航类引用的正确性完全靠「人肉对照」，代码里没有任何一处能回答「这些引用还对不对」，于是四类缺陷可以长期共存而不被发现：

1. **引导选择器指向不存在的锚点**。`guideConfig.js` 的步骤用 `[aria-label="X"]` 定位高亮目标，但 X 是从按钮的 **tooltip 文案**抄来的，不是 `aria-label`。`GuideOverlay.vue:resolveTarget()` 遍历选择器全部落空后走「目标未渲染 → 气泡居中」兜底，同时退到 `.top-bar .el-button` 这个通用选择器，**高亮到了工具栏第一个按钮（「刷新」）而不是「手动触发」**。引导照样能走完，只是指错了元素——这正是「复制级缺陷」的典型：视觉上看得到，机器上查不出。
2. **`router/index.js` 顶部的「菜单分组」注释与实际 `meta.group` 漂移**。注释是手写的第一版分组，后续新增页面/分组没有同步，缺「云端存储」，成员与 `（仅 admin）` 标记也不准。侧边栏本身是 `Layout.vue` 从 `meta` 派生的（不受影响），但注释被当成事实来源读，误导人。
3. **帮助文档里的菜单引用（「位于「XX」」）与 About 页内部链接**没有任何绑定，改了路由标题就是死引用。
4. **移动端导航是手写的 `to:` 列表**（`MobileLayout.vue` 的 `allTabs`、`ManageHome.vue` 的 `modules`），与 PC 路由表是两份平行真相，PC 侧改路径移动端不会报错，只会白屏。

结论：这一条需求（让导航引用同源）的真正缺口不是某个具体错别字，而是**缺少一个能在构建期把引用全量核对的机制**。

## 影响范围

- `apps/admin-web/src/guide/guideConfig.js`：27 个页面的引导步骤选择器（其中 `/workflows` 第二步实锤指错元素）。
- `apps/admin-web/src/router/index.js`：45 条路由 + 8 个分组 + 顶部注释。
- `apps/admin-web/src/layouts/MobileLayout.vue`、`src/views/mobile/ManageHome.vue`：手写 `to:` 目标。
- `apps/admin-web/src/views/help/*`、`src/views/about/*`：帮助章节菜单引用与 About 内部链接。
- 构建链路：此前任何引用错误都不影响 `npm run build` 成功。

## 修复（绝对路径 + 改动点）

commit `c1136f5`（路径限定提交，未裹挟并发 WIP `src/api/audio.js` / `CourseMaterials.vue`）。

1. **新增校验器** `D:\code\otherProjects\20_News\apps\admin-web\scripts\validate-nav.mjs`
   - 纯静态解析，**不用 eval / new Function**：自写引号感知的花括号配对 `literalAt()`，从 `router/index.js` 抠出 routes 字面量后按序扫 `path:`，遇到「绝对路径 + 声明 `children:`」才切换父级，从而正确展开嵌套路由（`/m` → `/m/manage/users`）。
   - `readMeta()` 解析 `meta`（`title` / `group` / `hidden` / `requireRole`），据此复算侧边栏可见集合，而不是猜。
   - `tagBlocks(text, 'IconButton')` 引号感知地抠组件标签块，保证 `@click="() => ..."` 里的 `=>` 不会提前结束标签。
   - `checkFacts()` 十类交叉核对：引导 route key 缺失（支持 `:param` 匹配）、引导 `[aria-label="X"]` 不在静态 aria-label 清单、帮助菜单引用不是路由标题/分组名、移动端 `to:` 解析不到路由、About 内部 href 解析不到、`meta.group` 没有 `groupConfig` 条目、`groupConfig` 条目没有任何可见路由、顶部注释分组与实际双向漂移、可见 PC 路由缺 title/group/icon。
   - 图标名是否存在于 `@element-plus/icons-vue` 的检查**默认关闭**（`--icons` 显式开启）——Node 侧加载 293 个导出约 2 分钟，作为构建门禁代价过高。
   - 帮助文档引用用窄句式（`(侧边栏|进入|打开|切换到|位于)「X」` 与 `「X」页面`）而非「所有「」」，避免把按钮名的「」误判成菜单引用。
2. **接入构建期门禁** `D:\code\otherProjects\20_News\apps\admin-web\vite.config.js`
   - `navConsistencyGate()`：`apply:'build'` 插件，`buildStart()` 调 `validateNav()`，有 error 就 `this.error()` 中止构建并逐行打印中文原因。
3. **命令** `D:\code\otherProjects\20_News\apps\admin-web\package.json`：`validate:nav`、`test:nav`（`node --test scripts/validate-nav.test.mjs`——Windows/git-bash 下 `node --test <目录>` 会 MODULE_NOT_FOUND，必须给显式文件路径）。
4. **修复被门禁抓到的真缺陷** `D:\code\otherProjects\20_News\apps\admin-web\src\guide\guideConfig.js`
   - `/workflows` 第二步选择器改为 `{ s: ['[aria-label="手动触发"]', '.top-bar .el-button'], ... }`，并注明原来的 `立即触发一期工作流` 是 tooltip 文案不是标签、永远选不中。
5. **重生顶部注释** `D:\code\otherProjects\20_News\apps\admin-web\src\router\index.js`：从抽取结果重新生成「菜单分组」（补「云端存储」、修正成员、加 `（仅 admin）`），并写明漂移由 `npm run validate:nav` 检查。
6. **新增单测** `D:\code\otherProjects\20_News\apps\admin-web\scripts\validate-nav.test.mjs`（6 例）：真仓库必须通过，**且抽取结果非空**（`routes>30`、`ariaLabels>50`、`menuRefs>5`，`/review` 与 `/m/manage/users` 展开正确）——防止「解析器退化返回空 → 门禁 vacuously 通过」这类假绿；再对 6 类违规各种植一次失败（假 route、假 aria-label、假菜单引用、分组漂移两个方向、假 `to:`、过期注释）。
7. **新增运行时锚点证明** `D:\code\otherProjects\20_News\apps\admin-web\tests\guide-target.spec.js`：静态「选择器存在」不等于「高亮到正确元素」，故用 e2e 断言高亮节点的 `aria-label` 恰为 `手动触发`。注意 `useGuide.open()` 在 `navigator.webdriver===true` 下默认不弹引导，测试必须走 `?guide=demo` 强制入口。

## 验证（实测证据）

1. `cd apps/admin-web && npm run validate:nav` → 通过，打印「[validate-nav] 路由 45 条 · 引导 27 页 · aria-label 115 个 · 分组 8 个 · 帮助章节 15 篇」；`--icons` 亦通过。
2. `npm run test:nav` → `node --test`：**6 pass / 0 fail**。
3. **门禁能失败的正向证明**：把 `guideConfig.js` 的选择器临时改成 `[aria-label="手动触发但根本不存在"]` 后 `npm run build` → 构建中止并打印「✗ 引导步骤选择了不存在的 aria-label：/workflows → [aria-label="手动触发但根本不存在"]（标题「手动触发」）」，随后还原。
4. `npm run build` → ✓ built（EXIT=0）。
5. `tests/guide-target.spec.js`：修复后 **1 passed**；把选择器还原成原始 `[aria-label="立即触发一期工作流"]` 后 **1 failed**，报错「Expected: "手动触发" / Received: "刷新"」——同时坐实根因（指错元素）与修复有效性。
6. 全量 e2e `PW_CHANNEL=chrome npx playwright test`（日志 `_validate/news2/t02500_e2e_full.log`）→ **134 passed / 4 failed**，4 条失败为既有问题（已归入 T02628 跟踪），非本单引入。

## 本次回写

- 派生单 **T02635**「【AI回写待审核】帮助文档章节与路由缺结构化绑定，菜单引用仍靠句式启发式识别」（描述源 `_validate/news2/desc_t02500_a.md`）——本单用窄句式匹配 `「」`，新句式仍会漏，根治要让帮助文档自带结构化引用。
- 派生单 **T02636**「【AI回写待审核】导航门禁接入日常开发强制点（e2e globalSetup 或 pre-commit）」（描述源 `_validate/news2/desc_t02500_b.md`）——当前只在 `vite build` 生效，`npm run dev` 与提交前都不会拦。
- 「引导步骤改用 `data-guide` 显式锚点替代 aria-label」**不新建单**，属于既有待办 **T02502**（引导选择器与状态修复）范围，避免重复。
- 本单未变更需求状态：需求状态由「关联计划+待办完成度」自动派生，不手工置位。

## 下一步建议

1. 实施 T02635：帮助文档 front-matter 增加 `menuRefs` 结构化字段，校验器改读该字段并删除句式启发式（已建派生单 T02635）。
2. 实施 T02636：把 `validate:nav` 挂到 e2e `globalSetup` 与 pre-commit，让 dev/提交路径也被拦（已建派生单 T02636）。
3. 在 T02502 内把引导锚点从脆弱的 `aria-label` 文案绑定改为 `data-guide` 稳定属性（复用既有单 T02502，不另建）。
4. T02628 继续跟踪全量 e2e 的 4 条既有失败（仅观察本单不扩范围，已建单在案）。
