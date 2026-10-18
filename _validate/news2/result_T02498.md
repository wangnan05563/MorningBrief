# T02498 [PRD] 3.4 FR-UX-304 登录失败可见

## 根因

登录失败的「看不见」由三个各自独立的原因叠成，缺一条都仍表现为「点了没反应」：

1. **拦截器在登录页上对 401 只做跳转、不做提示**。`src/api/index.js` 的 401 分支原本是
   `if (!document.hidden && location.pathname !== loginPath) location.href = loginPath`——
   用户已经在登录页时这个条件本就为假，于是整个分支什么都不做，错误被 401 处理逻辑吞掉。
2. **登录页跳转判定硬编码了 `/news` 前缀**（`loginPath = '/news/login'`）。dev 下 Vite
   `base: '/'`，实际路径是 `/login`，永远 `!== '/news/login'`——于是 dev 下每次 401 都会
   触发 `location.href` 整页刷新，页面被刷走、状态清空，用户看到的是「表单被重置、没有任何提示」。
   这条也是新加的常驻横幅在跑批时偶发失效的直接原因（横幅刚 set 就赶上页面卸载，竞态）。
3. **失败原因只有一条 3 秒即散的 toast**（FR-UX-301 的 `ElMessage`），且失败后输入被清空、
   焦点丢失。移动端更严重：toast 位置在视口顶部，键盘收起后用户根本没往那边看。

## 影响范围

- 仅管理端前端（PC 登录页 + 移动登录页 + axios 响应拦截器 + user store 登录调用）。
- 后端未改动：登录失败已经统一返回 `code=401 用户名或密码错误` / `code=403 账号已禁用`，
  文案本身够用，问题全在前端显示通道。
- 拦截器 401 分支的跳转目标从硬编码改为按 `import.meta.env.BASE_URL` 推导，
  生产环境（`base='/news/'`）算出的路径与原来逐字相同（`/news/login`、`/news/m/login`），
  因此线上跳转行为不变；变的只是 dev 下不再误刷页面。

## 修复（绝对路径+改动点）

- `D:\code\otherProjects\20_News\apps\admin-web\src\utils\loginError.js`（新增）
  `describeLoginError(err)`：按「HTTP 403/禁用 → 401 → 超时 → 断网 → 兜底」的顺序归一成一句人话；
  优先透传后端 `response.data.message`，网络层错误（`Network Error` / `ERR_CONNECTION_*`）
  翻译成「无法连接服务器，请确认后端服务已启动、地址配置正确」，不把原始英文串抛给用户。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\login\Login.vue`
  表单项上方新增常驻错误横幅（`el-alert` + `role="alert"` + `data-testid="login-error"`，不可关闭）；
  `catch` 由「交给拦截器」改为 `loginError.value = describeLoginError(e)`，`nextTick` 后
  `passwordRef.focus()`；提交前清空上一轮原因；输入框不加任何 reset，保留用户已敲的账号密码；
  `.login-error` 样式与表单同宽。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\mobile\Login.vue`
  同样加常驻横幅（`<p role="alert" data-testid="login-error">`）、密码框 `ref` 与聚焦、保留输入。
- `D:\code\otherProjects\20_News\apps\admin-web\src\stores\user.js`
  `api.post('/auth/login', {...}, { silent: true })`：登录这条路径的提示出口收敛为登录页一处，
  不再叠一条会消失的 toast（与 FR-UX-301/303 的单一出口口径一致）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\api\index.js`
  401 分支重写：`loginPath` 由 `import.meta.env.BASE_URL` 推导，「是否已在登录页」改用路径后缀
  匹配（`endsWith('/login')` / `endsWith('/m/login')`），dev 与生产同一套判定；
  已在登录页（或页面隐藏不便跳转）且非 `silent` 时补 `ElMessage.error` + `_markNotified`，
  使 401 在这条支路上不再是静默失败。
- `D:\code\otherProjects\20_News\apps\admin-web\tests\login.spec.js`
  原「错误凭据显示错误提示」（断言 toast）改为断言常驻横幅 + `.el-message` 数量为 0 +
  输入保留 + 密码框聚焦。
- `D:\code\otherProjects\20_News\apps\admin-web\tests\login-error-visible.spec.js`（新增，6 例）
  业务码 401 / HTTP 401（不被 location.href 刷走）/ 403 账号已禁用 / 断网连不上后端 /
  重试成功后横幅消失并进入系统 / 移动端登录页同样常驻并聚焦。

提交：`15a988d`（path-limited，仅上述 7 个文件；并发会话的 `api/audio.js`、`CourseMaterials.vue` WIP 未裹挟）。

## 验证（实测证据）

- `PW_CHANNEL=chrome npx playwright test tests/login-error-visible.spec.js tests/login.spec.js --repeat-each=2`
  → **20 passed (57.0s)**（两轮全绿，含此前偶发失败的 HTTP 401 用例；证明刷页竞态已消除）。
- 全量 e2e：`PW_CHANNEL=chrome npx playwright test` → **133 passed / 4 failed (4.1m)**。
  4 条失败逐条核对为本次改动前既有问题（`page-layout-padding` 内边距 3 条 + `review` 详情页图片放大预览 1 条），
  已另立 T02628 跟踪；本任务相关的 12 条登录用例全部通过。
- 生产构建：`npm run build` → **EXIT=0，✓ built in 25.89s**（改动后复跑一次）。
^- 分支文案核对：横幅文案取自后端 `message`，`code=403` 显示「账号已禁用」、
  连接拒绝显示「无法连接服务器…」，均断言在 e2e 中逐条验证（非仅命令层推断）。
- **留待人工抽查**（故本单 verified:false）：e2e 断言的是 DOM 文本、URL、焦点与提示出口数量，
  没有覆盖视觉观感。请真人用真机/真实浏览器过一遍这两处：
  ① PC 登录页 `http://<host>/news/login` 连续输错密码 → 横幅出现后刷新前不消失、
  焦点确实在密码框、回车能直接重试；② 移动端视口（iPhone SE 宽）登录失败 →
  红色提示条与输入框不重叠、不被键盘遮挡、样式不跳位。

## 本次回写

- 无新增/变更 PRD 条目：FR-UX-304 实现即需求原文两条（可见原因 + 保留输入聚焦密码框）。
- 提交 `15a988d` 为本单唯一代码提交；留痕文档随后单独提交。
- 关联需求 `9725cae2`（FR-UX-304）由待办完成自动派生状态，未手工改需求矩阵。

## 下一步建议

1. **拦截器里的路径口径应统一到一处**——目前 `api/index.js` 用 `BASE_URL` 推导登录页、
   路由守卫与部分视图仍各自拼接 `/news` 前缀，属同一类硬编码（dev/prod 分歧隐患，
   本单的 HTTP 401 用例在跑批下偶发失败即由此而来）。
   建议抽出 `utils/appPath.js`（`loginPath()` / `withBase()`）并加校验。→ 已建派生单 T02633。
2. **登录失败缺「连续失败后的引导」**——现在每次都只重复同一句「用户名或密码错误」，
   用户不会知道自己是否被锁定、也没有找回入口。建议连续 3 次失败后追加「忘记密码/联系管理员」引导，
   并核对后端是否有失败计数与锁定策略。→ 已建派生单 T02634。
3. **全量 e2e 仍有 4 条既有失败**（内边距 3 + 审核详情图片预览 1），非本单引入，
   已由既有单 **T02628** 跟踪（复用不新建）；M3 收口后建议按该单一次性归零，
   否则后续每单都要重复人工区分「是否本单引入」。
