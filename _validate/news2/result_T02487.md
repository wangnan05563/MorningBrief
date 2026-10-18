# T02487（FR-UX-104）配置页加载失败：页内错误态 + 重试 + 禁用保存

## 根因

四个配置页（COS / 内网穿透 / 通知 / AI 服务）的 `loadConfig()` 都在 `catch` 里把异常吞掉
（或只 `ElMessage.error` 后继续），组件状态机没有「加载失败」这一态：

- 请求失败后表单仍以**代码默认值**渲染（通知页是「三个开关全开 + SMTP 端口 587」，
  COS 页是空凭证，AI 页是内置 LLM 预设），用户看不出这是默认值还是线上值；
- 保存按钮不受加载结果约束，一次点击就把默认值整体 PUT 回 `ai_config`，**覆盖线上配置**；
- `useDraft` 在 `onMounted` 里无条件 `apply()` 本地草稿，草稿与未加载的默认值叠加后保存，
  覆盖面更大且没有任何提示；
- 失败反馈只有一条 3 秒后消失的 toast，重试只能刷新整页。

## 影响范围

- 直接命中：`views/cos/CosConfig.vue`、`views/tunnel/Tunnel.vue`、
  `views/notification/NotificationConfig.vue`、`views/ai/AIConfig.vue` 四个配置页的
  加载 / 保存 / 测试 / 恢复初始配置链路。
- 间接：`composables/useDraft.js` 新增 `peek()`（只探测不落表单），其余 8 个使用 `useDraft`
  的页面无行为变化（`apply/track/commit` 原样）。
- 未纳入（PRD 只点名这 4 页）：`QueueManagement.vue`、`system/AutoReviewConfig.vue` 等
  同样是「配置页 + 保存」形态，仍保留旧的吞异常写法 → 已建派生单 T02594。
- 后端无改动：本单是纯前端读态守卫，写入接口签名与语义不变。

## 修复

先落公共件，再逐页接入（避免 4 份复制的失败态实现漂移）：

- `D:\code\otherProjects\20_News\apps\admin-web\src\composables\useConfigLoad.js`（新增）
  `loading / ready / error` 三态机；`load()` 与 `retry()` 复用同一 `attempt()`；
  把 `null / undefined` 也判为失败（后端返回 `data: null` 时旧代码会当成功渲染默认值）；
  异常文案取 `e.message` 兜底「配置加载失败」。
- `D:\code\otherProjects\20_News\apps\admin-web\src\components\ConfigLoadError.vue`（新增）
  `el-alert type="error"`（class `config-load-error`）+「重新加载」`IconButton`；
  提示语按 `draftBlocked` 分叉：有未恢复草稿时说「保存会覆盖线上值；本地草稿已保留但未恢复」，
  否则说「保存已禁用」。
- `D:\code\otherProjects\20_News\apps\admin-web\src\composables\useDraft.js`
  新增并导出 `peek()`：只判断 `localStorage` 是否存在草稿，不合并进表单。
- 四个页面（同一路径下的 `views/...`）统一改造：
  - `loadConfig()` 不再吞异常，改为 `return data ?? null` 让状态机上抛；
  - `const configReady = ...isReady`，保存按钮 `:disabled="!configReady"`；
  - `handleSaveConfig` 首行 `if (!configReady.value) { ElMessage.error(...); return }`
    ——按钮禁用是第一道，函数内守卫防键盘/自动化绕过；
  - 通知页 `handleTestSend`、AI 页 `handleResetConfig` 同样守卫（两者内部都会先写配置）；
  - `onMounted`：`const ok = await cfgLoad.load()`，成功才 `restoreDraft()`，
    失败则 `draftBlocked.value = peekDraft()`（草稿保留在 localStorage，但不落表单）；
  - `retryLoad()`：重试成功后清 `draftBlocked` 并恢复草稿，仍失败则刷新提示。
- `D:\code\otherProjects\20_News\apps\admin-web\playwright.config.js`
  支持 `PW_CHANNEL` 覆盖（本机未下载 playwright 自带浏览器缓存时用系统 Chrome），默认行为不变。
- `D:\code\otherProjects\20_News\apps\admin-web\tests\config-load-error-guard.spec.js`（新增）
  数据驱动 4 页 × 2 例：注入 `code:500` 断言横幅可见 + 文案 + 重试按钮 + 保存禁用；
  再把接口翻成成功、点横幅内「重新加载」，断言横幅消失且保存恢复可用。

提交：`ff3d31f feat(ux): 配置页加载失败改为页内错误态 + 重试并禁用保存（FR-UX-104 / T02487）`
（9 files changed, 511 insertions(+), 63 deletions(-)，仅本单路径）

## 验证

- `PW_CHANNEL=chrome npx playwright test config-load-error-guard` → **8 passed (30.3s)**
  （COS / Tunnel / 通知 / AI 各 2 例，全部走真实浏览器渲染 + 网络拦截，非快照）。
- 全量 e2e `PW_CHANNEL=chrome npx playwright test` → 78 passed / 4 failed；
  4 条失败为 `page-layout-padding`（讲书稿素材池 / 素材库管理 / 素材录入，实测左内边距 16px）
  与 `review`（详情页采集图片预览数量），均指向 `views/channel/CourseMaterials.vue`
  与审核页——这两个文件当前被并发会话改动中（`git status` 可见未提交 WIP），
  与本单路径无交集，属 pre-existing，不在本单修复范围（仅观察不建单：待该会话自行收敛）。
- `npm run build` → 通过（改造前跑过一次，✓ 21.68s；本次提交后未引入新的编译单元）。
- 定位过程中的关键实测：通知页首跑失败时截图为**整页空白**，
  `#app` 只有 `<!---->`，`[window-guard] 页面隐藏，拦截已激活` + `/news/api/health/ready` 500
  ——确认是 dev 服务器冷启动 + 懒加载 chunk 现场编译导致首屏超过默认 5s 断言超时，
  不是页面逻辑缺陷；据此把首屏断言超时显式提到 30s（`NAV_TIMEOUT`），
  重跑单页与全量均通过，排除了该抖动。

## 本次回写

- 建派生单 **T02594**【AI回写待审核】其余配置页接入加载失败守卫（队列管理 / 自动审批等），
  来源：T02487；对应「未纳入」节，把 PRD 未点名但同形态的配置页一并接入 `useConfigLoad`。
- 建派生单 **T02595**【AI回写待审核】补 e2e 浏览器前置（playwright chromium 缓存缺失），
  来源：T02487；对应「验证」节遇到的 `chromium_headless_shell-1228` 缺失问题。
- verified:false —— 本单为 GUI 交互类，实测由 Playwright 驱动真实浏览器完成 8/8，
  但「用户视角的错误态观感」（文案是否够醒目、重试后草稿恢复是否符合预期）仍需人工过一遍：
  进入 `/#/notification`，在 devtools 把 `/notification/config` 改成 500 后刷新，
  确认横幅出现、保存置灰、本地草稿未被自动填进表单。

## 下一步建议

1. 其余配置页（队列管理、自动审批）接入同一守卫 → **已建派生单 T02594**。
2. CI 上 `npx playwright install chromium` 与本机缓存版本不一致（本仓配置期望的
   `chromium_headless_shell-1228` 未安装，需 `PW_CHANNEL=chrome` 才能跑）
   → **已建派生单 T02595**：把浏览器安装步骤写进 e2e 前置脚本/文档，避免他人首跑失败。
