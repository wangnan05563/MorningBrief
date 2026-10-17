# 逐菜单 UX 评审与优化建议（news / MorningBrief）

> 任务：T02323（项目 news，工作空间 `D:\code\otherProjects\20_News`）
> 交付时间：2026-10-18　评审方式：**源码走查（只读）**，全程未修改任何源码、未启动服务、未触发任何有副作用的动作（隧道启动/通知发送/清理/删除/上传一律未执行）。

## 0. 评审口径

### 0.1 覆盖范围（不可跳过，逐界面成节）

| 界面族 | 数量 | 说明 |
|---|---|---|
| PC 管理端注册菜单 | **27** | `src/router/index.js` 中 `meta.title` 且非 `hidden` 的全部项，分 8 组：内容运营 7（内容审核/频道管理/素材库管理/讲书稿素材池/素材录入/找书工具/队列管理）、广告管理 3、数据分析 4、AI 自动化 3、系统配置 3、云端存储 2、维护工具 3、帮助 2 |
| PC 隐藏子页面 | 2 | 审核详情 `/review/:id`、工作流详情 `/workflows/:id` |
| 全局壳层与横切件 | 8 节 | 侧栏/页头 `Layout.vue`、根组件端切换 `App.vue`、`MobileLayout.vue` 壳层、路由与角色守卫与 404 兜底、新手引导体系（`guide/guideConfig.js`+`GuideOverlay.vue`+`useGuide.js`）、公共组件与 stores、`utils/message.js` 与 `api/index.js` 拦截器、样式硬编码采样 |
| 登录 | 2 | PC `/login`、移动 `/m/login` |
| 移动端适配模式 `/m/*` | 13 | 4 个 Tab（首页/审批/消息/我的）+ 管理入口 + 6 个管理子页（用户/反馈/频道/广告/队列/应急停服）+ 移动登录 |
| 微信小程序用户端 | 18 | `app.json` 注册页全部（含 3 个 tabBar 项、协议/隐私/关于/webview），另含组件与服务层采样 |
| 弹窗/抽屉/预览/空态 | 随各页 | 各切片页面内的小节（接管式弹窗、批量确认、dry-run 预览、上传/删除确认、图片弹窗、任务抽屉、候选池弹窗等）均单独成节 |

**逐节小节数 94 个**（按 `### ` 界面节计），问题条目合计 **634 条**：高 **142** / 中 **344** / 低 **148**；成本分布 XS **207** / S **340** / M **87**（无「重构级」，全部可在 ≤3 人日内落地）。

### 0.2 评审维度与方法

六个维度逐菜单检查，问题条目均标注维度编号：1 信息架构与命名 / 2 交互流程 / 3 视觉与布局 / 4 文案与提示 / 5 反馈与状态（加载、成功、失败、空数据）/ 6 一致性与规范。

- **取证**：每条问题带 `相对路径:行号`，可由人独立回读源码复核；跨页共性问题在 §12 汇总。
- **双视角**：「普通用户首次使用」（进得来、看得懂、知道下一步、错了能自查）与「高频运营/值班日常操作」（步数、批量、筛选复用、实时性、误操作防护）。
- **优先级**：高 = 功能不可用 / 数据被误读 / 不可逆风险或真实对外副作用 / 首次用户走不通；中 = 明显摩擦但有绕路；低 = 打磨。**成本**：XS <0.5 人日 / S ≤1 人日 / M ≤3 人日，优先推荐低成本高收益。
- **诚实边界**：视觉与布局（维度 3）只能通过模板与 style 推断，不能从源码断言的一律写「需实测确认」；凡涉及真实接口响应、后端状态码、微信真机渲染的结论同样标「需实测确认」，不当作已验证事实。

### 0.3 本次抽验（防假阳性）

142 条高危中，主评审逐条回读源码复验 **12 条**（下表 §12 内以「已复验」标注），其中 1 条为假阳性并已剔除（初稿称移动端应急停服引用「未定义变量」的表述不准——变量已声明，真实缺陷是 prompt 解构出 `value` 却使用了 `inputValidator` 形参名 `v`，见 R1）。余下条目由 11 个并行切片各自回读源码取证，未逐条二次复验，落地前建议按批次再抽。

### 0.4 章节编号与切片对照

逐菜单正文按走查切片成章（章号 1～11）；**问题 ID 的前缀字母即切片号**，例如 `M14` 在第 11 章、`D33` 在第 4 章，界面小节编号沿用切片内 `X-n`。第 12 章是跨章系统性根因，第 13 章是汇总优先级矩阵。

| 章 | 切片 | 覆盖界面 |
|---|---|---|
| 1 | A | 壳层、路由、引导与登录（横切件） |
| 2 | B | 内容运营 > 内容审核 / 队列管理 |
| 3 | C | 内容运营 > 频道管理 / 素材库 / 讲书稿池 / 素材录入 / 找书工具 |
| 4 | D | 广告管理 3 菜单 + 数据分析 4 菜单 |
| 5 | E | AI 自动化 > 工作流监控与详情 |
| 6 | F | AI 自动化 > AI 服务 / 智能助手 |
| 7 | G | 系统配置（内网穿透 / 通知 / 自动审批） |
| 8 | H | 云端存储（云端配置 / 文件管理） |
| 9 | I | 移动端适配模式 `/m/*` |
| 10 | J | 微信小程序用户端 |
| 11 | M | 维护工具（数据库维护 / 系统清理 / 参数计算器）+ 帮助（帮助文档 / 关于） |
| 12 | — | 跨菜单系统性根因 R1–R7 |
| 13 | — | 汇总优先级矩阵（高危主题 / 逐界面 / 排期 / 中低分布 / 无显著缺陷清单） |

---

## 1. 壳层、路由、引导与登录（横切件）

### A-1 一级：侧栏与页头壳层（路由：全部，文件：layouts/Layout.vue）
**现状描述**：侧栏菜单由 `router.options.routes` 的 children 按 `meta.group` 分组渲染（groupConfig 顺序决定展示顺序），`el-menu :router` 直接跳转，`unique-opened` 单开、`activeMenu`/`activeGroup` 高亮并在路由变化时 `menuRef.open()` 自动展开；折叠态把 logo 换成 `/favicon.svg`、分组收成 popup。页头仅一个 `currentTitle`（route.meta.title），右侧为调色板主题入口 + 用户下拉（头像/用户名/角色 tag/退出）。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A1 | 2 | 「新手指引」右下角按钮 `hasGuide` 仅当 `currentPath === '/help'` 才显示，其它菜单一旦跳过引导后无任何重新唤起入口，只能专门去「帮助文档」页 | apps/admin-web/src/layouts/Layout.vue:83-84,165,169-171 | 低 | XS |
| A2 | 3 | 折叠态 logo 用 `<img src="/favicon.svg">`，绝对根路径在 history base `/news/` 下不会被改写，部署到子路径可能 404 显示裂图（需实测确认） | apps/admin-web/src/layouts/Layout.vue:8 | 低 | XS |
| A3 | 1 | 页头无面包屑，仅单层标题；下钻到 `审核详情`/`工作流详情` 等 hidden 子页时用户看不到所属列表层级，也无返回上一级的壳层入口 | apps/admin-web/src/layouts/Layout.vue:37-71,244 | 低 | S |
| A21 | 6 | 角色 tag 用 `role === 'admin' ? 管理员 : 运营` 三元硬编码，任何非 admin 的角色值都被显示成「运营」，未来加角色会误读 | apps/admin-web/src/layouts/Layout.vue:60-62 | 低 | XS |
**优化建议**：
- A1：`hasGuide` 改为「全站显示、仅在 `!guide.isDone(currentPath)` 或当前有可重放引导时出现」，或在用户下拉里加固定「重放新手指引」项调用 `openGuide()`。
- A2：`<img :src="publicBase + 'favicon.svg'">`（`import.meta.env.BASE_URL`），与 Login 拼接 publicPath 的口径统一。
- A3：页头 `header-left` 增 `el-breadcrumb`，由 `route.matched` 生成「分组 / 列表 / 详情」，详情态提供「返回列表」链接。
- A21：抽 `roleLabelMap`（`{admin:'管理员', operator:'运营', ...}`），未知角色显示原始 role 或「未知」而非默认「运营」。

### A-2 一级：根组件端切换壳层（文件：App.vue）
**现状描述**：App.vue 用 `useIsMobile`（matchMedia <768px）+ `?mode=` 会话覆盖，onMounted/watch 两处 `router.replace` 在 PC(`/review`) 与移动(`/m/home`) 命名空间间互跳，`catch` 静默吞掉导航拒绝。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A4 | 2/6 | 跨端重定向只给固定落地页（`/m/home` 或 `/review`），不保留原 `to` 的 path 段与 query，深链 `/news/stats?tab=x` 在手机上被打开会被丢弃参数直接送到首页；`?mode=` 之外的业务参数全丢 | apps/admin-web/src/App.vue:32-54 | 中 | S |
| A5 | 2 | 桌面用户把浏览器窗口拖窄到 <768px（或分屏）会被强制 `replace` 到 `/m`，无「停留桌面」退路，误触发即离开当前 PC 页 | apps/admin-web/src/App.vue:44-57 | 低 | XS |
**优化建议**：
- A4：`resolveTarget` 返回带原 query 的目标（`{ path, query: route.query }`），并支持 `?redirect=` 记录用户真正想去的路由，切端后回填。
- A5：视口跨越断点时改为「提示条 + 点击切换」而非自动 `replace`，或仅首次进入时判定、之后锁定模式。

### A-3 一级：移动端壳层 tabBar/标题栏（文件：layouts/MobileLayout.vue）
**现状描述**：壳层为「标题栏(居中 title) + router-view + 底部 tabBar」；tabBar 由 `allTabs` 过滤 `adminOnly`，`active-class` 由 router-link 提供；标题取 `route.meta.title || titleMap[route.name] || '运营助手'`。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A6 | 2 | 标题栏无返回/后退按钮，下钻页（`/m/manage/users`、`feedback`、`channels` 等 hidden 子页）在壳层没有后退 affordance，只能靠再点底部「管理」tab 回 ManageHome，深层页会失去来路 | apps/admin-web/src/layouts/MobileLayout.vue:3-5,11-23 | 中 | S |
| A7 | 6 | `titleMap` 键为 `home/review/...`，而 route.name 实为 `MobileHome/MobileReview/...`，`titleMap[route.name]` 永远 undefined，回退名（如 '内容审批'/'消息中心'）从未生效；一旦某移动路由漏配 `meta.title` 即显示兜底 '运营助手' | apps/admin-web/src/layouts/MobileLayout.vue:47-57 | 低 | XS |
| A8 | 3 | 底部「管理」tab `to=/m/manage`，进入 `/m/manage/users` 等兄弟子路由后 router-link active 判定基于路由记录匹配而非路径前缀，高亮大概率丢失，用户看不出自己在哪个分区（需实测确认） | apps/admin-web/src/layouts/MobileLayout.vue:11-22 | 低 | XS |
| A24b | 3/6 | 移动壳层背景/文字/边框全用硬编码 `#f5f6f8`/`#1f2329`/`#ebedf0`/`#8a8f99`，与 PC 的 CSS 主题变量体系完全脱钩，showcase 暗黑主题下移动壳层仍是浅色 | apps/admin-web/src/layouts/MobileLayout.vue:66-67,77,112,117-118 | 低 | S |
**优化建议**：
- A6：标题栏左槽加「返回」图标，`router.back()` 或跳父级 `/m/manage`；非 tab 页显示返回、tab 页显示品牌。
- A7：删死表并把 `titleMap` 键改成真实 route.name，或直接删（meta.title 已全覆盖）。
- A8：tab active 改自定义判定 `route.path.startsWith(tab.to)`（`/m/manage` 覆盖其子页）。
- A24b：移动壳层颜色迁移到 `--color-*` 变量并纳入主题。

### A-4 一级：路由/分组/守卫/404（文件：router/index.js）
**现状描述**：菜单完全由路由 `meta.group/title/icon` 驱动；`beforeEach` 先放行 public，再以 `localStorage.admin_role` 作登录代理态，未登录跳 `/login`|`/m/login`，`requireRole==='admin'` 且非 admin 时 `ElMessage.error('仅管理员可访问') + next(false)`；根与 404 均 `redirect '/review'`，base `/news/`。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A9 | 1/6 | 文件头「菜单分组」注释与实际 meta 漂移：注释无「云端存储」分组（`cos-config`/`cos-files` 实际 group=云端存储），且「内容运营」只列 3 项实际含 7 项、「数据分析」只列 1 项实际含 4 项；维护者照注释新增会分错组 | apps/admin-web/src/router/index.js:8-16 vs 96-165 | 低 | XS |
| A10 | 2/5 | `requireRole` 命中非 admin 时 `next(false)` 中止导航：从侧栏外（直接输入 URL / 深链 / 刷新 `/workflows`）首次访问时 `from` 为起始，abort 后停留空白首屏只剩一条 toast，用户看不到「可去哪」，首用走不通 | apps/admin-web/src/router/index.js:322-327 | 中 | XS |
| A11 | 2 | 404/根统一 `redirect '/review'`：未登录访问坏链 → 跳 `/review` 被守卫再踢 `/login`；移动端坏链 `/:pathMatch` 也先被送到 PC 的 `/review`，再由 App.vue 回跳 `/m/home`，出现 PC 壳闪现与二次跳转 | apps/admin-web/src/router/index.js:30,295; App.vue:34-40 | 低 | S |
**优化建议**：
- A9：同步头注释分组清单（补「云端存储」、补全内容运营/数据分析子项），或改为注释只写「见 groupConfig」避免重复维护。
- A10：非授权深链改为 `next('/review')`（或跳登录/首页）+ toast，保证始终落到一个合法落地页，避免空白。
- A11：404 兜底按当前端分流（`/m` 前缀回 `/m/home`，否则回 `/review`），并让守卫在 redirect 目标已含前缀时不再二次跳转。

### A-5 一级：新手引导体系（GuideOverlay.vue / guideConfig.js / useGuide.js）
**现状描述**：`maybeGuide` 在路由变化时对 `GUIDE_STEPS[path]` 且 `!isDone` 延时 350ms `open`；浮层用 `document.querySelector(选择器)` 逐个试匹配，命中则加 outline+超大 box-shadow 高亮并把气泡定位到旁侧，未命中则气泡居中。完成态存 `localStorage.mb_guide_done`（值为 1）。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A12 | 3/4/6 | `/workflows` 引导第 2 步选择器 `[aria-label="立即触发一期工作流"]` 与其承诺文案「点击触发按钮…」指向的按钮不匹配：该 IconButton 实际 `aria-label` = `label="手动触发"`（desc 才是"立即触发一期工作流"，不进 aria-label），主选择器命中不到，回落 `.top-bar .el-button` 会高亮到 top-bar 里第一个按钮即「重置」，把用户指向错误按钮（该页还含危险的「全频道启动/手动触发」） | apps/admin-web/src/guide/guideConfig.js:69-73; views/workflow/WorkflowList.vue:54,67-75; components/IconButton.vue:20,71-72,93 | 高 | XS |
| A13 | 2/5 | `skip()`/关闭 X 只 `close()` 不 `markDone()`，仅点「完成」才记录；跳过引导的用户每次进入该菜单都被再次自动弹出（`maybeGuide` 只判 `!isDone`），构成重复打扰 | apps/admin-web/src/guide/useGuide.js:77-84; components/GuideOverlay.vue:5,12; layouts/Layout.vue:118-124 | 中 | XS |
| A14 | 3 | 遮罩 `.mb-guide-mask` 为 `position:fixed; inset:0; z-index:12000` 未设 `pointer-events:none`，与脚本注释「目标自身 box-shadow 天然不拦截点击」矛盾：走查期间高亮目标很可能被透明遮罩挡住无法点击，"引导里可点按钮"的观感落空（需实测确认） | apps/admin-web/src/components/GuideOverlay.vue:2,36-38,166-170 | 低 | XS |
| A15 | 5 | `maybeGuide` 固定 `setTimeout 350ms` 打开；列表页 `.el-table`/`.el-pagination` 依赖接口数据渲染，慢网下 350ms 时表格未出，`resolveTarget` 返回 null 走居中兜底，标题写着"审核操作/分页浏览"却没有高亮对象，用户看不到它在讲哪里 | apps/admin-web/src/layouts/Layout.vue:122; components/GuideOverlay.vue:76-85; guide/guideConfig.js:12-13 | 低 | S |
**优化建议**：
- A12：把选择器对齐真实 `aria-label`（改 `[aria-label="手动触发"]`），或给 IconButton 增加可被引导定位的显式 `data-guide`/完整 aria-label；建议全站引导目标改用稳定 `data-guide` 属性，避免依赖会漂移的中文名/aria-label。
- A13：`skip()`/`close()` 也调用 `markDone(currentPath)`（或记 `dismissed`），把"再看"只留给右下角按钮，杜绝重复自动弹。
- A14：`.mb-guide-mask{pointer-events:none}`、仅气泡卡 `pointer-events:auto`，让高亮目标在走查中可点，兑现注释意图；若确需阻断则改文案别声称可点。
- A15：`resolveTarget` 未命中时改为轮询等待目标出现（如 MutationObserver/最多 2s）再高亮，超过阈值则整段跳过该步而非居中静放。

### A-6 一级：公共组件与 stores / message（ThemeSwitcher, IconButton, VoiceSyncButton; stores/theme, stores/user; utils/message）
**现状描述**：ThemeSwitcher 6 卡片点击即 `applyTheme` 并弹 success；IconButton 统一图标+tooltip(label：desc)+aria-label(=label)；VoiceSyncButton 拉官方音色、绿点标识来源、reset 有确认。theme 存 `admin_theme`、user 存 `admin_username/admin_role`。message.js 是所有 ElMessage/ElMessageBox 的包装，页面隐藏或刚恢复 2s 内丢弃。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A16 | 5 | 提示包装器在 `document.hidden` 或重新可见后的 2s `_isRestoring` 窗口内，把所有 success/error/warning 直接 `return` 丢弃、且 confirm 转为 reject：切走标签页期间的接口失败/成功反馈永久不再补发，构成系统性静默失败（本项目历史高频缺陷类） | apps/admin-web/src/utils/message.js:16-28,38-58 | 高 | S |
| A18 | 5 | VoiceSyncButton `loadMeta` 的 catch 把 meta 静默重置为 `is_custom:false`（内置态）且不额外提示：当"官方同步"列表的 meta 接口偶发失败时，绿点消失、标题变"内置静态清单"，用户会误判当前音色来源（数据被误读） | apps/admin-web/src/components/VoiceSyncButton.vue:87-97 | 中 | XS |
| A17 | 6 | theme.js 头注释宣称「跨标签页（storage 事件）保持一致」，但全文件无 `addEventListener('storage')` 监听：A 标签切主题、B 标签不更新直到刷新，注释与实现漂移 | apps/admin-web/src/stores/theme.js:7,92-96 | 低 | XS |
**优化建议**：
- A16：隐藏期把待发消息入队（error/success 各留最近若干条），恢复可见时 flush；`_isRestoring` 的 2s 全量抑制窗口应仅抑制"唤醒类"提示而非业务反馈。confirm 被抑制时不要静默 reject，改为「页面不可见 → 不做破坏性动作」的显式保护并留痕。
- A18：`loadMeta` 失败区分「未同步」与「加载失败」，失败时保留上次 `is_custom` 并显示"来源状态待确认/重试"，不要降级成"内置"误导。
- A17：补 `window.addEventListener('storage', …)` 在 key==admin_theme 时 `applyTheme`，或删掉误导性注释。

### A-7 一级：登录（views/login/Login.vue, views/mobile/Login.vue）
**现状描述**：PC 卡片磨砂玻璃+声波背景，`el-form` 校验后 `userStore.login`，成功 `ElMessage.success('登录成功')` 再 `push('/review')`；mobile 原生 input+按钮，空值 warning，成功 `replace('/m/home')`。两者 catch 均依赖拦截器报错、自身不提示。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A19 | 5 | 登录失败反馈缺失：拦截器 401 分支只清 localStorage 并「不在登录页才跳登录页」，既不弹 ElMessage 也不给用户可见原因；而登录请求失败正发生在登录页（pathname==loginPath 不跳），导致用户名/密码错误时（若后端返回 401）用户只看到 loading 结束、无任何提示，首次用户走不通（需实测确认后端登录失败的 HTTP 状态码；若返回 200+code!=0 则会正常提示） | apps/admin-web/src/api/index.js:52-61; views/login/Login.vue:141-150; views/mobile/Login.vue:49-56 | 高 | XS |
| A20 | 2 | PC 登录成功硬跳 `/review`：被 `requireRole`/401 挡回登录后重新登录也固定回审核页，不记住用户原想去的目标，深链登录后丢失上下文 | apps/admin-web/src/views/login/Login.vue:145 | 低 | XS |
| A25 | 3/6 | 移动端主色用 `var(--el-color-primary, #409eff)` 兜底科技蓝，与 PC macaron 主色薄荷青(#7ECEC1)体系脱节；PC 登录随 6 主题变化，移动登录恒为浅蓝，跨端品牌观感不一致 | apps/admin-web/src/views/mobile/Login.vue:75,103,116; styles/variables.scss:13 | 低 | S |
**优化建议**：
- A19：登录调用显式传 `silent:false` 并在 login catch 内自持一条 `ElMessage.error('用户名或密码错误')`，不依赖拦截器 401 分支；或在拦截器把 401 且已在登录页的情况改为弹后端 message。二选一即可消除空白反馈。
- A20：`beforeEach` 未登录时把 `to.fullPath` 存为 `?redirect=`，登录成功后优先跳 redirect。
- A25：移动壳层与移动登录纳入同一 `--color-*` 主题变量，避免主色兜底漂移。

### A-8 一级：长尾共性采样（api/index.js 错误收敛 + styles 硬编码漂移）
**现状描述**：axios 响应拦截把 `{code,message,data}` 解包，`code!==0` 与非 401/403 的 HTTP 错误统一 `ElMessage.error(message||'请求失败')`；401 清态跳登录。styles 三件套以 CSS 变量为真源，但多个组件仍散落硬编码色值/字号。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| A22 | 5/4 | 所有接口失败被收敛成"同一条瞬时 toast"：网络/超时错误直出英文 `error.message`（如 `timeout of 15000ms exceeded`/`Network Error`）给中文用户；`reject(new Error(message))` 丢失 code 使调用方无法分支；多条并发失败会堆叠多条 toast 无聚合/去重 | apps/admin-web/src/api/index.js:39-71 | 中 | S |
| A23 | 3/6 | 引导悬浮按钮 `guide-fab` 背景用 `var($color-primary)` 但阴影硬编码蓝 `rgba(37,99,235,.35)`、文字硬编码 `#fff`：macaron 薄荷主色按钮挂蓝色阴影，配色与主题脱节 | apps/admin-web/src/layouts/Layout.vue:269-270,273 | 低 | XS |
| A24 | 3/6 | ThemeSwitcher 激活卡片选中环硬编码马卡龙色 `rgba(126,206,193,.15)`（不随所选主题变化），预览卡背景又硬编码 `#1E1E2A`/`#FFFFFF`，切到 commerce/portfolio 时选中态仍是薄荷青 | apps/admin-web/src/components/ThemeSwitcher.vue:89-90,121-122 | 低 | XS |
| A25b | 3/6 | 引导浮层整套色板硬编码（`#2563eb` 蓝主按钮、灰阶 `#111827/#4b5563`），独立于 6 主题；暗黑 showcase 主题下引导气泡仍为纯白卡，风格割裂 | apps/admin-web/src/components/GuideOverlay.vue:171-256 | 低 | S |
| A26 | 6 | 字号无令牌化：`variables.scss` 未定义字阶，各处散落 `11/13/14/16/20/28px` 硬编码（页标题 16、logo 20、tab 标签 11、metric 28 等），改字号规范需全站翻找 | apps/admin-web/src/styles/variables.scss:32-36; layouts/Layout.vue:301,382; MobileLayout.vue:114; styles/global.scss:43,49 | 低 | S |
**优化建议**：
- A22：错误归一层——网络/超时映射为中文文案（"网络超时，请重试"），reject 保留 `Object.assign(err,{code,status})` 供调用方分支；同屏并发失败用去重（相同 message 合并计数）。
- A23/A24/A25b：把 `guide-fab`、ThemeSwitcher 选中环、引导浮层的强调色统一走 `--color-primary`/`--color-text-*` 令牌，气泡按 `[data-theme]` 或 `isDark` 切深浅底。
- A26：新增 `--font-size-xs/sm/base/lg/xl` 令牌，逐步替换散落 px，收敛到 SCSS 变量映射。

---

## 2. 内容运营 > 内容审核 / 队列管理

> 走查范围：菜单分组「内容运营」核心操作链（内容审核列表 / 审核详情 / 队列管理）及其 API 层与音频组件调用侧。
> 后端状态定义对照：`backend/app/models/review.py:14-17`（ReviewStatus = pending/approved/rejected/**replaced**）、`backend/app/models/workflow.py:51`（workflow status = queued/running/success/failed/cancelled）、`backend/app/models/workflow.py:85`（step status = pending/running/success/failed/**retrying**）、`backend/app/services/review_service.py:250-285`（已处理不可重复操作、BATCH_MAX_SIZE=50）。
> 只读走查，未运行/构建；视觉结论凡不能从 template/style 直接判定处标「需实测确认」。

---

### B-1 内容运营 > 内容审核 · 列表主体（路由 /review，文件 apps/admin-web/src/views/review/ReviewList.vue）

**现状描述**：三 tab（待审核/已通过/已打回）按 `status` 过滤，后端分页返回，列表展示日期/工作流ID/状态/时长/审核人/创建时间，行内仅有「审核」按钮跳详情。整体结构清晰，但筛选能力、分页与 URL 承载、后端第 4 态的呈现存在缺陷。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| B1 | 1/6 | 后端 `ReviewStatus` 有第 4 态 `replaced`，但列表只有 3 个 tab（pending/approved/rejected），`statusText/statusTagType` 也无 `replaced` 映射。详情页做「替换段落」后该记录状态变 `replaced`，从所有 tab 消失，运营再也找不到、无法追溯，误以为数据丢失 | apps/admin-web/src/views/review/ReviewList.vue:4-7,180-186；backend/app/models/review.py:14-17；backend/app/services/review_service.py:269 | 高 | S |
| B2 | 2/6 | tab、page、size 全为组件态，不写 URL：刷新/前进后退后回到「待审核+第1页」，无法深链或分享「已通过第 3 页」，处理到一半刷新即丢失上下文 | apps/admin-web/src/views/review/ReviewList.vue:140-144,152-174 | 中 | S |
| B3 | 2 | 分页 `size` 固定 10 且无 `:page-sizes` 选择器（layout 仅 prev/pager/next/total）：每天几百条时只能 10 行/页反复翻页，高频操作步数被放大 | apps/admin-web/src/views/review/ReviewList.vue:106-113,144 | 中 | XS |
| B4 | 2 | 列表无任何筛选区（按 workflow_id/日期/审核人/频道搜索均缺失），而后端 `list_reviews` 支持 `workflow_id` 过滤；高频定位单条只能盲翻页 | apps/admin-web/src/views/review/ReviewList.vue:39-115；backend/app/routers/admin/reviews.py:43-48 | 中 | S |
| B5 | 4 | 空态文案对所有 tab 硬编码「暂无待审核稿件」：切到「已通过/已打回」tab 且无数据时仍显示「待审核稿件」，误导 | apps/admin-web/src/views/review/ReviewList.vue:102 | 低 | XS |
| B6 | 5 | `loadList` 失败仅依赖拦截器弹 toast，`catch{}` 后 `list/total` 保持旧值不清空、无上屏错误态/重试按钮；用户难以区分「刷新失败但残留旧数据」与「正常」 | apps/admin-web/src/views/review/ReviewList.vue:152-165 | 中 | S |
| B7 | 1 | 状态列的「系统」自动审批标记为单字词、无 tooltip，首次用户不知其含义（=系统自动通过）；`auto_trigger_reason` 后端已返回但列表/详情均不展示 | apps/admin-web/src/views/review/ReviewList.vue:60-68；backend/app/services/review_service.py:178 | 低 | XS |

**优化建议**：
- B1：新增第 4 个 tab「已替换」（或并入「已打回」并在状态文案区分），补齐 `statusText('replaced')='已替换'`、`statusTagType('replaced')`；并在「替换段落」成功后落一个可见去向。
- B2：用 `route.query`（tab/page/size）承载列表态，`onMounted` 从 query 初始化，切换即写 query；`ReviewDetail` 返回列表时携带来源 tab/page。
- B3：分页 `layout` 增加 `sizes`，`:page-sizes="[10,20,50]"`，与队列页保持一致口径。
- B4：列表顶部加筛选区（workflow_id/日期区间/审核人），透传后端已支持的 `workflow_id`。
- B5：空态文案随 `activeTab` 动态：待审核/已通过/已打回分别「暂无…」。
- B6：`catch` 中置 `list=[]` 并显示「加载失败，点击重试」的表内错误态（区别于空态），保留拦截器 toast。
- B7：「系统」标记改为 `el-tooltip` 说明「系统自动审批」，并在 `auto_trigger_reason` 存在时展示命中条件。

---

### B-2 内容运营 > 内容审核 · 批量操作栏与确认弹窗（apps/admin-web/src/views/review/ReviewList.vue:10-37,212-287）

**现状描述**：批量栏仅在「待审核」tab 出现，有「已选 N 条」汇总，通过走 `ElMessageBox.confirm`（含自动发布说明）、打回走 `prompt` 收集统一理由，结果按 成功/跳过/失败/发布失败 分类提示。危险动作有确认，基本盘较稳，但跨页选择与不可逆口径有缺口。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| B8 | 2/6 | 选择列无 `row-key`+`reserve-selection`（对照队列页 QueueManagement.vue:118-119）：`loadList` 每次替换 `list.value` 会清空前页勾选，跨页多选不可用；批量时表头全选也只选当前页可见行。每天几百条要逐页反复勾选 | apps/admin-web/src/views/review/ReviewList.vue:39-51,195-197 | 中 | S |
| B9 | 2/6 | 后端 `BATCH_MAX_SIZE=50` 且超限「拒绝整批」，前端选中数无上限校验：若将来放开跨页/大页选中超 50，`confirm` 后才报错、整批不生效，用户体验割裂 | apps/admin-web/src/views/review/ReviewList.vue:212-245；backend/app/services/review_service.py:285,309-313 | 中 | XS |
| B10 | 4/2 | 通过/打回均**不可逆**（后端拦截非 pending 记录「该审核记录已处理」），但确认文案只说「将自动发布」/收集理由，未提示「不可撤销」；对照本页无、队列批量删除有明确「此操作不可撤销」，口径不一致 | apps/admin-web/src/views/review/ReviewList.vue:217-221,254-256；backend/app/services/review_service.py:250-251 | 中 | XS |
| B11 | 5/6 | `handleBatchApprove/Reject` 的业务调用只有 `try/finally` 无 `catch`：接口失败时 Promise 被 reject 冒泡为未处理拒绝（仅拦截器瞬时 toast），选中项未清理（可重试点，尚可）但无任何界面级失败态 | apps/admin-web/src/views/review/ReviewList.vue:228-244,272-287 | 低 | S |

**优化建议**：
- B8：给选择列加 `:reserve-selection="true"` + 表 `row-key="id"`，切换 tab 时显式 `clearSelection`（已有）。
- B9：点击批量前校验 `ids.length<=50`，超限直接提示「单次上限 50，请减少选择」，不发请求。
- B10：在批量通过/打回确认文案中补「此操作不可撤销，记录将移出待审核」，与队列删除同口径。
- B11：`try/catch/finally` 补 `catch`，失败时保留选中并给出可重试的界面提示。

---

### B-3 内容运营 > 审核详情 · 子页面（路由 /review/:id，hidden，文件 apps/admin-web/src/views/review/ReviewDetail.vue）

**现状描述**：左侧稿件全文+引用素材+采集图片，右侧 `<audio>` 试听 + 审核操作表单（通过/打回/替换段落，动态显隐理由/段落选择），提交前二次确认，成功后回 `/review`。信息分区合理，但音频试听可用性、可访问性、已处理态可见性是关键缺陷。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| B12 | 5/2 | 试听用原生 `<audio :src="detail.audio_url">` 直连远端 URL，未走 `getEpisodeAudioUrl/getAudioProxyUrl` 代理（这些助手仅 WorkflowDetail 在用）。打包/COS 态成品音频在私有桶、需 JWT+代理，直连会 403/CORS 失败且**无任何错误提示**：审核员看不到真实语音就盲批。缺 `@error` 处理、无加载态、无时长/采样点读数、无「重听」快捷 | apps/admin-web/src/views/review/ReviewDetail.vue:99-100；apps/admin-web/src/api/audio.js:5-11,65-69；对照 apps/admin-web/src/views/workflow/WorkflowDetail.vue:804-805 | 高 | M |
| B13 | 6 | `.audio-player{outline:none}` 抹掉原生播放器键盘焦点环：键盘操作虽可用但焦点不可见，可访问性退化，与全站 IconButton 保留 `aria-label` 的规范不一致 | apps/admin-web/src/views/review/ReviewDetail.vue:351-354 | 中 | XS |
| B14 | 1/5 | 后端详情已返回 `auto_approved/auto_trigger_reason/reviewer_name/reviewed_at`，但详情页头仅显示 日期/工作流ID/状态，均不展示；对已处理（尤其自动审批）记录看不到谁审/为何/何时。且已处理记录的动作 radio 仍可提交，点提交→确认→才收到「该审核记录已处理」错误，空耗一次往返 | apps/admin-web/src/views/review/ReviewDetail.vue:5-11,109-113；backend/app/services/review_service.py:177-180,250-251 | 中 | S |
| B15 | 6 | `statusText/statusTagType` 同样缺 `replaced` 映射：直接进 `/review/:id` 打开一条 `replaced`/其它态记录时，状态标签显示英文原文「replaced」+灰 info 标签 | apps/admin-web/src/views/review/ReviewDetail.vue:216-222 | 中 | XS |
| B16 | 2/4 | 「替换段落」确认仅泛化文案「确认执行「替换段落」操作？」，未说明后果（后端置状态=replaced 且不再出现在任何 tab，见 B1），审核员不知记录会「消失」 | apps/admin-web/src/views/review/ReviewDetail.vue:189-191,265-269 | 中 | XS |
| B17 | 2 | 成功动作后恒 `router.push('/review')`，列表无 URL 态（B2）→ 每次提交都被打回「待审核第1页」，高频审核员每审一条都要重新导航回到原处 | apps/admin-web/src/views/review/ReviewDetail.vue:204 | 中 | S |
| B18 | 4 | `reason` 文本域无 `maxlength`/字数计数/必填说明；打回理由对下游编导是关键信息却无长度约束提示 | apps/admin-web/src/views/review/ReviewDetail.vue:125-127 | 低 | XS |

**优化建议**：
- B12：详情页试听改用 `getEpisodeAudioUrl(workflowId, remoteUrl)`/`getAudioProxyUrl` 取 blob URL，`<audio>` 绑 ObjectURL，并加 `@error`→上屏「音频加载失败，点此重试」+ 加载 spinner；补自定义播放条显示时长与采样点、提供「从头重听」。与 WorkflowDetail 统一播放器实现。
- B13：移除 `outline:none` 或改为可见 `:focus-visible` 环。
- B14：详情头/侧栏补「审核人/审核时间/自动审批来源+触发条件」；对非 pending 记录禁用动作区并提示「已处理，仅供查看」。
- B15：同 B1，补 `replaced` 文案与色。
- B16：替换确认文案明确「提交后本记录状态置为『已替换』，将不再出现在待审核列表」。
- B17：`router.push('/review?tab=pending&page=N')`，配合列表 URL 态回原位；或提交后留在详情仅刷新。
- B18：`reason` 加 `maxlength` 与字数统计、必填红星提示。

---

### B-4 内容运营 > 审核详情 · 采集图片与「查看全部」弹窗（apps/admin-web/src/views/review/ReviewDetail.vue:32-90）

**现状描述**：图片卡片默认展示前 9 张缩略图，超量时出现「查看全部图片」→ 840px 弹窗全显、可点击放大预览；空时 `el-empty「本篇稿件引用的素材没有采集到图片」`，加载失败有 fallback。整体体验完整。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| B19 | 3 | 弹窗网格 `max-height:60vh` 内部滚动 + `el-image` 预览 `preview-teleported`，缩略图与预览层焦点/滚动是否冲突、窄窗换行表现需实测确认 | apps/admin-web/src/views/review/ReviewDetail.vue:70-90,339-345 | 低 | XS |
| B20 | 6 | 缩略图 `:key="url"` 在图片 URL 可能重复（同一图被多素材引用）时 key 冲突告警风险；建议索引兜底 | apps/admin-web/src/views/review/ReviewDetail.vue:51-52,72-73 | 低 | XS |

**优化建议**：
- B19：弹窗预览实测后视需要设 `overflow` 与关闭时 `hide-on-click-modal` 行为校验；窄屏验证一行缩略图数量。
- B20：`:key` 用 `i` 或 `url+i` 避免重复 URL 冲突。
- 其余：未发现显著体验缺陷。替代优化：图片卡片可在计数处对 `image_total>images.length`（若后端截断）加「部分展示」提示。

---

### B-5 内容运营 > 队列管理 · 主体（路由 /queue，文件 apps/admin-web/src/views/queue/QueueManagement.vue）

**现状描述**：顶部 4 状态统计卡、执行模式配置面板、状态/频道/优先级筛选、任务表格（多选+排序+行级取消/改优先级/重试/详情）、分页（含 page-size）、SSE+自适应轮询。工程细节（reserve-selection、行级 Set loading、轮询清理）做得扎实，主要风险在「失败静默回落正常态」。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| B21 | 5 | `listQueueTasks` 标 `silent:true`（拦截器不弹错），`loadTasks` catch 回落 `tasks=[],total=0`：初始加载/筛选/排序失败时直接显示「暂无队列任务」空态，后端宕机被**误读为空队列**（本项目历史高频缺陷） | apps/admin-web/src/views/queue/QueueManagement.vue:387-409；apps/admin-web/src/api/queue.js:11 | 高 | S |
| B22 | 5 | `loadStats` 失败静默且 `stats={}`→四张统计卡全显 0（含「已完成 0」），宕机时呈现「健康空队列」观感，无任何错误/加载失败标记 | apps/admin-web/src/views/queue/QueueManagement.vue:4-29,344-350 | 中 | S |
| B23 | 5/6 | `loadConfig` 失败回落默认 `serial/1` 且不上屏；若线上实际为 parallel/N，界面显示 serial/1，运维一次「保存配置」即 `PUT` serial/1 覆盖真实并发配置→误写生产 | apps/admin-web/src/views/queue/QueueManagement.vue:352-375；apps/admin-web/src/api/queue.js:18-19 | 中 | S |
| B24 | 6 | 步骤时间线用 `statusLabel(step.status)`，但 step 状态枚举含 `pending/retrying`（workflow.py:85），而 `STATUS_LABEL_MAP/STATUS_TAG_MAP` 只覆盖 workflow 级 queued/running/success/failed/cancelled→步骤里 `pending`/`retrying` 直接显示英文原文+info 灰标 | apps/admin-web/src/views/queue/QueueManagement.vue:211,215,252-271；backend/app/models/workflow.py:85 | 中 | XS |
| B25 | 2/6 | 筛选（status/channel_id/priority）、page、size、排序均不落 URL：刷新丢全部筛选与页码，无法深链协作 | apps/admin-web/src/views/queue/QueueManagement.vue:282-289,178-186 | 中 | S |
| B26 | 2 | 轮询对用户无「暂停/停止」开关：虽有 document.hidden/keep-alive 自动停（604-619，值得肯定），但运维想把视图冻结细查某行时无暂停按钮 | apps/admin-web/src/views/queue/QueueManagement.vue:545-557 | 低 | S |
| B27 | 5 | 「保存配置」`updateQueueConfig` 无 catch：失败靠拦截器瞬时 toast，但 `config` 单选/滑杆仍停在未保存的乐观值，界面显示与服务端不一致且无回退 | apps/admin-web/src/views/queue/QueueManagement.vue:363-375 | 中 | XS |
| B28 | 2 | 「改优先级」popover 对 success/failed/cancelled 行也常驻可点（无 status 限定），对已结束任务改优先级无意义却可操作 | apps/admin-web/src/views/queue/QueueManagement.vue:146-155 | 低 | XS |

**优化建议**：
- B21：区分「手动加载（初始/筛选/排序）」与「后台轮询」——手动加载失败时临时传 `silent:false` 或本地置错误态、显示「加载失败，点击重试」而非空态；轮询失败仍静默但可在表头保留「最后更新时间」并标红。
- B22：统计卡加载失败显示占位「—」+错误态样式，避免与真实 0 混淆。
- B23：`loadConfig` 失败显式提示「配置读取失败，保存前请重试加载」，并在未成功加载前禁用「保存配置」。
- B24：`STATUS_LABEL_MAP/STATUS_TAG_MAP` 增加 step 级 `pending:'待执行'`、`retrying:'重试中'` 映射（或对 step 与 workflow 各用独立映射）。
- B25：筛选/分页/排序写入 `route.query` 并从 query 初始化。
- B26：配置区加「实时刷新」开关，关闭时暂停轮询与 SSE 刷新。
- B27：`saveConfig` 补 catch，失败回退为上次成功加载值并提示。
- B28：仅对 queued/running 行展示「改优先级」。

---

### B-6 内容运营 > 队列管理 · 任务详情抽屉与步骤时间线（apps/admin-web/src/views/queue/QueueManagement.vue:190-224）

**现状描述**：点「详情」打开抽屉，`el-descriptions` 展示任务元信息 + `el-timeline` 展示步骤时间线，含步骤状态 tag 与起止时间，无步骤时 `el-empty「暂无步骤数据」`。展示结构清晰，但数据源新鲜度存疑。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| B29 | 2/5 | `openDetail` 直接把列表行对象赋给 `currentTask`，不二次拉详情：抽屉数据是列表快照，且轮询替换 `tasks.value` 后抽屉仍指向旧对象→运行中任务的步骤/耗时不更新；且列表接口是否返回 `steps` 决定时间线是否常显「暂无步骤数据」（需实测确认） | apps/admin-web/src/views/queue/QueueManagement.vue:496-499,206-222；apps/admin-web/src/api/queue.js:11 | 中 | S |
| B30 | 3 | 运行中步骤 `finished_at` 为空时显示「进行中」，但整抽屉无加载/自动刷新指示，用户不知抽屉数据是否会自行变化 | apps/admin-web/src/views/queue/QueueManagement.vue:217-219 | 低 | XS |

**优化建议**：
- B29：打开抽屉按 `id` 调单任务详情接口（若后端提供），或从 `tasks` 里按 id 取当前对象保持引用同步；无 steps 的接口应显式提示「打开详情以加载步骤」。
- B30：抽屉内运行中任务加轻量刷新/「最后更新 x 秒前」。

---

### B-7 API 封装层口径一致性（apps/admin-web/src/api/reviews.js · queue.js · audio.js · scripts.js）

**现状描述**：各 API 封装薄、注释到位；`audio.js` 对大文件 blob/代理/超时/重试处理严谨；`queue.js` 对轮询接口标注 silent 合理。存在少量调用路径不一致。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| B31 | 6 | 同一 `/reviews/:id/action` 端点有两条调用路径：详情组件直接 `api.post(...)` 手写 payload（ReviewDetail.vue:202），而 `reviews.js` 提供的 `handleReviewAction` 助手无人使用→请求体口径易漂移 | apps/admin-web/src/api/reviews.js:15-16；apps/admin-web/src/views/review/ReviewDetail.vue:199-202 | 低 | XS |
| B32 | 1 | `scripts.js`、`audio.js` 的取音频/取稿能力在审核详情未接入（详情稿/音频都在 review payload 里），`audio.js` 代理助手也只在 WorkflowDetail 用→审核员试听无 JWT/COS 兜底（见 B12） | apps/admin-web/src/api/audio.js:65-85；apps/admin-web/src/views/review/ReviewDetail.vue:99 | 中 | M |

**优化建议**：
- B31：详情改用 `handleReviewAction` 助手，统一请求体。
- B32：详情试听接入 `getEpisodeAudioUrl/getAudioProxyUrl`（同 B12）。
- 其余：`queue.js` 分页/筛选/配置字段（execution_mode/max_concurrent/items）与后端对齐，未发现显著体验缺陷；替代优化为在 `listQueueTasks` 增加可选 `silent` 入参，便于 B21 区分手动/轮询。

---

### B-8 音频/试听组件调用侧（VoiceSyncButton）

**现状描述**：经全量检索，`VoiceSyncButton` 仅被 `apps/admin-web/src/views/ai/AIConfig.vue:842` 引用（TTS 音色官方同步按钮），**未被内容审核列表/详情/队列任一页调用**；其职责为音色清单同步，与审核试听链无交集。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| — | — | 未发现显著体验缺陷（不在本切片调用链上；其自身同步失败已有 `ElMessage.error` 上屏，非仅 console，见 VoiceSyncButton.vue:114-119） | apps/admin-web/src/components/VoiceSyncButton.vue:99-120 | 低 | — |

**优化建议**：无需在本切片处理；本切片「音频重试进度」的实际缺口是详情页原生 `<audio>` 无加载/失败反馈（见 B12/B32），应优先在详情页补进度与错误反馈，而非引入本组件。

---

**条数统计（B1–B32，共 32 条）**：
- 高 3：B1（已替换态记录从所有 tab 消失）、B12（试听直连远端 URL，COS 态不可用/无错误反馈致盲批）、B21（队列列表加载失败静默回落「空态」，宕机被误读为无任务）。
- 中 19：B2、B3、B4、B6、B8、B9、B10、B13、B14、B15、B16、B17、B22、B23、B24、B25、B27、B29、B32。
- 低 10：B5、B7、B11、B18、B19、B20、B26、B28、B30、B31。
- 维度分布（同一问题可跨维度，按主维度计）：交互流程/一致性(2/6)与反馈/状态(5)占多数，命中本项目历史高频缺陷（失败静默回落正常态、URL 态缺失、后端枚举漂移 replaced/step retrying）。

---

## 3. 内容运营 > 频道管理 / 素材库 / 讲书稿池 / 素材录入 / 找书工具

> 范围：内容运营分组下「频道管理 → 素材库管理 → 讲书稿素材池 → 素材录入 → 找书工具」五页及其弹窗/抽屉/空态；评审方式为只读源码走查（Vue 模板 + script + `src/api/*` + `backend/app/routers/admin/*` 交叉比对），未运行构建或服务。视觉类判断仅从模板/样式推断处已标注「需实测确认」。
> 全链路角色预设：运营的日常动作是「找一本书 → 下载 → 上传入库 → 加进书单 → 配频道模式」，任一环节称谓或字段漂移都会直接放大误操作概率。

---

### C-1 内容运营 > 频道管理（路由 /channels，文件 apps/admin-web/src/views/channel/ChannelManagement.vue）

**现状描述**：单页「工具条 + 一张 12 列表格 + 一个四页签编辑弹窗」，1430 行中约 550 行模板、约 690 行脚本，是本项目最大页面。列表无搜索、无筛选、无分页，所有频道一次性平铺，行内唯一可改字段是「状态」开关，其余 11 类配置全部收在编辑弹窗内。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| C1 | 1 | 频道列表没有任何检索/筛选入口（无关键词、无类型、无启用状态筛选、无分页），频道数量增长后运营只能靠肉眼在平铺表里找目标行；同组的素材库管理却有 5 个筛选条件，同类列表页能力口径不一 | apps/admin-web/src/views/channel/ChannelManagement.vue:8-9；对比 apps/admin-web/src/views/channel/MaterialLibrary.vue:28-70 | 中 | S |
| C2 | 3 | 表格实际 12 列（名称/描述/类型/广告/定时触发/段间静音/段间BGM/状态/展示排序/素材回溯/创建时间/操作），min-width 累加约 1400px 以上，操作列 `fixed="right"` 后中段配置列必然横向滚出视野；页面无列设置/列隐藏能力，"段间静音/段间BGM/素材回溯/创建时间"这类低频列长期挤占主视区（具体断点需实测确认） | apps/admin-web/src/views/channel/ChannelManagement.vue:10-77（fixed 列 72） | 中 | M |
| C3 | 1 | 频道最关键的两项运行态「讲书稿模式是否开启」「书单进度」在列表完全不显示，只有 `类型=有声读物` 标签；运营要确认某频道走不走素材池，必须 打开编辑弹窗 → 切「采集与选题」页签 → 看开关，三跳才能读到本该一屏可见的状态 | apps/admin-web/src/views/channel/ChannelManagement.vue:12-18,302-324（模式开关位于弹窗内） | 中 | M |
| C4 | 6 | 编辑弹窗「展示排序」提示写「数值越小越靠前（小程序/首页 tab 顺序）」，但后台列表接口固定 `order_by(Channel.id)`，管理页表格显示的顺序与配置语义无关；运营会误以为"调整排序后本列表会重排"，从而怀疑保存失败 | apps/admin-web/src/views/channel/ChannelManagement.vue:110-119；backend/app/services/channel_service.py:40-42 | 中 | XS |
| C5 | 5 | `loadList()` 只有 `try/finally`，接口失败时既不提示也不区分错误：`list` 保持空数组，表格落到空态「暂无频道，点击右上角『新增频道』创建」——把服务异常渲染成"数据不存在"，首次用户会当真去新建重复频道 | apps/admin-web/src/views/channel/ChannelManagement.vue:675-684,78 | 高 | S |
| C6 | 2 | 行内「状态」`el-switch` 无 loading、无 disabled 窗口期，可被连续点击并发多次 `PUT /channels/{id}`；失败仅回滚 `row.is_active`，用户看不出这次切换是否已生效。同时该字段与弹窗内「启用」开关是两套保存时机（行内即时保存 / 弹窗需点「确认」），页面未作任何说明 | apps/admin-web/src/views/channel/ChannelManagement.vue:50-57,1060-1069；107-109 | 中 | S |
| C7 | 4 | 「定时触发」列空值显示灰色「默认」，而弹窗同字段提示是「为空则使用全局 cron（05:00）触发」；列表读者无法从「默认」得知实际触发时刻，做"今天为什么没生成"这类排障时信息不足 | apps/admin-web/src/views/channel/ChannelManagement.vue:25-30,191-194 | 中 | XS |
| C8 | 3 | 「广告」列同一列出现两种形态：`enable_ad===0` 显示 `el-tag`「关闭」，否则显示纯文本「投放」（无标签），扫表时"有标签=异常"的直觉与语义相反 | apps/admin-web/src/views/channel/ChannelManagement.vue:19-24 | 低 | XS |
| C9 | 6 | 三种"未配置"文案在一张表里并存：段间静音/段间BGM/素材回溯用「继承全局」「继承动态」，定时触发用「默认」；弹窗内同类字段又写「留空使用全局配置」「继承全局（AI 服务页设置）」，同一语义至少 5 种说法 | apps/admin-web/src/views/channel/ChannelManagement.vue:28,36,44,65；208,252,275,380,473 | 低 | S |
| C10 | 2 | 删除频道的二次确认只写「确认删除频道「X」？此操作不可恢复。」，未披露真实连带后果：讲书稿书单按外键 `ON DELETE CASCADE` 整本删除、素材行 `channel_id` 无外键约束会变成无主数据（列表/聚合视图永久筛不到）。运营在误删后无法预判损失范围 | apps/admin-web/src/views/channel/ChannelManagement.vue:1071-1093；backend/app/models/book_pool.py:30-31；backend/app/models/material.py:76；backend/app/services/channel_service.py:282-304 | 高 | S |
| C11 | 6 | 权限判定两套实现：本页直接读 `localStorage.getItem('admin_role')`（模块级常量，非响应式），素材库管理用 `useUserStore().role`；后续若登录态变更或角色由后端下发，本页按钮显隐不会跟随 | apps/admin-web/src/views/channel/ChannelManagement.vue:565-566；apps/admin-web/src/views/channel/MaterialLibrary.vue:332-333 | 中 | XS |
| C12 | 5 | 列表无手动「刷新」入口（页面挂载只 `loadList()` 一次），而列表接口有 5 分钟缓存；他处（脚本、移动端、其他人）改动频道后，本页无提示地显示旧配置，且没有任何"数据可能滞后"标记 | apps/admin-web/src/views/channel/ChannelManagement.vue:1234-1236；backend/app/routers/admin/channels.py:371-382 | 中 | XS |
| C13 | 4 | 空态与顶栏按钮均为「新增频道」文字描述，但按钮实际是纯 `Plus` 图标（文字仅进 `aria-label`/悬浮 tooltip），空态指向的"右上角按钮"在视觉上无文字锚点，首次用户需要逐个悬浮试探 | apps/admin-web/src/views/channel/ChannelManagement.vue:5,78；apps/admin-web/src/components/IconButton.vue:19-31 | 中 | XS |
| C14 | 1 | 后端 `ChannelCreateRequest.min_duration_sec` 与列表回传字段均存在，但五个页签里没有任何"时长下限"入口，管理端也无法配置该值；该字段成为只在 API 文档可见的隐藏配置 | backend/app/routers/admin/channels.py:82,349；apps/admin-web/src/views/channel/ChannelManagement.vue:88-504（全量表单无此字段） | 低 | S |

**优化建议**：
- C1：列表顶部加一行筛选（关键词 + 类型 + 启用状态 + 是否讲书稿模式），与素材库管理同一布局口径；超过 20 行再挂分页，保持「重置」按钮一致。
- C2：默认收起「段间BGM / 素材回溯 / 创建时间」三列，提供列设置下拉（勾选持久化到 localStorage）；`描述` 改为 tooltip 承载以省 200px。
- C3：新增「内容模式」列（资讯/书源/讲书稿池），讲书稿模式行内直接显示 `进度 已取X/共Y`，并让列表数据源加 `script_mode`+池进度；点击列内链接直达 `/channels/book-pool?channelId=`。
- C4：列表接口改按 `(display_order, id)` 排序，或在「展示排序」列旁标注「本列表按创建顺序显示」。
- C5：`loadList` 增 `catch`，失败时表格落 `el-result` 错误态并提供「重试」，空态文案仅在确认无数据时出现。
- C6：切换期间 `:disabled="row.__toggling"` 并加 `loading`；弹窗「启用」旁加灰字说明「此处修改需点『确认』保存；列表开关即时保存」。
- C7：「默认」改为「默认 05:00」，取值来自全局配置接口。
- C8：广告列统一用 `el-tag`（投放=success plain / 关闭=info plain）。
- C9：全站约定单一术语「继承全局」，并在 tooltip 内说明继承来源页；「继承动态」改「继承动态回溯」。
- C10：确认文案改为带数据的描述：「该频道讲书稿书单 N 本将一并删除、M 条素材失去归属，操作不可恢复」，列表接口需回传 `pool_total`/`material_count`；删除后 toast 附「已同步移除定时任务」。
- C11：统一走 `useUserStore().role`，并抽 `useCanOperate()` 供各页复用。
- C12：顶栏加「刷新」图标按钮；列表缓存命中时在页面角落显示「配置可能滞后 5 分钟」。
- C13：主 CTA（新增频道/手动录入素材/上传并解析/从素材库加入/检索）统一传 `inlineText`，让图标旁显示精简文字。
- C14：若时长下限仍需保留，请在「音频与 BGM」页签补一个字段；否则从请求体移除以免误用。

---

### C-2 频道管理 > 新增/编辑频道弹窗（四页签表单）

**现状描述**：一个 dialog 复用新增与编辑，内部分「基础信息/采集与选题/提示词与合规/音频与 BGM」四页签，内容区 `max-height:56vh` 内滚；页签内再嵌套 `el-divider` 分区与 `el-collapse` 折叠面板。校验规则只有 `name` 必填。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C15 | 5 | 新增模式下「启用」开关完全无效：`createChannel` 请求体不含 `is_active`，后端 `ChannelCreateRequest` 也没有该字段。用户把开关关掉再创建，得到的是一个已启用频道，且提示只有「已创建」 | apps/admin-web/src/views/channel/ChannelManagement.vue:107-109,1019-1038；backend/app/routers/admin/channels.py:58-103 | 高 | S |
| C16 | 2 | `resetForm()` 漏清 `book_rss_sources` 与 `icon_url`：编辑过「有声读物」频道 A 后点「新增频道」，A 的书籍 RSS 源会静默带入新频道并提交（`bookRssSourcesJson` 取自残留数组），图标预览也显示 A 的图标。跨频道配置串味且无任何提示 | apps/admin-web/src/views/channel/ChannelManagement.vue:713-750（对照 731-744 已清的字段）,914-918,1019-1038 | 高 | XS |
| C17 | 5 | 频道图标不显示：`_channel_to_dict` 未序列化 `icon_url`，编辑回填 `row.icon_url` 恒为空 → 每次打开编辑弹窗，图标区都显示「无图标」，运营以为图标丢失并重复上传/重复 AI 生成（每次生成有成本） | apps/admin-web/src/views/channel/ChannelManagement.vue:921,144-156；backend/app/routers/admin/channels.py:329-358（无 icon_url） | 高 | XS |
| C18 | 2 | AI 推荐类按钮保存时机不一致且与取消语义冲突：「AI 推荐 BGM」「AI 推荐 RSS 源与关键词」调用后立即 `updateChannel` 落库（提示「已保存」），但底部「取消」按钮 desc 写「关闭弹窗，放弃修改」；用户点取消后配置其实已经生效 | apps/admin-web/src/views/channel/ChannelManagement.vue:1182-1186,1220-1224；507 | 高 | S |
| C19 | 3 | 表单信息密度过高：四页签 + 页签内 divider + 折叠面板三层分组，「采集与选题」页签内含 9 个字段（含开关灰显与素材池链接），内容区限高内滚；页签内没有锚点/进度标识，未保存离开无拦截提示，用户难以判断"填到哪了"（滚动条可见性需实测确认） | apps/admin-web/src/views/channel/ChannelManagement.vue:88-190,190-325,1243-1252 | 中 | M |
| C20 | 4 | 保存成功提示恒为「已更新」/「已创建」，未说明生效时机；C 端频道列表缓存 60s，且后端失效的缓存键 `api:channels:list_active` 与实际使用的 `api:channels:list_active:v2` 不同名，小程序侧排序/封面变更需等 TTL 才可见 | apps/admin-web/src/views/channel/ChannelManagement.vue:1015,1039；backend/app/services/channel_service.py:58-60；backend/app/routers/api/channels.py:20 | 中 | XS |
| C21 | 2 | 校验失败时写死 `activeTab.value = 'basic'`，注释也承认"当前唯一必填在基础信息"；后续任何页签新增必填项，错误提示会藏在未激活页签里，用户只看到「没反应」 | apps/admin-web/src/views/channel/ChannelManagement.vue:956-962 | 中 | XS |
| C22 | 4 | 「素材 ID」为自由文本框（逗号分隔），提交时 `parseInt` 静默过滤非法值：误填 `12，、13` 之类只留下能解析的 ID，用户不会被告知哪些被丢弃；也无法确认 ID 属于本频道 | apps/admin-web/src/views/channel/ChannelManagement.vue:224-227,975-983 | 中 | S |
| C23 | 6 | `type_label`（类型标签）是冗余输入字段，但列表「类型」列只按 `channel_type` 映射中文，填了「听书精选」后管理界面毫无反馈，运营无法验证标签是否生效（只在小程序端体现） | apps/admin-web/src/views/channel/ChannelManagement.vue:104-106,12-18 | 低 | XS |
| C24 | 2 | T00828「断点续录」实际不可用：草稿仅在 `editing && form.id` 时写入 localStorage，而恢复只发生在 `openCreate()` 且条件为 `draft.id === form.id`（此时 form.id 恒为 null，条件永假）；`openEdit()` 完全不读草稿。用户以为"上次填的被系统记住了"，实际每次都要重填 | apps/admin-web/src/views/channel/ChannelManagement.vue:758-762,884-953,1051-1057 | 中 | S |
| C25 | 5 | 后端字段级校验错误（如 `channel_type 仅支持 news / course / audiobook`、`material_lookback_days 超出上限 90 天`）经拦截器原样直出为红色 toast，中文枚举值与英文字段名混排；界面没有前置约束兜底（例如 schedule_time 只靠 placeholder 说明格式） | apps/admin-web/src/views/channel/ChannelManagement.vue:192；backend/app/routers/admin/channels.py:112-118,146-152,186-190；apps/admin-web/src/api/index.js:52-72 | 中 | S |
| C26 | 6 | 提交按钮文案与同组其他页不一致：本页 `label="确认"`，素材库/工作流详情均为 `label="保存"`；同一后台"提交表单"存在两种动词 | apps/admin-web/src/views/channel/ChannelManagement.vue:508；apps/admin-web/src/views/channel/MaterialLibrary.vue:209 | 低 | XS |

**优化建议**：
- C15：把「启用」开关在新增模式下移除或置灰并注明「创建后可在列表开关」；若保留，请让 `createChannel` 透传且后端 `ChannelCreateRequest` 增补字段。
- C16：`resetForm()` 补齐 `book_rss_sources=[]`、`icon_url=''`、`manual_material_ids_text`；更稳的做法是表单初值抽 `defaultForm()` 工厂，新增时整体替换而非逐字段清空（可从根上避免漏字段）。
- C17：`_channel_to_dict` 增补 `icon_url`；并在图标区显示「已上传（保存于服务端）」而非空占位。
- C18：AI 推荐改为"只回填、不落库"，把「已保存」提示去掉；若必须即时落库，则取消按钮 desc 改为「关闭弹窗（AI 推荐结果已保存）」。
- C19：页签头部加"已配置 N/9 项"或改为分步向导（基础 → 采集 → 提示词 → 音频），并在 `before-close` 做脏值确认。
- C20：保存成功 toast 补「约 1 分钟内在小程序生效」；后端失效缓存改用 `delete_pattern("api:channels:list_active*")`。
- C21：校验失败按 `fields` 反查所属页签再切换；表单规则集中声明字段→页签映射。
- C22：改为多选素材选择器（复用 `/materials?channel_id=` 列表），或提交前解析并回显「识别到 N 个 ID，M 个无效：...」。
- C23：填了 `type_label` 时列表「类型」列优先展示该标签。
- C24：`openEdit` 读取并套用同 id 草稿，且弹窗顶部出现可关闭提示条「已恢复未保存草稿（时间）」；`openCreate` 删除无效分支。
- C25：前端补 `rules`（schedule_time 正则、lookback 1-90、channel_type/disclaimer 枚举由控件天然约束），把后端错误映射成字段级红字。
- C26：全站弹窗主按钮统一「保存」。

---

### C-3 频道管理 > 讲书稿素材池子弹窗（嵌套 BookPoolPanel）

**现状描述**：编辑弹窗「采集与选题」页签内有独立「讲书稿模式」开关 + 「讲书稿素材池」链接，点击在编辑弹窗之上再叠一个 900px 弹窗，内嵌与独立页共用的 `BookPoolPanel`（`destroy-on-close`）。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C27 | 2 | 共用的 `BookPoolPanel` 里没有模式开关（模板只有状态 alert），但组件内仍保留 `scriptMode/modeLoading/onToggleMode` 三个未使用状态/方法；因此子弹窗内只能"看池、改排序"，开/关模式必须回到外层页签的开关——用户在同屏看到两处与模式相关的提示，却只有一处能操作 | apps/admin-web/src/views/channel/BookPoolPanel.vue:3-24（无开关）,186-187,244-256（死代码）；apps/admin-web/src/views/channel/ChannelManagement.vue:302-324 | 高 | S |
| C28 | 4 | 开关 tip「已开启：内容来自『讲书稿素材池』（按书单顺序逐日取书），上方书源已停用（灰显）」措辞与外层链接「讲书稿素材池（书单 / 排序 / 进度）」对同一对象给了两种粒度描述，且链接是 `el-link` 而非按钮，视觉上不像可点入口 | apps/admin-web/src/views/channel/ChannelManagement.vue:311-322 | 低 | XS |
| C29 | 5 | 子弹窗关闭后不刷新外层任何状态：模式开关 tip、书源灰显（`bookPoolOn`）都不依赖池数据，但外层"素材池"入口没有池规模/进度的最小摘要，用户无法确认刚才在子弹窗里的改动是否生效（只能重开子弹窗） | apps/admin-web/src/views/channel/ChannelManagement.vue:317-322,511-521 | 中 | S |

**优化建议**：
- C27：把模式开关正式放回 `BookPoolPanel` 头部（复用 `onToggleMode`，删除 ChannelManagement 里的重复实现），确保"独立页 / 弹窗内"两种形态功能一致；若产品决定开关只留外层，则删除面板内死代码并在 alert 尾部加「模式开关见『采集与选题』页签」。
- C28：链接改 `IconButton`+`inlineText="书单/进度"`，tip 精简为「开关已生效，内容来自下方书单」。
- C29：子弹窗关闭回调里拉一次 `getScriptMode`，在外层链接下方显示「书单 N 本 · 进度 X/Y」。

**说明**：本节未发现"信息架构缺失"类问题，弹窗层级（编辑弹窗 → 池弹窗，`append-to-body`）本身可用。

---

### C-4 频道管理 > 预制封面选择弹窗（cover picker）

**现状描述**：760px 弹窗，`auto-fill minmax(120px,1fr)` 网格 + `max-height:460px` 内滚，点击缩略图即写入 `form.cover_url` 并关闭，附 mtime 版本号防缓存。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C30 | 5 | 列表只在首次打开时拉取（`coverPresets.length>0` 直接复用缓存），服务端新增封面后运营永远看不到，弹窗内没有刷新入口；唯一恢复方式是关闭整个编辑弹窗重进 | apps/admin-web/src/views/channel/ChannelManagement.vue:777-789 | 中 | XS |
| C31 | 2 | 两条设置封面路径能力不等：手输 URL 无任何格式/可达性校验（保存后仍显示旧值或加载失败），而选择预制封面会即时 `success` toast；用户无法预判自填 URL 是否可用 | apps/admin-web/src/views/channel/ChannelManagement.vue:135-141,815-819 | 中 | S |
| C32 | 3 | 网格无封面名称/频道号搜索，也没有「不使用封面」按钮（清空只能回到表单里删输入框）；预制项按 `channel_id` 排序展示 `#12 名称`，与服务端目录顺序耦合（当前实现依赖后端返回顺序，需实测确认） | apps/admin-web/src/views/channel/ChannelManagement.vue:531-546,1377-1385 | 低 | XS |
| C33 | 4 | 空态文案「服务端暂无预制封面（channel_assets 目录为空）」把部署路径细节暴露给运营；此时应引导"改用 URL 或上传图标" | apps/admin-web/src/views/channel/ChannelManagement.vue:532-534 | 低 | XS |

**优化建议**：
- C30：弹窗头部加「刷新」按钮 + 每次打开都重新拉取（列表接口很轻）。
- C31：URL 输入失焦时做一次 HEAD 校验或以 `el-image#error` 预览为准并显式提示「预览失败，可能线上也无法显示」。
- C32：加名称过滤输入与「清除封面」按钮。
- C33：空态改为「暂无预制封面，可直接填写图片 URL」。

---

### C-5 频道管理 > 频道图标（上传 / AI 生成）

**现状描述**：编辑弹窗「基础信息」页签内，72px 预览 + 上传按钮 + 关键词输入 + 「AI 生成」按钮；两者均要求先保存频道（`!editing` 时禁用），成功后直接写库。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C34 | 2 | 图标是唯一"点即写库、不经确认"的表单字段（上传/AI 生成端点直接改 DB），与同页其余字段的「点确认才保存」不同；`onCancelDialog` 保存的草稿也不含图标状态，取消后图标其实已变更 | apps/admin-web/src/views/channel/ChannelManagement.vue:821-847,1051-1057；backend/app/routers/admin/channels.py:857-878,919-922 | 中 | S |
| C35 | 5 | AI 生成超时设为 180s，期间只有按钮 loading 与转圈图标；无"预计耗时/可取消"提示，用户容易重复点击或关弹窗（关弹窗后请求仍在跑，结果不可见）。新频道下按钮置灰但 desc 仍是「调用 AI 生成频道图标」，未说明为何不可点 | apps/admin-web/src/views/channel/ChannelManagement.vue:173-185；apps/admin-web/src/api/channels.js:22-23 | 中 | S |
| C36 | 4 | 图标区 tip 与 36 行的禁用提示「（新频道请先保存，再配置讲书稿模式与素材池）」共用一套灰字，图标自身的"请先保存"说明只在 tooltip 里，且新频道保存后需要重开弹窗才能上传图标（无"保存并继续配置"入口） | apps/admin-web/src/views/channel/ChannelManagement.vue:163-185,323 | 低 | S |

**优化建议**：
- C34：改为回填 `icon_url` 后随「确认」提交（后端提供临时上传目录），或在按钮 tip 明确写「上传/生成会立即生效，不依赖底部确认」。
- C35：加进度占位（骨架 + 「AI 生成约需 30–120 秒」）与「取消生成」；新频道下把按钮替换为提示条「创建频道后即可上传/生成图标」。
- C36：新增成功后 toast 提供「继续配置图标与讲书稿」的行动按钮（重开编辑弹窗）。

---

### C-6 频道管理 > BGM 选择 / 上传 / 试听 / AI 推荐（「音频与 BGM」页签）

**现状描述**：分组下拉（预制/自定义）+ 试听按钮 + 原生 `<audio controls>` + AI 推荐 + 上传按钮（含 20MB/扩展名预校验）+ 音量滑块 + 段间静音/段间 BGM 继承项。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C37 | 2 | 试听必然失败：`bgmPreviewUrl` 拼 `/bgm/${path}`，既未走 `assetPreviewUrl()` 的 `/news` 前缀约定，Vite dev proxy 也没有 `/bgm` 或 `/news/bgm` 条目，后端静态挂载在裸 `/bgm`。开发态（5181）请求打到 Vite → 404；生产经 Funnel 只路由 `/news/*` → 同样 404。同一问题已在预制封面处修过并注明原因，BGM 漏改 | apps/admin-web/src/views/channel/ChannelManagement.vue:670-673,792-802,1121-1136；apps/admin-web/vite.config.js:36-63；backend/app/main.py:1431 | 高 | XS |
| C38 | 5 | 上传进度不可见：`label` 动态写成「上传中 45%」，但 `IconButton` 只把 `label` 用作 `aria-label` 和 tooltip，且 `loading` 时图标本身不渲染；界面上用户只看到转圈，最长 120s 无任何百分比反馈 | apps/admin-web/src/views/channel/ChannelManagement.vue:429,1153-1170；apps/admin-web/src/components/IconButton.vue:19-31；apps/admin-web/src/api/channels.js:42-52 | 中 | XS |
| C39 | 2 | 自定义 BGM 只增删不了：`deleteBgmFile` 封装存在但全站无调用点，弹窗也没有「管理 BGM」入口；上传失误的重复文件永久留在下拉里（下拉项只显示 `名称 (KB)`，同名文件无法区分） | apps/admin-web/src/api/channels.js:54-55；backend/app/routers/admin/channels.py:660-676；apps/admin-web/src/views/channel/ChannelManagement.vue:394-401 | 中 | S |
| C40 | 4 | 「BGM 音量」tip 写「留空/0.15 为默认」，但控件是 `slider 0–1, step .05`，永远不可能"留空"；滑块拖到 0 时究竟是"不播 BGM"还是"继承全局音量"未说明，语义与后端 `bgm_volume=None→全局` 不一致 | apps/admin-web/src/views/channel/ChannelManagement.vue:445-454；backend/app/routers/admin/channels.py:125-131 | 中 | S |
| C41 | 6 | 相邻两个"继承"字段默认值相反：段间静音 `inherit_segment_gap:false`（新频道固定 0.5s，遮蔽全局），段间 BGM `inherit_bgm_gap:true`（新频道继承全局）；页面上没有任何地方解释这一差异，运营调完全局后预期被无声打破 | apps/admin-web/src/views/channel/ChannelManagement.vue:627-635,456-494,900-905 | 低 | XS |
| C42 | 3 | 试听播放器插入位置在字段内动态显隐，会让「音频与 BGM」页签内容高度突变、后续字段下移（原生 `audio controls` 宽度 100%）；自动播放被浏览器策略拦截时静默 `catch`，界面文案仍是「试听」，用户不确定是坏了还是被拦截（视觉跳动需实测确认） | apps/admin-web/src/views/channel/ChannelManagement.vue:433-439,1121-1136 | 低 | S |

**优化建议**：
- C37：`bgmPreviewUrl` 改走 `assetPreviewUrl('/bgm/'+path)`，并在 vite proxy 增加 `/news/bgm` 与 `/bgm` 两条转发。
- C38：上传区改用可见 `el-progress`（或 `inlineText` 显示「上传中 45%」）。
- C39：自定义分组每项加「删除」（仅 `custom/` 前缀可用），或在弹窗内提供「管理 BGM」小表格。
- C40：把音量改为「继承全局」勾选 + 滑块，tip 拆成两句；0 明确标注「静音」。
- C41：两字段统一默认「继承全局」，并在 tip 里注明"未显式配置时跟随 AI 服务页"。
- C42：试听条固定占位（不隐藏），并加"浏览器可能拦截自动播放，请点击播放器"提示。

---

### C-7 内容运营 > 素材库管理（列表 / 筛选 / 分页 / 视图切换，路由 /channels/material-library）

**现状描述**：5 个筛选条件 + 明细/按书聚合双视图 + 分页；明细行支持编辑/删除，聚合行支持「查看章节」下钻与整本书删除（仅 admin）；另有精确定位提示条（素材 ID / 书名）。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C43 | 5 | 精确定位提示条与视图切换互相说谎：从讲书稿书单点「素材 ID」进入后显示「已按素材 ID 123 定位」，用户切到「按书聚合」时，聚合接口只接受 `channel_id/keyword/status`，`material_id`/`source` 被静默忽略，提示条仍在但结果已不过滤；运营据此误判"这本书只有这些章节" | apps/admin-web/src/views/channel/MaterialLibrary.vue:336-342,122-126,353-365；backend/app/routers/admin/materials.py:283-289 | 高 | S |
| C44 | 2 | 同样口径问题也发生在「来源类型 / 媒体类型」：这两项筛选在聚合视图下不进入请求参数（前端 `load()` 分支未传，后端也不支持），用户带着 `来源类型=资讯 RSS` 切到聚合视图后结果不变、无任何提示 | apps/admin-web/src/views/channel/MaterialLibrary.vue:350-365,367-377；backend/app/routers/admin/materials.py:283-292 | 中 | S |
| C45 | 1 | 全链路术语在最关键处漂移：菜单叫「素材库管理」，本页右上角按钮叫「手动录入素材」，讲书稿池 tips 却要求"新书素材请到『素材录入』上传"，而「素材录入」是另一个菜单页；同一页内又出现「素材池」（后端 docstring：素材是频道级素材池）。首次用户无法判断"库/池/录入"是几个对象 | apps/admin-web/src/views/channel/MaterialLibrary.vue:5-9,262；apps/admin-web/src/views/channel/BookPoolPanel.vue:86；apps/admin-web/src/router/index.js:93-112；backend/app/routers/admin/materials.py:211-213 | 高 | S |
| C46 | 5 | 明细列表既不能读正文也不能看归属：列表响应只有 `id/source/title/summary/category/status/crawled_at/url/media_*`，无 `channel_id`、无 `source_type`；页面在「全部频道」下不显示所属频道列，也不显示录入渠道列——刚在素材录入页录错频道时，本页无从核对 | backend/app/routers/admin/materials.py:265-280；apps/admin-web/src/views/channel/MaterialLibrary.vue:73-118 | 中 | M |
| C47 | 2 | 只有一个"编辑"入口能看正文：没有只读「查看」按钮，读全文要打开编辑弹窗（正文是 8 行 textarea），误触即进入可写状态；工作流详情页同类数据有「查看」只读弹窗，两页能力不对称 | apps/admin-web/src/views/channel/MaterialLibrary.vue:112-117,410-423；apps/admin-web/src/views/workflow/WorkflowDetail.vue:103,679 | 中 | S |
| C48 | 6 | 同一 `status` 枚举在两页两种译名，且全仓没有权威字典可对齐：本页 `pending/selected/skipped` → 「待消费/已选题/已跳过」，工作流详情页同三值 → 「待处理/已选中/已跳过」；后端只在 docstring 里裸列枚举值，`MaterialStatusLabels` 一类常量在本仓不存在（已全仓检索确认），两侧各硬编码一份 | apps/admin-web/src/views/channel/MaterialLibrary.vue:303；apps/admin-web/src/views/workflow/WorkflowDetail.vue:365-368；backend/app/models/material.py:28-32；backend/app/routers/admin/materials.py:197,287 | 中 | XS |
| C49 | 2 | 权限显隐只在聚合视图生效：明细行「编辑/删除」与顶部「手动录入素材」对所有角色可见，但后端 POST/PUT/DELETE 一律 `require_admin`，operator 只能收到「无权限执行此操作」toast；同页删除整本书却按 `canOperate` 隐藏，自相矛盾 | apps/admin-web/src/views/channel/MaterialLibrary.vue:112-117,134-144,332-333；backend/app/routers/admin/materials.py:361-365,411-416,471-475 | 中 | XS |
| C50 | 5 | 首屏初始化无兜底：`onMounted` 里 `channels.value = await listChannels()` 无 try/catch，接口失败时 `applyDeepLink/load` 根本不执行，表格永远空白并显示「没有匹配的素材」，与 C5 同类误读 | apps/admin-web/src/views/channel/MaterialLibrary.vue:522-528 | 中 | XS |
| C51 | 3 | 明细表 9 列（含 ID、来源、创建时间、类型、预览、双 fixed 操作列），`min-width` 累加 >1160px，1366 以下需横向滚动；「预览」列 56×64 图片使行高不齐（需实测确认）；无列设置 | apps/admin-web/src/views/channel/MaterialLibrary.vue:73-118,98-111 | 中 | S |
| C52 | 2 | 没有任何批量操作：清理一批 RSS 资讯素材只能逐条删除或回到「按书聚合」整本删；无批量改状态（如把某书全部章节标 skipped），日常运营成本高 | apps/admin-web/src/views/channel/MaterialLibrary.vue:73-150 | 中 | M |
| C53 | 4 | 「重置」按钮只重置筛选与精确定位，不切回视图模式与页大小，desc 写「重置筛选条件」；用户按「重置」后仍在聚合视图，容易以为按钮坏了 | apps/admin-web/src/views/channel/MaterialLibrary.vue:62,391-400 | 低 | XS |
| C54 | 6 | 分页文案两种量纲共用同一控件：明细视图「共 N 条」=素材条数，聚合视图「共 N」=书数，标签未随之变化；每页条数上限 100 与后端 `size<=100` 一致但界面未说明 | apps/admin-web/src/views/channel/MaterialLibrary.vue:152-161；backend/app/routers/admin/materials.py:289 | 低 | XS |
| C55 | 1 | 「来源类型」选项里没有 `book_plan`（找书工具写入的占位素材用的正是该值，且不在 `MaterialSourceType` 枚举中），这类"待上传书稿"素材既无法筛出、也无法在列里辨识，只能靠关键词搜书名 | apps/admin-web/src/views/channel/MaterialLibrary.vue:286-293；backend/app/routers/admin/ebooks.py:174；backend/app/models/material.py:13-25 | 中 | S |

**优化建议**：
- C43/C44：切视图时按目标接口支持项重算提示条——不支持的条件以 `el-tag type="warning"` 显示「当前视图不生效：素材 ID/书名/来源类型」，或直接在聚合视图禁用这些控件。
- C45：统一术语——菜单/按钮/文案全部采用「素材库」（数据）与「讲书稿书单」（池）；「素材录入」菜单改名「素材录入（多渠道）」并在页头一句话说明它与「素材库管理」的关系；按钮文案改「手动新增素材」。
- C46：列表响应补 `channel_id/source_type`，明细表加「所属频道」「录入渠道」两列（默认收起），聚合视图加「频道」列。
- C47：加只读「查看」按钮（复用 WorkflowDetail 的详情弹窗形态），编辑按钮不再承担"读"的职责。
- C48：抽 `src/constants/materialStatus.js` 统一 label/tag/tooltip，两页共用。
- C49：本页所有写操作按 `canOperate` 统一显隐（含顶部按钮与明细行）。
- C50：初始化 `try/catch` + 失败态展示；`listChannels` 失败不应阻断列表加载。
- C51：ID 列收起、创建时间改日期短格式、预览列合并进标题缩略图；提供列设置。
- C52：明细表加多选 + 批量删除/批量改状态（确认框必须带条数）。
- C53：「重置」同时恢复视图模式与页大小，desc 写「清空全部筛选并回到明细视图」。
- C54：聚合视图分页文案改「共 N 本书」，按 `viewMode` 动态切换。
- C55：`MaterialSourceType` 增补 `book_plan`，前端选项加「待讲书单占位」，列表可见并可一键转「素材录入」。

---

### C-8 素材库管理 > 编辑素材弹窗 / 手动录入素材弹窗 / 删除确认

**现状描述**：两个 640px 弹窗分别承担编辑与新增，字段几乎同构（编辑多「状态」与「缩略图」）；删除单条走 `ElMessageBox.confirm`，整本书删除显示条数并限定 admin。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C56 | 2 | 编辑弹窗不校验正文与来源：`onSaveEdit` 只挡空标题，正文/来源可被清空后照样提示「已保存」；而来源=书名正是讲书稿聚合键，清空即打断整本书聚合（该书在书单候选里消失） | apps/admin-web/src/views/channel/MaterialLibrary.vue:425-448,170-173；backend/app/services/book_pool_service.py:341-343 | 高 | S |
| C57 | 5 | `openEdit` 先 `await getMaterial(id)` 再开弹窗，期间无 loading、无过期响应防护，失败时弹窗不出现且编辑态残留上一行值（表单在成功后才整体赋值）；工作流详情页为同一场景加了请求序号，两页健壮性口径不一 | apps/admin-web/src/views/channel/MaterialLibrary.vue:410-423；apps/admin-web/src/views/workflow/WorkflowDetail.vue:600-623 | 中 | S |
| C58 | 1 | 新增弹窗必填项无 `required` 标记（只在点击后用 toast 提示「标题与正文为必填项」），而素材录入页的手动录入表单却给标题/正文标了红星；同项目内"表单必填呈现"两套规范 | apps/admin-web/src/views/channel/MaterialLibrary.vue:224-241,462-466；apps/admin-web/src/views/channel/CourseMaterials.vue:124-129 | 中 | XS |
| C59 | 2 | 新增弹窗「频道」默认取当前筛选频道、否则 `channels[0]`，且无「必选」校验；筛选频道为空时会静默落到列表第一个频道，素材录到错误频道后在本页（默认全部频道）也看不出来 | apps/admin-web/src/views/channel/MaterialLibrary.vue:450-460,216-220 | 中 | S |
| C60 | 4 | 单条删除确认文案写「讲书稿书单中的对应条目取书时会提示书稿缺失」，但删除整本书的确认只写「确定删除《X》全部 N 条章节素材？删除后不可恢复。」，未提该书若已在书单中会怎样；两种删除的告知粒度不一致 | apps/admin-web/src/views/channel/MaterialLibrary.vue:489-520 | 中 | XS |
| C61 | 6 | 删除/保存等写操作未做角色隐藏（见 C49），确认框标题与按钮文案本页用「删除素材/确认删除」，整本书用「删除整本书/确认删除」，频道页用「删除确认」——标题粒度三种写法 | apps/admin-web/src/views/channel/MaterialLibrary.vue:489-507；apps/admin-web/src/views/channel/ChannelManagement.vue:1075-1078 | 低 | XS |

**优化建议**：
- C56：编辑加 `rules`（标题/正文必填，来源为空时二次确认「清空来源会让这本书在讲书稿候选中消失」）。
- C57：`openEdit` 显示 loading 并加序号防护；失败时明确提示并中止。
- C58：两个弹窗都用 `el-form :rules` + `required` 星号，去掉手工 toast 校验。
- C59：频道项加 `required`，默认值仅在筛选频道存在时继承，否则留空并强制选择。
- C60：整本书删除时若该书在池中，文案补「《X》已在讲书稿书单第 N 位，删除后取书将报书稿缺失」。
- C61：确认框文案模板化：「删除素材」「删除整本书（N 条）」统一带条数。

---

### C-9 素材库管理 > 空态与深链定位（含从讲书稿池跳入的上下文保留）

**现状描述**：支持 `?channelId / ?materialId / ?source / ?keyword / ?view=book` 深链，命中精确条件时显示绿色可清除提示条；两个空态文案（无匹配 / 无聚合书）。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C62 | 4 | 空态不区分原因：「没有匹配的素材」同时覆盖"筛选过窄""素材不存在""接口失败"三种情形；从书单点进来的深链若命中失败（素材已删/属别的频道），界面就是这一句，用户会怀疑链接坏了 | apps/admin-web/src/views/channel/MaterialLibrary.vue:118,530-551 | 中 | S |
| C63 | 2 | 深链参数解析顺序造成互斥：`materialId` 命中即 `return`，同行携带的 `keyword`/`view=book` 被丢弃；从「管理素材 ↗」带 keyword 进入正常，但从素材 ID 进入后再想按书名二次过滤只能手输 | apps/admin-web/src/views/channel/MaterialLibrary.vue:537-551 | 中 | XS |
| C64 | 2 | 上下文只进不出：本页没有任何「回到讲书稿素材池」或「去素材录入」的链接，从池跳过来的运营看完素材后要退回，只能按浏览器后退或重新走菜单；池页带过去的 `channelId` 在本页筛选栏里也没有"来源标注"（用户不知为何预置了频道） | apps/admin-web/src/views/channel/MaterialLibrary.vue:4-10,28-70；apps/admin-web/src/views/channel/BookPoolPanel.vue:321-340 | 中 | S |
| C65 | 3 | 提示条为 `el-alert type="success"`（绿色），语义是"限定条件"而非"操作成功"，与页面里真正的成功反馈（保存/删除 toast）同色，视觉语义混淆（对比色需实测确认） | apps/admin-web/src/views/channel/MaterialLibrary.vue:13-26 | 低 | XS |

**优化建议**：
- C62：区分空态：命中 `materialId` 但结果为空 → 「素材 #123 不存在或不属于当前频道」+「清除限定」；有筛选 → 「放宽条件」快捷按钮（逐个清 source_type/media_type/keyword）。
- C63：按优先级合并参数（materialId 精确 + keyword 共存），或明确「深链参数互斥」并在提示条上展示被忽略的参数。
- C64：卡片头部加面包屑式关联链接「本频道讲书稿书单 →」；筛选频道由深链带入时在「频道」控件下方标注「来自讲书稿素材池」。
- C65：提示条改 `type="info"`，文案前缀「限定」。

---

### C-10 内容运营 > 讲书稿素材池（页面壳，路由 /channels/book-pool，BookPool.vue）

**现状描述**：薄壳页——一张卡片头部放频道下拉，卡片体内一句 `el-alert`，下方 `<BookPoolPanel>`；频道来源为全部频道列表，默认优先第一个 `audiobook` 频道，否则第一个频道。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C66 | 1 | 页面源码注释与实现不符：`BookPool.vue` 顶部注释与卡片内注释均写「讲书稿模式开关在下方面板内」，实际面板没有开关（见 C27）；本页因此没有任何"开启模式"的操作点，只有 alert 里那句"开启后忽略书源…"的描述 | apps/admin-web/src/views/channel/BookPool.vue:6,35；apps/admin-web/src/views/channel/BookPoolPanel.vue:3-24,244-256 | 高 | S |
| C67 | 2 | 频道下拉不做类型过滤：资讯/课程频道同样可选，选中后页面照常渲染"书单/取书间隔/进度"，这些配置对非有声读物频道无意义（`script_mode` 只在有声读物链路生效），运营会以为给资讯频道配了书单也管用 | apps/admin-web/src/views/channel/BookPool.vue:59-68；apps/admin-web/src/views/channel/BookPoolPanel.vue:4-45 | 中 | S |
| C68 | 5 | 深链/非法频道静默降级：`route.query.channelId` 直接赋给 `channelId`，不校验是否存在于 `channels`；频道不存在时面板按"未开启 + 空池"渲染并显示"请先加入书籍"，用户以为池被清空了 | apps/admin-web/src/views/channel/BookPool.vue:61-67；apps/admin-web/src/views/channel/BookPoolPanel.vue:222-228；backend/app/services/book_pool_service.py:42-45（channel 不存在返回 exists:false） | 高 | S |
| C69 | 2 | 频道选择与 URL 脱钩：切换频道不写 `query.channelId`，从本页跳去素材库再浏览器后退，回到的是初始自动选中频道而非刚看的频道；运营在两个频道间对比书单时来回成本很高 | apps/admin-web/src/views/channel/BookPool.vue:61-72；apps/admin-web/src/views/channel/BookPoolPanel.vue:321-340 | 中 | XS |
| C70 | 5 | `channels.value = await listChannels()` 无 catch：失败时下拉为空、面板不渲染、页面只剩一句「请先选择频道」，与"真的没有频道"不可区分 | apps/admin-web/src/views/channel/BookPool.vue:59-68,31-32 | 中 | XS |
| C71 | 4 | 卡片用 `:body-style="{ padding: 0 }"` 消除空 body 间距（历史反馈修复），但 alert 直接贴卡片边框、卡片头部只剩一个下拉，视觉上像缺失内容；本页也没有任何"这条链路怎么走"的入口（找书 → 录入 → 库 → 池） | apps/admin-web/src/views/channel/BookPool.vue:11-33 | 低 | S |
| C72 | 6 | `TYPE_LABELS` 映射在 BookPool.vue 与 CourseMaterials.vue 各写一份，频道管理列表又用模板内联三元表达式，三处维护同一份频道类型称谓 | apps/admin-web/src/views/channel/BookPool.vue:52-53；apps/admin-web/src/views/channel/CourseMaterials.vue:211-212；apps/admin-web/src/views/channel/ChannelManagement.vue:12-18 | 低 | XS |

**优化建议**：
- C66：把模式开关正式放回面板头部并删除外层重复实现，同时校正注释；本页再加一句「模式与频道配置见『频道管理 → 采集与选题』」的双向链接。
- C67：下拉只列 `channel_type==='audiobook'`（或标灰非有声频道并注明"讲书稿模式仅适用于有声读物频道"），默认选中第一个已开启模式的频道。
- C68：`query.channelId` 命中不到时回落默认选择并 `ElMessage.warning('频道 #X 不存在，已切换到…')`；后端 `exists:false` 应映射为界面错误态。
- C69：`onChannelChange` 用 `router.replace({ query: { channelId } })`，保证刷新/分享/后退都保留频道。
- C70：加载失败显示错误态与「重试」。
- C71：卡片头部加链路引导条（找书工具 → 素材录入 → 素材库管理 → 本池，标出当前所在环节），alert 保留但补内边距。
- C72：抽 `src/constants/channelType.js`，三处统一引用。

---

### C-11 讲书稿素材池 > BookPoolPanel（模式状态 / 调度 / 进度 / 书单表 / 重置与预览）

**现状描述**：面板含状态 alert、行内表单（取书间隔 / 末尾处理 / 进度 / 预览下次生成 / 重置进度）、书单表格（顺序 / 书名 / 分类 / 素材 ID / 上移下移移出）与一段底部 tips；素材库加入按钮打开候选弹窗。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C73 | 5 | 切频道时状态残留导致进度被误读：`loadState()/loadPool()` 无 catch，`Object.assign(state, data)` 在失败时保持上一频道值，界面继续显示「已取 X / 共 Y 本 · 上次《Z》」与上一频道的书单行，运营会把 A 频道的进度当成 B 频道 | apps/admin-web/src/views/channel/BookPoolPanel.vue:217-242 | 高 | XS |
| C74 | 2 | 「取书间隔」是 `el-input-number` 的 `@change` 即写库，连点箭头触发多次 PUT，无 debounce、无 loading、无失败回滚（失败后输入值与后端不一致却无提示）；「末尾处理」开关切换同时提交两个字段，用户不知道改了间隔还是改了循环 | apps/admin-web/src/views/channel/BookPoolPanel.vue:28-34,258-265 | 中 | S |
| C75 | 2 | 排序只能逐格上下移：`moveBookInPool` 一次移一格，没有拖拽、没有"置顶/置底"、没有输入目标位次；`reorderBookPool`（批量重排）已封装但前端完全未接。把第 30 本调到第 1 本需要点 29 次，且中途无 loading 反馈 | apps/admin-web/src/views/channel/BookPoolPanel.vue:69-75,284-287；apps/admin-web/src/api/bookPool.js:31-36 | 中 | M |
| C76 | 4 | 「进度」语义不明：显示「已取 cursor / 共 pool_total 本」，而 cursor 既表示"已发布数"又在预览文案里当"书单第 N 本"的基（`(cursor??0)+1`），末尾未循环时 cursor 会被置为 total；界面没有一处说明"已取=已发布成功"还是"已排产"。同页 tips 又用「讲解完一本后进度自动 +1（**在节目发布成功后**推进）」，`**` 星号原样显示，未做加粗 | apps/admin-web/src/views/channel/BookPoolPanel.vue:35-40,83-87,203-213；backend/app/services/book_pool_service.py:308-325 | 中 | S |
| C77 | 1 | 「重置进度」确认文案只说"书单与排序保留"，未说明对已发布节目/取书日的影响，也没给出当前进度值（重置掉的是哪一步）；对运营来说这是会影响下一期内容的动作，但损失范围不可见 | apps/admin-web/src/views/channel/BookPoolPanel.vue:276-282 | 中 | XS |
| C78 | 2 | 「移出」与「上移/下移」反馈缺失：移出有确认但成功后只有 `已移出书单` toast，排序操作（移动）完全无反馈也不置忙，快速点击会连续发多个请求且顺序不确定 | apps/admin-web/src/views/channel/BookPoolPanel.vue:284-295 | 中 | S |
| C79 | 3 | 书单表 5 列 + `fixed="right"` 操作列宽 230px；「下一本」用 `el-tag` 占据「顺序」列，其余行显示序号，同一列两种语义（读到"下一本"时该行位次消失）；池项已有 `author/cover_url` 字段却未展示 | apps/admin-web/src/views/channel/BookPoolPanel.vue:53-75；backend/app/services/book_pool_service.py:402-414 | 中 | S |
| C80 | 5 | 「预览下次生成」是一次性 POST 且结果常驻显示（`preview` 不清空），此后任何排序/加入/移出操作都不会使预览失效——用户看到的"下次将生成《X》"可能已过期，属于典型的数据被误读 | apps/admin-web/src/views/channel/BookPoolPanel.vue:46,267-274,284-295,242-256 | 高 | S |
| C81 | 4 | 面板 alert 与 tips 混用「素材池 / 素材库 / 书单 / 讲书稿」：标题区「书单（顺序即取书顺序）」、按钮「从素材库加入」、tips「整本书以『书』为单位加入书单」；「素材 ID」列点进去是"素材库管理"，但列名既叫"素材 ID"又承载"书稿"跳转语义 | apps/admin-web/src/views/channel/BookPoolPanel.vue:9,23,49-52,62-68,83-87 | 中 | S |
| C82 | 2 | 「重置进度」/「预览下次生成」按钮位于行内表单末尾、与「进度」tag 同一行，四个操作无分组（保存型 vs 只读型），首次用户分不清「重置进度」是危险操作（视觉上 `type=warning plain` 但混在只读控件之间） | apps/admin-web/src/views/channel/BookPoolPanel.vue:35-45 | 低 | XS |
| C83 | 6 | 本页与频道管理弹窗共用同一面板，但两处入口都没有双向链接：面板里没有「去频道配置」链接（改取书间隔前可能需要看频道定时触发），频道管理列表也看不到池进度（见 C3） | apps/admin-web/src/views/channel/BookPoolPanel.vue:144-172；apps/admin-web/src/views/channel/ChannelManagement.vue:317-322 | 中 | XS |

**优化建议**：
- C73：`loadState/loadPool` 加 catch 并在失败时清空 state 为"未知"（进度显示 `—`）+ 错误态与重试按钮；切频道前先重置 state。
- C74：间隔输入改为「失焦/点保存后提交」或 600ms debounce；提交期间禁用控件并显示 loading；失败回滚显示值并把错误提示绑定到该字段。
- C75：书单表支持拖拽排序（`sortablejs` 或 EP 行拖拽），拖拽结束后调 `reorderBookPool` 一次性保存；同时保留上移/下移按钮并加「置顶」。
- C76：进度改为「已讲 12 / 共 30 本（下一本：第 13 《X》）＋上次发布 2026-10-17」；tips 里的 `**` 用真正加粗或去掉标记。
- C77：确认文案带上下文：「当前进度 12/30（上次发布《活着》，2026-10-17）。重置后将从第 1 本《X》重新开始，已发布节目不受影响。」
- C78：移动期间对该行 loading，成功 toast「已上移到第 N 位」。
- C79：「顺序」列拆成两列：序号 + 「下一本」徽标列；补「作者」列（已有字段），封面作缩略图。
- C80：任何影响池的写操作（加入/移出/移动/重置/开关模式/改间隔）后把 `preview` 置 null，并在预览条上加「数据可能已变化，点『预览下次生成』刷新」。
- C81：统一命名：池内对象一律称「书单」，外部一律「素材库」；把「素材 ID」列改名「代表素材」并加 tooltip 说明其含义（点进去可编辑该条章节素材）。
- C82：把「重置进度」单独放到表格右上「危险操作」分组或收进下拉菜单，预览按钮加 `text` 样式区分。
- C83：面板头部加「频道配置：定时触发 04:00 · 段间静音 继承全局 → 编辑」链接跳 `/channels?highlight=id`（配合 C1 的搜索能力）。

---

### C-12 讲书稿素材池 > 「从素材库加入书籍」候选弹窗

**现状描述**：780px 弹窗，关键词搜索 + 多选表格（书名/章节/分类/状态），已在书单的行禁用勾选，底部显示「已选 N 本」与「加入书单」；含「管理素材 ↗」跳转。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C84 | 2 | 候选固定 `page:1, size:50`，界面没有任何翻页控件也不显示总数（后端返回 `total` 被丢弃）：本频道书多于 50 本时，第 51 本起"不存在"，运营会判定"素材库里没有这本书" | apps/admin-web/src/views/channel/BookPoolPanel.vue:303-315,107-132；backend/app/services/book_pool_service.py:359-360,394 | 高 | S |
| C85 | 2 | 没有「全选可加入」/按分类筛选，多书批量入池只能逐行勾选；勾选状态在搜索后清空（`candidates` 被替换、`selection-change` 重置），跨关键词累计选择不可行 | apps/admin-web/src/views/channel/BookPoolPanel.vue:107-140,317-319 | 中 | S |
| C86 | 5 | 搜索无"无结果"引导之外的原因提示：空态文案要求"先到『素材录入』上传 EPUB/DOCX"，但候选按 `channel_id` 过滤——最常见的真实原因是"素材录到了别的频道"（找书工具的占位素材 `channel_id` 为空，正属此类），文案没有指这条 | apps/admin-web/src/views/channel/BookPoolPanel.vue:126-131；backend/app/services/book_pool_service.py:345-352；backend/app/routers/admin/ebooks.py:174-187 | 中 | S |
| C87 | 4 | 「管理素材 ↗」跳的是「素材库管理」并携带关键词，但按钮文案是"管理素材"，目标页菜单叫"素材库管理"，池页 tips 又叫"素材录入"——一句话里三个称谓，用户在菜单里找不到对应项 | apps/admin-web/src/views/channel/BookPoolPanel.vue:101-105,321-328,86；apps/admin-web/src/router/index.js:93-112 | 中 | XS |
| C88 | 1 | 候选行不展示代表素材 ID 或章节标题样例，也不显示"最后入库时间"（聚合视图有 `latest_at`），同名/近似书名时运营只能靠书名猜是哪本书，加入后才发现不是 | apps/admin-web/src/views/channel/BookPoolPanel.vue:114-125；apps/admin-web/src/views/channel/MaterialLibrary.vue:128-130 | 中 | S |
| C89 | 6 | 「已在书单」行只禁用勾选，没有"去书单里定位该书"的链接；重复找同一本书的成本落在用户身上 | apps/admin-web/src/views/channel/BookPoolPanel.vue:114,120-124 | 低 | XS |
| C90 | 2 | 无批量导入/导出：整个内容运营链（找书 → 录入 → 入池）没有任何 CSV/Excel 导入书单或导出当前书单的入口，运营靠人工逐本勾选，也无法把外部选题表落进系统 | apps/admin-web/src/views/channel/BookPoolPanel.vue:49-52；apps/admin-web/src/api/bookPool.js（无导入导出） | 中 | M |

**优化建议**：
- C84：接 `total` 渲染分页（或滚动加载 + 「共 N 本，已显示 M 本」），关键词搜索与分页状态互通。
- C85：加「全选本页可加入」，并保留跨搜索的已选集合（以 `book_key` 为主键缓存）。
- C86：空态改双分支：有筛选关键词 → 「素材库中没有书名为 X 的书（仅统计本频道素材）」+「到素材库全频道搜索」按钮；无数据 → 「本频道还没有素材」。
- C87：文案统一为「打开素材库管理（带当前关键词）」。
- C88：候选行补「代表素材 #id」「最近入库时间」，列宽与素材库聚合视图一致。
- C89：「已在书单」改为可点 tag，点后面板滚到对应行并高亮。
- C90：面板头部提供「导出书单 CSV / 从 CSV 导入书名」，导入走 `addBooksToPool` 批量（后端已有 `added/skipped` 返回，前端未展示 added/skipped 明细，也应一并回显）。

---

### C-13 内容运营 > 素材录入（路由 /materials，CourseMaterials.vue）

**现状描述**：单卡片 + 五个页签（本地文件上传 / 云端存储导入 / 手动录入 / API·URL 拉取 / 二维码·链接分享），每页签一段 `.hint` 说明「适用场景 + 数据格式」，页签内各自重复校验目标频道；顶部一句 alert 说明与频道管理的分工。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C91 | 2 | 上传整本书遇重复章节会半本入库：后端逐章调用 `_persist_material`，每次内部 commit，重复内容抛 `BizError(409,"该频道已存在相同内容的素材")` 中断循环。结果是"前 N 章已入库 + 一条与场景无关的错误提示（不提第几章、不提已入库多少）"，重试仍卡在同一章。前端只在 `catch` 里留注释交给拦截器 toast | apps/admin-web/src/views/channel/CourseMaterials.vue:246-265；backend/app/routers/admin/materials.py:529-541,118-131 | 高 | M |
| C92 | 4 | 文案与实现不符（去重渠道）：「二维码 / 链接分享」页签写「复核后转『手动录入』正式入库（source_type=qrcode）」，预填提示也重复这一说法；但手动录入提交固定 `source_type:'list'`，`qrcode` 永远不会产生。素材库「来源类型=二维码/链接分享」筛选因此恒为空 | apps/admin-web/src/views/channel/CourseMaterials.vue:171-174,300-309,374；apps/admin-web/src/views/channel/MaterialLibrary.vue:286-293 | 高 | S |
| C93 | 5 | 成功反馈与结果去向脱节：手动录入成功提示「已保存到素材池」（实际写入素材库），页面上没有任何「查看这条素材」的链接；上传/COS 成功后只显示「解析完成，新增 N 条素材」，同样不可点，运营要自己切到素材库管理并按书名重搜 | apps/admin-web/src/views/channel/CourseMaterials.vue:310,256-257,283-284 | 中 | S |
| C94 | 2 | `el-upload :limit="1"` 但没有 `on-exceed`：已选一个文件后再点选第二个，组件默认不提示、`on-change` 也不触发，界面表现为"点了没反应"，用户以为上传控件坏了 | apps/admin-web/src/views/channel/CourseMaterials.vue:49-61,235-245 | 中 | XS |
| C95 | 3 | 同一页两套禁用反馈口径：上传按钮用 `el-tooltip` 显式解释禁用原因（"请先选择文件，并在页面右上角选择目标频道"，且有 `.upload-btn-wrap` 保证命中），而 COS「导入」、URL「拉取并入库」、分享「获取预览」三个按钮只 `:disabled` 无任何原因说明 | apps/admin-web/src/views/channel/CourseMaterials.vue:66-83,102-110,157-165,179 | 中 | XS |
| C96 | 1 | 「目标频道」放在卡片头部（右上角），而五个页签各自重复它的影响；用户在「手动录入」里填完长正文后才发现没选频道，需要回到页面顶部找那个 280px 下拉。频道切换后也只清空上传/COS 结果提示，已填表单来源默认值不重置（跨频道串用语义模糊） | apps/admin-web/src/views/channel/CourseMaterials.vue:9-24,377-381 | 中 | S |
| C97 | 4 | 手动录入的 URL 字段提示误导：「留空 URL 时按正文内容去重」，实现是 list 类型忽略用户 URL、恒以 content_hash 去重且合成 url 入库；填了 URL 也不会被用作去重键，用户据此判断"我填了 URL 就能重复录同一正文"是错的 | apps/admin-web/src/views/channel/CourseMaterials.vue:121,132-134；backend/app/routers/admin/materials.py:118-131,381-383 | 中 | XS |
| C98 | 2 | 去重范围随渠道变化却没有说明：list/cos 按频道去重（同内容可进不同频道），api/qrcode 按 URL 全局唯一（同链接第二次入库直接 409「URL 已存在」）。运营做"多频道分发同一篇文章"时，URL 页签必然失败且看不出为什么 | apps/admin-web/src/views/channel/CourseMaterials.vue:140-167；backend/app/routers/admin/materials.py:145-149 | 中 | S |
| C99 | 5 | 长任务无过程反馈：PDF/EPUB 解析走 60s 超时，期间只有按钮转圈，无进度、无"预计耗时/请勿关闭页面"；超时后拦截器直出 `timeout of 60000ms exceeded` 这类英文技术文案 | apps/admin-web/src/api/materials.js:28-35；apps/admin-web/src/api/index.js:60-70 | 中 | S |
| C100 | 6 | 「API / URL 拉取」页签的「类型」下拉含「分享链接」，与「二维码 / 链接分享」页签语义重叠；两个页签产出的 source_type 相同（api/qrcode 混用），素材库按来源类型筛选时无法区分用户走的哪条路 | apps/admin-web/src/views/channel/CourseMaterials.vue:149-154,170-192 | 低 | S |
| C101 | 3 | `.hint` 灰底说明块在每个页签重复且长度不一（上传页签 3 行、其余 2 行），信息层级高于表单本身；表单字段宽度 `max-width:560/640px` 两种，字段横向排布在 COS 页签是 `label-width:90px` 而上传页签是 inline 表单，视觉节奏不统一（实际观感需实测确认） | apps/admin-web/src/views/channel/CourseMaterials.vue:36-40,92-95,62-84,96-101 | 低 | S |
| C102 | 4 | 页签顺序按实现排列而非按使用频次：高频的「本地文件上传」在首位是对的，但「云端存储导入」COS 需要手填对象 Key 却无任何浏览/选择文件入口（同项目有「云端存储 → 文件管理」页），提示里也没给出可跳转入口 | apps/admin-web/src/views/channel/CourseMaterials.vue:90-115；apps/admin-web/src/router/index.js:161-166 | 中 | S |

**优化建议**：
- C91：后端 upload 接口改为收集式去重（返回 `created/skipped/duplicated_chapters`，不中断循环），前端结果区展示「新增 N 章、跳过 M 章（重复）」。
- C92：手动录入支持传入 `source_type`（分享导入路径传 `qrcode` 并携带 URL），否则删除两处「source_type=qrcode」字样并把页签改名为「链接预览转录」。
- C93：统一成功文案为「已保存到素材库」，并在 toast/结果条上附「到素材库管理查看」链接（携带 `?source=书名&channelId=`）。
- C94：加 `on-exceed` 提示「仅支持单个文件，请先移除已选文件」，或放开 limit 支持多选批量上传。
- C95：三个未选频道的按钮复用同样的 tooltip 包装（把 `uploadDisabledReason` 提到通用函数）。
- C96：把「目标频道」做成页签内表单的第一项（并在页签切换时保持），页面顶部保留只读回显。
- C97：提示改「list 类型按正文内容在本频道去重，URL 仅作溯源」。
- C98：在各页签 hint 增一行「去重范围」说明，并在 URL 拉取 409 时给「已在素材库，是否改标题重新入库」的分支引导。
- C99：上传时加可见进度条与耗时提示；把 axios 超时错误映射为「解析超时（>60s），请拆分文件或改用 PDF 文本层」的中文文案。
- C100：删掉「类型」下拉里的「分享链接」项（该场景已有专用页签）。
- C101：`.hint` 收进各页签首行的 `el-alert :closable="false"` 并统一宽度与 `label-width`。
- C102：COS 页签加「从文件管理选择」按钮（跳 `/cos-files` 并回填 key）。

---

### C-14 内容运营 > 找书工具（路由 /ebooks，BookFinder.vue）

**现状描述**：顶部说明 alert（明确"检索自动化、取件人工"）+ 索引状态卡片（就绪/构建中/未构建 + 构建按钮）+ 检索表单（关键词/分类/上限 + 检索/随机/刷新分类）+ 结果元信息 + 结果表（打开链接、加入书单）。索引构建用 3s 轮询。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C103 | 1 | 「加入待讲书单」名字与落库位置完全不同：按钮/列名都叫"待讲书单/加入书单"，而实际写入的是素材库一条占位素材（`source_type='book_plan'`、`channel_id=req.channel_id`），前端调用不传 `channel_id` → 落库为 null。结果：它既不在「讲书稿素材池」书单里（候选按 channel_id 过滤），也不在任何"书单"界面上，只能在全频道视图的素材库里靠书名搜到。首次用户点完按钮以为书已排上，链路实际断在这里 | apps/admin-web/src/views/ebooks/BookFinder.vue:118-130,209-228；backend/app/routers/admin/ebooks.py:145-188,40-47；backend/app/services/book_pool_service.py:345-352 | 高 | M |
| C104 | 4 | 顶部 alert 与结果元信息互相矛盾：分类下拉 placeholder 写「全部分类（较慢）」，而索引就绪时元信息又显示「结果来自本地索引（毫秒级）」；同一页两处对"全量搜索快不快"给出相反预期 | apps/admin-web/src/views/ebooks/BookFinder.vue:67-70,96-100 | 中 | XS |
| C105 | 2 | 索引未就绪时的"检索"会顺带启动全量重建：`onSearch` 分支在没选分类且索引未就绪时只弹一条 warning 就 `await onRebuildIndex()`（重操作，抓 1000 个分类、2-5 分钟、后台占资源），既不确认也不显示当前构建状态；同一按钮文案在「构建索引 / 重建索引」间切换但都是同一个动作 | apps/admin-web/src/views/ebooks/BookFinder.vue:262-284,312-321,42-50 | 中 | S |
| C106 | 5 | 加入书单后无任何后续指引：成功只提示「《X》已加入待讲书单」，不显示占位素材 ID、不提供「去素材录入上传书稿」或「在素材库查看」链接；而按钮所在行的下载链接是外部网盘，用户下一步动作完全靠记忆（顶部 alert 里那句长文） | apps/admin-web/src/views/ebooks/BookFinder.vue:209-228,4-11 | 中 | S |
| C107 | 6 | 结果表无「已加入/已在素材库」标记：同一本书第二次点击靠后端 `created:false` + message 兜住，界面上每行"加入书单"图标始终是可点状态；批量找书时无法一眼筛掉已处理项 | apps/admin-web/src/views/ebooks/BookFinder.vue:119-130,218-221 | 中 | M |
| C108 | 3 | 结果表两个 `fixed="right"` 列（下载 130 + 待讲书单 130）叠加在书名/作者/分类之上，窄屏下固定列遮挡正文的风险（EP 多固定列需实测确认）；书名/作者列无复制按钮，人工下载时反复手抄书名 | apps/admin-web/src/views/ebooks/BookFinder.vue:106-137 | 中 | S |
| C109 | 4 | 「上限」只作用于「检索」，「随机」内部固定 10 本，表单里没有任何说明；用户调到 100 再点随机，结果只有 10 行会以为出错 | apps/admin-web/src/views/ebooks/BookFinder.vue:78-86,249-253 | 低 | XS |
| C110 | 5 | 构建轮询无终止上限也不区分失败：`startPolling` 每 3s 拉状态，只在 `!building` 时停；若后端重启导致 `build.running` 恒 false 但 `ready` 仍 false，界面回落「索引未构建」而用户不知道之前的构建去哪了；页面切走再回来不显示历史失败原因 | apps/admin-web/src/views/ebooks/BookFinder.vue:292-310 | 低 | S |
| C111 | 2 | 「重建索引」无二次确认（索引已就绪时点它=全量重抓，成本最高），也没有"上次构建耗时/是否建议重建"提示；`el-alert` 里的授权声明（勿商用）是一次性长文，结果表里没有逐行提示 | apps/admin-web/src/views/ebooks/BookFinder.vue:42-50,312-321,5-11 | 中 | XS |
| C112 | 6 | 本页仅 `require_admin` 的后端接口（ebooks 全部端点）配合前端无角色判断：operator 进入即满屏 403（`categories/index/status` 都 require_admin），页面首挂就弹多条「无权限执行此操作」 | apps/admin-web/src/views/ebooks/BookFinder.vue:323-326；backend/app/routers/admin/ebooks.py:52-62,196-200 | 中 | S |

**优化建议**：
- C103：把按钮改名「登记为待上传书稿」，并在成功提示后直接给「去素材录入」跳转（带书名）；若要真进"书单"，前端必须让用户先选目标频道（新增频道选择器）并传 `channel_id`，同时把 `book_plan` 纳入 `MaterialSourceType` 与素材库筛选项。
- C104：placeholder 改「全部分类（索引已就绪时同样快）」或按 `indexReady` 动态显示。
- C105：触发重建前用确认框说明代价，并把按钮文案固定为「重建」，搜索分支只提示 + 引导选分类，不自动发起重建。
- C106：结果 toast 改 `ElMessageBox`/内联提示条：「已登记占位素材 #123（频道：未指定）→ 下载后到『素材录入』上传」。
- C107：检索响应附带"是否已入库"标记（后端按 url 比对），已加入行显示 tag 并把按钮置灰。
- C108：合并「下载」与「加入」到一个固定操作列（宽度 180），书名/作者加悬浮复制；固定列遮挡情况请实测确认后再决定是否减列。
- C109：随机按钮 desc 补「随机抽取 10 本，不受『上限』影响」。
- C110：轮询加最长时长与失败态提示（「构建状态获取失败，点这里手动刷新」）。
- C111：重建加确认；把授权声明以行内 tag/悬浮形式带到每行下载链接上。
- C112：非 admin 隐藏本页菜单或在页面顶部显示权限说明（与路由 `requireRole` 机制一致，见 workflow 路由）。

---

### C-15 跨页数据链、批量导入导出与文档/引导一致性（汇总）

**现状描述**：链路为 找书工具（检索/登记占位）→ 素材录入（五渠道入库）→ 素材库管理（浏览/编辑/按书聚合）→ 讲书稿素材池（整本入池/排序/进度）→ 频道管理（模式开关与取书相关配置）。跳转目前只有 池→库 一条（带 channelId/keyword/materialId），库/录入/找书三页之间没有可点链接；由于 Layout 未使用 keep-alive，跨页会重新拉数，因此数据本身不陈旧，丢的是筛选上下文。

**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| C113 | 1 | 链路只有单向跳：池 → 库（「管理素材 ↗」、素材 ID 深链）；库没有回池链接，素材录入没有到库/池的链接，找书工具到素材录入只有文字描述无可点入口。运营走完"下载→上传→加池"要在菜单里手动来回 4 次 | apps/admin-web/src/views/channel/BookPoolPanel.vue:101-105,321-340；apps/admin-web/src/views/channel/MaterialLibrary.vue:4-10；apps/admin-web/src/views/channel/CourseMaterials.vue:27-31；apps/admin-web/src/views/ebooks/BookFinder.vue:4-11 | 中 | S |
| C114 | 1 | 同一实体（Material）在三个界面被三种名字与三套字段编辑：菜单「素材库管理」/后端 docstring「频道级素材池」/工作流详情面板「爬虫采集 · 素材」；且字段口径不同——工作流详情用「品类」+「待处理/已选中」+ 必填 URL，素材库管理用「分类」+「待消费/已选题」+ 无 URL 字段。同一条素材在两处看起来是两种东西，改一处另一处需手动刷新（各页有「刷新」与否也不同） | apps/admin-web/src/views/channel/MaterialLibrary.vue:167-205,303；apps/admin-web/src/views/workflow/WorkflowDetail.vue:81-108,344-390,574；backend/app/routers/admin/materials.py:211-213 | 高 | M |
| C115 | 4 | 新手引导与帮助对这条链完全缺失：`Help.vue` 只有「频道管理」章节（内容审核/广告/统计/队列/工作流等），没有素材库管理、讲书稿素材池、素材录入、找书工具任何文档；`guideConfig.js` 虽有这四条路由的引导项，但 `/ebooks` 的步骤选择器写 `.toolbar`/`.top-bar`（页面上不存在这两个类），高亮必然落空，且描述「命中书目与下载状态一目了然」对应的"下载状态"列并不存在 | apps/admin-web/src/views/help/Help.vue:264-296；apps/admin-web/src/guide/guideConfig.js:60-64；apps/admin-web/src/views/ebooks/BookFinder.vue:2-139（无 .toolbar/.top-bar，也无下载状态列） | 中 | M |
| C116 | 6 | 引导文案与实际能力多处不符：`/channels` 引导写「按向导创建新频道」（实际是四页签弹窗，无向导步骤）；`/channels/material-library` 引导写「统一管理讲书稿素材」（实际是全渠道素材，含海量 RSS 资讯）；`/channels/book-pool` 引导写「支持从素材库一键加入」而实际只能逐本勾选、且超过 50 本翻不到 | apps/admin-web/src/guide/guideConfig.js:43-55；apps/admin-web/src/views/channel/ChannelManagement.vue:83-504；apps/admin-web/src/views/channel/BookPoolPanel.vue:303-315 | 中 | XS |
| C117 | 2 | 全链没有任何批量导入/导出：素材录入只支持单文件（`limit=1`）、书单只能逐本勾选、素材库无导出（运营无法把外部选书表/清理清单落进或带出系统），与"每日运营"频次不匹配 | apps/admin-web/src/views/channel/CourseMaterials.vue:49-61；apps/admin-web/src/views/channel/BookPoolPanel.vue:49-52；apps/admin-web/src/views/channel/MaterialLibrary.vue:73-161 | 中 | M |
| C118 | 5 | 概念称谓在两页 tips 间漂移造成误解：「进度/已取/已用」「素材/讲书稿/书稿」「池/库」「章节/待讲/待消费」——同一数字在池里叫「已取」、在候选里叫「待讲章节」、在素材库聚合里叫「待消费章节」；后端 aggregate 文档串写「待消费」而 book_pool 服务写「待讲」，前端两页各自照抄 | apps/admin-web/src/views/channel/BookPoolPanel.vue:36,117,83-87；apps/admin-web/src/views/channel/MaterialLibrary.vue:126；backend/app/routers/admin/materials.py:300-302；backend/app/services/book_pool_service.py:347-348 | 中 | S |
| C119 | 6 | 图标语义在全站不一致：`Refresh` 在本链里同时表示「AI 推荐」（频道管理 divider 按钮）、「重建索引/刷新分类」（找书工具两个按钮）、「重置进度」（池面板），`Plus` 同时表示「新增频道」「上传图标」「上传 BGM」「从素材库加入」「手动录入素材」「上传并解析」「转为手动录入」——项目已有「同类功能同一图标」的组件约定（IconButton 注释），但本链未按图标语义区分动作类型 | apps/admin-web/src/components/IconButton.vue:44-52；apps/admin-web/src/views/channel/ChannelManagement.vue:232-243,412-430；apps/admin-web/src/views/ebooks/BookFinder.vue:42-50,85；apps/admin-web/src/views/channel/BookPoolPanel.vue:43,51 | 中 | S |
| C120 | 3 | 全链所有操作按钮为纯图标（`label` 只进 `aria-label`/tooltip，`inlineText` 在 src 下无任何调用点），首次用户在 5 个页面里看不到任何带文字的主 CTA；`desc` 悬浮文案长度 15–25 字，tooltip 150ms 延迟 + 需逐个试探 | apps/admin-web/src/components/IconButton.vue:19-31,66-72；apps/admin-web/src/views/channel/MaterialLibrary.vue:8；apps/admin-web/src/views/channel/CourseMaterials.vue:73-81（全仓无 inlineText 用例） | 中 | M |

**优化建议**：
- C113：给四个页面加统一的「链路导航条」（找书 → 素材录入 → 素材库 → 讲书稿书单 → 频道配置，标当前步，点击带 `channelId`），并在素材录入/找书结果的成功提示里附直达链接。
- C114：确立唯一术语「素材库」+ 建一份单一状态字典（建议落 `src/constants/materialStatus.js` 供本页与工作流详情共用，后端同步补 `MaterialStatusLabels` 常量——目前全仓不存在该常量，`pending/selected/skipped` 的中文在两页分别是「待消费/已选题/已跳过」与「待处理/已选中/已跳过」）；注意与频道侧「已生产/待补采」属不同实体，统一命名需由评审汇总层定名后再改，不可在本链里就地替换；素材编辑弹窗抽成共享组件 `MaterialEditDialog`，工作流详情复用，不再维护第二套字段；跨页写操作后用统一事件（或简单提示「另一处需点刷新」）。
- C115：补 Help 四节（含"占位素材在哪看""50 本上限"等已知坑），并修正 `guideConfig.js` 的 `/ebooks` 选择器为真实存在的 `.index-card/.search-card/.result-card` 与 `.el-table`，删除不存在的"下载状态"描述。
- C116：引导文案按实际能力改写（「四页签表单」而非「向导」；「全渠道素材，可用来源类型筛书稿」）。
- C117：素材库加「导出当前筛选 CSV」，池加「从 CSV 导入书名」，上传支持多文件（并配套 C91 的收集式去重）。
- C118：数字统一叫法：池用「进度 已讲 X/共 Y」，候选与聚合用「章节 N（待讲 M）」并在两处使用同一组件渲染（抽 `BookChapterStat.vue`），避免前端各抄一份后端文案。
- C119：约定图标语义映射（新增=Plus、重生成=MagicStick/Refresh+「AI」文字、重置=RefreshLeft、刷新列表=Refresh），并给 AI 类按钮加 `inlineText="AI"`。
- C120：至少给每页 1 个主 CTA 与所有危险/确认类操作配 `inlineText`（新增频道 / 上传并解析 / 从素材库加入 / 检索 / 保存），其余保留纯图标。

**说明**：跨页"数据陈旧"方面未发现显著缺陷——`Layout.vue` 未启用 `<keep-alive>`（apps/admin-web/src/layouts/Layout.vue:75），路由切换会重新挂载并拉数，因此不存在"改了另一页必须手动刷新"的数据问题；真正缺失的是上下文保留（见 C63/C64/C69）与面板内的过期预览（见 C80）。

---

## 4. 广告管理 3 菜单 + 数据分析 4 菜单

> 走查范围：`apps/admin-web/src/views/ad/*.vue`、`apps/admin-web/src/views/stats/*.vue`、`apps/admin-web/src/api/ads.js`、`apps/admin-web/src/api/stats.js`，并交叉核对 `backend/app/routers/admin/{ads,stats}.py`、`backend/app/services/{ad_service,stats_service,rss_source_service}.py`、`backend/app/models/{ad_material,ad_placement,play_log}.py` 与 `backend/app/workflow/llm/rewriter.py`，用于确认统计口径与单位。菜单名以 `src/router/index.js` 的 `meta.title`（广告素材 / 投放规则 / 排期日历 / 数据统计 / 频道健康度 / RSS 源状态 / LLM 重试指标）为准。纯只读，未做任何修改。

### D-1 广告管理 > 广告素材（路由 /ads/materials，文件 apps/admin-web/src/views/ad/AdMaterials.vue）

**现状描述**：单表 CRUD（仅新增 + 删除），列为名称/描述/时长(秒)/默认占位/操作，后端返回的 `created_at`、`file_url` 未在列表展示。主操作是工具栏最左侧一枚纯图标「＋」按钮，空态与主操作文案存在方位/名称错配。试听复用页面底部一个隐藏 `<audio>`，无任何播放态反馈。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| D1 | 4 | 空态文案「暂无广告素材，点击右上角「新增素材」上传」三处失真：按钮实际在**左上角**（`.toolbar` 为 `justify-content: space-between` 且只有 1 个子项），按钮**无可见文字**（纯图标，只有 hover tooltip），且实际不是「上传」而是手填文件 URL | apps/admin-web/src/views/ad/AdMaterials.vue:52；:4-12；:70-99 | 中 | XS |
| D2 | 2 | 首次使用只看到一枚绿色「＋」，不看 tooltip 无法判断是新增素材还是刷新；主操作按钮全站未用 `inlineText` 承载文字 | apps/admin-web/src/views/ad/AdMaterials.vue:5-11；apps/admin-web/src/components/IconButton.vue:22-26 | 中 | XS |
| D3 | 1 | 无「编辑」能力：要改描述或换 URL 只能删除后重建；后端也只提供 POST/DELETE，素材名一旦被投放引用就无法纠正 | apps/admin-web/src/views/ad/AdMaterials.vue:31-51；backend/app/routers/admin/ads.py:46-79 | 中 | M |
| D4 | 5 | 删除按钮对「有关联投放」的素材仍可点，用户完成二次确认后才会收到后端 `该素材有关联投放，无法删除` 报错；确认框文案未提示该约束，形成「确认了个寂寞」的死循环 | apps/admin-web/src/views/ad/AdMaterials.vue:41-49；:187-195；backend/app/services/ad_service.py:74-82 | 中 | S |
| D5 | 4 | 列头「默认占位」含义不明（后端语义是「默认自营占位素材」），仅有绿色「默认」标签，无 tooltip/说明告诉运营「默认」意味着 C 端兜底播放，也解释了为何该行删除按钮被禁用 | apps/admin-web/src/views/ad/AdMaterials.vue:25-30；:41-44；backend/app/models/ad_material.py:25-27 | 中 | XS |
| D6 | 3 | 后端已返回 `created_at` 但列表不展示，运营无法确认「刚登记的那条是否成功入库」，只能靠名称肉眼比对；列表也无任何排序/搜索控件 | apps/admin-web/src/views/ad/AdMaterials.vue:17-30；backend/app/services/ad_service.py:52 | 中 | S |
| D7 | 5 | 试听无任何播放态：无暂停/停止按钮、无进度与时长显示、无「正在播放：xxx」标识；再次点击同图标行为不确定（从头重播还是无反应），只有失败才弹 warning | apps/admin-web/src/views/ad/AdMaterials.vue:197-205；:120 | 中 | S |
| D8 | 5 | 「文件 URL」字段仅必填校验、无格式/协议校验，可提交 `abc` 之类任意文本并「创建成功」，错误被推迟到点击试听才暴露 | apps/admin-web/src/views/ad/AdMaterials.vue:89-91；:149-153 | 中 | XS |
| D9 | 2 | 切换每页条数未重置页码：在第 5 页（size=10）改为 size=50 时仍请求 `page=5`，超出页数后表格显示空列表但分页栏仍显示 total>0，看起来像「数据丢了」 | apps/admin-web/src/views/ad/AdMaterials.vue:57-66；:155-166 | 中 | XS |
| D10 | 6 | 列表请求失败只有全局 toast（窗口隐藏时还会被静默丢弃），页面停留在上一次数据或空态，无「重试」入口；`fetchList` 只有 try/finally 无 catch | apps/admin-web/src/views/ad/AdMaterials.vue:155-166；apps/admin-web/src/utils/message.js:28-33 | 中 | S |
| D11 | 6 | `handleSubmit`/`handleDelete` 直接 `await formRef.value.validate()`、`await ElMessageBox.confirm()` 而不 catch，表单校验失败或用户点「取消」都会抛出未处理 Promise 异常刷控制台（与 LLM 页有 catch 的写法不一致） | apps/admin-web/src/views/ad/AdMaterials.vue:175；:189；对照 apps/admin-web/src/views/stats/LlmMetrics.vue:197 | 低 | XS |

**优化建议**：
- D1：空态文案改为「暂无广告素材，点击左上角「新增素材」登记音频地址」；同步 D2 给主按钮加 `inline-text="新增素材"`，使文案与界面按钮名一一对应。
- D2：主操作按钮统一「图标 + 精简文字」，与列表页高频操作惯例一致（IconButton 已支持 `inlineText`）。
- D3：后端补 `PUT /ads/materials/{id}`，操作列加「编辑」，对话框复用；在此之前至少在删除确认框中提示「如需修改请先删除后重建，将影响关联投放」。
- D4：列表接口返回 `placement_count`，行内展示「关联投放 N」，N>0 时禁用删除并 tooltip 说明原因，避免「确认后才报错」。
- D5：列头改「自营兜底」并加 `el-tooltip`（「C 端无投放排期时兜底播放的素材，不可删除」）。
- D6：加「创建时间」列（相对时间 + 绝对时间 tooltip），并提供名称搜索框（可前端过滤当前页 + 后端加 keyword 参数）。
- D7：试听改为行内播放器或页面底部固定播放条：显示素材名、播放/暂停切换、进度与时长；播放中该行图标切换为「暂停」。
- D8：`file_url` 增加 `type: 'url'` 规则与 `http(s)://` 前缀校验，并支持「粘贴 COS 地址 / 从文件管理选择」两种入口。
- D9：`@size-change` 内先 `page.value = 1` 再 `fetchList()`；两个 Ad 页同样处理。
- D10：请求失败时保留数据但显示顶部 `el-alert` 「上次更新失败：xxx（重试）」，并提供手动刷新按钮（与统计页统一）。
- D11：所有 `validate()`/`confirm()` 包 try/catch 或 `.catch(() => {})`，消除未处理 rejection。

### D-2 广告管理 > 投放规则（路由 /ads/placements，文件 apps/admin-web/src/views/ad/AdPlacements.vue）

**现状描述**：列表只有素材名称/广告位/开始日期/结束日期四列与一个删除操作，新建走对话框（素材下拉 + 广告位 + 日期范围）。后端 `AdPlacement.enabled` 与 `PUT /ads/placements/{id}`（移动端启停）已存在，但 PC 页既不显示 `enabled` 也不提供启停开关，与移动端能力割裂。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| D12 | 4 | 空态文案「点击右上角「新增规则」创建」指向一个**不存在的按钮名**（实际按钮 aria-label 为「新建投放」），且按钮在左上角、无可见文字；运营按文案找不到「新增规则」 | apps/admin-web/src/views/ad/AdPlacements.vue:38；:5-11；:96-109 | 中 | XS |
| D13 | 1 | 后端列表已返回 `enabled`（1/0），PC 表格无「状态」列、无开关，也没有按状态筛选：在移动端停用的规则在 PC 列表中与生效规则**完全同貌**，运营据此判断「这条还在投」 | apps/admin-web/src/views/ad/AdPlacements.vue:15-37；backend/app/services/ad_service.py:122；apps/admin-web/src/api/ads.js:12-14 | 高 | S |
| D14 | 5 | 「停用」这条唯一的可逆干预路径 PC 上不可用，只能删除（不可逆）；而移动端可用的 `PUT /ads/placements/{id}` 对不存在的 id 会 500（`error()` 未在 `ads.py` 导入），且 C 端 `get_active_placements` 查询**不过滤 enabled**，停用后客户端仍会播出该广告 → 开关不可信 | apps/admin-web/src/api/ads.js:13；backend/app/routers/admin/ads.py:9-10；:106-128；backend/app/services/ad_service.py:237-238 | 高 | M |
| D15 | 2 | 日期范围可选「同一天」，提交后后端以 `start_date >= end_date` 拒绝并弹出原文 `start_date 必须早于 end_date`（暴露英文字段名，且未说明「至少跨两天」），单日投放实际无法创建、用户不知如何修正 | apps/admin-web/src/views/ad/AdPlacements.vue:84-92；:184-195；backend/app/services/ad_service.py:161-162 | 高 | S |
| D16 | 2 | 素材下拉硬截断为 `page=1&size=100`，第 101 条起的素材在列表里根本不存在，`filterable` 只能在已加载的 100 条内搜索，且无任何「仅显示前 100 条」提示 → 运营会认定「素材没上传成功」 | apps/admin-web/src/views/ad/AdPlacements.vue:59-71；:171-176；backend/app/routers/admin/ads.py:36-37 | 高 | S |
| D17 | 3 | 列表无「未开始 / 生效中 / 已过期」状态标识，仅两列裸日期，是否正在投放要运营用心算当日与区间关系；也无按状态/日期排序 | apps/admin-web/src/views/ad/AdPlacements.vue:24-25 | 中 | S |
| D18 | 2 | 同一广告位、日期重叠的多条规则可反复创建，前后端都无冲突校验；后果直接体现在排期日历静默覆盖（见 D-3/D23），创建时零提示 | apps/admin-web/src/views/ad/AdPlacements.vue:184-202；backend/app/services/ad_service.py:140-172 | 中 | M |
| D19 | 4 | 删除确认文案为不带上下文的「确认删除该投放规则？」，未含素材名/广告位/日期区间，与素材页「确认删除素材「${row.name}」？」的写法不一致，多行同素材时无法确认删的是哪条 | apps/admin-web/src/views/ad/AdPlacements.vue:205；对照 apps/admin-web/src/views/ad/AdMaterials.vue:189 | 中 | XS |
| D20 | 5 | 素材选项在「点开对话框那一刻」才异步拉取：`el-select` 无 loading 态与失败提示，请求失败时下拉是空白「无匹配数据」，看起来像素材库为空 | apps/admin-web/src/views/ad/AdPlacements.vue:178-182；:59-71 | 中 | S |
| D21 | 1 | 广告位标签配色与排期日历不一致：本页 mid 用 `danger`（红）、tail 用 `info`（灰），日历 mid 用蜜桃粉、tail 用浅紫，同一「中间/结尾」在两个菜单里颜色语义不同 | apps/admin-web/src/views/ad/AdPlacements.vue:146-155；apps/admin-web/src/views/ad/AdSchedule.vue:171-179 | 中 | XS |
| D22 | 2 | 列表无任何筛选（素材/广告位/时间区间/状态），仅有分页；投放规则累积后运营只能逐页翻找当月规则 | apps/admin-web/src/views/ad/AdPlacements.vue:3-12；:41-52 | 中 | M |

**优化建议**：
- D12：改为「暂无投放规则，点击左上角「新建投放」创建」，并给按钮加文字。
- D13：加「状态」列（生效中/未开始/已过期/已停用四态染色 tag）+ 行内 `el-switch`（复用 `api/ads.js` 的 `updatePlacement`，替换现有裸 `api.post/delete`），筛选项按状态过滤。
- D14：PC 补启停入口 + 后端把 `enabled=1` 加入 `get_active_placements`/`get_schedule` 过滤，并修掉 `ads.py` 缺失的 `error` 导入；停用成功文案明确「已停用，C 端下次排期生效可能有 25h 缓存延迟」（`ACTIVE_PLACEMENT_TTL`）。
- D15：日期选择器加 `:disabled-date` 约束 + 提交前本地校验「结束日期需晚于开始日期」，或后端放开单日投放；错误提示改为业务语言「投放至少需要跨 1 天，请把结束日期设为开始日期的次日」。
- D16：改为远程搜索分页下拉（`remote` + `loading` + 显示总数「共 N 条，输入关键词检索」），或直接列出素材名 + 时长 + 默认标识的可选表格。
- D17：`start_date/end_date` 合并为「投放区间」列并附「剩余 N 天 / 已结束」次要文本。
- D18：新建成功后若同位同区间已存在，返回冲突列表并弹「该广告位在此区间已有投放，是否覆盖？」（后端加唯一性检查或前端提交前查询）。
- D19：确认文案带实体标识：「确认删除「{material_name}」在 {position}（{start}~{end}）的投放？」
- D20：`el-select` 加 `:loading`，失败时下拉内显示「素材列表加载失败，重试」。
- D21：抽出 `constants/adPosition.js` 统一 label/tag type/色值，两页共用（含 D-3 图例）。
- D22：筛选栏（广告位 + 生效状态 + 日期区间 + 素材搜索），并把筛选条件写入 query 或 localStorage 便于次日复用。

### D-3 广告管理 > 排期日历（路由 /ads/schedule，文件 apps/admin-web/src/views/ad/AdSchedule.vue）

**现状描述**：只读月历，每格固定渲染 head/mid/tail 三行，数据来自 `/ads/schedule?month=YYYY-MM`，前端把每条投放按天展开成 `{日期: {position: {material_name}}}` 的 map。顶部一枚月份选择器 + 图例，无操作入口。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| D23 | 5 | 已停用的投放仍出现在日历上：后端 `get_schedule` 只按日期区间过滤、不看 `enabled`，前端也无任何标记 → 运营在日历看到某天写着「品牌口播A」，实际该规则已被停用，据此判断「广告还在投」属误读 | apps/admin-web/src/views/ad/AdSchedule.vue:77-100；backend/app/services/ad_service.py:200-204 | 高 | S |
| D24 | 3 | 同广告位日期重叠时静默覆盖：`map[dateKey][p.position] = {material_name}` 后写覆盖前写，日历只显示其中一条，既无「+1 条冲突」角标也无 tooltip 展示其余素材 | apps/admin-web/src/views/ad/AdSchedule.vue:93-97 | 高 | S |
| D25 | 5 | 加载失败零反馈：`fetchSchedule` 只有 try/finally 无 catch，失败时 `scheduleMap` 保留上一个月的数据，日历切到新月份后全部显示「—」，用户读作「本月无排期」；页面无错误提示与重试按钮（全局 toast 还会被 `document.hidden` 吞掉） | apps/admin-web/src/views/ad/AdSchedule.vue:77-104；apps/admin-web/src/utils/message.js:28-33 | 高 | S |
| D26 | 1 | 纯只读页无任何出口：点击日期格无反应，没有「在本日新建投放 / 查看该规则」入口，也没有引导文案指向真实菜单名「投放规则」，运营必须自己想到去另一个菜单 | apps/admin-web/src/views/ad/AdSchedule.vue:32-53；:9-16 | 中 | S |
| D27 | 6 | 月份切换存在两个入口（顶部 `el-date-picker` 与 `el-calendar` 自带「上月/下月」按钮 + 标题），二者互为 watch 同步；重复选同一月份时 `calendarDate` 被赋新 Date 对象仍会触发一次多余请求 | apps/admin-web/src/views/ad/AdSchedule.vue:5-13；:107-126 | 低 | S |
| D28 | 3 | 图例与单元格配色不一致：图例块用 0.5/0.8/0.7 透明度实色，单元格背景用 0.15/0.5/0.4，肉眼难以把「开头」青点与「开头」浅底对应；且「中间」用蜜桃粉（近似红）易与告警色混淆（需实测确认对比度） | apps/admin-web/src/views/ad/AdSchedule.vue:171-179；:232-240 | 中 | S |
| D29 | 3 | 素材名过长被 `ellipsis` 截断且**无 title/tooltip**，只剩前几字，运营无法确认是哪条素材；日期格空间紧张（`min-height: 80/90px` 内塞 3 行标签） | apps/admin-web/src/views/ad/AdSchedule.vue:44-47；:220-225；:183-205 | 中 | XS |
| D30 | 2 | 无「今天」锚点：只有被选中单元格高亮（且我们自定义成薄荷绿底），用户易把「选中态」读成「今天」；跨月查看后需手动点回，日历也无「回到本月」按钮 | apps/admin-web/src/views/ad/AdSchedule.vue:32；:269-275 | 低 | XS |
| D31 | 4 | 页面没有任何数据口径说明：不显示「共 N 条投放覆盖本月」、无「更新于 xx:xx」，空月份与无权限/失败三种情况视觉相同（一片「—」） | apps/admin-web/src/views/ad/AdSchedule.vue:1-55 | 中 | S |
| D32 | 6 | 跨月区间显示不完整：后端按「与该月重叠」返回，但前端把区间内所有日期（含上月/下月天）都写进 map，非当月格被 `opacity: .4` 弱化，上月那几天照常填充，用户可能误认为那属于本月统计 | apps/admin-web/src/views/ad/AdSchedule.vue:92-97；:243-251 | 低 | XS |

**优化建议**：
- D23：请求返回后按 `enabled` 区分（后端补字段），停用的格子加删除线/灰态并 tooltip「已停用，不会播放」；同时提供「仅看生效」开关。
- D24：map 值改为数组，格内显示首个素材 + `+N` 角标，hover 出 popover 列出该位该日的全部投放与区间，冲突时给 warning 色。
- D25：`fetchSchedule` 加 catch → 保留月份、清空 map、页面顶部显示 `el-alert`「排期加载失败：{msg}」+「重试」；不要出现「无数据」与「加载失败」同貌。
- D26：日期格加 hover 出现「＋ 新建」链接（跳 `/ads/placements` 并带上预填日期 query），图例右侧加说明「本日历只读，排期请在「投放规则」中维护」（菜单名与 `meta.title` 一致）。
- D27：只保留日历自带表头导航（或只保留月份选择器），并对同月份重复赋值做等值判断后再 fetch。
- D28：图例改用与单元格完全相同的底色块；抽 `--ad-pos-head/mid/tail` 三个 CSS 变量，与投放规则页 tag 共用（配合 D21）。
- D29：`slot-name` 加 `:title`，并在 popover 中展示完整名称 + 时长 + 创建人/时间；素材名超过格宽时改为纵向堆叠或缩略 + 悬浮展开。
- D30：给今天加独立样式（描边 +「今天」小徽标），并在日历表头加「回到今天」按钮。
- D31：日历上方加统计条「本月生效投放 12 条 / 覆盖 21 天 / 数据更新于 10-05 09:12」；空月份显示显式空态「本月暂无排期，去「投放规则」新建」。
- D32：非当月日期不渲染排期内容（仅灰显日期），避免跨月视觉混淆。

### D-4 数据分析 > 数据统计（路由 /stats，文件 apps/admin-web/src/views/stats/StatsOverview.vue）

**现状描述**：顶部一个日期选择器（默认今日）驱动 5 张指标卡（DAU / 播放量 / 完播率(%) / 平均收听(分钟) / 广告曝光），下方一张折线趋势卡（指标 3 选 1 + 区间 7d/30d）。趋势区间与顶部日期互不影响，且后端趋势恒返回 `range_days` 个点（缺失日补 0）。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| D33 | 6 | 「平均收听(分钟)」显示的是**秒**：后端取 `AVG(play_log.duration)`，该列模型注释为「本次会话已播放时长（秒）」，前端直接贴「(分钟)」标签不做换算 → 数值虚高 60 倍（平均 300 秒被读成 300 分钟） | apps/admin-web/src/views/stats/StatsOverview.vue:84；backend/app/services/stats_service.py:42；:53-55；backend/app/models/play_log.py:32 | 高 | XS |
| D34 | 6 | 同一指标两处单位不一致：概览卡把 `completion_rate` ×100 显示为百分数，趋势图把后端原始 0~1 序列（`func.avg(PlayLog.completed)`）直接画线，系列名却叫「完播率(%)」，Y 轴刻度是 0.00–1.00 → 卡片写 62.5、图写 0.625 | apps/admin-web/src/views/stats/StatsOverview.vue:83；:96-100；:104-131；backend/app/services/stats_service.py:85-86 | 高 | S |
| D35 | 5 | 空数据被画成 0 折线：后端对区间内每一天补 0，前端 `hasTrend` 只判断 `dates.length>0`（恒为真），「暂无趋势数据」空态几乎不可达 → 新上线/埋点缺失/查询为空的区间显示成「断崖归零」 | apps/admin-web/src/views/stats/StatsOverview.vue:93；:46-48；backend/app/services/stats_service.py:108-110 | 高 | S |
| D36 | 1 | 筛选作用范围无标注：日期选择器只刷新卡片，趋势卡永远基于 `date.today()` 往前 N 天（后端不使用 date 参数），页面上既没写「近 7 天（截至今日）」，切换日期后趋势图纹丝不动 → 运营以为两者联动 | apps/admin-web/src/views/stats/StatsOverview.vue:5-13；:147-158；backend/app/services/stats_service.py:75-77 | 高 | S |
| D37 | 5 | 趋势无任何加载态：`loadTrend` 没有 loading 变量也没有 try/finally，切换指标时图表静默等待；同时系列名取自 `metric.value`（立即变更）而数据仍是上一个指标返回的 values，出现「新指标名 + 旧曲线」的假象；请求失败产生未处理 rejection | apps/admin-web/src/views/stats/StatsOverview.vue:156-158；:101-119 | 中 | S |
| D38 | 3 | 页面级 `v-loading` 挂在最外层：仅切换日期也会把趋势卡一并遮罩闪烁；同时卡片/趋势两个请求共用一个 spinner，无法区分是哪个在加载 | apps/admin-web/src/views/stats/StatsOverview.vue:2；:147-154 | 中 | XS |
| D39 | 4 | 「广告曝光」是推算值 `play_count * 3`（后端注释「每期固定三段广告」），前端当作真实曝光埋点展示且无脚注 → 用其评估广告效果会系统性高估（无点击/完播口径） | apps/admin-web/src/views/stats/StatsOverview.vue:85；backend/app/services/stats_service.py:57-63 | 高 | S |
| D40 | 2 | 日期选择器无快捷项（今天/昨天）也未禁用未来日期：可任选 2099-01-01，卡片返回后端补零后的全 0（`dau or 0` 等），看起来像「数据崩塌」而非「无数据」 | apps/admin-web/src/views/stats/StatsOverview.vue:5-13；:80-86；backend/app/services/stats_service.py:50-55 | 中 | S |
| D41 | 3 | 「平均收听(分钟)」用裸值渲染（无 `formatNum`、无小数位控制），后端为 `float(AVG(duration))` → 可能显示 `1234.5678901234` 这类长小数，与其他卡的千分位风格不统一 | apps/admin-web/src/views/stats/StatsOverview.vue:84；:134-143；backend/app/services/stats_service.py:53-55 | 中 | XS |
| D42 | 1 | 后端支持 `90d` 与 `avg_listen_duration` 趋势，前端只暴露 7d/30d 与 3 个指标；`api/stats.js` 注释仍写「区间（7d/30d/90d）」，接口能力与界面口径不一致 | apps/admin-web/src/views/stats/StatsOverview.vue:34-42；apps/admin-web/src/api/stats.js:13-15；backend/app/routers/admin/stats.py:32-33 | 低 | XS |
| D43 | 6 | `api/stats.js` 的 `getOverview/getTrend/getToday` 全站零引用（视图各自 `api.get` 裸调），且 `getToday()` 指向 `/stats/today` —— stats 路由并无该端点（同名端点在 workflows 路由）→ 一旦被复用即 404，注释「无需传日期，后端取当天」误导后续维护 | apps/admin-web/src/api/stats.js:9-18；backend/app/routers/admin/stats.py:19-101；backend/app/routers/admin/workflows.py:62 | 低 | XS |
| D44 | 2 | 无任何导出/复制入口（全组 7 个菜单都没有），日报场景需手抄数字；卡片也无「较昨日/较上周」对比，无法一眼判断涨跌 | apps/admin-web/src/views/stats/StatsOverview.vue:16-26；组内全站检索无导出实现 | 中 | M |

**优化建议**：
- D33：单位换算在前端集中做（`formatDuration(avg_duration)` 秒→「X 分 Y 秒」或分钟保留 1 位），列标签写「平均收听时长（分:秒）」；更稳妥是后端返回 `_seconds` 后缀字段并加单位约定注释。
- D34：趋势接口按指标返回换算后的值（或在 service 中 `avg*100`），前端对 `completion_rate` 的 Y 轴配 `ticks.callback` 加 `%`，保证卡片与图同源同单位。
- D35：把「无数据」与「0」区分开：后端缺失日返回 `null`（Chart.js 断线），或前端在 values 全 0 时改为显示「区间内无播放记录」空态；`hasTrend` 改为「至少有一个 >0 的点」。
- D36：在趋势卡标题明确「近 7 天（{起}~{止}，截至今日）」，返回体已含 `dates` 可直接取首末日期；若业务需要，把 `date` 作为区间右端传参并让切换日期同时刷新趋势。
- D37：`loadTrend` 加独立 `trendLoading` + try/catch/finally，用请求序号（或 AbortController）丢弃过期响应；加载中在画布区显示骨架/spinner 而不是保留旧曲线。
- D38：`v-loading` 分别下沉到指标卡区与趋势卡，避免整页遮罩闪烁。
- D39：卡片加 info 图标 tooltip「按每期 3 段推算（播放数×3），非真实曝光埋点」；名称改「推算广告曝光」。
- D40：加 `:disabled-date="d => d > Date.now()"` 与「今天/昨天」快捷选项（`el-date-picker` shortcuts）。
- D41：统一走 `formatNum` + 固定小数位（保留 1 位），并在数值旁显示单位后缀而非只写在标题里。
- D42：补齐「90 天」与「平均收听」趋势，或删掉后端不支持展示的部分；同步 `api/stats.js` 注释。
- D43：把视图改为复用 `api/stats.js`（并把 `getToday` 指向真实端点或删除），统一请求层，避免死代码。
- D44：趋势卡加「导出 CSV / 复制为表格」；指标卡加「较昨日 ±x%」小字。

### D-5 数据分析 > 频道健康度（路由 /stats/channel-health，文件 apps/admin-web/src/views/stats/ChannelHealth.vue）

**现状描述**：顶部近 7/14/30 天切换，4 张汇总卡（健康/警告/严重/频道总数），下方频道卡片网格，每卡含徽章 + 四宫格计数 + 80px mini 折线。后端恒返回长度等于 `range_days` 的补 0 序列。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互数值，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| D45 | 3 | 每张卡片的 mini 折线 Y 轴独立自适应且 `x/y` 全部 `display:false`，无刻度、无最大值标注、无日期轴 → 两卡片曲线形状相似却可能相差百倍量级，视觉斜率完全不可比，首次用户会据此判断「A 频道比 B 频道活跃」 | apps/admin-web/src/views/stats/ChannelHealth.vue:119-131；:70-80 | 高 | S |
| D46 | 6 | 跨页同名指标口径不同且无说明：卡片「RSS 源」计数来自频道配置 `channel.rss_sources` JSON 数组长度，而「RSS 源状态」页的「源总数」来自后端 `rss.yaml` 全局源清单 → 两页数字对不上，运营试图互相印证必然困惑 | apps/admin-web/src/views/stats/ChannelHealth.vue:60-61；backend/app/services/stats_service.py:208-215；apps/admin-web/src/views/stats/RssHealth.vue:160；backend/app/services/rss_source_service.py:28-51 | 高 | S |
| D47 | 4 | 徽章「健康/警告/严重」的判定阈值（区间 0 入库=critical、`today_pending<3` 或 `zero_days≥N-1`=warning）页面完全未说明，也无图例；用户把「健康」误读为「无需关注」（对照 LLM 页有说明卡，本页没有 → 组内不一致） | apps/admin-web/src/views/stats/ChannelHealth.vue:44-47；backend/app/services/stats_service.py:226-235；对照 apps/admin-web/src/views/stats/LlmMetrics.vue:14-26 | 中 | S |
| D48 | 1 | 汇总卡数字的时间作用范围未标注：4 张卡只写「健康/警告/严重/频道总数」，实际随「近 N 天」切换而变（critical 判定基于区间入库），用户易读成「全量/今日」；「频道总数」还包含 `is_active=0` 的未激活频道（卡片上有「未激活」tag 但总数未剔除） | apps/admin-web/src/views/stats/ChannelHealth.vue:14-22；:111-116；backend/app/services/stats_service.py:141-146；:240-241 | 中 | XS |
| D49 | 5 | 「无数据」空态不可达：`v-if="ch.daily_trend && ch.daily_trend.length > 0"` 对后端补 0 的定长序列恒为真，`el-empty`「无数据」分支成死代码；真实「从未入库」与「趋势未采集」都画成贴底 0 平线 | apps/admin-web/src/views/stats/ChannelHealth.vue:74-78；backend/app/services/stats_service.py:192-201 | 中 | S |
| D50 | 2 | 无状态筛选/排序，critical 与 healthy 混排（后端按 channel.id 顺序返回），频道数十个时运营需逐屏找红灯；也没有「只看严重」快捷 | apps/admin-web/src/views/stats/ChannelHealth.vue:28-36；:169-178；backend/app/services/stats_service.py:142-144 | 中 | S |
| D51 | 1 | 卡片不可下钻：发现 critical 后无任何处置入口（不跳「队列管理」「工作流监控」「RSS 源状态」「频道管理」），徽章也没写下一步动作 → 本页只能看不能办 | apps/admin-web/src/views/stats/ChannelHealth.vue:37-81 | 中 | M |
| D52 | 4 | 四宫格里混用两种时间口径：「今日待改写」（仅今天）与「区间入库」（近 N 天）相邻且都只写名字不写窗口；「关键词」无单位量词（个），四个数值均无量词 | apps/admin-web/src/views/stats/ChannelHealth.vue:51-66 | 低 | XS |
| D53 | 5 | 区间切换只靠 `v-loading` 遮整片网格，失败时无提示且保留旧数据；`rangeDays` 选择与滚动位置都不持久化，每天进来都要重设、重找重点频道 | apps/admin-web/src/views/stats/ChannelHealth.vue:5-10；:169-178 | 中 | S |
| D54 | 3 | 频道名 `max-width: 140px` 直接 ellipsis（lg 断点 6 列时更窄），仅靠 `title` 悬浮，长频道名/中英混排读不全，卡片之间难以区分 | apps/admin-web/src/views/stats/ChannelHealth.vue:251-259 | 低 | XS |
| D55 | 6 | 本页折线色板（`#FFB84D/#FF6B6B`）与同组 RSS 页（`#E09020/#E05050`）、LLM 页（同 RSS 值）不一致，同为「警告/严重」两种红黄；且 critical→`danger`、warning→`warning` 的 tag 映射与状态文案在素材页/日历页各写一份 | apps/admin-web/src/views/stats/ChannelHealth.vue:135-139；:225-228；apps/admin-web/src/views/stats/RssHealth.vue:304-307；:350-352 | 低 | S |

**优化建议**：
- D45：三选其一 —— 全网格共用固定 Y 轴上限（取全体频道最大值，或归一化为「占该频道区间日均值」）、卡片折线右上角标注「峰值 N 条/日」、或把曲线改为 7 格柱状 + 数字；至少把 x 轴日期显示出来（间隔取首/中/末 3 个 label）。
- D46：卡片标签改为「本频道已配源（个）」并 tooltip「来自频道配置的源清单，全局源可达性请看「RSS 源状态」」；或让后端把两端口径统一为同一份源清单。
- D47：页面顶部加与 LLM 页同款 `el-alert` 说明口径：「严重=近 N 天 0 入库；警告=当日待改写<3 或仅 1 天有入库；健康=近 N 天≥2 天入库且当日待改写≥3」。
- D48：卡片标签写「近 14 天 健康」「频道总数（含未激活 3）」，并把未激活频道数单独展示或默认排除。
- D49：后端返回 `has_data` 或前端判断 `range_total === 0` 时改显示「近 N 天无入库」文案而非 0 平线；删除不可达的空态分支。
- D50：顶部加 `el-radio-group`「全部 / 只看严重 / 只看警告」与按状态优先排序（critical→warning→healthy），并把 critical 卡片顶置。
- D51：卡片右下角加动作链接「去 RSS 源状态」「查看该频道队列」；徽章 tooltip 里给出处置建议（真实菜单名）。
- D52：统一标签格式「今日待改写（条）」「区间入库（条，近 14 天）」「RSS 源（个）」「关键词（个）」。
- D53：`rangeDays` 写入 localStorage/sessionStorage 或 URL query 复用；切换失败时保留提示 + 重试。
- D54：名称行改为两行截断或随断点放宽 `max-width`，并提供列表视图切换。
- D55：抽 `styles/status-tokens.scss`（healthy/warning/critical 三色 + tag 类型映射），四个统计页与广告页共用。

### D-6 数据分析 > RSS 源状态（路由 /stats/rss-health，文件 apps/admin-web/src/views/stats/RssHealth.vue）

**现状描述**：4 张汇总卡（源总数/正常/失败/未巡检）+ 状态 radio 带计数 + 关键词搜索 + 单张大表格（9 列，含延迟 ms、连续失败、修复建议、URL 外链），另有「立即巡检」按钮触发 `?refresh=true`（后端注释 5–15s）。筛选与搜索为纯前端过滤，分页缺失。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| D56 | 4 | 搜索关键词生效后，汇总卡与 4 个 radio 计数仍显示全量数字（「全部（52）」「失败（6）」），而表格可能只剩 2 行 → 数字与行数不一致，看起来像筛选失效；且 `el-empty` 文案固定为「暂无 RSS 源」，搜索无匹配时会误判「源配置丢了」 | apps/admin-web/src/views/stats/RssHealth.vue:34-47；:153-164；:191-201；:131 | 高 | S |
| D57 | 2 | 建议是死胡同：「修复建议」列写「建议暂时移除该源」「建议升级到 HTTPS」，但源清单来自后端 `rss.yaml` 配置文件，本页无编辑/移除入口，也不说明该去哪里改 → 运营看完建议无路可走 | apps/admin-web/src/views/stats/RssHealth.vue:124-130；backend/app/services/rss_source_service.py:181-193；:28-51 | 中 | S |
| D58 | 5 | 「立即巡检」5–15s 期间只有按钮转圈：表格与汇总卡仍显示旧数据、无「巡检中，请稍候…」提示、无进度、完成后也无「巡检完成：新增 2 个失败」回执；`timeout` 提到 60s 与实例默认 15s 不一致，超 15s 的巡检会先失败一次（需实测确认 axios per-request timeout 覆盖生效） | apps/admin-web/src/views/stats/RssHealth.vue:9-16；:227-247；apps/admin-web/src/api/index.js:17 | 中 | S |
| D59 | 3 | 「连续失败」列用 `<el-badge>` 空插槽渲染（数字浮在空白处，无承载文本），而失败数为 0 时改用行内文本「0」，同一列两套表达方式；badge 数值也无「次」量词 | apps/admin-web/src/views/stats/RssHealth.vue:86-95 | 中 | XS |
| D60 | 4 | 「最近巡检」只显绝对时间（YYYY-MM-DD HH:mm），无「3 分钟前」相对显示；后端每 2h 自动巡检，页面既不自动刷新也不提示数据陈旧，进程重启后状态字典清空导致 `lastCheckedAt=null`，「最近巡检」整段文案消失 → 无法区分「从未巡检」与「加载失败」 | apps/admin-web/src/views/stats/RssHealth.vue:6-8；:185-188；:214-219；backend/app/routers/admin/stats.py:69-72；backend/app/services/rss_source_service.py:347-375 | 中 | S |
| D61 | 6 | 后端 refresh 已返回权威的 `checked_at`，前端弃用，改为把所有源的 `last_check` 做**字符串排序取最大**自行推导，一旦时间格式不同（带/不带毫秒、含时区）就会取错时间 | apps/admin-web/src/views/stats/RssHealth.vue:214-219；:238-242；backend/app/services/rss_source_service.py:296-298；:343 | 低 | XS |
| D62 | 5 | 空态语义缺失：`rss.yaml` 缺失时后端返回 `total:0`，页面显示「暂无 RSS 源」，不提示「配置文件未找到」；`refresh=true` 返回体不含 `unknown` 字段，前端 `|| 0` 兜底，导致巡检后「未巡检（0）」与「全部」标签计数含义漂移 | apps/admin-web/src/views/stats/RssHealth.vue:131；:206-213；:230-236；backend/app/services/rss_source_service.py:275-277；:338-344 | 中 | S |
| D63 | 6 | 「延迟」列数值直传 `latency_ms` 并在列头写 ms，`0` 与「未巡检」源（后端固定回 `latency_ms:0`）都渲染成「-」；单位只在表头，行内是裸数字，与后端注释「单源超时 8s」这一口径无法对齐阅读 | apps/admin-web/src/views/stats/RssHealth.vue:77-84；backend/app/services/rss_source_service.py:367-371；:266-268 | 中 | XS |
| D64 | 6 | 表格 `:default-sort` 与列排序都按后端英文枚举 `status`（fail/ok/unknown）字典序排，展示却是中文「失败/正常/未巡检」，用户点「状态」列头后得到的顺序与标签不自洽；筛选栏注释声明「状态筛选 + 品类筛选 + 搜索」但**没有品类筛选控件**（注释与界面不符） | apps/admin-web/src/views/stats/RssHealth.vue:52-56；:69；:32-33；:34-39 | 中 | S |
| D65 | 1 | 告警无去向：后端连续失败≥3 只写 WARNING 日志，页面不提供「去通知管理配置告警」的入口或提示（真实菜单名为「通知管理」） | apps/admin-web/src/views/stats/RssHealth.vue:86-95；backend/app/routers/admin/stats.py:70-72；src/router/index.js:168-172 | 中 | S |
| D66 | 2 | 表格无分页、无行操作（无「单源重试」「查看该源最近条目」），源数 50+ 时只能滚动；URL 外链直接新窗口打开外部站点，无二次提示（可能引入钓鱼风险，需实测确认是否需要白名单提示） | apps/admin-web/src/views/stats/RssHealth.vue:52-132；:104-115 | 中 | M |
| D67 | 6 | `loadData` 与 `refresh` 两处 40 行完全重复的数据赋值 + 时间推导逻辑，且都无 catch（失败静默留旧数据）；与 LLM 页唯一带 catch 的写法不一致 | apps/admin-web/src/views/stats/RssHealth.vue:203-247；对照 apps/admin-web/src/views/stats/LlmMetrics.vue:197 | 低 | XS |

**优化建议**：
- D56：把汇总卡与 radio 计数改为「随关键词联动」的派生值（在 `applyFilter` 的匹配集上统计），或保留全量但标签写「全部（52）· 当前匹配 2」；空态区分两种文案：无源 vs「无匹配源（清空搜索）」。
- D57：建议列改为可执行动作：源名旁给「在频道管理中解绑」「复制 URL」等真实入口，文案引用真实菜单名（「频道管理」「帮助文档」），并说明「源清单由后端 rss.yaml 维护，改动需运维更新配置」。
- D58：巡检期间给页面级进度反馈（表格 `v-loading` + 「正在巡检 52 个源，预计 10s…」），完成后 `ElMessage.success(「巡检完成：正常 X / 失败 Y」)` 并在汇总卡做数值 diff 高亮；统一 timeout 配置并注释说明。
- D59：改为行内 tag「失败 3 次」（≥3 用 danger），去掉空插槽 el-badge，统一 0/非 0 表达。
- D60：用后端 `checked_at`（refresh 时）显示「最近巡检 3 分钟前（10-05 09:12）」，加 60s 轮询或「数据已过期，点击刷新」条；`lastCheckedAt` 为空时显式提示「尚未巡检，点击「立即巡检」」。
- D61：优先读 `data.checked_at`，仅在缺失时回退到本地推导。
- D62：`total===0` 时区分文案「后端未配置 RSS 源（rss.yaml 为空）」；refresh 返回体也补齐 `unknown` 字段。
- D63：延迟显示为「1.2 s」或「800 ms」并统一单位换算规则，未巡检显式写「—（未巡检）」，与真实 0 延迟区分；tooltip 说明「单源超时 8s」。
- D64：状态列排序提供 `sort-method` 按严重度（fail>unknown>ok）排，补齐品类筛选（`el-select` 取 `category_hint` 去重）或删除误导性注释。
- D65：页顶 `el-alert` 说明「连续失败 3 次会写告警日志；如需钉钉/邮件通知请到「通知管理」配置」。
- D66：加前端分页（或后端分页）、行操作「单独重测」；外链改为二次确认或仅展示可复制文本。
- D67：抽 `applyPayload(data)` 复用赋值，统一加 catch 与失败提示条。

### D-7 数据分析 > LLM 重试指标（路由 /stats/llm-metrics，文件 apps/admin-web/src/views/stats/LlmMetrics.vue）

**现状描述**：一个纯图标刷新按钮 + 说明卡（阈值解释）+ 3 张派生率卡（触发率/改善率/未改善率，含 `x / y 次` 副标题）+ 4 张计数卡 + 手写宽度百分比的三段「重试漏斗」。数据来自 `/stats/llm-metrics`。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| D68 | 4 | 数据时间范围全程未标注：后端返回的是**自进程启动以来累计**计数（重启即归零），页面没有任何「累计/自 xx 启动/重启清零」字样，卡片与漏斗看起来像「当前状态」→ 运营发布重启后看到 0% 会误判「问题已修复」 | apps/admin-web/src/views/stats/LlmMetrics.vue:37-59；:61-79；backend/app/routers/admin/stats.py:85-98；backend/app/workflow/llm/rewriter.py:448-462 | 高 | XS |
| D69 | 5 | 率值渲染无容错：`metrics.trigger_rate.toFixed(2)` 直接对后端字段调 `.toFixed`，而赋值是 `{...defaults, ...data}` 整体浅合并 —— 若后端把该字段返回为 `null` 或字符串，合并后即为 null/字符串，渲染阶段抛 TypeError 使整页白屏（正是注释想防的「缺字段」场景，只防了 key 缺失、没防值为 null） | apps/admin-web/src/views/stats/LlmMetrics.vue:104-126；:189-202 | 高 | XS |
| D70 | 4 | 说明卡与空态互斥：`v-if="!loading && metrics.total_calls > 0"` 让「触发率/改善率含义 + 阈值」说明恰好在首次使用（total_calls=0）时不显示，新用户先看到一句「暂无 LLM 调用数据」却不知本页要读什么；同时空态判定用 `=== 0` 严格相等，字段类型变化时空态不出现而卡片显示 NaN% | apps/admin-web/src/views/stats/LlmMetrics.vue:15-33 | 中 | XS |
| D71 | 3 | 漏斗第三段宽度公式与「改善率」口径不同：`width = improved/triggered × triggered/total × 100`（即 improved/total），却与「触发重试」段用 `improved/triggered` 计算的副标题混排，用户按卡片百分比理解条宽会对不上；`triggered===0` 时该段 `width:0` 整条消失，看起来像渲染错误 | apps/admin-web/src/views/stats/LlmMetrics.vue:138-166 | 中 | S |
| D72 | 1 | 漏斗只有 total→triggered→improved 三段，页面上并列展示的「未改善率/未改善次数」在图中没有分支位置，`improved + not_improved 是否等于 triggered` 无处核对（后端确实满足该关系，但 UI 不给验证路径） | apps/admin-web/src/views/stats/LlmMetrics.vue:61-79；:129-134；backend/app/workflow/llm/rewriter.py:448-462 | 低 | S |
| D73 | 6 | `funnelStages` 中 `value: triggered > 0 ? total : total` 是恒等三元（两分支相同），说明该处逻辑曾按空态分叉后又没写完，属遗留噪声，易误导后续维护 | apps/admin-web/src/views/stats/LlmMetrics.vue:146 | 低 | XS |
| D74 | 5 | 失败静默留旧值：唯一的 `catch (e)` 分支注释「保留 metrics 现值不清空，避免页面闪烁」，页面无任何「数据可能已过期/上次成功时间」标识，刷新按钮 loading 结束后数字与之前一模一样，用户以为已刷新 | apps/admin-web/src/views/stats/LlmMetrics.vue:189-202 | 中 | S |
| D75 | 6 | 刷新按钮形态与同组 RSS 页不一致（本页 plain 图标「刷新」+ `:loading="loading"`，RSS 页 primary「立即巡检」+ 独立 `refreshing`），同为「拉数据」语义两套视觉与命名；两页也都无「上次更新时间」 | apps/admin-web/src/views/stats/LlmMetrics.vue:5-11；apps/admin-web/src/views/stats/RssHealth.vue:9-16 | 低 | XS |
| D76 | 2 | 阈值只染色不给去处：触发率 >50% 变红、改善率 <30% 变红，但没有「该做什么」的行动指引（改 prompt 要去「AI 服务」、看失败工作流要去「工作流监控」，二者均 requireRole=admin，普通运营看不到入口也不会被引导），红字成为无人响应的告警 | apps/admin-web/src/views/stats/LlmMetrics.vue:168-187；src/router/index.js:144-148；:126-130 | 中 | S |
| D77 | 3 | 卡片量词/命名与全站不完全一致：「总调用次数/触发重试次数/改善次数/未改善次数」用「次数」，而 RSS 页「连续失败」用裸数字、数据统计用「播放量」，同类计数三种表述；率值保留 2 位小数（85.71%）与统计页完播率 1 位小数（85.7）精度不一 | apps/admin-web/src/views/stats/LlmMetrics.vue:129-134；:104-126；apps/admin-web/src/views/stats/StatsOverview.vue:140-143；apps/admin-web/src/views/stats/RssHealth.vue:86-95 | 低 | XS |

**优化建议**：
- D68：页顶加口径条「统计范围：自服务启动累计（{started_at} 起），重启后归零」，并在计数卡副标题显示累计起点；如需按日趋势，后端补 `/stats/llm-metrics/daily` 并加区间选择（与本页其它统计页保持一致的「今日/近 N 天/全部」显式标注）。
- D69：改 `const rate = Number(x ?? 0)` 统一 `formatRate()` 包装（NaN 显示「-」），渲染层不直接 `.toFixed`；赋值时逐字段 `Number.isFinite` 校验并回退默认值。
- D70：说明卡改为常驻（或首次空态时显示引导版「工作流执行后本页将累计以下指标：…」），空态判定放宽为 `!(total_calls > 0)`。
- D71：漏斗统一按「占总数百分比」定宽并在每段右侧同时显示「数值 + 占比」，`triggered===0` 时保留最小宽度并显式标注「0」；或改用 Element Plus 的 steps/进度条组件，避免手写宽度公式。
- D72：漏斗第四段补「未改善」（`not_improved`），并在 tooltip 写明 `improved + not_improved = triggered` 的对账关系。
- D73：删除恒等三元，直接 `value: total`。
- D74：catch 中把 `lastLoadedAt` 与错误信息记录并显示「数据更新于 09:12，最近一次刷新失败：{msg}」+ 重试按钮；成功后 `ElMessage.success('已刷新')`。
- D75：统一「刷新（重取数据）」与「立即巡检（触发后端探测）」的图标、类型与命名规范，两页都加「上次更新 HH:mm:ss」。
- D76：率值超阈值时在卡下出现提示条「触发率偏高，建议优化改写 prompt（管理员可到「AI 服务」调整）；执行记录见「工作流监控」」——菜单名严格取自 `meta.title`，并对非 admin 用户改说「请联系管理员」。
- D77：统一量词（次/条/个）与百分比精度（建议 1 位小数），沉淀到 `utils/format.js`。

### D-8 组内共性问题（跨 7 个菜单，不重复计入上表）

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| D78 | 5 | 反馈可达性系统风险：`utils/message.js` 与 api 拦截器在 `document.hidden` 时**静默丢弃**所有 ElMessage，包括删除成功/失败与请求错误；最小化窗口后台轮询的运营回来看不到任何提示，误认为操作成功 | apps/admin-web/src/utils/message.js:28-33；:56-72；apps/admin-web/src/api/index.js:47-52 | 高 | S |
| D79 | 6 | 组内 7 个视图全部绕过 `api/ads.js`/`api/stats.js` 直接 `api.get('/...')` 裸调（只有移动端 ManageAds 用了 ads.js），路径字符串硬编码、错误处理各写各的（1 页有 catch、6 页没有），无统一「加载失败 + 重试」组件 | apps/admin-web/src/api/stats.js:9-18；apps/admin-web/src/api/ads.js:9-14；apps/admin-web/src/views/ad/AdPlacements.vue:160-176；apps/admin-web/src/views/stats/StatsOverview.vue:147-158 | 中 | M |
| D80 | 2 | 筛选与区间状态一律不持久化（`metric`/`range`/`rangeDays`/`statusFilter`/`keyword`/`selectedMonth`/日期都只活在组件内），高频运营每天需重设；也不写入 URL query，无法把「近 30 天的频道健康度」直接分享给同事 | apps/admin-web/src/views/stats/StatsOverview.vue:76；:89-90；ChannelHealth.vue:105；RssHealth.vue:149-150；AdSchedule.vue:64 | 中 | S |
| D81 | 5 | 无自动刷新与陈旧标识：4 个盯盘页（数据统计/频道健康度/RSS 源状态/LLM 重试指标）都只在挂载时取一次，无轮询、无「数据已 N 分钟未更新」提示，页面长时间打开即呈现过期数字（后端 rss 巡检本身是 2h 一次的定时任务） | apps/admin-web/src/views/stats/StatsOverview.vue:160-163；ChannelHealth.vue:180；RssHealth.vue:249；LlmMetrics.vue:204；backend/app/routers/admin/stats.py:69-72 | 中 | S |
| D82 | 1 | 分组信息架构与命名：路由头注释仍写「数据分析 - 数据统计」而实际该组已有 4 个菜单；「频道健康度」「RSS 源状态」都属「健康度/状态」概念却分列两页（且 D46 的源计数口径冲突），菜单名未说明各自负责「内容入库健康」还是「外部源可达性」 | src/router/index.js:8-15；:69-86 | 低 | S |
| D83 | 4 | 广告组三个页面的空态/引导文案都不引用真实界面名（素材页与规则页均写「右上角」「新增规则」，日历页零引导），且组内无任何指向「队列管理」「工作流监控」「通知管理」等真实菜单的处置提示（对照 D26/D51/D65/D76） | apps/admin-web/src/views/ad/AdMaterials.vue:52；AdPlacements.vue:38；AdSchedule.vue:1-55 | 中 | XS |

---

**条数统计**（逐条按表格「优先级」列清点，共 83 条：D1–D83）：

- **高 18 条**：D13、D14、D15、D16（投放规则：停用不可见/不生效、单日投放被英文字段名报错拒绝、素材下拉截断 100 条）、D23、D24、D25（排期日历：停用仍显示、重叠静默覆盖、加载失败一片「—」）、D33、D34、D35、D36、D39（数据统计：秒当分钟、完播率卡图不同单位、补 0 折线、日期与趋势不联动、曝光为推算值）、D45、D46（频道健康度：mini 折线各自缩放致误读、两页 RSS 源计数口径冲突）、D56（RSS 源状态：筛选后计数与行数不一致）、D68、D69（LLM 指标：累计口径未标注、`.toFixed` 空值白屏）、D78（隐藏窗口吞掉全部反馈）。
- **中 49 条**：D1–D10、D12、D17–D22、D26、D28、D29、D31、D37、D38、D40、D41、D44、D47–D51、D53、D57–D60、D62–D66、D70、D71、D74、D76、D79–D81、D83。
- **低 16 条**：D11、D27、D30、D32、D42、D43、D52、D54、D55、D61、D67、D72、D73、D75、D77、D82。

**修复优先建议顺序**：先做零成本纯文案/口径标注类高优项（D33、D36、D39、D46、D48、D68、D23 标注），再做 D69/D35/D45 三处「渲染即错」项，D13/D14/D15/D16 需要前端补状态列与校验（S–M），D24/D51/D66/D44/D79/D80/D81 属结构性改造（M）。

---

# slice_E：AI 自动化分组 · 工作流监控与详情（T02323 UX 评审，只读走查）

走查范围：`/workflows` 列表页、`/workflows/:id` 详情页、页内弹窗/步骤条/重试停止/空态/轮询/SSE，对照 `docs/工作流队列管理系统需求规格说明书.md` 与 `backend/app/` 步骤枚举。未修改任何源码。

## 5. AI 自动化 > 工作流监控与详情

### E-1 AI 自动化 > 工作流监控（路由 /workflows，文件 apps/admin-web/src/views/workflow/WorkflowList.vue）

**现状描述**：列表提供频道/日期/状态/来源四筛选 + 分页，行内用 WorkflowProgressIndicator 紧凑状态灯展示 6 步进度，SSE 事件 + 「有 running/queued 时 5s silent 轮询」双通道刷新，timer 在 onUnmounted 清理、document.hidden 时跳过轮询，工程兜底较扎实。手动触发/全频道启动/批量删除均有二次确认，确认文案说明了删除范围（删什么、留什么）。主要短板集中在「实时链路失效不可感知」「失败原因在列表层不可见」「跳过爬虫开关作用域误导」三点。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| E1 | 5 | 实时链路断流完全不可见：轮询与 SSE 均为 silent 失败（拦截器对 silent 请求不提示、loadList 无 catch 只留 unhandled rejection），若接口连续失败（网络抖动/会话异常/后端重启），页面静止显示旧的 running 状态且无任何「数据可能过期」提示；页面上也没有独立的「刷新」按钮（「重置」会连带清空筛选条件，不能当刷新用），无手动重连入口 | apps/admin-web/src/views/workflow/WorkflowList.vue:340-373、560-573；apps/admin-web/src/api/index.js:62-69；apps/admin-web/src/utils/sse.js:150-154 | 高 | M |
| E2 | 4 | 空态与错误态共用文案：非 silent 加载失败时（接口 5xx/网络错误，拦截器 toast 后）list 仍渲染 el-empty「暂无工作流」，值班者会把「查询失败」误读为「今天没有任务」 | apps/admin-web/src/views/workflow/WorkflowList.vue:166、340-373 | 中 | S |
| E3 | 6 | 运行中/排队中的工作流在本页没有任何「停止/取消」入口：状态筛选里有「已取消」选项、后端也有 cancelled 态，但取消只在「队列管理」页对 queued 生效（running 后端根本无取消接口），值班者发现触发错频道后只能等它跑完或事后删除，且不知道 queued 可去队列管理页取消 | apps/admin-web/src/views/workflow/WorkflowList.vue:38-43；backend/app/services/queue_service.py:146-160；docs/工作流队列管理系统需求规格说明书.md:361、396 | 中 | S |
| E4 | 2 | 批量删除未做前端预检：可勾选 running/queued 行提交，后端「任一 ID 不存在或状态非法时整批回滚」，一条选错整批失败且只弹后端原始报错串；后端限单批 1-100 个 ID，前端对超 100 条勾选无任何提示，直接收 422 | apps/admin-web/src/views/workflow/WorkflowList.vue:115-123、490-520；backend/app/routers/admin/workflows.py:40-58、94-116 | 中 | S |
| E5 | 1 | 「跳过爬虫」开关作用域误导：它位于「全频道启动」与「手动触发」两按钮之间，但只有 handleTrigger 读取 skipCrawl，handleTriggerAll 与 retryFailedChannels 都不带 skip_crawl——开启开关后点「全频道启动」，对课程/资料类频道全部从 crawl 重跑，无生效提示也无失效提示 | apps/admin-web/src/views/workflow/WorkflowList.vue:67-87、375-436、438-483；apps/admin-web/src/api/workflow.js:17-23 | 中 | S |
| E6 | 5 | 状态跃迁无汇总提示：SSE/轮询刷新仅整体替换数据，行从 running→failed 无高亮、无 toast、无「本次刷新新增 N 个失败」汇总；failed 行的工作流级 error 字段后端列表接口就没下发（payload 只有 steps_summary），列表上点不进失败原因除非逐个点小红灯 | apps/admin-web/src/views/workflow/WorkflowList.vue:528-546；backend/app/services/workflow_service.py:108-125 | 中 | M |
| E7 | 3 | 列表进度列在 compact 模式下阶段名称 display:none，只剩 6 个等大彩点 + 百分比，首次使用无法不悬停就分辨灯序（且后端步骤含 quality_check，实际 6 步，代码注释仍写「5 阶段」强化了误解）；可点击查错误的 failed 灯仅有 hover 时 cursor:pointer 提示，无下划线/图标等静态可供性 | apps/admin-web/src/views/workflow/components/WorkflowProgressIndicator.vue:186-203、230-245；apps/admin-web/src/views/workflow/WorkflowList.vue:150-159 | 中 | S |
| E8 | 2 | 触发成功后的结果不可跳转：单频道触发成功 toast「已触发，工作流 ID: xxx」为纯文本；「全频道触发结果」对话框的 triggered 表 workflow_id 列也是纯文本，均需回列表搜索/肉眼匹配；且对话框默认停在「成功」Tab，存在失败频道时要点一次 Tab 才能重试 | apps/admin-web/src/views/workflow/WorkflowList.vue:211-241、394 | 低 | S |
| E9 | 2 | 筛选与分页不同步 URL：从详情 router.back() 返回列表后筛选/页码全部丢失（loadList 初始态）；无法分享「只看昨日失败」之类的带条件链接。另第 126 行注释称「点击跳详情使用 replace」，实际 goDetail 用 push，注释误导后续维护 | apps/admin-web/src/views/workflow/WorkflowList.vue:126-127、522-524 | 低 | S |
| E10 | 4 | 频道悬空（channel_id 被 SET NULL）时列表/筛选文案为「默认」，与真实「默认频道」语义冲突：这类工作流无法用频道筛选器命中（筛选器无「默认/无频道」选项），历史数据被筛选「隐身」 | apps/admin-web/src/views/workflow/WorkflowList.vue:130-136、344-346；backend/app/models/workflow.py:62-64 | 低 | S |

**优化建议**：
- E1：加独立「刷新」IconButton（不重置筛选）；轮询连续 N 次（如 3 次）失败时在表格上方挂一条 el-alert「实时数据更新中断，最后成功时间 HH:mm:ss，点击重试」；SSE 模块已暴露重连逻辑，页面可订阅 onerror/心跳超时事件把「实时/降级轮询/已断」三态显示在筛选栏右侧小徽标。
- E2：loadList 记录 lastError，表格空态改为区分「加载失败：xxx [重试]」与真空态；错误态下保留旧数据并加「数据未更新」水印。
- E3：queued 行操作列加「取消排队」按钮（复用 queue 的 cancel 接口）并在确认框说明「仅排队中可取消，运行中不可中断」；若产品决定支持 running 停止，再补后端接口，否则在文档明确「running 不可停止」。
- E4：提交前过滤 running/queued 行并在确认框显示「N 条运行中将被跳过」或禁用其勾选（el-table selectable）；勾选超 100 时禁用批量删除按钮并提示上限。
- E5：把开关移入「手动触发」确认框内（或紧贴手动触发按钮并加「仅对手动触发生效」小字），全频道启动确认文案明确「始终执行爬虫」。
- E6：SSE 收到 workflow.failed/step.failed 且事件 id 不在已提示集合时，ElMessage.warning 一条「频道 X 工作流 Y 在 Z 阶段失败」+该行 3s 高亮；后端列表 payload 增加 workflow.error 截断字段，failed 行状态 tag 旁加「!」tooltip。
- E7：compact 下在首尾灯旁保留缩写（爬/改/审/音/拼/核）或 hover 外常显当前运行阶段的名称；failed 灯加红色描边/小叉图标做静态可点暗示。
- E8：触发成功 toast 用 ElMessageBox/h 渲染带 router-link 的 workflow_id；全频道结果对话框有 failed 时默认激活失败 Tab（el-tabs 加 v-model），triggered 表 workflow_id 列改 el-link 跳详情。
- E9：筛选/分页写入路由 query（watch → router.replace），mounted 时从 query 恢复；修正第 126 行注释。
- E10：频道筛选器加「（无频道/默认）」特殊选项映射空值，或悬空时 tag 文案改为「频道已删除」。

### E-2 AI 自动化 > 工作流详情（路由 /workflows/:id，文件 apps/admin-web/src/views/workflow/WorkflowDetail.vue）

**现状描述**：详情页 = 元数据 descriptions + 6 步 el-steps 步骤条 + 步骤表（含耗时/重试次数/错误信息列）+ 5 个懒加载产物折叠面板（素材/稿件/TTS/成品/审核，含 CRUD 与内联播放）+ 底部「选步骤重跑」。SSE 按 workflow_id 过滤刷新 + 非终态 5s silent 轮询，卸载时清 timer、revoke blob，危险操作（删除素材/稿件/音频、打回）均有确认。核心缺陷：素材「查看」按钮必然报错、深链进入后回不到列表、重跑入口未按状态收口。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| E11 | 2 | 素材行「查看」按钮点击必失败：viewMaterial 内用 `h(...)` 构建 VNode，但 script setup 只 import 了 ref/computed/onMounted/onUnmounted，vite AutoImport 未配 `imports:['vue']`（同仓 Maintenance.vue 是显式 import h 的），运行时 ReferenceError 被 Promise 吞掉——无弹窗、无提示，用户以为按钮坏了 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:428、669-683；apps/admin-web/vite.config.js:18-20；对照 apps/admin-web/src/views/maintenance/Maintenance.vue:221 | 高 | XS |
| E12 | 2 | 「返回」按钮用 router.back()：直接输入/新标签打开/刷新 /workflows/xxx 深链时无历史栈，点返回无任何反应；页面标题被去掉、无面包屑，「工作流详情」菜单项又 hidden，唯一退路是手改地址栏——深链值班路径走不通 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:3-8；apps/admin-web/src/router/index.js:131-136 | 高 | S |
| E13 | 5 | 底部「从指定步骤重跑」对任意状态的工作流都显示且可点：后端 retry 仅允许 status=failed（其余 400「任务不存在或非失败状态」），对 success/running 页面上的重跑按钮是虚假可供性；步骤下拉列全部 6 步，不依据各步骤完成情况禁用「前驱未成功」的选项，全靠提交后报错 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:326-342、893-910；backend/app/services/workflow_scheduler.py:893-919；backend/app/routers/admin/workflows.py:276-311 | 中 | S |
| E14 | 5 | 输入不存在/已删除的 workflow_id：loadDetail 失败仅有一次拦截器 toast，页面渲染全空 descriptions（undefined 值）、步骤条 6 个 wait 灰点、产物面板各自「暂无」——看起来像「刚创建的工作流」而非「对象不存在」，且不会跳走 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:531-540、10-48；backend/app/services/workflow_service.py:127-136 | 中 | S |
| E15 | 4 | loadScript / loadReview 的 catch 把所有异常（网络失败、403、500）一概置 null 渲染「该工作流暂无稿件」「该工作流暂无审核记录」，把「加载失败」说成「没有数据」，与 E14 同类误导；面板内也无重试按钮（review/stitch/rewrite 三个面板没有刷新入口，仅 crawl/tts 有） | apps/admin-web/src/views/workflow/WorkflowDetail.vue:688-698、863-873、139-142、275-277、299-316 | 中 | S |
| E16 | 5 | 产物面板 loadedPanels 一次性缓存不失效：重跑完成、SSE 刷新或审核通过后面板数据不自动重载（轮询只刷 detail，不刷已展开面板），rewrite/stitch/review 面板又无手动刷新按钮，值班验证重跑产物只能 F5 整页 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:543-565、893-910、914-928 | 中 | S |
| E17 | 1 | crawl 面板标题「爬虫采集 · 素材」+ 空态「本工作流尚未关联素材」，实际按 channel_id 拉的是频道级素材池（代码注释自述 workflow_id 终态即释放）：展示范围与文案不符；channel_id 为空（频道被删）时传 undefined，axios 省略参数 → 面板列出全系统素材；素材表也无「本流已选中」标记 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:82-108、571-586 | 中 | S |
| E18 | 1 | 规格要求详情页「步骤时间线 + 每步日志 + 耗时统计」（队列系统说明书把它列为详情页增强验收项），现页面没有任何日志入口/执行日志区，失败定位要在步骤表 error 列 tooltip 与「系统日志」菜单间来回切 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:37-73；docs/工作流队列管理系统需求规格说明书.md:115、129、221-222、585 | 中 | M |
| E19 | 2 | 审核面板「通过」按钮零确认直接生效（打回反而要求填理由）；「创建审核 · 审核记录」面板与「审核管理」菜单功能重叠，但通过/打回在本页即可完成，无「此处操作与审核台是否同规则/能否反悔」说明，重审流程是否可逆需实测确认 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:299-316、875-890 | 中 | S |
| E20 | 6 | 步骤命名三方不一致：后端 step_name CHECK 约束含 7 个值（有 publish），调度器实际只跑 6 步（quality_check 插 rewrite 后、无 publish），前端 STEP_ORDER/orderedSteps 固定 6 步——若历史数据存在 publish 步骤记录，会被 orderedSteps 的 map-过滤静默丢弃（步骤条与步骤表都不显示）；规格文档口径仍是「5 步」且时间线写 crawl/…/publish；列表页注释也残留「5 阶段状态灯」 | backend/app/models/workflow.py:26-34、84；backend/app/services/workflow_scheduler.py:1269-1277；apps/admin-web/src/views/workflow/WorkflowDetail.vue:456-495；docs/工作流队列管理系统需求规格说明书.md:29、70、222；apps/admin-web/src/views/workflow/WorkflowList.vue:150 | 中 | S |
| E21 | 4 | 重跑确认文案「保留已完成的步骤产出」不完整：后端会删除 from_step 及其后的全部步骤记录（含历史 error/retry_count），文案未提示「该步骤此前的执行记录将被清除」；也无「本步骤已自动重试 N 次/重跑不限次」提示（步骤表 retry_count 列有数据但无解读入口） | apps/admin-web/src/views/workflow/WorkflowDetail.vue:893-899；backend/app/routers/admin/workflows.py:283-287；apps/admin-web/src/views/workflow/WorkflowDetail.vue:70 | 低 | S |
| E22 | 3 | 视觉维度多为模板推断，需实测确认：el-steps 六项 align-center 中文 4 字标题在 <1200px 视口可能换行/挤压；detail.error 原始异常长串直接做 el-alert title 无截断/滚动；稿件分段预览固定 `slice(0,80)+'...'` 短内容也带省略号；产物面板 20 条分页 el-pagination `v-if="total>20"` 恰 20 条时静默截断 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:27-48、143-152、110-119 | 低 | S |
| E23 | 5 | 成品音频「点击加载播放」加载完成后 `<audio autoplay>` 直接出声，值班环境可能惊吓；加载期间仅按钮 loading，无「正在下载 xxx MB」进度提示；rewrite 面板无稿件空态与 review 面板空态同款（见 E15） | apps/admin-web/src/views/workflow/WorkflowDetail.vue:257-274、796-811 | 低 | XS |

**优化建议**：
- E11：`import { h } from 'vue'` 一行修复（XS）；同时在 vite AutoImport 加 `imports:['vue']` 或 lint 规则防再犯；建议顺手给 viewMaterial 的 getMaterial 加 catch 提示。
- E12：返回按钮改为 `history.state.back ? router.back() : router.push('/workflows')`；页头恢复轻量面包屑「AI 自动化 / 工作流监控 / 详情(短 ID)」，深链用户可点面包屑回列表。
- E13：`v-if="detail.status==='failed'"` 才显示重跑卡（或对 queued/running 显示禁用 + tooltip「仅失败的工作流可重跑」）；下拉中前驱未成功的步骤置 disabled 并附原因「crawl 未成功」。
- E14：loadDetail 捕获 404 时渲染专属 el-result「工作流不存在或已被清理 [返回列表]」，终止后续卡片渲染。
- E15：loadScript/loadReview 区分 404 与其他错误：后者显示「加载失败，点击重试」+ 面板内统一刷新按钮（五个面板都加）。
- E16：detail 状态跃迁（workflow.completed/failed/step.*）时清空 loadedPanels 并对当前展开面板重新 loadPanelData；retry 成功后同样失效。
- E17：面板标题改「频道素材池（供本频道工作流选用）」，channel_id 为空时改为空态「频道已删除，素材池不可用」而非全量列表；表格加「本流选中」过滤/徽标。
- E18：步骤表加「日志」列按钮，弹抽屉按 workflow_id 过滤展示系统日志尾部 N 行 + 每步耗时柱状小图；这是规格既定项，优先补。
- E19：「通过」加 ElMessageBox.confirm（说明通过后的下游动作）；文案与审核台对齐（打回必填理由 vs 通过零确认的规则差异如果是刻意的，至少在 tooltip 说明「通过无需理由」）。
- E20：orderedSteps 改为「STEP_ORDER ∪ 实际 steps 中未知步骤」并排尾部标注「历史步骤」；统一文档与代码注释的步数口径（现行为 6 步含质量审核、不含 publish），确认库中是否存在 publish 记录后决定是否需要展示兼容。
- E21：确认文案补「将清除「X 步骤及之后」的执行记录（重试历史/错误），产物保留」；步骤表 retry_count 列表头加 tooltip「自动重试上限见调度配置」。
- E22：窄屏实测 el-steps，必要时降级为 WorkflowProgressIndicator；el-alert 长错误加 max-height + overflow；`slice(0,80)` 仅超长时加省略号；pagination 条件改 `total>materialsPage*20`。
- E23：去掉 autoplay，加载完成后 focus 播放器由用户按播放；加载中显示字节进度或骨架。

**替代优化（未发现显著缺陷的方面）**：轮询/SSE/visibilitychange/blob 生命周期管理在两页中均正确闭环（onUnmounted clearInterval + 移除监听 + revokeObjectURL，页面隐藏时停轮询、恢复即补拉，cleanupLoadingMasks 防遮罩残留），状态映射表键与后端小写枚举一致无「恒灰」问题，重试/删除/打回类破坏性操作都有后果说明——这部分实现质量高，无需改动，仅需保持。

### E-3 两页共用弹窗与组件（el-dialog 触发结果框 / WorkflowProgressIndicator / 素材与分段编辑弹窗）

**现状描述**：全频道触发结果对话框（统计四色块 + 成功/跳过/失败三 Tab + 失败重试按钮）、进度状态灯组件、素材编辑弹窗与分段编辑弹窗均内嵌于上述两页。逐条问题已并入对应页面表格（E7、E8 归 E-1；E11/E17/E21 涉及弹窗组件）。

**问题清单**：除已归入 E-1/E-2 的条目外，本层补充一项：

| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| E24 | 6 | 「重试失败频道」按钮在结果对话框内直接执行、无二次确认，且重试调用 `triggerWorkflow(ch.channel_id)` 不携带本次全频道启动时任何参数（skip_crawl 也不适用），重试产生的新工作流与原批次在列表中无关联标识；对话框打开期间 retryFailedChannels 会再次 loadList 重置分页到第 1 页，副作用波及用户正在看的筛选结果（page.value=1 强改筛选态） | apps/admin-web/src/views/workflow/WorkflowList.vue:229-240、438-483 | 低 | S |

**优化建议**：
- E24：重试前 confirm「将重新触发 N 个失败频道」；重试成功后 workflow_id 以 el-link 呈现；避免在对话框流程里静默重置用户 page/filter（改为增量合并或提示「列表已刷新」）。

---

统计：24 条（高 3 / 中 14 / 低 7）。高优先三项：E1 断流不可见+无手动刷新入口、E11 素材「查看」按钮运行时崩溃（h 未导入）、E12 深链进入详情后无法返回列表。

---

# Slice F — AI 自动化分组 UX 评审（T02323）

评审范围：`/ai-config`（AI 服务）、`/ai-qa`（智能助手）。后端契约对照 `backend/app/routers/admin/ai_config.py`、`backend/app/routers/admin/assistant.py`、`backend/app/services/ai_config_service.py`。
**总注**：本切片两页均无 SSE 流式通道（问答为阻塞式 POST 一次性返回），任务书所设「流式输出/停止生成」界面在本实现中不存在，相关缺陷按此现实记录。

## 6. AI 自动化 > AI 服务 / 智能助手

### F-1 AI 自动化 > AI 服务（路由 /ai-config，文件 apps/admin-web/src/views/ai/AIConfig.vue）

**现状描述**：单页 5 个 tab（LLM 大模型 / TTS 语音合成 / 图片模型 / 用量统计），顶部唯一「保存配置」图标按钮做全量「编辑→保存」（非即改即存）；密钥类字段后端返回 `****xxxx` 脱敏值回显，测试连接透传未保存表单值且不落库（`test_llm_connection` 等仅读回退、无写路径，已核实**不会顺手改线上配置**）。保存 toast「配置已保存并热更新」与后端实现一致（`update_config` 即时覆盖 Settings 单例并清 TTS 工厂缓存，无重启文案，正确）。三套 useDraft 把未保存输入静默写 localStorage。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| F1 | 2/5 | 无脏检查：保存按钮恒可点、无「有未保存改动」指示，也无离开/关页拦截；改完 slider 直接切菜单即丢（仅靠隐形草稿兜底） | apps/admin-web/src/views/ai/AIConfig.vue:4,1266-1288；无 onBeforeRouteLeave/beforeunload | 中 | S |
| F2 | 5 | 断点草稿**静默恢复**：`applyDraft/apply` 把上次未保存的本地草稿深合并进刚加载的服务端配置，无任何「已恢复草稿/丢弃」横幅；`hasDraft` 在 useDraft 中已导出但页面未使用。换机器/他人改过线上配置后，本浏览器陈旧草稿值会顶掉真实值并在下次保存时被静默写入 | apps/admin-web/src/views/ai/AIConfig.vue:1578-1584；apps/admin-web/src/composables/useDraft.js:62-81,116 | 高 | S |
| F3 | 4/5 | **清空密钥保存是静默 no-op**：`_normalize_llm/_normalize_tts/_normalize_image` 均 `if api_key and not _is_masked(...)` 才写入，空串被跳过——但同文件 docstring 声称「空字符串视为清除 Key」（契约与实现矛盾）。用户在 API Key 框清空→保存→提示成功→重进页面旧 Key 脱敏值仍在，且界面无任何「清除密钥」入口 | apps/admin-web/src/backend 对照：backend/app/services/ai_config_service.py:594,667-669,720-727,697-699 | 高 | M |
| F4 | 4 | 脱敏回显无说明文案：LLM API Key、阿里云 AccessToken/AppKey、腾讯 SecretId/Key 输入框回显 `****abcd`，但字段旁没有「已保存密钥以脱敏显示，保持 `****` 开头即不修改」的提示；仅图片模型 tab 的 placeholder 写了「留空沿用已保存值」，同一页内规则不一致，首次配置者易把 `****abcd` 当真实 key 去续写 | apps/admin-web/src/views/ai/AIConfig.vue:83-98,296-333,445-476,755-761 | 中 | XS |
| F5 | 5 | 测试结果 tag 不随参数变更失效：切换预设（`applyPreset` 改 base_url/model）、修改模型名后，上一个「连接成功」绿 tag 仍挂在按钮旁，误导当前配置已验证；保存成功后旧 tag 也不清 | apps/admin-web/src/views/ai/AIConfig.vue:146-152,1247-1263,1266-1280 | 中 | XS |
| F6 | 5/6 | `handleTestLLM` 无 catch：请求被拒绝（500/网络错）时 `testingLlm` 永远停留 loading，按钮卡死且无失败 tag（对照 `handleTestTTS` 有 catch 兜底，同类功能两套行为）；`finally` 里重置的是无关的 `loading` | apps/admin-web/src/views/ai/AIConfig.vue:1368-1382（对照 1412-1417） | 中 | S |
| F7 | 5 | `handleResetConfig` 无 catch：`/ai/reset-config` 请求失败时 `resetting` 恒为 true，「恢复初始配置」按钮永久 loading 无法重试；异常冒泡为 unhandled rejection（拦截器 toast 之外页面零状态兜底） | apps/admin-web/src/views/ai/AIConfig.vue:1311-1340 | 中 | S |
| F8 | 1 | 信息架构错位：「节目参数（目标时长/段间静音/最大段数/预期字数）」放在「LLM 大模型」tab，但段间静音是 TTS 拼接参数（后端 config_key `segment_gap_sec`→`SEGMENT_GAP_SEC`，用于 stitch），找它的运营第一反应在 TTS tab；且这些字段全部寄生在 `llmForm` 里随 LLM 一起保存 | apps/admin-web/src/views/ai/AIConfig.vue:50-82,852-861；backend/app/services/ai_config_service.py:148-151 | 中 | S |
| F9 | 4 | 「预期字数」tag 的段数硬钳 3~6 段，与上方「最大段数」可调 3~40 直接矛盾：听书档把最大段数调到 18~20 后，校验 tag 仍显示「6 段 × N 字」，高频调参场景下反馈失真 | apps/admin-web/src/views/ai/AIConfig.vue:69-82,1151-1154 | 中 | S |
| F10 | 2 | 切换预设无覆盖确认：`applyPreset` 一键改写已手填的 Base URL/模型名（不覆盖时才保留 preset 默认），未保存的手改值被静默替换（随后又被草稿持久化，错误被固化） | apps/admin-web/src/views/ai/AIConfig.vue:1247-1263 | 中 | S |
| F11 | 5/2 | TTS 模型下载状态不回显：轮询只在点按钮后存活，离开页面 `onUnmounted` 停轮询；再进来时后台仍在下载却无任何进行中指示，再点「下载模型」会再次 POST 触发新后台任务（可能并发重复下载） | apps/admin-web/src/views/ai/AIConfig.vue:1057-1112,1588-1590；backend/app/routers/admin/ai_config.py:408-439 | 中 | S |
| F12 | 2/6 | 保存语义是「五个 tab 一次全存」：`handleSave` 无条件提交 llm+tts+image+selected_preset，TTS tab 按保存会把 LLM tab 里改了一半的字段一并落库；界面没有任何「本次将保存全部 tab」提示，与常见「按 tab 保存」预期不符 | apps/admin-web/src/views/ai/AIConfig.vue:1266-1274 | 低 | M |
| F13 | 3 | 最高频动作「保存配置」与「恢复初始配置」均为纯图标按钮（IconButton 支持 `inline-text` 但未用），需悬浮才知语义；「恢复初始配置」label 有「LLM」限定只藏在 tooltip/desc 里，确认弹窗文案本身是清楚的 | apps/admin-web/src/views/ai/AIConfig.vue:4,37-46,1313-1316；apps/admin-web/src/components/IconButton.vue:27 | 低 | XS |
| F14 | 1 | 本页 1715 行按 tab 分组已缓解总量，但 TTS tab 内部为长单列：档位 alert→引擎选择→交叉音色→provider 表单→试音→测试连接，低屏需长滚，无锚点/折叠；视觉拥挤度需实测确认 | apps/admin-web/src/views/ai/AIConfig.vue:159-748 | 低 | S |
| F15 | 6 | 密钥显隐控件两套形态并存：LLM/TTS 用 `:type` 切换 + append 自绘 IconButton，图片 tab 用 `type=password show-password`；且 AppKey/SecretId 这类半敏感 ID 也全程掩码（后端确按敏感处理，一致但增加首次录入核对成本） | apps/admin-web/src/views/ai/AIConfig.vue:83-97 vs 755-762,315-333 | 低 | XS |
| F16 | 4/5 | 参数计算器同步：当前 provider 非 edge 时 `applyCalculatorParams` 仍把语速倍率写进 `edge_rate`（隐藏字段）并 toast「已从参数计算器同步：语速倍率」——用户看不到该字段、实际也不生效，提示与结果不符 | apps/admin-web/src/views/ai/AIConfig.vue:1553-1565 | 低 | S |
| F17 | 5 | 用量统计仅首次进 tab 且 trend 为空时加载，无刷新按钮；当天保存配置/调用后数据停留旧值 | apps/admin-web/src/views/ai/AIConfig.vue:1520-1537 | 低 | XS |
| F18 | 1/4 | 高频调参缺口：整页无温度/max_tokens 等采样参数入口（后端 chat 硬编码 temperature=0.7，`llmForm` 无对应字段），「试温度」只能在代码外做；「测试→保存→去智能助手实测」的生效验证路径也未在文案中给出 | apps/admin-web/src/views/ai/AIConfig.vue:49-154；backend/app/services/ai_config_service.py:1534 | 低 | M |

**恢复初始配置确认弹窗**（ElMessageBox，1313-1317）：文案准确列明清空范围与不可恢复性，未发现显著体验缺陷；替代优化——确认后草稿未清理（`commitDraft` 未在 reset 路径调用，1322-1339），reset 前遗留的本地草稿字段（如 timeout）可能立即覆盖回显示值，建议 reset 成功后同步 `commitDraft()`。

**交叉音色/试音/测试连接区块**：音色不足 2 个的告警（258-266）、piper 禁用说明（253-256）、试音 blob 错误手工解析 JSON（1499-1513）都做得到位，未发现显著体验缺陷；替代优化——「测试连接」按钮位于 tab 最底部（722-747），与顶部引擎选择区相距远，改完音色想验证需先滚到底。

**优化建议**（逐条对应编号）：
- F1：`llmForm/ttsForm/imageForm` 与最近一次服务端快照做深比较，保存按钮加圆点徽标 + tooltip「有 N 项未保存」；`onBeforeRouteLeave` + `beforeunload` 在未保存时拦截。
- F2：`applyDraft` 返回非 null（已有草稿）时页面顶部挂 `el-alert`「检测到上次未保存的修改（时间戳），已临时载入｜查看差异｜丢弃草稿」，丢弃=commit 清 localStorage；差异比对基线用 loadConfig 的服务端快照。
- F3：给每个密钥字段加「清除已保存密钥」小按钮（显式发送清除语义，如 `api_key__clear: true`），后端 `_normalize_*` 支持显式清除；同时把 `update_config` docstring 与实现对齐（当前「空字符串视为清除」为虚假承诺）。
- F4：统一在密钥字段 `field-tip` 写「已保存密钥显示为 ****后4位；保持脱敏值=不修改」。
- F5：watch 表单关键字段（base_url/model/api_key/provider 等）变化即置 `llmTestResult/ttsTestResult/imageTestResult = null`；保存成功同样清空。
- F6/F7：对齐 `handleTestTTS` 的写法补 catch：失败时结果 tag 置 `{success:false,message}`、`testingLlm/resetting` 在 finally 复位。
- F8：把「节目参数」divider 区块迁到 TTS tab（或独立「节目编排参数」tab），并与后端 key 归属对齐展示。
- F9：`calculatedSegments` 上限改用 `llm_max_script_segments`，或拆示「模型建议段数 / 上限段数」两值。
- F10：`applyPreset` 前若当前 base_url/model 与预设默认不同且未保存，弹 ElMessageBox 确认覆盖。
- F11：onMounted 时按当前 provider 拉一次 `/download-tts-models/status`，downloading 则恢复轮询与 tag；后端对同 provider 重复 POST 应幂等拒绝。
- F12：保存按钮移入各 tab 底部并按 tab 分组提交，或至少在确认 toast 中列「已保存：LLM/TTS/图片」。
- F13：「保存配置」加 `inline-text="保存"`；「恢复初始配置」label 改「恢复 LLM 初始配置」。
- F14：试音区与测试连接行用 `el-collapse`（默认收起试音历史）或在 card 右上加锚点链接。
- F15：全部改 `show-password` 统一形态。
- F16：同步前判断 provider，非 edge 时改提示「当前引擎不支持该倍率，已忽略」。
- F17：usage tab 加刷新图标按钮；`loadUsage` 每次进入 tab 都拉。
- F18：如调参是真实需求，在 LLM tab 增「生成参数」分区（temperature/top_p/max_tokens）并接后端；否则在 field-tip 说明「采样参数由代码控制」。

### F-2 AI 自动化 > 智能助手（路由 /ai-qa，文件 apps/admin-web/src/views/ai/KnowledgeQA.vue）

**现状描述**：顶部模型选择条（自动刷新开关 + 刷新按钮，即改即存：切模型立刻 POST `/ai/selected-model` 持久化）+ 两个 tab：「自动调度」（NL→动作草稿卡片→确认落地 create_channel）与「知识库问答」（POST `/ai/chat` 阻塞式整段返回，15s 前端超时，无流式、无停止生成）。空态引导、动作草稿可编辑确认流程、错误以 ⚠️ 气泡留在会话，框架完整。

**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| F19 | 2/5 | **长回复必然失败**：`/ai/chat` 用全局 axios `timeout: 15000`，而后端模型调用超时取 `LLM_TIMEOUT_SEC`（可配至 120s）；超过 15s 的回答前端报 `timeout of 15000ms exceeded`，会话只留错误气泡、无任何内容，也无法停止/续传——问答主流程在正常长度回答上走不通 | apps/admin-web/src/views/ai/KnowledgeQA.vue:498-501；apps/admin-web/src/api/index.js:17；backend/app/services/ai_config_service.py:1535；backend/app/routers/admin/ai_config.py:53 | 高 | S |
| F20 | 5 | 错误文案作为 role=assistant 消息永久留在 `messages`，下一轮整段历史再发给模型（489 行组装 history 不做过滤）：模型会把「⚠️ 调用模型失败…」当作自己的发言延续，污染后续回答；用户也无法删除单条错误 | apps/admin-web/src/views/ai/KnowledgeQA.vue:484-519 | 中 | S |
| F21 | 2 | 无会话管理：两个 tab 都没有「清空/新建会话」入口，历史无限增长，token 成本线性上涨直至上下文超限报错且无法自救（只能刷新页面） | apps/admin-web/src/views/ai/KnowledgeQA.vue:216-265 | 中 | S |
| F22 | 4 | 新手引导文案与界面对不上：guideConfig 对 /ai-qa 的描述是「可切换模型并**选择会话来源**」「开启自动刷新可**跟随最新会话**」——实际自动刷新刷的是模型列表（90s 轮询 /ai/models），页面上不存在任何「会话来源」概念；且步骤选择器 `.top-bar` 在本页 DOM 中不存在（本页是 `.as-header`），引导高亮退化到整页容器 | apps/admin-web/src/guide/guideConfig.js:82-85；apps/admin-web/src/views/ai/KnowledgeQA.vue:2-46,278 | 中 | XS |
| F23 | 5 | 模型自动刷新双重打扰：轮询失败会把 `modelError` 置红，用户正在问答时页面顶部突然弹出「无法获取模型列表」告警（无关闭按钮、无解释来源）；90s 一次的 silent 轮询持续消耗 provider /models 配额 | apps/admin-web/src/views/ai/KnowledgeQA.vue:49-58,414-445,467-482 | 中 | S |
| F24 | 2/6 | 保存范式在两页间冲突：本页切模型是「即改即存」（POST /ai/selected-model，弹「已切换模型」），AI 服务页是「编辑→点保存」；运营在 /ai-qa 换的模型与 /ai-config 的「模型名称」字段分属两处存储（`llm_selected_model` vs `llm_model`），页面上无一句文案说明两者关系，首次配置者会以为同一字段 | apps/admin-web/src/views/ai/KnowledgeQA.vue:456-465；apps/admin-web/src/views/ai/AIConfig.vue:102-129；backend/app/services/ai_config_service.py:1573-1580 | 中 | S |
| F25 | 5 | `onModelChange` 持久化失败被 catch 吞掉后**仍然**弹「已切换模型：X」成功 toast：本次会话生效但默认值没存住，下次进入变回旧模型，反馈与实际状态不符 | apps/admin-web/src/views/ai/KnowledgeQA.vue:456-465 | 低 | XS |
| F26 | 2 | 确认创建仅校验 name 非空（168 行 disabled 条件），其余 required 字段（schedule_time 等）靠后端 ChannelCreateRequest 报错，前端展示的是 Pydantic 原始 str(e)（经 422 透传），首次使用者看不懂要改哪个框 | apps/admin-web/src/views/ai/KnowledgeQA.vue:163-174；backend/app/routers/admin/assistant.py:91-106 | 中 | S |
| F27 | 6 | 失败提示三层叠加：拦截器对 code≠0 已 `ElMessage.error(message)`，页面 catch 再弹一次同样文案的 toast，再在会话流里留 ⚠️ 气泡——一次失败最多看到 2 个 toast + 1 条气泡 | apps/admin-web/src/api/index.js:39-44；apps/admin-web/src/views/ai/KnowledgeQA.vue:346-352,373-375 | 低 | XS |
| F28 | 3/5 | 消息渲染为纯插值文本（`{{ msg.content }}`）：无 markdown/代码块渲染、无复制按钮，长回复只能手动划选；`.assistant { height: calc(100vh - 140px) }` 写死页高，与 Layout 实际头部高度的匹配需实测确认 | apps/admin-web/src/views/ai/KnowledgeQA.vue:182,232,543 | 低 | S |
| F29 | 2 | 发送即清空输入：plan 失败后原文案丢失，重试需重新敲指令；用户消息气泡上无「重新发送」动作 | apps/admin-web/src/views/ai/KnowledgeQA.vue:308-357 | 低 | XS |
| F30 | 3 | 草稿卡片 `v-for :key="idx"` + 按索引 splice 删除：删除中间卡片后后续卡片表单项可能因索引复用而错位（受控 v-model 可部分抵消，风险需实测确认）；已执行卡片里 `el-result` 成功态与头部「✅ 已创建」tag 信息重复 | apps/admin-web/src/views/ai/KnowledgeQA.vue:78,93-108,380-382 | 低 | XS |
| F31 | 1 | 「自动调度」tab 名大于实：后端仅支持 `create_channel`（其余 action_id 直接 400），确认按钮、结果文案也全部写死「频道/前往频道管理」；而 `/assistant/actions` 注册表接口前端封装了（assistant.js:13 `listAssistantActions`）却从未调用，动态能力没被用起来——文案上应说明当前仅支持新增频道 | apps/admin-web/src/views/ai/KnowledgeQA.vue:100-108,163-174,371；backend/app/routers/admin/assistant.py:80-81；apps/admin-web/src/api/assistant.js:13 | 中 | S |

**空态与错误态（两 tab）**：调度 tab 空态给了可点抄的示例指令、问答 tab 空态显示当前模型并承诺「切换立即生效」（与后端每次请求携带 model 的实现一致，核实无误）；未发现显著体验缺陷。替代优化——问答 tab 无模型时输入框直接 disabled，仅靠底部一行橙色小字提示，建议空态里给一个「去 AI 服务配置 LLM」的链接按钮（当前 LLM 未配置时 modelError 只说「模型列表为空」，新手不知道要去 /ai-config 填 key）。

**优化建议**（逐条对应编号）：
- F19：chat 请求单独放宽 `timeout: Math.max(LLM_TIMEOUT_SEC+10, 120000)`；中期上 SSE（后端 `/ai/chat` 增加 stream 透传），前端加「停止生成」按钮与逐字渲染；短期至少在错误气泡旁提示「可稍后重试，回答可能仍在生成」。
- F20：错误气泡存 `kind:'error'` 标记，组装 history 时过滤掉 error 条目；每条 AI 消息 hover 显示删除入口。
- F21：输入栏上方加「清空会话」图标按钮（带确认），dispatch 与 qa 各自独立。
- F22：重写 guideConfig 文案为「顶部选择对话模型，自动刷新每 90 秒同步最新模型列表」；步骤选择器改 `.as-header`、`.as-model-select`、`.as-input-bar`。
- F23：轮询失败只降级不打扰（silent 时不写 `modelError`，改为刷新按钮上挂小红点 + tooltip 最近失败原因）。
- F24：模型切换 toast 补一句「仅影响智能助手问答，播报流水线模型请去 AI 服务保存」；或把两处模型字段合并展示（读取 `/ai/config` 的 llm.model 作参照）。
- F25：持久化失败时 toast 降级为 `ElMessage.warning('本次已切换，但默认模型保存失败')`。
- F26：按 `f.required` 做前端必填/格式校验（schedule_time 用 HH:MM 正则），确认按钮 disabled 条件覆盖全部 required 字段，错误定位到具体表单项。
- F27：这两个调用传 `{ silent: true }`，由页面统一决定 toast/气泡的展示层。
- F28：接入轻量 markdown 渲染 + 消息级复制按钮；页高改 flex 由 Layout 供给。
- F29：失败时把原文案回填输入框，或用户消息 hover 出「重发」。
- F30：`:key` 改消息唯一 id（push 时生成）；已执行卡片只保留 el-result 一种成功呈现。
- F31：tab 内首条空态文案点明「当前支持：新增频道」；若注册表继续留空，删除未使用的 `listAssistantActions`，或反向用它渲染多动作确认表单。

---

统计：高 3（F2、F3、F19）/ 中 13（F1、F4-F11、F20-F24、F26、F31）/ 低 10（F12-F18、F25、F27-F30）；共 31 条。

---

## 7. 系统配置（内网穿透 / 通知 / 自动审批）

> 评审基线：`apps/admin-web/src/api/index.js:30-72` 响应拦截器对业务错误（HTTP 200 且 `code!==0`）执行 `Promise.reject(new Error(message))`（index.js:39-43），**只保留 `.message`，丢弃 `.code`/`.data`**；且非 silent 请求会先 `ElMessage.error(message)` 一次。此事实贯穿三页错误处理判断。

### G-1 系统配置 > 内网穿透（路由 /tunnel，文件 apps/admin-web/src/views/tunnel/Tunnel.vue）

**现状描述**：状态卡片 + 下载/授权引导 alert + Provider 配置表单 + Cloudflare 固定域名三步向导。保存走 `POST /tunnel/config`（字段与后端 `TunnelConfigBody` 一一对齐，无包装名差异）。但引导 UI 依赖 `error.response.data.code` 分支，与拦截器错误形态不符；配置加载失败时表单退回默认值。

**问题清单**：
| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| G1 | 5/2 | 「二进制下载失败」引导块与「Tailscale Funnel 需要授权」引导块**永不渲染**：后端 `/tunnel/start` 下载失败/需授权时返回 HTTP 200 + `{code:5001/5003,data.error_type,...}`，但拦截器把 `code!==0` 当作业务错误 `reject(new Error(message))`，`handleStart` 里 `error?.response?.data || error` 得到的是纯 Error（无 `.code`/`.data`），`resp?.code === 5001` 恒为假，`downloadError/tailscaleAuthError` 始终为 null。用户只看到一句泛化 toast，看不到手动放置路径/复制/下载源/授权链接 | apps/admin-web/src/views/tunnel/Tunnel.vue:484-496；apps/admin-web/src/api/index.js:39-43；backend/app/routers/admin/tunnel.py:123-150 | 高 | M |
| G1a | 5 | 承 G1：因拦截器已弹一次 `ElMessage.error(message)`，`handleStart` else 分支又 `ElMessage.error(resp?.message)`，启动失败时**同一错误弹两次** | apps/admin-web/src/views/tunnel/Tunnel.vue:495；apps/admin-web/src/api/index.js:41 | 低 | XS |
| G2 | 4/2 | `loadConfig()` 失败仅 `console.error`、无任何用户提示（catch 446-448），页面静默退回表单默认值（provider=cloudflare、hostname/tunnel_id/credentials_file/tunnel_name/binary_path 全空）。运维在网络抖动后直接点「保存配置」→ `handleSaveConfig` 把默认值 POST，后端 `save_config` 会**用空值覆盖已持久化的 Named Tunnel 字段并把 provider 重置为 cloudflare**（仅 authtoken/cert_file 有 `or existing` 兜底，其余无） | apps/admin-web/src/views/tunnel/Tunnel.vue:446-448,521-534；backend/app/services/tunnel_service.py:249-261 | 高 | S |
| G3 | 1/6 | `path_prefix` 契约缺口：`get_config()` 返回 `path_prefix`（tunnel_service.py:233），但前端 `form` 无该字段、`handleSaveConfig` 不提交，后端 `save_config` 组装的 `new_cfg` 也不含 `path_prefix` → 每次保存配置文件写回后 `_load_config` 用默认 `/news/` 兜底，多应用共存场景下自定义前缀被**静默清零**，直接影响 Tailscale URL 前缀与跳转 | backend/app/services/tunnel_service.py:233,249-261,37-53；apps/admin-web/src/views/tunnel/Tunnel.vue:369-381 | 中 | S |
| G4 | 2/5 | 「启动隧道」是 120s 长阻塞（`timeout:120000`），期间仅有按钮 loading 转圈，无「正在下载二进制/首次较慢，请勿关闭」进度文案，也无取消入口；对照同页 G1 本应显示的下载引导又失效，长等待体验断层 | apps/admin-web/src/views/tunnel/Tunnel.vue:476-500 | 中 | S |
| G5 | 2 | 「停止」即时切断公网访问（影响外部可访问性），按钮无二次确认、无「停止后远程设备将无法访问」后果说明；`handleStop` 成功提示「隧道已关闭」但未提示开机自启/当前 provider 下次仍会重启 | apps/admin-web/src/views/tunnel/Tunnel.vue:502-515,49-57 | 中 | XS |
| G6 | 1 | 死代码：`apiBaseURL` computed（405-410）定义后模板/逻辑均未引用，易误导后续维护者以为界面会展示 API 基址 | apps/admin-web/src/views/tunnel/Tunnel.vue:405-410 | 低 | XS |
| G7 | 2 | 固定域名向导步骤依赖 `config` 已加载：`handleCloudflareRouteDns` 取 `config.value?.tunnel_name || config.value?.tunnel_id` 作为 `tunnel_name_or_id`，若 config 未加载成功（G2 场景）则传 `undefined`，提交后报「DNS 配置失败」但根因不可见 | apps/admin-web/src/views/tunnel/Tunnel.vue:625,430-448 | 低 | S |

**优化建议**：
- G1/G1a：改造拦截器为业务错误保留原始负载——`reject` 时挂上 `Object.assign(new Error(message), { code, data, isBusinessError:true })`（或让 `/tunnel/start` 这类需引导的端点走 `silent`+由页面自行判定 `code`）；`handleStart` 改读 `error.code/error.data`。避免与拦截器重复弹 toast：页面自处理时给请求传 `silent:true`。
- G2：`loadConfig()` catch 增加 `ElMessage.error('隧道配置加载失败，请勿直接保存，避免覆盖现有配置')` 并将 `savingConfig`/保存按钮置灰，直到成功加载；或后端 `save_config` 对所有字段统一采用 `body or existing` 兜底语义。
- G3：`form` 增加 `path_prefix` 字段并在 `loadConfig`/`handleSaveConfig` 往返提交，后端 `save_config` 写入时保留 `path_prefix`（`body.get('path_prefix', existing.get('path_prefix','/news/'))`）。
- G4：启动时显示 `ElMessage`/进度条 + 「首次会下载二进制，可能耗时 1-2 分钟」文案，配合 G1 修复后渲染真实下载引导。
- G5：停止前 `ElMessageBox.confirm('停止后所有远程设备将立即失去访问，确认？')`。
- G6：删除 `apiBaseURL` 或在状态卡片实际展示。
- G7：route-dns 前校验 `config.value` 存在，缺失时提示「请先完成创建隧道步骤」。

### G-2 系统配置 > 通知管理（路由 /notification，文件 apps/admin-web/src/views/notification/NotificationConfig.vue）

**现状描述**：三 Tab（基础配置/消息模板/发送日志），基础配置含全局+3 场景开关、钉钉/企微/邮件三渠道凭证、测试发送、访问地址；保存走 `PUT /notification/config`（字段与后端 `SaveConfigBody` 完全对齐，`enabled` 布尔/0-1 由 Pydantic 兼容，无包装名差异）。敏感脱敏仅覆盖 `dingtalk_secret`/`email_smtp_password`。

**问题清单**：
| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| G8 | 4/2 | 加载失败后保存**静默清空已持久化渠道 + 反转到「全局开启」**：`loadConfig()` catch 空处理（569-571），`configForm` 初始 `global_enabled:true`（527）而 `dingtalk_webhook/wecom_webhook/email_smtp_host/email_to/admin_base_url` 初始全空（531-539）；`handleSaveConfig` 提交 `{...configForm}`，后端 `save_config` 对这些 key **无条件写入 `str(data or "")`**（无 `or existing` 兜底，仅 secret/password 有 masked 跳过）→ 网络抖动后点保存会把 webhook/SMTP 全部清成空串，并把全局开关从库里的 `0` 改成 `1`，导致本应静音的通知被打开 | apps/admin-web/src/views/notification/NotificationConfig.vue:526-540,548-574,576-589；backend/app/services/notification/config_service.py:119-155,21-35 | 高 | S |
| G9 | 6/4 | 脱敏不一致且泄密：`get_config()` 只脱敏 `dingtalk_secret`/`email_smtp_password`，却把 `dingtalk_webhook`、`wecom_webhook` **原样明文返回**（含 `access_token=` 凭据段），界面用 `type=password` 掩成圆点（52-53,95-96），用户误以为是脱敏占位；一旦手动清空/改前缀即破坏 token。界面注释「后端返回脱敏值 ****」（552）与实际不符 | backend/app/services/notification/config_service.py:100-102,38,48-52；apps/admin-web/src/views/notification/NotificationConfig.vue:552,51-65 | 中 | M |
| G10 | 2/5 | 「测试发送」先落库再发送的隐性副作用：`handleTestSend` 每次点击都先 `saveNotificationConfig({...configForm})`（597）把当前（可能半填写）表单持久化，再真实向**所有已配置渠道群发**测试消息（599），按钮仅 desc「向所有已配置渠道发送测试通知」，未提示「会先把未保存修改写入配置且真实推送至群」 | apps/admin-web/src/views/notification/NotificationConfig.vue:173-181,591-611；backend/app/services/notification/sender.py:240-272 | 中 | S |
| G11 | 5 | 保存/校验失败双重 toast：`saveNotificationConfig` 业务错误时拦截器已 `ElMessage.error(message)`，页面 catch 虽注释「拦截器已统一提示」不再弹，但 `handleTestSend` 的 catch（606-607）又把 `e.message` 塞进 `testResult` 显示 danger tag，与拦截器 toast 叠加，反馈来源混乱 | apps/admin-web/src/api/index.js:41；apps/admin-web/src/views/notification/NotificationConfig.vue:604-607 | 低 | XS |
| G12 | 2 | 模板开关「改即存」连带未提交正文：`handleTemplateChange` 切换 enabled 会调用 `handleSaveTemplate`（630-643），该保存把 `name/title_template/body_template` 一并落库，用户仅想临时开关却把正在编辑、未点保存的文案改动一起写进去 | apps/admin-web/src/views/notification/NotificationConfig.vue:236-243,630-650 | 低 | S |

**优化建议**：
- G8：`loadConfig()` catch 明确提示「配置加载失败，禁止保存」并禁用保存按钮；后端 `save_config` 对 webhook/host/user/to/admin_base_url 也统一 `data[k] or existing` 语义，或前端仅在加载成功后提交（区分「未改动」与「清空」）。修正前端默认 `global_enabled` 与后端默认 `0` 不一致。
- G9：对 `dingtalk_webhook`/`wecom_webhook` 同样脱敏返回（如仅尾 6 位）+ `*_configured` 布尔 + 「已配置，留空不修改」占位（与 Tunnel 的 authtoken 处理对齐），并让 `_is_masked` 跳过逻辑覆盖 webhook。
- G10：测试发送前用 `ElMessageBox` 说明「将真实推送到已配置群」；或后端 `/test` 支持接收未落库的表单快照，避免「点测试=隐式保存」。
- G11：给 `/notification/test` 传 `silent` 并统一由页面渲染结果 tag，消除双弹。
- G12：开关切换只提交 `{enabled}` 单字段（后端 `UpdateTemplateBody` 支持 `exclude_none` 部分更新）。

### G-3 系统配置 > 自动审批（路由 /auto-review，文件 apps/admin-web/src/views/system/AutoReviewConfig.vue）

**现状描述**：规则配置（总开关 + 内容安全/一次成功两条 AND 规则 + 关键词白名单）、统计四卡、执行历史表 + 失败重试。**PUT 契约完全对齐**（`{enabled,require_content_safe,require_steps_first_success,keyword_whitelist}` ↔ `ConfigUpdateRequest`，无必填/包装名/类型不符）；本界面**无数值阈值**，故「pass 分数 vs 自动通过分数矛盾」前提在本项目不适用。真正风险是「零条件即上线」。

**问题清单**：
| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| G13 | 2/4 | **护栏缺失，可致任意内容零检查自动上线**：后端 `try_auto_approve` 对三条规则均是「开启才校验」，`require_content_safe`/`require_steps_first_success` 关闭且 `keyword_whitelist` 为空时，`matched_rules` 与 `fail_reasons` 皆空 → 直接进入 approve+publish。界面divider 承诺「全部命中才自动通过」，但当管理员打开总开关又把两条规则都关掉、白名单留空时，等于「无条件全部命中」；UI 与后端 `update_config`（无「至少保留一条规则」兜底/校验）都不阻止该组合 | backend/app/services/auto_review_service.py:315-372,106-121；apps/admin-web/src/views/system/AutoReviewConfig.vue:40-110,339-356 | 高 | S |
| G14 | 5 | 加载失败后保存覆盖持久化白名单：`loadConfig` catch 虽弹 toast（332）但不阻断，`form` 退回默认 `keyword_whitelist:[]`（300），随后 `saveConfig` 提交空数组会清空已配置关键词白名单 | apps/admin-web/src/views/system/AutoReviewConfig.vue:322-336,296-301,339-348 | 中 | S |
| G15 | 2 | 打开总开关无任何「内容将自动发布上线、不可逆」的后果确认；开关直接 `v-model` 绑定，保存后才提示「下次工作流按新配置判定」，缺少「启用=放弃人工审核」的前置警示 | apps/admin-web/src/views/system/AutoReviewConfig.vue:40-46,349 | 中 | XS |
| G16 | 4 | 「关键词白名单」命名/语义歧义：后端把白名单当作「内容必须命中其中关键词才放行」的正向必要条件（`_check_keyword_whitelist` 未命中即 fail），而「白名单」直觉是「仅这些被豁免/排除」，界面提示仅「留空表示不启用此规则」，未说明「非空=内容必须包含其一」 | apps/admin-web/src/views/system/AutoReviewConfig.vue:82-110；backend/app/services/auto_review_service.py:222,336-346 | 低 | XS |
| G17 | 5 | 重试按钮 loading 以 `workflow_id` 为键（`retryingStat===row.workflow_id`），同一 workflow 多条历史记录会同时转圈、状态互相误标；应用 `row.id`(stat_id，即重试实际入参) 作键 | apps/admin-web/src/views/system/AutoReviewConfig.vue:252-253,413-441 | 低 | XS |
| G18 | 6 | 保存/校验失败双重 toast：拦截器已 `ElMessage.error(message)`，`saveConfig`/`retryStat` catch 又各弹 `'保存失败：'+err.message`，同错双提示 | apps/admin-web/src/views/system/AutoReviewConfig.vue:351-353,436-437；apps/admin-web/src/api/index.js:41 | 低 | XS |

**优化建议**：
- G13：前端在「总开关=开」且（两规则均关且白名单为空）时，`saveConfig` 阻断并提示「至少保留一项触发条件，否则所有内容将无检查直接上线」；后端 `update_config` 增加同等下限校验（`enabled` 为真时要求至少一条规则生效）。
- G14：`loadConfig` 失败时禁用保存按钮/回滚表单，避免以默认值覆盖；或改后端支持「仅提交被修改字段」的部分更新。
- G15：打开总开关时 `ElMessageBox.confirm` 说明放弃人工审核、发布不可逆。
- G16：文案改为「关键词必要条件（非空时，内容须包含其一才自动通过）」，或在输入框下补一行语义说明。
- G17：`retryingStat` 改用 `row.id`。
- G18：由页面自处理的请求传 `silent:true`，消除与拦截器重复弹错。

---
**契约对齐小结（正向确认）**：
- 内网穿透 `POST /tunnel/config` 全字段 ↔ `TunnelConfigBody`（tunnel.py:34-51）名称/类型一致；create/route-dns 必填字段（tunnel_name、tunnel_name_or_id+hostname）均按序提交，无缺失。
- 通知 `PUT /notification/config` ↔ `SaveConfigBody`（notification.py:34-47）一致；模板 `PUT` 部分字段 ↔ `UpdateTemplateBody(exclude_none)` 兼容 0/1→bool。
- 自动审批 `PUT /auto-review/config` ↔ `ConfigUpdateRequest`（auto_review.py:27-38）必填三项齐全，`retry/{stat_id}` 用 `row.id` 正确。
- 主要缺陷集中在**错误形态假设（G1）**、**加载失败退默认值再保存的静默覆盖（G2/G8/G14）**、**脱敏不一致（G9）**与**自动审批零条件上线（G13）**，而非字段名不匹配。

---

## 8. 云端存储（云端配置 / 文件管理）

### H-1 云端存储 > 云端配置（路由 /cos-config，文件 apps/admin-web/src/views/cos/CosConfig.vue）

**现状描述**：单表单页，顶部右侧「测试连接/保存配置」图标按钮 + 就绪状态 tag，卡内为 SecretId/SecretKey/地域/Bucket/CDN 五字段，密钥以「****+后4位」脱敏回显、password 控件 + 显隐开关（只泄露掩码位，真实密钥永不下发前端），草稿机制已排除敏感字段落盘——凭据明文泄露风险未发现。主要风险集中在「加载失败后保存会静默清空配置」「测试连接语义误导首装用户」「Bucket 占位文案做出后端未兑现的承诺」。

**问题清单**：
| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| H1 | 5 | loadConfig 失败被 catch 吞掉后表单保持初值 bucket=''，「保存配置」payload 仍无条件携带 bucket/cdn_domain，后端 update_config 也无条件覆写这两项 → 加载失败（网络抖动/500）后点一次保存即把已存 Bucket、CDN 域名清空，配置静默损毁且需重填凭据才能恢复 | apps/admin-web/src/views/cos/CosConfig.vue:198-209,214-220；backend/app/services/cos_config_service.py:139-143 | 高 | M |
| H2 | 4 | Bucket 输入框 placeholder 承诺「不含 -{appid} 后缀亦可，系统按 SecretId APPID 拼接」，但后端将 COS_BUCKET 原样传给 SDK，全仓无任何 appid 拼接逻辑 → 首装用户按文案省略后缀，保存后所有操作报「存储桶不存在」，无从排查 | apps/admin-web/src/views/cos/CosConfig.vue:101-103；backend/app/cos/client.py:63 | 高 | S |
| H3 | 2 | 「测试连接」只测**已保存生效**的配置（读 Settings 单例），不测表单当前值；首装用户填完四项直接点测试，得到「COS 未配置：请先填写 SecretId/SecretKey/Bucket」——字面意思是"没填"，实际是"没保存"，界面任何位置未说明该差异 | apps/admin-web/src/views/cos/CosConfig.vue:229-233；backend/app/services/cos_config_service.py:212-224 | 中 | M |
| H4 | 5 | handleSave 成功后不清 testResult：修改并保存新配置后，上一轮的绿色「连接成功」横幅仍滞留页顶，用户会误以为新配置已验证通过 | apps/admin-web/src/views/cos/CosConfig.vue:26-37,211-227 | 中 | XS |
| H5 | 6 | onMounted 顺序为 loadConfig→applyDraft：localStorage 旧草稿在服务端最新配置**之后**深合并覆盖 form（bucket/region/cdn 均可能回退成上次未提交的旧值），且 hasDraft 从未展示，无任何「已恢复草稿」提示条/撤销入口 → 双管理员场景下 A 的新值被 B 的陈草稿静默顶掉再被保存 | apps/admin-web/src/views/cos/CosConfig.vue:242-246；apps/admin-web/src/composables/useDraft.js:62-81 | 中 | S |
| H6 | 4 | 顶部说明「留空（显示为 **** ）则保留原值」把两种状态混为一谈；实际空字符串与掩码值都被后端跳过（无法从 UI 清除/删除凭据，想注销密钥做不到），后端 docstring 甚至自相矛盾地写「空字符串视为清除 Key」 | apps/admin-web/src/views/cos/CosConfig.vue:45-46；backend/app/services/cos_config_service.py:136,145-148 | 低 | XS |
| H7 | 2 | el-form 无 :rules、必填项无红星：Bucket 留空也能点「保存配置」且成功提示照发（与 H1 叠加即毁配置）；保存按钮无 dirty 门槛，配置未改动也总是全量提交 | apps/admin-web/src/views/cos/CosConfig.vue:49,98-104,211-227 | 中 | S |

**优化建议**：
- H1：① loadConfig 失败置 `loadFailed=true` 并禁用「保存配置」+ 展示重试横幅；② 后端 CosConfigBody 字段改 `Optional[str] = None`，None=保持原值、""=显式清空，前端只提交 dirty 字段（落点 CosConfig.vue、backend/app/routers/admin/cos.py:35-41、cos_config_service.py:126-149）。
- H2：二选一——把 placeholder 改为「必填完整桶名，含 -APPID 后缀，如 news-1250000000-1300000000」；或在 update_config/客户端初始化里真正实现按 SecretId 推导 APPID 拼接（推荐先改文案，S 级止血）。
- H3：短期在按钮 tooltip/alert 文案注明「测试的是已保存配置，修改后请先保存再测试」；根治让 /cos/test-connection 接收可选表单值并用临时客户端试连（未保存也能验密）。
- H4：handleSave 开头 `testResult.value = null`。
- H5：applyDraft 检出草稿时顶部提示「已从本地草稿恢复未提交内容（时间戳）[丢弃草稿]」；或草稿带 savedAt，晚于服务端 updatedAt 才允许覆盖。
- H6：文案改为「显示为 ****xxxx 或留空均不会修改已存密钥」；若需支持清除，配合 H1 的 None 语义加显式「清除凭据」次级按钮 + 二次确认。
- H7：bucket 加 required+格式校验（`/^[\w-]+-\d+$/` 呼应 H2），保存前校验不通过时按钮置灰并标红字段。

### H-2 云端存储 > 文件管理（路由 /cos-files，文件 apps/admin-web/src/views/cos/CosFiles.vue）

**现状描述**：面包屑（桶根/子目录）+ 上传/新建文件夹/刷新按钮组 + 单表列表（文件夹在前、文件在后），行内下载/重命名/删除操作。删除文件/文件夹有确认且明示「不可恢复」，交互底线合格。集中风险在：文件夹重命名路径拼接缺陷、上传同名静默覆盖、耗时操作零进度、页面不显示当前 bucket。

**问题清单**：
| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| H8 | 5 | 后端返回的文件夹名自带结尾斜杠（"sub1/"），行内 name 与表格显示均含"/"；openRename 把含"/"的 name 预填进「新名称」，confirmRename 再无条件追加"/" → 用户在重命名弹窗**不改动直接点确定**时 destKey="sub1//"（≠row.key 所以不会短路返回），整个目录被移进"//"畸形路径，列表随即出现空白子层级，等效数据错位；改对也要求用户手动删掉预填的尾斜杠，全程无提示 | apps/admin-web/src/views/cos/CosFiles.vue:214-221,327,339-343；backend/app/services/cos_storage_service.py:145-150 | 高 | S |
| H9 | 2 | 「上传文件」不做同名检测：后端 key=prefix+原文件名直接 put_object，重传同名音频即静默覆盖旧对象，无「已存在，是否覆盖？」确认 → 高频运维最容易触发的无确认破坏性动作 | apps/admin-web/src/views/cos/CosFiles.vue:288-300；backend/app/routers/admin/cos.py:141-145；backend/app/services/cos_storage_service.py:191 | 高 | M |
| H10 | 5 | opLoading 唯一视觉载体是两个已关闭弹窗的 footer 按钮：点「上传文件」选中文件后，按钮无 loading、无进度条、卡片 v-loading 也不触发，60s 硬超时的上传期间界面完全静止（可再次点击重复提交）；移动/递归删除大目录同样全程无反馈 | apps/admin-web/src/views/cos/CosFiles.vue:32-38,291,313,344,367（loading 绑定处仅 :129,:161）；apps/admin-web/src/api/cos.js:35-37 | 中 | S |
| H11 | 2 | 上传仅支持单文件（input 无 multiple，代码只取 files[0]），批量传素材需逐一「点按钮-选文件-等 toast」，且无「成功 N 件/失败 M 件+失败清单」汇总 | apps/admin-web/src/views/cos/CosFiles.vue:54-59,288-290 | 中 | M |
| H12 | 1 | 页面任何位置不显示当前 bucket/region（getCosStatus 返回的 bucket 被丢弃，面包屑只称「桶根」）：在云端配置切桶后进入本页无法确认操作对象，CDN 域名变更同样不可见 | apps/admin-web/src/views/cos/CosFiles.vue:242-249；backend/app/routers/admin/cos.py:104-109 | 中 | XS |
| H13 | 5 | loadList 失败仅弹 toast，folders/files 维持旧值或空数组 → 首屏加载失败时误显示空态「该目录下暂无内容」，用户会把接口故障当成目录为空；列表无错误态横幅/重试入口（三态缺「错误」一态） | apps/admin-web/src/views/cos/CosFiles.vue:64,251-263 | 中 | S |
| H14 | 5 | loadStatus 的 catch 把网络失败也置 configured=false，顶部显示「COS 尚未配置：请先在云端配置页填写…」——配置明明完好，仅 status 请求失败即误导用户重填凭据 | apps/admin-web/src/views/cos/CosFiles.vue:242-249 | 中 | XS |
| H15 | 2 | 列表无列排序（名称/大小/最后修改均未开 sortable）、无文件名搜索、无分页控件；后端自动翻页上限 10 页×1000（超出静默截断，响应也不带 truncated 标志），万级目录用户不知情 | apps/admin-web/src/views/cos/CosFiles.vue:66-80；backend/app/services/cos_storage_service.py:36-38,140-173 | 中 | M |
| H16 | 3 | 文件夹名称单元格渲染为带尾斜杠的"sub/"（H8 同源显示层）；「最后修改」列直接输出后端 ISO 串（含 T/时区，200px 列宽下长串可读性差、格式是否溢出需实测确认）；大小列文件夹恒为"-" | apps/admin-web/src/views/cos/CosFiles.vue:73,78-79,218；backend/app/services/cos_storage_service.py:355-364 | 低 | S |

**优化建议**：
- H8：list_path 返回或前端映射时 strip 文件夹名尾斜杠（显示用）；row.key 单独保留完整前缀；confirmRename 对 newName 做 `replace(/\//g,'')` 校验并加 rules；destKey 拼接前归一化。
- H9：上传前调用对象存在性检查（后端已有 cos_client.object_exists，backend/app/cos/client.py:202，补一个 HEAD 路由），已存在则 ElMessageBox「该目录下已有同名文件，是否覆盖？」；或 upload 接口加 `overwrite=false` 参数由后端拒绝并回传可读错误。
- H10：上传按钮绑定 loading 并 disabled；上传改用 axios onUploadProgress 显示百分比（el-progress）；删除文件夹给出「正在递归删除…」常驻提示；超时按文件大小放宽而非硬编码 60s。
- H11：input 加 multiple，循环上传后汇总 toast/列表「成功 N、失败 M（文件名+原因）」，失败项可单独重试。
- H12：top-bar 或面包屑左侧显示「桶根（{bucket} · {region}）」，status 数据已有，零后端改动。
- H13：loadList catch 置 listError=true，卡片内显示错误 alert +「重试」按钮，与 el-empty 区分。
- H14：loadStatus 失败区分「未配置」与「状态获取失败（重试）」两文案。
- H15：三个数据列加 sortable；顶部加名称过滤输入框（可纯前端过滤）；后端响应透出 truncated 标志，前端提示「目录对象超过上限，仅显示前 1 万项」。
- H16：last_modified 前端格式化为 `YYYY-MM-DD HH:mm`（本地时区）；文件夹名显示去除尾斜杠（与 H8 一并解决）。

### H-2a 文件管理 > 新建文件夹弹窗

**现状描述**：单输入 + 取消/确定（均带 loading），回车可提交，前后端均拒绝含 "/" 的名称并做路径穿越校验，基本可用。
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| H17 | 6 | 校验规则与重命名弹窗不一致：本弹窗拦空+拦"/"，重命名弹窗连"/"都不拦（见 H18）；对 ".."、首尾空格、与既有文件夹同名均无表单内提示，靠后端报错 toast 兜底 | apps/admin-web/src/views/cos/CosFiles.vue:307-311,333-337 | 低 | XS |

**优化建议**：H17：抽公共 `validateObjectName`（非空、不含 / \ ..、trim），两弹窗共用并以 el-form rules 内联提示，替代事后 warning toast。

### H-2b 文件管理 > 重命名/移动弹窗

**现状描述**：原名称禁用回显 + 新名称输入，回车提交，destKey 恒等于当前前缀+新名。标题承诺与实际能力不符。
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| H18 | 1 | 弹窗标题「重命名 / 移动」，但实现只支持同级重命名（前缀硬编码 currentPrefix），无任何目标目录选择器；用户期望"移动文件到别的目录"落空，误把"/"写进新名会产生命名畸形或意外深层 key | apps/admin-web/src/views/cos/CosFiles.vue:139,338-339 | 中 | M |
| H19 | 2 | 重命名目标与既有对象同名时不检测不确认：后端 move=copy+delete 直接覆盖目标对象（且文件夹移动逐对象串行 copy，大目录耗时长、弹窗确定按钮 loading 单一 opLoading 与删除等共享），数据丢失无感知 | apps/admin-web/src/views/cos/CosFiles.vue:344-349；backend/app/services/cos_storage_service.py:277-315 | 中 | M |

**优化建议**：H18：短期把标题与 desc 改为「重命名（仅限当前目录）」；完整版加目标目录下拉（用 list_path 懒取子目录）真正实现"移动"。H19：move 前 HEAD 目标 key，存在则覆盖确认；与 H9 复用同一存在性检查接口。

### H-2c 文件管理 > 删除确认 / 空态 / 未配置态

**现状描述**：删除文件和文件夹均有 ElMessageBox 强确认，文案明确「及其下所有内容」「此操作不可恢复」，按钮名「确认删除」，底线合格；空目录显示 el-empty；未配置显示 warning alert。
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| H20 | 4 | 删除文件夹确认框不含对象数量（用户无法预估影响面）；成功后后端返回「已删除 N 个对象」message 被拦截器解构丢弃，UI 只说"已删除"，批量删除规模反馈缺失 | apps/admin-web/src/views/cos/CosFiles.vue:356-379；backend/app/routers/admin/cos.py:196；apps/admin-web/src/api/index.js:37-45 | 低 | S |
| H21 | 2 | 未配置态 warning alert 只说「请先在云端配置页…」，无可点击的跳转（router-link/按钮直达 /cos-config），首装用户在两页间手动找菜单 | apps/admin-web/src/views/cos/CosFiles.vue:5-13 | 低 | XS |

**优化建议**：H20：确认文案插入对象数（删除前调用 /cos/objects 或 metadata 计数，超阈值如 >500 时要求输入文件夹名确认）；删除成功 toast 使用返回的 count（改接口返回 data.count 前端展示「已删除 N 个对象」）。H21：alert 内嵌「前往云端配置」link-button，另附 H12 的修复可在配置保存返回时自动带刷新。

**跨页一致性备注**：菜单组名「云端存储」下两页标题「云端配置/文件管理」清晰；但同实体称谓不一——配置页用「存储桶 Bucket」「桶名称」，文件管理面包屑用「桶根」，storage 报错文案用「云端配置页填写凭证」，建议统一为「存储桶（Bucket）」并在文件页头部显示实际桶名（随 H12 一并解决）。视觉维度（列宽、ISO 串溢出、尾斜杠观感）基于模板/scss 推断，需实测确认。

---

## 9. 移动端适配模式 `/m/*`

> 走查范围：`apps/admin-web/src/views/mobile/*` 全部页面 + `layouts/MobileLayout.vue` + 路由守卫/请求拦截器 + 与 PC 端（`views/review/ReviewList.vue`、`views/queue/QueueManagement.vue`、`views/workflow/WorkflowDetail.vue`）一致性对照。视觉结论均从模板/`<style>`/媒体查询推断，标注「需实测确认」者为无法静态断言项。

---

### I-1 移动端 > 审批（路由 /m/review，文件 apps/admin-web/src/views/mobile/ReviewList.vue）
**现状描述**：卡片列表 + 标题行点击展开懒加载详情 + 每卡「驳回/通过」+ 顶部「一键全部审批」。支持从队列页带 `workflow_id` 进入的作用域模式。整体触控目标做得较好（标题行 min-height 44px）。
**问题清单**：
| # | 维度 | 问题（具体到界面元素/交互节点，禁止笼统） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| I1 | 2 | 「通过」按钮单击即调用 `handleReviewAction(...,'approve')` 并触发后端自动发布，无任何二次确认；而同卡的「驳回」却有 prompt。外勤拇指易误触「通过」→ 直接发布节目，误操作不可逆 | apps/admin-web/src/views/mobile/ReviewList.vue:154 / 246-275 | 高 | S |
| I2 | 2 | 「一键全部审批」在**非作用域**模式下把跨频道全部待审（最多 200 条）一次性通过，仅一个 confirm 文案「确认一键通过当前 N 条」，不展示频道分布、不要求选择，小屏一键即批量发布，确认强度与风险不匹配 | apps/admin-web/src/views/mobile/ReviewList.vue:17-24 / 288-318 | 高 | M |
| I3 | 1 | 作用域模式顶部「工作流」chip 直接显示 `route.query.workflow_id` 的**原始值**（从队列进入时是队列任务 id 数字），而非工作流名称；与「展示当前工作流名称」的注释/语义不符，用户看到一串 id | apps/admin-web/src/views/mobile/ReviewList.vue:13 / 175-177 | 中 | S |
| I4 | 6 | 单条「驳回」允许留空理由并静默写死为「移动端驳回」；PC 批量打回强制 `inputValidator` 理由非空。同一功能两端理由口径冲突，下游作者无法区分真实驳回原因 | apps/admin-web/src/views/mobile/ReviewList.vue:250-263 ↔ apps/admin-web/src/views/review/ReviewList.vue:254-263 | 中 | S |
| I5 | 6 | 移动端列表卡片缺失 PC 端已有的关键质量信号：`measured_duration_sec`（时长）与 `supplement_sec`「凑时」标记（PC 用 tooltip+warning tag 提示成品时长不代表真实内容长度）。外勤在移动端审批时看不到「凑时」，可能把凑时长的节目判为合格 | apps/admin-web/src/views/mobile/ReviewList.vue:49-54 / 80-100 ↔ apps/admin-web/src/views/review/ReviewList.vue:71-88 | 高 | M |
| I6 | 5 | 每次 approve/reject 成功后调 `await load()` 全量重取，列表被整体替换为新对象（`expanded:false`），正在展开阅读的详情会收起、滚动位置丢失；处理长列表时需反复定位 | apps/admin-web/src/views/mobile/ReviewList.vue:267-269 / 197-203 | 中 | M |
| I7 | 2 | 列表仅 `onMounted(load)`，无下拉刷新；从消息/首页跳入或审批完成返回后不自动刷新，跨 tab 状态陈旧 | apps/admin-web/src/views/mobile/ReviewList.vue:320 | 中 | S |
| I8 | 5 | 加载 `catch` 为空（依赖拦截器 toast），失败后 `list` 保持空数组 → 界面显示「暂无待审内容 🎉」把网络/服务错误误报为「无待审」 | apps/admin-web/src/views/mobile/ReviewList.vue:210-214 / 158 | 中 | S |
| I9 | 3 | 详情区「完整文本」用 `max-height:320px;overflow-y:auto` 内层滚动，嵌在页面滚动容器内，移动端易出现「滚动陷阱」（需实测确认双指/惯性滚动手感） | apps/admin-web/src/views/mobile/ReviewList.vue:584-597 | 低 | S |
| I10 | 4 | 加载态仅 `v-if="loading && !list.length"` 显示「加载中…」，重取（审批后 load）时已有列表不显示任何进行中提示，「一键审批」期间除按钮文案外无遮罩 | apps/admin-web/src/views/mobile/ReviewList.vue:27 / 19-24 | 低 | S |

**优化建议**：
- I1：给「通过」加轻确认（ElMessageBox.confirm 或滑动确认/长按 500ms），至少与「驳回」对称；或在未展开阅读详情前禁用「通过」。
- I2：作用域外模式改为需勾选/展示「覆盖 X 频道 Y 条」并要求输入数量确认；或限制一键仅对当前已加载页生效并明示。
- I3：chip 优先显示 `workflow_name`，id 作为次要小字；从队列跳转时带真实工作流名（见 I-12）。
- I4：与 PC 对齐——驳回理由设为必填（沿用 inputValidator），去掉「移动端驳回」兜底。
- I5：卡片/详情补 `时长` 与 `凑时` warning 标记，字段口径直接复用 PC（`measured_duration_sec`/`supplement_sec`/`original_duration_sec`）。
- I6：审批后就地移除该卡片或局部更新，避免整表重建；保留展开态与滚动位置。
- I7：接入下拉刷新（容器已有 `-webkit-overflow-scrolling`，补 touch 事件或改用支持刷新的列表容器）。
- I8：区分「加载失败」与「空」两态，失败显示错误+重试按钮。
- I9/I10：低优先打磨，展开文本改为整段铺开或提供「放大查看」；进行中补顶部进度条/骨架。

---

### I-2 移动端 > 登录（路由 /m/login，文件 apps/admin-web/src/views/mobile/Login.vue）
**现状描述**：自绘账号/密码 + 登录按钮，输入框 16px 防 iOS 聚焦放大，登录成功 `replace('/m/home')`。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I11 | 2 | 登录成功固定跳 `/m/home`，丢失深链目标：未登录直接访问 `/m/review` 被守卫弹到 `/m/login`，登录后回不到原意图页（无 `?redirect=` 回跳） | apps/admin-web/src/views/mobile/Login.vue:51 + apps/admin-web/src/router/index.js:316-319 | 中 | S |
| I12 | 5 | 提交错误完全依赖响应拦截器 toast；表单无内联错误位、无字段级校验高亮，toast 被 `safeElMessage` 在页面隐藏/恢复期丢弃时用户看不到任何反馈 | apps/admin-web/src/views/mobile/Login.vue:52-56 + apps/admin-web/src/utils/message.js:38-42 | 中 | S |
| I13 | 2 | 已登录状态下直接访问 `/m/login`（public 路由放行）仍显示登录表单，不自动进 `/m/home`，易造成「重复登录」困惑 | apps/admin-web/src/router/index.js:310-313 + Login.vue:43-57 | 低 | S |
| I14 | 4 | 无密码可见性切换、无「忘记密码/联系管理员」出口；纯占位 hint「建议使用企业微信/钉钉内置浏览器」对新用户无帮助链接 | apps/admin-web/src/views/mobile/Login.vue:14-27 | 低 | S |

**优化建议**：I11 守卫跳转时携带 `redirect`，登录成功后回跳；I12 表单补内联错误文本 + 失败抖动，减少对 toast 的依赖；I13 有 role 时 `replace('/m/home')`；I14 补密码显隐与错误联系文案。

---

### I-3 移动端 > 首页（路由 /m/home，文件 apps/admin-web/src/views/mobile/Home.vue）
**现状描述**：今日指标 2×2 卡 + 「待我审批 / 未读消息」两行入口，数据来自 `/m/dashboard-summary` 聚合。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I15 | 5 | `getDashboardSummary().catch(()=>({today:{},pending_review:0,unread_message:0}))` 把失败静默成「DAU -、待审 0、未读 0」的正常空态；外勤首屏遇网断会误判「今天没有要审的」 | apps/admin-web/src/views/mobile/Home.vue:57-66 | 高 | S |
| I16 | 6 | 首页「未读消息」用 `dashboard-summary.unread_message`，消息页用 `/m/inbox.unread_count`（I-4），两处口径来自不同接口，数字可能不一致，用户切到消息页发现对不上 | apps/admin-web/src/views/mobile/Home.vue:64 ↔ Message.vue:51 | 中 | M |
| I17 | 1 | `msgReady` 恒为 `true`，模板里「建设中」文案与底部 `m-tip`「消息中心…当前为占位」永远不显示，是残留死代码/误导注释 | apps/admin-web/src/views/mobile/Home.vue:43 / 21 / 26-28 | 低 | XS |
| I18 | 2 | 仅 `onMounted(load)`，无下拉刷新；从审批页返回首页后「待我审批」数不更新，与审批页实际条数脱节 | apps/admin-web/src/views/mobile/Home.vue:75 | 中 | S |

**优化建议**：I15 失败态与空态分离，展示「加载失败/重试」；I16 统一未读口径（首页复用 inbox 计数或都走 dashboard 聚合）；I17 删除 msgReady 死分支或据真实就绪状态驱动；I18 加下拉刷新/`onActivated` 重载。

---

### I-4 移动端 > 消息（路由 /m/message，文件 apps/admin-web/src/views/mobile/Message.vue）
**现状描述**：未读数 + 「全部已读」+ 卡片列表（等级色点/类型标签/时间），数据来自 `/m/inbox`，点击标记已读。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I19 | 2 | 点击消息 `open()` 仅标记已读、对已读/审批类消息直接 `return`，注释写「已读项若带深链可跳转（如审批详情）」但无任何跳转实现：外勤点开「审批提醒」消息无法直达对应待审项，流程断在这里 | apps/admin-web/src/views/mobile/Message.vue:63-71 | 高 | M |
| I20 | 5 | `load()` 只有 `try/finally` 无 `catch`，`getInbox` 抛错后 `list` 保持空 → 显示「暂无消息」空态吞掉错误（拦截器 toast 会被页面隐藏期丢弃） | apps/admin-web/src/views/mobile/Message.vue:46-55 / 11 | 中 | S |
| I21 | 2 | 固定 `page:1, page_size:20`，无加载更多/分页；超过 20 条历史消息不可达，也无下拉刷新 | apps/admin-web/src/views/mobile/Message.vue:49 | 中 | M |
| I22 | 4 | 「全部已读」无二次确认，一键把包括 critical 告警在内的所有未读标为已读，误触即丢失待办提示 | apps/admin-web/src/views/mobile/Message.vue:5 / 57-61 | 中 | S |
| I23 | 3 | `levelClass` 常量定义后未使用；圆点类名直接拼 `'m-msg__dot--'+m.level`，level 非 info/warning/critical 时落到 `.m-msg__dot` 灰色默认，未知等级告警颜色缺失 | apps/admin-web/src/views/mobile/Message.vue:44 / 20 / 137-152 | 低 | S |

**优化建议**：I19 给 `msg_type==='review'` 的消息接深链跳 `/m/review?workflow_id=…`（并按 I-12 修正真实 id）；I20 补 catch→错误态+重试；I21 加触底加载更多；I22 「全部已读」加 confirm；I23 删除死常量并给未知等级一个兜底色。

---

### I-5 移动端 > 我的（路由 /m/mine，文件 apps/admin-web/src/views/mobile/Mine.vue）
**现状描述**：头像/用户名/角色 + 「切换到 PC 完整后台」+ 退出登录。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I24 | 2 | `goPc()` 直接 `router.push('/review')`。手机视口（<768px）`isMobile` 仍为 true，落到 PC 布局在手机上不可用（侧栏/宽表挤压）；且与「视口自动切移动端」机制冲突：一旦发生视口变化或重进被 `syncModeRoute` 立刻弹回 `/m/home`（无 force-desktop 写入、无提示） | apps/admin-web/src/views/mobile/Mine.vue:31-33 ↔ App.vue:32-57 + useIsMobile.js:46-51 | 中 | M |
| I25 | 2 | 返回移动端无应用内路径：进入 PC 后只能靠浏览器后退；「我的」页也无面包屑/返回说明 | apps/admin-web/src/views/mobile/Mine.vue:11-14 | 中 | S |
| I26 | 6 | 信息单薄：无版本号、无「当前角色能做什么」说明、无消息通知开关入口；与 PC「我的/关于」承载信息不一致 | apps/admin-web/src/views/mobile/Mine.vue:2-17 | 低 | M |

**优化建议**：I24 「切换到 PC 完整后台」应写 `setForcedMode('desktop')`（或跳带 `?mode=desktop` 的 URL）再导航，避免被自动切回；宽屏可用提示、窄屏提示「建议横屏/桌面端」。I25 进入 PC 模式后在 PC 端也提供「返回移动版」入口。I26 补版本与角色说明。

---

### I-6 壳层（文件 apps/admin-web/src/layouts/MobileLayout.vue）
**现状描述**：48px 吸顶标题 + 中部 `router-view` + 底部 tabBar（管理项 adminOnly）。`.m-app` 用 `100dvh` + `safe-area` 适配刘海/底部。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I27 | 1 | tabBar 各 item **无未读角标**（审批待办数、消息未读数都不体现）：外勤停在审批 tab 时无法感知有新消息/新待审，必须逐个 tab 点进去看 | apps/admin-web/src/layouts/MobileLayout.vue:11-22 / 35-45 | 高 | M |
| I28 | 2 | 管理子页（hidden 路由）复用同一 MobileLayout，标题正确但顶部**无返回箭头**；从 `/m/manage/users` 返回 `/m/manage` 只能再点底部「管理」tab（tab 高亮虽正确，但缺显式「← 返回」，层级感弱） | apps/admin-web/src/layouts/MobileLayout.vue:3-5 / 47-49 | 中 | S |
| I29 | 1 | `titleMap`（home:'运营助手'…）与路由 `meta.title`（'首页'）双份命名并存，`title` 计算优先 meta，titleMap 实为死代码，两处命名不同步风险 | apps/admin-web/src/layouts/MobileLayout.vue:47-57 ↔ router/index.js:229 | 低 | XS |
| I30 | 3 | tabBar 文字 11px、图标 22px，item 高度未固定（padding 6px/4px）；整体约 <44px 命中区偏小（需实测确认拇指误触率） | apps/admin-web/src/layouts/MobileLayout.vue:105-124 | 低 | S |

**优化建议**：I27 给「审批/消息」tab 加 `el-badge`/红点角标，数据源统一走 I-3/I-4 口径；I28 子页在 appbar 左侧渲染返回按钮（`hidden` 路由时显示「‹ 管理」）；I29 删 titleMap 或统一到 meta；I30 给 item 设 `min-height:48px`。

---

### I-7 移动端 > 管理入口（路由 /m/manage，文件 apps/admin-web/src/views/mobile/ManageHome.vue）
**现状描述**：2×3 宫格入口，卡片文案「启用/停用、取消/重试」等已描述各子页动作范围；顶部提示「仅管理员、与 PC 数据实时同步」。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I31 | 1 | 顶部「与 PC 后台数据实时同步」为不实承诺：各子页仅 `onMounted` 拉一次，无轮询/SSE（PC 队列有 5s 轮询+SSE），移动端并不「实时」，易误导管理员以陈旧数据决策 | apps/admin-web/src/views/mobile/ManageHome.vue:3 ↔ QueueManagement.vue:542-548 | 中 | S |
| I32 | 1 | 「应急停服」卡图标 `WarningFilled` 为普通主色样式，与其他管理卡视觉同权，未对高危动作做红色/警示区分 | apps/admin-web/src/views/mobile/ManageHome.vue:31 / 71-74 | 低 | S |
| I33 | 6 | 6 个入口均无「移动端仅支持部分操作」的范围说明（如频道不含新建/排期、队列不含改优先级/删除），desc 只写正向动作，缺能力边界 | apps/admin-web/src/views/mobile/ManageHome.vue:25-32 | 低 | S |

**优化建议**：I31 文案改「进入页面时同步」或补轮询；I32 应急停服卡用 danger 配色；I-7 卡片对缺失能力补「(完整操作请用 PC 端)」标注。

---

### I-8 移动端 > 用户管理（路由 /m/manage/users，文件 apps/admin-web/src/views/mobile/ManageUsers.vue）
**现状描述**：`el-input` 搜索 + 卡片列表（昵称/状态徽标/脱敏 openid/收听量）+ 启停按钮（带二次确认）。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I34 | 3 | 启停按钮 `.m-btn--sm` 高 34px（<44px），是该行唯一动作却是小命中区；搜索按钮 `.m-users__searchbtn` 同 32px | apps/admin-web/src/views/mobile/ManageUsers.vue:108-112 / 170-175 | 中 | S |
| I35 | 2 | 固定 `page:1,size:50`，无分页/加载更多；用户数 >50 时后续不可达，搜索也只回到第一页 | apps/admin-web/src/views/mobile/ManageUsers.vue:63 | 中 | M |
| I36 | 5 | `catch` 空吞错→`list` 空显示「暂无用户」，与真实「无搜索结果」混淆 | apps/admin-web/src/views/mobile/ManageUsers.vue:65-69 / 16 | 低 | S |
| I37 | 3 | 「收听 X 次 · Y 秒」直接展示秒数（`total_listen_duration`），未像 Home 那样换算「分」，大数值可读性差且单位口径与其它页不一致 | apps/admin-web/src/views/mobile/ManageUsers.vue:28 ↔ Home.vue:54 | 低 | S |

**优化建议**：I34 动作按钮统一 ≥44px 或整卡可点进详情；I35 加触底分页；I36 区分错误/空；I37 秒换算为分/时展示。

---

### I-8b 移动端 > 用户反馈（路由 /m/manage/feedback，文件 apps/admin-web/src/views/mobile/ManageFeedback.vue）
**现状描述**：4 段状态 tab（全部/待处理/处理中/已解决）+ 卡片 + 「标记为…」逐级流转。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I38 | 6 | 状态集合为 pending/processed/resolved；但无「已处理→回退/重新打开」反向动作，单向流转，误点「标记为已解决」不可撤销且无确认 | apps/admin-web/src/views/mobile/ManageFeedback.vue:57-58 / 28-32 / 84-94 | 中 | S |
| I39 | 3 | tab `.m-fb__tab` 高 34px 且 4 个并排（`flex:1`），小屏每段 <60px 宽、文案「待处理/处理中」易截断，命中区偏小 | apps/admin-web/src/views/mobile/ManageFeedback.vue:111-126 | 中 | S |
| I40 | 2 | 固定 `size:50` 无分页/加载更多；`catch` 空吞错→「暂无反馈」 | apps/admin-web/src/views/mobile/ManageFeedback.vue:65-75 | 低 | S |
| I41 | 1 | 无按 category/关键词筛选，仅有状态 tab；反馈量大时难定位 | apps/admin-web/src/views/mobile/ManageFeedback.vue:42-47 | 低 | M |

**优化建议**：I38 流转加确认+支持回退；I39 tab 改可横向滚动或增大高度/字号；I40 分页+错误态；I41 补分类筛选。

---

### I-9 移动端 > 频道管理（路由 /m/manage/channels，文件 apps/admin-web/src/views/mobile/ManageChannels.vue）
**现状描述**：卡片列表（名称/状态徽标/描述/定时）+「启用/停用」按钮，调 `updateChannel(id,{is_active})`。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I42 | 2 | 频道停用是线上影响动作（停用会取消该频道 queued 任务、停止内容产出），但 `toggle(c)` **零确认**直接执行；对照用户禁用却有 ElMessageBox 二次确认（I-8），确认强度与安全等级倒挂 | apps/admin-web/src/views/mobile/ManageChannels.vue:48-57 ↔ ManageUsers.vue:72-91 + QueueManagement.vue:560 | 高 | S |
| I43 | 6 | `is_active` 布尔字段被写成数字 `0/1`（`next=c.is_active?0:1`），与 PC 端布尔口径不一致，依赖后端强转；停用后本地把 `is_active=0` 但接口返回若回布尔可能与列表真值不符 | apps/admin-web/src/views/mobile/ManageChannels.vue:49 / 52 | 中 | S |
| I44 | 5 | `catch` 空吞错→「暂无频道」；无分页（`listChannels(false)` 一次全量，频道多时无限长列表性能/滚动问题） | apps/admin-web/src/views/mobile/ManageChannels.vue:36-45 / 4 | 低 | S |

**优化建议**：I42 停用加 ElMessageBox 二次确认并说明连带影响；I43 按后端契约统一布尔；I44 补错误态、必要时折叠/分页。

---

### I-10 移动端 > 广告投放（路由 /m/manage/ads，文件 apps/admin-web/src/views/mobile/ManageAds.vue）
**现状描述**：卡片列表（素材名/投放中·已停用徽标/位置/周期）+「停用/启用」（`updatePlacement(id,next)`）。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I45 | 2 | 广告启停直接影响线上投放曝光，`toggle` **零确认**，与用户禁用有确认、频道应确认的口径不一致（同 I42 类问题） | apps/admin-web/src/views/mobile/ManageAds.vue:50-59 ↔ ManageUsers.vue:72-91 | 高 | S |
| I46 | 4 | 卡片主标题用 `material_name || '素材 #id'`，用户操作语义是「启停投放规则」，但界面呈现对象是「素材名」，命名与动作对象（投放规则/排期）易混淆 | apps/admin-web/src/views/mobile/ManageAds.vue:9 ↔ router/index.js:277 | 中 | S |
| I47 | 5 | 固定 `page:1,size:50` 无分页；`catch` 空吞错→「暂无投放规则」 | apps/admin-web/src/views/mobile/ManageAds.vue:41-47 | 低 | S |

**优化建议**：I45 启停加二次确认；I46 标题体现「投放规则」并副标题带素材名与投放位；I47 分页+错误态。

---

### I-11 移动端 > 队列监控（路由 /m/manage/queue，文件 apps/admin-web/src/views/mobile/ManageQueue.vue）
**现状描述**：顶部 4 统计（排队/执行/失败/已完成）+ 任务卡（频道/状态/队列编号可复制/来源/期次/优先级/错误）+ 取消/重试/去审核。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I48 | 2 | 「去审核」`goReview` 把**队列任务主键 `t.id` 当作 `workflow_id`** 传入（`query:{workflow_id:t.id}`），审核页用其过滤 `params.workflow_id`。任务 id ≠ 工作流 id（PC 队列详情显示「任务 ID」，工作流另有 workflow_id 口径，见 WorkflowDetail 用 `route.params.id` 即真实 workflow_id），作用域审核页大概率过滤为空 → 显示「暂无待审内容 🎉」，误导管理员以为无待审 | apps/admin-web/src/views/mobile/ManageQueue.vue:79-84 ↔ ReviewList.vue:194-195 ↔ QueueManagement.vue:194 ↔ WorkflowDetail.vue:866 | 高 | M |
| I49 | 6 | 统计「已完成」读 `stats.finished`，但 PC `/queue/stats` 用 `stats.success`（PC 卡片 `stats.success||0`）。字段口径不一致 → 移动端「已完成」几乎恒显示 `-` | apps/admin-web/src/views/mobile/ManageQueue.vue:17 ↔ QueueManagement.vue:20 | 高 | S |
| I50 | 6 | 状态标签映射用 `finished:'已完成'`，而任务实际状态值是 `success`（PC `STATUS_LABEL_MAP.queued/running/success/...`），移动端已完成任务显示原始字符串「success」而非「已完成」；`running` 用 `m-badge--warn`（橙）与 PC `primary`（蓝）颜色不一致 | apps/admin-web/src/views/mobile/ManageQueue.vue:86-94 ↔ QueueManagement.vue:253-265 | 中 | S |
| I51 | 5 | `getQueueStats().catch(()=>null)` 吞错隐藏统计条（stats 为 null 时整块 `v-if` 不显示），任务列表 `catch` 空吞→「队列为空」；错误态与真空态不可分 | apps/admin-web/src/views/mobile/ManageQueue.vue:99-108 / 23 | 中 | S |
| I52 | 2 | 无下拉刷新/轮询（PC 有 5s 轮询+SSE）；队列是强动态页，移动端进入后状态冻结，running→failed 变化不可见 | apps/admin-web/src/views/mobile/ManageQueue.vue:167 ↔ QueueManagement.vue:542-548 | 中 | M |
| I53 | 3 | 「去审核」按钮对所有状态（含 running/failed）恒显示，未过滤——失败/执行中任务本无可审内容，点了进空作用域页（叠加 I48） | apps/admin-web/src/views/mobile/ManageQueue.vue:56-59 | 低 | S |

**优化建议**：I48 队列任务对象需带真实 `workflow_id`，`goReview` 用 `t.workflow_id`（并在 UI 用名称而非 id 显示）；I49/I50 统一读 `success` 键、状态标签/色板与 PC `STATUS_LABEL_MAP/STATUS_TAG_MAP` 对齐；I51 分错误/空态；I52 加下拉刷新或轻量轮询（尊重 `document.hidden`）；I53 「去审核」仅在存在待审关联时启用。

---

### I-12 移动端 > 应急停服（路由 /m/manage/alert，文件 apps/admin-web/src/views/mobile/ManageAlert.vue）
**现状描述**：停服状态横幅（维护/正常 + 原因/操作人）+ 说明文案 + 「应急停服/解除应急停服」按钮，停服走 prompt 采集原因、恢复走 confirm。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I54 | 2 | **高危动作功能失效**：`stop()` 里 `const { value } = await ElMessageBox.prompt(...)` 之后写 `reason = v.trim()`，`v` 在该作用域未定义 → 抛 ReferenceError 被外层 `catch { return }` 吞掉，等同「用户取消」，`emergencyStop` 永不触发。点「应急停服」填完原因确认后毫无反应，应急态无法开启 | apps/admin-web/src/views/mobile/ManageAlert.vue:53-62 | 高 | XS |
| I55 | 5 | `getMaintenanceStatus().catch(()=>({enabled:false}))` 把「读不到状态」误判为「生产运行正常」（绿色横幅）：真实处于停服态但状态接口失败时，管理员看到「生产运行正常」，掩盖事故现场，且据此可能误操作 | apps/admin-web/src/views/mobile/ManageAlert.vue:44 / 6-7 | 高 | S |
| I56 | 6 | 文案「该操作仅超级管理员可用」，但路由 `requireRole:'admin'` 只校验到 admin；普通 admin 能进入并点击，失败靠后端 403→拦截器 toast，前端权限口径与文案不一致 | apps/admin-web/src/views/mobile/ManageAlert.vue:14 ↔ router/index.js:290 | 中 | S |
| I57 | 3 | 停服/恢复用桌面 `ElMessageBox.prompt/confirm`，小屏 textarea 与按钮宽度/触控需适配（Element Plus 对话框非移动端形态，需实测确认是否撑不满/输入不便） | apps/admin-web/src/views/mobile/ManageAlert.vue:53-58 / 73-75 + utils/message.js | 中 | M |
| I58 | 2 | 停服成功后不刷新展示 `m.value` 的操作人/时间以外信息，且无「再次确认」（高危一键即停）；相比 I54 修复后，仍建议停服要求二次确认或输入指定关键字 | apps/admin-web/src/views/mobile/ManageAlert.vue:63-68 | 低 | M |

**优化建议**：I54 立即改 `reason = value.trim()`（并把校验/赋值移出易错写法，`reason` 未用可删）；I55 失败态显示「状态未知/重试」而非默认绿色正常；I56 前端补 super-admin 判定或与后端一致化文案；I57 移动端用底部动作面板替代桌面 MessageBox；I58 停服加输入关键字二次确认。

---

### I-13 跨端一致性 / 角色入口 / 深链（路由守卫、App.vue、拦截器）
**现状描述**：App.vue 以 `matchMedia(<768px)` 自动在 `/m` 与 PC 命名空间间切换（`?mode=` 可覆盖）；守卫 `beforeEach` 以 `localStorage.admin_role` 作登录代理态，`requireRole:'admin'` 拦非管理员。
**问题清单**：
| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| I59 | 1 | 深链直接访问：正常桌面浏览器（视口≥768）打开 `/m/review` 会被 `syncModeRoute` 直接弹到 `/review`，移动端页面在 PC 无法预览（除非 `?mode=mobile`）；反之手机打开 `/review` 弹到 `/m/home`。运维/测试发移动端深链给他人点开常落到 PC，「深链直接访问是否可用」存疑 | App.vue:38-46 + useIsMobile.js:15/46-51 | 中 | S |
| I60 | 2 | 非管理员被拦体验：`requireRole` 命中时 `ElMessage.error('仅管理员可访问'); next(false)`。若在**直达深链/首屏**（如直接输入 `/m/manage`）时 `next(false)` 中止初始导航，`router-view` 无内容可渲染 → 移动端出现空白页而非回落到 `/m/home` | apps/admin-web/src/router/index.js:322-327 | 中 | S |
| I61 | 6 | `localStorage` 键 `admin_role/admin_username` 与 PC 共用（同源同会话，登录态本就共享，属预期）；但守卫把 `role` 当唯一登录代理，其它标签页/PC 端登出后移动标签仍持旧 `admin_role` 停留在已失效会话，直到某请求 401 才被拦截器清态跳转——两端「状态互相污染」主要体现在陈旧登录态而非数据 | router/index.js:307-330 + stores/user.js:11-14 + api/index.js:52-61 | 中 | M |
| I62 | 5 | 拦截器 401 用 `globalThis.location.href='/news/m/login'` 硬跳转（非 router），整页刷新丢弃 SPA 状态与未提交输入；`document.hidden` 时错误全静默，移动后台切前台后错误不再提示 | apps/admin-web/src/api/index.js:49-61 | 低 | S |
| I63 | 3 | 全站移动端仅用 px、无 rem/vw/媒体查询断点：3 列/4 列栅格（队列统计 `repeat(4,1fr)`、Home/Manage `repeat(2,1fr)`）在 ≤360px 小屏可能挤压溢出（需实测确认换行/截断） | ManageQueue.vue:177-181 + Home.vue:92-96 | 低 | M |
| I64 | 1 | PC 与移动端「审批」命名/口径不同：PC 页标题「内容审核」、tab「待审核/已通过/已打回」，移动端标题「审批」、驳回动作 PC 称「打回」——同一功能跨端术语混用（审核/审批、驳回/打回） | router/index.js:37/235 ↔ ReviewList.vue:6/153 ↔ 移动 Meta '审批' | 低 | S |

**优化建议**：I59 允许通过 URL（如带移动端标记或 `?mode=mobile`）稳定访问移动端深链，避免预览/分享被弹回；I60 `requireRole` 拦截时改 `next('/m/home')` 回落而非 `next(false)`，并对首屏空白兜底；I61 进入需鉴权路由前做一次轻量会话校验（或用 `/auth/me` 探活）；I62 401 改用 router 跳转并携带 redirect，前后台恢复时补显式错误；I63 关键栅格加 `flex-wrap`/小屏降列或引入 vw 单位；I64 统一术语（建议全站「审核 / 通过 / 驳回」或「审批 / 通过 / 打回」二选一）。

> 说明：`href="#/xxx"` 在 history 路由下不跳转的问题——本轮走查 `/m` 命名空间及 MobileLayout **未发现** `href="#..."` 拼接锚点写法（tabBar 用 `router-link`，审核素材链接为真实外链 `target="_blank"`），此项无缺陷。

---

### 条数统计（共 64 条，编号 I1–I64）
- 高：**12 条** — I1, I2, I5, I15, I19, I27, I42, I45, I48, I49, I54, I55
- 中：**30 条** — I3, I4, I6, I7, I8, I11, I12, I16, I18, I20, I21, I22, I24, I25, I28, I31, I34, I35, I38, I39, I43, I46, I50, I51, I52, I56, I57, I59, I60, I61
- 低：**22 条** — I9, I10, I13, I14, I17, I23, I26, I29, I30, I32, I33, I36, I37, I40, I41, I44, I47, I53, I58, I62, I63, I64

> 高危动作与「首次走不通/与 PC 口径冲突」集中在：应急停服按钮实际失效（I54）、状态读失败误显正常（I55）、队列「去审核」参数口径错配致空态（I48）、审批「通过」零确认即发布（I1）+ 一键跨频道批量发布（I2）、移动端看不到 PC「凑时」质量信号（I5）、频道/广告启停零确认（I42/I45）、首页把错误吞成「无待审」（I15）、消息无法深链跳转（I19）、tabBar 无未读角标（I27）、已完成统计字段口径不一致恒显示「-」（I49）。

---

# Slice J — 微信小程序用户端 UX 评审（T02323）

评审范围：`apps/miniprogram` 全部 18 个页面（按 `app.json` 声明顺序）+ `app.json` 的 tabBar/window 配置 + `components/`、`services/`、`utils/`、`app.js` 生命周期与登录态；能力一致性对照 `backend/app/routers/api/`。
方法约束：只读走查源码，未运行构建、未上传体验版；纯 wxml/wxss 无法证实的视觉结论一律标注「需实测确认」。

## 10. 微信小程序用户端

**先做的一件确定的事 —— tabBar 实际声明值（`apps/miniprogram/app.json:28-50`）**

| 序号 | pagePath | text | iconPath | selectedIconPath |
|---|---|---|---|---|
| 1 | pages/index/index | **缺失（无该键）** | images/icons/tab-today-inactive.png | images/icons/tab-today-active.png |
| 2 | pages/history/history | **缺失（无该键）** | images/icons/tab-history-inactive.png | images/icons/tab-history-active.png |
| 3 | pages/profile/profile | **缺失（无该键）** | images/icons/tab-profile-inactive.png | images/icons/tab-profile-active.png |

结论：三项 `list` 只写了 `pagePath`/`iconPath`/`selectedIconPath`，**没有任何一项带 `text`**。这是合法配置（微信允许纯图标 tabBar），但对本产品构成首屏级信息架构缺陷，已记为 J1（高）。叠加全站「T00384 图标即按钮」去文案改造，用户端在首屏、详情页动作区、设置页底部栏、外链兜底页四个关键位置都是零文字标签。

### J-1 底部导航 > 今日节目（pages/index/index，含 app.json 全局配置）

**现状描述**：首屏为「顶栏（搜索+睡眠两个图标）→ 频道横向胶囊 → 问候卡（今日共 N 个频道已更新）→ 继续收听卡 → 节目行列表」，配 `enablePullDownRefresh`，空态与骨架齐备，信息密度控制得不错。主要问题集中在三处：底部导航纯图标无文字、顶栏随 loading 整块消失造成跳变、以及播放态浮条在长驻 tab 页上不刷新。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J1 | 1 | 底部导航只有图标、无文字：三个 tab 项均未声明 `text`，「今日/历史/我的」全靠图形猜测；`tab-today/history/profile` 三个图标在小尺寸下辨识度低，新用户首次进入无法预判第二个 tab 是播放记录还是节目库，而这两者恰好各有两套实现（见 J14、J63） | apps/miniprogram/app.json:33-49 | 高 | XS |
| J2 | 5 | 顶栏 `wx:if="{{!loading}}"` 包住搜索入口、频道胶囊与睡眠定时器整条（wxml:4、8），下拉刷新即令三个入口同时消失再出现，首屏布局明显跳变；用户想在下拉刷新时点搜索会点空 | apps/miniprogram/pages/index/index.wxml:4,8 | 中 | S |
| J3 | 1/6 | 顶栏两枚按钮为纯图标且连 `aria-label` 都没有（wxml:5-6、19-20 只有 `<image>`），而历史页同类工具条却逐枚写了 aria-label（history.wxml:36,40,47）：同一控件族两套无障碍规范，屏幕阅读器用户在首页完全听不到这两枚按钮 | apps/miniprogram/pages/index/index.wxml:5-6,19-20；apps/miniprogram/pages/history/history.wxml:34-47 | 中 | XS |
| J4 | 4 | 空态标题把「错误」和「今日暂无」塞进同一字段 `error \|\| '今日节目暂未上线'`，网络异常时用户读到的是「节目暂未上线，通常每天上午更新」，被明确误导为内容问题而非连接问题，且该空态无重试按钮（重试只在骨架超时态出现） | apps/miniprogram/pages/index/index.wxml:42-43,132-138 | 高 | XS |
| J5 | 5 | 播放中浮条在首页不出现：`floating-player` 只在 `attached` 调用 `_refresh()` 计算 `visible`/`episode`，两个订阅回调只 setData `isPlaying` 与进度角（js:24-36），组件无 `pageLifetimes.show`；tab 页组件 attach 一次后常驻，从详情播放返回首页时 `visible` 仍为旧值 false → 浮条整条不显示，用户失去暂停/续播入口 | apps/miniprogram/components/floating-player/floating-player.js:21-37,45-58；apps/miniprogram/pages/index/index.wxml:155 | 高 | S |
| J6 | 2 | 行内播放键 `catchtap="onPlayEpisode"` 会「立即起播 + navigateTo 详情」（wxml:125），整卡 `bindtap="onTapEpisode"` 也进详情（wxml:84），两个区域语义相同但一个会发出声音；想"先看详情再决定听不听"没有入口，拇指落在卡片右下即意外播放 | apps/miniprogram/pages/index/index.wxml:84,125 | 中 | S |
| J7 | 1 | 首页声明了 6 个 wxml 未绑定的处理函数（`onToggleFavorite`、`onTogglePlay`、`onSeek`、`onViewScript`、`onOpenQueue`、`onCycleRate`），其中 `onOpenQueue:737` 意味着首页本应有队列入口却没落地——直接后果是队列页只剩一个无文字图标可进（见 J72） | apps/miniprogram/pages/index/index.js:606,697,712,721,737,872 | 中 | S |
| J8 | 2 | 偏爱为空时的引导卡，其设置按钮是纯图标（仅有 aria-label「去设置偏爱频道」，无可见文字），这是新用户第一个必须完成的动作，却只给一个齿轮 | apps/miniprogram/pages/index/index.wxml:54 | 中 | XS |
| J9 | 3 | 频道胶囊对课程/听书的类型区分主要靠 `course` 类换色（wxml:13-17），无文字前缀；色弱与低亮度场景不可辨（需实测确认） | apps/miniprogram/pages/index/index.wxml:13-17 | 低 | S |
| J10 | 6 | 游客可直接浏览与收听，但收藏/偏爱/进度云同步等能力的登录门槛要等到操作失败才以 toast 出现，首屏对游客身份零说明，与 profile 游客态的沉默（见 J19）连成一条断裂路径 | apps/miniprogram/pages/profile/profile.wxml:4-9；apps/miniprogram/pages/preferred-settings/preferred-settings.js(onSave) | 中 | S |

**优化建议**：
- J1：给三项补 `"text"`（今日 / 历史 / 我的），这是 1 行 3 处的改动，收益覆盖全端；若坚持纯图标，需同时把图标换成带文字徽标的自绘 tabBar（custom），并在使用协议页做一次改名说明。
- J2：`loading` 期间保留顶栏骨架（胶囊用占位灰块），只禁用交互不卸载节点。
- J3：两枚 `top-action` 补 `aria-label="搜索节目"`/`aria-label="睡眠定时器"`，并与 history 页共用同一份工具条组件，统一规范。
- J4：拆分 `errorText` 与 `emptyText` 两个字段；错误态空态里放「网络异常 / 重试」按钮（复用 `.load-retry-btn`），"节目暂未上线"只在成功返回空数组时使用。
- J5：给组件加 `pageLifetimes: { show() { this._refresh() } }`，并在 `_refresh` 内同时更新 `visible/episode/isPlaying`；这是全站浮条失灵的共同根因（与 J100 同源，建议一次改组件、十页同时受益）。
- J6：行内播放键只负责起播（不跳转），进详情统一走整卡 `bindtap`；或将卡片右侧划为"播放区"、左侧为"详情区"，并用一条细分隔线示意。
- J7：绑定 `onOpenQueue` 到首页睡眠图标旁的队列位，其余 5 个死函数删除，避免误导后续维护。
- J8：引导卡按钮改为文字主按钮「去选择偏爱频道」。
- J9：胶囊内加类型前缀文字或图标（资讯/课程/听书），文字与颜色双通道表达。
- J10：游客态在问候卡下方给一条可关闭的提示「登录后可同步收藏与续听进度」，附「暂不登录」选项。

### J-2 底部导航 > 历史（pages/history/history）

**现状描述**：这是功能最完整的列表页——骨架、分级 loading、超时重试、三态筛选（全部/未播/已播）、排序、队列 chip、偏爱空态都有，无障碍标注也做了。但两个交互决策把可用性拉了下来：整行点击与播放键走同一函数、以及失败被渲染成空态。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J11 | 2 | 行容器 `bindtap="onPlay"`（wxml:105）与行内播放 chip `catchtap="onPlay"`（wxml:148）指向同一个处理函数，该函数固定「起播 + navigateTo detail」：本意图是"打开这条历史"的点击（点标题、点封面、点任意空白）一律先发出声音再跳页，公共场合误触即外放，且列表页没有"只看不听"的入口 | apps/miniprogram/pages/history/history.wxml:105,148；apps/miniprogram/pages/history/history.js:320 | 高 | S |
| J12 | 1 | 队列入口形态最差：一枚 `arrows`/列表图标 chip（wxml:40-41，仅 aria-label），全站唯一能把用户带到 `pages/queue/queue` 整页的入口就是它（detail 内是 modal、首页 `onOpenQueue` 未绑定），多数用户不会知道自己有一个"播放队列"页 | apps/miniprogram/pages/history/history.wxml:40-41；apps/miniprogram/pages/index/index.js:737 | 高 | S |
| J13 | 1 | 排序 chip 的方向状态只靠 CSS 类 `.asc` 翻转图标表达（wxml:34-38），无文字、无「最新/最早」标签；筛选 chip 有文字（全部/未播/已播）而排序没有，同一工具条内两套表达强度 | apps/miniprogram/pages/history/history.wxml:34-47 | 中 | XS |
| J14 | 1 | 与「最近播放」页职责重叠、数据源不同：本页取节目库 `fetchHistory`（可作为"我关注的频道都更新了什么"），recent 取 `localData.getHistory` 播放记录；两者名称都指"过去"，用户从底部 tab 进历史后找不到"我昨天听到的那一集"，反而要退回"我的"再点「查看全部 ↗」 | apps/miniprogram/pages/history/history（fetchHistory）；apps/miniprogram/pages/recent/recent（localData.getHistory）；apps/miniprogram/pages/profile/profile.wxml:132 | 高 | M |
| J15 | 5 | 生命周期未等 app 就绪：onLoad/onShow 不 `await getApp().readyPromise`，冷启动直接落在历史 tab 时可能在登录/preload 完成前发起请求，首屏偶发空列表或 401 重试（对照 index 的处理） | apps/miniprogram/pages/history/history.js(onLoad/onShow) | 中 | S |
| J16 | 4 | 加载失败先 toast（`err.message`），随后条件直接把界面渲染成通用空态「暂无历史节目」（wxml:72-74），把"取不到"说成"没有"；这一模式在 search/channels/course/recent/preferred 上重复出现（见 J101） | apps/miniprogram/pages/history/history.wxml:72-74 | 高 | XS |
| J17 | 6 | 频道胶囊缺少首页有的分组标签与角标（无 `isGroupLabel`、无 `pill-badge`），同一份频道数据在两个 tab 上信息量不同，用户切 tab 时以为进了另一个应用 | apps/miniprogram/pages/history/history.wxml:14；apps/miniprogram/pages/index/index.wxml:13-17 | 中 | S |
| J18 | 3 | 行内已播/未播状态、时长、播放次数三处小字与标题同色阶，扫读时难以先定位"哪条还没听"（对比度与字号需实测确认） | apps/miniprogram/pages/history/history.wxml:95-150 | 低 | S |

**优化建议**：
- J11：行容器改绑 `onOpenDetail`（只跳详情、不起播），保留播放 chip 的 `catchtap="onPlayEpisode"`；这是"返回用户续听"路径的核心修复。
- J12：chip 加可见文字「队列 3」；同时在首页落地 J7 的队列入口，并在详情页 modal 底部加「在队列页查看全部」。
- J13：排序 chip 显示当前方向文字（「最新优先」/「最早优先」），点击后 toast 同步反馈。
- J14：二选一——把 recent 并入历史页做成「播过的」二级 tab，或将底部 tab 改名为「更新」并让 recent 承担「历史」语义；不要保留两个都指"过去"的入口。
- J15：onShow 首行 `await getApp().readyPromise` 再取数。
- J16：新增 `error` 分支，空态与错误态分离，错误态带重试。
- J17：把频道胶囊抽成公共组件，分组/角标配置随页面传入。
- J18：未播项加左侧强调条，已播项整体降透明度，形成"先扫状态后读标题"的视觉顺序。

### J-3 底部导航 > 我的（pages/profile/profile）

**现状描述**：登录后是「用户卡 + 收听统计 + 两层 tab（我的课程 / 最近·收藏·频道·下载·偏爱）+ 五个入口项」，结构完整；游客态却只有一张耳机图和一句提示，把包括设置、关于、用户协议、隐私政策在内的全部入口封在 `<block wx:else>` 里。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J19 | 2 | 游客拿不到合规与自助入口：`wx:if="{{!userInfo}}"` 分支只渲染登录卡（wxml:4-13），意见反馈、播放设置、关于我们、用户协议、隐私政策、退出登录全部位于 `wx:else`（15-210）之内；未登录用户既读不到隐私政策，也无法反馈或清缓存，而产品恰恰在首启就要弹隐私授权（`__usePrivacyCheck__: true`） | apps/miniprogram/pages/profile/profile.wxml:4-15,210；apps/miniprogram/app.json:55 | 高 | S |
| J20 | 1 | 重复界面成组出现：「我的课程」有嵌入面板也有 course 页，最近/收藏/频道/下载/偏爱五项都既以 `secondList` 内嵌（wxml:117-133）又以整页存在（recent/favorites/channels/download/preferred-settings），两套渲染逻辑与两份取数代码；面板只显前 N 条、"查看全部"是唯一的升层提示 | apps/miniprogram/pages/profile/profile.wxml:117-145；apps/miniprogram/pages/recent、favorites、channels、download、preferred-settings | 高 | M |
| J21 | 4/6 | 退出登录的语义承诺错误：`onLogout` 只调 `localData.clearByOpenid` + `downloadStore.clearByOpenid` 后 reLaunch（711-719），后端收藏/进度/播放记录全部保留，但隐私政策第 3 条写着「要求删除个人信息（退出登录即可）」——本页与 privacy 页共同构成一个不可兑现的承诺 | apps/miniprogram/pages/profile/profile.js:709-719；apps/miniprogram/pages/privacy/privacy.js:38 | 高 | M |
| J22 | 4 | 「收听分钟」= `Math.round(totalListenDuration / 60)` 的裸数字（354），四舍五入把 30 秒显示成 1、把 29 秒显示成 0；0 与"从未听过"同形，且没有"约"字或分钟以下处理说明 | apps/miniprogram/pages/profile/profile.js:354 | 中 | XS |
| J23 | 2 | 二级面板条目的跳转判据过粗：`item.isChannel ? '/pages/course/course?channelId=' : '/pages/detail/detail?id='`（621,643），资讯类频道在「我的频道」面板里点开会被送进课程页（course 按课程语义渲染章节与订阅），用户点资讯频道看到的却是"第 N 章" | apps/miniprogram/pages/profile/profile.js:621,643 | 中 | S |
| J24 | 3 | 登录按钮是 `btn-icon-only`（wxml:8，仅 aria-label「点击登录」），登录是本页唯一的转化动作，却没有任何文字；头像昵称编辑（213-262）里的取消/保存同样只用图标 aria-label 标注 | apps/miniprogram/pages/profile/profile.wxml:8,259-262 | 高 | XS |
| J25 | 5 | 一级 tab（audiobook）与二级 tab（recent/favorites/…）双层切换状态全存本地（`data.firstTab/secondTab`，js:28 附近），离开本页再回会重置；且二层内容里 downloads/preferred 只渲染"跳转卡"而非真列表，同一 tab 族里三类内容三种呈现（真列表 / 跳转卡 / 空态） | apps/miniprogram/pages/profile/profile.js(data, loadSecondContent)；apps/miniprogram/pages/profile/profile.wxml:117-145 | 中 | S |
| J26 | 6 | `routeMap` + `navigateTo` 失败降级 `reLaunch`（737-757）：reLaunch 会清空页面栈，用户从「关于我们」按返回会直接回到首页而不是"我的"，返回路径被静默改写；这条降级掩盖了真实导航错误且无提示 | apps/miniprogram/pages/profile/profile.js:737-757 | 中 | S |

**优化建议**：
- J19：游客分支下保留完整入口清单，只把需要登录的动作项（统计、列表、退出登录）替换为「登录后查看」占位；隐私政策/用户协议/意见反馈必须对游客可见可点。
- J20：面板只做"预览 + 查看全部"，或反之取消整页、把面板做成可分页的完整视图；两处共用同一份组件，避免继续双实现。
- J21：退出登录弹窗改为明确二择——「仅退出登录（保留云端数据）」/「删除我的数据」；后者需后端提供删除路由（当前 `backend/app/routers/api/` 无任何账号/数据删除接口），并在隐私政策同步措辞。
- J22：不足 1 分钟显示「<1 分钟」，其余用「X 小时 Y 分」或向下取整。
- J23：按 `channel_type` 分流：news → 频道首页/列表，course/audiobook → course 页。
- J24：登录按钮恢复文字「微信一键登录」；编辑弹窗按钮同样加文字，图标仅作辅助。
- J25：tab 状态写入 storage 或 globalData；downloads/preferred 两个 tab 要么渲染真列表要么从二层 tab 组里移除，不要保留点进去只是"跳走"的 tab。
- J26：降级用 `wx.navigateTo` 失败后的 `wx.redirectTo` 或提示「页面栈已满，请返回后再进」，不要 reLaunch；并在 catch 里上报失败原因。

### J-4 节目详情（pages/detail/detail）

**现状描述**：本页是播放控制中枢（轮播、上一集/播放/下一集、进度滑块、6 枚动作 chip、文稿、评论、睡眠定时），能力密度全站最高。核心缺陷是状态反馈缺失：缓冲态字段算了却不渲染、课程语境字段渲染缺失、错误态无重试，加之内嵌队列 modal 与队列整页重复。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J27 | 5 | 缓冲等待态被计算但从未呈现：`isWaiting` 在 js:66 初始化、js:194 随播放器 waiting 事件更新，wxml 里没有任何节点引用它——弱网起播时界面看起来与"正常播放中"完全相同，进度环静止但无「缓冲中」提示，用户只能反复点播放键 | apps/miniprogram/pages/detail/detail.js:66,194；apps/miniprogram/pages/detail/detail.wxml（无 isWaiting 节点） | 高 | S |
| J28 | 4 | 课程语境字段同样算了不显示：`isCourse`/`courseName`/`chapterLabel`（js:80-83,130-133）与 1117 行的分享标题用到，界面却不显示「第 N 章 / 共 M 章 · 课程名」，用户从课程页点进某一章后失去坐标感，不知道自己在整门课的哪个位置 | apps/miniprogram/pages/detail/detail.js:80-83,130-133,1117-1118 | 高 | S |
| J29 | 2 | 队列在这里是页内 modal（wxml:330-367，含清空与"当前项"高亮），在 `pages/queue/queue` 是另一套整页实现，同一功能两份代码两种交互（modal 无法分页/排序、整页也无法删单项），且两边都不给"移除这一首" | apps/miniprogram/pages/detail/detail.wxml:330-367；apps/miniprogram/pages/queue/queue.wxml:8,27 | 高 | M |
| J30 | 3 | 动作区六枚 chip 全部图标化（倍速 chip 只显 `1.5x` 数字、下载 chip 显 `···` 或百分比，wxml:147-187），加上右上角分享/返回首页两枚图标（28-33），本页主操作区零可见文字；`aria-label` 齐全但只服务读屏用户 | apps/miniprogram/pages/detail/detail.wxml:28-33,147-187 | 中 | S |
| J31 | 5 | 下载 chip 的状态语义只靠 aria-label 区分「取消下载 / 已下载点击导出 / 下载到本地」（wxml:171-173），可见区没有对应文字，下载中用户无法判断再点一次是取消还是重试 | apps/miniprogram/pages/detail/detail.wxml:171-173 | 中 | XS |
| J32 | 4 | 详情加载失败态只有一段文本、无「重试」按钮；本页每次进入都重新网络拉取（无缓存兜底），断网从列表点进来只能看到失败文案 | apps/miniprogram/pages/detail/detail.json:2；apps/miniprogram/pages/detail/detail.wxml 错误态 | 高 | S |
| J33 | 6 | 导航标题恒为「节目详情」（detail.json:2），不用 `wx.setNavigationBarTitle` 显示节目名——对比 course 页会动态设标题（course.js:145）；连点几集后页面栈顶部标题完全相同，返回时无法判断层级 | apps/miniprogram/pages/detail/detail.json:2；apps/miniprogram/pages/course/course.js:145 | 中 | XS |
| J34 | 2 | 「查看原文」只做复制链接（`onTapSource` → `copySourceUrl`，规避业务域名白名单），但界面文案对用户呈现为"看原文"的动作，结果是剪贴板里多了一条链接、屏幕上什么都没打开；`pages/webview` 存在却在这条主路径上不使用 | apps/miniprogram/pages/detail/detail.js(onTapSource)；apps/miniprogram/utils/clipboard.js:135 | 中 | S |
| J35 | 5 | `onSeek` 拖动进度即把 `isPlaying` 置 true，未起播状态下拖滑块会显示播放态图标、造成"正在播"的错觉 | apps/miniprogram/pages/detail/detail.js(onSeek) | 中 | XS |
| J36 | 3 | 评论发送按钮用 `::after` 内联 SVG 自绘（detail.wxss:706-711），与站内其余按钮（`<image>` 资源）实现不同，字体放大/深色模式下易错位或缺失（需实测确认）；评论 textarea `maxlength=200` 与后端 `comments.py:32` content max 200 一致，这点做对了 | apps/miniprogram/pages/detail/detail.wxss:706-711；apps/miniprogram/pages/detail/detail.wxml:275；backend/app/routers/api/comments.py:32 | 低 | S |
| J37 | 1 | `episode-card` 与 `audio-player` 两个组件既不在 `app.json` 全局 usingComponents、也不在 detail.json 注册，本页仅复用了 `.card` 类名（wxml:79）；本页事实上内联了一整套播放器，与"组件化播放器"并存，是队列/浮条状态不同源的结构原因之一 | apps/miniprogram/app.json:56-58；apps/miniprogram/components/episode-card、components/audio-player | 中 | M |

**优化建议**：
- J27：在播放键/进度条区域渲染 `isWaiting` → 「缓冲中…」+ 轻微呼吸动画；超过 8s 升级为「网络较慢，点击重试」。
- J28：卡片副标题加「{{chapterLabel}} · {{courseName}}」，并把课程名做成可点回课程页的面包屑。
- J29：统一收敛到 `pages/queue`，detail 的 modal 只做"前 5 首预览 + 查看全部"；两处都补「左滑删除本首」。
- J30/J31：chip 恢复 4 字内文字（倍速/收藏/队列/文稿/下载/定时），下载中显示「取消」，已下载显示「导出」。
- J32：错误态加 `load-retry-btn`（复用 app.wxss 样式），并对已下载章节走本地文件优先渲染。
- J33：加载成功后 `wx.setNavigationBarTitle({ title: ep.title })`。
- J34：文案改为「复制原文链接」，或按白名单情况分策略：可打开时用 webview，不可打开时按钮文案直接写「复制链接」。
- J35：seek 仅在已起播时同步 `isPlaying`。
- J36：改用 `<image>` 或文字按钮，与站内实现统一。
- J37：二选一——正式注册并复用组件，或删除两个死组件目录，避免后续改动落在无人使用的代码上。

### J-5 搜索（pages/search/search）

**现状描述**：搜索框 + 三档类型筛选 + 历史标签 + 分页结果，交互骨架对。问题在于反馈链：首屏搜索期间空白、失败被说成无结果、键盘"搜索"键形同虚设、关键词长度不设上限。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J38 | 5 | 首次搜索期间屏幕空白：空态条件 `!loading && keyword && results.length===0`（wxml:50）在加载中为假、结果未达为 0 时列表也不渲染，唯一的 loading 文本藏在底部 `load-more`（84-85），用户按下搜索后对着空页面等待 | apps/miniprogram/pages/search/search.wxml:50,84-85 | 高 | S |
| J39 | 4 | 失败被表述为无结果：`doSearch` catch 里只 toast `err.message \|\| '搜索失败'`（js:117，api.js 抛的是「网络异常/请求超时/登录失败，部分功能不可用」这类固定串），toast 一闪后页面落到「未找到相关节目」空态，用户被引导去怀疑自己的关键词 | apps/miniprogram/pages/search/search.js:117；apps/miniprogram/pages/search/search.wxml:50-52；apps/miniprogram/services/api.js | 高 | S |
| J40 | 2 | `confirm-type="search"` 却没有 `bindconfirm`/`bindsearch`（wxml:10-11 只绑 `bindinput`，js 只有 `onInput`），键盘上的「搜索」按钮不触发立即检索，仍要等 300ms 防抖（js:16）；对"打完字就按键"的用户，按钮给了承诺却不兑现 | apps/miniprogram/pages/search/search.wxml:5-12；apps/miniprogram/pages/search/search.js:16,74-86 | 中 | XS |
| J41 | 4/6 | 关键词无长度上限：后端 `/episodes/search` 要求 `keyword` `max_length=64`（backend/app/routers/api/episodes.py:56），输入框无 `maxlength`，粘贴长句直接 422，前端呈现为一次无意义的"搜索失败" | apps/miniprogram/pages/search/search.wxml:5-12；backend/app/routers/api/episodes.py:56 | 中 | XS |
| J42 | 1 | 类型口径跨页不一致：本页筛选是「全部/资讯/课程」，把 `audiobook` 与 `course` 折进"课程"；首页/偏爱的口径是 news/audiobook/course 三类，用户在同一份内容集上被给了两套分类语言 | apps/miniprogram/pages/search/search.js(FILTER_OPTIONS)；apps/miniprogram/utils/skin.js | 中 | S |
| J43 | 3 | 清空搜索历史是纯图标 trash（wxml:33-34），无二次确认、无「已清空 + 撤销」；下载页、队列页的同类破坏性图标也是同样处理（见 J57、J73） | apps/miniprogram/pages/search/search.wxml:33-34 | 中 | XS |
| J44 | 4 | 无结果空态只有一句「未找到相关节目」（wxml:50-52），不提示换关键词、不提示切「全部」类型、不给去频道页的出口——搜索是低容错功能，改写建议是标配 | apps/miniprogram/pages/search/search.wxml:50-52 | 中 | XS |

**优化建议**：
- J38：搜索中显示 2-3 张结果骨架卡；`hasSearched && results.length===0` 才显示空态。
- J39：把 `error` 状态独立渲染为「搜索失败 · 重试」块，与空态分离；toast 文案做映射（超时→「网络较慢，请重试」）。
- J40：加 `bindconfirm="onConfirmSearch"`，清除防抖立即检索并收起键盘。
- J41：input 加 `maxlength="64"`，并在超限粘贴时 toast「关键词最多 64 字」。
- J42：统一为「全部 / 资讯 / 课程 / 听书」四档，或在 chip 下加一行说明「课程含听书」。
- J43：清空前 `wx.showModal` 确认，或改为可撤销（本地暂存上一次历史）。
- J44：空态给三个建议动作：切全部类型、换更短关键词、浏览全部频道。

### J-6 我的频道（pages/channels/channels）

**现状描述**：全站频道清单 + 订阅文字按钮 + 下拉刷新 + 骨架超时重试，实现本身规矩。但页面名不副实、点资讯频道"没反应"、失败伪装空态三条凑在一起，使本页成为最容易被误判为"坏了"的一页。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J45 | 1 | 页名与内容不符：`navigationBarTitleText` 为「我的频道」（channels.json:2），列出的却是全部频道及订阅态（wxml:61 已订阅/订阅）——"我的"暗示已订阅集合，用户找不到"只看我的"的开关，而那功能实际住在偏爱设置页 | apps/miniprogram/pages/channels/channels.json:2；apps/miniprogram/pages/channels/channels.wxml:61 | 高 | XS |
| J46 | 2 | 点资讯频道在用户视角"没反应"：`onTapChannel` 对 news 分支只写 `app.globalData.currentChannelId = id` 后 `switchTab` 到首页（js:105-106），而首页从不读取 `currentChannelId` 来切换选中胶囊/滚动定位，结果用户跳回首页看到的还是原样，且无任何 toast 说明"已切换频道" | apps/miniprogram/pages/channels/channels.js:105-106；apps/miniprogram/pages/index/index.js（未读取 currentChannelId） | 高 | S |
| J47 | 5 | 失败先 toast「加载失败」（js:47）再落到「暂无可用频道」空态（wxml:21-22），该空态无重试按钮（重试只在骨架超时块，wxml:16），一次性失败即被固化为"没有频道" | apps/miniprogram/pages/channels/channels.js:47；apps/miniprogram/pages/channels/channels.wxml:16,21-22 | 高 | XS |
| J48 | 1 | 「订阅」（本页）与「偏爱」（preferred-settings）两个概念在界面上没有任何区分说明，卡片布局几乎一致，用户会以为自己已经设置成功、回首页却发现排序没变 | apps/miniprogram/pages/channels/channels.wxml:40-62；apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:20-40 | 高 | M |
| J49 | 1/6 | 频道不按类型分组、无更新角标，与首页胶囊的 `isGroupLabel`/`pill-badge` 呈现不同（同一份数据两种 IA），本页也没有首页那种分组标题可供扫读 | apps/miniprogram/pages/channels/channels.wxml:40-62；apps/miniprogram/pages/index/index.wxml:13-17 | 中 | S |
| J50 | 6 | 订阅按钮在本页是文字按钮（wxml:61「订阅/已订阅」），课程页同一动作却是纯图标 check/checks（course.wxml:36-41）；两页语义相同、控件强度不同 | apps/miniprogram/pages/channels/channels.wxml:61；apps/miniprogram/pages/course/course.wxml:36-41 | 中 | S |

**优化建议**：
- J45：改名「全部频道」，或顶部加「全部 / 已订阅」两个 chip 让页名成立。
- J46：首页 onShow 读取并消费 `currentChannelId`（切换选中胶囊、横向滚动定位、刷新列表），并 toast「已切到《X》」；不消费就删掉这行赋值。
- J47：空态与错误态分离，错误态内嵌重试；同时保留上次成功列表做兜底展示。
- J48：本页顶部加一句定义（「订阅决定节目会不会出现在你的列表；偏爱决定首页与历史的排序」），并把两页做成同一页的两个 tab。
- J49/J50：分组与控件形态与首页、课程页对齐，订阅统一为带文字的状态按钮。

### J-7 课程主页（pages/course/course）

**现状描述**：课程元信息 + 动态导航标题 + 继续/从头播放 + 下载整门课程条 + 章节列表，是回访用户的主战场。`wx.setNavigationBarTitle` 用得对（js:145）。三处硬缺陷：装饰性可点错觉、50 章静默截断、无 onShow 导致状态陈旧。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J51 | 5 | 章节数被硬截到 50：`fetchHistory(1, 50, channelId, 'asc')`（js:165）只取首页 50 条且不做后续分页，长课程（听书常见 100+ 章）在此页只显示前 50 章；更糟的是下载条的 `12/30` 计数用的是 totalCount（js:66-68），列表与计数口径不一致，用户数得出"少了 70 章" | apps/miniprogram/pages/course/course.js:165；apps/miniprogram/pages/course/course.wxml:66-68 | 高 | S |
| J52 | 3 | 每章右侧的 `chapter-play` 小图标（wxml:117）是纯装饰、未绑任何事件，真实点击区在父容器 `onTapChapter`（88）；图标暗示"点这里播放"，点了却走父级详情逻辑，是典型的可点错觉 | apps/miniprogram/pages/course/course.wxml:88,117 | 中 | XS |
| J53 | 5 | 没有 `onShow`：从详情返回后各章的播放进度、下载状态、当前播放高亮全部停留在进入前的快照，用户听完一章回到课程页看到的仍是"未播"，与详情页的进度记忆脱节 | apps/miniprogram/pages/course/course.js（无 onShow；对照 js:145） | 中 | S |
| J54 | 4 | 「下载整门课程」条只在 `batchDownloading` 时显示百分比、否则显示 `12/30`（wxml:66-68），没有「取消」「重试失败项」文字，也没有失败汇总；批量中断后用户不知道下一步该点哪里 | apps/miniprogram/pages/course/course.wxml:66-68 | 中 | S |
| J55 | 3 | 首屏三个主操作（订阅、继续学习、从头播放）全是 `btn-icon-only`（wxml:36-41,54-59），加上"下载整门课程"条，本页顶部操作带完全无文字；「继续学习」与「从头播放」两个相反语义只靠图标差异区分 | apps/miniprogram/pages/course/course.wxml:36-41,54-59 | 中 | XS |
| J56 | 6 | `course.json` 配了 `backgroundTextStyle: "dark"` 却没开 `enablePullDownRefresh`（json:2-3），下拉三圆点样式挂在死配置上；章节列表又无分页加载态，长列表底部仅靠 onReachBottom 取数 | apps/miniprogram/pages/course/course.json:2-3 | 中 | XS |
| J57 | 2 | 资讯类频道被 profile 面板误导向本页（J23）时，本页仍按课程语义渲染"章节/订阅/下载整门课程"，用户点的是资讯却进了课程壳，语义冲突在本页显形 | apps/miniprogram/pages/profile/profile.js:643 | 中 | S |

**优化建议**：
- J51：改为分页循环拉全量（或以 `totalCount` 驱动循环），并在章节数 > 已加载数时显示「继续加载更多章节」。
- J52：给装饰图标去掉（或 `aria-hidden` + 无点击暗示样式），或真的绑上"直接播放本章"的 `catchtap`。
- J53：加 `onShow` 做增量刷新（至少同步当前播放章节与下载态）。
- J54：条内加「取消」与结果态「N 章失败 · 重试」，进度显示「已存 12/30」。
- J55：三枚按钮补文字（订阅 / 继续第 12 章 / 从头播放）。
- J56：要么开 `enablePullDownRefresh`（课程详情+章节需重新取数），要么删掉死配置。
- J57：入口分流按 `channel_type` 走（见 J23），并对 news 频道做降级渲染。

### J-8 我的下载（pages/download/download）

**现状描述**：按频道分组的离线文件清单 + 占用统计 + 三级删除（全部/频道/单项），支持导出分享。问题集中在文案字面量、离线承诺的真实性和破坏性操作无分级。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J58 | 4 | 空态文案里出现字面量反斜杠 n：`在课程页点击「下载整门课程」或单章「下载」，\n即可离线收听～`——WXML 文本节点不做转义解析，用户屏幕上真的会显示 `\n` | apps/miniprogram/pages/download/download.wxml:49 | 中 | XS |
| J59 | 4 | 「已下载」不等于能离线播：条目点击是跳 `detail?id=&channelId=`（wxml:30），而详情页每次进入都重新网络拉取详情（J32），断网时点已下载的章节直接落到加载失败；「关于」页却把能力宣传成「下载后无网络也能听」（about.js:34） | apps/miniprogram/pages/download/download.wxml:30；apps/miniprogram/pages/detail/detail.js；apps/miniprogram/pages/about/about.js:34 | 高 | M |
| J60 | 6 | 三枚删除按钮同形同色（全部清空 trash、频道清空 trash、单项删除 x，wxml:11-22,38），"清空 30 章"与"删 1 章"视觉权重一致；除整表清空外均无二次确认 | apps/miniprogram/pages/download/download.wxml:11-22,38 | 高 | S |
| J61 | 5 | 无加载失败态与重试：读下载索引异常时直接落到空态（wxml:46-49），用户以为下载全丢了；本页也未 `enablePullDownRefresh`，无手动刷新手段 | apps/miniprogram/pages/download/download.json:2；apps/miniprogram/pages/download/download.wxml:46-49 | 中 | S |
| J62 | 1 | 与播放队列页职责易混（两者都是"清单+计数+清空图标"），download 是本地文件、queue 是播放序列，但两页都没有一句界定用途的说明；「占用 {{totalSizeLabel}}」与设置页「{{cacheSize}}」是两个口径（后者不含 USER_DATA_PATH 音频，见 J79） | apps/miniprogram/pages/download/download.wxml:8；apps/miniprogram/pages/queue/queue.wxml:14-17 | 中 | XS |

**优化建议**：
- J58：把 `\n` 换成真正的换行（拆两个 `<text>` 或用 `\n` 于 js 数据字段）。
- J59：已下载条目优先本地文件起播（详情走本地缓存/索引渲染），并在条目上标注「离线可听」；否则把宣传文案改成「下载后可导出到本地播放器收听」。
- J60：单项删除降为文字「删除」+ 行内确认；"清空全部/清空频道"用红色危险样式并二次确认列出影响条数。
- J61：错误态与空态分离 + 重试；开启下拉刷新。
- J62：页顶加一行说明，并统一"占用"口径（把下载目录计入设置页缓存统计，或明确分开写「音频文件」与「本地缓存」）。

### J-9 偏爱频道设置（pages/preferred-settings/preferred-settings）

**现状描述**：首启引导与普通入口共用一页（`onSkip` 确实存在于 js:113），卡片勾选 + 底部操作栏 + 保存计数角标，逻辑基本完整。缺陷集中在未登录死路和底部栏零文字。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J63 | 2 | 未登录时保存只会 toast「请先登录后再设置偏爱」（js:onSave），页面不出现登录按钮、不跳 profile、不解释为什么必须登录；从首启引导进来的新用户在此被硬卡住，唯一出路是自行摸索底部 tab | apps/miniprogram/pages/preferred-settings/preferred-settings.js(onSave)；apps/miniprogram/app.js(needsPreferredOnboarding) | 高 | S |
| J64 | 3 | 底部栏三枚按钮全部图标化：全选/全不选（checks/x）、暂不设置、保存（✓+数量角标），wxml:40-57 只给 aria-label；这是引导流程的最终决策界面，"保存"与"暂不"两个相反动作只有图标差异 | apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:40-57 | 高 | XS |
| J65 | 5 | 加载失败 toast 后显示「暂无可用频道」空态且无重试（与 J47 同型），引导首屏若网络不佳会直接呈现"没有频道可选" | apps/miniprogram/pages/preferred-settings/preferred-settings.js；apps/miniprogram/pages/preferred-settings/preferred-settings.wxml 空态 | 中 | XS |
| J66 | 1 | 与 channels 页构成重复（同一份频道清单、两套勾选语义），本页又不自述"偏爱会影响首页与历史的排序"，用户保存后回到首页看到的变化无法归因；两处勾选状态是否互相同步也不可见 | apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:20-40；apps/miniprogram/pages/channels/channels.wxml:40-62 | 高 | M |
| J67 | 6 | `enablePullDownRefresh: false`（json:3）本身合理，但同页底部栏与常驻浮条的位置避让只写在本页 wxss（wxss:78 注释显式与 floating-player 错开），这个避让没有下沉到公共样式，其他带底部栏的页面存在遮挡风险（需实测确认） | apps/miniprogram/pages/preferred-settings/preferred-settings.json:3；apps/miniprogram/pages/preferred-settings/preferred-settings.wxss:78 | 中 | S |

**优化建议**：
- J63：未登录时把保存按钮替换为「登录后保存（微信一键登录）」并就地触发 `wx.login` 流程；或允许本地暂存选择、登录后自动补同步并提示。
- J64：三枚恢复文字：「全选」「暂不设置」「保存（已选 5）」。
- J65：错误态与空态分离 + 重试按钮。
- J66：与 channels 合并成「频道」一页两 tab（订阅 / 偏爱），顶部说明两者差异；引导页沿用同一组件。
- J67：把底部栏避让安全区与浮条的样式抽成公共类，全站统一。

### J-10 最近播放（pages/recent/recent）

**现状描述**：本地播放记录列表 + 分页 + 下拉刷新，只有 4 条显著问题，其中两条与"和 tab 里的历史页重复"直接相关。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J68 | 1 | 与底部「历史」tab 构成同名职责重复且数据源不同（本页 `localData.getHistory` 播放记录，历史 tab `fetchHistory` 节目库）；入口只有 profile 面板的「查看全部 ↗」，从底部 tab 进来的用户不会知道这里还有一个更贴近"我听到哪了"的列表 | apps/miniprogram/pages/recent/recent.js(loadRecent)；apps/miniprogram/pages/profile/profile.wxml:132；apps/miniprogram/app.json:40 | 高 | M |
| J69 | 5 | `onShow` 每次都 `loadRecent(true)` 重新加载并重置分页，从详情返回即丢失滚动位置与已翻页数据，用户"听完一集回去找刚才那集"需重新下滑 | apps/miniprogram/pages/recent/recent.js(onShow) | 高 | S |
| J70 | 3 | 无骨架/无加载态：空态条件 `!loading && list.length === 0`（wxml:4）使加载中呈现为空白页，随后列表突然出现；与 favorites 的 `loading-mask` 文本、history 的骨架形成同族页三套首屏呈现 | apps/miniprogram/pages/recent/recent.wxml:4 | 中 | S |
| J71 | 4 | 读取失败 toast 后落到「还没有播放记录」空态（wxml:4-7），"记录读不出来"被说成"你还没听过" | apps/miniprogram/pages/recent/recent.js；apps/miniprogram/pages/recent/recent.wxml:4-7 | 中 | XS |

**优化建议**：
- J68：把本页作为"历史" tab 的「播过的」视图（见 J14），或把底部 tab 改名「更新」以消除语义冲突。
- J69：`onShow` 只在 `needsRefresh` 标记或首屏时刷新，刷新保留 scrollTop 与已加载页数。
- J70：复用 `skeleton-wrap`；`loading && length===0` 时渲染骨架。
- J71：错误态独立 + 重试。

### J-11 我的收藏（pages/favorites/favorites）

**现状描述**：收藏列表 + 下拉刷新 + 长按取消 + 不可用项降透明。三个体验断点都在"用户看不见规则"上。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J72 | 2 | 取消收藏的唯一手势是长按：规则只写在页面底部一行提示里（wxml:50-52），列表项右侧无「…」菜单、无滑动删除；首次进入的用户点条目只会被送进详情，找不到移除入口 | apps/miniprogram/pages/favorites/favorites.wxml:50-52 | 高 | S |
| J73 | 5 | 已下架节目只整体降透明度（`.item-unavailable`，wxml:21），没有「已下架」文字标签，点击行为也未说明；用户会误判为加载失败或界面卡死 | apps/miniprogram/pages/favorites/favorites.wxml:21 | 高 | XS |
| J74 | 3 | 加载态是遮罩里的纯文本「加载中」（wxml:4 loading-mask），与 history 的骨架、recent 的空白并存，同族列表页三套首屏语言 | apps/miniprogram/pages/favorites/favorites.wxml:4 | 中 | S |
| J75 | 1 | 收藏语义在三处各有一套呈现：本页整页、profile「收藏」内嵌面板（js 直接 `getFavorites`）、详情页/列表页的收藏 chip 反馈，过滤与排序口径不同，用户在 A 处取消收藏后 B 处顺序变化无法预期 | apps/miniprogram/pages/favorites/favorites.js(getFavorites)；apps/miniprogram/pages/profile/profile.wxml:117-145；apps/miniprogram/pages/detail/detail.wxml:152-154 | 中 | M |

**优化建议**：
- J72：条目右侧加「取消收藏」图标按钮（带文字 tooltip）或左滑删除；底部提示保留作为辅助。
- J73：加「已下架」灰底标签，并把点击行为改为 toast 说明原因。
- J74：统一骨架屏。
- J75：收藏列表组件化，面板与整页共用同一份排序/过滤逻辑。

### J-12 播放队列（pages/queue/queue）

**现状描述**：整页队列清单 + 清空图标 + 当前项高亮，本地数据、无下拉刷新。它最大的问题是可达性与"和详情 modal 双实现"。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J76 | 1 | 整页事实上是孤儿页：唯一进入路径是历史页一枚无文字的列表图标 chip（history.wxml:40-41），首页 `onOpenQueue`（index.js:737）没有绑定到任何元素，详情页用的是自己的内嵌 modal（detail.wxml:330-367）；浮动播放器也不通向本页，多数用户从未到过队列页 | apps/miniprogram/pages/history/history.wxml:40-41；apps/miniprogram/pages/index/index.js:737；apps/miniprogram/pages/detail/detail.wxml:330-367 | 高 | S |
| J77 | 6 | 与详情 modal 双实现，且两处都不能删除单项、不能拖拽排序，只提供"整表清空"（queue.wxml:8；detail.wxml:336）——队列最基本的两项管理动作缺失 | apps/miniprogram/pages/queue/queue.wxml:8；apps/miniprogram/pages/detail/detail.wxml:336 | 高 | M |
| J78 | 4 | 空态说明与真实规则不符：「在历史列表中点击节目即可加入队列」（wxml:17），而实际历史整行点击是"起播+跳详情"（history.wxml:105，J11），加队列的机制在别处；用户按提示操作后队列仍为空 | apps/miniprogram/pages/queue/queue.wxml:17；apps/miniprogram/pages/history/history.wxml:105 | 中 | S |
| J79 | 5 | 清空按钮纯图标（wxml:7-8，注释明写「T00384：清空改为图标按钮」），无二次确认，一键把整条听程抹掉；当前播放项之外的顺序也无文字说明 | apps/miniprogram/pages/queue/queue.wxml:7-8 | 中 | XS |

**优化建议**：
- J76：把入口落地三处——首页队列 chip、详情 modal 底部「查看完整队列」、浮条长按菜单；或彻底删除整页、只保留 modal。
- J77：两处统一实现，补「左滑移除本首」与拖拽排序（或上移/下移按钮），点击项即播。
- J78：文案改成真实规则（如「在节目详情点「队列」加入；或在历史页长按节目」），并在空态直接放一个「去历史挑几集」按钮。
- J79：恢复「清空」文字并加二次确认（显示将清除的条数）。

### J-13 播放设置（pages/settings/settings）

**现状描述**：播放/通知/存储/关于四组，含倍速 picker、自动连播、仅 WiFi、无缝过渡、清除缓存、检查更新。本页两条"文案与实现对不上"的记录是全端风险最高的两条。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J80 | 4 | 「清除缓存」的确认文案撒谎：`content: '将清除本地缓存（保留登录信息与设置），确定继续？'`（js:147），而 `KEEP_KEYS` 只保 `news_token`/`news_user`/播放设置（js:24），循环删除其余所有 key（js:152-157），实际被抹掉的包括收藏、播放进度、播放历史、偏爱频道、下载索引、上次播放项、搜索历史、反馈历史——用户以为清了图片缓存，结果收藏清空、续听进度归零 | apps/miniprogram/pages/settings/settings.js:24,147,152-157 | 高 | S |
| J81 | 5 | 「检查更新」的反馈不可信：无论是否真的检测到更新，都在 2000ms 后固定 toast「已是最新版本」（js:199），不等 `onCheckForUpdate` 回调结果；弱网下真有新版本也先报"已最新"，用户会以为功能坏了或版本永远不变 | apps/miniprogram/pages/settings/settings.js:173-199 | 高 | S |
| J82 | 4 | 「占用 {{cacheSize}}」只等于 `wx.getStorageInfoSync().currentSize + ' KB'`（js:135），不含 `services/download.js` 落在 USER_DATA_PATH 的音频文件；本页"存储管理"显示的占用与下载页「占用 {{totalSizeLabel}}」是两个口径，且真实大头（音频）恰好没被计入 | apps/miniprogram/pages/settings/settings.js:135；apps/miniprogram/pages/download/download.wxml:8 | 高 | S |
| J83 | 3 | 破坏性的「清除缓存」与普通设置项完全同形（wxml:39-41 list-item + chevron），危险只体现在弹窗 confirmColor 上；进入本页前用户无法预期"缓存"二字包含收藏 | apps/miniprogram/pages/settings/settings.wxml:39-41 | 中 | XS |
| J84 | 2 | 通知开关与系统权限的关系未说明：页面把"通知设置"呈现为可关的能力，实际关闭站内开关并不等于微信服务通知授权状态，用户预期错位；开关无状态解释文案 | apps/miniprogram/pages/settings/settings.js（通知设置）；apps/miniprogram/app.js（scene 1014 通知路由） | 中 | S |
| J85 | 6 | 本页不挂 `floating-player`（挂载清单只有 index/history/profile/search/channels/course/download/favorites/recent/queue），播放中进设置后浮条消失、无法暂停，与"设置播放参数时正在听"这一高频场景冲突；本页也无安全区底部避让（app.wxss 未定义全局 safe-area，需实测确认底部项是否被.home indicator 遮挡） | apps/miniprogram/app.json:56-58；各页 wxml 末行；apps/miniprogram/app.wxss | 中 | S |

**优化建议**：
- J80：把弹窗文案改成实话，并把"缓存"拆成两项——「清理网络缓存（不影响收藏）」与「清空我的数据（含收藏、进度、历史，不可恢复）」；`KEEP_KEYS` 随之扩到包含用户数据键。
- J81：把 toast 移到 `onCheckForUpdate` 回调里按 `hasUpdate` 分支给出，超时/失败给「暂时无法检查更新，请稍后再试」；不要固定 2s 假反馈。
- J82：占用统计计入下载目录，或明确分成「本地缓存 X KB」与「下载音频 Y MB」两行。
- J83：清除类项目左缘加红色图标，文案改「清除本地数据」。
- J84：开关下加一行「关闭后仍可能收到微信服务通知，可在微信-设置中管理」。
- J85：全站把 floating-player 提升为根级常驻（或至少覆盖 settings/webview），并在 app.wxss 定义统一的 `--safe-bottom` 令牌。

### J-14 意见反馈（pages/feedback/feedback）

**现状描述**：本地反馈历史卡 + 正文（10-500 字，带实时计数）+ 选填联系方式（50 字）+ 提交按钮。与后端限制完全对齐（`backend/app/routers/api/feedbacks.py:28-30` MIN 10 / MAX 500 / 联系方式 50），这是全端做得到位的一处。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J86 | 5 | 提交成功后 800ms 自动 `navigateBack`（js），用户来不及确认"发出去了吗"，也看不到刚才那条被记进了本页的历史卡；反馈无单号、无处理时限、无查看回复的路径（后端未向用户端开放状态查询），承诺感缺失 | apps/miniprogram/pages/feedback/feedback.js（成功后 navigateBack）；apps/miniprogram/pages/feedback/feedback.wxml:4 | 中 | S |
| J87 | 1 | 「意见反馈」入口位于登录后的 profile 清单（profile.wxml:15-210 的 else 分支），游客既无法反馈首启隐私弹窗问题、也无法反馈播放故障，与 J19 同一处断裂 | apps/miniprogram/pages/profile/profile.wxml:15-210 | 高 | S |
| J88 | 3 | 提交中只靠 `disabled` + aria-label「提交中」（wxml:62-68），按钮可见区无 loading 指示；失败后是否有输入保留、是否重复提交都无说明 | apps/miniprogram/pages/feedback/feedback.wxml:62-68 | 中 | XS |
| J89 | 4 | 计数条显示 `{{content.length}}/{{maxLength}}`（wxml:44），下限"至少 10 字"只写在 placeholder 里（38），不足 10 字时提交按钮不置灰，用户按下去才知道不合规；上限 500 的截断也无说明 | apps/miniprogram/pages/feedback/feedback.wxml:38-44；backend/app/routers/api/feedbacks.py:28-30 | 低 | XS |

**优化建议**：
- J86：成功后保留在本页 1.5s、显示「已提交，我们会在 N 个工作日内查看」并追加到历史卡顶部；把自动返回改成显式「返回」按钮。
- J87：入口对游客可见（见 J19），或在隐私弹窗与错误态里各挂一个「反馈」出口。
- J88：按钮内显示 spinner 或文案切「提交中…」，失败时明确「内容已保留，可直接重试」。
- J89：字数不足时按钮置灰并就地提示「还需要 X 个字」。

### J-15 关于我们（pages/about/about）

**现状描述**：品牌头 + 版本号 + 功能清单 + 联系邮箱 + 版权脚注，静态页实现干净。两处与后端/实现的一致性问题和一处调试后门。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J90 | 4 | 功能清单宣称「离线收听 · 下载后无网络也能听」，而下载条目点击需先经详情页网络取数（J59）；宣传与可实现行为不一致，断网场景正是这一宣传的承诺场景 | apps/miniprogram/pages/about/about.js:34；apps/miniprogram/pages/download/download.wxml:30 | 高 | S |
| J91 | 4 | 版本号来源不唯一：本页 `version \|\| '1.0.0'`（js:50）兜底，而 app.js 的默认 VERSION 是 '1.3.0'，两处兜底常量不同；`getEnvVersion` 失败时用户看到「1.0.0」，与真实发布版本无关，也无从判断是否落后 | apps/miniprogram/pages/about/about.js:24,50；apps/miniprogram/app.js(VERSION) | 中 | S |
| J92 | 2 | 连点版本号 5 次弹出「配置后端地址」编辑框（js:61-70 + utils/server-discovery），生产包保留了调试后门；普通用户（尤其小孩/老人）连点后得到一个看不懂的输入框与「保存」，且改错会导致全站请求失败 | apps/miniprogram/pages/about/about.js:61-70 | 中 | S |
| J93 | 6 | 联系邮箱只有图标复制按钮（走 utils/clipboard 隐私包装），无邮件客户端拉起、无模板；与意见反馈构成两条互不相通的联系路径，用户不知道该走哪条 | apps/miniprogram/pages/about/about.js（copyText） | 低 | S |
| J94 | 3 | 本页不挂浮条（见 J85 清单），从"我的"进来即失去正在播放的可见性；页尾脚注「© 2026 {{appName}} · 用耳朵听新闻」与隐私/协议页脚注风格是否一致需实测确认 | apps/miniprogram/pages/about/about.js:48-50；app.json:56-58 | 低 | XS |

**优化建议**：
- J90：按 J59 修复后保留宣传；否则改为「下载管理 · 支持导出到本地播放器」。
- J91：单一版本源（app.js 的 VERSION 或后端环境版本），兜底常量统一，并显示构建日期与"检查更新"入口。
- J92：后门改为仅开发/体验版可用（用 `wx.getAccountInfoSync().miniProgram.envVersion !== 'release'` 守卫）。
- J93：加「复制邮箱」文字与「去意见反馈」次按钮，并说明两条路径的适用场景。

### J-16 用户协议（pages/agreement/agreement）

**现状描述**：顶部「最后更新：2026 年 7 月」+ 7 个静态 section 纯文本，实现极简。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J95 | 4 | 生效版本不可验证：日期硬编码在 wxml（agreement.wxml:5），无版本号、无变更摘要、无"上一条协议"入口，用户无法确认自己同意的是哪一版；隐私政策用同一句式（privacy 页"最后更新"），两页日期是否同步无人保证 | apps/miniprogram/pages/agreement/agreement.wxml:5 | 中 | XS |
| J96 | 6 | 长纯文本无目录/锚点/折叠（wxml:8-10 逐段平铺），手机上需长滚；协议内提及"退出登录/删除数据"等权利时不能跳到隐私政策或设置页，两个法律文本互相孤立 | apps/miniprogram/pages/agreement/agreement.wxml:8-10 | 低 | S |
| J97 | 3 | 无返回上级的显式入口（依赖系统返回），与 about/privacy 三页之间也没有底部导航互链；纯文本行距与字号对长文阅读的适配需实测确认 | apps/miniprogram/pages/agreement/agreement.wxss | 低 | XS |

**优化建议**：
- J95：日期旁边加「v1.3.0」与"查看更新说明"，日期由构建注入而非硬编码，两页共用同一常量。
- J96：顶部加目录 chip（点击滚动到锚点），关键权利条目做可点击内链到 privacy/settings。
- J97：底部加固定栏「我已阅读」/「返回关于」，与 privacy 页做成两 tab。

### J-17 隐私政策（pages/privacy/privacy）

**现状描述**：8 个静态 section。本页含全端风险最高的一条文案缺陷。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J98 | 4 | 用户权利条款写了不可兑现的承诺：「您有权：…3) 要求删除个人信息（退出登录即可）」（privacy.js:38），而退出登录只清本地（profile.js:711-712 的 `clearByOpenid` 两个调用），服务端 openid 关联的收藏/进度/播放记录全部保留，且 `backend/app/routers/api/` 下不存在任何账号注销或数据删除接口——按指引操作的用户实际没删掉任何个人信息 | apps/miniprogram/pages/privacy/privacy.js:38；apps/miniprogram/pages/profile/profile.js:709-719；backend/app/routers/api/（无删除路由） | 高 | M |
| J99 | 4/6 | 同一句里的第 4 条也不成立：「关闭某些数据收集（在设置中操作）」，但设置页只有播放/通知/存储三组（settings.wxml:39-52），没有任何数据收集开关，也没有埋点上报开关（utils/tracker 始终上报）；用户在隐私页读到的控制项在设置页找不到 | apps/miniprogram/pages/privacy/privacy.js:38；apps/miniprogram/pages/settings/settings.wxml:39-52；apps/miniprogram/utils/tracker.js | 高 | S |
| J100 | 1 | 隐私页与协议页、关于页无互链，也没有"联系我们行使权利"的入口（联系路径在 about 页的复制邮箱）；行使权利的真实路径（发邮件）在隐私文本里没有指向 | apps/miniprogram/pages/privacy/privacy.js；apps/miniprogram/pages/about/about.js | 中 | XS |
| J101 | 5 | 本页与 agreement 页的 wxss 为空（0 行），沿用全局样式；长纯文本块的段间距、可点击链接色等表现需实测确认，两页排版是否一致也依赖全局 | apps/miniprogram/pages/privacy/privacy.wxss；apps/miniprogram/pages/agreement/agreement.wxss | 低 | XS |

**优化建议**：
- J98：把第 3 条改为实话（「要求删除个人信息：请在意见反馈中提出，或联系客服邮箱，我们将在 X 个工作日内处理」），并在设置页加「删除我的数据」入口；若需"退出即删"，须由后端补一个按 openid 清除的接口再挂到退出弹窗。
- J99：要么在设置页补齐真实开关（数据统计/个性化推荐），要么删掉这条权利描述。
- J100：底部加「行使权利：去意见反馈」按钮，并与协议页做成两 tab 互链。
- J101：两页共用同一套文本排版样式（字号、段距、链接色、目录）。

### J-18 查看原文（pages/webview/webview）

**现状描述**：`web-view` 容器 + 错误兜底块（说明 + URL 展示 + 复制/返回两个图标按钮）+ 5 秒看门狗；`error` 为 true 时不渲染 web-view 以避免微信原生拦截页，这个防御是对的。问题是它进不了正常路径，且失败态反馈最弱。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J102 | 1 | 正常浏览路径里不可达：唯一进入点是 `utils/clipboard.js:135` 拼的 `/pages/webview/webview?url=…&fallback=1`，也就是"复制失败之后的兜底"；详情页的"原文"动作刻意不走它（J34），而本页导航标题却叫「查看原文」（webview.json:2），用户真按标题预期找原文时它是缺席的 | apps/miniprogram/utils/clipboard.js:135；apps/miniprogram/pages/webview/webview.json:2 | 中 | S |
| J103 | 3 | 导航栏配色与全站冲突：app.json 全局 `navigationBarBackgroundColor: #FFFFFF` + 黑字（22-27），本页 json 覆写成深蓝底白字（webview.json:2-3），从白底详情页跳进来时顶部颜色突变；错误态整页变白底文字块，落差更大（实际观感需实测确认） | apps/miniprogram/app.json:22-27；apps/miniprogram/pages/webview/webview.json:2-3 | 中 | XS |
| J104 | 4 | 兜底文案是推测句而非结论句：「链接可能未加入业务域名白名单，请复制到浏览器打开」（wxml:11），把平台配置问题表述成不确定的"可能"，用户不知道该等一会儿再试还是上报；本页也没有「反馈此问题」出口（唯一相关入口还在登录后，见 J87） | apps/miniprogram/pages/webview/webview.wxml:9-12 | 中 | XS |
| J105 | 6 | 失败场景最需要明确指令，两个按钮却被去成纯图标（wxml:14-18，注释明写「T00384：图标即按钮，去掉"复制链接/返回"文案」，仅留 aria-label）；URL 原文整行展示（12）在小屏上大概率溢出或截断，用户无法核对复制到了哪条链接（需实测确认） | apps/miniprogram/pages/webview/webview.wxml:12-18 | 高 | XS |

**优化建议**：
- J102：详情页对已配置白名单的域名直接走本页打开，未配置的才降级复制；把"复制"与"打开"做成两个可见选项，而不是让用户猜。
- J103：导航栏配色回归全局白底黑字，错误态与加载态用同一底色。
- J104：文案改确定句 + 出路：「该站点不在小程序可打开范围内，请复制链接到浏览器打开。若希望我们支持，可点此反馈来源站点」，并附「重试」按钮。
- J105：恢复「复制链接」「返回」文字（失败兜底属于低频高风险场景，图标可辨识性最低），URL 做折行或尾部省略 + 「已复制完整链接」确认 toast。

### J-附 跨页组件 / 服务 / 生命周期

**现状描述**：全局 `usingComponents` 只注册 floating-player；`services/api.js` 有 TTL 缓存、同请求去重、401 刷新重试、10s 超时与一次网络重试，`utils/loading.js` 有 600/2000/8000ms 分级加载，工程质量整体不错。以下条目是全端共性问题的归因，逐页清单中的同源项都指向这里。

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| J106 | 5 | 全站"错误伪装成空态"模式：`api.js` 失败时抛出固定串（「网络异常」「请求超时」「登录失败，部分功能不可用」），各页统一做法是 toast 一句然后落到"暂无 ××"空态——history/search/channels/course/recent/favorites/preferred/download 八页同型（J16、J39、J47、J61、J65、J71），用户学会不了"空"和"坏"的区别 | apps/miniprogram/services/api.js（`_rawRequest` fail 分支）；apps/miniprogram/pages/history/history.wxml:72-74；apps/miniprogram/pages/search/search.js:117；apps/miniprogram/pages/channels/channels.js:47 | 高 | M |
| J107 | 2 | 后台播放与页面显示不同步的根因在组件缺 `show` 钩子：`services/audio.js` 用订阅扇出补偿 `getBackgroundAudioManager` 的覆盖式回调，但订阅回调只更新 `isPlaying`/进度角，从不重算 `visible`/`episode`，且没有任何页面在显示时主动取一次播放器快照（J5、J53、J85 同源） | apps/miniprogram/components/floating-player/floating-player.js:21-37,45-58；apps/miniprogram/pages/history/history.js:79 | 高 | M |
| J108 | 1 | 死组件留在仓库：`components/episode-card`、`components/audio-player` 未被任何页面 json 或全局 usingComponents 注册，样式类名却还在详情页被复用（detail.wxml:79），改动无处生效、评审容易误判 | apps/miniprogram/app.json:56-58；apps/miniprogram/components/episode-card、apps/miniprogram/components/audio-player | 中 | XS |
| J109 | 3 | 无深色模式适配：`app.json` 未声明 `darkmode`、项目内无 `theme.json`，app.wxss 的令牌是硬编码色值（`--accent:#3f6c8f` 等），深色环境下白底卡与黑字导航的对比需实测确认，读屏文本可能整体反色后失真 | apps/miniprogram/app.json:22-27；apps/miniprogram/app.wxss | 中 | M |
| J110 | 3 | 安全区适配不统一：全局无 `env(safe-area-inset-bottom)` 约定，只有 preferred-settings 在页内 wxss 单独处理与浮条的避让（wxss:78），带底部操作栏或浮条的页面在全面屏上存在遮挡风险（需实测确认）；列表底部最后一项与 tabBar 的间距同理 | apps/miniprogram/app.wxss；apps/miniprogram/pages/preferred-settings/preferred-settings.wxss:78 | 中 | S |
| J111 | 2 | 隐私弹窗只在 profile/detail/about 三页挂载 `privacy-modal`，用户在首页首屏或搜索页首次触发受保护 API 时，`app.js checkPrivacy` 走 `_privacyUI` 槽为空 → 降级 `wx.showModal`，只剩一段系统弹窗文字、无《用户隐私保护指引》可点开的链接，与自定义弹窗能力不对等 | apps/miniprogram/app.js（checkPrivacy）；apps/miniprogram/components/privacy-modal（挂载清单） | 中 | S |
| J112 | 6 | 「T00384 图标即按钮」的去文案改造被逐页无差别套用（代码注释可查，如 queue.wxml:7、webview.wxml:14、preferred-settings.wxml:40、course.wxml:54），结果是全端在导航（tabBar）、主操作区（详情页 6 chip）、终局决策（偏爱底栏）、失败兜底（webview）四类最需要文字的场景同时失字；而 aria-label 普遍存在，说明改造考虑了读屏却牺牲了 sighted 用户的可发现性 | apps/miniprogram/app.json:33-49；apps/miniprogram/pages/detail/detail.wxml:147-187；apps/miniprogram/pages/queue/queue.wxml:7-8；apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:40-57 | 高 | S |

**优化建议**：
- J106：在 `empty-state` 组件内增加 `type="error"`（图标 + 「加载失败」+ 重试按钮 + 保留上次数据），各页只需把 catch 里的 `error` 写入 data；一次改造八页受益。
- J107：floating-player 增加 `pageLifetimes.show → _refresh()`，`_refresh` 同时重算 visible/episode/isPlaying；并让需要本地同步的页面（course/detail/queue）走同一快照函数。
- J108：注册复用或删除，二者择一，别留中间态。
- J109：声明 `darkmode` + `theme.json`，令牌改为 light/dark 双值。
- J110：app.wxss 提供 `.page-bottom-safe` 公共类（含 `env(safe-area-inset-bottom)` + 浮条高度变量），列表页统一引用。
- J111：把 privacy-modal 挂到 app 级容器或在所有调用受保护 API 的页面预挂载，保证首启即能点开《用户隐私保护指引》。
- J112：定一条可执行的规范并回扫全站——"导航项、破坏性操作、终局决策按钮必须带文字；仅列表行内重复出现的次要动作可用图标 + aria-label"。按此至少恢复 tabBar `text`、详情页 6 chip、偏爱底栏、webview 兜底按钮四处。

### 双视角走查结论

**新用户（首次进入 / 游客）**：纯图标 tabBar 让其在三个 tab 之间靠猜（J1）；首启引导进入偏爱设置后若未登录，保存只给一句 toast、无出路（J63）；回到首页偏爱引导卡又是图标按钮（J8）；游客态"我的"页连隐私政策都读不到（J19），而产品恰恰在首启要求隐私授权（J111）；若想反馈，入口在登录之后（J87）。新用户主路径上有 4 处需要"猜图标"或"撞墙"。

**回访用户（续听 / 历史 / 收藏）**：从详情听完返回首页，浮条不出现，暂停/续播入口消失（J5、J107）；到底部"历史"tab 想找回刚听的那集，整行点击会先外放再跳页（J11），而"我实际播过的"在另一个 recent 页且每次返回都被重置滚动（J14、J69）；课程用户回课程页看到章节仍是"未播"（J53），长课程还可能根本看不到 50 章之后的内容（J51）；想清理空间时"清除缓存"会把收藏和进度一起抹掉（J80）。回访用户的核心诉求（找到上次听到的、继续听、不误删）目前三条都有障碍。

### 统计

| 优先级 | 条数 | 占比 |
|---|---|---|
| 高 | 44 | 39% |
| 中 | 59 | 53% |
| 低 | 9 | 8% |
| 合计 | 112 | 100% |

成本分布：XS 39 条（多为补 `text`/`aria-label`、改文案与状态分支）、S 58 条、M 15 条（重复界面收敛、队列双实现合一、数据删除路由、深色模式、错误态组件化）。
建议先做的三件低成本高收益改动：`app.json` 三个 tab 补 `text`（J1，XS）、floating-player 加 `pageLifetimes.show`（J5/J107，S）、设置页把"清除缓存"的文案与保留键改对（J80，S）。

---

## 11. 维护工具（数据库维护 / 系统清理 / 参数计算器）+ 帮助（帮助文档 / 关于）

> 走查范围：参数计算器 `/tools/calculator`、数据库维护 `/db-admin`、系统清理 `/maintenance`、帮助文档 `/help`、关于 `/about`（含各页弹窗/dry-run 预览/确认框/空态）。
> 菜单权威名取自 `apps/admin-web/src/router/index.js` meta.title：参数计算器(router/index.js:183)、数据库维护(:189)、系统清理(:195)、帮助文档(:201)、关于(:207)；关联项「AI 服务」(:147)。
> 全站按钮统一走 `apps/admin-web/src/components/IconButton.vue`：`label` 只落到 aria-label 与 Tooltip，**按钮本体仅渲染 icon + 可选 `inline-text`**（IconButton.vue:24-28, 93）。凡未传 `inline-text` 的按钮，界面上看不到名字——本切片多处高危动作正属于此类，已在具体条目中标注。
> 双视角结论：首次使用者在「按钮无名、锁定模型无说明、预览/执行同按钮」三处最容易误操作；高频运维的主要摩擦在「令牌手输、跨页选中丢失、图标按钮靠 hover 分辨、清理历史无处可查」。
> 视觉维度均据模板/style 推断，不能静态断言处已写明「需实测确认」。

---

### M-1 维护工具 > 参数计算器（路由 /tools/calculator，文件 apps/admin-web/src/views/tools/ParamCalculator.vue）

**现状描述**：三卡片（时长/总字数/语速倍率）本地联算，固定其中一项由另两项推导，基础语速 210 字/分硬编码为页面常量（:221）；底部 4 个预设方案，唯一出口动作是右上角「应用到 AI 配置」（走 query 传参，纯前端计算，无接口调用）。
**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| M1 | 2/5 | 唯一出口动作「应用到 AI 配置」未传 `inline-text`，界面上只是一枚纸飞机图标；按钮名与「将当前三参数带入 AI 配置页」全在 hover Tooltip 里。首次使用者无法确认这点下去会发生什么 | apps/admin-web/src/views/tools/ParamCalculator.vue:4-10；apps/admin-web/src/components/IconButton.vue:24-28 | 中 | XS |
| M2 | 2/5 | 「应用到 AI 配置」的有效区间与目标页不一致且**静默夹取**：本页允许时长 60–1800s、倍率 0.5–2.5x，而 AIConfig 接收时把 `duration` clamp 到 180–1200s、把倍率换算成 `edge_rate` 百分串（2.5x→"+150%"，超出其滑杆 -50~100 范围），但 toast 仍报「已从参数计算器同步：目标时长、语速倍率」，用户以为按自己填的值带过去了 | ParamCalculator.vue:60-62,161-162,306-314；apps/admin-web/src/views/ai/AIConfig.vue:1546-1559,406-413 | 高 | S |
| M4 | 4 | 「计算中」Tag 文案错误：该状态表示「本项被锁定、由另外两项推导得出，当前只读」，不是正在计算；本页无任何异步计算，用 `type="warning"` 的「计算中」会被读成任务在跑。真正含义直到下方 result-label「由其他参数计算得出」才说明，两处措辞不呼应 | ParamCalculator.vue:38-44,69,88-94,119,138-144,170 | 中 | XS |
| M5 | 2 | 锁定模型无说明、无解锁：已锁定的卡片把「锁定此项」按钮换成 Tag，卡片上不再有任何按钮，用户找不到「取消锁定」的路径，只能猜「去锁另一项」；页面从头到尾没有一句「同一时刻只有一项是推导出来的」 | ParamCalculator.vue:45-53,88-104,138-154,280-284 | 中 | S |
| M6 | 5 | 夹取后的不自洽零提示：`recalculate()` 用 `Math.max/min` 夹到区间边界（如 10000 字 + 0.5x 需 5714s，被夹成 1800s），三个 result-value 会同时显示「10000 字 / 30分0秒 / 0.50x」这组互相矛盾的值，界面无任何「超出可算范围，结果已截断」告警 | ParamCalculator.vue:241-257,67-72,117-122,168-173 | 中 | S |
| M7 | 4 | 单位混用：时长 `el-input-number` 本体只显示裸数字 600（无「秒」后缀），顶部公式写「时长(秒)」，预设 Tooltip 又写「5分钟 · 1x · 1050字」；同一个量在一页内出现秒与分钟两套单位且输入框无单位锚点 | ParamCalculator.vue:20,58-66,195 | 中 | S |
| M8 | 6/3 | 预设卡片的关键区分信息不可见：`desc`（时长·倍率·字数）只进 Tooltip，卡片本体只有名字 + 图标；模板下方为「两行卡片」写的 `.preset-label`/`.preset-hint` 样式在 IconButton 内部并不存在（它只输出 `.icon-btn__text`），属死样式；`.preset-btn` 的 padding/height 依赖 attr 经 el-tooltip fallthrough，是否生效需实测确认 | ParamCalculator.vue:189-199,402-411；IconButton.vue:24-28,31-50 | 中 | S |
| M9 | 3 | 「完整节目」与「快节奏精华」时长同为 600s，卡片可见信息（名字+图标）不足以表达差异来自倍率 1.0x/1.5x；需实测确认（受 M8 影响） | ParamCalculator.vue:234-238 | 低 | XS |
| M10 | 5 | 结果不可复用：三个 result-value 是纯 `span`，无「复制本项」「复制三参数」入口；且「应用」只带 `duration`+`rate`，不带字数（AIConfig 侧靠 `target_duration_sec×210×rate/60` 反算），运营想留存手算结果只能截图 | ParamCalculator.vue:67-72,117-122,168-173,306-314；AIConfig.vue:1145-1147 | 低 | S |
| M11 | 1 | 按钮文案「应用到 AI 配置」与权威菜单名「AI 服务」不一致，导航里没有「AI 配置」这一项；跳转后落在多 Tab 页，未定位到对应 Tab，用户到达后还要自己找 | ParamCalculator.vue:6；router/index.js:147 | 低 | XS |
| M12 | 6 | 210 字/分基线在两个页面各自硬编码（本页 `BASE_WORDS_PER_MIN`，AIConfig 的 `calculatedWords` 直接写 210），注释声称「与 AIConfig 中公式保持一致」但无任何机制保证；基线若变，本页会整体性误导且界面不显示基线来源/校验时间 | ParamCalculator.vue:220-221,20；AIConfig.vue:1145-1147 | 中 | S |
| M13 | 5 | 「应用」写入的是未保存值，却被目标页的草稿机制作持久化：AIConfig `onMounted` 顺序是 `enableDraft()/enableDraftTts()` 在前、`applyCalculatorParams()` 在后，因此这次改动会进草稿；用户下次直接进「AI 服务」时草稿把时长/语速又恢复出来，看上去像「我没点应用怎么数值变了」 | AIConfig.vue:1576-1585 | 中 | M |

**优化建议**：
1. （M2，最高优先）在 `goToAiConfig()` 发送前做区间预校验：把 `duration` 限定到 180–1200、`rate` 限定到 0.5–2.0；越界时用 `ElMessageBox` 明确「AI 服务页仅支持 3–20 分钟 / 0.5–2.0x，是否按边界应用」，并在卡片上给时长/倍率输入框补 min/max 提示文案。落点 `ParamCalculator.vue:306-314,60-62,159-167`；同步把 AIConfig `applyCalculatorParams`（`AIConfig.vue:1540-1570`）改为「clamp 后如实告知」，把 toast 文案改成「目标时长已按 AI 服务上限取 1200s」。
2. （M4/M5）把 `计算中` Tag 改为 `推导值（只读）`，result-label 与之统一用同一词；在锁定卡片上保留一颗「改为此项推导」的按钮（点击等价 `lockParam`），并在 intro-alert 补一句「同一时刻只有一项由另外两项推导」。落点 `ParamCalculator.vue:38-44,88-94,138-144,13-22`。
3. （M6）`recalculate()` 返回是否发生夹取，命中边界时在对应卡片 result-line 追加 `el-alert`/文字「结果已按上限截断，此组合不自洽」；落点 `ParamCalculator.vue:241-257,67-72`。
4. （M7/M8/M10）给三输入框补单位：时长用 `el-input-number` 的 formatter（后缀「秒」）并在 result-line 保留「X分Y秒」双显示；预设改为自绘卡片（名字 + 第二行「5 分钟 · 1.0x · 1050 字」常驻可见），删除 `ParamCalculator.vue:402-411` 的死样式；三行 result 各加一枚「复制」IconButton（复用 `About.vue:429-437` 的 clipboard 降级写法）。
5. （M1/M11）主操作按钮补 `inline-text="应用到 AI 服务"`，并把文案对齐权威菜单名；跳转时带上目标 Tab（`AIConfig.vue` 的 `handleTabChange` 语义）以便直达 LLM/TTS 区域。落点 `ParamCalculator.vue:4-10,306-314`。
6. （M12）把 210 提到单一常量模块（如 `src/constants/speech.js`）由两页共引，并在 intro-alert 标注「基线 210 字/分（项目常量，非实测标定）」。
7. （M13）在 `AIConfig.vue` 中让 `applyCalculatorParams()` 之后显式 `commitDraft` 或干脆把应用结果标记为「未保存的临时值」不进草稿；至少 toast 里说明「不会自动保存，离开页面可能残留在草稿」。
8. 空态：本页无列表/无数据场景，**未发现显著体验缺陷**；替代优化——加一条本地会话内的「上次应用记录（时间 + 三参数）」，便于运维回溯手算依据。

---

### M-2 维护工具 > 数据库维护 > 主界面（表浏览 / 行编辑 / 搜索排序 / 导入导出）（路由 /db-admin，文件 apps/admin-web/src/views/maintenance/DatabaseAdmin.vue + src/api/dbAdmin.js）

**现状描述**：左侧白名单 16 表（中文 label + 行数徽标），右侧工具栏 + 动态列数据表 + 分页，支持行 CRUD、CSV/JSON 导入导出、表结构弹窗、审计日志弹窗；删除类动作统一走 `CONFIRM_DELETE` 令牌。后端为 `backend/app/routers/admin/db_admin.py` + `backend/app/services/db_admin_service.py`。
**问题清单**：

| # | 维度 | 问题（具体到界面元素/交互节点） | 证据（相对路径:行号） | 优先级 | 成本 |
|---|---|---|---|---|---|
| M14 | 2/5 | **脱敏值回写覆盖真实数据（不可逆）**：`list_rows` 会把 `password_hash`/`token`/`secret` 以及 `ai_config.config_value` 显示为 `***`，而编辑弹窗用 `formData = {...row}` 预填、`editableColumns` 含全部列且只禁用主键，保存时 `update_row` 只按「非主键 + 非空」过滤、不排除敏感列 → 只要对 `admin_user`/`ai_config` 任一行点「确认」（哪怕只改了简介），就会把 `password_hash` 或 API Key 写成字面量 `***`，随即该运营账号无法登录 / 该服务商密钥作废，且界面提示「更新成功」 | DatabaseAdmin.vue:200-213,496-504,506-520；backend/app/services/db_admin_service.py:86-116,129-140,298-319；backend/app/models/admin_user.py:27；backend/app/models/ai_config.py:36 | 高 | S |
| M16 | 5 | 后端 `update_row` 把 `None` 与空字符串一律过滤掉（「空字符串视为不更新」），前端输入框却是 `clearable`：用户清空一个文本字段后保存 → 该列被静默丢弃、数据库保持旧值，同时前端弹「更新成功」，形成「改了没生效但说成功」；置空在 UI 上永远做不到 | DatabaseAdmin.vue:208-211,506-520；db_admin_service.py:306-310 | 高 | M |
| M17 | 5 | 编辑保存的 PK 由前端从「当前行」取（`editingPkValue`），若该行已被他人删除，后端 `affected=0` 仍返回成功结构，前端不看 `affected` 直接「更新成功」，用户以为写进去了 | DatabaseAdmin.vue:501-513,562-576；db_admin_service.py:317-319 | 中 | XS |
| M18 | 2 | 「必填」只有文字提示 `(必填)`，`el-form` 无任何 rules/校验；新增时必填列留空 → 空值被后端过滤掉 → 抛 SQLite 原始约束错误，用户看到的是驱动级报错文本；`create_row` 还会在「全部字段为空」时抛「无有效字段」，与界面上的字段级提示不成对 | DatabaseAdmin.vue:198-213,506-520；db_admin_service.py:270-296 | 中 | S |
| M20 | 2 | 时间戳列（`created_at`/`updated_at`）在编辑弹窗里是普通可编辑文本，预填的是后端 `isoformat()` 出来的 `2026-10-17T22:01:00`；保存会把它作为字符串原样回写，与库中原有的空格分隔格式不同，而「保留天数」类清理与排序都直接对该列做字符串/时间比较——界面对「这列不建议改」零提示 | DatabaseAdmin.vue:200-213,666-678；db_admin_service.py:118-126,306-309；backend/app/services/maintenance_service.py:370-386 | 高 | S |
| M21 | 4/6 | 批量删除的「选中条数」进不了眼睛：`:label="\`批量删除 (${selectedRows.length})\`"` 未配 `inline-text`，按钮本体只是一枚垃圾桶图标，数字只出现在 Tooltip/aria-label；对不可逆动作，选中数量是决策依据，应在按钮上常驻可见 | DatabaseAdmin.vue:58-66；IconButton.vue:24-28,93 | 中 | XS |
| M22 | 2 | 工具栏 7 颗按钮全部图标化且无 `inline-text`（新增/批量删除/导出/导入/表结构/审计日志/刷新），语义靠 hover 分辨；其中 View=表结构、Document=审计日志、Upload=导入、Download=导出属反直觉搭配，且危险动作「批量删除」与非危险动作「删除行」共用同一枚 Delete 图标，视觉权重无差别 | DatabaseAdmin.vue:51-111,149-169 | 中 | S |
| M23 | 4/5 | 导出静默截断：后端固定 `LIMIT DB_ADMIN_MAX_PAGE_SIZE*10`（=10000 行）且与搜索/排序/分页无关，前端按钮 desc 写「导出当前表数据」、成功后只报「导出成功」，用户在 16 表里挑大表导出时拿到的是一份被截断且不受筛选影响的文件，毫无线索 | DatabaseAdmin.vue:67-83,580-590；db_admin_service.py:406-430 | 中 | S |
| M24 | 2 | 搜索框 placeholder 只有「搜索...」，后端仅对 TEXT/VARCHAR/CHAR 列做 `LIKE`；输入数字 ID（如 workflow 主键为 VARCHAR 时可命中，`play_log.id` 为 INT 时永远搜不到）返回空表，界面无「仅搜索文本列」提示，用户误判为「数据不存在」 | DatabaseAdmin.vue:39-48,467-487；db_admin_service.py:219-235 | 中 | XS |
| M25 | 2 | 排序只对含 INT/DATE 的列开放（`:sortable` 条件），文本列列头没有排序箭头且无解释；运维按标题/状态排查时无法排序 | DatabaseAdmin.vue:127-134 | 低 | XS |
| M26 | 2 | 跨页选中丢失：`el-table` 未设 `row-key`/`reserve-selection`，翻页或改每页条数后已选行清空，但「批量删除 (N)」按钮文案与确认弹窗只描述当前选中；同时无「全选当前筛选结果 N 行」入口，逐页勾选是清数据的唯一路径 | DatabaseAdmin.vue:116-133,172-184,543-560 | 中 | M |
| M27 | 4/6 | 列头直接铺英文原始列名（`script_id`、`finished_at`），与左侧中文表名（「稿件」「工作流」）风格断裂；`(必填)` 前的 `col.type` 提示用 SQL 类型串（`VARCHAR(256)`）当 placeholder，对非工程背景运营无信息量 | DatabaseAdmin.vue:127-142,207,212,659-664；db_admin_service.py:181-191 | 低 | M |
| M28 | 5 | 所有失败只 `console.warn`：`loadTables/loadSchema/loadRows/submitForm/confirmDelete/handleImport/handleExport/loadAuditLogs` 的 catch 里没有任何界面态；虽然 axios 拦截器会 toast 一次（`api/index.js:30-72`），但页面自身停留在「空/旧数据」上，无「加载失败，重试」的可点区域 | DatabaseAdmin.vue:435-487,506-520,562-590,634-641 | 中 | S |
| M29 | 6 | 前后端契约：删除/批量删除/导入的令牌是前端硬编码常量 `CONFIRM_DELETE`（`dbAdmin.js:10`），后端读 `settings.DB_ADMIN_CONFIRM_TOKEN`，而 `config.py:492` 默认为空串、`.env.example:183` 明确要求「替换为随机字符串」——只要部署照 example 做，删除/批量删除/导入三类动作**必然失败**，报错文案仅「confirm_token 校验失败」，用户会以为是自己的拼写问题 | src/api/dbAdmin.js:10,43-56；backend/app/routers/admin/db_admin.py:30,61-70；backend/app/config.py:492；backend/.env.example:183 | 高 | M |
| M30 | 5 | 危险动作前的「输入 CONFIRM_DELETE」是把答案写在题目里（`:334` 文案原样公布令牌、`:335` placeholder 同样），既不校验拼写来源也不增加真实防护，却给每次不可逆删除加固定手输成本；且令牌输入框与后端的令牌比对是同一个静态串，脚本调用可绕过全部界面确认 | DatabaseAdmin.vue:334-335,343-351 | 中 | M |

**优化建议**：
1. （M14，先做）编辑弹窗对 `col.sensitive === true` 的列改为**只读展示 + 「不修改该字段」**：不渲染输入控件，并在 `submitForm` 前把这些 key 从 payload 中 `delete`；后端同步在 `update_row`/`import_rows` 的 `valid_cols` 里剔除 `SENSITIVE_COLUMNS` 与 `ai_config.config_value`，形成双保险。落点 `DatabaseAdmin.vue:200-213,506-520`、`db_admin_service.py:298-319,434-481`。
2. （M16/M17）把「置空」显式化：每个可空字段右侧加「清空此列」开关，勾选后发送 `null`；后端区分「字段缺省=不更新」与「显式 null=置空」（当前 `v is not None` 逻辑已支持 null，只需前端不再把清空成 `''`）。同时前端读取 `result.affected`，`affected===0` 时提示「未找到该行（可能已被删除），请刷新」。
3. （M18/M20）给弹窗加 `rules`（非空列必填、数值列类型校验），提交前拦下；对 `*_at`/`created_at`/`updated_at` 列改为只读并在字段旁标「由数据库维护，不建议手改」，如需改则用 `el-date-picker` 而非裸文本。
4. （M21/M22）危险/主操作按钮补 `inline-text`：「批量删除 N」「新增」「导入」「预览清理/立即执行」等；给「批量删除」换成与单行删除不同的图标（如 `DeleteFilled`）并在 `selectedRows.length===0` 时把 Tooltip 改成「先在左侧勾选行」而不是只禁用。落点 `DatabaseAdmin.vue:51-111,149-169`。
5. （M23）导出前用当前 `search/order_by/limit` 组装 query（后端 `export_rows` 需支持透传筛选），并在 desc 与结果 toast 里写明条数与上限：「导出 N 行（上限 10000，超出部分未导出）」；命中上限时改为 `ElMessageBox.warning`。落点 `DatabaseAdmin.vue:67-83,580-590`、`db_admin_service.py:406-430`。
6. （M24/M25/M26）搜索 placeholder 改「搜索文本列…」，并在返回 0 行且关键词像数字时提示「数字主键请点列头排序定位」；给全部列开 `sortable="custom"`（后端已有标识符白名单校验，`db_admin_service.py:237-243`）；`el-table` 加 `row-key` + `reserve-selection` 实现跨页累积选中，并新增「全选本次筛选结果（N 行，共 M 页）」。
7. （M28）页面级错误态：`loadTables/loadRows` 失败时渲染 `el-result` + 「重试」按钮，而不只是 toast；表格区保留上次数值并加「数据未刷新」灰条。
8. （M29/M30）新增 `GET /db-admin/confirm-token`（返回当前部署是否已配置令牌 + 一个一次性 nonce），前端删除时把 nonce 发给后端做常量时间比对；界面文案改为「请输入 DELETE 以确认」（与后端配置的密钥解耦）。短期内至少：令牌缺失时把删除按钮禁用并在 Tooltip 说明「服务器未配置危险操作令牌」。落点 `src/api/dbAdmin.js:10,43-56`、`db_admin.py:61-70`、`DatabaseAdmin.vue:334-351`。

---

### M-3 维护工具 > 数据库维护 > 删除确认弹窗（级联预览 + 令牌）（DatabaseAdmin.vue:314-352）

**现状描述**：单行/批量删除都会先打 `cascade-preview`，弹窗显示「将删除 X 表的 N 行记录」+ 关联影响列表（cascade/set_null 两类图标 + 行数），下方要求手输 `CONFIRM_DELETE` 才能激活红色「确认删除」按钮。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M31 | 5/2 | **预览失败即静默降级为「零信息确认」**：`cascadePreview` 抛错时 `deleteCascade = null`，而整块预览在 `v-if="deleteCascade"` 下，弹窗只剩分割线 + 令牌输入框 + 可点确认；对不可逆删除，用户看不到删什么/多少条/有无级联，仍能一路确认到底（失败只 `console.warn`） | DatabaseAdmin.vue:316-332,533-540,553-559 | 高 | S |
| M32 | 4 | 确认文案三处缺项：① 用英文表名 `deleteTarget`（`admin_user`）而非左栏已给的中文名；② 通篇没有「此操作不可恢复 / 无回收站 / 建议先备份」（对比系统清理页至少有一句「不可逆」）；③ 后端返回的 `total_affected`（级联合计行数）被前端丢弃，用户看不到「主表 N + 级联 M = 共 N+M 行」 | DatabaseAdmin.vue:317,334-335；db_admin.py:197-207；db_admin_service.py:371-402 | 高 | S |
| M33 | 4/1 | **预览口径与真实删除口径不一致**：预览/级联都只走 `TABLE_RELATIONS` 声明表，删 `workflow` 只提示并清理 `workflow_step`，而 `workflow` 的真实下游（script/review/episode/play_log/play_progress/comment/favorite/notification_log/auto_review_stat）既不预览也不清理——同一份数据在「系统清理」里是按全链级联删的；文档式承诺「工作流步骤将一并删除」给运维造成「删干净了」的错觉，实际留下悬空数据 | db_admin_service.py:62-82,561-587；maintenance_service.py:388-496；Help.vue:309-336 | 高 | M |
| M34 | 5 | 关联影响里 `count === 0` 的条目与有影响的条目同权重展示（"审核记录将一并删除 0 行"），真正的风险被 0 行噪声稀释；`set_null`（会破坏节目与稿件的关联，属不可逆语义变更）与 `cascade` 只靠图标颜色区分，文案没有「置空后不可恢复」 | DatabaseAdmin.vue:318-330；db_admin_service.py:392-400 | 中 | S |
| M35 | 6 | 弹窗标题「确认删除」没有携带危险等级视觉锚点（无 danger 边框/无表名徽标），且底部按钮顺序为「取消 / 确认删除」，与全站「次要左、主要右」一致 ✓ 但 `type="danger"` 按钮在令牌未匹配时只是变灰，没有就近说明「为什么不能点」 | DatabaseAdmin.vue:315,343-351,870-880 | 低 | XS |
| M36 | 2 | 令牌输入无 `@keyup.enter` 提交、`clearable` 但每次都需重新手输；批量删除与单行删除走同一套手输流程，高频运维时每行 4 次击键起步 | DatabaseAdmin.vue:335,562-576 | 中 | XS |
| M37 | 5 | 删除成功后仅 `已删除 N 行`，N 取的是**请求数** `deleteIds.length` 而非后端 `affected`/`cascade` 实际值（后端两者都返回了），存在「说删了 50 行、实际删了 47 行」而用户无从察觉 | DatabaseAdmin.vue:562-576；db_admin_service.py:321-336,338-367 | 高 | S |
| M38 | 3 | 级联图标色 `#FF9AA2`/`#FFE5B4` 为硬编码，未走主题变量（同页其余配色都来自 `variables.scss`），主题变更时会脱节；需实测确认 | DatabaseAdmin.vue:321-324,692-881 | 低 | XS |

**优化建议**：
1. （M31）预览失败时改为**阻断**：`deleteCascade === null` 时显示 `el-alert type="error"`「无法获取级联影响，已禁止执行删除」+「重新获取」按钮，并把确认按钮 `disabled`；至少要在弹窗里显示「影响范围未知」而不是留白。落点 `DatabaseAdmin.vue:316-332,533-559`。
2. （M32）标题改「不可恢复删除：{{ currentTableLabel }}（{{ deleteIds.length }} 行）」，正文补三行清单：主表行数 / 级联删除合计（用后端 `total_affected`）/「SQLite 无回收站，删除后只能通过备份恢复」；并给出「先去 备份 页导出」的跳转（`backend/app/routers/admin/backup.py` 已存在）。
3. （M33）把 `TABLE_RELATIONS` 与清理服务的级联口径对齐（推荐抽出共用 `WORKFLOW_DOWNSTREAM` 清单），或至少在预览里加一条「未声明的下游数据（如稿件/节目/播放日志）不会随之删除」提示；落点 `db_admin_service.py:62-82`、`maintenance_service.py:388-496`。
4. （M34）过滤 `count===0` 的条目并合并成一句「其余关联无影响」；`set_null` 文案升级为「将把 {table}.{fk} 置空（该关联无法通过本界面恢复）」。
5. （M37）toast 用后端返回：`已删除 ${res.affected} 行` + 有级联时追加「，级联 ${cascadeTotal} 行」；`res.affected !== deleteIds.length` 时用 warning 色提示差异。落点 `DatabaseAdmin.vue:562-576`。
6. （M36）令牌输入框加 `@keyup.enter="confirmDelete"`（仅当已匹配时）；同一会话内连续删除允许沿用已输入的令牌（会话级标记 + 界面显示「本会话已确认危险操作」），把每行的固定手输成本降为一次。

---

### M-4 维护工具 > 数据库维护 > 新增/编辑行弹窗 + 表结构弹窗（DatabaseAdmin.vue:191-248）

**现状描述**：单弹窗双模式（`formMode` create/edit），按反射出的列动态渲染 `el-input-number/el-switch/el-input`，编辑态禁用主键；另有「表结构」弹窗展示列名/类型/主键/可空/敏感/默认值。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M39 | 2 | 主键在**新增**态可编辑、**编辑**态禁用（`:disabled="formMode==='edit' && col.primary_key"`）✓ 方向正确；但新增自增表时主键输入框同样开放且无「留空=自增」说明，`create_row` 又会把空值丢弃，用户填 0 或误填旧 ID 会直接撞唯一约束，报错是驱动原文 | DatabaseAdmin.vue:208,490-494,506-520；db_admin_service.py:270-296 | 中 | S |
| M40 | 6 | 组件映射过粗：`getFormComponent` 只看类型串子串，`DATETIME/TIMESTAMP` 落回 `el-input`（裸文本可改时间戳，见 M20）、枚举/状态列（`status`、`action`）也是裸文本，可写出后端不接受的值；`BOOL` 用 `el-switch` 但 `el-switch` 拿不到 `active-value/inactive-value`，存 0/1 时开关态与库值语义需实测确认 | DatabaseAdmin.vue:666-678,204-211 | 中 | M |
| M41 | 6 | `type="primary"` 与 `clearable` 被无条件透传给动态组件：`el-input-number`/`el-switch` 不认 `clearable`/`type`，属无效属性（控制台可能有 unknown-attr 警告），且 `clearable` 恰好是 M16「清空被丢弃」的诱因之一 | DatabaseAdmin.vue:204-211 | 低 | XS |
| M42 | 4 | placeholder 用 `col.type`（`VARCHAR(256)`）当占位符，label 也是英文列名；`(必填)` 后缀与真实后端约束来源不同步（后端按反射出的 `nullable`，前端同源于反射 ✓，但无长度/范围约束提示，超 256 字照样提交） | DatabaseAdmin.vue:198-213 | 中 | S |
| M43 | 5 | 弹窗关闭即丢内容且无挽留：`@close="formDialogVisible = false"`，用户填了 15 个字段误触遮罩/Esc 就全丢；全站表单弹窗未见同类挽留规范 | DatabaseAdmin.vue:192-197,215-229 | 中 | S |
| M44 | 6 | 「表结构」弹窗与主表格列头信息重复但口径不同：弹窗有「默认值」列，表格列头没有；`default` 直接 `str(col['default'])` 输出 SQLAlchemy 表达式（如 `NextSequence`/`now()`），对运营无解释价值 | DatabaseAdmin.vue:232-248,136-142；db_admin_service.py:181-191 | 低 | S |
| M45 | 2 | 「表结构」「审计日志」弹窗打开入口是图标按钮且弹窗无加载/失败态：`auditLogs` 为旧数据时再次点击直接复用旧列表展示（`loadAuditLogs` 成功后才置 visible，但失败时弹窗不打开、用户以为没点到） | DatabaseAdmin.vue:91-104,634-641 | 中 | XS |

**优化建议**：
1. （M39/M42）新增态若主键是 autoincrement（可由后端在 schema 中补 `autoincrement` 字段），把主键项替换为「自动生成（留空即可）」只读说明；表单项统一 `label="中文名 / 列名"` + `el-tooltip` 说明类型与长度，并加 `maxlength`/范围 rules。落点 `DatabaseAdmin.vue:198-213`、`db_admin_service.py:165-196`。
2. （M40）映射补齐：`DATETIME` → `el-date-picker type="datetime"`、值为有限集合的列（status/action/role）→ `el-select`（后端可提供 distinct 值或前端按 `default`/注释推断）；时间戳列在编辑态默认只读（见 M20）。
3. （M41）按组件类型分支传属性，不再把 `clearable`/`type` 广播给 `el-input-number`/`el-switch`。
4. （M43）`formDialogVisible` 关闭前判断表单是否 dirty，弹 `ElMessageBox.confirm('内容未保存，确认关闭？')`；遮罩关闭设 `:close-on-click-modal="false"`（表单类弹窗应统一）。
5. （M44/M45）表结构弹窗加「说明」列（取模型 comment/中文映射），默认值做人类可读化；审计日志/表结构入口按钮加 `inline-text`，并在请求期间给按钮 `loading`、失败时打开弹窗并显示 `el-result` 错误态。

---

### M-5 维护工具 > 数据库维护 > 导入弹窗（DatabaseAdmin.vue:267-312）

**现状描述**：CSV/JSON 两个粘贴 Tab，导入模式二选一（insert 主键冲突跳过 / replace 主键冲突覆盖），确认后前端本地解析并 `POST /import`，成功 toast「导入完成：成功 X，跳过 Y」。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M46 | 4/5 | 顶部警示文案与后端行为相反：弹窗写「敏感字段会被忽略」，但 `import_rows` 只按 `valid_cols` 过滤，**不过滤敏感列** → 粘贴含 `password_hash`/`config_value` 的 CSV 会真实写入；叠加「导出文件本身是脱敏的（`***`）」，导出→原样导入就是把 `***` 覆盖进生产库的凭据列 | DatabaseAdmin.vue:269-271；db_admin_service.py:434-481,406-430 | 高 | S |
| M47 | 2/5 | 无 dry-run/无预览：不像删除有级联预览，导入这颗按钮直接写库；`replace` 模式会覆盖既有行，界面上没有任何「预计影响 N 行 / 其中主键冲突 M 行」的事前估算，也没有二次确认（仅按钮 `type="warning"`） | DatabaseAdmin.vue:297-311,593-631 | 高 | M |
| M48 | 6 | 前端 CSV 解析是 `split(',')` + `split('\n')`：不支持引号包裹、字段内逗号/换行、`\r\n` 与 BOM；而导出侧用 `csv.writer`（含引号转义）+ 写 BOM，**导出→编辑→导入往返必然串列或产生错位脏数据**，且第 0 行 BOM 会被当成列名的一部分（`"id"`→`\ufeffid"`）从而被后端过滤掉整列 | DatabaseAdmin.vue:605-616；db_admin.py:223-236 | 高 | S |
| M49 | 5 | 后端逐行错误 `errors:[{row,error}]` 完整返回，前端只取 `inserted/skipped` 拼 toast，用户永远看不到哪一行因何失败；`skipped` 同时混装了「主键冲突跳过」「非法行」「列名不匹配」三种语义 | DatabaseAdmin.vue:622-627；db_admin_service.py:452-481 | 高 | S |
| M50 | 2 | CSV/JSON 两个 Tab 共用同一份 `importContent`：切 Tab 不清空也不提示，粘的是 JSON 但停在 CSV Tab 会被按逗号拆成一行垃圾对象；Tab 名「CSV 粘贴 / JSON 粘贴」也未把当前生效格式回显在按钮附近 | DatabaseAdmin.vue:272-296,413-416,593-620 | 中 | XS |
| M51 | 4 | 列名不匹配静默跳过：若粘贴表头与本表列名完全不同，后端每行 `filtered` 为空 → `skipped += 1`，toast 显示「成功 0，跳过 N」，没有任何「请核对列名与本表结构（可点『表结构』查看）」的引导 | DatabaseAdmin.vue:458-461 | 中 | XS |
| M52 | 4 | 「单次最多导入 5000 行」✓ 与后端 `DB_ADMIN_MAX_IMPORT_ROWS=5000` 一致（本切片少见的契约正确项），但前端解析阶段不做条数预检，超过 5000 才由后端整体拒绝，用户白粘一次 | DatabaseAdmin.vue:269-271；db_admin_service.py:444-445；backend/app/config.py:495-496 | 低 | XS |
| M53 | 2 | 导入后不刷新行数徽标：`loadRows` 只更新表格，左栏 `t.rows` 仍是进入页面时的旧值（`loadTables` 只在 mount 调用），运维据此判断「导入生效了吗」会看错 | DatabaseAdmin.vue:435-444,622-628 | 中 | XS |

**优化建议**：
1. （M46）文案与实现二选一：要么后端在 `import_rows` 的过滤里加入 `SENSITIVE_COLUMNS`（推荐，改 `db_admin_service.py:450`），要么前端改为「含 password_hash/config_value 的行会被直接写入，请勿粘贴脱敏导出文件」。
2. （M47）加「解析预览」步骤：点「确认导入」先在前端算出 `列名匹配 X/Y、预计新增 N、主键冲突 M（replace 将覆盖 M 行）`，用 `el-table` 展开前 5 行，再要求第二次点击「写入数据库」；`replace` 模式追加 `ElMessageBox.confirm` 明示覆盖不可恢复。落点 `DatabaseAdmin.vue:593-631`。
3. （M48）CSV 换成成熟解析（项目已引 `element-plus`，可加 `papaparse` 或写一个支持引号/转义/CRLF/BOM 的解析函数），并在解析后做表头 trim + BOM 剥离；同时校验表头列名是否都在本表结构中，未识别列直接列出。
4. （M49/M51）结果改为 `el-dialog`/`el-alert` 明细：`成功 X / 跳过 Y`，展开显示 `errors` 前 20 条（行号 + 原因），并区分「主键冲突跳过 / 校验失败 / 列名不匹配」；`skipped>0` 时用 warning 而非 success toast。
5. （M50/M52/M53）Tab 切换时清空或明确「两种格式共用输入框，当前按 CSV 解析」；解析后本地判条数 >5000 即前置报错；导入成功后并行刷新 `loadTables()` 与 `loadRows()`。

---

### M-6 维护工具 > 数据库维护 > 空态 / 加载失败态（DatabaseAdmin.vue:28,187 + 数据加载链）

**现状描述**：两处空态——左栏「无匹配表」`el-empty`、右栏「请从左侧选择一张表」`el-empty`；数据/结构加载失败走 catch → `console.warn` + 清空本地数据，界面表现为与真实空表完全一致的样式。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M54 | 5 | 接口失败伪装成「空」：`loadRows` 失败时 `rows=[]、total=0`，表格显示 Element Plus 默认「暂无数据」，与真的空表无法区分；`loadSchema` 失败时 `columns=[]`，表格退化成「只剩勾选框 + 操作列」的空壳，用户会误判该表被清空（本表可删行，误判后果严重） | DatabaseAdmin.vue:456-487,116-133 | 高 | S |
| M55 | 4/5 | 左栏表列表加载失败显示「无匹配表」：`tables=[]` 时 `filteredTables.length===0` 命中同一空态，把「拉取失败/无权限」表述为「没有匹配的表」，且没有重试按钮；403（非 admin）也是同一表现 | DatabaseAdmin.vue:28,435-444；api/index.js:62-68 | 中 | S |
| M56 | 2 | 空态无行动指引：「请从左侧选择一张表」没有说明能做什么（新增/导入/导出）；搜索无结果时也没有「清除搜索」按钮（仅靠 clearable 图标） | DatabaseAdmin.vue:187,28 | 低 | XS |
| M57 | 6 | 与同组「系统清理」页的加载态语言不一致：清理页用 `v-loading` + `-` 占位，本页首屏无任何骨架/loading 文案（`rowsLoading` 只挂在表格上，左栏与工具栏在加载期间呈现为可用的假态） | DatabaseAdmin.vue:5-30,116-125；Maintenance.vue:15 | 低 | S |

**优化建议**：
1. （M54/M55）为三类加载各加错误态：左栏失败 → `el-result icon="warning" title="数据表列表加载失败"` + 「重试」；右栏行加载失败 → 表内空态自定义插槽「数据加载失败，点击重试」（不要用默认「暂无数据」）；schema 失败 → 顶部 `el-alert`「表结构获取失败，编辑/删除已临时禁用」并把删除/编辑按钮置灰。
2. （M56）空态文案给出下一步：「选择一张表后可查看/编辑/导入数据」；搜索无结果时显示「没有匹配「{kw}」的表 · 清除搜索」。
3. （M57）统一首屏加载语言：左栏加 `v-loading="tablesLoading"`，工具栏在 `rowsLoading` 期间禁用写操作按钮。

---

### M-7 维护工具 > 系统清理 > 三列清理卡片与 dry-run/执行（路由 /maintenance，文件 apps/admin-web/src/views/maintenance/Maintenance.vue）

**现状描述**：缓存/数据库/日志三张卡片，各自「清理目标」下拉 + 「预览模式」开关（默认开）+ 同一颗执行按钮（label 随开关在「预览清理/立即执行清理」间切换）+ 卡片内结果块；非预览时走一次通用 `ElMessageBox` 确认。后端 `backend/app/routers/admin/maintenance.py` + `services/maintenance_service.py`。
**契约核对结论（先说好消息）**：`{target, days, dry_run}` 字段名与后端 `CleanupRequest` 逐字段一致；三张卡片所有 target 取值（`all/ttlcache/pycache/temp`、`all/old_playlogs/old_workflows/old_reviews/expired_blacklist/old_dedup/old_ai_usage/vacuum`、`all/old_logs/large_logs`）都能在 `maintenance_service.cleanup_cache/database/logs` 中找到分支；status 响应里前端读取的 `db.db_size_mb/playlog_count/workflow_count/review_count/blacklist_count`、`logs.total_size_mb/file_count/oldest`、`cache.ttlcache_count/pycache_count/temp_files` 与后端字段名全部对得上，`cleaned[]/errors[]` 结构一致。以下为体验侧缺陷。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M58 | 2/5 | **预览与执行是同一颗图标按钮**：`label` 在「预览清理/立即执行清理」间切换，但未传 `inline-text`，界面上两态都只是一枚垃圾桶图标（仅靠 `type` 从 primary 变 danger 区分），按钮名与「执行真实删除，不可恢复」全在 hover Tooltip；这是本切片最危险的单点 | Maintenance.vue:88-97,141-150,189-198；IconButton.vue:24-28,93 | 高 | XS |
| M59 | 4 | 不可逆动作的确认框不含任何具体信息：文案固定「即将执行真实删除操作，此操作不可逆，是否继续？」，未写清**删什么（目标+保留天数）、多少条（预览结果就在同一张卡片里）、能否恢复（SQLite 无回收站，只有备份）**；三张卡片共用同一段文案 | Maintenance.vue:310-321 | 高 | S |
| M60 | 2 | 预览不构成执行的门槛：预览显示「将删除 0 条」或直接跳过预览，都能一键进入真实删除；「先预览再执行」只写在页面底部使用说明里，交互上无强制/无提醒（例如未预览时按钮旁无「建议先预览」标记） | Maintenance.vue:79-97,206-216,310-321 | 中 | S |
| M61 | 5 | 汇总数字被丢弃：后端返回 `total_deleted`（数据库）与 `total_freed_mb`（日志），前端 `CleanupResult` 只逐行渲染 `cleaned[]` 文本，运维要点着数行才能拼出「一共删多少条/释放多少 MB」，且没有大号汇总卡 | Maintenance.vue:228-253；maintenance_service.py:272-279,354-361 | 中 | S |
| M62 | 5/2 | 15s 超时 vs 分钟级操作：axios `timeout: 15000`（`src/api/index.js:17`），而 VACUUM / 大批量 DELETE 常超 15s（后端注释也提示 VACUUM 锁库直到完成）；前端先报「超时/清理失败」，后端仍在继续，用户以为失败会重复点击 → 重复锁库；整个过程中页面无进度、无「执行中请勿关闭」提示 | Maintenance.vue:323-343；api/index.js:16-17；maintenance_service.py:544-569；Help.vue:444-448 | 高 | M |
| M63 | 4 | 保留天数无风险分级：`el-input-number` 允许 1–365，填 1 天近乎清空全部历史（后端 `days=max(1,days)` 只做下限保护，无「保留过短」告警），也不会把「将删除 N 条」实时反映在表单旁（需先点预览） | Maintenance.vue:123-131,171-179；maintenance_service.py:236-238,344 | 中 | S |
| M64 | 4 | 「清理目标 = 全部」把语义不同的动作打包：数据库卡片选 `all` 时同一次会执行时间清理 + 过期黑名单 + VACUUM，而界面上「保留天数」仍显示且对 VACUUM/黑名单无效（仅底部说明第 2 条有一句话），用户会以为 VACUUM 也受天数约束 | Maintenance.vue:110-131,210；maintenance_service.py:244-279 | 中 | S |
| M65 | 4 | 缓存清理的实际副作用无提示：`ttlcache` 会清空进程内缓存（含鉴权/限流相关计数），文案只有「TTLCache 将清空 N 条」，未告知可能导致登录态/限流窗口/正在跑的读请求受影响；`pycache` 会 `shutil.rmtree` 遍历应用根目录（已排除 venv/node_modules，但界面不显示清理根路径），用户不知道「删的是哪个目录下的东西」 | Maintenance.vue:70-78,99；maintenance_service.py:154-220,615-673 | 中 | S |
| M66 | 5 | 预览过度承诺：`large_logs` 预览会把当前正在写入的 `app.log` 列为「将删除（大于 10MB）」，真实执行时 Windows 下对已打开文件 `unlink` 会 `PermissionError` → 落入 `errors`，即预览说会删、执行必然失败（需实测确认）；预览结果未剔除不可删除项 | Maintenance.vue:163-199；maintenance_service.py:716-793 | 中 | M |
| M67 | 6 | 错误提示重复：`handleCleanup` 的 catch 里再 `ElMessage.error(...)`，而 axios 拦截器已对同一失败弹过一次（`api/index.js:62-68`），失败时出现两条内容相近的 toast | Maintenance.vue:338-341；api/index.js:30-72 | 低 | XS |
| M68 | 1 | 清理无历史可查：`maintenance_service._write_audit` 把审计写进 `audit_log`（category=`maintenance`），但数据库维护页的审计查询 SQL 固定 `WHERE category='db_admin'`，且 `audit_log` 不在 db-admin 表白名单里——系统清理到底谁在什么时候删了多少，**界面上没有任何入口能看到** | maintenance_service.py:797-824；db_admin_service.py:507-526,40-57 | 中 | M |
| M69 | 6 | 目标取值在代码里两处漂移：本页 `src/api/maintenance.js` 无人引用（0 处 import），且其 JSDoc 写的数据库取值是 `blacklist \| dedup \| ai_usage \| playlog \| vacuum`（与真实 `old_playlogs/expired_blacklist/...` 不符），Maintenance.vue 直接 `import api from '../../api'` 自己拼 payload；后续按该封装改契约的人会踩坑 | Maintenance.vue:226,289-344；src/api/maintenance.js:1-58 | 中 | S |
| M70 | 3 | 三列 `el-col :span="8"` 在窄屏（移动端管理）会挤成三列窄卡，`el-select` 的中文长选项如「旧审核记录（已完结）」可能截断；需实测确认 | Maintenance.vue:62-203 | 低 | S |

**优化建议**：
1. （M58，先做）执行按钮加 `inline-text`，并把两态在视觉上拉开：预览态 `label/inline-text="预览清理"`（primary 描边），真实态 `inline-text="立即执行"`（danger 实心 + 「不可恢复」小字常驻，不依赖 Tooltip）。落点 `Maintenance.vue:88-97,141-150,189-198`。
2. （M59）确认文案动态化：`将${targetLabel}：${days ? '保留'+days+'天，' : ''}预览结果为 ${totalText}。SQLite 无回收站，删除后只能通过备份恢复。确认执行？`，其中 `totalText` 取上一次同卡片预览的 `total_deleted/total_freed_mb/cleaned`；未预览过时改为「尚未预览，建议先预览」并提供「先去预览」按钮。落点 `Maintenance.vue:310-321`。
3. （M60）引入执行门槛：`dry_run` 开关从开→关时，若本卡片无同目标+同参数的预览结果，把执行按钮置灰并提示「请先预览」。
4. （M61）`CleanupResult` 顶部加汇总行：数据库「合计将删除/已删除 N 条」、日志「合计释放 X MB」，用后端 `total_deleted/total_freed_mb`；VACUUM 行单独显示前后文件大小。
5. （M62）给清理请求单独放宽超时（该请求传 `timeout: 0` 或 10 分钟，`api` 支持逐请求覆盖），并改为「提交 → 轮询进度」两步（可复用 `about` 的 `upgrade/status` 轮询范式）；执行中在卡片上显示 `el-skeleton` + 「VACUUM 进行中，期间数据库写入会被阻塞，请勿关闭页面」。落点 `Maintenance.vue:323-343`、`src/api/index.js`。
6. （M63/M64）`days<=7` 时在数字下方追加 warning 文案「保留天数≤7 将清除几乎全部历史，请先备份」；`target==='all'` 时把「保留天数」项标注「仅作用于按时间清理，不影响 VACUUM/过期黑名单」并把 per-target 明细直接列在选择框下（而不是靠底部说明）。
7. （M65）缓存卡片加「清理范围」说明行：TTLCache「会重置进程内缓存，可能影响限流统计与已缓存查询」；pycache「清理根目录：<app_root>，不动 .venv/node_modules」；temp「仅 data 目录下 *.tmp」。
8. （M66）预览阶段对当前活动日志文件（进程持有的 `app.log`）打标「正在使用，执行时会跳过」，避免预览与执行结果对不上。
9. （M67）删掉页内 `ElMessage.error`，或给请求传 `silent: true` 由页面自己呈现（拦截器已支持 `silent`，`api/index.js:40-62`）。
10. （M68/M69）审计入口补齐：`db_admin_service.list_audit_logs` 支持 `category` 参数并把 `audit_log` 纳入白名单（或系统清理页自建「清理历史」弹窗）；同时删除或修正 `src/api/maintenance.js` 的过时 JSDoc 与未引用状态，让页面统一走封装。

---

### M-8 维护工具 > 系统清理 > 存储状态卡 / 结果区 / 空态（Maintenance.vue:14-59,228-253）

**现状描述**：三张状态卡（数据库 / 日志文件 / 缓存），数值来自 `GET /maintenance/status`；每卡片下方有 `CleanupResult` 内联组件展示 `cleaned/errors`，两者皆空时显示「无需清理」。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M71 | 5 | 状态接口失败即伪装成「干净」：`loadStatus` catch 只 `console.error`，`status` 为 null 时三卡显示 `-` 与 `0 条 / 0 个`，运维会读成「数据库 0 条日志、无需清理」；若是二次刷新失败，更糟——**继续展示上一次的旧数值且无任何过期标记**，据此判断清理效果会得出错误结论 | Maintenance.vue:23-57,289-298 | 高 | S |
| M72 | 5 | 状态区缺 3 个清理目标的体量：后端已返回 `dedup_count`、`ai_usage_count`（及 `cache.pycache_mb`），界面一个都没展示，而数据库下拉里恰好有「旧爬虫去重记录 / 旧 AI 用量日志」；用户无法预判这两项规模就决定要不要清 | Maintenance.vue:24-29,48-56；maintenance_service.py:109-137 | 中 | XS |
| M73 | 4 | 结果区在预览态与执行态共用同一句「无需清理」：`cleaned` 为空时不分 dry_run；预览命中 0 条应写「预览：无匹配项，本次执行不会删除任何内容」。同时 `dry_run` 结果的标题「清理结果：」也不区分「预览结果」 | Maintenance.vue:228-253 | 中 | XS |
| M74 | 6 | 单位与量纲混排：数据库/日志卡主数值走 `formatMb`（<1MB 自动降到 KB），缓存卡主数值是「N 条」，detail 里「目录 / 个」混用；卡片标题不带单位，`formatMb` 的 KB/MB 切换需要用户自己看后缀 | Maintenance.vue:23,38,51,282-286 | 低 | S |
| M75 | 2 | 结果是一次性的：卡片内 `result` 不持久、切走页面即丢，也无法对比「清理前 800MB → 清理后 620MB」；`loadStatus` 只在非 dry_run 后调用，预览完不刷新体量参考 | Maintenance.vue:260-268,324-337 | 中 | M |
| M76 | 3 | 无空态/首屏占位：`loadingStatus` 初值为 true 且 `status` 为 null，卡片主值先渲染 `-`（非骨架），与失败态视觉相同（呼应 M71）；状态区 `min-height:120px` 但三卡 detail 行数不等（日志卡按条件少一行），三卡高度不齐需实测确认 | Maintenance.vue:256-257,38-42,372-415 | 低 | S |

**优化建议**：
1. （M71）`loadStatus` 失败时把状态区切为错误态（`el-result` + 重试），若已有旧数据则在卡片区上方常驻一条灰条「状态数据截至 {{time}}，刷新失败」；给 `status` 加 `fetchedAt` 与 `stale` 标记，并在成功时记录。落点 `Maintenance.vue:256-298`。
2. （M72）补 `dedup_count`/`ai_usage_count` 到数据库卡 detail，补 `pycache_mb` 到缓存卡；下拉里每个目标行右侧显示对应体量（「旧爬虫去重记录 · 12,405 条」）。
3. （M73）`CleanupResult` 接收 `dryRun` prop，分别渲染「预览结果 / 清理结果」标题与空态文案（「预览：无匹配项」/「无可清理内容」）。
4. （M74）主数值统一带单位（`MB`/`条`），`formatMb` 阈值文案改「KB/MB」后固定右侧对齐；detail 行统一「量 + 单位 + 名词」。
5. （M75）把三张卡片的结果区改为页面底部「本次操作记录」列表（含目标、参数、时间、前后体量对比），并在预览后也刷新状态（只读，成本低）。

---

### M-9 帮助 > 帮助文档（路由 /help，文件 apps/admin-web/src/views/help/Help.vue）

**现状描述**：左目录（16 章节，搜索框按标题+简介过滤）+ 右侧静态文档卡片（feature/steps/scenario/config/note 五类块），顶部「API 文档」按钮开 `/docs`；滚动高亮监听 `.el-main` 容器。
**逐条比对结论**（菜单名以 router meta.title 为准）：章节标题与菜单名对齐的有 内容审核/广告素材/投放规则/排期日历/数据统计/频道管理/队列管理/工作流监控/内网穿透/AI 服务/通知管理/参数计算器/数据库维护/系统清理/关于 ✓；文档内**未声明任何快捷键**，代码中也未见全局快捷键绑定 → 快捷键项无漂移。以下为漂移与交互缺陷。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M77 | 4 | 内容审核步骤的按钮名不存在：文档写「通过：点击「审核通过」」「驳回：点击「驳回」，填写驳回原因」；实际界面是单选组 **通过 / 打回 / 替换段落** + 一颗「提交」按钮，全站 Tab/批量按钮也叫「已打回 / 批量打回」，「审核通过」「驳回」两个词在界面上都不存在，且文档漏掉「替换段落」这一动作 | Help.vue:199-201；apps/admin-web/src/views/review/ReviewDetail.vue:108-129；apps/admin-web/src/views/review/ReviewList.vue:4-6,22,32 | 高 | XS |
| M78 | 4 | 工作流「重试」入口不存在：文档「失败工作流可点击「重试」从失败步骤恢复」，但工作流列表按钮是 手动触发/全频道启动/批量删除/重置，详情页按钮只有 返回/刷新/新增素材，均无「重试」；后端其实有 `POST /admin/api/v1/workflows/{id}/retry`（界面未接），文档描述的是接口能力而非界面现实 | Help.vue:327；WorkflowList.vue:51-95；apps/admin-web/src/views/workflow/WorkflowDetail.vue:89-90；backend/app/routers/admin/workflows.py:276 | 高 | XS |
| M79 | 4 | 快速开始「创建工作流：在「工作流监控」页面新建工作流」中的「新建」不存在，实际动作叫「手动触发」（且触发后是排队执行，不是创建一条可编辑草稿） | Help.vue:162；WorkflowList.vue:72 | 中 | XS |
| M80 | 4 | 数据库维护章节功能虚标：写「提供 **20+ 业务表** 的在线 CRUD」，实际白名单是 **16 张**；写「支持表结构查看、记录编辑、**SQL 查询**、CSV 导入导出」，页面上没有任何 SQL 输入/执行入口；「危险操作需 CONFIRM_DELETE 令牌双重确认」只说了一半——该令牌须与后端 `DB_ADMIN_CONFIRM_TOKEN` 部署配置一致，否则删除/导入全部被拒 | Help.vue:423-424；db_admin_service.py:40-57；DatabaseAdmin.vue:36-113；backend/app/config.py:492 | 高 | S |
| M81 | 4 | 参数计算器章节整段与实际不符：文档写「输入目标时长（**分钟**），自动计算 LLM 应生成字数（**330 WPM 基线** ±10%）与 TTS 语速调节建议」；实际界面单位是**秒**、基线是 **210 字/分**、无 ±10% 容差，也没有「语速调节建议」这种输出，实际是「三选一锁定推导 + 应用到 AI 服务」。运维按文档理解会算错约 57% 的字数 | Help.vue:403-411；ParamCalculator.vue:20,58-66,221 | 高 | XS |
| M82 | 1/4 | 「API 文档」按钮指向不存在的入口：`window.open('/docs')`，而后端 `docs_url` 仅在 `is_dev`（`APP_ENV=="development"`）开启，生产打包后 `/docs` 落到 SPA fallback 返回 index.html——新标签页打开的是运营后台/登录页而非文档；此外前端 base 是 `/news/`，绝对路径 `/docs` 在 Funnel 路径区分模式下也不对 | Help.vue:552-554；backend/app/main.py:1318；backend/app/config.py:539-541；apps/admin-web/src/router/index.js:301；main.py:1460-1478 | 高 | S |
| M83 | 4 | 内容审核「查看热力评分（关键词密度、可读性、敏感词检测）」的功能在审核页不存在：审核详情页没有评分卡、列表页无红色敏感词标签；「敏感词」只出现在频道管理（频道级配置）与智能助手，文档把配置能力写成了审核页展示能力 | Help.vue:198,206；ReviewDetail.vue（全文无相关元素）；apps/admin-web/src/views/channel/ChannelManagement.vue | 中 | S |
| M84 | 4 | COS 章节命令路径错误：「验证凭证：`python jmeter_test/verify_cos.py`」「迁移历史音频：`python jmeter_test/migrate_audio_to_cos.py`」，两个脚本实际在 `scripts/jmeter_test/` 下，仓库根没有 `jmeter_test/` 目录，照抄命令必然报「文件不存在」 | Help.vue:491-492；scripts/jmeter_test/verify_cos.py；scripts/jmeter_test/migrate_audio_to_cos.py | 高 | XS |
| M85 | 4 | 快速开始与产品形态错位：文档让用户 `pip install -r backend/requirements.txt` + `copy .env.example .env` + 「双击 启动服务.bat」（实际位于 `scripts/`），而项目交付物是 exe 安装包（`installer.iss`/`MorningBrief.spec`），安装后无 `backend/` 源码目录；「访问 http://127.0.0.1:8000/」也没带前端 base 的 `/news/` 前缀，端口依赖 `APP_PORT` 默认 8000 ✓ 但路径提示不完整 | Help.vue:157-160；scripts/启动服务.bat；installer.iss；backend/app/config.py:129；router/index.js:301 | 中 | S |
| M86 | 4 | 队列管理写「支持手动重试失败任务、清空已完成任务」：「重试」存在 ✓，但界面里没有「清空已完成任务」这颗按钮，实际是勾选后「批量删除」；文档也未提队列页真正的主角——执行模式/并发数配置与保存 | Help.vue:304；QueueManagement.vue:44,95,162 | 中 | XS |
| M87 | 1 | 文档覆盖缺口约一半菜单：`素材库管理`、`素材录入`、`找书工具`、`讲书稿素材池`、`智能助手`、`自动审批`、`云端配置`、`文件管理`、`频道健康度`、`RSS 源状态`、`LLM 重试指标` 均无章节；已有章节「音频存储（COS）」讲的是 .env 与脚本，反而没写这两个真实菜单页面怎么用；同时「审计日志在哪里看」全系统无文档（见 M68） | router/index.js:96-178,161-165；Help.vue:141-541 | 中 | M |
| M88 | 2 | 搜索只匹配标题与简介（`s.title / s.intro`），正文里才有关键词的内容一律搜不到：搜「CONFIRM_DELETE」「VACUUM」「COS」「密钥」都会返回「未找到匹配的章节」，而这三项在文档正文里都有 | Help.vue:544-550,423,442,454 | 高 | S |
| M89 | 5 | 搜索无结果态过于贫瘠：仅一行文字「未找到匹配的章节」，没有「清除搜索」按钮、没有说明搜索范围（标题/简介）、没有近义章节建议；此时右侧内容整体消失，用户不知道自己把文档「弄没了」 | Help.vue:102-104 | 中 | S |
| M90 | 2 | 目录高亮有盲区：`handleScroll` 只在 `rect.top ∈ [0,120)` 时更新 `activeSection`，两章节间距或长表格导致该区间落空时高亮会停在旧章节，出现「看着在讲 A，目录亮的是 B」；容器靠 `document.querySelector('.el-main')` 硬取，布局类名一改即静默失效（无兜底） | Help.vue:566-589 | 低 | S |
| M91 | 2 | 锚点不能分享：目录项用 `<a :href="#id">` + `@click.prevent`，页面不读 `route.hash`/`query.section`，所以无法给出「直达数据库维护章节」的链接；关于页/新手指引跳来 `/help` 也不会定位；右键/中键打开 `#id` 只是本地锚点，落到 SPA 后仍是章节顶部取决于渲染时机 | Help.vue:31-41,556-562,583 | 低 | S |
| M92 | 4 | 文档无版本/更新日期标识：页面底部只写「MorningBrief · 帮助文档」，与关于页的版本号（`1.0.20261017.001`）无对应关系，运维无法判断这份文档是否匹配当前安装包——在本切片发现 8 处文档漂移的情况下尤其致命 | Help.vue:106-109；About.vue:10；backend/app/_build_info.py:9-11 | 中 | XS |
| M93 | 3 | 目录卡片 `position: sticky; top: 0` 且 `.anchor-list` 无 `max-height/overflow`，16 个章节在较矮视口下会超出粘顶区域，下方章节名在滚动中不可达（需实测确认）；`<992px` 时目录整体压到内容上方并取消粘顶，长文档检索体验骤降 | Help.vue:649-667,835-844 | 低 | S |

**优化建议**：
1. （M77–M81、M83–M86，先做）对 Help.vue 的 8 处漂移逐条改写为界面真名：`审核通过→通过`、`驳回→打回`、补「替换段落」；工作流「重试」改为「当前界面暂无重试入口（后端接口存在）」并同步产品补齐按钮；数据库维护「20+ 表→16 张白名单表」、删掉「SQL 查询」或加真实功能；参数计算器章节重写为「时长(秒)/总字数(字)/倍率(x) 三选一锁定，基线 210 字/分，结果通过「应用到 AI 服务」带入且区间为 180–1200s、0.5–2.0x」；COS 命令改 `python scripts/jmeter_test/verify_cos.py`；队列「清空已完成任务→勾选后「批量删除」」。落点全部在 `Help.vue:157-160,199-206,304,327,403-411,423-424,491-492`。
2. （M82）「API 文档」改为按环境判定：由 `/admin/api/v1/about` 或新增配置接口返回 `docs_enabled`，非 dev 时按钮变「API 文档（仅开发环境）」并禁用/提示，同时链接补 `/news` base（用 `router.base`/`import.meta.env.BASE_URL` 拼）。落点 `Help.vue:552-554`。
3. （M88/M89）搜索范围扩到 `blocks[].title + content（字符串与数组都覆盖）+ config 行`，命中后高亮关键词；无结果态补「清除搜索」按钮与「搜索范围：章节标题、小节与正文」说明。落点 `Help.vue:544-550,102-104`。
4. （M87）补齐 11 个缺章节（可先做「一句话 + 入口路径 + 注意事项」的轻量档），并把「维护工具 > 审计/清理历史在哪看」写成独立章节——这依赖 M68 的入口补齐。
5. （M92）章节数据加 `docVersion`/`lastVerifiedAt` 字段并在 footer 与每章标题旁渲染「对齐版本 1.0.20261017.001」，漂移排查时有锚点。
6. （M90/M91/M93）滚动高亮改为「取当前视口内最靠上的章节」（`getBoundingClientRect().top <= 120` 的最大值者胜），容器用 `el-main` 的 ref/注入而非全局 querySelector；`scrollToSection` 同步 `router.replace({ hash: '#id' })` 并在 mount 时读 `route.hash` 定位；目录 `max-height: calc(100vh - 140px); overflow:auto`。

---

### M-10 帮助 > 关于（路由 /about，文件 apps/admin-web/src/views/about/About.vue）

**现状描述**：品牌卡（版本号 + 复制 + 检查更新五态按钮 + 一键升级进度）+ 元信息卡（产品/Python/平台/Git SHA）+ 8 项链接列表 + 开源声明 Modal（静态 41 条依赖，可搜索）；进页 5s 自动检查、每 60 分钟复查。
**版本号来源核对结论**：`backend/VERSION=1.0.20261017.001` → `backend/build_info.py` 生成 → `backend/app/_build_info.py`（当前 `__version__="1.0.20261017.001"、build_date="2026-10-17"、git_sha="cb64ac1"`）→ `GET /admin/api/v1/about` 透出（`backend/app/routers/admin/about.py:65-78,195-211`）。三者当前**一致** ✓，前端不再硬编码版本。以下为其余缺陷。
**问题清单**：

| # | 维度 | 问题 | 证据 | 优先级 | 成本 |
|---|---|---|---|---|---|
| M94 | 5 | **更新检查根本没工作，却宣称「已是最新」**：`REPO_URL` 默认为空串（`backend/app/config.py:138`、`backend/.env.example:19` 也是空），后端直接降级返回 `has_update=false, source='local', error="未配置 REPO_URL，跳过更新检查"`；前端把 `res.error` **完全忽略**（`about.js:30` 已把这个字段写进 JSDoc 说前端会用于诊断），`source==='local'` 落入 else 分支 → 按钮显示绿色「已是最新」。GitHub 403/超时/404 等降级路径同理，一律显示「已是最新」 | About.vue:300-336；backend/app/routers/admin/about.py:229-246；src/api/about.js:30 | 高 | S |
| M95 | 2 | **一键升级无二次确认**：`newer` 态点「立即更新 (vX.Y.Z)」直接 `POST /about/upgrade`，后端下载 release 包并在桌面端自动替换、重启服务（`restarting` 为终态），界面无「将重启服务、中断进行中的工作流/审核」提示，也没有变更内容/体积/来源仓库摘要 | About.vue:64-67,375-401；backend/app/routers/admin/about.py:272-293 | 高 | S |
| M96 | 4 | 5 个外链是占位假地址：用户协议 `https://example.com/terms`、隐私条款 `https://example.com/privacy`、联系我们 `mailto:dev@example.com`、官方社区 `https://example.com/community`、报告问题 `https://example.com/issues/new`，都带外链箭头且可点击，点了就是打不开/发给不存在的邮箱；「API 文档 `/docs`」同样不可用（见 M82，生产 `docs_url=None` 且未带 `/news` 前缀） | About.vue:205-214,210；backend/app/main.py:1318 | 高 | S |
| M97 | 4 | 版本比较丢弃第 4 段：项目版本是四段 `1.0.20261017.001`，而 `_SEMVER_RE` 只取前三段并按 `(maj,min,patch)` 比较——同一天重打包（`.002`）永远判定「无更新」，同日多次热修场景下「检查更新」系统性失灵 | backend/app/routers/admin/about.py:91-119；backend/VERSION:1 | 中 | S |
| M98 | 5 | 「已是最新」3 秒后自动退回 idle：手动点检查后，确认反馈自己消失，用户回眼看变成一颗没点过的「检查更新」；同时后台每 60 分钟 + 进页 5 秒的自动检查会自行改按钮状态（甚至自行弹出「立即更新」这颗带破坏性的按钮），用户没操作却在动 | About.vue:49-67,326-348,457-467 | 中 | S |
| M99 | 4 | 「发布于」语义被后台轮询改写：`source==='remote'` 且无更新时，用远端 release 的 `published_at` 覆盖 `info.build_date`（界面无任何说明），而该字段本意是本地安装包的构建日期；一旦 release 时间≠构建时间，关于页展示的发布日期就不再对应本机安装的那一版 | About.vue:313-319；about.py:261 | 中 | S |
| M100 | 5 | 元信息接口失败时静默兜底 `'--'`，界面不显示「获取失败/重试」入口；此时「复制版本号」会把 `--` 写进剪贴板并提示「已复制」；后台自动检查仍可能显示「立即更新 (vX)」，出现「版本号未知但有新版本」的矛盾画面 | About.vue:170-181,274-282,429-437 | 中 | S |
| M101 | 4/6 | 开源清单与实际依赖不一致：41 条为静态硬编码（代码注释自认「P2 再接 license-checker」），其中 `edge-tts` 写 **6.1.10**，而 `backend/requirements.txt:22` 已固定 **7.2.8** 并注明「6.x 的 TrustedClientToken 已被微软封禁（403），必须 >=7.2.8」——清单展示了一个已知不可用的版本；依赖增删也不会自动同步 | About.vue:218-262；backend/requirements.txt:22 | 中 | M |
| M102 | 4 | 页脚提示指向用户机器上不存在的东西：Tooltip 写「详见 README 中的「风险免责」」，README 确有该章节（`README.md:174`），但 `MorningBrief.spec`/`installer.iss` 未收集 README/docs，安装后的运营机上没有这份 README | About.vue:120-122；README.md:174；MorningBrief.spec（无 README/docs 收集项） | 中 | XS |
| M103 | 6 | 链接列表是 `div @click`，无 `role="link"`/`tabindex`/键盘 Enter 触发，键盘与读屏用户无法打开「开源软件声明」与任何外链；「帮助文档」是站内跳转却也用 `TopRight`（外链箭头）图标，与 5 个真外链同一视觉语言 | About.vue:105-116,205-214,439-455 | 中 | S |
| M104 | 6 | Git SHA 同页自相矛盾：品牌卡按 `showSha` 在 SHA 为 `unknown` 时隐藏（注释明说「避免误导」），元信息卡却无条件渲染 `Git SHA: unknown` | About.vue:15,199-202,98-100 | 低 | XS |
| M105 | 1 | 「报告问题」是占位外链，但产品里已有真实反馈通道（移动端 用户反馈管理 `/m/manage/feedback`、`src/api/feedbacks.js`），运营侧却无处提交问题；帮助文档也只描述该链接存在 | About.vue:213；src/api/feedbacks.js；router/index.js:263-267 | 中 | M |
| M106 | 5 | 升级进度的终态无出口：`restarting`/`dev_staged` 只是文案，界面无「点这里重新加载后台」或自动跳转，用户会停在进度卡上等待一个已经重启完成的服务；轮询瞬时失败被强行改回 `downloading` 态，可能长时间假「正在下载」 | About.vue:20-36,403-427 | 中 | S |

**优化建议**：
1. （M94，先做）按 `source`/`error` 分支呈现：`source==='local'` 且带 `error` 时按钮显示「未配置更新源」并给出说明与跳转（内网穿透/配置页），不再显示「已是最新」；GitHub 降级同理显示「无法连接更新源（网络/限流），上次成功检查：—」。落点 `About.vue:300-360`。
2. （M95）「立即更新」前加 `ElMessageBox.confirm`：列出当前版本 → 目标版本、包体积、并明确「下载完成后会自动替换并重启后台服务，正在运行中的工作流可能中断，请确认当前为低峰期」；升级面板补「查看变更」。
3. （M96）占位外链治理：`REPO_URL`/`ISSUES_URL`/`CONTACT_EMAIL` 由后端 `/admin/api/v1/about` 一并透出，前端对未配置项渲染为禁用态并标注「管理员可在 .env 配置 REPO_URL」；生产环境隐藏或禁用「API 文档」项（与 M82 同源修复）。
4. （M97）版本解析支持任意段数：`_SEMVER_RE` 改为 `\d+(\.\d+)*` 并按 tuple 逐段比较，或改用 `packaging.version.Version`（已在 Python 依赖生态内）；比较结果在 `checked_at` 上暴露给 UI。
5. （M98/M99）手动检查的 `latest` 结果不再 3s 自动回收（改为常驻 + 一个「重新检查」小按钮）；自动检查只在结果变化时提示（`ElNotification` 一次性），且不自动切到 `newer` 破坏性按钮——`newer` 由用户主动检查后出现；「发布于」拆成两个字段 `build_date`（本机）与 `release_published_at`（远端），不再互相覆盖。
6. （M100/M104）`loadAbout` 失败时顶部 `el-alert`「系统元信息获取失败 · 重试」，`version==='--'` 时禁用复制按钮；元信息卡与品牌卡对 SHA 采用同一 `showSha` 判定。
7. （M101）开源清单改为打包期由 `license-checker`/`pip-licenses` 生成 JSON 资产随包发布（或运行时由后端读取 `requirements.txt`/`package.json`），删除静态表；至少在页脚显示「清单生成时间」。
8. （M103/M105）列表项改 `<a>`/`<button>`（站内项用 `router-link`），加可见 focus 态；站内跳转与外链用不同图标（`Right` vs `TopRight`）；「报告问题」指向真实反馈入口（可先指向关于页所在的运营后台反馈页或 Git Issues，取决于 M96 的配置结果）。
9. （M106）`restarting` 终态提供「服务已重启，点这里重新加载后台」按钮（`location.reload()`）与倒计时；`dev_staged` 说明「开发环境已暂存更新包，需手动执行安装脚本 + 路径」；轮询连续失败 N 次后切为「进度获取失败 · 重试」而不是伪 `downloading`。
10. 弹窗/空态补充：开源声明 Modal 的无结果态「未找到匹配的依赖」✓ 存在且合理，**未发现显著体验缺陷**；替代优化——把依赖清单按「前端/后端/构建工具」分组加计数与过滤，40+ 条单列平铺时长尾检索费力。

---

### 附：本切片契约核对一览（前端 payload ↔ 后端模型）

| 界面动作 | 前端 | 后端 | 结论 |
|---|---|---|---|
| 新增行 | `POST /db-admin/tables/{t}/rows` body `{values}`（dbAdmin.js:34-36） | `RowCreateRequest{values: dict}`（db_admin.py:33-36,122-134） | 结构一致；但空值/空串被后端丢弃（M16/M18） |
| 更新行 | `PATCH .../rows/{pk}` body `{values}`（dbAdmin.js:39-41） | `@router.patch` + `RowUpdateRequest{values}`（db_admin.py:137-153） | 方法/包装一致；敏感列与时间列可被误写（M14/M20） |
| 单行删除 | `DELETE .../rows/{pk}?confirm_token=CONFIRM_DELETE`（dbAdmin.js:44-48） | Query `confirm_token` 必填并常量时间比对（db_admin.py:156-173,61-70） | 一致，但令牌值依赖部署配置（M29） |
| 批量删除 | `POST .../rows/batch-delete` body `{ids, confirm_token}` | `BatchDeleteRequest{ids, confirm_token}`（db_admin.py:43-46,176-192） | 一致；条数上限 1000 与 UI 每页≤200 不冲突 |
| 级联预览 | `POST .../cascade-preview` body `{ids}` | `CascadePreviewRequest{ids}`（db_admin.py:49-52,197-207） | 一致；返回的 `total_affected` 前端未用（M32） |
| 导入 | `POST .../import` body `{rows, mode, confirm_token}` | `ImportRequest{rows: list[dict], mode, confirm_token}`（db_admin.py:54-58,249-265） | 一致；「敏感字段被忽略」文案与实现相反（M46） |
| 导出 | `GET .../export?format=csv\|json` + `responseType:'blob'` | `format` Query + StreamingResponse（db_admin.py:212-244） | 一致；blob 分支拦截器已特判（api/index.js:34-36）；上限静默截断（M23） |
| 审计日志 | `GET /db-admin/audit-log?limit=100` | `limit` 校验 1–500，SQL 固定 `category='db_admin'`（db_admin.py:270-279；db_admin_service.py:507-526） | 一致；清理类别审计无入口（M68） |
| 存储状态 | `GET /maintenance/status` 读 `db/logs/cache` 各字段 | `MaintenanceService.get_status`（maintenance_service.py:70-137） | 字段全对齐；3 个已返回字段未展示（M72） |
| 三类清理 | `POST /maintenance/{database\|logs\|cache}` body `{target, days?, dry_run}` | `CleanupRequest{target, days=0, dry_run}`（maintenance.py:22-26,44-93） | 字段名与取值集合全部匹配 ✓（唯 `api/maintenance.js` 是过时死代码，M69） |
| 关于 / 检查更新 / 升级 | `GET /about`、`GET /about/check-update`、`POST /about/upgrade`、`GET /about/upgrade/status`（about.js:37-63） | about.py:195-301 | 路径/方法一致；前端丢弃 `error`/`source` 语义（M94） |
| 计算器 → AI 服务 | `router.push('/ai-config', query={duration, rate})` | `AIConfig.applyCalculatorParams` 读取并映射 `edge_rate` 百分串 | 参数名与倍率换算一致 ✓；区间不一致 + 静默 clamp（M2） |

---

## 12. 跨菜单系统性根因（R1–R7）

逐菜单条目里的多数问题是以下 7 条根因的表象。每条附「单点修法」——修根因可一次性消掉一片条目。标「已复验」的条目由主评审回读源码逐字确认。

### R1　全站反馈通道被设计成「可以静默丢弃」（已复验）

- `apps/admin-web/src/utils/message.js:16-45`：只要 `document.hidden` 为真、或窗口刚恢复的 2 秒内，`ElMessage.success/error/warning/info/loading` **一律直接 `return`**——不排队、不补发、不落任何可见记录。
- `apps/admin-web/src/api/index.js:18,62-69`：全局 `timeout: 15000`；错误提示受 `!error.config?.silent` 门控，凡带 `silent: true` 的请求（后台轮询、部分页面首屏加载）失败后**永久无感**，只留 `Promise.reject` 给调用方自行处理——而下游大量调用方是 `catch {}` 或 `.catch(() => null)`。

后果：最小化窗口跑批/轮询的真实失败与成功回执全部丢失；「后端挂了」在各页被渲染成「暂无数据 / 全 0 正常态」。切片 A/B/D/E/G/I/M 的静默失败类条目（高危 45 条）几乎都挂在这两处。
单点修法：`message.js` 改为**排队 + 恢复可见时补发**（上限 N 条聚合），并给 `silent` 语义加约束（silent 只允许用于"预期会有下次轮询覆盖"的状态查询，页面首屏加载禁用）；同时补一条 ESLint 规则禁止页面组件里裸 `catch {}`/`console.error` 收尾。

### R2　「加载失败 → 回落默认值 → 点保存即覆写已持久化配置」

- 通知管理：加载失败退默认值后保存，会静默清空已存 webhook 并把全局开关反转（G8）。
- 云端配置：加载失败后保存静默清空 Bucket/CDN，前后端均无条件覆写（H1 组）。
- AI 服务：草稿静默恢复可用陈旧值覆盖线上配置（F2）。

共同形态：`field: config?.x || ''` / 默认对象兜底 + 保存走**全量 PUT** + 后端不做「字段缺省即不改」。
单点修法：配置页统一改为「加载失败即禁用保存并给重试」+ 后端 PUT 只接受脏字段（或引入 `If-Match`/`updated_at` 乐观锁）。

### R3　脱敏值被当成真实数据回写（最严重，可致不可逆数据毁损，已复验）

- 后端 `backend/app/services/db_admin_service.py:129-140`：`_mask_sensitive()` 把 `password_hash`/`token`/`secret` 以及 `ai_config` 中 key 含 key/secret/password/token 的 `config_value` 一律返回字面量 `"***"`。
- 前端 `apps/admin-web/src/views/maintenance/DatabaseAdmin.vue:390`：`editableColumns = computed(() => columns.value)`——**敏感列同样可编辑**；`:496-503` `formData.value = { ...row }` 把带 `"***"` 的整行灌进编辑弹窗；`:512` `updateRow(table, pk, formData.value)` 整包提交。
- 后端 `db_admin_service.py:298-315`：`update_row()` 只过滤 `None` 与 `""`，**不认识 `"***"` 哨兵**，直接拼进 `UPDATE ... SET`。
- 结果：编辑任意一行（哪怕只改备注）都会把该行的 `password_hash` 或 API Key 写成字符串 `***`，同时前端 `:513` 弹「更新成功」；而 `:519` 的 `catch { console.warn }` 让失败同样静默。
- 同源第二条：`:270` 导入提示「敏感字段会被忽略」，但 `import_rows`（`:434` 起）无任何敏感列过滤——导出（含 `***`）→ 导入往返同样毁数据，且文案是错的。

单点修法（成本 XS，收益最高）：`update_row`/`import_rows` 服务端把 `"***"` 视为「不更新」哨兵并拒绝落库；前端 `editableColumns` 过滤 `_is_sensitive_column`，编辑弹窗对敏感列只读并提示「需通过专用重置流程」。

### R4　前端枚举、引导与文档与后端实现漂移（缺单一事实源）

- 审核状态：后端 `backend/app/models/review.py:13-25` 有 4 态（含 `replaced`，且 DB 有 CheckConstraint 兜住），前端 `ReviewList.vue:4-6` 只有「待审核/已通过/已打回」三个 tab → 做过「替换段落」的记录**在所有 tab 都看不见**，不可追溯（已复验）。
- 新手引导：`guide/guideConfig.js:71` 第 2 步锚点 `[aria-label="立即触发一期工作流"]`，而 `views/workflow/WorkflowList.vue` **全文无 `aria-label`** → 锚点必然失配，回落到 `.top-bar .el-button`（第一个按钮，非触发按钮），引导指错地方（已复验）。
- 帮助文档：8 处描述指向不存在的按钮/功能/路径（「审核通过」「驳回」「新建工作流」「工作流重试」「SQL 查询」「20+ 表」等）（M）。
- 关于页：5 个外链仍是 `https://example.com/terms|privacy|community|issues/new` 与 `mailto:dev@example.com` 占位（`views/about/About.vue:206-213`，已复验）；`REPO_URL` 默认为空使「检查更新」永远报「已是最新」。
- 菜单权威名只有 `router/index.js` 的 `meta.title` 一处，但该文件头注释（`router/index.js:8-15`）声明的分组里**没有「云端存储」**，实际路由有 8 组 → 注释与实现漂移；文案里出现「右上角」「新增规则」这类不存在的方位/按钮名（D）。

单点修法：状态/步骤枚举由后端一次性下发（或前端生成常量表），引导配置与帮助文档条目改为「按 `meta.title` + 真实按钮文案」生成并加一条 e2e 断言（每个引导锚点必须能在目标路由命中元素）。

### R5　统计数字缺口径限定语与单位错（数据被误读）

- **单位错（已复验）**：`backend/app/models/play_log.py:32` 明确 `duration` 注释为「本次会话已播放时长（秒）」；`backend/app/services/stats_service.py:53-56,86-87` 直接取 `avg(PlayLog.duration)` 不做换算；前端 `views/stats/StatsOverview.vue:84` 标签写 **「平均收听(分钟)」** → 数值被读成分钟，实际是秒，约 60 倍误导。
- 完播率卡片 ×100 而趋势图仍 0~1（同一指标两种刻度，D）；缺数据日补 0 被画成断崖且真实空态分支不可达；日期区间选择只作用于统计卡、趋势恒为「截至今日」（D）。
- 全组 7 个菜单（广告 3 + 数据分析 4）均无导出、无自动刷新、筛选不持久化，且空态文案指向不存在的按钮名。

单点修法：统一 `<StatCard scope=… unit=… />`，口径与单位由组件层强制传入；后端下发指标元数据（单位/是否百分比），前端不再各自换算。

### R6　长任务/流式的基本能力缺失（超时、断流、无收尾）

- **已复验**：`api/index.js:18` 全局 `timeout: 15000`，而 `views/ai/KnowledgeQA.vue:498` 调 `/ai/chat` **未覆盖超时**；同仓 `api/assistant.js:21,29` 已显式 `{ timeout: 120000 }` → 证明是遗漏而非约定。LLM 长回复必被前端 15 秒掐断，用户只看到失败提示，且问答无流式、无停止生成按钮。
- 工作流列表/详情的轮询与 SSE 静默失败，无断流提示、无独立刷新入口（E）；15s 超时早于 VACUUM 完成会诱导重复触发（M）；上传无进度、批量无结果汇总。

单点修法：凡「预期耗时 > 15s」的接口调用统一走显式超时常量；流式/轮询失败必须落可见状态并给「重连/手动刷新」；长任务完成一律 `notification` 汇总。

### R7　高危/有副作用动作的确认与后果说明缺失（含"点了没反应"）

- **已复验**：移动端应急停服 `views/mobile/ManageAlert.vue:51-62`：`ElMessageBox.prompt` 解构出 `value`，随后却写 `reason = v.trim()`（`v` 只存在于 `inputValidator` 的形参作用域）→ `ReferenceError` 被紧随的 `catch { return // 取消 }` 吞掉，**点「确认停服」后静默返回，永远停不了服**。这个页面存在的唯一理由就是紧急止损，它在紧急时不可用。
- 移动端「通过」单击即发布、支持一键跨频道批量发布，无确认（I1/I2）；频道/广告启停零确认（I42/I45）。
- 系统清理的「预览」与「真实删除」共用一颗纯图标按钮，确认文案不含目标与条数（M）。
- 文件管理上传同名静默覆盖无确认（H）。
- 自动审批：总开关开 + 两条规则关 + 白名单空 = **后端零条件自动发布上线**，UI 与后端均无下限护栏（G13）。

单点修法：所有"改变线上状态"的动作统一 `ElMessageBox.confirm` + 四要素文案（动作/影响范围/数量/恢复成本）；自动审批类加后端下限校验（无规则且无白名单时禁止启用）。

---

## 13. 汇总优先级矩阵

三张表：**13.1** 142 条高危按根因主题归组（决定「先修哪一类」）；**13.2** 94 个界面小节按高/中/低计数（决定「先看哪个菜单」）；**13.3–13.5** 排期批次、中低分布与「未发现显著体验缺陷」清单。

### 13.1 高危条目按主题归组（142 条）

**R3 脱敏值回写/不可逆数据毁损（9 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| D14 | 广告管理 > 投放规则 | 「停用」这条唯一的可逆干预路径 PC 上不可用，只能删除（不可逆）；而移动端可用的 `PUT /ads/placements/{id}` 对不存在的 id 会 500（`error()` 未在 `ads.py` 导入），且 C 端 `get_active_placements` 查询**不过滤 enabled**，停用后客户端仍会播出该广告 → 开关不可信 | apps/admin-web/src/api/ads.js:13；backend/app/routers/admin/ads.py:9-10；:106-128；backend/app/services/ad_service.py:237-238 | M |
| F3 | AI 自动化 > AI 服务 | **清空密钥保存是静默 no-op**：`_normalize_llm/_normalize_tts/_normalize_image` 均 `if api_key and not _is_masked(...)` 才写入，空串被跳过——但同文件 docstring 声称「空字符串视为清除 Key」（契约与实现矛盾）。用户在 API Key 框清空→保存→提示成功→重进页面旧 Key 脱敏值仍在，且界面无任何「清除密钥」入口 | apps/admin-web/src/backend 对照：backend/app/services/ai_config_service.py:594,667-669,720-727,697-699 | M |
| H1 | 云端存储 > 云端配置 | loadConfig 失败被 catch 吞掉后表单保持初值 bucket=''，「保存配置」payload 仍无条件携带 bucket/cdn_domain，后端 update_config 也无条件覆写这两项 → 加载失败（网络抖动/500）后点一次保存即把已存 Bucket、CDN 域名清空，配置静默损毁且需重填凭据才能恢复 | apps/admin-web/src/views/cos/CosConfig.vue:198-209,214-220；backend/app/services/cos_config_service.py:139-143 | M |
| M14 | 维护工具 > 数据库维护 > 主界面（表浏览 / 行编辑 / 搜索排序 / 导入导出） | **脱敏值回写覆盖真实数据（不可逆）**：`list_rows` 会把 `password_hash`/`token`/`secret` 以及 `ai_config.config_value` 显示为 `***`，而编辑弹窗用 `formData = {...row}` 预填、`editableColumns` 含全部列且只禁用主键，保存时 `update_row` 只按「非主键 + 非空」过滤、不排除敏感列 → 只要对 `admin_user`/`ai_config` 任一行点「确认」（哪怕只改了简介），就会把 `password_hash` 或 API Key 写成字面量 `***`，随即该运营账号无法登录 / 该服务商密钥作废，且界面提示「更新成功」 | DatabaseAdmin.vue:200-213,496-504,506-520；backend/app/services/db_admin_service.py:86-116,129-140,298-319；backend/app/models/admin_user.py:27；backend/app/models/ai_config.py:36 | S |
| M29 | 维护工具 > 数据库维护 > 主界面（表浏览 / 行编辑 / 搜索排序 / 导入导出） | 前后端契约：删除/批量删除/导入的令牌是前端硬编码常量 `CONFIRM_DELETE`（`dbAdmin.js:10`），后端读 `settings.DB_ADMIN_CONFIRM_TOKEN`，而 `config.py:492` 默认为空串、`.env.example:183` 明确要求「替换为随机字符串」——只要部署照 example 做，删除/批量删除/导入三类动作**必然失败**，报错文案仅「confirm_token 校验失败」，用户会以为是自己的拼写问题 | src/api/dbAdmin.js:10,43-56；backend/app/routers/admin/db_admin.py:30,61-70；backend/app/config.py:492；backend/.env.example:183 | M |
| M46 | 维护工具 > 数据库维护 > 导入弹窗 | 顶部警示文案与后端行为相反：弹窗写「敏感字段会被忽略」，但 `import_rows` 只按 `valid_cols` 过滤，**不过滤敏感列** → 粘贴含 `password_hash`/`config_value` 的 CSV 会真实写入；叠加「导出文件本身是脱敏的（`***`）」，导出→原样导入就是把 `***` 覆盖进生产库的凭据列 | DatabaseAdmin.vue:269-271；db_admin_service.py:434-481,406-430 | S |
| M47 | 维护工具 > 数据库维护 > 导入弹窗 | 无 dry-run/无预览：不像删除有级联预览，导入这颗按钮直接写库；`replace` 模式会覆盖既有行，界面上没有任何「预计影响 N 行 / 其中主键冲突 M 行」的事前估算，也没有二次确认（仅按钮 `type="warning"`） | DatabaseAdmin.vue:297-311,593-631 | M |
| M48 | 维护工具 > 数据库维护 > 导入弹窗 | 前端 CSV 解析是 `split(',')` + `split('\n')`：不支持引号包裹、字段内逗号/换行、`\r\n` 与 BOM；而导出侧用 `csv.writer`（含引号转义）+ 写 BOM，**导出→编辑→导入往返必然串列或产生错位脏数据**，且第 0 行 BOM 会被当成列名的一部分（`"id"`→`\ufeffid"`）从而被后端过滤掉整列 | DatabaseAdmin.vue:605-616；db_admin.py:223-236 | S |
| M80 | 帮助 > 帮助文档 | 数据库维护章节功能虚标：写「提供 **20+ 业务表** 的在线 CRUD」，实际白名单是 **16 张**；写「支持表结构查看、记录编辑、**SQL 查询**、CSV 导入导出」，页面上没有任何 SQL 输入/执行入口；「危险操作需 CONFIRM_DELETE 令牌双重确认」只说了一半——该令牌须与后端 `DB_ADMIN_CONFIRM_TOKEN` 部署配置一致，否则删除/导入全部被拒 | Help.vue:423-424；db_admin_service.py:40-57；DatabaseAdmin.vue:36-113；backend/app/config.py:492 | S |
**R7 高危动作缺确认或点了没反应（39 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| A19 | 一级：登录 | 登录失败反馈缺失：拦截器 401 分支只清 localStorage 并「不在登录页才跳登录页」，既不弹 ElMessage 也不给用户可见原因；而登录请求失败正发生在登录页（pathname==loginPath 不跳），导致用户名/密码错误时（若后端返回 401）用户只看到 loading 结束、无任何提示，首次用户走不通（需实测确认后端登录失败的 HTTP 状态码；若返回 200+code!=0 则会正常提示） | apps/admin-web/src/api/index.js:52-61; views/login/Login.vue:141-150; views/mobile/Login.vue:49-56 | XS |
| C10 | 内容运营 > 频道管理 | 删除频道的二次确认只写「确认删除频道「X」？此操作不可恢复。」，未披露真实连带后果：讲书稿书单按外键 `ON DELETE CASCADE` 整本删除、素材行 `channel_id` 无外键约束会变成无主数据（列表/聚合视图永久筛不到）。运营在误删后无法预判损失范围 | apps/admin-web/src/views/channel/ChannelManagement.vue:1071-1093；backend/app/models/book_pool.py:30-31；backend/app/models/material.py:76；backend/app/services/channel_service.py:282-304 | S |
| C56 | 素材库管理 > 编辑素材弹窗 / 手动录入素材弹窗 / 删除确认 | 编辑弹窗不校验正文与来源：`onSaveEdit` 只挡空标题，正文/来源可被清空后照样提示「已保存」；而来源=书名正是讲书稿聚合键，清空即打断整本书聚合（该书在书单候选里消失） | apps/admin-web/src/views/channel/MaterialLibrary.vue:425-448,170-173；backend/app/services/book_pool_service.py:341-343 | S |
| C68 | 内容运营 > 讲书稿素材池 | 深链/非法频道静默降级：`route.query.channelId` 直接赋给 `channelId`，不校验是否存在于 `channels`；频道不存在时面板按"未开启 + 空池"渲染并显示"请先加入书籍"，用户以为池被清空了 | apps/admin-web/src/views/channel/BookPool.vue:61-67；apps/admin-web/src/views/channel/BookPoolPanel.vue:222-228；backend/app/services/book_pool_service.py:42-45（channel 不存在返回 exists:false） | S |
| C80 | 讲书稿素材池 > BookPoolPanel（模式状态 / 调度 / 进度 / 书单表 / 重置与预览） | 「预览下次生成」是一次性 POST 且结果常驻显示（`preview` 不清空），此后任何排序/加入/移出操作都不会使预览失效——用户看到的"下次将生成《X》"可能已过期，属于典型的数据被误读 | apps/admin-web/src/views/channel/BookPoolPanel.vue:46,267-274,284-295,242-256 | S |
| D24 | 广告管理 > 排期日历 | 同广告位日期重叠时静默覆盖：`map[dateKey][p.position] = {material_name}` 后写覆盖前写，日历只显示其中一条，既无「+1 条冲突」角标也无 tooltip 展示其余素材 | apps/admin-web/src/views/ad/AdSchedule.vue:93-97 | S |
| D35 | 数据分析 > 数据统计 | 空数据被画成 0 折线：后端对区间内每一天补 0，前端 `hasTrend` 只判断 `dates.length>0`（恒为真），「暂无趋势数据」空态几乎不可达 → 新上线/埋点缺失/查询为空的区间显示成「断崖归零」 | apps/admin-web/src/views/stats/StatsOverview.vue:93；:46-48；backend/app/services/stats_service.py:108-110 | S |
| D68 | 数据分析 > LLM 重试指标 | 数据时间范围全程未标注：后端返回的是**自进程启动以来累计**计数（重启即归零），页面没有任何「累计/自 xx 启动/重启清零」字样，卡片与漏斗看起来像「当前状态」→ 运营发布重启后看到 0% 会误判「问题已修复」 | apps/admin-web/src/views/stats/LlmMetrics.vue:37-59；:61-79；backend/app/routers/admin/stats.py:85-98；backend/app/workflow/llm/rewriter.py:448-462 | XS |
| D78 | 组内共性问题（跨 7 个菜单，不重复计入上表） | 反馈可达性系统风险：`utils/message.js` 与 api 拦截器在 `document.hidden` 时**静默丢弃**所有 ElMessage，包括删除成功/失败与请求错误；最小化窗口后台轮询的运营回来看不到任何提示，误认为操作成功 | apps/admin-web/src/utils/message.js:28-33；:56-72；apps/admin-web/src/api/index.js:47-52 | S |
| E1 | AI 自动化 > 工作流监控 | 实时链路断流完全不可见：轮询与 SSE 均为 silent 失败（拦截器对 silent 请求不提示、loadList 无 catch 只留 unhandled rejection），若接口连续失败（网络抖动/会话异常/后端重启），页面静止显示旧的 running 状态且无任何「数据可能过期」提示；页面上也没有独立的「刷新」按钮（「重置」会连带清空筛选条件，不能当刷新用），无手动重连入口 | apps/admin-web/src/views/workflow/WorkflowList.vue:340-373、560-573；apps/admin-web/src/api/index.js:62-69；apps/admin-web/src/utils/sse.js:150-154 | M |
| G2 | 系统配置 > 内网穿透 | `loadConfig()` 失败仅 `console.error`、无任何用户提示（catch 446-448），页面静默退回表单默认值（provider=cloudflare、hostname/tunnel_id/credentials_file/tunnel_name/binary_path 全空）。运维在网络抖动后直接点「保存配置」→ `handleSaveConfig` 把默认值 POST，后端 `save_config` 会**用空值覆盖已持久化的 Named Tunnel 字段并把 provider 重置为 cloudflare**（仅 authtoken/cert_file 有 `or existing` 兜底，其余无） | apps/admin-web/src/views/tunnel/Tunnel.vue:446-448,521-534；backend/app/services/tunnel_service.py:249-261 | S |
| G8 | 系统配置 > 通知管理 | 加载失败后保存**静默清空已持久化渠道 + 反转到「全局开启」**：`loadConfig()` catch 空处理（569-571），`configForm` 初始 `global_enabled:true`（527）而 `dingtalk_webhook/wecom_webhook/email_smtp_host/email_to/admin_base_url` 初始全空（531-539）；`handleSaveConfig` 提交 `{...configForm}`，后端 `save_config` 对这些 key **无条件写入 `str(data or "")`**（无 `or existing` 兜底，仅 secret/password 有 masked 跳过）→ 网络抖动后点保存会把 webhook/SMTP 全部清成空串，并把全局开关从库里的 `0` 改成 `1`，导致本应静音的通知被打开 | apps/admin-web/src/views/notification/NotificationConfig.vue:526-540,548-574,576-589；backend/app/services/notification/config_service.py:119-155,21-35 | S |
| G13 | 系统配置 > 自动审批 | **护栏缺失，可致任意内容零检查自动上线**：后端 `try_auto_approve` 对三条规则均是「开启才校验」，`require_content_safe`/`require_steps_first_success` 关闭且 `keyword_whitelist` 为空时，`matched_rules` 与 `fail_reasons` 皆空 → 直接进入 approve+publish。界面divider 承诺「全部命中才自动通过」，但当管理员打开总开关又把两条规则都关掉、白名单留空时，等于「无条件全部命中」；UI 与后端 `update_config`（无「至少保留一条规则」兜底/校验）都不阻止该组合 | backend/app/services/auto_review_service.py:315-372,106-121；apps/admin-web/src/views/system/AutoReviewConfig.vue:40-110,339-356 | S |
| H9 | 云端存储 > 文件管理 | 「上传文件」不做同名检测：后端 key=prefix+原文件名直接 put_object，重传同名音频即静默覆盖旧对象，无「已存在，是否覆盖？」确认 → 高频运维最容易触发的无确认破坏性动作 | apps/admin-web/src/views/cos/CosFiles.vue:288-300；backend/app/routers/admin/cos.py:141-145；backend/app/services/cos_storage_service.py:191 | M |
| I1 | 移动端 > 审批 | 「通过」按钮单击即调用 `handleReviewAction(...,'approve')` 并触发后端自动发布，无任何二次确认；而同卡的「驳回」却有 prompt。外勤拇指易误触「通过」→ 直接发布节目，误操作不可逆 | apps/admin-web/src/views/mobile/ReviewList.vue:154 / 246-275 | S |
| I2 | 移动端 > 审批 | 「一键全部审批」在**非作用域**模式下把跨频道全部待审（最多 200 条）一次性通过，仅一个 confirm 文案「确认一键通过当前 N 条」，不展示频道分布、不要求选择，小屏一键即批量发布，确认强度与风险不匹配 | apps/admin-web/src/views/mobile/ReviewList.vue:17-24 / 288-318 | M |
| I42 | 移动端 > 频道管理 | 频道停用是线上影响动作（停用会取消该频道 queued 任务、停止内容产出），但 `toggle(c)` **零确认**直接执行；对照用户禁用却有 ElMessageBox 二次确认（I-8），确认强度与安全等级倒挂 | apps/admin-web/src/views/mobile/ManageChannels.vue:48-57 ↔ ManageUsers.vue:72-91 + QueueManagement.vue:560 | S |
| I45 | 移动端 > 广告投放 | 广告启停直接影响线上投放曝光，`toggle` **零确认**，与用户禁用有确认、频道应确认的口径不一致（同 I42 类问题） | apps/admin-web/src/views/mobile/ManageAds.vue:50-59 ↔ ManageUsers.vue:72-91 | S |
| I54 | 移动端 > 应急停服 | **高危动作功能失效**：`stop()` 里 `const { value } = await ElMessageBox.prompt(...)` 之后写 `reason = v.trim()`，`v` 在该作用域未定义 → 抛 ReferenceError 被外层 `catch { return }` 吞掉，等同「用户取消」，`emergencyStop` 永不触发。点「应急停服」填完原因确认后毫无反应，应急态无法开启 | apps/admin-web/src/views/mobile/ManageAlert.vue:53-62 | XS |
| I55 | 移动端 > 应急停服 | `getMaintenanceStatus().catch(()=>({enabled:false}))` 把「读不到状态」误判为「生产运行正常」（绿色横幅）：真实处于停服态但状态接口失败时，管理员看到「生产运行正常」，掩盖事故现场，且据此可能误操作 | apps/admin-web/src/views/mobile/ManageAlert.vue:44 / 6-7 | S |
| J21 | 底部导航 > 我的（pages/profile/profile） | 退出登录的语义承诺错误：`onLogout` 只调 `localData.clearByOpenid` + `downloadStore.clearByOpenid` 后 reLaunch（711-719），后端收藏/进度/播放记录全部保留，但隐私政策第 3 条写着「要求删除个人信息（退出登录即可）」——本页与 privacy 页共同构成一个不可兑现的承诺 | apps/miniprogram/pages/profile/profile.js:709-719；apps/miniprogram/pages/privacy/privacy.js:38 | M |
| J29 | 节目详情（pages/detail/detail） | 队列在这里是页内 modal（wxml:330-367，含清空与"当前项"高亮），在 `pages/queue/queue` 是另一套整页实现，同一功能两份代码两种交互（modal 无法分页/排序、整页也无法删单项），且两边都不给"移除这一首" | apps/miniprogram/pages/detail/detail.wxml:330-367；apps/miniprogram/pages/queue/queue.wxml:8,27 | M |
| J60 | 我的下载（pages/download/download） | 三枚删除按钮同形同色（全部清空 trash、频道清空 trash、单项删除 x，wxml:11-22,38），"清空 30 章"与"删 1 章"视觉权重一致；除整表清空外均无二次确认 | apps/miniprogram/pages/download/download.wxml:11-22,38 | S |
| J72 | 我的收藏（pages/favorites/favorites） | 取消收藏的唯一手势是长按：规则只写在页面底部一行提示里（wxml:50-52），列表项右侧无「…」菜单、无滑动删除；首次进入的用户点条目只会被送进详情，找不到移除入口 | apps/miniprogram/pages/favorites/favorites.wxml:50-52 | S |
| J77 | 播放队列（pages/queue/queue） | 与详情 modal 双实现，且两处都不能删除单项、不能拖拽排序，只提供"整表清空"（queue.wxml:8；detail.wxml:336）——队列最基本的两项管理动作缺失 | apps/miniprogram/pages/queue/queue.wxml:8；apps/miniprogram/pages/detail/detail.wxml:336 | M |
| J80 | 播放设置（pages/settings/settings） | 「清除缓存」的确认文案撒谎：`content: '将清除本地缓存（保留登录信息与设置），确定继续？'`（js:147），而 `KEEP_KEYS` 只保 `news_token`/`news_user`/播放设置（js:24），循环删除其余所有 key（js:152-157），实际被抹掉的包括收藏、播放进度、播放历史、偏爱频道、下载索引、上次播放项、搜索历史、反馈历史——用户以为清了图片缓存，结果收藏清空、续听进度归零 | apps/miniprogram/pages/settings/settings.js:24,147,152-157 | S |
| J98 | 隐私政策（pages/privacy/privacy） | 用户权利条款写了不可兑现的承诺：「您有权：…3) 要求删除个人信息（退出登录即可）」（privacy.js:38），而退出登录只清本地（profile.js:711-712 的 `clearByOpenid` 两个调用），服务端 openid 关联的收藏/进度/播放记录全部保留，且 `backend/app/routers/api/` 下不存在任何账号注销或数据删除接口——按指引操作的用户实际没删掉任何个人信息 | apps/miniprogram/pages/privacy/privacy.js:38；apps/miniprogram/pages/profile/profile.js:709-719；backend/app/routers/api/（无删除路由） | M |
| J105 | 查看原文（pages/webview/webview） | 失败场景最需要明确指令，两个按钮却被去成纯图标（wxml:14-18，注释明写「T00384：图标即按钮，去掉"复制链接/返回"文案」，仅留 aria-label）；URL 原文整行展示（12）在小屏上大概率溢出或截断，用户无法核对复制到了哪条链接（需实测确认） | apps/miniprogram/pages/webview/webview.wxml:12-18 | XS |
| J107 | J-附 跨页组件 / 服务 / 生命周期 | 后台播放与页面显示不同步的根因在组件缺 `show` 钩子：`services/audio.js` 用订阅扇出补偿 `getBackgroundAudioManager` 的覆盖式回调，但订阅回调只更新 `isPlaying`/进度角，从不重算 `visible`/`episode`，且没有任何页面在显示时主动取一次播放器快照（J5、J53、J85 同源） | apps/miniprogram/components/floating-player/floating-player.js:21-37,45-58；apps/miniprogram/pages/history/history.js:79 | M |
| M16 | 维护工具 > 数据库维护 > 主界面（表浏览 / 行编辑 / 搜索排序 / 导入导出） | 后端 `update_row` 把 `None` 与空字符串一律过滤掉（「空字符串视为不更新」），前端输入框却是 `clearable`：用户清空一个文本字段后保存 → 该列被静默丢弃、数据库保持旧值，同时前端弹「更新成功」，形成「改了没生效但说成功」；置空在 UI 上永远做不到 | DatabaseAdmin.vue:208-211,506-520；db_admin_service.py:306-310 | M |
| M31 | 维护工具 > 数据库维护 > 删除确认弹窗（级联预览 + 令牌） | **预览失败即静默降级为「零信息确认」**：`cascadePreview` 抛错时 `deleteCascade = null`，而整块预览在 `v-if="deleteCascade"` 下，弹窗只剩分割线 + 令牌输入框 + 可点确认；对不可逆删除，用户看不到删什么/多少条/有无级联，仍能一路确认到底（失败只 `console.warn`） | DatabaseAdmin.vue:316-332,533-540,553-559 | S |
| M32 | 维护工具 > 数据库维护 > 删除确认弹窗（级联预览 + 令牌） | 确认文案三处缺项：① 用英文表名 `deleteTarget`（`admin_user`）而非左栏已给的中文名；② 通篇没有「此操作不可恢复 / 无回收站 / 建议先备份」（对比系统清理页至少有一句「不可逆」）；③ 后端返回的 `total_affected`（级联合计行数）被前端丢弃，用户看不到「主表 N + 级联 M = 共 N+M 行」 | DatabaseAdmin.vue:317,334-335；db_admin.py:197-207；db_admin_service.py:371-402 | S |
| M33 | 维护工具 > 数据库维护 > 删除确认弹窗（级联预览 + 令牌） | **预览口径与真实删除口径不一致**：预览/级联都只走 `TABLE_RELATIONS` 声明表，删 `workflow` 只提示并清理 `workflow_step`，而 `workflow` 的真实下游（script/review/episode/play_log/play_progress/comment/favorite/notification_log/auto_review_stat）既不预览也不清理——同一份数据在「系统清理」里是按全链级联删的；文档式承诺「工作流步骤将一并删除」给运维造成「删干净了」的错觉，实际留下悬空数据 | db_admin_service.py:62-82,561-587；maintenance_service.py:388-496；Help.vue:309-336 | M |
| M37 | 维护工具 > 数据库维护 > 删除确认弹窗（级联预览 + 令牌） | 删除成功后仅 `已删除 N 行`，N 取的是**请求数** `deleteIds.length` 而非后端 `affected`/`cascade` 实际值（后端两者都返回了），存在「说删了 50 行、实际删了 47 行」而用户无从察觉 | DatabaseAdmin.vue:562-576；db_admin_service.py:321-336,338-367 | S |
| M54 | 维护工具 > 数据库维护 > 空态 / 加载失败态 | 接口失败伪装成「空」：`loadRows` 失败时 `rows=[]、total=0`，表格显示 Element Plus 默认「暂无数据」，与真的空表无法区分；`loadSchema` 失败时 `columns=[]`，表格退化成「只剩勾选框 + 操作列」的空壳，用户会误判该表被清空（本表可删行，误判后果严重） | DatabaseAdmin.vue:456-487,116-133 | S |
| M58 | 维护工具 > 系统清理 > 三列清理卡片与 dry-run/执行 | **预览与执行是同一颗图标按钮**：`label` 在「预览清理/立即执行清理」间切换，但未传 `inline-text`，界面上两态都只是一枚垃圾桶图标（仅靠 `type` 从 primary 变 danger 区分），按钮名与「执行真实删除，不可恢复」全在 hover Tooltip；这是本切片最危险的单点 | Maintenance.vue:88-97,141-150,189-198；IconButton.vue:24-28,93 | XS |
| M59 | 维护工具 > 系统清理 > 三列清理卡片与 dry-run/执行 | 不可逆动作的确认框不含任何具体信息：文案固定「即将执行真实删除操作，此操作不可逆，是否继续？」，未写清**删什么（目标+保留天数）、多少条（预览结果就在同一张卡片里）、能否恢复（SQLite 无回收站，只有备份）**；三张卡片共用同一段文案 | Maintenance.vue:310-321 | S |
| M78 | 帮助 > 帮助文档 | 工作流「重试」入口不存在：文档「失败工作流可点击「重试」从失败步骤恢复」，但工作流列表按钮是 手动触发/全频道启动/批量删除/重置，详情页按钮只有 返回/刷新/新增素材，均无「重试」；后端其实有 `POST /admin/api/v1/workflows/{id}/retry`（界面未接），文档描述的是接口能力而非界面现实 | Help.vue:327；WorkflowList.vue:51-95；apps/admin-web/src/views/workflow/WorkflowDetail.vue:89-90；backend/app/routers/admin/workflows.py:276 | XS |
| M95 | 帮助 > 关于 | **一键升级无二次确认**：`newer` 态点「立即更新 (vX.Y.Z)」直接 `POST /about/upgrade`，后端下载 release 包并在桌面端自动替换、重启服务（`restarting` 为终态），界面无「将重启服务、中断进行中的工作流/审核」提示，也没有变更内容/体积/来源仓库摘要 | About.vue:64-67,375-401；backend/app/routers/admin/about.py:272-293 | S |
**R1 静默失败/错误被吞成空态或正常态（21 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| A16 | 一级：公共组件与 stores / message（ThemeSwitcher, IconButton, VoiceSyncButton; stores/theme, stores/user; utils/message） | 提示包装器在 `document.hidden` 或重新可见后的 2s `_isRestoring` 窗口内，把所有 success/error/warning 直接 `return` 丢弃、且 confirm 转为 reject：切走标签页期间的接口失败/成功反馈永久不再补发，构成系统性静默失败（本项目历史高频缺陷类） | apps/admin-web/src/utils/message.js:16-28,38-58 | S |
| B21 | 内容运营 > 队列管理 · 主体 | `listQueueTasks` 标 `silent:true`（拦截器不弹错），`loadTasks` catch 回落 `tasks=[],total=0`：初始加载/筛选/排序失败时直接显示「暂无队列任务」空态，后端宕机被**误读为空队列**（本项目历史高频缺陷） | apps/admin-web/src/views/queue/QueueManagement.vue:387-409；apps/admin-web/src/api/queue.js:11 | S |
| C5 | 内容运营 > 频道管理 | `loadList()` 只有 `try/finally`，接口失败时既不提示也不区分错误：`list` 保持空数组，表格落到空态「暂无频道，点击右上角『新增频道』创建」——把服务异常渲染成"数据不存在"，首次用户会当真去新建重复频道 | apps/admin-web/src/views/channel/ChannelManagement.vue:675-684,78 | S |
| C16 | 频道管理 > 新增/编辑频道弹窗（四页签表单） | `resetForm()` 漏清 `book_rss_sources` 与 `icon_url`：编辑过「有声读物」频道 A 后点「新增频道」，A 的书籍 RSS 源会静默带入新频道并提交（`bookRssSourcesJson` 取自残留数组），图标预览也显示 A 的图标。跨频道配置串味且无任何提示 | apps/admin-web/src/views/channel/ChannelManagement.vue:713-750（对照 731-744 已清的字段）,914-918,1019-1038 | XS |
| C43 | 内容运营 > 素材库管理（列表 / 筛选 / 分页 / 视图切换，路由 /channels/material-library） | 精确定位提示条与视图切换互相说谎：从讲书稿书单点「素材 ID」进入后显示「已按素材 ID 123 定位」，用户切到「按书聚合」时，聚合接口只接受 `channel_id/keyword/status`，`material_id`/`source` 被静默忽略，提示条仍在但结果已不过滤；运营据此误判"这本书只有这些章节" | apps/admin-web/src/views/channel/MaterialLibrary.vue:336-342,122-126,353-365；backend/app/routers/admin/materials.py:283-289 | S |
| C73 | 讲书稿素材池 > BookPoolPanel（模式状态 / 调度 / 进度 / 书单表 / 重置与预览） | 切频道时状态残留导致进度被误读：`loadState()/loadPool()` 无 catch，`Object.assign(state, data)` 在失败时保持上一频道值，界面继续显示「已取 X / 共 Y 本 · 上次《Z》」与上一频道的书单行，运营会把 A 频道的进度当成 B 频道 | apps/admin-web/src/views/channel/BookPoolPanel.vue:217-242 | XS |
| C91 | 内容运营 > 素材录入 | 上传整本书遇重复章节会半本入库：后端逐章调用 `_persist_material`，每次内部 commit，重复内容抛 `BizError(409,"该频道已存在相同内容的素材")` 中断循环。结果是"前 N 章已入库 + 一条与场景无关的错误提示（不提第几章、不提已入库多少）"，重试仍卡在同一章。前端只在 `catch` 里留注释交给拦截器 toast | apps/admin-web/src/views/channel/CourseMaterials.vue:246-265；backend/app/routers/admin/materials.py:529-541,118-131 | M |
| D25 | 广告管理 > 排期日历 | 加载失败零反馈：`fetchSchedule` 只有 try/finally 无 catch，失败时 `scheduleMap` 保留上一个月的数据，日历切到新月份后全部显示「—」，用户读作「本月无排期」；页面无错误提示与重试按钮（全局 toast 还会被 `document.hidden` 吞掉） | apps/admin-web/src/views/ad/AdSchedule.vue:77-104；apps/admin-web/src/utils/message.js:28-33 | S |
| E11 | AI 自动化 > 工作流详情 | 素材行「查看」按钮点击必失败：viewMaterial 内用 `h(...)` 构建 VNode，但 script setup 只 import 了 ref/computed/onMounted/onUnmounted，vite AutoImport 未配 `imports:['vue']`（同仓 Maintenance.vue 是显式 import h 的），运行时 ReferenceError 被 Promise 吞掉——无弹窗、无提示，用户以为按钮坏了 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:428、669-683；apps/admin-web/vite.config.js:18-20；对照 apps/admin-web/src/views/maintenance/Maintenance.vue:221 | XS |
| F2 | AI 自动化 > AI 服务 | 断点草稿**静默恢复**：`applyDraft/apply` 把上次未保存的本地草稿深合并进刚加载的服务端配置，无任何「已恢复草稿/丢弃」横幅；`hasDraft` 在 useDraft 中已导出但页面未使用。换机器/他人改过线上配置后，本浏览器陈旧草稿值会顶掉真实值并在下次保存时被静默写入 | apps/admin-web/src/views/ai/AIConfig.vue:1578-1584；apps/admin-web/src/composables/useDraft.js:62-81,116 | S |
| H8 | 云端存储 > 文件管理 | 后端返回的文件夹名自带结尾斜杠（"sub1/"），行内 name 与表格显示均含"/"；openRename 把含"/"的 name 预填进「新名称」，confirmRename 再无条件追加"/" → 用户在重命名弹窗**不改动直接点确定**时 destKey="sub1//"（≠row.key 所以不会短路返回），整个目录被移进"//"畸形路径，列表随即出现空白子层级，等效数据错位；改对也要求用户手动删掉预填的尾斜杠，全程无提示 | apps/admin-web/src/views/cos/CosFiles.vue:214-221,327,339-343；backend/app/services/cos_storage_service.py:145-150 | S |
| I15 | 移动端 > 首页 | `getDashboardSummary().catch(()=>({today:{},pending_review:0,unread_message:0}))` 把失败静默成「DAU -、待审 0、未读 0」的正常空态；外勤首屏遇网断会误判「今天没有要审的」 | apps/admin-web/src/views/mobile/Home.vue:57-66 | S |
| J4 | 底部导航 > 今日节目 | 空态标题把「错误」和「今日暂无」塞进同一字段 `error \ | \ | XS |
| J11 | 底部导航 > 历史（pages/history/history） | 行容器 `bindtap="onPlay"`（wxml:105）与行内播放 chip `catchtap="onPlay"`（wxml:148）指向同一个处理函数，该函数固定「起播 + navigateTo detail」：本意图是"打开这条历史"的点击（点标题、点封面、点任意空白）一律先发出声音再跳页，公共场合误触即外放，且列表页没有"只看不听"的入口 | apps/miniprogram/pages/history/history.wxml:105,148；apps/miniprogram/pages/history/history.js:320 | S |
| J16 | 底部导航 > 历史（pages/history/history） | 加载失败先 toast（`err.message`），随后条件直接把界面渲染成通用空态「暂无历史节目」（wxml:72-74），把"取不到"说成"没有"；这一模式在 search/channels/course/recent/preferred 上重复出现（见 J101） | apps/miniprogram/pages/history/history.wxml:72-74 | XS |
| J38 | 搜索（pages/search/search） | 首次搜索期间屏幕空白：空态条件 `!loading && keyword && results.length===0`（wxml:50）在加载中为假、结果未达为 0 时列表也不渲染，唯一的 loading 文本藏在底部 `load-more`（84-85），用户按下搜索后对着空页面等待 | apps/miniprogram/pages/search/search.wxml:50,84-85 | S |
| J39 | 搜索（pages/search/search） | 失败被表述为无结果：`doSearch` catch 里只 toast `err.message \ | \ | S |
| J47 | 我的频道（pages/channels/channels） | 失败先 toast「加载失败」（js:47）再落到「暂无可用频道」空态（wxml:21-22），该空态无重试按钮（重试只在骨架超时块，wxml:16），一次性失败即被固化为"没有频道" | apps/miniprogram/pages/channels/channels.js:47；apps/miniprogram/pages/channels/channels.wxml:16,21-22 | XS |
| J106 | J-附 跨页组件 / 服务 / 生命周期 | 全站"错误伪装成空态"模式：`api.js` 失败时抛出固定串（「网络异常」「请求超时」「登录失败，部分功能不可用」），各页统一做法是 toast 一句然后落到"暂无 ××"空态——history/search/channels/course/recent/favorites/preferred/download 八页同型（J16、J39、J47、J61、J65、J71），用户学会不了"空"和"坏"的区别 | apps/miniprogram/services/api.js（`_rawRequest` fail 分支）；apps/miniprogram/pages/history/history.wxml:72-74；apps/miniprogram/pages/search/search.js:117；apps/miniprogram/pages/channels/channels.js:47 | M |
| M2 | 维护工具 > 参数计算器 | 「应用到 AI 配置」的有效区间与目标页不一致且**静默夹取**：本页允许时长 60–1800s、倍率 0.5–2.5x，而 AIConfig 接收时把 `duration` clamp 到 180–1200s、把倍率换算成 `edge_rate` 百分串（2.5x→"+150%"，超出其滑杆 -50~100 范围），但 toast 仍报「已从参数计算器同步：目标时长、语速倍率」，用户以为按自己填的值带过去了 | ParamCalculator.vue:60-62,161-162,306-314；apps/admin-web/src/views/ai/AIConfig.vue:1546-1559,406-413 | S |
| M71 | 维护工具 > 系统清理 > 存储状态卡 / 结果区 / 空态 | 状态接口失败即伪装成「干净」：`loadStatus` catch 只 `console.error`，`status` 为 null 时三卡显示 `-` 与 `0 条 / 0 个`，运维会读成「数据库 0 条日志、无需清理」；若是二次刷新失败，更糟——**继续展示上一次的旧数值且无任何过期标记**，据此判断清理效果会得出错误结论 | Maintenance.vue:23-57,289-298 | S |
**R2 加载失败回落默认值后保存即覆写（1 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| A12 | 一级：新手引导体系 | `/workflows` 引导第 2 步选择器 `[aria-label="立即触发一期工作流"]` 与其承诺文案「点击触发按钮…」指向的按钮不匹配：该 IconButton 实际 `aria-label` = `label="手动触发"`（desc 才是"立即触发一期工作流"，不进 aria-label），主选择器命中不到，回落 `.top-bar .el-button` 会高亮到 top-bar 里第一个按钮即「重置」，把用户指向错误按钮（该页还含危险的「全频道启动/手动触发」） | apps/admin-web/src/guide/guideConfig.js:69-73; views/workflow/WorkflowList.vue:54,67-75; components/IconButton.vue:20,71-72,93 | XS |
**R4 枚举/引导/文档与实现漂移（22 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| B1 | 内容运营 > 内容审核 · 列表主体 | 后端 `ReviewStatus` 有第 4 态 `replaced`，但列表只有 3 个 tab（pending/approved/rejected），`statusText/statusTagType` 也无 `replaced` 映射。详情页做「替换段落」后该记录状态变 `replaced`，从所有 tab 消失，运营再也找不到、无法追溯，误以为数据丢失 | apps/admin-web/src/views/review/ReviewList.vue:4-7,180-186；backend/app/models/review.py:14-17；backend/app/services/review_service.py:269 | S |
| C45 | 内容运营 > 素材库管理（列表 / 筛选 / 分页 / 视图切换，路由 /channels/material-library） | 全链路术语在最关键处漂移：菜单叫「素材库管理」，本页右上角按钮叫「手动录入素材」，讲书稿池 tips 却要求"新书素材请到『素材录入』上传"，而「素材录入」是另一个菜单页；同一页内又出现「素材池」（后端 docstring：素材是频道级素材池）。首次用户无法判断"库/池/录入"是几个对象 | apps/admin-web/src/views/channel/MaterialLibrary.vue:5-9,262；apps/admin-web/src/views/channel/BookPoolPanel.vue:86；apps/admin-web/src/router/index.js:93-112；backend/app/routers/admin/materials.py:211-213 | S |
| C84 | 讲书稿素材池 > 「从素材库加入书籍」候选弹窗 | 候选固定 `page:1, size:50`，界面没有任何翻页控件也不显示总数（后端返回 `total` 被丢弃）：本频道书多于 50 本时，第 51 本起"不存在"，运营会判定"素材库里没有这本书" | apps/admin-web/src/views/channel/BookPoolPanel.vue:303-315,107-132；backend/app/services/book_pool_service.py:359-360,394 | S |
| C103 | 内容运营 > 找书工具 | 「加入待讲书单」名字与落库位置完全不同：按钮/列名都叫"待讲书单/加入书单"，而实际写入的是素材库一条占位素材（`source_type='book_plan'`、`channel_id=req.channel_id`），前端调用不传 `channel_id` → 落库为 null。结果：它既不在「讲书稿素材池」书单里（候选按 channel_id 过滤），也不在任何"书单"界面上，只能在全频道视图的素材库里靠书名搜到。首次用户点完按钮以为书已排上，链路实际断在这里 | apps/admin-web/src/views/ebooks/BookFinder.vue:118-130,209-228；backend/app/routers/admin/ebooks.py:145-188,40-47；backend/app/services/book_pool_service.py:345-352 | M |
| D16 | 广告管理 > 投放规则 | 素材下拉硬截断为 `page=1&size=100`，第 101 条起的素材在列表里根本不存在，`filterable` 只能在已加载的 100 条内搜索，且无任何「仅显示前 100 条」提示 → 运营会认定「素材没上传成功」 | apps/admin-web/src/views/ad/AdPlacements.vue:59-71；:171-176；backend/app/routers/admin/ads.py:36-37 | S |
| G1 | 系统配置 > 内网穿透 | 「二进制下载失败」引导块与「Tailscale Funnel 需要授权」引导块**永不渲染**：后端 `/tunnel/start` 下载失败/需授权时返回 HTTP 200 + `{code:5001/5003,data.error_type,...}`，但拦截器把 `code!==0` 当作业务错误 `reject(new Error(message))`，`handleStart` 里 `error?.response?.data |  | M |
| H2 | 云端存储 > 云端配置 | Bucket 输入框 placeholder 承诺「不含 -{appid} 后缀亦可，系统按 SecretId APPID 拼接」，但后端将 COS_BUCKET 原样传给 SDK，全仓无任何 appid 拼接逻辑 → 首装用户按文案省略后缀，保存后所有操作报「存储桶不存在」，无从排查 | apps/admin-web/src/views/cos/CosConfig.vue:101-103；backend/app/cos/client.py:63 | S |
| I27 | 壳层 | tabBar 各 item **无未读角标**（审批待办数、消息未读数都不体现）：外勤停在审批 tab 时无法感知有新消息/新待审，必须逐个 tab 点进去看 | apps/admin-web/src/layouts/MobileLayout.vue:11-22 / 35-45 | M |
| J1 | 底部导航 > 今日节目 | 底部导航只有图标、无文字：三个 tab 项均未声明 `text`，「今日/历史/我的」全靠图形猜测；`tab-today/history/profile` 三个图标在小尺寸下辨识度低，新用户首次进入无法预判第二个 tab 是播放记录还是节目库，而这两者恰好各有两套实现（见 J14、J63） | apps/miniprogram/app.json:33-49 | XS |
| J5 | 底部导航 > 今日节目 | 播放中浮条在首页不出现：`floating-player` 只在 `attached` 调用 `_refresh()` 计算 `visible`/`episode`，两个订阅回调只 setData `isPlaying` 与进度角（js:24-36），组件无 `pageLifetimes.show`；tab 页组件 attach 一次后常驻，从详情播放返回首页时 `visible` 仍为旧值 false → 浮条整条不显示，用户失去暂停/续播入口 | apps/miniprogram/components/floating-player/floating-player.js:21-37,45-58；apps/miniprogram/pages/index/index.wxml:155 | S |
| J14 | 底部导航 > 历史（pages/history/history） | 与「最近播放」页职责重叠、数据源不同：本页取节目库 `fetchHistory`（可作为"我关注的频道都更新了什么"），recent 取 `localData.getHistory` 播放记录；两者名称都指"过去"，用户从底部 tab 进历史后找不到"我昨天听到的那一集"，反而要退回"我的"再点「查看全部 ↗」 | apps/miniprogram/pages/history/history（fetchHistory）；apps/miniprogram/pages/recent/recent（localData.getHistory）；apps/miniprogram/pages/profile/profile.wxml:132 | M |
| J63 | 偏爱频道设置（pages/preferred-settings/preferred-settings） | 未登录时保存只会 toast「请先登录后再设置偏爱」（js:onSave），页面不出现登录按钮、不跳 profile、不解释为什么必须登录；从首启引导进来的新用户在此被硬卡住，唯一出路是自行摸索底部 tab | apps/miniprogram/pages/preferred-settings/preferred-settings.js(onSave)；apps/miniprogram/app.js(needsPreferredOnboarding) | S |
| J64 | 偏爱频道设置（pages/preferred-settings/preferred-settings） | 底部栏三枚按钮全部图标化：全选/全不选（checks/x）、暂不设置、保存（✓+数量角标），wxml:40-57 只给 aria-label；这是引导流程的最终决策界面，"保存"与"暂不"两个相反动作只有图标差异 | apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:40-57 | XS |
| J68 | 最近播放（pages/recent/recent） | 与底部「历史」tab 构成同名职责重复且数据源不同（本页 `localData.getHistory` 播放记录，历史 tab `fetchHistory` 节目库）；入口只有 profile 面板的「查看全部 ↗」，从底部 tab 进来的用户不会知道这里还有一个更贴近"我听到哪了"的列表 | apps/miniprogram/pages/recent/recent.js(loadRecent)；apps/miniprogram/pages/profile/profile.wxml:132；apps/miniprogram/app.json:40 | M |
| J90 | 关于我们（pages/about/about） | 功能清单宣称「离线收听 · 下载后无网络也能听」，而下载条目点击需先经详情页网络取数（J59）；宣传与可实现行为不一致，断网场景正是这一宣传的承诺场景 | apps/miniprogram/pages/about/about.js:34；apps/miniprogram/pages/download/download.wxml:30 | S |
| J112 | J-附 跨页组件 / 服务 / 生命周期 | 「T00384 图标即按钮」的去文案改造被逐页无差别套用（代码注释可查，如 queue.wxml:7、webview.wxml:14、preferred-settings.wxml:40、course.wxml:54），结果是全端在导航（tabBar）、主操作区（详情页 6 chip）、终局决策（偏爱底栏）、失败兜底（webview）四类最需要文字的场景同时失字；而 aria-label 普遍存在，说明改造考虑了读屏却牺牲了 sighted 用户的可发现性 | apps/miniprogram/app.json:33-49；apps/miniprogram/pages/detail/detail.wxml:147-187；apps/miniprogram/pages/queue/queue.wxml:7-8；apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:40-57 | S |
| M20 | 维护工具 > 数据库维护 > 主界面（表浏览 / 行编辑 / 搜索排序 / 导入导出） | 时间戳列（`created_at`/`updated_at`）在编辑弹窗里是普通可编辑文本，预填的是后端 `isoformat()` 出来的 `2026-10-17T22:01:00`；保存会把它作为字符串原样回写，与库中原有的空格分隔格式不同，而「保留天数」类清理与排序都直接对该列做字符串/时间比较——界面对「这列不建议改」零提示 | DatabaseAdmin.vue:200-213,666-678；db_admin_service.py:118-126,306-309；backend/app/services/maintenance_service.py:370-386 | S |
| M49 | 维护工具 > 数据库维护 > 导入弹窗 | 后端逐行错误 `errors:[{row,error}]` 完整返回，前端只取 `inserted/skipped` 拼 toast，用户永远看不到哪一行因何失败；`skipped` 同时混装了「主键冲突跳过」「非法行」「列名不匹配」三种语义 | DatabaseAdmin.vue:622-627；db_admin_service.py:452-481 | S |
| M77 | 帮助 > 帮助文档 | 内容审核步骤的按钮名不存在：文档写「通过：点击「审核通过」」「驳回：点击「驳回」，填写驳回原因」；实际界面是单选组 **通过 / 打回 / 替换段落** + 一颗「提交」按钮，全站 Tab/批量按钮也叫「已打回 / 批量打回」，「审核通过」「驳回」两个词在界面上都不存在，且文档漏掉「替换段落」这一动作 | Help.vue:199-201；apps/admin-web/src/views/review/ReviewDetail.vue:108-129；apps/admin-web/src/views/review/ReviewList.vue:4-6,22,32 | XS |
| M82 | 帮助 > 帮助文档 | 「API 文档」按钮指向不存在的入口：`window.open('/docs')`，而后端 `docs_url` 仅在 `is_dev`（`APP_ENV=="development"`）开启，生产打包后 `/docs` 落到 SPA fallback 返回 index.html——新标签页打开的是运营后台/登录页而非文档；此外前端 base 是 `/news/`，绝对路径 `/docs` 在 Funnel 路径区分模式下也不对 | Help.vue:552-554；backend/app/main.py:1318；backend/app/config.py:539-541；apps/admin-web/src/router/index.js:301；main.py:1460-1478 | S |
| M84 | 帮助 > 帮助文档 | COS 章节命令路径错误：「验证凭证：`python jmeter_test/verify_cos.py`」「迁移历史音频：`python jmeter_test/migrate_audio_to_cos.py`」，两个脚本实际在 `scripts/jmeter_test/` 下，仓库根没有 `jmeter_test/` 目录，照抄命令必然报「文件不存在」 | Help.vue:491-492；scripts/jmeter_test/verify_cos.py；scripts/jmeter_test/migrate_audio_to_cos.py | XS |
| M96 | 帮助 > 关于 | 5 个外链是占位假地址：用户协议 `https://example.com/terms`、隐私条款 `https://example.com/privacy`、联系我们 `mailto:dev@example.com`、官方社区 `https://example.com/community`、报告问题 `https://example.com/issues/new`，都带外链箭头且可点击，点了就是打不开/发给不存在的邮箱；「API 文档 `/docs`」同样不可用（见 M82，生产 `docs_url=None` 且未带 `/news` 前缀） | About.vue:205-214,210；backend/app/main.py:1318 | S |
**R5 统计口径与单位误读（13 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| C17 | 频道管理 > 新增/编辑频道弹窗（四页签表单） | 频道图标不显示：`_channel_to_dict` 未序列化 `icon_url`，编辑回填 `row.icon_url` 恒为空 → 每次打开编辑弹窗，图标区都显示「无图标」，运营以为图标丢失并重复上传/重复 AI 生成（每次生成有成本） | apps/admin-web/src/views/channel/ChannelManagement.vue:921,144-156；backend/app/routers/admin/channels.py:329-358（无 icon_url） | XS |
| C92 | 内容运营 > 素材录入 | 文案与实现不符（去重渠道）：「二维码 / 链接分享」页签写「复核后转『手动录入』正式入库（source_type=qrcode）」，预填提示也重复这一说法；但手动录入提交固定 `source_type:'list'`，`qrcode` 永远不会产生。素材库「来源类型=二维码/链接分享」筛选因此恒为空 | apps/admin-web/src/views/channel/CourseMaterials.vue:171-174,300-309,374；apps/admin-web/src/views/channel/MaterialLibrary.vue:286-293 | S |
| C114 | 跨页数据链、批量导入导出与文档/引导一致性（汇总） | 同一实体（Material）在三个界面被三种名字与三套字段编辑：菜单「素材库管理」/后端 docstring「频道级素材池」/工作流详情面板「爬虫采集 · 素材」；且字段口径不同——工作流详情用「品类」+「待处理/已选中」+ 必填 URL，素材库管理用「分类」+「待消费/已选题」+ 无 URL 字段。同一条素材在两处看起来是两种东西，改一处另一处需手动刷新（各页有「刷新」与否也不同） | apps/admin-web/src/views/channel/MaterialLibrary.vue:167-205,303；apps/admin-web/src/views/workflow/WorkflowDetail.vue:81-108,344-390,574；backend/app/routers/admin/materials.py:211-213 | M |
| D23 | 广告管理 > 排期日历 | 已停用的投放仍出现在日历上：后端 `get_schedule` 只按日期区间过滤、不看 `enabled`，前端也无任何标记 → 运营在日历看到某天写着「品牌口播A」，实际该规则已被停用，据此判断「广告还在投」属误读 | apps/admin-web/src/views/ad/AdSchedule.vue:77-100；backend/app/services/ad_service.py:200-204 | S |
| D33 | 数据分析 > 数据统计 | 「平均收听(分钟)」显示的是**秒**：后端取 `AVG(play_log.duration)`，该列模型注释为「本次会话已播放时长（秒）」，前端直接贴「(分钟)」标签不做换算 → 数值虚高 60 倍（平均 300 秒被读成 300 分钟） | apps/admin-web/src/views/stats/StatsOverview.vue:84；backend/app/services/stats_service.py:42；:53-55；backend/app/models/play_log.py:32 | XS |
| D34 | 数据分析 > 数据统计 | 同一指标两处单位不一致：概览卡把 `completion_rate` ×100 显示为百分数，趋势图把后端原始 0~1 序列（`func.avg(PlayLog.completed)`）直接画线，系列名却叫「完播率(%)」，Y 轴刻度是 0.00–1.00 → 卡片写 62.5、图写 0.625 | apps/admin-web/src/views/stats/StatsOverview.vue:83；:96-100；:104-131；backend/app/services/stats_service.py:85-86 | S |
| D39 | 数据分析 > 数据统计 | 「广告曝光」是推算值 `play_count * 3`（后端注释「每期固定三段广告」），前端当作真实曝光埋点展示且无脚注 → 用其评估广告效果会系统性高估（无点击/完播口径） | apps/admin-web/src/views/stats/StatsOverview.vue:85；backend/app/services/stats_service.py:57-63 | S |
| D46 | 数据分析 > 频道健康度 | 跨页同名指标口径不同且无说明：卡片「RSS 源」计数来自频道配置 `channel.rss_sources` JSON 数组长度，而「RSS 源状态」页的「源总数」来自后端 `rss.yaml` 全局源清单 → 两页数字对不上，运营试图互相印证必然困惑 | apps/admin-web/src/views/stats/ChannelHealth.vue:60-61；backend/app/services/stats_service.py:208-215；apps/admin-web/src/views/stats/RssHealth.vue:160；backend/app/services/rss_source_service.py:28-51 | S |
| I48 | 移动端 > 队列监控 | 「去审核」`goReview` 把**队列任务主键 `t.id` 当作 `workflow_id`** 传入（`query:{workflow_id:t.id}`），审核页用其过滤 `params.workflow_id`。任务 id ≠ 工作流 id（PC 队列详情显示「任务 ID」，工作流另有 workflow_id 口径，见 WorkflowDetail 用 `route.params.id` 即真实 workflow_id），作用域审核页大概率过滤为空 → 显示「暂无待审内容 🎉」，误导管理员以为无待审 | apps/admin-web/src/views/mobile/ManageQueue.vue:79-84 ↔ ReviewList.vue:194-195 ↔ QueueManagement.vue:194 ↔ WorkflowDetail.vue:866 | M |
| J51 | 课程主页（pages/course/course） | 章节数被硬截到 50：`fetchHistory(1, 50, channelId, 'asc')`（js:165）只取首页 50 条且不做后续分页，长课程（听书常见 100+ 章）在此页只显示前 50 章；更糟的是下载条的 `12/30` 计数用的是 totalCount（js:66-68），列表与计数口径不一致，用户数得出"少了 70 章" | apps/miniprogram/pages/course/course.js:165；apps/miniprogram/pages/course/course.wxml:66-68 | S |
| J82 | 播放设置（pages/settings/settings） | 「占用 {{cacheSize}}」只等于 `wx.getStorageInfoSync().currentSize + ' KB'`（js:135），不含 `services/download.js` 落在 USER_DATA_PATH 的音频文件；本页"存储管理"显示的占用与下载页「占用 {{totalSizeLabel}}」是两个口径，且真实大头（音频）恰好没被计入 | apps/miniprogram/pages/settings/settings.js:135；apps/miniprogram/pages/download/download.wxml:8 | S |
| M62 | 维护工具 > 系统清理 > 三列清理卡片与 dry-run/执行 | 15s 超时 vs 分钟级操作：axios `timeout: 15000`（`src/api/index.js:17`），而 VACUUM / 大批量 DELETE 常超 15s（后端注释也提示 VACUUM 锁库直到完成）；前端先报「超时/清理失败」，后端仍在继续，用户以为失败会重复点击 → 重复锁库；整个过程中页面无进度、无「执行中请勿关闭」提示 | Maintenance.vue:323-343；api/index.js:16-17；maintenance_service.py:544-569；Help.vue:444-448 | M |
| M81 | 帮助 > 帮助文档 | 参数计算器章节整段与实际不符：文档写「输入目标时长（**分钟**），自动计算 LLM 应生成字数（**330 WPM 基线** ±10%）与 TTS 语速调节建议」；实际界面单位是**秒**、基线是 **210 字/分**、无 ±10% 容差，也没有「语速调节建议」这种输出，实际是「三选一锁定推导 + 应用到 AI 服务」。运维按文档理解会算错约 57% 的字数 | Help.vue:403-411；ParamCalculator.vue:20,58-66,221 | XS |
**R6 长任务/流式基本能力缺失（4 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| D56 | 数据分析 > RSS 源状态 | 搜索关键词生效后，汇总卡与 4 个 radio 计数仍显示全量数字（「全部（52）」「失败（6）」），而表格可能只剩 2 行 → 数字与行数不一致，看起来像筛选失效；且 `el-empty` 文案固定为「暂无 RSS 源」，搜索无匹配时会误判「源配置丢了」 | apps/admin-web/src/views/stats/RssHealth.vue:34-47；:153-164；:191-201；:131 | S |
| F19 | AI 自动化 > 智能助手 | **长回复必然失败**：`/ai/chat` 用全局 axios `timeout: 15000`，而后端模型调用超时取 `LLM_TIMEOUT_SEC`（可配至 120s）；超过 15s 的回答前端报 `timeout of 15000ms exceeded`，会话只留错误气泡、无任何内容，也无法停止/续传——问答主流程在正常长度回答上走不通 | apps/admin-web/src/views/ai/KnowledgeQA.vue:498-501；apps/admin-web/src/api/index.js:17；backend/app/services/ai_config_service.py:1535；backend/app/routers/admin/ai_config.py:53 | S |
| J27 | 节目详情（pages/detail/detail） | 缓冲等待态被计算但从未呈现：`isWaiting` 在 js:66 初始化、js:194 随播放器 waiting 事件更新，wxml 里没有任何节点引用它——弱网起播时界面看起来与"正常播放中"完全相同，进度环静止但无「缓冲中」提示，用户只能反复点播放键 | apps/miniprogram/pages/detail/detail.js:66,194；apps/miniprogram/pages/detail/detail.wxml（无 isWaiting 节点） | S |
| M94 | 帮助 > 关于 | **更新检查根本没工作，却宣称「已是最新」**：`REPO_URL` 默认为空串（`backend/app/config.py:138`、`backend/.env.example:19` 也是空），后端直接降级返回 `has_update=false, source='local', error="未配置 REPO_URL，跳过更新检查"`；前端把 `res.error` **完全忽略**（`about.js:30` 已把这个字段写进 JSDoc 说前端会用于诊断），`source==='local'` 落入 else 分支 → 按钮显示绿色「已是最新」。GitHub 403/超时/404 等降级路径同理，一律显示「已是最新」 | About.vue:300-336；backend/app/routers/admin/about.py:229-246；src/api/about.js:30 | S |
**信息架构与导航（tabBar/孤儿页/重复职责）（6 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| J12 | 底部导航 > 历史（pages/history/history） | 队列入口形态最差：一枚 `arrows`/列表图标 chip（wxml:40-41，仅 aria-label），全站唯一能把用户带到 `pages/queue/queue` 整页的入口就是它（detail 内是 modal、首页 `onOpenQueue` 未绑定），多数用户不会知道自己有一个"播放队列"页 | apps/miniprogram/pages/history/history.wxml:40-41；apps/miniprogram/pages/index/index.js:737 | S |
| J19 | 底部导航 > 我的（pages/profile/profile） | 游客拿不到合规与自助入口：`wx:if="{{!userInfo}}"` 分支只渲染登录卡（wxml:4-13），意见反馈、播放设置、关于我们、用户协议、隐私政策、退出登录全部位于 `wx:else`（15-210）之内；未登录用户既读不到隐私政策，也无法反馈或清缓存，而产品恰恰在首启就要弹隐私授权（`__usePrivacyCheck__: true`） | apps/miniprogram/pages/profile/profile.wxml:4-15,210；apps/miniprogram/app.json:55 | S |
| J20 | 底部导航 > 我的（pages/profile/profile） | 重复界面成组出现：「我的课程」有嵌入面板也有 course 页，最近/收藏/频道/下载/偏爱五项都既以 `secondList` 内嵌（wxml:117-133）又以整页存在（recent/favorites/channels/download/preferred-settings），两套渲染逻辑与两份取数代码；面板只显前 N 条、"查看全部"是唯一的升层提示 | apps/miniprogram/pages/profile/profile.wxml:117-145；apps/miniprogram/pages/recent、favorites、channels、download、preferred-settings | M |
| J66 | 偏爱频道设置（pages/preferred-settings/preferred-settings） | 与 channels 页构成重复（同一份频道清单、两套勾选语义），本页又不自述"偏爱会影响首页与历史的排序"，用户保存后回到首页看到的变化无法归因；两处勾选状态是否互相同步也不可见 | apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:20-40；apps/miniprogram/pages/channels/channels.wxml:40-62 | M |
| J76 | 播放队列（pages/queue/queue） | 整页事实上是孤儿页：唯一进入路径是历史页一枚无文字的列表图标 chip（history.wxml:40-41），首页 `onOpenQueue`（index.js:737）没有绑定到任何元素，详情页用的是自己的内嵌 modal（detail.wxml:330-367）；浮动播放器也不通向本页，多数用户从未到过队列页 | apps/miniprogram/pages/history/history.wxml:40-41；apps/miniprogram/pages/index/index.js:737；apps/miniprogram/pages/detail/detail.wxml:330-367 | S |
| J87 | 意见反馈（pages/feedback/feedback） | 「意见反馈」入口位于登录后的 profile 清单（profile.wxml:15-210 的 else 分支），游客既无法反馈首启隐私弹窗问题、也无法反馈播放故障，与 J19 同一处断裂 | apps/miniprogram/pages/profile/profile.wxml:15-210 | S |
**前后端契约字段不匹配（1 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| D15 | 广告管理 > 投放规则 | 日期范围可选「同一天」，提交后后端以 `start_date >= end_date` 拒绝并弹出原文 `start_date 必须早于 end_date`（暴露英文字段名，且未说明「至少跨两天」），单日投放实际无法创建、用户不知如何修正 | apps/admin-web/src/views/ad/AdPlacements.vue:84-92；:184-195；backend/app/services/ad_service.py:161-162 | S |
**深链/状态持久化/跨端丢参（7 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| B12 | 内容运营 > 审核详情 · 子页面 | 试听用原生 `<audio :src="detail.audio_url">` 直连远端 URL，未走 `getEpisodeAudioUrl/getAudioProxyUrl` 代理（这些助手仅 WorkflowDetail 在用）。打包/COS 态成品音频在私有桶、需 JWT+代理，直连会 403/CORS 失败且**无任何错误提示**：审核员看不到真实语音就盲批。缺 `@error` 处理、无加载态、无时长/采样点读数、无「重听」快捷 | apps/admin-web/src/views/review/ReviewDetail.vue:99-100；apps/admin-web/src/api/audio.js:5-11,65-69；对照 apps/admin-web/src/views/workflow/WorkflowDetail.vue:804-805 | M |
| D13 | 广告管理 > 投放规则 | 后端列表已返回 `enabled`（1/0），PC 表格无「状态」列、无开关，也没有按状态筛选：在移动端停用的规则在 PC 列表中与生效规则**完全同貌**，运营据此判断「这条还在投」 | apps/admin-web/src/views/ad/AdPlacements.vue:15-37；backend/app/services/ad_service.py:122；apps/admin-web/src/api/ads.js:12-14 | S |
| D69 | 数据分析 > LLM 重试指标 | 率值渲染无容错：`metrics.trigger_rate.toFixed(2)` 直接对后端字段调 `.toFixed`，而赋值是 `{...defaults, ...data}` 整体浅合并 —— 若后端把该字段返回为 `null` 或字符串，合并后即为 null/字符串，渲染阶段抛 TypeError 使整页白屏（正是注释想防的「缺字段」场景，只防了 key 缺失、没防值为 null） | apps/admin-web/src/views/stats/LlmMetrics.vue:104-126；:189-202 | XS |
| E12 | AI 自动化 > 工作流详情 | 「返回」按钮用 router.back()：直接输入/新标签打开/刷新 /workflows/xxx 深链时无历史栈，点返回无任何反应；页面标题被去掉、无面包屑，「工作流详情」菜单项又 hidden，唯一退路是手改地址栏——深链值班路径走不通 | apps/admin-web/src/views/workflow/WorkflowDetail.vue:3-8；apps/admin-web/src/router/index.js:131-136 | S |
| I19 | 移动端 > 消息 | 点击消息 `open()` 仅标记已读、对已读/审批类消息直接 `return`，注释写「已读项若带深链可跳转（如审批详情）」但无任何跳转实现：外勤点开「审批提醒」消息无法直达对应待审项，流程断在这里 | apps/admin-web/src/views/mobile/Message.vue:63-71 | M |
| J69 | 最近播放（pages/recent/recent） | `onShow` 每次都 `loadRecent(true)` 重新加载并重置分页，从详情返回即丢失滚动位置与已翻页数据，用户"听完一集回去找刚才那集"需重新下滑 | apps/miniprogram/pages/recent/recent.js(onShow) | S |
| M88 | 帮助 > 帮助文档 | 搜索只匹配标题与简介（`s.title / s.intro`），正文里才有关键词的内容一律搜不到：搜「CONFIRM_DELETE」「VACUUM」「COS」「密钥」都会返回「未找到匹配的章节」，而这三项在文档正文里都有 | Help.vue:544-550,423,442,454 | S |
**其他高危（19 条）**

| # | 界面小节 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| C15 | 频道管理 > 新增/编辑频道弹窗（四页签表单） | 新增模式下「启用」开关完全无效：`createChannel` 请求体不含 `is_active`，后端 `ChannelCreateRequest` 也没有该字段。用户把开关关掉再创建，得到的是一个已启用频道，且提示只有「已创建」 | apps/admin-web/src/views/channel/ChannelManagement.vue:107-109,1019-1038；backend/app/routers/admin/channels.py:58-103 | S |
| C18 | 频道管理 > 新增/编辑频道弹窗（四页签表单） | AI 推荐类按钮保存时机不一致且与取消语义冲突：「AI 推荐 BGM」「AI 推荐 RSS 源与关键词」调用后立即 `updateChannel` 落库（提示「已保存」），但底部「取消」按钮 desc 写「关闭弹窗，放弃修改」；用户点取消后配置其实已经生效 | apps/admin-web/src/views/channel/ChannelManagement.vue:1182-1186,1220-1224；507 | S |
| C27 | 频道管理 > 讲书稿素材池子弹窗（嵌套 BookPoolPanel） | 共用的 `BookPoolPanel` 里没有模式开关（模板只有状态 alert），但组件内仍保留 `scriptMode/modeLoading/onToggleMode` 三个未使用状态/方法；因此子弹窗内只能"看池、改排序"，开/关模式必须回到外层页签的开关——用户在同屏看到两处与模式相关的提示，却只有一处能操作 | apps/admin-web/src/views/channel/BookPoolPanel.vue:3-24（无开关）,186-187,244-256（死代码）；apps/admin-web/src/views/channel/ChannelManagement.vue:302-324 | S |
| C37 | 频道管理 > BGM 选择 / 上传 / 试听 / AI 推荐（「音频与 BGM」页签） | 试听必然失败：`bgmPreviewUrl` 拼 `/bgm/${path}`，既未走 `assetPreviewUrl()` 的 `/news` 前缀约定，Vite dev proxy 也没有 `/bgm` 或 `/news/bgm` 条目，后端静态挂载在裸 `/bgm`。开发态（5181）请求打到 Vite → 404；生产经 Funnel 只路由 `/news/*` → 同样 404。同一问题已在预制封面处修过并注明原因，BGM 漏改 | apps/admin-web/src/views/channel/ChannelManagement.vue:670-673,792-802,1121-1136；apps/admin-web/vite.config.js:36-63；backend/app/main.py:1431 | XS |
| C66 | 内容运营 > 讲书稿素材池 | 页面源码注释与实现不符：`BookPool.vue` 顶部注释与卡片内注释均写「讲书稿模式开关在下方面板内」，实际面板没有开关（见 C27）；本页因此没有任何"开启模式"的操作点，只有 alert 里那句"开启后忽略书源…"的描述 | apps/admin-web/src/views/channel/BookPool.vue:6,35；apps/admin-web/src/views/channel/BookPoolPanel.vue:3-24,244-256 | S |
| D36 | 数据分析 > 数据统计 | 筛选作用范围无标注：日期选择器只刷新卡片，趋势卡永远基于 `date.today()` 往前 N 天（后端不使用 date 参数），页面上既没写「近 7 天（截至今日）」，切换日期后趋势图纹丝不动 → 运营以为两者联动 | apps/admin-web/src/views/stats/StatsOverview.vue:5-13；:147-158；backend/app/services/stats_service.py:75-77 | S |
| D45 | 数据分析 > 频道健康度 | 每张卡片的 mini 折线 Y 轴独立自适应且 `x/y` 全部 `display:false`，无刻度、无最大值标注、无日期轴 → 两卡片曲线形状相似却可能相差百倍量级，视觉斜率完全不可比，首次用户会据此判断「A 频道比 B 频道活跃」 | apps/admin-web/src/views/stats/ChannelHealth.vue:119-131；:70-80 | S |
| I5 | 移动端 > 审批 | 移动端列表卡片缺失 PC 端已有的关键质量信号：`measured_duration_sec`（时长）与 `supplement_sec`「凑时」标记（PC 用 tooltip+warning tag 提示成品时长不代表真实内容长度）。外勤在移动端审批时看不到「凑时」，可能把凑时长的节目判为合格 | apps/admin-web/src/views/mobile/ReviewList.vue:49-54 / 80-100 ↔ apps/admin-web/src/views/review/ReviewList.vue:71-88 | M |
| I49 | 移动端 > 队列监控 | 统计「已完成」读 `stats.finished`，但 PC `/queue/stats` 用 `stats.success`（PC 卡片 `stats.success |  | S |
| J24 | 底部导航 > 我的（pages/profile/profile） | 登录按钮是 `btn-icon-only`（wxml:8，仅 aria-label「点击登录」），登录是本页唯一的转化动作，却没有任何文字；头像昵称编辑（213-262）里的取消/保存同样只用图标 aria-label 标注 | apps/miniprogram/pages/profile/profile.wxml:8,259-262 | XS |
| J28 | 节目详情（pages/detail/detail） | 课程语境字段同样算了不显示：`isCourse`/`courseName`/`chapterLabel`（js:80-83,130-133）与 1117 行的分享标题用到，界面却不显示「第 N 章 / 共 M 章 · 课程名」，用户从课程页点进某一章后失去坐标感，不知道自己在整门课的哪个位置 | apps/miniprogram/pages/detail/detail.js:80-83,130-133,1117-1118 | S |
| J32 | 节目详情（pages/detail/detail） | 详情加载失败态只有一段文本、无「重试」按钮；本页每次进入都重新网络拉取（无缓存兜底），断网从列表点进来只能看到失败文案 | apps/miniprogram/pages/detail/detail.json:2；apps/miniprogram/pages/detail/detail.wxml 错误态 | S |
| J45 | 我的频道（pages/channels/channels） | 页名与内容不符：`navigationBarTitleText` 为「我的频道」（channels.json:2），列出的却是全部频道及订阅态（wxml:61 已订阅/订阅）——"我的"暗示已订阅集合，用户找不到"只看我的"的开关，而那功能实际住在偏爱设置页 | apps/miniprogram/pages/channels/channels.json:2；apps/miniprogram/pages/channels/channels.wxml:61 | XS |
| J46 | 我的频道（pages/channels/channels） | 点资讯频道在用户视角"没反应"：`onTapChannel` 对 news 分支只写 `app.globalData.currentChannelId = id` 后 `switchTab` 到首页（js:105-106），而首页从不读取 `currentChannelId` 来切换选中胶囊/滚动定位，结果用户跳回首页看到的还是原样，且无任何 toast 说明"已切换频道" | apps/miniprogram/pages/channels/channels.js:105-106；apps/miniprogram/pages/index/index.js（未读取 currentChannelId） | S |
| J48 | 我的频道（pages/channels/channels） | 「订阅」（本页）与「偏爱」（preferred-settings）两个概念在界面上没有任何区分说明，卡片布局几乎一致，用户会以为自己已经设置成功、回首页却发现排序没变 | apps/miniprogram/pages/channels/channels.wxml:40-62；apps/miniprogram/pages/preferred-settings/preferred-settings.wxml:20-40 | M |
| J59 | 我的下载（pages/download/download） | 「已下载」不等于能离线播：条目点击是跳 `detail?id=&channelId=`（wxml:30），而详情页每次进入都重新网络拉取详情（J32），断网时点已下载的章节直接落到加载失败；「关于」页却把能力宣传成「下载后无网络也能听」（about.js:34） | apps/miniprogram/pages/download/download.wxml:30；apps/miniprogram/pages/detail/detail.js；apps/miniprogram/pages/about/about.js:34 | M |
| J73 | 我的收藏（pages/favorites/favorites） | 已下架节目只整体降透明度（`.item-unavailable`，wxml:21），没有「已下架」文字标签，点击行为也未说明；用户会误判为加载失败或界面卡死 | apps/miniprogram/pages/favorites/favorites.wxml:21 | XS |
| J81 | 播放设置（pages/settings/settings） | 「检查更新」的反馈不可信：无论是否真的检测到更新，都在 2000ms 后固定 toast「已是最新版本」（js:199），不等 `onCheckForUpdate` 回调结果；弱网下真有新版本也先报"已最新"，用户会以为功能坏了或版本永远不变 | apps/miniprogram/pages/settings/settings.js:173-199 | S |
| J99 | 隐私政策（pages/privacy/privacy） | 同一句里的第 4 条也不成立：「关闭某些数据收集（在设置中操作）」，但设置页只有播放/通知/存储三组（settings.wxml:39-52），没有任何数据收集开关，也没有埋点上报开关（utils/tracker 始终上报）；用户在隐私页读到的控制项在设置页找不到 | apps/miniprogram/pages/privacy/privacy.js:38；apps/miniprogram/pages/settings/settings.wxml:39-52；apps/miniprogram/utils/tracker.js | S |

### 13.2 逐界面小节问题计数（94 小节 / 634 条）

| 界面小节 | 高 | 中 | 低 | 合计 | 高危条目 ID |
|---|---|---|---|---|---|
| 一级：侧栏与页头壳层 | 0 | 0 | 4 | 4 | — |
| 一级：根组件端切换壳层 | 0 | 1 | 1 | 2 | — |
| 一级：移动端壳层 tabBar/标题栏 | 0 | 1 | 2 | 3 | — |
| 一级：路由/分组/守卫/404 | 0 | 1 | 2 | 3 | — |
| 一级：新手引导体系 | 1 | 1 | 2 | 4 | A12 |
| 一级：公共组件与 stores / message（ThemeSwitcher, IconButton, VoiceSyncButton; stores/theme, stores/user; utils/message） | 1 | 1 | 1 | 3 | A16 |
| 一级：登录 | 1 | 0 | 2 | 3 | A19 |
| 一级：长尾共性采样 | 0 | 1 | 3 | 4 | — |
| 内容运营 > 内容审核 · 列表主体 | 1 | 4 | 2 | 7 | B1 |
| 内容运营 > 内容审核 · 批量操作栏与确认弹窗（apps/admin-web/src/views/review/ReviewList.vue:10-37,212-287） | 0 | 3 | 1 | 4 | — |
| 内容运营 > 审核详情 · 子页面 | 1 | 5 | 1 | 7 | B12 |
| 内容运营 > 审核详情 · 采集图片与「查看全部」弹窗（apps/admin-web/src/views/review/ReviewDetail.vue:32-90） | 0 | 0 | 2 | 2 | — |
| 内容运营 > 队列管理 · 主体 | 1 | 5 | 2 | 8 | B21 |
| 内容运营 > 队列管理 · 任务详情抽屉与步骤时间线（apps/admin-web/src/views/queue/QueueManagement.vue:190-224） | 0 | 1 | 1 | 2 | — |
| API 封装层口径一致性 | 0 | 1 | 1 | 2 | — |
| 内容运营 > 频道管理 | 2 | 9 | 3 | 14 | C5, C10 |
| 频道管理 > 新增/编辑频道弹窗（四页签表单） | 4 | 6 | 2 | 12 | C15, C16, C17, C18 |
| 频道管理 > 讲书稿素材池子弹窗（嵌套 BookPoolPanel） | 1 | 1 | 1 | 3 | C27 |
| 频道管理 > 预制封面选择弹窗（cover picker） | 0 | 2 | 2 | 4 | — |
| 频道管理 > 频道图标（上传 / AI 生成） | 0 | 2 | 1 | 3 | — |
| 频道管理 > BGM 选择 / 上传 / 试听 / AI 推荐（「音频与 BGM」页签） | 1 | 3 | 2 | 6 | C37 |
| 内容运营 > 素材库管理（列表 / 筛选 / 分页 / 视图切换，路由 /channels/material-library） | 2 | 9 | 2 | 13 | C43, C45 |
| 素材库管理 > 编辑素材弹窗 / 手动录入素材弹窗 / 删除确认 | 1 | 4 | 1 | 6 | C56 |
| 素材库管理 > 空态与深链定位（含从讲书稿池跳入的上下文保留） | 0 | 3 | 1 | 4 | — |
| 内容运营 > 讲书稿素材池 | 2 | 3 | 2 | 7 | C66, C68 |
| 讲书稿素材池 > BookPoolPanel（模式状态 / 调度 / 进度 / 书单表 / 重置与预览） | 2 | 8 | 1 | 11 | C73, C80 |
| 讲书稿素材池 > 「从素材库加入书籍」候选弹窗 | 1 | 5 | 1 | 7 | C84 |
| 内容运营 > 素材录入 | 2 | 8 | 2 | 12 | C91, C92 |
| 内容运营 > 找书工具 | 1 | 7 | 2 | 10 | C103 |
| 跨页数据链、批量导入导出与文档/引导一致性（汇总） | 1 | 7 | 0 | 8 | C114 |
| 广告管理 > 广告素材 | 0 | 10 | 1 | 11 | — |
| 广告管理 > 投放规则 | 4 | 7 | 0 | 11 | D13, D14, D15, D16 |
| 广告管理 > 排期日历 | 3 | 4 | 3 | 10 | D23, D24, D25 |
| 数据分析 > 数据统计 | 5 | 5 | 2 | 12 | D33, D34, D35, D36, D39 |
| 数据分析 > 频道健康度 | 2 | 6 | 3 | 11 | D45, D46 |
| 数据分析 > RSS 源状态 | 1 | 9 | 2 | 12 | D56 |
| 数据分析 > LLM 重试指标 | 2 | 4 | 4 | 10 | D68, D69 |
| 组内共性问题（跨 7 个菜单，不重复计入上表） | 1 | 4 | 1 | 6 | D78 |
| AI 自动化 > 工作流监控 | 1 | 6 | 3 | 10 | E1 |
| AI 自动化 > 工作流详情 | 2 | 8 | 3 | 13 | E11, E12 |
| 两页共用弹窗与组件（el-dialog 触发结果框 / WorkflowProgressIndicator / 素材与分段编辑弹窗） | 0 | 0 | 1 | 1 | — |
| AI 自动化 > AI 服务 | 2 | 9 | 7 | 18 | F2, F3 |
| AI 自动化 > 智能助手 | 1 | 7 | 5 | 13 | F19 |
| 系统配置 > 内网穿透 | 2 | 3 | 2 | 7 | G1, G2 |
| 系统配置 > 通知管理 | 1 | 2 | 2 | 5 | G8 |
| 系统配置 > 自动审批 | 1 | 2 | 3 | 6 | G13 |
| 云端存储 > 云端配置 | 2 | 4 | 1 | 7 | H1, H2 |
| 云端存储 > 文件管理 | 2 | 6 | 1 | 9 | H8, H9 |
| a 文件管理 > 新建文件夹弹窗 | 0 | 0 | 1 | 1 | — |
| b 文件管理 > 重命名/移动弹窗 | 0 | 2 | 0 | 2 | — |
| c 文件管理 > 删除确认 / 空态 / 未配置态 | 0 | 0 | 2 | 2 | — |
| 移动端 > 审批 | 3 | 5 | 2 | 10 | I1, I2, I5 |
| 移动端 > 登录 | 0 | 2 | 2 | 4 | — |
| 移动端 > 首页 | 1 | 2 | 1 | 4 | I15 |
| 移动端 > 消息 | 1 | 3 | 1 | 5 | I19 |
| 移动端 > 我的 | 0 | 2 | 1 | 3 | — |
| 壳层 | 1 | 1 | 2 | 4 | I27 |
| 移动端 > 管理入口 | 0 | 1 | 2 | 3 | — |
| 移动端 > 用户管理 | 0 | 2 | 2 | 4 | — |
| b 移动端 > 用户反馈 | 0 | 2 | 2 | 4 | — |
| 移动端 > 频道管理 | 1 | 1 | 1 | 3 | I42 |
| 移动端 > 广告投放 | 1 | 1 | 1 | 3 | I45 |
| 移动端 > 队列监控 | 2 | 3 | 1 | 6 | I48, I49 |
| 移动端 > 应急停服 | 2 | 2 | 1 | 5 | I54, I55 |
| 跨端一致性 / 角色入口 / 深链 | 0 | 3 | 3 | 6 | — |
| 底部导航 > 今日节目 | 3 | 6 | 1 | 10 | J1, J4, J5 |
| 底部导航 > 历史（pages/history/history） | 4 | 3 | 1 | 8 | J11, J12, J14, J16 |
| 底部导航 > 我的（pages/profile/profile） | 4 | 4 | 0 | 8 | J19, J20, J21, J24 |
| 节目详情（pages/detail/detail） | 4 | 6 | 1 | 11 | J27, J28, J29, J32 |
| 搜索（pages/search/search） | 2 | 5 | 0 | 7 | J38, J39 |
| 我的频道（pages/channels/channels） | 4 | 2 | 0 | 6 | J45, J46, J47, J48 |
| 课程主页（pages/course/course） | 1 | 6 | 0 | 7 | J51 |
| 我的下载（pages/download/download） | 2 | 3 | 0 | 5 | J59, J60 |
| 偏爱频道设置（pages/preferred-settings/preferred-settings） | 3 | 2 | 0 | 5 | J63, J64, J66 |
| 最近播放（pages/recent/recent） | 2 | 2 | 0 | 4 | J68, J69 |
| 我的收藏（pages/favorites/favorites） | 2 | 2 | 0 | 4 | J72, J73 |
| 播放队列（pages/queue/queue） | 2 | 2 | 0 | 4 | J76, J77 |
| 播放设置（pages/settings/settings） | 3 | 3 | 0 | 6 | J80, J81, J82 |
| 意见反馈（pages/feedback/feedback） | 1 | 2 | 1 | 4 | J87 |
| 关于我们（pages/about/about） | 1 | 2 | 2 | 5 | J90 |
| 用户协议（pages/agreement/agreement） | 0 | 1 | 2 | 3 | — |
| 隐私政策（pages/privacy/privacy） | 2 | 1 | 1 | 4 | J98, J99 |
| 查看原文（pages/webview/webview） | 1 | 3 | 0 | 4 | J105 |
| J-附 跨页组件 / 服务 / 生命周期 | 3 | 4 | 0 | 7 | J106, J107, J112 |
| 维护工具 > 参数计算器 | 1 | 8 | 3 | 12 | M2 |
| 维护工具 > 数据库维护 > 主界面（表浏览 / 行编辑 / 搜索排序 / 导入导出） | 4 | 9 | 2 | 15 | M14, M16, M20, M29 |
| 维护工具 > 数据库维护 > 删除确认弹窗（级联预览 + 令牌） | 4 | 2 | 2 | 8 | M31, M32, M33, M37 |
| 维护工具 > 数据库维护 > 新增/编辑行弹窗 + 表结构弹窗 | 0 | 5 | 2 | 7 | — |
| 维护工具 > 数据库维护 > 导入弹窗 | 4 | 3 | 1 | 8 | M46, M47, M48, M49 |
| 维护工具 > 数据库维护 > 空态 / 加载失败态 | 1 | 1 | 2 | 4 | M54 |
| 维护工具 > 系统清理 > 三列清理卡片与 dry-run/执行 | 3 | 8 | 2 | 13 | M58, M59, M62 |
| 维护工具 > 系统清理 > 存储状态卡 / 结果区 / 空态 | 1 | 3 | 2 | 6 | M71 |
| 帮助 > 帮助文档 | 7 | 7 | 3 | 17 | M77, M78, M80, M81, M82, M84, M88 |
| 帮助 > 关于 | 3 | 9 | 1 | 13 | M94, M95, M96 |

### 13.3 汇总优先级矩阵（三）：排期建议

把 142 条高危按根因归成 7 个可独立交付的批次。**批次顺序即建议排期顺序**，判据是「不修会造成不可逆损失 / 用户根本走不通」优先于「体验更好」。

成本口径：`XS` ≈ 半小时内的单点改动；`S` ≈ 半天内（含自测）；`M` ≈ 1～2 天（跨前后端或需回归）。

| 批次 | 归入根因 | 高危条数 | 成本构成 | 建议排期 | 排序理由 |
|---|---|---|---|---|---|
| 第 1 批 | R3 + R2 | 10 | XS 1 / S 4 / M 5 | 本周内 | 唯一会**丢数据**的一类：数据库维护把 `password_hash` / API Key 覆写成字面量 `***`（M14），账号与密钥当场失效却提示「更新成功」；云端配置加载失败后点保存清空 Bucket/CDN（H1）。这一批修完，后续批次只剩「不好用」，不再有「用了就坏」。 |
| 第 2 批 | R7 | 39 | XS 6 / S 23 / M 10 | 第 1～2 周 | 39 条里含 3 处「功能本身失效」：移动端应急停服点确认永无反应（I54）、广告「停用」PC 端不可用且停用后 C 端仍播出（D14）、删除/清理类动作缺有效二次确认。属于「真要用的时候才发现不能用」，代价高于普通打磨。 |
| 第 3 批 | R1 | 21 | XS 6 / S 13 / M 2 | 第 2～3 周 | 21 条与前一批的失败路径共同收敛到 `utils/message.js` + `api/index.js` 两个文件，**改一处消解一片**。把「静默」变「可见」之后，第 1、2 批的修复才具备可验证的反馈面。 |
| 第 4 批 | R4 + 前后端契约字段不匹配 | 23 | XS 4 / S 14 / M 5 | 第 3～4 周 | 23 条集中在「前端写的与后端做的不是一个东西」：`replaced` 状态无 tab、引导锚点 `[aria-label]` 命中不到并回落到错误按钮（A12）、关于页 5 个 `example.com` 占位外链、帮助文档 8 处指向不存在的菜单（M83）。阻断的是首次使用路径，但不毁数据，故列第 4。 |
| 第 5 批 | R5 | 13 | XS 3 / S 7 / M 3 | 第 4～5 周 | 13 条，其中「平均收听(分钟)」实际取的是秒（D33）为 60 倍量级误读。修法全部是补单位、补口径说明、对齐字段，XS+S 占 10/13，可由前端单独并行插缝完成。 |
| 第 6 批 | 信息架构与导航（tabBar/孤儿页/重复职责） + 深链/状态持久化/跨端丢参 | 13 | XS 1 / S 8 / M 4 | 第 5～6 周 | 13 条：小程序底部 tabBar 三项无 `text`（J1）、孤儿页与重复职责、深链与跨端参数丢失。属配置与路由层的结构性调整，需一次成型再回归，拆碎做反而反复。 |
| 第 7 批 | R6 + 其他高危 | 23 | XS 4 / S 16 / M 3 | 第 7 周起 | 23 条：AI 对话未覆盖全局 15s 超时、工作流与清理预览缺断流收尾（4 条），其余 19 条是逐菜单独立缺陷（表单校验、分页 size、空态无行动指引等），彼此无公共修法，按菜单逐条消化。 |

7 批合计覆盖 142 / 142 条高危，无重复计入。

**中/低条目不单列批次**：它们的集中修法已包含在上述批次的同一处改动里（例如分页 `:page-sizes`、空态行动指引、toast 文案），建议在各菜单批次交付时**顺手带掉同小节的同类中/低项**，而不是单开一轮——13.4 的分布就是给这个「顺手带掉」用的清单口径。

### 13.4 中 / 低优先级条目的分布

中 344 条、低 148 条按菜单大类分布如下（与 13.2 同源，仅按大类聚合；成本列是该大类**全部条目**的成本构成，含高危）：

| 菜单大类 | 高 | 中 | 低 | 合计 | XS | S | M |
|---|---|---|---|---|---|---|---|
| 频道管理 / 素材库 / 讲书稿池 / 素材录入 / 找书工具 | 20 | 77 | 23 | 120 | 45 | 61 | 14 |
| 维护工具 3 菜单 + 帮助 2 菜单 | 28 | 55 | 20 | 103 | 31 | 56 | 16 |
| 小程序 18 页 | 44 | 59 | 9 | 112 | 39 | 58 | 15 |
| 广告管理 3 菜单 + 数据分析 4 菜单 | 18 | 49 | 16 | 83 | 31 | 44 | 8 |
| 移动端 `/m/*` 13 页 | 12 | 30 | 22 | 64 | 3 | 44 | 17 |
| 内容审核 + 队列管理 | 3 | 19 | 10 | 32 | 16 | 14 | 2 |
| AI 服务 + 智能助手 | 3 | 16 | 12 | 31 | 10 | 18 | 3 |
| 壳层 / 路由 / 引导 / 登录 / 公共件 | 3 | 6 | 17 | 26 | 17 | 9 | 0 |
| 工作流监控与详情 | 3 | 14 | 7 | 24 | 2 | 19 | 3 |
| 云端存储（云端配置 / 文件管理） | 4 | 12 | 5 | 21 | 6 | 8 | 7 |
| 系统配置（内网穿透 / 通知 / 自动审批） | 4 | 7 | 7 | 18 | 7 | 9 | 2 |
| **合计** | **142** | **344** | **148** | **634** | **207** | **340** | **87** |

读法：
- **中优先级最密集的三块**是内容运营组（77 条）、小程序（59 条）、维护工具+帮助（55 条）——共同特征是「表单/列表能用但每次都要多几步」：缺分页尺寸选择、缺批量入口、筛选项不持久、错误提示不指出去处。这些不需要新设计，按同小节批量补齐即可。
- **低优先级 148 条里有 79 条是 `XS`**（53%），且高度集中在壳层/登录/公共件（17 条低）与小程序、维护工具的文案与视觉一致性上——属「看一眼就能改」的措辞、间距、图标、空态插画类，适合攒一次统一收口，不值得单独立项。
- **`M` 成本的 87 条**不应理解为「都要做」：其中相当一部分是「补齐某个页面的分页 / 持久化 / 行动指引」，同一处公共组件改好后会连带消解；建议在做高/中批次时顺带评估，剩余再逐条排期。

### 13.5 未发现显著体验缺陷的对象

按任务要求逐菜单走查后，**没有任何小节被判为「零问题」**——每个界面至少命中 1 条低优先级的打磨项。下列 5 个小节的走查结论是「未发现显著体验缺陷」（无高、无中，只有 `XS` 级措辞/视觉建议），如实单列而不是跳过：

| 界面小节 | 低 | 说明 |
|---|---|---|
| A-1 一级：侧栏与页头壳层（路由：全部，文件：layouts/Layout.vue） | 4 | 侧栏/页头壳层：分组、折叠、主题切换、用户区职责清晰，问题只在「引导不可重新唤起」「无面包屑」等可发现性补充。 |
| B-4 内容运营 > 审核详情 · 采集图片与「查看全部」弹窗（apps/admin-web/src/views/review/ReviewDetail.vue:32-90） | 2 | 审核详情的采集图片区与「查看全部」弹窗：缩略图尺寸、预览、翻页在走查中未见阻断；仅建议补图片加载失败占位。 |
| E-3 两页共用弹窗与组件（el-dialog 触发结果框 / WorkflowProgressIndicator / 素材与分段编辑弹窗） | 1 | 工作流两页共用弹窗与组件：触发结果框、进度指示器、素材与分段编辑弹窗的行为与文案一致；仅建议补一条「关闭后仍在看板」的提示。 |
| H-2a 文件管理 > 新建文件夹弹窗 | 1 | 文件管理 > 新建文件夹弹窗：字段单一、校验存在、成功/失败有反馈；仅建议自动去首尾空格。 |
| H-2c 文件管理 > 删除确认 / 空态 / 未配置态 | 2 | 文件管理 > 删除确认 / 空态 / 未配置态：确认文案含文件名、未配置态给出去处；仅建议空态补一个主操作按钮。 |

另有 20 个小节「无高危、仅中/低」（合计 78 条），集中在移动端管理类页面（I-2 / I-5 / I-7 / I-8 / I-8b / I-13）、广告素材（D-1）、素材库空态与深链（C-9）、队列详情抽屉（B-6）、API 封装层（B-7）、频道图标与预制封面弹窗（C-4 / C-5）、用户协议页（J-16）、数据库维护的新增/编辑行弹窗（M-4）——这些页面的**主流程可用**，缺陷是「多几步 / 少个提示」，属于中低批次顺带收口的范围。

**未给出「无缺陷」判定的原因（诚实边界）**：本次是源码走查，视觉维度（对比度、间距、图标可辨识度、暗色主题下的实际渲染）无法从代码断言，按任务口径一律标「需实测确认」而非「无问题」。因此上述结论的适用范围是**信息架构、交互流程、反馈与数据安全**四个维度。

