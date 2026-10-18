来源：T02498（FR-UX-304 登录失败可见）

## 问题（T02498 修复过程中确认）

应用路径前缀（`/news`）在代码里是多处各自拼接的，口径不统一：

- `src/api/index.js` 401 分支：本次已改为按 `import.meta.env.BASE_URL` 推导登录页
  （dev base=`/`、生产 base=`/news/`）。
- 但同文件的 `axios baseURL` 仍是硬编码字符串 `'/news/admin/api/v1'`；401 跳转目标、
  路由守卫、以及部分视图里 `globalThis.location.href = '/news/...'` 之类拼接分散在多处。
- 后果已经在 T02498 实测过一次：硬编码前缀使 dev 下「当前是否已在登录页」永远判不成，
  401 会触发整页 `location.href` 刷新，把刚设置的错误横幅连状态一起刷掉
  （e2e 表现为偶发 `element(s) not found`，全量跑批复现、单跑不复现）。
  同一类分歧在其它路径判断上仍会复发。

## 要做的事

1. 抽 `src/utils/appPath.js`（或在既有 utils 下）：`loginPath(isMobile)`、`withBase(path)`、
   `isLoginPage(pathname)`、`apiBaseURL`，全部以 `import.meta.env.BASE_URL` 为唯一来源。
2. 把散落的 `/news` 字面量替换为上述函数：先 `grep -rn "/news" apps/admin-web/src` 列出完整
   改动点矩阵（含 `api/index.js`、路由/守卫、`views/login/*`、`views/mobile/*`、任何
   `location.href` / `window.open` / `<a href>` 拼接），逐条替换，禁止漏改。
3. 加构建期或测试期校验：dev 与 prod base 下，登录页判定与跳转目标必须一致
   （可用一条 e2e 断言：HTTP 401 在登录页不产生整页导航、URL 停留在 `.../login`）。
4. 与 T02500（路由 meta 菜单/帮助/引导构建期校验）区分边界：本单只管「路径前缀拼接口径」，
   T02500 管「菜单/文档引用的路由与 aria-label 是否存在」；落地时两者可共用同一校验脚本入口。

## 验收

- `grep -rn "'/news" apps/admin-web/src` 除 `vite.config.js`/文档注释外无业务代码命中。
- `npm run build` 通过；`PW_CHANNEL=chrome npx playwright test tests/login.spec.js tests/login-error-visible.spec.js --repeat-each=2` 全绿。
- 全量 e2e 相对本单开始前不新增失败。
