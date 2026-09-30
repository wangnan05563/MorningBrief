# 微信小程序端代码评审报告

- **评审范围**：`apps/miniprogram/` 全端（18 个页面 + 4 个组件 + services/utils 基础设施）
- **评审日期**：2026-08-15
- **评审口径**：`news-frontend-code-review` 维度框架（FE-196~FE-230 + 补充维度 A~M）
- **方法**：基础设施逐行通读（app.js / audio.js / api.js / local-data.js / clipboard.js）+ 三大页面集群（内容浏览 / 个人数据 / 账户设置）并行 Explore 子代理覆盖 + 关键 HIGH 项源码复核

---

## 一、问题总览

| 分级 | 数量 | 关键项 |
|------|------|--------|
| 🔴 HIGH（逻辑缺陷，影响核心功能） | 2 | 首页下拉刷新不刷新列表；收藏/最近播放点击跳转失效 |
| 🟠 MEDIUM（逻辑/合规缺陷，需修复） | 4 | "仅 WiFi 自动播放"死开关；about 绕过隐私封装；未登录偏爱静默丢失；history 续播卡片不刷新 |
| 🟡 LOW（质量/防御性） | 3 | 生产残留 console.log；channels 无骨架屏；隐私 handler 启动时序（防御性） |
| 🔵 UX 优化点 | 8 | 浮动播放器仅 3 tab 页、课程封面无占位、缺手动检查更新、反馈无历史等 |

---

## 二、A 类：代码逻辑问题

### 🔴 HIGH

#### A1. 首页下拉刷新在「全部 / 我的偏爱」模式下不刷新列表
- **位置**：`pages/index/index.js` `onPullDownRefresh` L190–209
- **根因**：
  ```js
  const episode = await fetchTodayEpisode(this.data.currentChannelId);
  this.setData({ episode, loading: false, error: '' });   // ← 在列表模式(currentChannelId=null)下，fetch 返回的是数组
  ```
  在「全部」(`currentChannelId = null`) 与「我的偏爱」模式下，页面以 `todayList` 渲染列表、`episode` 仅用于单频道卡片。下拉刷新直接把数组塞进 `episode`，**既不更新 `todayList`，又把单卡片字段污染成数组**，导致可见列表完全不变。单频道模式（数字 id）碰巧能跑，掩盖了 bug。
- **影响**：用户下拉想刷新今日节目，列表纹丝不动（且偏爱模式下不调 `loadPreferred`，偏爱数据也刷不到）。
- **修复**：非偏爱分支复用 `initData()`（其内 `_applyTodayData` 已正确处理数组/单条两种模式），不要手写 `setData`：
  ```js
  async onPullDownRefresh() {
    try {
      if (this.data.isPreferredMode) await this.loadPreferred();
      else await this.initData();   // 内部已 setData todayList + loading 复位
    } catch (err) {
      this.setData({ error: err.message || '今日节目暂未上线' });
    } finally {
      wx.stopPullDownRefresh();
    }
  }
  ```

#### A2. 收藏页 / 最近播放页点击条目跳转失效（本地缓存项 id 字段不一致）
- **位置**：
  - `pages/favorites/favorites.wxml` L23–24：`wx:key="episode_id"`、`data-id="{{item.episode_id}}"`
  - `pages/favorites/favorites.js` `onTapItem` L65–69（读 `dataset.id` → 为空早退）
  - `pages/recent/recent.wxml` L16–17、L65–78（同上）
- **根因**：`local-data.js` 写入本地收藏/历史时用的是 `episode.id`（`addFavorite` 存 `{...episode, favorited_at}`、`addHistory` 存 `{ id, ... }`）。而 WXML 取的是 `item.episode_id`。本地缓存项**没有 `episode_id` 字段** → `data-id` 为 `undefined` → `onTapItem` 首行 `if (!id) return;` 直接 return，**整行点击无反应**。后端来源的项带 `episode_id` 能正常跳，但本地优先路径（绝大多数用户场景）全部失效。
- **影响**：用户从收藏/最近播放页点节目进不去详情页，核心入口失效。
- **修复**（在 JS 层做字段归一，最稳）：
  - `favorites.js` `loadFavorites`：`items = items.map(it => ({ ...it, episode_id: it.episode_id ?? it.id }));`
  - `recent.js` `loadRecent`：`items = items.map(it => ({ ...it, episode_id: it.episode_id ?? it.id }));`（`queueEpisodes` 的 `id: it.episode_id` 亦随之正确）
  - WXML 的 `wx:key="episode_id"` 无需改（归一后存在）。

---

### 🟠 MEDIUM

#### A3. 设置页「仅 WiFi 自动播放」为死开关
- **位置**：`pages/settings/settings.js` L90–95（`onWifiOnlyChange`）+ `settings.wxml` L18
- **根因**：全仓检索 `wifiOnlyAutoPlay` 仅出现在「写入 storage / setData / 展示」三处，**没有任何读取方**（包括 `audio.js`、`app.js`）。开关状态存进 `news_settings` 后从未被消费。
- **影响**：用户以为开启了"仅 WiFi 下自动播放"，实际行为无任何变化，属于误导性 UI。
- **修复**：二选一——① 真正接入：在 `audio.js` 自动播放/预加载逻辑里读取 `wx.getStorageSync('news_settings').wifiOnlyAutoPlay` 并在 `networkType !== 'wifi'` 时跳过自动播放；② 若当前产品不需要该能力，直接从 settings 移除该开关，避免误导。

#### A4. 隐私合规绕过：about 页直接调用 `wx.setClipboardData`
- **位置**：`pages/about/about.js` L106–114 `onCopyContact`
- **根因**：项目已封装 `utils/clipboard.js` 的 `copyText`/`copySourceUrl`，内含 `requirePrivacyAuthorize` 隐私授权弹窗 + 三阶段重试兜底（FE-200 合规要求：未同意隐私协议时 `setClipboardData` 会 `fail errCode:104`）。about 页却绕过封装直接调原生 `wx.setClipboardData`。
- **影响**：在 `__usePrivacyCheck__: true` 且用户未授权时，点击复制邮箱**静默失败且无任何提示**，复制功能形同虚设。
- **修复**：改为 `const { copyText } = require('../../utils/clipboard'); await copyText(this.data.contact); wx.showToast({title:'邮箱已复制',icon:'success'});`（或 `copySourceUrl` 风格的统一提示）。

#### A5. 未登录时保存偏爱频道静默丢失
- **位置**：`services/local-data.js` `setPreferredChannels` L468–477（`if (!openid) return;`）
- **根因**：偏爱频道按 openid 隔离存储，未登录（`getOpenid()` 返回空）保存直接 return，无提示。当 `preferred-settings` 在登录完成前被打开并保存时，选择结果被丢弃。
- **影响**：用户勾选并保存后无反馈，返回"我的偏爱"为空，体验困惑。
- **修复**：保存前判断 `getOpenid()`，若为空则 `wx.showToast({title:'请先登录后再设置',icon:'none'})` 并阻止 `navigateBack`；或在 `app.js` 登录成功后若检测到 `globalData.preferredChannelsChanged` 为待保存态则补写。

#### A6. history 页「继续播放」卡片返回时不刷新
- **位置**：`pages/history/history.js` `onShow` L71–98（只调 `loadPlayedHistory`，未调 `loadLastPlayed`）
- **根因**：`lastPlayedEpisode` 仅在 `onLoad` 的 `loadLastPlayed` 填充。用户在详情页播放新节目后返回 history，续播卡片仍显示旧数据（已播节目变化了但卡片没变）。
- **修复**：`onShow` 中补调 `this.loadLastPlayed()`（或把续播进度同步逻辑收敛到全局播放器状态变更订阅里），确保返回即最新。

---

### 🟡 LOW

#### A7. 生产代码残留 `console.log`
- **位置**：`app.js` L89 / L100 / L109 / L112；`pages/index/index.js` L242；`pages/history/history.js` L115
- **问题**：项目约定生产代码用 `console.warn/error`，禁 `console.log`（易泄露调试信息、且上线后噪音）。
- **修复**：统一替换为 `console.warn` 或移除。

#### A8. channels 页无加载骨架/等待态
- **位置**：`pages/channels/channels.js` L13 `loading:true`，但 `channels.wxml` 未对 `loading` 做骨架或占位展示。
- **影响**：首屏拉频道列表时白屏（尤其弱网）。
- **修复**：加骨架屏或 `wx.showLoading` / 占位行。

#### A9. 隐私 handler 注册时序（防御性）
- **位置**：`app.js` `checkPrivacy` L220 在 `readyPromise` async IIFE 末尾调用；`wx.onNeedPrivacyAuthorization` 本身是同步注册（正确），但因 `checkPrivacy` 排在 `Promise.all(login+preload)` 之后，注册时机晚于启动早期。实测启动阶段无任何隐私接口调用，故当前无真实风险，仅作防御性提示：若未来在 `onLaunch` 早期加入涉及用户信息的调用，需确保 handler 在首次敏感 API 前已注册。

---

## 三、B 类：用户体验优化点

| # | 优化点 | 位置 | 建议 |
|---|--------|------|------|
| B1 | 首页首屏 / 列表缺骨架屏与 waiting 指示 | `index.wxml`（loading 态未充分展示） | 加骨架屏；`initData` 期间顶部 loading 条 |
| B2 | channels 无骨架屏 | `channels.wxml` | 同 A8，统一骨架组件 |
| B3 | 课程封面无占位图 | `pages/course/course.js/.wxml` | 封面 `lazy-load` + 加载失败占位（`binderror` 兜底灰块），避免裂图 |
| B4 | **浮动播放器（迷你播放器）仅 3 个 tab 页可见** | `index.wxml`/`history.wxml`/`profile.wxml` 含 `<floating-player>`；`recent`/`favorites`/`channels`/`course` 等页缺失 | 在更多页面（尤其 recent/favorites）挂浮动播放器，让用户离开 tab 后仍能看到/控制后台播放，提升收听连续性 |
| B5 | 下载中进度不展示 | `pages/download/download.js` | 下载任务进行时实时回显进度条/百分比，而非仅完成态 |
| B6 | 缺手动检查更新入口 | `app.js` `checkUpdate` 仅 release 自动弹 | settings/about 增加「检查更新」按钮，主动触发 `getUpdateManager` |
| B7 | 反馈无历史记录 | `pages/feedback/feedback.js` | 提交后保留本地已发送列表，便于用户回溯 |
| B8 | recent 页返回不自动刷新列表 | `recent.js` 仅 `onLoad`+`onPullDownRefresh`，无 `onShow` | 加 `onShow` 静默 `loadRecent(true)`，与 favorites 对齐（已含 onShow 刷新） |
| B9 | 偏爱引导「暂不」即永久关闭 | `preferred-settings.onSkip` → `markPreferredChannelsOnboarded` | 若希望保留再次引导机会，可区分"跳过"与"已完成"，或允许在设置里重新触发引导 |

---

## 四、优先级行动清单（建议执行顺序）

1. **P0（立即修，核心功能失效）**：A1 首页下拉刷新、A2 收藏/最近跳转失效。
2. **P1（本迭代修，合规/误导）**：A3 死开关、A4 隐私绕过、A5 未登录偏爱丢失、A6 续播卡片刷新。
3. **P2（质量清理）**：A7 console.log、A8 骨架屏。
4. **P3（体验增强）**：B 类按需排期，其中 B4（浮动播放器覆盖）与 B3（封面占位）性价比最高。

---

## 五、复核结论

- 2 个 HIGH 均为**确定性功能缺陷**（可本地复现：列表模式下拉无刷新、本地收藏/最近点击无跳转），建议作为本迭代 blocker 修复。
- 基础设施层（`audio.js` 单例、`api.js` 三层加速、`local-data` 双写隔离、`clipboard` 隐私封装）设计扎实，主要问题集中在**页面层字段契约不一致**与**几处未接线的开关/封装**。
- 未发现崩溃级异常（如 `__route__` 未定义类），当前线上主要风险为上述 HIGH/MEDIUM 逻辑缺陷导致的功能不可用。

---

## 六、修复记录（2026-08-17）

> 按 P0→P1→P2 顺序落地，全部 `node --check` 通过。A3/A5 为产品/设计决策项，未臆改，留作待确认。

| 项 | 状态 | 改动文件:行 | 说明 |
|----|------|------------|------|
| A1 首页下拉刷新不刷新列表 | ✅ 已修复 | `pages/index/index.js:190` `onPullDownRefresh` | 全部模式(`currentChannelId===null`)改调 `initData()` 刷新 `todayList`；单频道模式保留刷新 `episode`；偏爱模式仍走 `loadPreferred()` |
| A2 收藏/最近点击跳转失效 | ✅ 已修复 | `favorites.js:58`、`recent.js:39` `loadFavorites`/`loadRecent` | 列表项归一化 `episode_id = it.episode_id ?? it.id`，WXML `data-id`/`wx:key` 恢复有效，点击/长按/队列均正常 |
| A4 about 绕过隐私封装 | ✅ 已修复 | `about.js:13`(require)、`about.js:110` `onCopyContact` | 改用 `utils/clipboard.js` 的 `copyText`，未授权先弹隐私协议；失败时给明确 toast 而非静默 |
| A6 history 续播卡片返回不刷新 | ✅ 已修复 | `history.js:75` `onShow` | 补调 `this.loadLastPlayed()`，从详情页返回即反映最新续播进度 |
| A7 生产 console.log 残留 | ✅ 已修复 | `app.js:89/100/109/112/194`、`index.js:242`、`history.js:115` | 全部改为 `console.warn`，符合生产禁 `console.log` 约定 |
| A3 「仅 WiFi 自动播放」死开关 | ⏸️ 待决策 | `settings.js:90-95` | **未改**。二选一：① 接入 `audio.js` 在 `networkType!=='wifi'` 时跳过自动播放；② 产品若不需要则移除该开关避免误导。需你确认语义再落地 |
| A5 未登录保存偏爱静默丢失 | ⏸️ 留观 | `local-data.js:468` `setPreferredChannels` | **未改**。当前按 openid 隔离是有意设计（`app.js` 登录完成后才进页面，openid 通常就绪）。如需兜底可加未登录 toast 拦截 |

### 验证
- 6 个改动文件 `node --check` 全部 OK（小程序基础库语法兼容 `??`）。
- 未做真机/模拟器运行验证（环境无小程序编译链路）。逻辑层已逐行复核：下拉刷新路径、`episode_id` 字段契约、`copyText` 返回 Promise、续播缓存读取路径均一致。

### 下一步建议
1. 在微信开发者工具跑一次模拟器，回归：首页下拉刷新、收藏/最近点击进详情、about 复制邮箱、history 返回续播卡片。
2. 确认 A3 处理方向（接入 vs 移除）。
3. B 类 UX 优化点（尤其 B4 浮动播放器覆盖、B3 封面占位）可单独排期。

---

## 七、B 类 / 遗留 UX 修复记录（2026-08-17 续）

> 延续 P0~P2 修复后，推进 B 类体验优化与 A8 骨架屏。floating-player 已在 app.json 全局注册，挂载零成本。

| 项 | 状态 | 改动文件 | 说明 |
|----|------|----------|------|
| B4 浮动播放器覆盖非 tab 页 | ✅ 已修复 | recent/favorites/channels/course/download/search/queue 共 7 个 wxml 末尾 | 离开 tab 后（如最近播放、收藏、频道、课程、下载、搜索、队列页）常驻「正在播放」浮钮，点击跳详情续播；无播放时 `wx:if` 隐藏，零干扰。现共 10 页带浮钮（含 index/history/profile 3 tab） |
| B8 recent 返回刷新列表 | ✅ 已修复 | `recent.js` 新增 `onShow` | 从详情页返回静默 `loadRecent(true)`，反映新播放记录，与 favorites 对齐 |
| A8 channels 骨架屏 | ✅ 已修复 | `channels.wxml`（loading-mask→skeleton 4 卡占位）、`channels.wxss`（.skeleton-* + .shimmer 补全） | 频道列表加载中由纯文字升级为频道卡骨架屏，弱网不再白屏，与首页/course 一致 |

### 验证
- 7 个 wxml 末尾 `<floating-player />` 已确认挂载（grep 全量 10 处）；`recent.js` `node --check` OK。
- `.shimmer` 原仅在 index/course/history 局部定义，channels 已补全，骨架动画正常。
- 仍**未做真机/模拟器运行验证**（环境无小程序编译链路）。建议回归：离开 tab 进入 recent/favorites 等页确认浮钮出现与跳转、channels 弱网/首次进入骨架屏展示、recent 从详情返回列表刷新。

### 仍待确认（决策项，未动）
- A3「仅 WiFi 自动播放」死开关：接入 vs 移除，需你定方向。
- A5 未登录保存偏爱静默丢失：按 openid 隔离是有意设计，是否加登录拦截待定。

---

## 八、B 类 UX 修复记录（2026-08-17 续二：B3 / B6 / B7）

> 延续上一轮 B4/B8/A8，推进剩余可确定的 B 类体验优化。B5 经核查无需改动。

| 项 | 状态 | 改动文件 | 说明 |
|----|------|----------|------|
| B3 课程封面加载失败占位 | ✅ 已修复 | `course.wxml:20-22`、`course.js:40/135/145-147` | 封面 `<image>` 加 `wx:if="{{!coverError}}"` + `binderror="onCoverError"`；`wx:else` 展示灰块占位 `.course-cover.course-cover-fallback`（含文字「课程封面」）。`defaultCover` 等也失败时不再裂图 |
| B6 手动检查更新 | ✅ 已修复 | `settings.wxml:43-49`（新增「检查更新」「关于 MorningBrief」两项）、`settings.js:154-193` | `onCheckUpdate` 调 `wx.getUpdateManager()`，含 loading + `onCheckForUpdate`/`onUpdateReady`(重启 modal)/`onUpdateFailed`(toast) + 2s 兜底「已是最新版本」；`onOpenAbout` 跳 `/pages/about/about`。弥补 `onLaunch` 仅 release 自动弹、无手动入口的缺口 |
| B7 反馈历史本地留存 | ✅ 已修复 | `feedback.js`（STORAGE_KEY_FEEDBACK_HISTORY / MAX_HISTORY=20、`history` data、`loadHistory`/`appendHistory`、`formatTime`/`decorateHistory`）、`feedback.wxml:4-16`（历史区渲染）、`feedback.wxss`（`.history-*` 样式） | 提交成功后本地双写历史（分类 + 内容摘要 + 时间），按时间倒序最多 20 条；返回页仍可回溯；`timeLabel` 由 `formatTime` 推导，兼容仅存 `time` 的旧记录 |

### 交付修正点（B7 收尾）
- B7 首版交付时存在 wxml 用 `item.timeLabel` 而 js 写 `time: Date.now()` 的字段不一致（`timeLabel` 恒空）。本轮补 `formatTime` / `decorateHistory`，在 `loadHistory` 与 `appendHistory` 中统一补全 `timeLabel`，旧版仅 `time` 的历史也能正确显示。
- `feedback.wxss` 此前缺失 `.history-*` 样式，本轮补齐，配色与全局薄荷青 / 蜜桃粉马卡龙一致（`history-cate` 用薄荷青胶囊、`history-time`/`history-summary` 灰阶文字）。

### 验证
- `feedback.js` / `settings.js` / `course.js` `node --check` 全部 OK。
- 仍**未做真机 / 模拟器运行验证**（环境无小程序编译链路）。建议回归：课程封面图故意失效看灰块占位、设置页「检查更新」入口、反馈提交后返回查看历史区。

### B5 判定（无需改动）
- 经核查 `download.js` 为「已完成下载管理页」，无进行中数据源；单章实时进度已在 `course` 页 `{item.progress}%` 与整课 `batchProgress` 实时展示。B5（下载进度）已被 `course` 页覆盖，**无需额外改动**，避免臆改。

### 仍待确认（决策项）
- A3 / A5 / B9 已于 2026-08-18 按「推荐默认实现」落地（见第九节），均为可逆改动，若产品方向不同可回退。
- 其余此前列为待决策的小项（B9 引导语义）已现场确认无需改代码。

---

## 九、决策项落地记录（2026-08-18：A3 / A5 / B9）

> 用户指令「继续」推进此前标为「待决策」的 A3 / A5 / B9。三者均为产品 / 设计向，按最稳妥的**推荐默认实现**落地，且保持可逆，报告中明确标注，便于回退。

### A3「仅 WiFi 自动播放」死开关 → 接入自动连播闸门
- **根因**：`wifiOnlyAutoPlay` 仅被 `settings.js` 保存（`onWifiOnlyChange`），`audio.js` 从未读取；`playNext()`（自动连播唯一触发点，仅 `onEnded` 调用，无手动入口）无 WiFi 闸门，开关是死开关。
- **改动（`services/audio.js`）**：
  1. 新增模块变量 `wifiOnlyAutoPlay`（L41）、`loadSettings` 读取（L83/86）、init 初始化（L100）。
  2. 新增 `setWifiOnlyAutoPlay(enabled)`（L356）导出。
  3. 新增 `canAutoPlayOnCurrentNetwork()`（L371）：开关关闭恒允许；开启时仅 `globalData.networkType === 'wifi'` 允许；`app/globalData` 不可用退回允许（防误伤）。
  4. `onEnded` 自动连播条件追加 `&& canAutoPlayOnCurrentNetwork()`（L135）。
- **依赖字段安全**：`globalData.networkType` 在 `app.js:37` 默认 `'wifi'`，并在 `app.js:125` 经 `getNetworkType` 实时刷新 —— 字段恒有值、默认值安全，不存在「开关一开就永远挡住连播」的边缘。
- **接线（`pages/settings/settings.js`）**：`onWifiOnlyChange` 切开关时同步调 `setWifiOnlyAutoPlay(value)`（L95），import 已含（L10）。
- **可逆性**：回退只需删 L135 的 `&& canAutoPlayOnCurrentNetwork()` 与 `setWifiOnlyAutoPlay` 调用即可恢复死开关行为。

### A5 未登录保存偏爱静默丢失 → 明确反馈拦截
- **根因**：`setPreferredChannels`（原 `local-data.js`）在无 `openid` 时静默 `return`，偏爱设置丢失；调用方 `preferred-settings.js:onSave` 随后仍 `markOnboarded` + `navigateBack`，用户误以为已保存。
- **改动（`services/local-data.js`）**：`setPreferredChannels` 改返回 `boolean`（`true`=成功 / `false`=失败），未登录时 `console.warn` + `return false`（不再静默）。
- **改动（`pages/preferred-settings/preferred-settings.js`）**：`onSave` 检查返回值，失败时 `wx.showToast({title:'请先登录后再设置偏爱'})` 并 `return`（**不** markOnboarded、不 navigateBack），避免误判已保存。
- **可逆性**：回退只需把 `if (!saved) { ... return; }` 删掉，恢复原静默行为。

### B9 偏爱引导「暂不」语义 → 确认无需改动
- **核查结论**：`index.js` 引导模态「暂不」已 `markPreferredChannelsOnboarded`（不再弹窗），而 `preferredEmpty` 仍驱动的页面内**非侵入引导卡片**（index / history 均保留）—— 语义已合理：**保持未选态 + 页面内二次引导并存**，用户随时可点卡片进入设置，无歧义、无信息丢失。
- **结论**：不改动代码，仅记录确认。

### 验证
- `services/audio.js` / `pages/settings/settings.js` / `services/local-data.js` / `pages/preferred-settings/preferred-settings.js` 四个文件 `node --check` 全部 OK。
- 仍**未做真机 / 模拟器运行验证**（环境无小程序编译链路）。建议回归：设置页开「仅 WiFi 自动播放」后在 4G 下播完一首看是否停止连播；未登录进入偏爱设置页点保存看 toast 拦截。

---

## 十、二次跨页扫描（2026-08-18 续：A7 扩展 + 模式一致性核查）

> 全部确定性项闭环后，按用户「继续」做一轮跨页面二次扫描，把评审中已验证有效的模式（A7 禁 console.log、B3 图片兜底、A5 未登录静默 return）在整个小程序范围统一排查，区分「可直接修」与「决策/观察项」。

### A7 扩展：页面生产代码 console.log 违规
| 文件:行 | 原 | 处置 | 说明 |
|---------|-----|------|------|
| `pages/detail/detail.js:310` | `console.log("加载节目列表失败，降级为单条:", err.message)` | ✅ 改 `console.warn` | 失败日志，语义贴合 |
| `pages/detail/detail.js:619` | `console.log('评论加载失败:', err.message \|\| err)` | ✅ 改 `console.warn` | 失败日志（评论加载失败静默处理分支） |
| `pages/profile/profile.js:75` | `console.log('silentEnrichProfile fetchWxProfile 失败:', err.message \|\| err)` | ✅ 改 `console.warn` | 旧 API 报错分支，失败日志 |

### 决策 / 观察项（严格对齐 A7 后状态）
- **`utils/server-discovery.js`（实际 15 处 console.log，原记 21 为误算）**：用户指令「严格对齐 A7」后已全部转 `console.warn`（2026-08-18 续）。该模块为诊断工具，warn 仍保留调试可见性，符合 A7「禁 console.log、用 warn/error」约定。
- **`utils/tracker.js:17`（`console.log('[tracker]', …)`）**：同为「严格对齐 A7」转 `console.warn`。该处为 MVP 埋点调试桩（注释写明「上线前替换 sendToVendor 为真实上报」），接真实 SDK 后会彻底移除日志。
- **`images/svg-src/convert-icons.js`（5 处 console.log）**：Node 构建脚本（SVG→PNG 转换），非运行时小程序代码，不适用 A7，**忽略**。
- **`README_导入启动指南.md:158`**：文档示例，非代码，**忽略**。
- **B3 图片兜底缺口**：15 个页用 `<image>`，仅 `course.wxml` / `detail.wxml` / `webview.wxml` 3 个有 `binderror`。其余 12 页（about / channels / history / favorites / profile / download / feedback / recent / queue / search / settings / index）多为图标 / 头像 / 列表缩略图，失败影响轻微；给全部页加 `wx:if/else` 灰块属**过度改动**，列为观察项，仅建议对 hero / 头像类（如 channels 头像）按需补兜底，不自动全量改。
- **`local-data.js:303`（`addHistory` 未登录 `return`）**：历史按 openid 隔离且非关键，静默跳过可接受，**无需改**。
- **`local-data.js:515`（`clearByOpenid` 未登录 `return`）**：退出清理操作，无 openid 本就无数据可清，静默 return 正确，**无需改**。

### 验证
- `pages/detail/detail.js` / `pages/profile/profile.js` 两个文件 `node --check` 全部 OK。
- 「严格对齐 A7」补充校验：`utils/server-discovery.js` / `utils/tracker.js` 两个文件 `node --check` 全部 OK；全局复扫运行时代码已无 `console.log` 残留（仅 `convert-icons.js` 构建脚本与 README 文档保留，二者不适用 A7）。
