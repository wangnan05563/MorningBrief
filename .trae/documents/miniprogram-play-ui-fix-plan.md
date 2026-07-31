# 小程序播放与 UI 迭代修复计划（8 项 + 测试）

## Summary

针对微信小程序「今日要闻」8 项缺陷进行闭环修复：tab 胶囊顺序调整、节目来源超链接复制/跳转、播放队列自动连播、播放计数器（>30s 即 +1）、播放按钮状态同步、累计收听时长统计、微信登录资料返显。所有修复完成后使用 `news-auto-testing` 技能进行全面功能/性能/API 测试，确保通过。

## Current State Analysis（根因定位）

### 任务1：tab/胶囊顺序
- [history.js:95-107](file:///d:/code/otherProjects/20_News/miniprogram/pages/history/history.js#L95-L107) `loadChannels`：频道胶囊顺序为 `[全部, ...频道列表, 我的偏爱]`，「我的偏爱」在末尾。
- [index.js:73-79](file:///d:/code/otherProjects/20_News/miniprogram/pages/index/index.js#L73-L79) `data` 注释显示 index 页同样有「我的偏爱」胶囊在末尾（`loadChannels` 同款逻辑）。
- **根因**：「我的偏爱」胶囊在末尾，用户期望前置到「全部」之前。
- **用户澄清**：「我的偏爱放到我的页面和历史页面中'全部'的前面」。结合代码，只有 index 首页和 history 历史页有「全部」频道胶囊，故理解为这两个页面的胶囊前置。（profile 页无频道胶囊，不涉及）

### 任务2：复制失败修复
- [clipboard.js:15-23](file:///d:/code/otherProjects/20_News/miniprogram/utils/clipboard.js#L15-L23) `copyText` 用 `wx.setClipboardData`，fail 时 resolve(false)。
- [webview.js:82-90](file:///d:/code/otherProjects/20_News/miniprogram/pages/webview/webview.js#L82-L90) `onCopy` 复制失败时 toast「复制失败，请长按上方链接复制」——这是用户看到的"复制失败"错误来源。
- [app.js:161-197](file:///d:/code/otherProjects/20_News/miniprogram/app.js#L161-L197) `checkPrivacy` 异步执行，`wx.setClipboardData` 属于隐私接口，若用户未同意隐私协议会 fail。
- **根因**：隐私授权异步未完成 / 未同意时，`setClipboardData` 直接 fail；当前无重试与授权引导。

### 任务3：超链接跳转提示（用户选择：弹 ActionSheet 双选项）
- [detail.js:648-653](file:///d:/code/otherProjects/20_News/miniprogram/pages/detail/detail.js#L648-L653) `onTapSource` 当前直接调 `copySourceUrl`（已放弃 webview 方案）。
- [webview.js:56-76](file:///d:/code/otherProjects/20_News/miniprogram/pages/webview/webview.js#L56-L76) `onError`/`onWebviewLoad` 已实现，`binderror` + 5s 超时兜底能触发 fallback。
- **方案**：改为 ActionSheet [复制链接 / 在小程序内打开]；选"在小程序内打开"跳 webview（不带 fallback=1），域名不在白名单时 webview fallback 显示「无法在小程序内打开，请复制到浏览器打开」+ 复制按钮。

### 任务4：播放队列自动播放
- [audio.js:85-105](file:///d:/code/otherProjects/20_News/miniprogram/services/audio.js#L85-L105) `onEnded` 已实现 `autoPlayNext && !sleepTickTimer && !sleepTailTimer` 时调 `playNext()`。
- [audio.js:565-581](file:///d:/code/otherProjects/20_News/miniprogram/services/audio.js#L565-L581) `playNext` 队列末端 toast「已是最后一首」，否则 `queueIndex+1` 调 `playEpisode`。
- **根因**：`playEpisode` 时**不会自动 `setQueue`**。从分享链接/收藏页直接进入详情页时队列可能为空，`playNext` 直接返回「已是最后一首」，自动连播失效。
- 异常处理：`onError`（[audio.js:137-148](file:///d:/code/otherProjects/20_News/miniprogram/services/audio.js#L137-L148)）已处理网络中断/音频损坏（重置状态+提示）。

### 任务5：播放计数器（用户选择：播放超 30 秒即 +1）
- [play_service.py:100-110](file:///d:/code/otherProjects/20_News/backend/app/services/play_service.py#L100-L110) 仅 `completed=True` 时插入 PlayLog。
- play_count 基于 PlayLog 表 COUNT 聚合（注释提到 content_service.py）。
- **根因**：未完播不计入播放次数；用户听了几秒就退出，播放次数始终为 0。
- **方案**：改为 position 首次 ≥30 秒时插入 PlayLog（每用户每节目去重一次），完播不再单独插 PlayLog（避免重复计数）。

### 任务6：播放按钮状态同步
- [detail.js:248-299](file:///d:/code/otherProjects/20_News/miniprogram/pages/detail/detail.js#L248-L299) `bindPlayerEvents` 注册 `player.onPlay/onPause/onTimeUpdate/onEnded`。
- [detail.js:102-110](file:///d:/code/otherProjects/20_News/miniprogram/pages/detail/detail.js#L102-L110) `onPlaybackChange` 订阅仅处理节目切换，未处理同节目播放/暂停状态。
- [floating-player.js:23-27](file:///d:/code/otherProjects/20_News/miniprogram/components/floating-player/floating-player.js#L23-L27) 浮动按钮通过 `onPlaybackChange` 同步 isPlaying。
- **根因**：detail 页 `_onPause` 检查 `isCurrentEpisode()`（[detail.js:266-269](file:///d:/code/otherProjects/20_News/miniprogram/pages/detail/detail.js#L266-L269)），当 currentEpisode 已切换但页面 episode 未同步时，onPause 不更新 isPlaying，导致按钮卡在"播放中"。两套事件源（player.onPlay/onPause 与 onPlaybackChange）时序不一致。
- **方案**：统一用 `onPlaybackChange` 订阅处理播放/暂停状态同步，弱化 player.onPlay/onPause 的状态职责（保留兜底）。

### 任务7：累计收听时间
- [users.py:56-63](file:///d:/code/otherProjects/20_News/backend/app/routers/api/users.py#L56-L63) `/stats` 用 `sum(PlayProgress.position)` 计算累计时长。
- PlayProgress 是 upsert（每用户每节目一条），position 是**最后播放位置**，重新听会覆盖而非累加；未完播 position 可能为 0。
- [user.py:24-25](file:///d:/code/otherProjects/20_News/backend/app/models/user.py#L24-L25) User 模型已有 `total_listen_duration`（default=0）和 `total_listen_count` 字段，但 `/stats` 未使用。
- **根因**：`sum(position)` 语义错误，非累计收听时长。
- **方案**：前端上报"本次收听时长增量"，后端累加到 `User.total_listen_duration`；`/stats` 改用 User 字段返回。

### 任务8：微信登录资料返显
- [auth.js:53-89](file:///d:/code/otherProjects/20_News/miniprogram/services/auth.js#L53-L89) `login` → `setToken(data.token, data.user)`，新用户 `data.user = {openid, nickname:null, avatar:null}`。
- [profile.js:283-355](file:///d:/code/otherProjects/20_News/miniprogram/pages/profile/profile.js#L283-L355) `onLogin`：login → fetchWxProfile（旧版）/ showEditProfile（新版）→ onConfirmEditProfile。
- [profile.js:181-231](file:///d:/code/otherProjects/20_News/miniprogram/pages/profile/profile.js#L181-L231) `onConfirmEditProfile`：uploadAvatar + updateUserProfile + setData。
- [profile.wxml:18,21](file:///d:/code/otherProjects/20_News/miniprogram/pages/profile/profile.wxml#L18) 绑定 `userInfo.avatar_url || userInfo.avatar || userInfo.avatarUrl`、`userInfo.nickname || userInfo.nickName`。
- **可能根因**（需运行时确认）：
  1. `uploadAvatar` 失败（网络/接口路径）导致 avatarUrl=null，仅保存昵称；
  2. `chooseAvatar` 隐私授权未同意导致 onChooseAvatar 不回调；
  3. `onLogin` 新版路径 `setData({userInfo: enriched})` 时 enriched 仅含 openid，用户未点保存就退出弹窗，资料未写回；
  4. 后端 `update_profile` 未返回最新 user，前端用本地构造值，若 uploadAvatar 失败则 avatar 缺失。
- **方案**：增加全链路日志 + 错误分支提示；确保 onConfirmEditProfile 成功后刷新 loadStats 与 globalData；uploadAvatar 失败时保留临时路径并明确提示。

## Proposed Changes

### 任务1：频道胶囊「我的偏爱」前置
**文件**：
- [miniprogram/pages/history/history.js](file:///d:/code/otherProjects/20_News/miniprogram/pages/history/history.js) `loadChannels`（约 95-107 行）
- [miniprogram/pages/index/index.js](file:///d:/code/otherProjects/20_News/miniprogram/pages/index/index.js) `loadChannels`（需定位，与 history 同款）

**修改**：将频道胶囊数组从 `[全部, ...频道列表, 我的偏爱]` 改为 `[我的偏爱, 全部, ...频道列表]`。
- 为什么：用户期望「我的偏爱」最显眼，前置到「全部」之前。
- 如何：`loadChannels` 中调整数组拼接顺序，`{id:'preferred', name:'我的偏爱'}` 放首项。
- **默认选中**：保持默认选中「全部」（`currentChannelId=null`），避免未设置偏爱频道时启动即显示空引导。用户原描述"启动优先显示"已通过胶囊前置满足视觉优先，不强改默认选中。

### 任务2：复制失败修复
**文件**：
- [miniprogram/utils/clipboard.js](file:///d:/code/otherProjects/20_News/miniprogram/utils/clipboard.js) `copyText`
- [miniprogram/app.js](file:///d:/code/otherProjects/20_News/miniprogram/app.js) `checkPrivacy`

**修改**：
1. `copyText` 调用 `wx.setClipboardData` 前，检查 `getApp().globalData.privacyAuthorized`，未授权时先调 `wx.requirePrivacyAuthorize`（或引导用户同意隐私协议）后再复制。
2. 复制失败时增加重试一次（间隔 500ms），仍失败再走 webview fallback。
3. 复制成功时确保有明确反馈（`copySourceUrl` 已有 modal，保留）。
- 为什么：隐私授权异步未完成是 setClipboardData fail 的主因；重试覆盖瞬态失败。
- 如何：在 `copyText` 内增加 privacyAuthorized 检查 + requirePrivacyAuthorize 回调链 + 一次重试。

### 任务3：超链接 ActionSheet 双选项
**文件**：
- [miniprogram/pages/detail/detail.js](file:///d:/code/otherProjects/20_News/miniprogram/pages/detail/detail.js) `onTapSource`（648-653 行）
- [miniprogram/pages/webview/webview.js](file:///d:/code/otherProjects/20_News/miniprogram/pages/webview/webview.js) + `webview.wxml`（优化 fallback 提示文案）

**修改**：
1. `onTapSource` 改为 `wx.showActionSheet({itemList: ['复制链接', '在小程序内打开']})`：
   - 选「复制链接」→ 调 `copySourceUrl(url)`（现有逻辑）。
   - 选「在小程序内打开」→ `wx.navigateTo({url: '/pages/webview/webview?url=' + encodeURIComponent(url)})`（不带 fallback=1，让 web-view 尝试加载）。
2. webview fallback 页提示文案改为「无法在小程序内打开此链接，请复制到浏览器打开」+「复制链接」按钮（webview.js onCopy 已有，wxml 调整文案）。
3. webview.js 已有 `onError` + 5s 超时兜底，确保域名不在白名单时一定显示 fallback。
- 为什么：用户期望双选项交互；webview fallback 已有完整机制，仅需 ActionSheet 入口 + 文案优化。

### 任务4：播放队列自动播放保障
**文件**：
- [miniprogram/services/audio.js](file:///d:/code/otherProjects/20_News/miniprogram/services/audio.js) `playEpisode`（335-427 行）

**修改**：
1. `playEpisode` 开头：若 `playQueue.length === 0`（队列未设置），自动拉取当日列表作为队列（调用 `fetchTodayEpisode`，成功后 `setQueue([episode], 0)` 或 `setQueue(episodes, indexOfCurrent)`）。
2. 拉取失败时静默降级（单条播放，不阻断）。
3. `onEnded`→`playNext` 队列末端时，保留现有「已是最后一首」提示。
- 为什么：从分享链接/收藏页直接进入详情页时队列空，自动连播失效；自动补全队列保障连播连续性。
- 如何：在 `playEpisode` 设置 `currentEpisode` 后，异步 `fetchTodayEpisode` 补全队列（不阻塞播放）。
- 异常处理：网络中断（onError 已处理）、音频损坏（onError 已处理）、队列拉取失败（降级单条播放）。

### 任务5：播放计数器（>30s 即 +1）
**文件**：
- [backend/app/services/play_service.py](file:///d:/code/otherProjects/20_News/backend/app/services/play_service.py) `report_progress`（31-124 行）
- [backend/app/models/play_log.py](file:///d:/code/otherProjects/20_News/backend/app/models/play_log.py)（PlayLog 语义调整，无需改表结构）

**修改**：
1. `report_progress` 中，当 `position >= 30` 且该用户该节目在 PlayLog 表中不存在记录时，插入一条 PlayLog（`completed` 字段记录当前是否完播，`duration` 记录当前 position）。
2. 完播时（`completed=True`）若已存在 PlayLog 记录，则更新该记录的 `completed=1` 和 `position`；若不存在则插入。
3. 去重逻辑：`select(PlayLog).where(user_id=?, episode_id=?)`，存在则 update，不存在则 insert。
4. play_count 聚合（content_service.py）保持基于 PlayLog COUNT 不变。
- 为什么：用户期望"播放超 30 秒即 +1"，避免误触点击也算播放量；去重保证每用户每节目只计一次。
- 如何：在 `report_progress` 的 upsert PlayProgress 之后，增加 PlayLog 的 upsert 逻辑（position>=30 阈值）。
- 配置：30 秒阈值通过 `project-config.json` 管理（可配置）。

### 任务6：播放按钮状态同步
**文件**：
- [miniprogram/pages/detail/detail.js](file:///d:/code/otherProjects/20_News/miniprogram/pages/detail/detail.js) `bindPlayerEvents` + `onPlaybackChange` 订阅

**修改**：
1. `onPlaybackChange` 订阅回调（102-110 行）扩展：除了处理节目切换，也同步 `isPlaying` 状态（`evt.paused` 字段）。
2. `_onPause` 移除 `isCurrentEpisode()` 严格检查，改为：若 currentEpisode 为空或与页面 episode 不一致，仍允许设置 `isPlaying=false`（避免按钮卡在播放中）。
3. `onTogglePlay` 中 `player.paused ? player.play() : player.pause()` 保留，但增加 `setData({isPlaying: !player.paused})` 即时反馈。
- 为什么：两套事件源时序不一致导致状态不同步；统一以 `onPlaybackChange` 为权威状态源。
- 如何：扩展 onPlaybackChange 订阅处理 `evt.paused`，弱化 player.onPause 的状态职责。

### 任务7：累计收听时长统计
**文件**：
- [backend/app/routers/api/users.py](file:///d:/code/otherProjects/20_News/backend/app/routers/api/users.py) `get_user_stats`（46-89 行）
- [backend/app/services/play_service.py](file:///d:/code/otherProjects/20_News/backend/app/services/play_service.py) `report_progress`（增加收听时长累加）
- [backend/app/routers/api/playlogs.py](file:///d:/code/otherProjects/20_News/backend/app/routers/api/playlogs.py) `ProgressRequest`（增加 `listened_seconds` 字段）
- [miniprogram/services/audio.js](file:///d:/code/otherProjects/20_News/miniprogram/services/audio.js)（上报收听时长增量）
- [miniprogram/services/local-data.js](file:///d:/code/otherProjects/20_News/miniprogram/services/local-data.js) `saveProgress`（透传 listened_seconds）

**修改**：
1. 前端 `audio.js`：记录上次上报的 position（`lastReportedPosition`），`startProgressReport` 每次上报时计算增量 `delta = currentPos - lastReportedPosition`（delta>0 时透传），`onPause/onEnded` 时也计算增量上报。
2. `local-data.saveProgress` 增加 `listened_seconds` 参数，透传给 `reportPlayProgress`。
3. `api.js reportPlayProgress` data 增加 `listened_seconds` 字段。
4. 后端 `ProgressRequest` 增加 `listened_seconds: int = Field(0, ge=0)`。
5. 后端 `play_service.report_progress` 增加 `listened_seconds` 参数，累加到 `User.total_listen_duration`（`UPDATE user SET total_listen_duration = total_listen_duration + ? WHERE id = ?`）。
6. 后端 `/stats` 改为返回 `User.total_listen_duration` 和 `User.total_listen_count`（不再用 sum(PlayProgress.position)）。
- 为什么：sum(position) 语义错误（最后位置之和，非累计）；改用 User 字段累加实际收听增量，语义清晰。
- 如何：前端计算增量 → 后端累加到 User 字段 → /stats 返回 User 字段。
- 异常处理：增量计算为负（用户 seek 后退）时丢弃该次增量，避免负累加。

### 任务8：微信登录资料返显
**文件**：
- [miniprogram/pages/profile/profile.js](file:///d:/code/otherProjects/20_News/miniprogram/pages/profile/profile.js) `onLogin` + `onConfirmEditProfile` + `onChooseAvatar`

**修改**：
1. `onLogin` 新版路径：`showEditProfile=true` 后，增加引导 toast「请选择微信头像和昵称」（已有，确认保留）。
2. `onChooseAvatar`：增加隐私授权检查，未授权时提示用户同意隐私协议。
3. `onConfirmEditProfile`：
   - `uploadAvatar` 失败时，保留临时路径 `editAvatar` 到 `globalData.userInfo.avatar`（本会话可见），并明确 toast「头像上传失败，已临时显示，下次登录需重新选择」。
   - `updateUserProfile` 成功后，重新 `loadStats()` 并 `setData({userInfo: enriched})` 确保 UI 刷新。
   - 增加全链路 console.log 便于排查（chooseAvatar 回调、uploadAvatar 结果、updateUserProfile 结果）。
4. `onLogin` 旧版路径（fetchWxProfile 成功）：确认 `setData({userInfo: enriched})` 后 `loadStats()` 已调用。
- 为什么：当前流程完整但缺错误分支提示与日志，失败时用户无感知；增加日志与提示定位具体失效环节。
- 如何：增加隐私授权检查 + 错误分支提示 + 全链路日志 + 成功后强制刷新。

## Assumptions & Decisions

1. **任务1「我的页面」**：理解为 index 首页和 history 历史页（仅有「全部」胶囊的两个页面）。若用户实际指 profile 页，需额外说明（profile 无频道胶囊，不适用）。
2. **任务1 默认选中**：胶囊前置但默认仍选「全部」，避免未设置偏爱频道时启动即空。若用户要求默认选「我的偏爱」，需再确认。
3. **任务5 阈值**：30 秒通过 `project-config.json#play_count_threshold` 配置，便于调整。
4. **任务7 增量计算**：用户 seek 后退时 delta 为负，丢弃该次增量；用户切歌时 lastReportedPosition 重置。
5. **任务8 根因**：代码流程完整，可能根因为隐私授权/网络/接口失败，增加日志后运行时定位。若仍无法定位，使用 `TRAE-debugger` 技能启动运行时调试。
6. **测试**：使用 `news-auto-testing` 技能进行前端自动化测试（Playwright MCP + Chrome DevTools MCP）。小程序部分需真机/开发者工具验证，后端 API 部分用 Playwright/pytest 验证。

## Verification Steps

### 阶段 1：静态检查
- 后端：`python -m py_compile` 所有修改的 .py 文件（play_service.py / users.py / playlogs.py）
- 前端：`node --check` 所有修改的 .js 文件（audio.js / detail.js / profile.js / clipboard.js / history.js / index.js / local-data.js / webview.js）
- 小程序：在微信开发者工具编译无报错

### 阶段 2：运行时验证
- 后端服务重启 + `GET /openapi.json` 确认端点注册
- `GET /api/v1/health` 健康检查
- 后端 pytest 单元测试（play_service / user_service）通过

### 阶段 3：功能验证（news-auto-testing 技能）
调用 `news-auto-testing` 技能执行：
1. **任务1**：index/history 页频道胶囊顺序验证（「我的偏爱」在「全部」前）
2. **任务2**：节目来源复制链接 → 成功 modal 提示
3. **任务3**：节目来源 ActionSheet 双选项 → 复制链接 / 在小程序内打开（fallback 提示）
4. **任务4**：播放完一首 → 自动播放下一首（队列空时自动补全）
5. **任务5**：播放超 30 秒 → play_count +1（API 验证 PlayLog 落库）
6. **任务6**：播放/暂停按钮状态与实际播放状态同步（浮动按钮 + 详情页）
7. **任务7**：播放一段时间 → /users/stats 返回累计收听时长 > 0
8. **任务8**：点击登录 → 选择微信头像昵称 → 头像昵称正确返显

### 阶段 4：回归测试
- SonarQube 二次扫描确保无新增问题（规范 75）
- 全部测试通过后交付

## 执行顺序

1. 任务1（胶囊前置，最简单，独立）
2. 任务2 + 任务3（超链接相关，耦合）
3. 任务5 + 任务7（后端播放计数 + 收听时长，耦合，均改 play_service）
4. 任务4（播放队列，前端 audio.js）
5. 任务6（播放按钮状态，前端 detail.js）
6. 任务8（微信登录，前端 profile.js）
7. news-auto-testing 全面测试
