---
name: "news-frontend-code-review"
description: "对 MorningBrief 项目前端代码（admin-web/src/ 下 Vue 3/Element Plus 文件 + miniprogram/ 下微信小程序文件）进行全面评审与逻辑审查，覆盖组件规范、状态管理、API 契约、路由设计、类型安全、性能、可访问性、前后端字段契约、小程序生命周期、音频播放管理等维度。当用户要求'审查/检查/走查/把关/review/评估/看看对不对/规范不规范'前端 Vue/JS 代码、'.vue/.js 文件修改'、'迭代发布前前端走查'，或提到'前端评审/frontend review/Vue 代码审查/小程序代码审查'时调用。仅审查前端文件；纯后端 .py 文件审查请改用 news-backend-code-review。"
whenToUse: "需要审查 MorningBrief 前端代码（admin-web/src/ 下 .vue/.js 文件 + miniprogram/ 下 .js/.wxml/.wxss 文件）是否符合项目规范"
triggers: "前端代码 走查/审查/审核/把关/review/检查/评估 | .vue/.js 文件 修改/变更/迭代 走查 | 迭代发布前 前端 代码 走查 | 这段前端代码 写得对不对/规范不规范 | Vue/小程序 代码 review | 页面/组件/Store/路由 代码 审查"
version: "1.7.0"
updated: "2026-07-17"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# MorningBrief 前端代码审查

对 MorningBrief 项目前端代码进行全面的代码评审及逻辑审查，覆盖**运营后台（admin-web/，Vue 3 + Element Plus + Vite + Pinia）**与**微信小程序（miniprogram/，原生小程序）**两套前端代码。评审涵盖 **49 个维度**：目录结构、命名规范、Vue 3 组件规范、Element Plus 规范、Pinia 状态管理、API 调用规范、路由设计、前后端字段契约、小程序生命周期、小程序音频播放管理、小程序 API 层、性能、可访问性、代码质量、错误处理、频道级配置同步、前端验证脚本兼容性。

## 配置驱动

**核心原则**：所有评审规则、硬约束、项目规范均通过 `config.yaml` 管理，技能本身不含任何业务参数或硬编码值。新增规则只需修改配置文件，无需改动技能本身。

配置文件位置：`.trae/skills/news-frontend-code-review/config.yaml`

首次使用时，从同目录的 `config.example.yaml` 复制并按项目实际情况修改。配置项分为 8 大类：

| 配置类 | 职责 | 关键参数 |
|--------|------|----------|
| `scope` | 评审范围 | include_paths, exclude_paths, file_extensions, max_files_per_run |
| `priority` | 优先级排序 | severity_order, category_order, report_threshold |
| `hard_constraints` | 硬约束规则 | rules（可扩展列表，每条含 name/pattern/message/severity/auto_fix） |
| `checklist` | 评审检查清单 | 15 大类开关 |
| `abstraction_thresholds` | 抽象建议阈值 | inline_style_repeat, text_literal_repeat, function_max_lines 等 |
| `report` | 报告生成 | output_dir, format, include_good_practices, max_suggestions |
| `verify` | 验证配置 | run_tests_after_review, test_command, fail_on_critical |
| `project_conventions` | 项目专属规范参考 | tech_stack, field_contract_frontend, miniprogram_lifecycle 等 |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh .trae/skills/news-frontend-code-review/scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文件 | 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建议 |
| 全量审查 | `admin-web/src/**/*.{vue,js}` + `miniprogram/**/*.{js,wxml,wxss}` | 默认 |

---

## 审查规则（15 项维度）

### 1. 目录结构

**审查范围**：admin-web/src/ 与 miniprogram/ 的目录分层。

- 【强制】admin-web/src/ 下按 `views/`、`router/`、`api/`、`stores/`、`utils/`、`layouts/`、`styles/` 分层，禁止跨层反向依赖（如 views 引用 layouts 内部组件）
- 【强制】miniprogram/ 下按 `pages/`、`services/`、`components/` 分层，services 内禁止反向引用 pages
- 【强制】admin-web 页面文件用 PascalCase（如 `AdSchedule.vue`、`ReviewDetail.vue`）
- 【强制】miniprogram 页面用小写目录名（如 `pages/detail/detail.js`）
- 【强制】admin-web API 模块位于 `api/`，新增 API 归入子模块而非扩展 `index.js`
- 【强制】miniprogram 服务层位于 `services/`（`api.js`/`auth.js`/`audio.js`），禁止页面直接 `wx.request`

**判断信号**：
- `grep -r "from '\.\./\.\./layouts/" admin-web/src/views/` 发现 views 直接引用 layouts 内部 → 违规
- `grep -r "require('\.\./pages/" miniprogram/services/` 发现 services 反向引用 pages → 违规

### 2. 命名规范

- 【强制】Vue 组件文件 PascalCase（如 `AdSchedule.vue`、`WorkflowDetail.vue`）
- 【强制】API 模块 camelCase（如 `api/index.js` 导出的函数 `fetchTodayEpisode`）
- 【强制】Pinia store 用 `use*Store` 命名（如 `useUserStore`）
- 【强制】miniprogram 页面用小写目录名 + 同名 js/wxml/wxss
- 【强制】常量 UPPER_SNAKE_CASE（如 `BASE_URL`、`MAX_RETRY`）
- 【强制】事件处理函数 `on*` 前缀（小程序 `onPlay`、`onLoad`；Vue `@click="handleSubmit"`）

### 3. Vue 3 组件规范

- 【强制】使用 `<script setup>` 语法（项目规范，禁止 Options API 用于新组件）
- 【强制】Props 用 `defineProps` + 类型标注，事件用 `defineEmits`
- 【强制】组件名与文件名一致（`AdSchedule.vue` 内组件名 `AdSchedule`）
- 【强制】条件渲染合理选择 `v-if`（切换成本低、初始化重）与 `v-show`（频繁切换）
- 【强制】列表渲染用 `:key` 绑定稳定唯一标识（禁止用 index 作为 key）
- 【推荐】复杂逻辑用 `computed` 缓存，避免模板内函数调用
- 【推荐】副作用用 `watch`/`watchEffect`，且需在 `onUnmounted` 清理

```vue
<!-- ✅ 推荐：script setup + defineProps + defineEmits -->
<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  episode: { type: Object, required: true },
})

const emit = defineEmits(['play', 'pause'])

const isPlaying = computed(() => props.episode?.status === 'playing')
</script>
```

### 4. Element Plus 规范

- 【强制】表单验证用 `el-form` + `:rules` + `ref` 调用 `validate()`
- 【强制】表格用 `el-table` + `el-pagination` 分页，禁止一次性渲染全部数据
- 【强制】对话框用 `el-dialog` + `v-model` 控制显隐
- 【强制】消息提示用 `ElMessage`（轻提示）/ `ElMessageBox`（确认框），禁止 `alert`/`confirm`
- 【强制】状态标签用 `el-tag` + `type` 映射（success/warning/danger/info）
- 【强制】表单提交按钮加 `:loading` 防重复提交
- 【推荐】大量数据表格用 `el-table-v2`（虚拟滚动）

### 5. Pinia 状态管理

- 【强制】用 `defineStore` 定义，store 名与文件名一致
- 【强制】`state`/`getters`/`actions` 分离（Options API 风格，与项目现状一致）
- 【强制】跨组件共享状态用 store，禁止 props 多层透传（>2 层）
- 【推荐】持久化用 `pinia-plugin-persistedstate`，避免手动 `localStorage` 读写散落
- 【强制】store action 必须处理异常（try-catch 或调用方处理），禁止静默失败

```js
// ✅ 推荐：state/getters/actions 分离 + 持久化
export const useUserStore = defineStore('user', {
  state: () => ({ token: '', role: '' }),
  getters: { isAdmin: (state) => state.role === 'admin' },
  actions: {
    async login(username, password) {
      const data = await api.post('/auth/login', { username, password })
      this.token = data.token
      this.role = data.role
    },
  },
  persist: true,  // 持久化配置
})
```

### 6. API 调用规范

- 【强制】统一用 `api/` 模块封装，禁止组件内直接 `axios`/`fetch`
- 【强制】axios 实例配置 `baseURL` + 请求/响应拦截器
- 【强制】请求拦截器注入 `Authorization: Bearer <token>`
- 【强制】响应拦截器统一处理 `{ code, message, data }` 结构，`code !== 0` 视为业务错误
- 【强制】401 自动跳转登录页（清 token + replace），403 提示无权限
- 【强制】错误处理用 try-catch + `ElMessage.error`，禁止 `.catch(() => {})` 静默吞错
- 【推荐】路径判断用严格相等（`pathname === '/login'`），避免 `includes('/login')` 误匹配 `/login-callback`

```js
// ✅ 推荐：路径严格相等判断
if (globalThis.location.pathname !== '/login') {
  globalThis.location.href = '/login'
}

// ❌ 禁止：includes 过宽，会误匹配 /login-callback
if (!globalThis.location.pathname.includes('/login')) {
  globalThis.location.href = '/login'
}
```

### 7. 路由设计

- 【强制】路由懒加载（`() => import('../views/xxx.vue')`）
- 【强制】路由守卫（`beforeEach` 校验 token + 角色）
- 【强制】404 兜底路由（`{ path: '/:pathMatch(.*)*', redirect: '/review' }`），避免白屏
- 【强制】布局组件嵌套路由（`/` 下 `children`），`redirect` 到默认子路由
- 【强制】需要登录的路由 `meta.requiresAuth: true`，角色限制 `meta.requireRole: 'admin'`
- 【推荐】路由 name 唯一，便于 `router.push({ name: 'xxx' })`

### 8. 前后端字段契约

**核心原则**：后端返回 snake_case，前端直接用，**禁止**转 camelCase（与后端字段名保持一致是单一可信源）。

- 【强制】后端返回 snake_case 字段，前端直接用（如 `episode.audio_url`、`player.episode_id`）
- 【强制】Enum 值用后端返回的 `.value`，禁止前端硬编码字符串
- 【强制】日期字段用后端 ISO 格式（如 `2026-07-09T10:00:00Z`），前端用 `new Date(isoStr)` 解析
- 【强制】比率字段注意单位：完播率/进度等字段需确认是 0-1 还是 0-100，前后端一致
- 【强制】分类字段名前后端一致（`categories` vs `category` 需明确，禁止混用）
- 【强制】稿件字段名一致（`script` vs `content` 需明确，历史兼容需注释说明）
- 【强制】排期字段前后端结构一致（前端期望 `dates` map 还是 `placements` 数组，需与后端对齐）
- 【强制】工作流步骤字段名一致（`step_name` vs `name` 需明确）

**已知字段契约表**（详见 `config.yaml#field_contract_frontend.known_field_pairs`）：

| 后端字段 | 前端禁止用法 | 说明 |
|----------|--------------|------|
| `audio_url` | `audioUrl` | 音频地址（snake_case 透传） |
| `episode_id` | `episodeId`（前端变量可用，但取后端字段需用 `episode_id`） | 节目 ID |
| `categories` | `category` | 分类列表（复数） |
| `script` | `content`（历史兼容可 fallback） | 稿件内容 |
| `placements` | `dates`（结构不同） | 排期投放数组 |
| `step_name` | `name` | 工作流步骤名 |

### 9. 小程序生命周期

- 【强制】`onLoad`/`onUnload` 配对：`onLoad` 注册的监听器必须在 `onUnload` 中 `off`
- 【强制】`onShow`/`onHide` 处理页面可见性（如暂停音频播放、停止定时器）
- 【强制】全局 `player` 监听器必须在 `onUnload` 中 `off`（`offPlay`/`offPause`/`offTimeUpdate`/`offEnded`）
- 【强制】`globalData` 字段必须显式声明（如 `player: null`、`listenStats: null`），禁止运行时动态新增
- 【强制】`Page` 内事件回调保存为实例属性（`this._onPlay = () => {...}`），便于 `onUnload` 精确 `off`
- 【推荐】`onLoad` 接收 query 参数后立即校验（如 `if (!id) { showError(); return }`）

```js
// ✅ 推荐：onLoad/onUnload 配对 + 实例属性持有回调
onLoad(options) {
  this.bindPlayerEvents();  // this._onPlay = () => {...}
},
onUnload() {
  const player = getApp().globalData.player;
  if (player && this._onPlay) {
    player.offPlay(this._onPlay);
    player.offPause(this._onPause);
    player.offTimeUpdate(this._onTimeUpdate);
    player.offEnded(this._onEnded);
  }
  this._onPlay = null;  // 清除引用避免内存泄漏
},
```

### 10. 小程序音频播放管理

**核心机制**：全局单例 `player`（`app.globalData.player`），所有页面共享。

- 【强制】全局单例 `player`（`app.globalData.player`），`initPlayer` 在 `app.js onLaunch` 调用一次
- 【强制】`playEpisode` 设置 `episodeId`（`audioManager.episodeId = episode.id`），**禁止**用 `title` 判断当前节目（标题重复会误判）
- 【强制】`onCanplay` 监听器用后即 `off`（避免累积）：
  ```js
  const onCanplay = () => {
    audioManager.seek(startPosition);
    audioManager.offCanplay?.(onCanplay);  // 自清理
  };
  audioManager.onCanplay(onCanplay);
  ```
- 【强制】断点续播用 `startPosition`（从 `fetchPlayProgress` 获取），`completed === true` 时不续播
- 【强制】进度上报用 `onTimeUpdate`（每 5 秒定时器 + 暂停/结束时立即上报）
- 【强制】弱网降频：根据 `globalData.networkType` 调整上报间隔（wifi 5s，非 wifi 15s）
- 【强制】`isCurrentEpisode` 判断用 `player.episodeId === ep.id`，禁止用 `player.title === ep.title`
- 【推荐】`onEnded` 上报 `completed: true` + `position: duration`

### 11. 小程序 API 层

- 【强制】循环依赖处理：`api.js` 内 `require('./auth')` 延迟到 `request` 函数内部调用，禁止顶部 `require`（auth.js 加载时需要 request，顶部 require 会拿不到 `getToken`）
- 【强制】`BASE_URL` 按环境切换（`__wxConfig.envVersion === 'release'` 走生产，其余走开发），禁止硬编码单一环境
- 【强制】token 管理：`getToken`/`refreshToken`/`setToken` 集中在 `auth.js`，禁止散落
- 【强制】请求封装统一 header（`Content-Type: application/json` + `Authorization`）
- 【强制】401 自动 `refreshToken` 后重试原请求一次，失败则 reject 友好提示
- 【强制】业务错误（`code !== 0`）reject `Error(message)`，调用方 try-catch

```js
// ✅ 推荐：延迟 require 避免循环依赖
function request(options) {
  // 延迟 require：auth.js 加载时需要 request，顶部 require 会拿不到 getToken
  const { getToken, refreshToken } = require('./auth');
  const token = getToken();
  if (token) {
    header.Authorization = `Bearer ${token}`;
  }
  // ...
}
```

### 12. 性能

- 【强制】路由懒加载（`() => import()`）
- 【推荐】列表虚拟滚动（大数据量场景，如 `el-table-v2`）
- 【推荐】图片懒加载（小程序 `lazy-load` 属性，admin-web 用 `v-lazy` 或 IntersectionObserver）
- 【强制】搜索输入防抖（300-500ms），避免每次按键触发请求
- 【强制】小程序 `setData` 批量更新（合并多次 `setData` 为一次），避免频繁触发渲染
- 【推荐】小程序首屏加速：稿件懒加载（用户点击才请求 `fetchEpisodeScript`）
- 【推荐】小程序预加载（`app.js onLaunch` 预拉今日节目元数据）

### 13. 可访问性

- 【强制】语义化 HTML（`el-button` 用 `type="primary"` 等属性，禁止 `<div @click>` 模拟按钮）
- 【强制】图标按钮加 `aria-label`（如 `<el-button :icon="Search" aria-label="搜索" />`）
- 【强制】表单 `label` 关联（`el-form-item label="用户名"` + `for` 或 `id` 关联）
- 【推荐】颜色对比度满足 WCAG AA 标准（正文 ≥ 4.5:1）
- 【推荐】小程序 `aria-role`/`aria-label`（无障碍模式支持）

### 14. 代码质量

- 【强制】禁止 `console.log`（生产代码，调试用 `console.warn`/`console.error` 且需有明确语义）
- 【强制】禁止 `debugger`
- 【强制】禁止未使用变量（ESLint `no-unused-vars`）
- 【推荐】函数行数 < 50 行（超过建议拆分）
- 【推荐】组件行数 < 300 行（超过建议拆分子组件）
- 【强制】注释解释"为什么"而非"做什么"（项目规范）
- 【强制】循环依赖必须用延迟 `require` 解决，禁止"假设加载顺序"

### 15. 错误处理

- 【强制】API 调用必须 try-catch（或 `.catch`），禁止未捕获的 Promise rejection
- 【强制】空状态处理（无数据时显示占位，如 `el-empty`、小程序 `wx.showToast({title: '暂无数据'})`）
- 【强制】加载状态（`loading` 字段 + `v-loading`/骨架屏）
- 【强制】网络错误友好提示（`ElMessage.error('网络异常，请检查网络连接')`）
- 【强制】小程序 `wx.request` fail 分支必须 reject 友好提示（如 `new Error('网络异常')`）
- 【推荐】错误边界（Vue `errorCaptured`/小程序页面级 try-catch）

---

## 补充审查要点

> 以下审查要点来源于项目迭代复盘，配置详见 `config.yaml` 对应节点。

### A. el-table 拖拽排序审查

**配置节点**：`config.yaml#element_plus_drag_sort`

- 【强制】Sortable.js 拖拽 el-table 时，`onEnd` 回调必须先恢复 DOM（`removeChild` + `insertBefore`）再改数组，避免 Vue diff 冲突（规范 43）
- 【强制】el-table 拖拽模式下必须取消 `fixed` 列，否则双 tbody 导致 Sortable 错位（规范 44）
- 判断信号：grep 搜索 `Sortable.create` + `el-table`，检查 onEnd 是否有 DOM 恢复 + 是否有 `fixed` 属性

### B. canvas 验证码审查

**配置节点**：`config.yaml#canvas_captcha`

- 【强制】验证码字符集必须排除形近字符（`0/O`、`l/I/1`、`5/S` 等），避免用户无法区分（规范 42）
- 判断信号：grep 搜索验证码字符集定义，检查是否包含 `0`、`O`、`l`、`I`、`1` 等形近字符
- 推荐安全字符集：`ABCDEFGHJKMNPQRSTUVWXYZ23456789`（已排除 I/L/O/Q/S/Z）

### C. el-upload 文件校验审查

**配置节点**：`config.yaml#el_upload_validation`

- 【强制】`el-upload` 必须配置 `before-upload` 进行文件类型 + 大小双重校验
- 【强制】`accept` 属性限制文件类型（如 `.jpg,.png,.mp3`）
- 【强制】`before-upload` 函数校验失败时必须返回 `false` 阻止上传
- 判断信号：grep 搜索 `<el-upload` 无 `before-upload` 属性

### D. 图表组件注册审查

**配置节点**：`config.yaml#chart_components`

- 【强制】Chart.js 使用 `BarElement`/`LineElement`/`Filler` 等插件时必须 `import` 并 `Chart.register()`，否则图表渲染失败
- 判断信号：grep 搜索 `new Chart(` 或 `fill: true`，检查是否 `Chart.register` 了对应插件
- 常见遗漏：`Filler` 插件（折线图填充）、`BarElement`（柱状图）

### E. 趋势图 Y 轴单位审查

**配置节点**：`config.yaml#trend_chart`

- 【强制】趋势图指标切换时 Y 轴单位必须同步更新（如 dau→"人"、completion_rate→"%"）
- 【强制】指标→单位映射必须配置驱动（`metric_unit_map`），禁止硬编码在组件内
- 判断信号：grep 搜索 Y 轴标题配置，检查是否随指标动态切换

---

## 四维度复盘

> 基于本次 MorningBrief 前端代码审查实践，使用 Sequential Thinking 4 维度复盘法沉淀可复用的工作流模板。

### 维度 1：成功执行任务的完整步骤

本次审查覆盖 admin-web/src/ 与 miniprogram/ 两套前端代码，关键成功路径（按时间顺序）：

1. **范围识别**：确认审查目标为 Vue 3 + Element Plus（admin-web）+ 原生小程序（miniprogram）双栈
2. **配置加载**：读取 `config.yaml` 获取审查规则、硬约束、字段契约
3. **快速自检**：运行 `scripts/auto-scan.ps1` 扫描阻塞级问题（12 项）
4. **维度遍历**：按 15 维度逐项审查，每维度记录违规位置 + 修复建议
5. **字段契约核对**：对照 `config.yaml#field_contract_frontend.known_field_pairs` 检查前后端字段一致性
6. **小程序生命周期核对**：检查 `onLoad`/`onUnload` 配对、player 监听器 off、globalData 声明
7. **报告生成**：按 `templates/report-template.md` 输出结构化报告
8. **四维度复盘**：沉淀失败点与可抽象流程

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 小程序 api.js/auth.js 循环依赖导致 getToken 为 undefined | `api.js` 顶部 `require('./auth')`，auth.js 加载时调用 `request` | 所有 API 调用返回 401 | 模块加载顺序导致 `getToken` 未定义 | 延迟 `require` 到 `request` 函数内部 |
| 排期日历字段不匹配 | 前端期望 `dates` map，后端返回 `placements` 数组 | 排期日历页面渲染空白 | 前后端字段契约未对齐 | 前端按 `placements` 数组渲染，注释说明结构 |
| 工作流步骤字段名不匹配 | 前端用 `step_name`，后端返回 `name` | 工作流详情步骤名不显示 | 前后端字段名不一致 | 统一为后端字段 `name`，前端直接透传 |
| 稿件字段名不匹配 | 前端用 `content`，后端返回 `script` | 稿件内容不显示 | 历史字段名迁移未同步 | 前端 fallback `res.script || res.content`，注释历史兼容 |
| 分类字段名不匹配 | 前端用 `category`，后端返回 `categories` | 分类筛选失效 | 单复数混淆 | 统一为 `categories`（复数），与后端一致 |
| 完播率单位不一致 | 前端期望 0-100，后端返回 0-1 | 完播率显示 0.85% 而非 85% | 单位约定未对齐 | 后端统一返回 0-1，前端展示时 `* 100` 并注释 |
| 全局 player 事件未 off 导致内存泄漏 | `onLoad` 注册 `onPlay` 但 `onUnload` 未 `offPlay` | 多次进出页面后回调累积，UI 串扰 | 生命周期配对缺失 | `onUnload` 中 `offPlay`/`offPause`/`offTimeUpdate`/`offEnded` |
| isCurrentEpisode 用 title 判断 | `player.title === ep.title` | 标题重复时误判为同一节目，进度串扰 | 缺少稳定唯一标识 | `playEpisode` 设置 `player.episodeId`，用 ID 判断 |
| globalData.listenStats 未声明 | profile 页读取 `globalData.listenStats` 但 `app.js` 未声明 | 兜底读取返回 undefined | globalData 字段未显式声明 | `app.js globalData` 显式声明 `listenStats: null` |
| 路由缺 404 兜底 | 路由表无 `/:pathMatch(.*)*` | 访问错误路径白屏 | 路由设计遗漏 | 添加 404 兜底路由 redirect 到 `/review` |
| api/index.js 路径判断过宽 | `pathname.includes('/login')` | `/login-callback` 被误判为已在登录页，401 死循环 | 字符串包含判断不精确 | 改用 `pathname === '/login'` 严格相等 |
| BASE_URL 硬编码 | 小程序 `BASE_URL = 'http://localhost:8000'` | 生产环境请求失败 | 未按环境切换 | 按 `__wxConfig.envVersion` 切换 BASE_URL |
| onCanplay 监听器累积 | 每次 `playEpisode` 都 `onCanplay` 未 `off` | 监听器累积，seek 多次触发 | 监听器未自清理 | 命名回调 + `offCanplay(onCanplay)` 自清理 |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 对应维度 | 核心判断信号 | 落地配置节点 |
|------|----------|--------------|--------------|
| 前后端字段契约核对 | 维度 8 | `grep "audioUrl\|episodeId" admin-web/src/` 发现 camelCase 取后端字段 | `field_contract_frontend.known_field_pairs` |
| 小程序生命周期配对 | 维度 9 | `grep "onPlay\|onPause" miniprogram/pages/` 但无 `offPlay`/`offPause` | `miniprogram_lifecycle.listener_pairs` |
| 全局 player 单例管理 | 维度 10 | `grep "player.title ===" miniprogram/` 发现用 title 判断 | `miniprogram_audio.episode_id_required` |
| 循环依赖延迟 require | 维度 11 | `grep "^const.*require.*auth" miniprogram/services/api.js` 顶部 require | `miniprogram_api.circular_dependency_delayed_require` |
| 路径严格相等判断 | 维度 6 | `grep "includes.*login\|includes.*admin" admin-web/src/` | `hard_constraints.rules.path_strict_equality` |
| 环境化 BASE_URL | 维度 11 | `grep "BASE_URL.*=.*localhost\|http://" miniprogram/services/` 硬编码 | `miniprogram_api.env_based_base_url` |

## 新增审查维度：前端与后端交互一致性

### 维度 16：前端配置键与后端路由字段对齐

**为什么**：前端表单字段名必须与后端路由模型字段名一致，否则配置值无法正确传递。

检查信号：Grep ttsForm.edge_rate 等字段，确认后端 TTSConfigBody 中有同名字段
修复建议：字段名不一致时统一命名，避免 edge_rate vs edge_tts_rate 混淆

### 维度 17：重跑确认对话框显示正确步骤标签

**为什么**：用户点击重跑时应看到从哪一步开始，而不是笼统的重跑。

检查信号：Grep ElMessageBox.confirm 中的提示文本
修复建议：使用 stepLabel(retryStep.value) 显示具体步骤名

### 维度 18：前端路由静态路径定义顺序

**为什么**：Vite + Vue Router 中静态路由必须在动态路由之前定义，否则动态路由会捕获静态路径。

检查信号：Grep routes 数组中静态路径在动态路径之后
修复建议：将 /batch-delete 等静态路由移至 /:id 之前

### 维度 19：前端批量操作确认与上限提示

**为什么**：批量删除等操作应显示数量上限和二次确认，防止误操作。

检查信号：Grep 批量操作无 max_length 前端校验
修复建议：添加 v-if selectedIds.length <= 100 禁用按钮 + 确认对话框

### 维度 20：前端参数显示规范化

**为什么**：前端展示的 Edge 语速/音量参数应格式化为友好显示（如 +10% 而非 0.1）。

检查信号：Grep 表单绑定值直接显示原始数值
修复建议：添加计算属性格式化显示值，编辑时转换回原始值
### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 前后端字段契约核对 | 后端返回 snake_case 的项目、字段名易混淆（categories/category、script/content） | 后端已统一 camelCase、GraphQL 自动转驼峰 |
| 小程序生命周期配对 | 原生小程序、uni-app（onLoad/onUnload 体系） | React/Vue（用 useEffect/onUnmounted，不同机制） |
| 全局 player 单例管理 | 小程序 BackgroundAudioManager、web Audio 单例 | 每页独立 audio 实例的场景 |
| 循环依赖延迟 require | CommonJS（require/module.exports）、小程序 | ES Modules（import/export 静态分析） |
| 路径严格相等判断 | SPA 路由判断、登录页跳转 | 模糊匹配场景（如面包屑高亮） |
| 环境化 BASE_URL | 多环境部署（开发/测试/生产）| 单环境内部工具 |
| onCanplay 自清理 | 一次性事件监听（seek 后即 off） | 持续监听（如 onTimeUpdate 需要持续触发） |

### 维度 5（补充）：频道级配置同步与脚本兼容性复盘（2026-07-17）

**成功执行任务的完整步骤（补充）**：

1. **问题定位**：后端 rss.yaml 源 name 变更后，前端 ChannelManagement.vue 的 rss_sources 多选下拉框选项未同步
2. **根因分析**：前端选项来源为硬编码或旧 API，未动态获取 rss.yaml 最新源列表
3. **代码修复**：改为从 API 动态获取 RSS 源列表，确保前后端配置同步
4. **字段契约对齐**：确认前端 rss_sources 提交格式为 JSON 数组字符串，与后端 channel.rss_sources 存储格式一致
5. **验证脚本兼容性**：前端构建脚本中 Python 脚本调用改用 `python -u script.py 2>&1` 避免 PowerShell stdout 缓冲

**任务执行中的不确定性与失败点（补充）**：

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 前端 RSS 源选项硬编码 | ChannelManagement.vue 中 el-select 选项硬编码 | rss.yaml 变更后前端不同步，用户配置无效源 | 选项未动态获取 | 改为从 API 动态获取源列表 |
| 前端 rss_sources 格式不一致 | 前端提交数组，后端期望 JSON 字符串 | 后端解析失败，rss_sources 存储为 null | 前后端字段格式契约未对齐 | 前端提交时 JSON.stringify，回显时 JSON.parse |
| 前端验证脚本输出不可见 | PowerShell 调用 `python script.py` 无 -u | 脚本"卡住"误判 | stdout 块缓冲未刷新 | `python -u script.py 2>&1` |
| 前端脚本误判 logger.error 为异常 | PowerShell 包装 stderr 为 RemoteException | 脚本被误中断 | 未区分日志输出与真实异常 | 理解 RemoteException 是正常包装，不中断 |

**可抽象的固定流程与判断逻辑（补充）**：

| 模板 | 核心判断信号 | 落地配置节点 |
|------|--------------|--------------|
| 前端配置动态获取检查 | Grep `el-select` 中 RSS 源选项硬编码而非 API 动态获取 | `hard_constraints.rules.frontend_config_dynamic_fetch` |
| 前后端字段格式契约检查 | Grep 前端 rss_sources 提交格式与后端存储格式不一致 | `field_contract_frontend.rss_sources_format` |
| 前端 PowerShell Python 调用检查 | Grep `package.json` 或 `.ps1` 中 `python script.py` 无 `-u` 或 `2>&1` | `hard_constraints.rules.frontend_powershell_python_unbuffered` |

**适用场景与不适用场景（补充）**：

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 前端配置动态获取检查 | 频道级配置管理页面、前后端配置同步场景 | 全局配置（无频道隔离）、无配置页面项目 |
| 前后端字段格式契约检查 | JSON 数组字符串字段（rss_sources/keywords 等） | 简单字符串/数值字段（无格式转换） |
| 前端 PowerShell Python 调用检查 | Windows + PowerShell + 前端工具链（含 Python） | bash/zsh、纯 Node.js 前端工具链 |

---

## 审查流程

### 阶段 1：快速自检（阻塞级）

```powershell
pwsh .trae/skills/news-frontend-code-review/scripts/auto-scan.ps1
```

扫描 12 项阻塞级问题，发现 CRITICAL 必须修复后再继续。

### 阶段 2：人工评审（15 维度）

按 `config.yaml#checklist` 开关逐维度审查：

1. 读取 `config.yaml` 获取启用维度
2. 按维度遍历，每维度记录违规位置 + 修复建议
3. 对照 `field_contract_frontend.known_field_pairs` 核对字段契约
4. 对照 `miniprogram_lifecycle.listener_pairs` 核对生命周期配对
5. 触发 `abstraction_thresholds` 时记录抽象建议

### 阶段 3：报告生成

按 `templates/report-template.md` 输出报告，包含：

- 基本信息、审查结果摘要
- 硬约束合规性检查结果
- 详细问题列表（按 severity 分组）
- 好的实践（正面反馈）
- 四维度复盘
- 配置变更点

### 阶段 4：修复验证

修复后重新运行阶段 1 + 阶段 2，确认问题已解决。

---

## 新增审查维度：前端与后端交互一致性

### 维度 16：前端配置键与后端路由字段对齐

**为什么**：前端表单字段名必须与后端路由模型字段名一致，否则配置值无法正确传递。

检查信号：Grep 	tsForm.edge_rate 等字段，确认后端 TTSConfigBody 中有同名字段
修复建议：字段名不一致时统一命名，避免 edge_rate vs edge_tts_rate 混淆

### 维度 17：重跑确认对话框显示正确步骤标签

**为什么**：用户点击重跑时应看到从哪一步开始，而不是笼统的"重跑"。

检查信号：Grep ElMessageBox.confirm 中的提示文本
修复建议：使用 stepLabel(retryStep.value) 显示具体步骤名

### 维度 18：前端路由静态路径定义顺序

**为什么**：Vite + Vue Router 中静态路由必须在动态路由之前定义，否则动态路由会捕获静态路径。

检查信号：Grep outes 数组中静态路径在动态路径之后
修复建议：将 /batch-delete 等静态路由移至 /:id 之前

### 维度 19：前端批量操作确认与上限提示

**为什么**：批量删除等操作应显示数量上限和二次确认，防止误操作。

检查信号：Grep 批量操作无 max_length 前端校验
修复建议：添加 -if="selectedIds.length <= 100" 禁用按钮 + 确认对话框

### 维度 20：前端参数显示规范化

**为什么**：前端展示的 Edge 语速/音量参数应格式化为用户友好的显示（如 +10% 而非  .1）。

检查信号：Grep 表单绑定值直接显示原始数值
修复建议：添加计算属性格式化显示值，编辑时转换回原始值


### 维度 21：前端配置键与后端字段一致性

**为什么**：前端表单字段名、路由模型字段名、数据库配置键、Settings 属性四者必须一致或通过明确映射连接。字段不一致会导致前端保存的值在后端被忽略。

检查信号：Grep 前端字段名（如 edge_rate）与后端路由模型字段名不一致
修复建议：统一键名或使用 LEGACY_KEY_MAP 兼容旧键名读取

### 维度 22：前端批量失败诊断信息展示

**为什么**：批量操作中每步每段失败原因必须在前端以友好方式展示，不能仅显示"X/Y 失败"。

检查信号：Grep 批量操作失败后无分段级错误信息展示
修复建议：解析后端返回的失败摘要，逐段展示错误原因（脱敏后）

### 维度 23：前端路由静态路径优先级

**为什么**：Vue Router 中静态路由必须在动态路由之前定义，否则动态路由会捕获静态路径。

检查信号：Grep routes 数组中静态路径定义在动态路径之后
修复建议：将 /batch-delete 等静态路由移至 /:id 之前

### 维度 24：前端参数规范化展示

**为什么**：前端展示的数值参数应格式化为友好显示（如 +10% 而非 0.1），编辑时转换回原始值。

检查信号：Grep 表单绑定值直接显示原始数值
修复建议：添加计算属性格式化显示值，编辑时转换回原始值

### 维度 25：前端临时文件/资源清理意识

**为什么**：前端上传/下载临时文件后应提供清理提示或自动清理机制，防止浏览器存储泄漏。

检查信号：Grep Blob URL 创建后无 revokeObjectURL 调用
修复建议：使用完 Blob URL 后调用 URL.revokeObjectURL() 释放内存

---

## 新增审查维度：第三方服务模型名称与配置持久化

### 维度 26：第三方服务模型名称大小写核对

**为什么**：第三方 AI 服务商（LLM/TTS）的模型名称是区分大小写的字符串。使用错误的模型名会导致 API 调用失败或路由到错误的模型。前端预设配置中的模型名称必须以官方文档为事实源。

检查信号：Grep 预设配置中的模型名（如 deepseek-chat），与官网文档逐字核对
修复建议：新接入服务商时先查阅官方文档确认模型名称大小写，修改预设默认模型时同步更新后端定价表

### 维度 27：预设切换后下拉框状态反射

**为什么**：用户选择预设后，下拉框应反映当前选中的预设，否则用户无法确认当前使用的是哪个提供商。

检查信号：Grep applyPreset 函数中是否设置了 selectedPreset.value = key
修复建议：预设切换函数中必须同步更新 selectedPreset 状态

### 维度 28：页面加载后预设自动匹配

**为什么**：页面加载后应从数据库读取配置，并根据 base_url 自动匹配对应的预设提供商，使用户一眼就能知道当前使用的是哪个服务商。

检查信号：Grep loadConfig 函数中是否包含基于 base_url 的预设自动匹配逻辑
修复建议：在 presets.value 赋值后，遍历预设列表匹配 base_url，设置 selectedPreset.value

### 维度 29：预设切换时 API Key 不被覆盖

**为什么**：不同服务商的 API Key 完全不同。切换预设时如果覆盖了已保存的 API Key，会导致鉴权失败。

检查信号：Grep applyPreset 函数中是否意外设置了 api_key 字段
修复建议：预设切换只更新 base_url 和 model，不触碰 api_key

---

## 新增审查维度：批量操作与多选交互

### 维度 30：批量删除多选交互规范

**为什么**：批量删除是不可逆操作，表格必须提供选择列、选中计数、二次确认，防止误操作。

检查信号：Grep el-table 无 type="selection" 列、批量操作无 ElMessageBox.confirm
修复建议：添加 selection 列 + @selection-change 事件 + 二次确认对话框

### 维度 31：批量操作按钮禁用状态

**为什么**：未选中任何行时批量操作按钮应禁用，避免空操作。

检查信号：Grep 批量操作按钮无 :disabled="selectedRows.length === 0"
修复建议：添加 disabled 绑定，选中数量变化时实时更新

### 维度 32：删除后分页修正

**为什么**：批量删除后剩余记录可能少于当前页，需要自动回退到有效页码。

检查信号：Grep 批量删除后无分页修正逻辑
修复建议：计算 remainingTotal，若 page > maxPage 则 page = maxPage，然后重新加载列表

### 维度 33：批量操作前端确认提示文案

**为什么**：确认对话框必须明确告知用户删除范围和数据不可恢复，降低误操作风险。

检查信号：Grep ElMessageBox.confirm 中无"永久删除""不可恢复"等关键词
修复建议：提示文案包含选中数量、删除范围（素材/稿件/审核/节目/播放数据）、不可恢复声明



---

## 新增审查维度：前端 FFmpeg 安装体验

### 维度 34：FFmpeg 前端安装依赖完整性

**为什么**：前端点击下载 FFmpeg 后，后端解压必须包含完整 bin 目录（含 DLL），仅复制 exe 会导致运行时 找不到 avdevice-63.dll。

检查信号：Grep 前端安装流程无后端 DLL 完整性校验
修复建议：安装完成后验证 bin 目录下 DLL 数量 >= 7（shared build 至少 7 个 DLL）

### 维度 35：FFmpeg 安装进度与超时提示

**为什么**：FFmpeg 下载约 30MB，解压需要时间。前端必须提供明确的进度反馈和合理的超时设置（建议 10 分钟）。

检查信号：Grep installFFmpeg 请求无 timeout 配置
修复建议：axios 请求设置 	imeout: 600000（10 分钟），前端显示"正在下载，请耐心等待..."

### 维度 36：FFmpeg 安装后自动检测

**为什么**：安装完成后应立即重新检测可用性，向用户反馈成功或失败状态，避免用户反复点击下载。

检查信号：Grep 安装成功后无自动 re-check 逻辑
修复建议：安装完成后调用 check_ffmpeg 验证，成功显示绿色勾 + 版本号，失败显示错误信息

---

## 新增审查维度：类型契约与状态恢复

> 以下维度来源于 2026-07-15 前端迭代复盘，覆盖 el-switch 类型契约、blob 请求错误处理、v-loading 状态恢复、页面标题冗余、频道级配置控件对齐等高频故障场景。配置详见 `config.yaml#hard_constraints.rules` 对应条目。

### 维度 37：el-switch 类型契约（int vs bool）

**为什么**：后端返回 `enabled: 1`（int），但 el-switch 默认 `active-value=true`（bool）。JavaScript 严格相等 `1 !== true`，el-switch 认为值不等于 active-value，显示为关闭状态。用户切换开关时 emit `true`（bool），后端存 1，刷新后返回 1，el-switch 又显示关闭——死循环，配置无法持久化。

检查信号：Grep `<el-switch` 无 `:active-value` 且对应后端字段为 int 类型（如 enabled/status/is_active）
修复建议：el-switch 显式配置 `:active-value="1" :inactive-value="0"` 与后端 int 类型一致
适用场景：所有后端返回 int（0/1）的开关字段
不适用场景：后端已返回 bool（true/false）

### 维度 38：blob 请求超时与错误解析

**为什么**：axios 全局 `timeout=15000ms`（15s）对大文件（成品音频 11MB+）下载可能不够，导致 Network Error。且 `responseType: 'blob'` 的请求返回错误时，`error.response.data` 是 Blob 类型，axios 拦截器无法读取 `.message` 字段，前端只能显示 "Network Error"，无法定位真实错误（如 404 文件不存在、500 服务器错误）。

检查信号：Grep `responseType: 'blob'` 无 `timeout: 60000` 且无 `parseBlobError` 函数
修复建议：blob 请求独立配置 `timeout: 60000` + `silent: true`，catch 中检查 `err.response?.data instanceof Blob`，是则 `await blob.text()` 解析 JSON 获取真实 message，调用方手动 `ElMessage.error`
适用场景：文件下载、音频流、图片请求
不适用场景：JSON 响应（默认 responseType）

### 维度 39：v-loading 状态恢复（visibility 切换）

**为什么**：页面 visibility 切换（窗口最小化/切 tab 再切回）时，`handleVisibilityChange` 立即调用 `loadDetail()` 会触发 `loading=true`。Element Plus v-loading 在窗口最小化/恢复时 DOM 布局变化导致 mask 元素定位异常或残留，页面永久遮罩。

检查信号：Grep `handleVisibilityChange` 中直接调用 `loadDetail()` 或 `load()` 无 `nextTick` 延迟
修复建议：切回时先重置所有 loading 状态为 false，用 `nextTick` 延迟到下一帧再执行加载，让 Vue 先处理 `loading=false` 的 DOM 更新，清除可能残留的 mask DOM
适用场景：所有带 v-loading + visibility 事件的页面
不适用场景：无 v-loading 的简单页面

### 维度 40：页面标题冗余

**为什么**：顶部导航栏（侧边栏菜单）已显示页面名称时，页面内再渲染 `<span class="page-title">页面名</span>` 是冗余信息，占用屏幕空间，破坏视觉层次。应只保留顶部导航，页面内容直接展示功能控件。

检查信号：Grep `<span class="page-title">` 且 Layout 侧边栏已有同名菜单项
修复建议：移除页面内 page-title，CSS `.top-bar` 改为 `justify-content: flex-end`，删除 `.page-title` 样式
适用场景：所有带顶部导航的后台页面
不适用场景：无顶部导航的独立页面（如登录页）

### 维度 41：频道级配置控件与后端字段对齐

**为什么**：后端 Channel 模型新增配置字段（如 segment_gap_sec、enable_thinking_question）时，前端频道管理页面必须同步添加对应控件（el-slider、el-switch 等）。否则用户无法在页面上配置这些参数，功能等于不存在。这与维度 21（前端配置键与后端字段一致性）是同一问题的前端侧补充——维度 21 关注字段名对齐，本维度关注控件存在性。

检查信号：Grep 后端 Channel 模型新增字段后，ChannelManagement.vue 表单无对应 `el-form-item`
修复建议：后端新增频道字段时，前端同步添加控件，控件类型与字段类型匹配（float→el-slider、int 0/1→el-switch、string→el-input）
适用场景：所有频道/租户配置字段的前端控件
不适用场景：内部字段（不暴露给前端配置）
















---

## 新增审查维度：环境隔离与页面完整性

> 以下维度来源于 2026-07-17 真机测试与小程序迭代复盘，覆盖环境隔离、页面四件套、事件绑定对称性、工具层 bug 识别等高频故障场景。配置详见 `config.yaml#hard_constraints.rules` 对应条目。

### 维度 42：环境隔离与 BASE_URL 配置化

**为什么**：小程序真机测试时，手机访问不到电脑的 localhost/127.0.0.1（这两个地址在手机上指向手机自己）。如果 BASE_URL 硬编码 localhost，会导致真机所有 API 请求"网络异常"，容易被误判为"音频过大"等问题。

检查信号：Grep `BASE_URL.*localhost\|BASE_URL.*127\.0\.0\.1` 在 miniprogram/services/ 下硬编码单一环境
修复建议：按 `__wxConfig.envVersion` 切换 BASE_URL，开发环境用电脑局域网 IP
适用场景：小程序 + 后端服务架构、前后端分离项目
不适用场景：纯前端 SPA（无后端）、单机内部工具

### 维度 43：小程序页面四件套完整性

**为什么**：小程序页面由 .json/.js/.wxml/.wxss 四件套组成，缺一会导致编译错误或样式失效。历史问题：index/detail/profile 三个核心页面 .json 缺失，导致默认配置无 navigationBarTitleText；history.wxss 缺 top-bar/channel-pill 样式定义，导致频道胶囊垂直堆叠显示丑陋。

检查信号：
- Glob 检查 `miniprogram/pages/*/*.json` 是否每个页面都有对应 .json
- Grep 检查 .wxml 中使用的 CSS 类是否在对应 .wxss 中定义

修复建议：新建页面必须同步创建 .json/.js/.wxml/.wxss 四个文件；.wxml 中用到的所有 CSS 类必须在对应 .wxss 中定义
适用场景：微信小程序原生开发、uni-app
不适用场景：React/Vue SPA（单文件组件）

### 维度 44：事件绑定对称性（on/off 配对）

**为什么**：小程序全局 player 的 onPlay/onPause/onTimeUpdate/onEnded 等监听器如果在 onLoad 注册但 onUnload 未 off，reLaunch 后 onLoad 重复绑定会导致回调叠加，UI 串扰（如多个 setData 竞争）。

检查信号：
- Grep `player.on\w+\(` 或 `audioManager.on\w+\(` 后检查 onUnload 是否有对应 `off\w+`
- Grep `this._onPlay = ` 检查回调是否保存为实例属性（用于精确 off）

修复建议：
- 所有 onXxx 监听器必须有对应 offXxx 解绑
- 回调必须保存为实例属性（this._onXxx），禁止匿名函数（无法精确 off）
- onUnload 中必须 off 所有监听器，并清除引用
适用场景：小程序 Page/Component、Node.js EventEmitter、浏览器 addEventListener
不适用场景：一次性 Promise、async/await（自动清理）

### 维度 45：navigateTo 失败降级

**为什么**：wx.navigateTo 在页面栈满 10 层或目标页面未注册时会静默失败，无 toast、无日志，用户感知为"点击无反应"。

检查信号：Grep `wx.navigateTo` 后无 `fail` 回调
修复建议：navigateTo 失败时降级为 reLaunch，并 console.warn 输出原因便于排查
适用场景：所有小程序页面跳转
不适用场景：tabBar 页面切换（用 wx.switchTab）

### 维度 46：工具层 bug 识别

**为什么**：微信开发者工具基础库 3.17.0 灰度版的 webview bug（`routeDone with a webviewId N is not found`）和 `appservice/mainframe 500` 被误判为代码问题，浪费修复时间。工具层 bug 无法通过代码修复，必须先排工具层后查代码层。

检查信号：
- 错误信息含 `system error` / `webviewId` / `appservice` / `mainframe` → 工具层
- 错误仅在特定环境（开发者工具/真机/特定基础库版本）出现 → 工具层

修复建议：
- 工具层 bug：降基础库版本 + 清缓存 + 重启工具 + 兜底重装
- 代码层 bug：现象采集 → 代码定位 → 根因假设 → 验证 → 修复 → 测试
- 防御性代码仍需实施（navigateTo 降级 reLaunch、off 用可选链），但不是根治
适用场景：所有依赖开发工具的项目
不适用场景：纯命令行项目（无 IDE 依赖）

---

## 新增审查维度：401 重试与 API 调用健壮性

### 维度 47：401 重试无限循环防护

**为什么**：API 请求 401 时自动 refreshToken 后重试原请求，但如果原请求就是 /auth/login（登录接口本身返回 401），会形成 login → 401 → refreshToken → login → 401 → ... 无限递归。即使不是登录接口，token 仍无效时也会无限重试。

检查信号：Grep `request` 函数中 401 处理逻辑无 `_retried` 标记或无 `url.startsWith('/auth/')` 排除
修复建议：
- 排除 /auth/ 前缀请求触发 401 重试（登录接口本身不重试）
- 用 `_retried` 标记最多重试一次，防止 token 仍无效时无限递归
适用场景：所有带 token 刷新机制的 API 封装
不适用场景：无 token 刷新的简单 API 调用

---

## 新增审查维度：频道级配置同步与脚本兼容性

> 以下维度来源于 2026-07-17 频道级数据隔离修复与 RSS 源端到端验证复盘，覆盖前端配置文件与后端数据源同步、前端验证脚本 PowerShell 兼容性等高频故障场景。配置详见 `config.yaml#hard_constraints.rules` 对应条目。

### 维度 48：前端频道配置与后端数据源同步

**为什么**：后端 rss.yaml 中的源 name 变更后，前端频道管理页面（ChannelManagement.vue）的 rss_sources 多选下拉框选项必须同步更新。如果前端仍从旧 API 获取源列表，或硬编码了源 name，会导致用户配置的 rss_sources 在后端 crawler 按 name 匹配时找不到源，返回 0 条素材。这是前后端配置不同步的典型问题。

**检查信号**：
- Grep `ChannelManagement.vue` 中 rss_sources 多选下拉框，检查选项来源是否为动态 API（如 `/admin/api/v1/rss-sources`）而非硬编码
- Grep 前端代码中硬编码的 RSS 源 name（如 `'少数派'`、`'36氪'`），应改为从 API 动态获取
- Grep 前端频道表单提交时，rss_sources 字段是否为 JSON 数组字符串（与后端 `channel.rss_sources` 存储格式一致）

**修复建议**：
```vue
<!-- ❌ 反模式：硬编码 RSS 源选项 -->
<el-select v-model="channelForm.rss_sources" multiple>
  <el-option label="少数派" value="少数派" />
  <el-option label="36氪" value="36氪" />
  <!-- 硬编码，rss.yaml 变更后不同步 -->
</el-select>

<!-- ✅ 正确：从 API 动态获取 RSS 源列表 -->
<el-select v-model="channelForm.rss_sources" multiple placeholder="不选则使用全部源">
  <el-option
    v-for="source in availableRssSources"
    :key="source.name"
    :label="`${source.name} (${source.category})`"
    :value="source.name"
  />
</el-select>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchRssSources } from '@/api/channel'

const availableRssSources = ref([])

onMounted(async () => {
  // 从后端 API 动态获取 rss.yaml 中的源列表
  const data = await fetchRssSources()
  availableRssSources.value = data.sources
})
</script>
```

**前后端字段契约**：
- 前端 `channelForm.rss_sources` 提交时必须为 JSON 数组字符串（如 `'["少数派","极客公园"]'`）
- 后端 `channel.rss_sources` 字段存储格式为 JSON 数组字符串
- 前端回显时必须 `JSON.parse(channel.rss_sources)` 转为数组

适用场景：频道级 RSS 源配置管理、前后端配置同步场景
不适用场景：全局 RSS 源（不按频道隔离）、无配置页面的项目

### 维度 49：前端验证脚本 PowerShell 兼容性

**为什么**：前端开发流程中可能调用 Python 脚本（如构建脚本、验证脚本、数据迁移脚本）。PowerShell 调用 Python 脚本时，stdout 默认是块缓冲，脚本输出在缓冲区满或脚本退出前不可见，导致长时间运行的脚本看起来"卡住"。同时 Python 的 logger.error 写入 stderr，PowerShell 会包装为 RemoteException 警告，但脚本继续执行。前端开发者可能误判脚本失败而中断。

**检查信号**：
- Grep 前端 `package.json` 的 scripts 中 `python script.py`（无 -u 参数）
- Grep 前端构建脚本（如 `build.ps1`）中 `python script.py` 后无 `2>&1` 重定向
- Grep 前端开发文档中因 RemoteException 警告而误判脚本失败的说明

**修复建议**：
```json
// package.json scripts 规范
{
  "scripts": {
    // ❌ 反模式：stdout 缓冲导致输出不可见
    "verify": "python scripts/verify.py",

    // ✅ 正确：-u 禁用缓冲 + 2>&1 捕获 stderr
    "verify": "python -u scripts/verify.py 2>&1"
  }
}
```

```powershell
# 前端构建脚本规范（build.ps1）
# ❌ 反模式
python scripts/gen_sitemap.py

# ✅ 正确
python -u scripts/gen_sitemap.py 2>&1
```

**注意事项**：
- `python -u` 禁用 stdout 缓冲，确保输出实时可见
- `2>&1` 将 stderr 重定向到 stdout，捕获 logger.error 输出
- PowerShell 包装 stderr 为 RemoteException 警告是正常行为，不应因警告中断脚本
- 仅适用于 Windows + PowerShell 环境，bash/zsh 默认行缓冲无需此处理

适用场景：Windows + PowerShell + 前端工具链（含 Python 脚本调用）
不适用场景：bash/zsh（默认行缓冲）、IDE 内运行（IDE 处理缓冲）、纯 Node.js 前端工具链（无 Python 依赖）
