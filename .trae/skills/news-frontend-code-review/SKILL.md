---
name: "news-frontend-code-review"
description: "对 20_News 项目前端代码（admin-web/src/ 下 Vue 3/Element Plus 文件 + miniprogram/ 下微信小程序文件）进行全面评审与逻辑审查，覆盖组件规范、状态管理、API 契约、路由设计、类型安全、性能、可访问性、前后端字段契约、小程序生命周期、音频播放管理等维度。当用户要求'审查/检查/走查/把关/review/评估/看看对不对/规范不规范'前端 Vue/JS 代码、'.vue/.js 文件修改'、'迭代发布前前端走查'，或提到'前端评审/frontend review/Vue 代码审查/小程序代码审查'时调用。仅审查前端文件；纯后端 .py 文件审查请改用 news-backend-code-review。"
whenToUse: "需要审查 20_News 前端代码（admin-web/src/ 下 .vue/.js 文件 + miniprogram/ 下 .js/.wxml/.wxss 文件）是否符合项目规范"
triggers: "前端代码 走查/审查/审核/把关/review/检查/评估 | .vue/.js 文件 修改/变更/迭代 走查 | 迭代发布前 前端 代码 走查 | 这段前端代码 写得对不对/规范不规范 | Vue/小程序 代码 review | 页面/组件/Store/路由 代码 审查"
version: "1.5.0"
updated: "2026-07-12"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 20_News 前端代码审查

对 20_News 项目前端代码进行全面的代码评审及逻辑审查，覆盖**运营后台（admin-web/，Vue 3 + Element Plus + Vite + Pinia）**与**微信小程序（miniprogram/，原生小程序）**两套前端代码。评审涵盖 **36 个维度**：目录结构、命名规范、Vue 3 组件规范、Element Plus 规范、Pinia 状态管理、API 调用规范、路由设计、前后端字段契约、小程序生命周期、小程序音频播放管理、小程序 API 层、性能、可访问性、代码质量、错误处理。

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

> 基于本次 20_News 前端代码审查实践，使用 Sequential Thinking 4 维度复盘法沉淀可复用的工作流模板。

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















