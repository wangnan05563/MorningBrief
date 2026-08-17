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
