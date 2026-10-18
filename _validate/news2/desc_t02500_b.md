来源：T02500（FR-UX-401 路由 meta 菜单校验脚本）

## 问题

门禁现在挂在 Vite `build` 的 `buildStart`（覆盖 `npm run build` 与
`scripts/build-frontend.ps1` 直连 vite 的两条路径），但：

- **dev 不挂**（有意为之：一条注释漂移不该让服务起不来），
- **提交前不跑**：仓库没有 ESLint（见 T02610）、没有 pre-commit 钩子，
  改坏引导/菜单引用的人要等到下一次打包才发现问题，
  而打包往往已经在发布流程里了。

## 要做的事

1. 把 `npm run validate:nav` + `npm run test:nav` 接进开发侧的强制点，二选一（择一落地即可，别两个都做）：
   - 首选：Playwright 全局前置——在 `apps/admin-web/tests/` 加一条 e2e（或在既有
     `guide-target.spec.js` 同目录新增 `nav-gate.spec.js`），`npx playwright test` 启动时
     由 `globalSetup` 跑校验脚本，失败即整套 e2e 红；这样本地 `npm run test:e2e` 与 CI 都覆盖。
   - 次选：仓库内最小 pre-commit 钩子（`.githooks/` + `core.hooksPath` 需在结果里说明未擅自改配置，
     由用户手工启用）。
2. 输出要可诊断：门禁报错已经能指出「哪个引导步骤、哪个选择器」，接入后请保持同样可读，
   不要只回一句 exit code 1。

## 验收

- 故意改坏一条引导 `aria-label` 后，走「日常开发会跑的那条命令」（`npm run test:e2e` 或钩子）能失败；
  验证完回滚。
