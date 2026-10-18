来源：T02493

排查背景：T02493 的同名覆盖确认之所以形同虚设，是因为 `CosFiles.vue` 调用了
`dangerConfirm(...)` 却没有 `import { dangerConfirm } from '../../utils/dangerConfirm'`。
Vue 模板/组合式 API 里这种「用了没导入」不会编译报错，运行时抛 ReferenceError 又被
全局 Promise 守卫吞掉，界面表现为「点了没反应」，直到 Playwright 断言确认框存在才暴露。

要做（系统性防复发）：
1. `apps/admin-web` 目前没有 ESLint（无 `.eslintrc*`/`eslint.config.*`，package.json 也没有
   `lint` 脚本）——引入 flat config + `eslint-plugin-vue`，显式打开 `no-undef`
   （含 `<script setup>` 的 vue 解析）与 `import/no-unresolved`；
2. 新增 `npm run lint`，并把它接入 `npm run build` 前置（或 CI 步骤），避免只本地手动跑；
3. 一次性全仓扫：`npx eslint "src/**/*.{vue,js}"`，把同类「引用未导入的本地 util」清零
   （重点：utils/dangerConfirm、utils/autoReviewRules、utils/message 这几个新增公共模块）；
4. 输出一份「引用了但未导入」的检查清单与修复 commit 链接，作为回归门禁基线。

验证：故意在任一 view 里引用未导入的 util，`npm run lint` 必须非零退出。
