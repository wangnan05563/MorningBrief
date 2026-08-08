# 前端代码审查维度详解

> 完整审查维度定义（118 项），含判断信号、grep 模式、严重级别、修复示例。
> 主技能文件 [SKILL.md](../SKILL.md) 中为快速参考表。

---

## 核心维度（1-15，默认全开）

### 维度 1：目录结构

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

**严重级别**：CRITICAL

### 维度 2：命名规范

- 【强制】Vue 组件文件 PascalCase（如 `AdSchedule.vue`、`WorkflowDetail.vue`）
- 【强制】API 模块 camelCase（如 `api/index.js` 导出的函数 `fetchTodayEpisode`）
- 【强制】Pinia store 用 `use*Store` 命名（如 `useUserStore`）
- 【强制】miniprogram 页面用小写目录名 + 同名 js/wxml/wxss
- 【强制】常量 UPPER_SNAKE_CASE（如 `BASE_URL`、`MAX_RETRY`）
- 【强制】事件处理函数 `on*` 前缀（小程序 `onPlay`、`onLoad`；Vue `@click="handleSubmit"`）

**严重级别**：HIGH

### 维度 3：Vue 3 组件规范

- 【强制】使用 `<script setup>` 语法（项目规范，禁止 Options API 用于新组件）
- 【强制】Props 用 `defineProps` + 类型标注，事件用 `defineEmits`
- 【强制】组件名与文件名一致（`AdSchedule.vue` 内组件名 `AdSchedule`）
- 【强制】条件渲染合理选择 `v-if`（切换成本低、初始化重）与 `v-show`（频繁切换）
- 【强制】列表渲染用 `:key` 绑定稳定唯一标识（禁止用 index 作为 key）
- 【推荐】复杂逻辑用 `computed` 缓存，避免模板内函数调用
- 【推荐】副作用用 `watch`/`watchEffect`，且需在 `onUnmounted` 清理

**判断信号**：grep `export default {` 在 `.vue <script>` 中（非 setup）→ 违规

**严重级别**：HIGH

### 维度 4：Element Plus 规范

- 【强制】表单验证用 `el-form` + `:rules` + `ref` 调用 `validate()`
- 【强制】表格用 `el-table` + `el-pagination` 分页，禁止一次性渲染全部数据
- 【强制】对话框用 `el-dialog` + `v-model` 控制显隐
- 【强制】消息提示用 `ElMessage`（轻提示）/ `ElMessageBox`（确认框），禁止 `alert`/`confirm`
- 【强制】状态标签用 `el-tag` + `type` 映射（success/warning/danger/info）
- 【强制】表单提交按钮加 `:loading` 防重复提交
- 【推荐】大量数据表格用 `el-table-v2`（虚拟滚动）

**严重级别**：HIGH

### 维度 5：Pinia 状态管理

- 【强制】用 `defineStore` 定义，store 名与文件名一致
- 【强制】`state`/`getters`/`actions` 分离（Options API 风格，与项目现状一致）
- 【强制】跨组件共享状态用 store，禁止 props 多层透传（>2 层）
- 【推荐】持久化用 `pinia-plugin-persistedstate`，避免手动 `localStorage` 读写散落
- 【强制】store action 必须处理异常（try-catch 或调用方处理），禁止静默失败

**判断信号**：grep `localStorage.setItem` 在非 store 文件中 → 违规

**严重级别**：HIGH

### 维度 6：API 调用规范

- 【强制】统一用 `api/` 模块封装，禁止组件内直接 `axios`/`fetch`
- 【强制】axios 实例配置 `baseURL` + 请求/响应拦截器
- 【强制】请求拦截器注入 `Authorization: Bearer <token>`
- 【强制】响应拦截器统一处理 `{ code, message, data }` 结构，`code !== 0` 视为业务错误
- 【强制】401 自动跳转登录页（清 token + replace），403 提示无权限
- 【强制】错误处理用 try-catch + `ElMessage.error`，禁止 `.catch(() => {})` 静默吞错
- 【推荐】路径判断用严格相等（`pathname === '/login'`），避免 `includes('/login')` 误匹配 `/login-callback`

**判断信号**：grep `axios(` 或 `fetch(` 在 `views/` 中 → 违规

**严重级别**：HIGH

### 维度 7：路由设计

- 【强制】路由懒加载（`() => import('../views/xxx.vue')`）
- 【强制】路由守卫（`beforeEach` 校验 token + 角色）
- 【强制】404 兜底路由（`{ path: '/:pathMatch(.*)*', redirect: '/review' }`），避免白屏
- 【强制】布局组件嵌套路由（`/` 下 `children`），`redirect` 到默认子路由
- 【强制】需要登录的路由 `meta.requiresAuth: true`，角色限制 `meta.requireRole: 'admin'`
- 【推荐】路由 name 唯一，便于 `router.push({ name: 'xxx' })`

**判断信号**：grep `import.*from.*views` 在 router 顶部（非懒加载）→ 违规

**严重级别**：HIGH

### 维度 8：前后端字段契约

**核心原则**：后端返回 snake_case，前端直接用，**禁止**转 camelCase（与后端字段名保持一致是单一可信源）。

- 【强制】后端返回 snake_case 字段，前端直接用（如 `episode.audio_url`、`player.episode_id`）
- 【强制】Enum 值用后端返回的 `.value`，禁止前端硬编码字符串
- 【强制】日期字段用后端 ISO 格式，前端用 `new Date(isoStr)` 解析
- 【强制】比率字段注意单位：完播率/进度等需确认是 0-1 还是 0-100
- 【强制】分类字段名前后端一致（`categories` vs `category` 需明确）

**已知字段契约表**：

| 后端字段 | 前端禁止用法 | 说明 |
|----------|--------------|------|
| `audio_url` | `audioUrl` | 音频地址（snake_case 透传） |
| `episode_id` | `episodeId` | 节目 ID |
| `categories` | `category` | 分类列表（复数） |
| `script` | `content` | 稿件内容（历史兼容可 fallback） |
| `placements` | `dates` | 排期投放数组（结构不同） |
| `step_name` | `name` | 工作流步骤名 |

**严重级别**：CRITICAL

### 维度 9：小程序生命周期

- 【强制】`onLoad`/`onUnload` 配对：`onLoad` 注册的监听器必须在 `onUnload` 中 `off`
- 【强制】`onShow`/`onHide` 处理页面可见性（如暂停音频播放、停止定时器）
- 【强制】全局 `player` 监听器必须在 `onUnload` 中 `off`（`offPlay`/`offPause`/`offTimeUpdate`/`offEnded`）
- 【强制】`globalData` 字段必须显式声明（如 `player: null`、`listenStats: null`），禁止运行时动态新增
- 【强制】`Page` 内事件回调保存为实例属性（`this._onPlay = () => {...}`），便于 `onUnload` 精确 `off`
- 【推荐】`onLoad` 接收 query 参数后立即校验（如 `if (!id) { showError(); return }`）

**判断信号**：grep `onPlay(` 在某页但该页 `onUnload` 无 `offPlay(` → 违规

**严重级别**：CRITICAL

### 维度 10：小程序音频播放管理

**核心机制**：全局单例 `player`（`app.globalData.player`），所有页面共享。

- 【强制】全局单例 `player`（`app.globalData.player`），`initPlayer` 在 `app.js onLaunch` 调用一次
- 【强制】`playEpisode` 设置 `episodeId`，**禁止**用 `title` 判断当前节目（标题重复会误判）
- 【强制】`onCanplay` 监听器用后即 `off`（避免累积）
- 【强制】断点续播用 `startPosition`（从 `fetchPlayProgress` 获取），`completed === true` 时不续播
- 【强制】进度上报用 `onTimeUpdate`（每 5 秒定时器 + 暂停/结束时立即上报）
- 【强制】弱网降频：根据 `globalData.networkType` 调整上报间隔（wifi 5s，非 wifi 15s）
- 【强制】`isCurrentEpisode` 判断用 `player.episodeId === ep.id`，禁止用 `player.title === ep.title`
- 【推荐】`onEnded` 上报 `completed: true` + `position: duration`

**判断信号**：grep `player.title ===` 在 `miniprogram/` → 违规（应用 episodeId）

**严重级别**：CRITICAL

### 维度 11：小程序 API 层

- 【强制】循环依赖处理：`api.js` 内 `require('./auth')` 延迟到 `request` 函数内部调用，禁止顶部 `require`
- 【强制】`BASE_URL` 按环境切换（`__wxConfig.envVersion === 'release'` 走生产，其余走开发），禁止硬编码单一环境
- 【强制】token 管理：`getToken`/`refreshToken`/`setToken` 集中在 `auth.js`，禁止散落
- 【强制】请求封装统一 header（`Content-Type: application/json` + `Authorization`）
- 【强制】401 自动 `refreshToken` 后重试原请求一次，失败则 reject 友好提示
- 【强制】业务错误（`code !== 0`）reject `Error(message)`，调用方 try-catch

**判断信号**：grep `require('./auth')` 在 api.js 顶部（非函数内部）→ 违规

**严重级别**：HIGH

### 维度 12：性能

- 【强制】路由懒加载（`() => import()`）
- 【推荐】列表虚拟滚动（大数据量场景，如 `el-table-v2`）
- 【推荐】图片懒加载（小程序 `lazy-load` 属性，admin-web 用 `v-lazy` 或 IntersectionObserver）
- 【强制】搜索输入防抖（300-500ms），避免每次按键触发请求
- 【强制】小程序 `setData` 批量更新（合并多次 `setData` 为一次），避免频繁触发渲染
- 【推荐】小程序首屏加速：稿件懒加载（用户点击才请求 `fetchEpisodeScript`）
- 【推荐】小程序预加载（`app.js onLaunch` 预拉今日节目元数据）

**严重级别**：MEDIUM

### 维度 13：可访问性

- 【强制】语义化 HTML（`el-button` 用 `type="primary"` 等属性，禁止 `<div @click>` 模拟按钮）
- 【强制】图标按钮加 `aria-label`（如 `<el-button :icon="Search" aria-label="搜索" />`）
- 【强制】表单 `label` 关联（`el-form-item label="用户名"` + `for` 或 `id` 关联）
- 【推荐】颜色对比度满足 WCAG AA 标准（正文 ≥ 4.5:1）
- 【推荐】小程序 `aria-role`/`aria-label`（无障碍模式支持）

**严重级别**：MEDIUM

### 维度 14：代码质量

- 【强制】禁止 `console.log`（生产代码，调试用 `console.warn`/`console.error` 且需有明确语义）
- 【强制】禁止 `debugger`
- 【强制】禁止未使用变量（ESLint `no-unused-vars`）
- 【推荐】函数行数 < 50 行（超过建议拆分）
- 【推荐】组件行数 < 300 行（超过建议拆分子组件）
- 【强制】注释解释"为什么"而非"做什么"（项目规范）
- 【强制】循环依赖必须用延迟 `require` 解决，禁止"假设加载顺序"

**严重级别**：HIGH

### 维度 15：错误处理

- 【强制】API 调用必须 try-catch（或 `.catch`），禁止未捕获的 Promise rejection
- 【强制】空状态处理（无数据时显示占位，如 `el-empty`、小程序 `wx.showToast({title: '暂无数据'})`）
- 【强制】加载状态（`loading` 字段 + `v-loading`/骨架屏）
- 【强制】网络错误友好提示（`ElMessage.error('网络异常，请检查网络连接')`）
- 【强制】小程序 `wx.request` fail 分支必须 reject 友好提示
- 【推荐】错误边界（Vue `errorCaptured`/小程序页面级 try-catch）

**严重级别**：HIGH

---

## 补充审查要点（A-M）

### A. el-table 拖拽排序审查

**配置节点**：`config.yaml#element_plus_drag_sort`

- 【强制】Sortable.js 拖拽 el-table 时，`onEnd` 回调必须先恢复 DOM（`removeChild` + `insertBefore`）再改数组，避免 Vue diff 冲突
- 【强制】el-table 拖拽模式下必须取消 `fixed` 列，否则双 tbody 导致 Sortable 错位
- 判断信号：grep 搜索 `Sortable.create` + `el-table`，检查 onEnd 是否有 DOM 恢复 + 是否有 `fixed` 属性
- **严重级别**：HIGH

### B. canvas 验证码审查

**配置节点**：`config.yaml#canvas_captcha`

- 【强制】验证码字符集必须排除形近字符（`0/O`、`l/I/1`、`5/S` 等），避免用户无法区分
- 判断信号：grep 搜索验证码字符集定义，检查是否包含 `0`、`O`、`l`、`I`、`1` 等形近字符
- 推荐安全字符集：`ABCDEFGHJKMNPQRSTUVWXYZ23456789`（已排除 I/L/O/Q/S/Z）
- **严重级别**：HIGH

### C. el-upload 文件校验审查

**配置节点**：`config.yaml#el_upload_validation`

- 【强制】`el-upload` 必须配置 `before-upload` 进行文件类型 + 大小双重校验
- 【强制】`accept` 属性限制文件类型（如 `.jpg,.png,.mp3`）
- 【强制】`before-upload` 函数校验失败时必须返回 `false` 阻止上传
- 判断信号：grep 搜索 `<el-upload` 无 `before-upload` 属性 → 违规
- **严重级别**：HIGH

### D. 图表组件注册审查

**配置节点**：`config.yaml#chart_components`

- 【强制】Chart.js 使用 `BarElement`/`LineElement`/`Filler` 等插件时必须 `import` 并 `Chart.register()`
- 判断信号：grep 搜索 `new Chart(` 或 `fill: true`，检查是否 `Chart.register` 了对应插件
- 常见遗漏：`Filler` 插件（折线图填充）、`BarElement`（柱状图）
- **严重级别**：HIGH

### E. 趋势图 Y 轴单位审查

**配置节点**：`config.yaml#trend_chart`

- 【强制】趋势图指标切换时 Y 轴单位必须同步更新（如 dau→"人"、completion_rate→"%"）
- 【强制】指标→单位映射必须配置驱动（`metric_unit_map`），禁止硬编码在组件内
- 判断信号：grep 搜索 Y 轴标题配置，检查是否随指标动态切换
- **严重级别**：MEDIUM

### F. V2.2：外部服务降级与音频 URL 前端审查

**配置节点**：`config.yaml#audio_url_adaptability_check` + `config.yaml#storage_fallback_ui_check`

- 【强制】前端 audio 标签 src 与下载函数必须同时支持绝对 URL（`https://...`）与相对路径（`/audio/<key>`），禁止仅匹配 `^https?://`
- 【强制】管理后台存储配置页必须根据后端 `is_cos_configured` 状态展示降级提示（`el-alert` 或 `el-tag`），禁止静默降级
- 【强制】前端播放器遇到音频加载失败（`onerror`）时，必须区分网络错误与路径错误
- 判断信号：
  - grep `audio.*src.*=.*http` 或 `new URL.*http` 仅匹配绝对 URL → 违规
  - grep `is_cos_configured` 前端配置页无对应状态展示 → 违规
  - grep `onerror` audio 标签无错误分类处理 → 违规
- **严重级别**：HIGH

### G. 小程序用户态数据双层同步审查

**配置节点**：`config.yaml#review_dimensions` → `miniprogram_state_sync`

- 【强制】所有写入 `app.globalData` 的用户态数据（userInfo/token/偏好），必须紧接同步写入 localStorage
- 【强制】UI 状态（弹窗开关、临时编辑值）不写入 localStorage，仅写 globalData 或 setData
- 判断信号：
  - grep `app.globalData.userInfo =` 后 3 行内无 `setToken` 或 `wx.setStorageSync` → 违规
  - grep `app.globalData.token =` 后 3 行内无 `wx.setStorageSync('news_token'` → 违规
- **严重级别**：CRITICAL（重启后数据丢失属严重体验问题）

### H. 小程序 4 维静态验证审查

**配置节点**：`config.yaml#review_dimensions` → `miniprogram_static_4d_check`

- 【强制】修改 miniprogram/*.js 后必须完成 4 维验证：
  - 语法维：`node --check` 检查所有修改的 .js 文件
  - 接口维：验证调用的依赖模块函数签名一致
  - 契约维：验证前端请求/响应字段与后端路由定义对齐
  - 渲染维：验证 .wxml 数据绑定字段名与 setData 一致
- 判断信号：
  - 修改了 miniprogram/**/*.js 但无 `node --check` 执行记录 → 违规
  - 修改了 .wxml 绑定字段但未验证 setData 对应字段存在 → 违规
- **严重级别**：HIGH

### I. 前后端字段契约验证清单审查

**配置节点**：`config.yaml#review_dimensions` → `field_contract_checklist`

- 【强制】每个涉及前后端交互的 API，必须核对三项：
  - 请求字段：前端发送的字段名 vs 后端 Pydantic Model 字段名
  - 响应字段：后端返回的字段名 vs 前端使用的字段名
  - 兜底链：前端多名字兜底（如 `avatar_url || avatar || avatarUrl`）每个名字都有数据源
- 判断信号：
  - 前端用 `snake_case` 而后端返回 `camelCase`，或反之 → 违规
  - 前端使用了后端响应体中不存在的字段名 → 违规
- **严重级别**：HIGH

### J. 小程序进度上报条件容错审查

**配置节点**：`config.yaml#review_dimensions` → `progress_report_fallback`

- 【强制】进度上报函数不得因单一字段异常（如 `duration <= 0`）而整体跳过上报
- 【强制】`listened_seconds` 必须作为独立累计字段上报，不依赖 duration 是否有效
- 判断信号：
  - grep `if (duration <= 0)` 或 `if (duration > 0)` 在进度上报函数中且后跟 `return` → 违规
  - grep `reportPlayProgress` 参数中无 `listened_seconds` → 违规
- **严重级别**：HIGH

### K. 状态属性与标志位一致性审查

**配置节点**：`config.yaml#review_dimensions` → `state_property_consistency`

- 【强制】对象的 `status` 属性（property）必须先检查标志位（如 `_stopped`），不能直接查询外部状态覆盖
- 【强制】`stop()` 方法必须设置标志位，`start()` 方法必须重置标志位
- 判断信号：
  - grep `def status` 或 `get status` 属性中直接查询外部状态而无 `if self._stopped` 检查 → 违规
  - grep `def stop` 无 `self._stopped = True` 赋值 → 违规
- **严重级别**：HIGH

### L. 音频队列自动播放审查

**配置节点**：`config.yaml#review_dimensions` → `audio_queue_autoplay`

- 【建议】`onEnded` 回调必须触发 `playNext()` 自动播放下一首
- 【建议】`playNext()` 中队列空时调用 `_autoFillQueue()` 预填队列
- 判断信号：
  - grep `onEnded` 无 `playNext` 调用 → 违规
  - grep `playNext` 无 `_autoFillQueue` → 建议改进
- **严重级别**：MEDIUM

### M. 小程序分包配置校验审查

**配置节点**：`config.yaml#review_dimensions` → `subpackage_config_check`

- 【强制】app.json 中 `pages` 数组的页面路径不能以 `subPackages[].root` 为前缀
- 判断信号：
  - app.json 中 `pages` 数组包含 `subPackages[].root` 开头的路径 → 违规
  - 修改 app.json 的 `subPackages` 配置但未校验 `pages` 冲突 → 违规
- **严重级别**：HIGH

---

## 扩展维度（16-118，按需激活）

以下维度按需通过 `config.yaml` 开关激活，覆盖跨项目迁移、SonarQube、播放安全、表单类型契约等场景。

### 维度 16-25：前端与后端交互/批量操作/FFmpeg

#### 维度 16：前端配置键与后端路由字段对齐

**为什么**：前端表单字段名必须与后端路由模型字段名一致，否则配置值无法正确传递。

检查信号：Grep `ttsForm.edge_rate` 等字段，确认后端 TTSConfigBody 中有同名字段
修复建议：字段名不一致时统一命名
**严重级别**：HIGH

#### 维度 17：重跑确认对话框显示正确步骤标签

**为什么**：用户点击重跑时应看到从哪一步开始，而不是笼统的"重跑"。

检查信号：Grep `ElMessageBox.confirm` 中的提示文本
修复建议：使用 `stepLabel(retryStep.value)` 显示具体步骤名
**严重级别**：MEDIUM

#### 维度 18：前端路由静态路径定义顺序

**为什么**：Vue Router 中静态路由必须在动态路由之前定义，否则动态路由会捕获静态路径。

检查信号：Grep routes 数组中静态路径在动态路径之后
修复建议：将 `/batch-delete` 等静态路由移至 `/:id` 之前
**严重级别**：HIGH

#### 维度 19：前端批量操作确认与上限提示

**为什么**：批量删除等操作应显示数量上限和二次确认，防止误操作。

检查信号：Grep 批量操作无 `max_length` 前端校验
修复建议：添加 `v-if="selectedIds.length <= 100"` 禁用按钮 + 确认对话框
**严重级别**：HIGH

#### 维度 20：前端参数显示规范化

**为什么**：前端展示的数值参数应格式化为友好显示（如 +10% 而非 0.1）。

检查信号：Grep 表单绑定值直接显示原始数值
修复建议：添加计算属性格式化显示值，编辑时转换回原始值
**严重级别**：MEDIUM

#### 维度 21：前端配置键与后端字段一致性

检查信号：Grep 前端字段名（如 `edge_rate`）与后端路由模型字段名不一致
修复建议：统一键名或使用 `LEGACY_KEY_MAP` 兼容旧键名读取
**严重级别**：HIGH

#### 维度 22：前端批量失败诊断信息展示

检查信号：Grep 批量操作失败后无分段级错误信息展示
修复建议：解析后端返回的失败摘要，逐段展示错误原因（脱敏后）
**严重级别**：MEDIUM

#### 维度 23：前端路由静态路径优先级

同维度 18，强调 Vue Router 静态路由必须在动态路由前。
**严重级别**：HIGH

#### 维度 24：前端参数规范化展示

同维度 20。
**严重级别**：MEDIUM

#### 维度 25：前端临时文件/资源清理意识

**为什么**：前端上传/下载临时文件后应提供清理提示或自动清理机制。

检查信号：Grep `Blob URL` 创建后无 `revokeObjectURL` 调用
修复建议：使用完 Blob URL 后调用 `URL.revokeObjectURL()` 释放内存
**严重级别**：MEDIUM

### 维度 26-36：第三方服务/批量操作/FFmpeg

#### 维度 26：第三方服务模型名称大小写核对

检查信号：Grep 预设配置中的模型名（如 `deepseek-chat`），与官网文档逐字核对
修复建议：新接入服务商时先查阅官方文档确认模型名称大小写
**严重级别**：HIGH

#### 维度 27：预设切换后下拉框状态反射

检查信号：Grep `applyPreset` 函数中是否设置了 `selectedPreset.value = key`
修复建议：预设切换函数中必须同步更新 `selectedPreset` 状态
**严重级别**：MEDIUM

#### 维度 28：页面加载后预设自动匹配

检查信号：Grep `loadConfig` 函数中是否包含基于 `base_url` 的预设自动匹配逻辑
修复建议：在 `presets.value` 赋值后，遍历预设列表匹配 `base_url`
**严重级别**：MEDIUM

#### 维度 29：预设切换时 API Key 不被覆盖

检查信号：Grep `applyPreset` 函数中是否意外设置了 `api_key` 字段
修复建议：预设切换只更新 `base_url` 和 `model`，不触碰 `api_key`
**严重级别**：HIGH

#### 维度 30-33：批量操作与多选交互（合并）

- 【强制】`el-table` 必须提供选择列（`type="selection"`）+ 选中计数 + 二次确认
- 【强制】未选中任何行时批量操作按钮禁用（`:disabled="selectedRows.length === 0"`）
- 【强制】批量删除后剩余记录可能少于当前页，需自动回退到有效页码
- 【强制】确认对话框必须明确告知删除范围和不可恢复声明
**严重级别**：HIGH

#### 维度 34-36：FFmpeg 安装体验（合并）

- 【强制】前端点击下载 FFmpeg 后，后端解压必须包含完整 bin 目录（含 DLL）
- 【强制】FFmpeg 下载需提供进度反馈和合理超时设置（建议 10 分钟）
- 【强制】安装完成后应立即重新检测可用性，向用户反馈成功或失败状态
**严重级别**：MEDIUM

### 维度 37-41：类型契约与状态恢复

#### 维度 37：el-switch 类型契约（int vs bool）

**为什么**：后端返回 `enabled: 1`（int），但 el-switch 默认 `active-value=true`（bool），JS 严格相等 `1 !== true` 导致配置无法持久化。

检查信号：Grep `<el-switch` 无 `:active-value` 且对应后端字段为 int 类型
修复建议：el-switch 显式配置 `:active-value="1" :inactive-value="0"` 与后端 int 类型一致
**严重级别**：CRITICAL

#### 维度 38：blob 请求超时与错误解析

检查信号：Grep `responseType: 'blob'` 无 `timeout: 60000` 且无 `parseBlobError` 函数
修复建议：blob 请求独立配置 `timeout: 60000` + `silent: true`
**严重级别**：HIGH

#### 维度 39：v-loading 状态恢复（visibility 切换）

检查信号：Grep `handleVisibilityChange` 中直接调用 `loadDetail()` 无 `nextTick` 延迟
修复建议：切回时先重置所有 loading 状态为 false，用 `nextTick` 延迟加载
**严重级别**：HIGH

#### 维度 40：页面标题冗余

检查信号：Grep `<span class="page-title">` 且 Layout 侧边栏已有同名菜单项
修复建议：移除页面内 page-title
**严重级别**：LOW

#### 维度 41：频道级配置控件与后端字段对齐

检查信号：Grep 后端 Channel 模型新增字段后，ChannelManagement.vue 表单无对应 `el-form-item`
修复建议：后端新增频道字段时，前端同步添加控件
**严重级别**：HIGH

### 维度 42-46：环境隔离与页面完整性

#### 维度 42：环境隔离与 BASE_URL 配置化

检查信号：Grep `BASE_URL.*localhost` 在 `miniprogram/services/` 下硬编码
修复建议：按 `__wxConfig.envVersion` 切换 BASE_URL
**严重级别**：CRITICAL

#### 维度 43：小程序页面四件套完整性

检查信号：Glob 检查 `miniprogram/pages/*/*.json` 是否每个页面都有对应 .json
修复建议：新建页面必须同步创建 .json/.js/.wxml/.wxss 四个文件
**严重级别**：HIGH

#### 维度 44：事件绑定对称性（on/off 配对）

检查信号：Grep `player.on\w+\(` 后检查 onUnload 是否有对应 `off\w+`
修复建议：所有 onXxx 监听器必须有对应 offXxx 解绑，回调保存为实例属性
**严重级别**：HIGH

#### 维度 45：navigateTo 失败降级

检查信号：Grep `wx.navigateTo` 后无 `fail` 回调
修复建议：navigateTo 失败时降级为 reLaunch
**严重级别**：MEDIUM

#### 维度 46：工具层 bug 识别

检查信号：错误信息含 `system error` / `webviewId` / `appservice` → 工具层
修复建议：降基础库版本 + 清缓存 + 重启工具
**严重级别**：MEDIUM

### 维度 47-49：401 重试/频道同步/脚本兼容

#### 维度 47：401 重试无限循环防护

检查信号：Grep `request` 函数中 401 处理逻辑无 `_retried` 标记
修复建议：排除 `/auth/` 前缀请求触发 401 重试，用 `_retried` 标记最多重试一次
**严重级别**：HIGH

#### 维度 48：前端频道配置与后端数据源同步

检查信号：Grep rss_sources 多选下拉框，检查选项来源是否为动态 API 而非硬编码
修复建议：从 API 动态获取 RSS 源列表
**严重级别**：HIGH

#### 维度 49：前端验证脚本 PowerShell 兼容性

检查信号：Grep `python script.py`（无 -u 参数）在 package.json scripts 中
修复建议：`python -u script.py 2>&1` 禁用缓冲 + 捕获 stderr
**严重级别**：MEDIUM

### 维度 50-51：表单标签语义与密钥获取入口

#### 维度 50：表单字段标签语义明确性

检查信号：Grep `el-form-item\s+label="API Key"` 使用通用名称
修复建议：所有密钥类表单字段 label 必须使用字段的具体业务名称
**严重级别**：MEDIUM

#### 维度 51：密钥获取入口超链接规范化

检查信号：Grep 含密钥字段的表单无 `el-link href` 指向官方控制台
修复建议：提供 `el-link` + `target="_blank"` 指向官方控制台
**严重级别**：MEDIUM

### 维度 52-56：数据库维护与系统清理前端规范

#### 维度 52：左右分栏布局响应式审查

检查信号：Grep `el-aside` 无响应式断点（`@media` 或 `:xs`/`:sm`）
修复建议：配置响应式断点（如 768px 以下切换为上下布局）
**严重级别**：MEDIUM

#### 维度 53：CONFIRM_DELETE 令牌前端交互审查

检查信号：Grep 危险操作按钮使用 `ElMessageBox.confirm` 而非 `ElMessageBox.prompt`
修复建议：使用 `ElMessageBox.prompt` 要求输入令牌字符串
**严重级别**：HIGH

#### 维度 54：级联预览弹窗审查

检查信号：Grep 删除操作处理函数无级联预览 API 调用
修复建议：先展示级联影响预览再确认删除
**严重级别**：HIGH

#### 维度 55：dry_run 预览开关审查

检查信号：Grep 清理页面提交按钮无 `dry_run` 参数
修复建议：dry_run 开关默认开启（预览模式），用户手动切换到执行模式
**严重级别**：MEDIUM

#### 维度 56：审计日志展示审查

检查信号：Grep 审计日志页面是否存在，表格是否包含必要列
修复建议：审计日志展示操作类型/表名/记录ID/操作人/时间
**严重级别**：LOW

### 维度 57-60：SonarQube 迭代闭环

#### 维度 57：未使用导入检测（SonarQube S1128）

- 【强制】Vue SFC `<script setup>` 中的 import 必须被使用
- 【强制】import 语句删除前确认未在 template 中使用
- 判断信号：eslint `no-unused-vars` 警告、SonarQube S1128 issue
- **严重级别**：WARN

#### 维度 58：import 语句组织（SonarQube S3863）

- 【强制】import 语句分三组：标准库/Vue 内置 → 第三方库 → 项目内，每组按字母序
- 判断信号：eslint `import/order` 警告
- **严重级别**：INFO

#### 维度 59：DOM API 现代化（SonarQube S7762）

- 【强制】废弃 API 必须替换：`removeChild(el)` → `el.remove()`、`appendChild` → `append`
- 判断信号：grep `removeChild(`、`appendChild`、`.className\s*=`
- **严重级别**：WARN

#### 维度 60：空 catch 块检测（SonarQube S2486）

- 【强制】catch 块禁止为空或仅 `console.error`，必须包含用户提示或显式注释
- 判断信号：grep `catch\s*\([^)]*\)\s*\{\s*\}`
- **严重级别**：WARN

### 维度 61-69：小程序播放与跨端数据流

#### 维度 61：非 ASCII 文件名 URL 编码审查

- 【强制】含中文文件名的 URL 必须用 `encodeURIComponent` 编码，再拼接基础 URL
- 判断信号：grep `new URL.*[\u4e00-\u9fff]` 含中文的 URL 构造
- **严重级别**：CRITICAL（404 导致资源加载失败）
- 配置节点：`config.yaml#url_safety_check`

#### 维度 62：倍速切换 iOS pause/play 序列

- 【强制】iOS 端切换 playbackRate 前必须先 pause → 设 rate → play → seek
- 判断信号：grep `playbackRate\s*=` 前无 `pause\(\)`
- **严重级别**：HIGH
- 配置节点：`config.yaml#miniprogram_playback_safety.rate_switch`

#### 维度 63：onTimeUpdate 节流规范

- 【强制】`audioManager.onTimeUpdate` 回调内 `setData` 必须用时间戳节流（默认 800ms）
- 判断信号：grep `onTimeUpdate` 后直接 `setData` 无时间戳判断
- **严重级别**：HIGH（UI 卡顿）
- 配置节点：`config.yaml#miniprogram_playback_safety.time_update_throttle`

#### 维度 64：异步上报防重叠标志

- 【强制】异步上报函数必须用模块级 `progressReporting` 标志位包裹，`finally` 中清除
- 判断信号：grep `async function report\w+` 后无 `if (reporting) return`
- **严重级别**：HIGH
- 配置节点：`config.yaml#miniprogram_playback_safety.progress_report`

#### 维度 65：seek 操作 pendingSeek 标志位

- 【强制】`audioManager.seek()` 必须用模块级 `pendingSeek` 标志位记录目标位置
- 判断信号：缺模块级 `let pendingSeek = null` 声明
- **严重级别**：HIGH
- 配置节点：`config.yaml#miniprogram_playback_safety.seek`

#### 维度 66：高频 setter lastApplied 缓存

- 【强制】`playbackRate`/`volume` 等高频 setter 必须用 `lastAppliedRate` 缓存上次应用值
- 判断信号：grep `audioManager\.playbackRate\s*=\s*` 在 onTimeUpdate 内
- **严重级别**：MEDIUM
- 配置节点：`config.yaml#miniprogram_playback_safety.cached_setters`

#### 维度 67：列表页与详情页布局分离

- 【强制】列表页禁止内嵌完整播放卡片组件，点击必须 `wx.navigateTo` 跳转详情页
- 判断信号：grep `<player-card` 在 `pages/index/` 或 `pages/history/`
- **严重级别**：HIGH
- 配置节点：`config.yaml#miniprogram_layout_separation`

#### 维度 68：频道/筛选切换状态隔离

- 【强制】频道切换时必须清空所有关联状态字段（episode/script/segments/comments 等）
- 判断信号：grep `currentChannelId\s*=` 后 `setData` 仅清 `todayList`
- **严重级别**：HIGH
- 配置节点：`config.yaml#miniprogram_state_isolation`

#### 维度 69：跳转详情页前恢复播放

- 【强制】从浮动按钮/历史列表跳转到详情页前必须调用 `resumePlay()` 恢复播放
- 判断信号：grep `wx\.navigateTo.*detail\?id=` 前无 `resumePlay\(\)`
- **严重级别**：HIGH
- 配置节点：`config.yaml#miniprogram_navigation_safety`

### 维度 70-74：SonarQube 全项目扫描

#### 维度 70：NOSONAR 注释位置正确性（前端语法）

- 【强制】前端 NOSONAR 按文件类型使用对应语法（`.js` → `// NOSONAR`、`.vue <template>` → `<!-- NOSONAR -->`、`.wxss` → `/* NOSONAR */`）
- 【强制】NOSONAR 大小写敏感（必须全大写）
- **严重级别**：CRITICAL
- 配置节点：`config.yaml#nosonar_positioning_frontend`

#### 维度 71：SonarQube 扫描环境兼容性（Node.js 版本预检）

- 【强制】Node.js > 20.99.0 时跳过 JS/TS 扫描
- 【强制】PowerShell 5 调用 sonar-scanner 必须用 `.bat` 封装
- **严重级别**：HIGH
- 配置节点：`config.yaml#sonarqube_environment_frontend`

#### 维度 72：并行子代理修复结果核查

- 【强制】子代理报告"已加 NOSONAR"必须用 grep 二次验证
- 【强制】派发给子代理的文件组必须互斥
- **严重级别**：HIGH
- 配置节点：`config.yaml#parallel_subagent_verification_frontend`

#### 维度 73：前端测试失败 git stash 验证

- 【强制】前端测试失败时必须用 `git stash` 暂存修改后跑测试验证基线
- **严重级别**：HIGH
- 配置节点：`config.yaml#test_failure_diagnosis_frontend`

#### 维度 74：NOSONAR 抑制 vs 代码修复决策

- 【强制】`must_fix_rules` 中的规则禁止用 NOSONAR 抑制，必须实际修复代码
- 【强制】`can_suppress_rules` 允许抑制但必须注释说明原因
- **严重级别**：CRITICAL
- 配置节点：`config.yaml#nosonar_decision_matrix_frontend`

### 维度 75-77：跨项目模块迁移

#### 维度 75：跨项目模块迁移 7 步法

- 【强制】跨项目迁移必须执行：需求确认 → 架构对齐 → 后端开发 → 前端开发 → 测试 → 构建验证
- 判断信号：跳过架构对齐步骤直接复制代码
- **严重级别**：HIGH
- 配置节点：`config.yaml#cross_project_migration_frontend`

#### 维度 76：前端嵌套目录相对路径校验

- 【强制】`views/<module>/<Page>.vue` 嵌套目录下 SCSS `@use` 和 JS `import` 的相对路径必须按嵌套层级计算（`../../` 而非 `../`）
- 判断信号：grep `@use '\.\./styles/'` 在嵌套目录中
- **严重级别**：CRITICAL
- 配置节点：`config.yaml#frontend_nested_paths`

#### 维度 77：UI 图标跨库迁移存在性验证

- 【强制】从参考项目迁移图标时必须验证图标在目标 UI 库中存在
- 判断信号：grep `from '@element-plus/icons-vue'` 后跟非标准图标名
- **严重级别**：HIGH
- 配置节点：`config.yaml#icon_migration_frontend`

### 维度 78-82：综合复盘

#### 维度 78：菜单分组与角色可见性审查

- 【强制】菜单数量 ≥ 10 时必须按功能分组（`el-sub-menu`），通过路由 `meta.group` 配置
- 【强制】角色可见性控制：未在 `visible_roles` 中的角色不渲染该分组
- 判断信号：grep `routes.length >= 10` 但 Layout.vue 无 `el-sub-menu`
- **严重级别**：HIGH
- 配置节点：`config.yaml#menu_grouping_check`

#### 维度 79：PWA 图标与 manifest 审查

- 【强制】`public/manifest.json` 含 192x192 和 512x512 图标 + `"purpose": "any maskable"`
- 【强制】`index.html` 引用 manifest.json + theme-color meta 标签
- 判断信号：grep `manifest.json` 无 `"purpose": "any maskable"`
- **严重级别**：HIGH
- 配置节点：`config.yaml#pwa_icon_check`

#### 维度 80：图片封面渲染与降级审查

- 【强制】小程序图片加载失败（`binderror`）必须自然降级（隐藏图片容器）
- 【强制】图片必须使用 `lazy-load` 模式
- 判断信号：grep `<image` 无 `binderror` 事件绑定
- **严重级别**：MEDIUM
- 配置节点：`config.yaml#cover_image_rendering_check`

#### 维度 81：About/Help 模块完整性审查

- 【强制】About 页面必须展示版本号/git_sha/build_date，从后端 `/api/about` 获取
- 判断信号：grep About.vue 无 `git_sha` 字段
- **严重级别**：LOW
- 配置节点：`config.yaml#about_help_module_check`

#### 维度 82：菜单点击导航 fallback 审查

- 【强制】菜单点击后比对导航前后 URL，若一致说明导航失败，需 fallback
- 判断信号：grep 菜单点击无 URL 变化比对
- **严重级别**：MEDIUM
- 配置节点：`config.yaml#menu_navigation_fallback_check`

### 维度 83-90：小程序跨页面一致性

#### 维度 83：最小化防护（ElMessage 安全包装器）

- 【强制】`ElMessage` 调用前必须检查 `document.visibilityState`，hidden 时跳过
- 判断信号：grep 拦截器中直接 `ElMessage.error(` 无 visibility 检查
- **严重级别**：HIGH

#### 维度 84：router.replace 异步时序

- 【强制】`router.replace` 后立即读取 `route.query` 可能读到旧值，需 `await router.isReady()`
- **严重级别**：HIGH

#### 维度 85：PWA manifest 配置化

- 【强制】`display` 字段从配置读取，禁止硬编码
- **严重级别**：MEDIUM

#### 维度 86：跨浏览器兼容性

- 【强制】`blur`/`visibilitychange` 联合判断，Edge blur 先于 visibilitychange
- **严重级别**：MEDIUM

#### 维度 87：HTMLElement.prototype.focus 拦截

- 【强制】拦截 `focus` 防止最小化时激活窗口
- **严重级别**：MEDIUM

#### 维度 88：SSE 隐藏断开

- 【强制】页面隐藏时断开 SSE 连接（`eventSource.close()`），显示时重新建立
- **严重级别**：MEDIUM

#### 维度 89：连续修复失败重评机制

- 【强制】同一问题连续代码修复 ≥3 轮未解决时触发重评
- **严重级别**：MEDIUM

#### 维度 90：UI 异常诊断决策树

- 【强制】UI 异常必须先确认无痕模式是否正常，再决定是环境问题还是代码问题
- **严重级别**：MEDIUM

### 维度 91-94：TTS 多 Provider 前端 UI

#### 维度 91：Provider 切换 UI 联动审查

- 【强制】Provider 切换控件必须绑定 `@change` 事件触发表单联动
- 【强制】切换 Provider 不残留其他 Provider 的字段值
- 判断信号：grep `el-radio-group.*provider` 无 `@change` 事件
- **严重级别**：HIGH
- 配置节点：`config.yaml#tts_provider_switch_ui_check`

#### 维度 92：动态表单按 Provider 联动审查

- 【强制】每个 Provider 的专属字段必须用 `v-if="ttsForm.provider === '<provider>'"` 条件渲染
- 【强制】切换 Provider 时清空非通用字段
- 判断信号：grep 条件渲染无条件判断
- **严重级别**：HIGH
- 配置节点：`config.yaml#tts_dynamic_form_check`

#### 维度 93：图标导入完整性审查（Connection 图标案例）

- 【强制】所有使用的 Element Plus 图标必须在 import 语句中声明
- 判断信号：对比模板中使用的图标名与 import 的图标名，差集为违规
- **严重级别**：HIGH
- 配置节点：`config.yaml#element_plus_icon_import_check`

#### 维度 94：降级链路配置 UI 审查

- 【强制】降级链路配置区块必须存在，placeholder 提示格式
- 判断信号：grep `fallback_providers` 前端无配置入口
- **严重级别**：HIGH
- 配置节点：`config.yaml#tts_fallback_config_ui_check`

### 维度 95-96：外部服务降级与音频 URL

#### 维度 95：前端音频 URL 适配性审查

- 【强制】前端 audio 标签 src 必须同时支持绝对 URL 与相对路径
- 【强制】小程序端 `dataUrl` 必须为绝对 URL，相对路径需先拼接 `BASE_URL`
- 判断信号：grep `audio.*src.*=.*http` 仅匹配绝对 URL
- **严重级别**：HIGH
- 配置节点：`config.yaml#audio_url_adaptability_check`

#### 维度 96：前端降级模式 UI 提示审查

- 【强制】`is_cos_configured = false` 时必须显示 `el-alert` 降级提示
- 判断信号：grep `is_cos_configured` 无对应 UI 状态展示
- **严重级别**：HIGH
- 配置节点：`config.yaml#storage_fallback_ui_check`

### 维度 97-100：浏览器环境诊断与防御纵深

#### 维度 97：浏览器窗口管理

- 【强制】`window.focus()` 调用前检查 `visibilityState`，hidden 时跳过
- 【强制】ElMessage 使用安全包装器
- **严重级别**：HIGH

#### 维度 98：PWA manifest 配置化（补充）

- 【强制】manifest 相关配置必须从 config.yaml 读取
- **严重级别**：MEDIUM

#### 维度 99：跨浏览器事件测试

- 【强制】关键事件序列（blur/visibilitychange）必须在 Edge/Chrome/Firefox 上测试
- **严重级别**：MEDIUM

#### 维度 100：UI 异常诊断决策流程

- 【强制】UI 异常（窗口焦点/事件）必须先执行：无痕模式测试 → 浏览器差异验证 → 配置文件检查，再进入代码修复
- **严重级别**：MEDIUM

### 维度 101-103：频道管理与表单类型契约

#### 维度 101：el-switch 类型契约（补充）

同维度 37，强调 int 0/1 与 bool true/false 的类型匹配。
**严重级别**：CRITICAL
配置节点：`config.yaml#switch_type_contract_check`

#### 维度 102：请求级超时配置

- 【强制】长耗时接口（AI 生成/大文件上传）必须用请求级 `timeout` 覆盖全局默认
- 判断信号：grep `generate\|upload\|batch` API 调用无 `timeout` 参数
- **严重级别**：HIGH
- 配置节点：`config.yaml#api_timeout_override_check`

#### 维度 103：频道级表单字段初始化

- 【强制】表单打开编辑时必须对后端返回字段做类型转换（如 `is_active = row.is_active ? 1 : 0`）
- 判断信号：grep `openEdit` 中字段初始化类型不一致
- **严重级别**：HIGH
- 配置节点：`config.yaml#channel_form_init_check`

### 维度 104-108：AI 配置持久化与跨页同步

#### 维度 104：UI 图标库存在性验证

- 【强制】`meta.icon` 引用的图标名必须在目标图标库中存在
- 判断信号：`node -e "import('@element-plus/icons-vue').then(m => console.log(Object.keys(m)))"`
- **严重级别**：HIGH
- 配置节点：`config.yaml#icon_library_existence_check`

#### 维度 105：Router query 跨页参数同步

- 【强制】跨页面参数传递必须通过 `router.push({ path, query })`，目标页 `onMounted` 读取 `route.query`
- 判断信号：grep `router\.push` 无 `query`
- **严重级别**：HIGH
- 配置节点：`config.yaml#router_query_sync_check`

#### 维度 106：配置键四端对齐

- 【强制】前端字段名/路由模型字段名/数据库配置键/Settings 属性必须一致
- 判断信号：前端字段名与后端 CONFIG_KEY_MAP 键名不一致
- **严重级别**：HIGH
- 配置节点：`config.yaml#config_key_alignment_check`

#### 维度 107：表单 Body 对齐

- 【强制】前端提交的 form 字段集必须与后端 Pydantic Body 模型字段集一致
- 判断信号：grep `class.*Body.*BaseModel` 字段集与前端 form 字段集差异
- **严重级别**：HIGH
- 配置节点：`config.yaml#form_body_alignment_check`

#### 维度 108：时间本地化显示

- 【强制】工作流/统计页面的 UTC 时间必须本地化显示（`dayjs`/`formatDateTime`）
- 判断信号：grep `created_at` 无 formatDateTime/dayjs
- **严重级别**：MEDIUM
- 配置节点：`config.yaml#workflow_time_localization_check`

### 维度 109-112：前端响应处理与按需加载

#### 维度 109：响应拦截器 blob/二进制响应处理

- 【强制】响应拦截器开头必须判断 `response.config?.responseType === 'blob'`，命中时直接返回
- 判断信号：拦截器中无前置 `responseType` 判断
- **严重级别**：CRITICAL
- 配置节点：`config.yaml#blob_response_interceptor_check`

#### 维度 110：内联 audio/video 控件的 blob URL 内存释放

- 【强制】组件 `onUnmounted` 时必须调用 `URL.revokeObjectURL` 释放所有 blob URL
- 判断信号：创建点数量 > 释放点数量
- **严重级别**：HIGH
- 配置节点：`config.yaml#blob_url_lifecycle_check`

#### 维度 111：按需加载策略

- 【强制】列表页禁止预加载所有行的媒体文件（`Promise.all(rows.map(fetchBlob))`）
- 判断信号：grep `loadList` 中含 `api.get.*blob`
- **严重级别**：HIGH
- 配置节点：`config.yaml#on_demand_loading_check`

#### 维度 112：工作流重跑前端行为

- 【强制】重跑成功后禁止 `router.replace` 跳转新路由，改为 `await loadDetail(workflowId)` 刷新当前页
- 判断信号：grep `rerun` 回调中含 `router.replace`
- **严重级别**：HIGH
- 配置节点：`config.yaml#workflow_rerun_behavior_check`

### 维度 113-116：跨项目移植与编码规范

#### 维度 113：跨项目移植前端适配检查

- 【强制】移植前必须执行 4 项前端适配：命名约定/UI 组件库/API 契约/认证模型
- 【强制】移植后验证无源项目特有命名残留
- **严重级别**：HIGH

#### 维度 114：前端 computed 命名避让内置属性

- 【强制】computed 名称不得与同文件中 `el-*` 组件的内置 prop 同名（如 `duration`/`size`/`type`）
- 【强制】computed 命名推荐加前缀：`calculatedXxx` / `expectedXxx`
- 判断信号：grep `const duration = computed\|const size = computed\|const type = computed`
- **严重级别**：HIGH
- 配置节点：`config.yaml#frontend_computed_naming_safety`

#### 维度 115：前端参数计算器联动显示

- 【强制】参数计算器必须支持三参数（时长/字数/语速）联动计算
- 【强制】预设方案必须通过配置管理，禁止硬编码
- 判断信号：grep `ParamCalculator` 无路由注册
- **严重级别**：HIGH
- 配置节点：`config.yaml#param_calculator_check`

#### 维度 116：前端修改后构建验证

- 【强制】.vue/.js 文件修改后必须执行 `npm run build` 验证（exit 0 方可认定完成）
- 判断信号：修改 .vue/.js 后无 `npm run build` 执行记录
- **严重级别**：HIGH
- 配置节点：`config.yaml#dual_verification_workflow`

### 维度 117-118：前端空数据分层诊断

#### 维度 117：前端列表空数据分层诊断

- 【强制】前端空数据 issue 必须附上三层诊断：
  1. API 返回 total 字段值
  2. 后端日志确认步骤状态
  3. 数据库实际记录数
- 【强制】前端列表组件应区分"加载中"、"加载完成无数据"、"加载失败"三种状态
- 判断信号：前端空数据 issue 直接定性为渲染 bug 无分层诊断 → 违规
- **严重级别**：HIGH
- 配置节点：`config.yaml#frontend_empty_data_diagnosis_check`

#### 维度 118：素材面板空数据后端根因排查

- 【强制】素材面板空数据时，前端应显示后端诊断信息（crawl 步骤状态、素材总数）
- 【强制】素材面板空数据须区分「dev 空」与「打包模式空」：exe 模式 COS 已配置时本地无副本，须确认后端 list_audio 已回退 DB 远程 URL（path=云端(COS)），而非前端渲染问题
- 【强制】素材面板应调用 API 获取 total 字段，而非仅依赖列表长度判断
- 判断信号：grep 素材面板组件无 `total` 字段读取 → 违规
- **严重级别**：MEDIUM
- 配置节点：`config.yaml#frontend_empty_data_diagnosis_check`

### 维度 119：详情面板懒加载

> 来源：2026-08-05 复盘（规范 R192）。详情页三面板数据量大，一次性加载增加首屏耗时与接口压力。

**配置节点**：`config.yaml#checklist` → `detail_panel_lazy_load`

- 【强制】工作流详情页素材/TTS/成品面板须用 `activePanels` + 变更处理器按需加载，禁止 `onMounted`/`created` 一次性拉全
- 判断信号：grep 详情页 `onMounted`/`created` 同时拉取素材+TTS+成品且无面板激活判断 → 违规
- **严重级别**：HIGH

### 维度 120：远程音频代理播放

> 来源：2026-08-05 复盘（规范 R193）。直连 COS 公网 URL 暴露签名且无法做 SSRF 收敛与统一鉴权。

**配置节点**：`config.yaml#checklist` → `remote_audio_proxy_playback`

- 【强制】远程（云端）音频必须经由 `proxy_audio` 端点播放，禁止前端直接拼接 COS 公网 URL
- 不适用：本地 `/audio/<key>` 直读
- 判断信号：grep 前端 `new Audio(`/`<audio src=` 直接拼接 `cos`/`.myqcloud.com` URL → 违规
- **严重级别**：HIGH

### 维度 121：远程资源删除保护

> 来源：2026-08-05 复盘（规范 R194）。云端对象与本地文件生命周期不同，前端误删无法本地恢复。

**配置节点**：`config.yaml#checklist` → `remote_resource_delete_protect`

- 【强制】`path` 标记远程（云端）的资源前端禁用删除/本地文件操作
- 判断信号：grep 前端对 `item.path === "云端(COS)"` 仍渲染删除按钮 → 违规
- **严重级别**：HIGH

### 维度 122：字段契约展示一致性

> 来源：2026-08-05 复盘（规范 R195/R191）。远程项 `size_bytes=0` 若直接渲染会误判无数据。

**配置节点**：`config.yaml#checklist` → `field_contract_display`

- 【强制】前端对 `size_bytes=0`（远程）与 `path="云端(COS)"` 须正确展示语义标签，禁止显示 0/空误判无数据
- 判断信号：grep 前端直接渲染 `item.size_bytes` 未区分本地/远程 → 违规
- **严重级别**：MEDIUM

---

## 配置节点索引

各维度的 `config.yaml` 配置节点汇总（详细配置见 `config.yaml` 本身）：

| 维度范围 | 配置根节点 | 说明 |
|----------|-----------|------|
| 1-15 | `checklist` | 15 大类开关 |
| A-M | `review_dimensions` | 补充审查要点开关 |
| 16-36 | `hard_constraints.rules` | 硬约束规则扩展 |
| 37-41 | `hard_constraints.rules` | 类型契约与状态恢复 |
| 42-46 | `hard_constraints.rules` | 环境隔离与页面完整性 |
| 47-49 | `hard_constraints.rules` | 401 重试/频道同步/脚本兼容 |
| 50-51 | `review_dimensions` | 表单标签语义与密钥入口 |
| 52-56 | `hard_constraints.rules` | 数据库维护与系统清理 |
| 57-60 | `sonarqube_checklist` | SonarQube 迭代闭环 |
| 61-69 | `miniprogram_playback_safety` 等 | 小程序播放安全 |
| 70-74 | `nosonar_positioning_frontend` 等 | SonarQube 全项目 |
| 75-77 | `cross_project_migration_frontend` 等 | 跨项目迁移 |
| 78-82 | `menu_grouping_check` 等 | 综合复盘 |
| 83-90 | `browser_window_management_check` 等 | 浏览器环境诊断 |
| 91-94 | `tts_provider_switch_ui_check` 等 | TTS 多 Provider UI |
| 95-96 | `audio_url_adaptability_check` 等 | 外部服务降级 |
| 97-100 | `ui_diagnosis_flow_check` 等 | 浏览器防御纵深 |
| 101-103 | `switch_type_contract_check` 等 | 频道管理与表单类型 |
| 104-108 | `icon_library_existence_check` 等 | AI 配置持久化 |
| 109-112 | `blob_response_interceptor_check` 等 | 响应处理与按需加载 |
| 113-116 | `frontend_computed_naming_safety` 等 | 跨项目移植与编码规范 |
| 117-118 | `frontend_empty_data_diagnosis_check` | 空数据分层诊断（含打包模式 COS 根因） |
| 119-122 | `detail_panel_lazy_load` / `remote_audio_proxy_playback` / `remote_resource_delete_protect` / `field_contract_display` | 打包模式面板懒加载/远程资源 |
| FE-196~FE-200 | `remote_resource_display_check` / `build_metadata_display_check` / `packaging_fallback_ui_check` / `hls_cold_start_retry_check` / `wechat_privacy_scope_check` | V3.0 会话复盘（DS-5/6/13/14） |
| FE-201 | `backend_switch_field_passthrough_check` | V3.1 会话复盘（DS-15 媒体特性可开关化与真静音） |

---

## V3.0 2026-08-05 会话复盘新增前端审查维度（FE-196~FE-200）

> 来源：打包模式三面板空白、关于页版本失真、HLS 首播冷启动失败、微信剪贴板隐私未声明四类真实问题。完整规则、判断信号与代码示例见 news-code-dev `references/diagnostic-standards.md` 的 DS-5 / DS-6 / DS-13 / DS-14；参数全部由 `config.yaml` 对应节点管理（无硬编码）。

### 维度 FE-196：远程资源字段契约展示一致性（DS-5）
**配置节点**：`config.yaml#remote_resource_display_check`
- 【强制】远程来源 `path` 返回语义值（如「云端(COS)」）；`size_bytes` 未知须置 0 且前端展示不为空/异常；删除按钮 `v-if` 排除远程项（`!row.remote`）；远程 blob 走 SSRF 白名单代理端点
- 判断信号：grep `云端(COS)`/`path.*COS`/`row.remote`；`size_bytes`；`v-if=.!.*remote`；`proxy?url=`
- 严重级别：HIGH
- 适用/不适用：适用 exe/打包部署且 COS 已配置；不适用纯开发模式（本地优先）

### 维度 FE-197：关于页/版本真实发布日展示（DS-6）
**配置节点**：`config.yaml#build_metadata_display_check`
- 【强制】GitHub ISO 必须转 UTC+8（`_formatPublishedAt`）；检查更新必须基于真实 version；禁止写死 `git_sha="unknown"`/`build_date`/`version="1.0.0"`；ISO 解析失败兜底防御
- 判断信号：grep `_formatPublishedAt`；`git_sha|build_date|version`；`checkUpdate`
- 严重级别：MEDIUM
- 适用/不适用：适用有版本发布流程的项目；不适用一次性无发布脚本

### 维度 FE-198：打包模式回退 UI 一致性（DS-5）
**配置节点**：`config.yaml#packaging_fallback_ui_check`
- 【强制】详情页素材/TTS/成品面板在 COS 回退下必须可展示（非空面板）；远程 blob 走代理端点；`activePanels` 懒加载避免首屏拉空
- 判断信号：grep `activePanels`；`is_cos_configured|sys.frozen`；`proxy?url=`；`remote:true|row.remote`
- 严重级别：HIGH
- 适用/不适用：同 FE-196

### 维度 FE-199：HLS 首播冷启动静默重试与降级（DS-13）
**配置节点**：`config.yaml#hls_cold_start_retry_check`
- 【强制】小程序 `BackgroundAudioManager` 首播 HLS(m3u8) `onError` 必须有静默重试分支（`MAX_HLS_RETRY=1`，不弹错、不中断 loading）；重试耗尽回退 mp3 直链
- 判断信号：grep `onError`/`MAX_HLS_RETRY`/`currentRetry`/`mp3Url|_applyProtocol`/`BackgroundAudioManager`
- 反模式：`onError` 直接 `showToast` 并 `loading=false`（首播冷启动被误判致命）
- 严重级别：HIGH
- 适用/不适用：适用小程序/H5 播 HLS 流式音频；不适用纯本地 mp3 直链

### 维度 FE-200：微信隐私合规 scope 声明（DS-14）
**配置节点**：`config.yaml#wechat_privacy_scope_check`
- 【强制】敏感 API（`setClipboardData`/`getClipboardData`/位置/相册等）调用前必须 `requirePrivacyAuthorize`/`onNeedPrivacyAuthorization`；后台须声明对应 scope（剪贴板读写共用「剪贴板」scope，非「写入剪贴板」/ `setClipboardData` 字面量）
- 判断信号：grep `setClipboardData|getClipboardData`；`requirePrivacyAuthorize|onNeedPrivacyAuthorization`
- 反模式：直接 `setClipboardData(` 且无授权流程包裹
- 严重级别：CRITICAL（真机报 `setClipboardData:fail api scope is not declared in the privacy agreement`）
- 适用/不适用：适用微信小程序调用隐私接口；不适用非微信平台

---

## V3.1 2026-08-05 段间静音/bgm_gap_mode 复盘新增前端审查维度（FE-201）

> 来源：段间静音做成可开关 `bgm_gap_mode`(silence/bridge) 后，前端须保证通用 axios 透传不丢新字段，并在列表/编辑表单显式展示与编辑该开关；后端 `NULL`（继承全局）与前端"继承/自定义"往返一致。完整规则与代码示例见 news-code-dev `references/diagnostic-standards.md` 的 DS-15；参数全部由 `config.yaml` 对应节点管理（无硬编码）。

### 维度 FE-201：后端新增开关/枚举字段的前端透传与列表列展示（DS-15）
**配置节点**：`config.yaml#backend_switch_field_passthrough_check`
- 【强制】通用 axios 透传包装（取 `response.data` 直传）不得裁剪/重命名后端新增字段（snake_case 直传）；后端新增开关/枚举字段（如 `bgm_gap_mode`）须在列表新增展示列，并在编辑表单提供控件（如下拉 silence/bridge）
- 【强制】后端 `NULL` 表示"继承全局"，前端编辑表单须提供"继承"选项，选择时回传 `null`，避免频道误覆盖全局默认（inherit→null 往返一致）
- 判断信号：grep 透传包装 `return res.data|return response.data`；列表/表单是否覆盖 `watch_switch_fields` 中字段；表单是否建模"继承"语义
- 反模式：透传裁剪字段导致开关不可见；表单硬编码具体值、无"继承"选项导致全局默认被静默覆盖
- 严重级别：HIGH
- 适用/不适用：适用后端新增开关/枚举字段需前端展示编辑；不适用后端字段已在前端硬编码映射的遗留接口
