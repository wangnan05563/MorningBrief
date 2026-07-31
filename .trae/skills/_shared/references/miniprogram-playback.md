# 小程序音频播放规范

> 共享来源：news-code-dev / news-frontend-code-review / news-backend-code-review 维度 81-83 / news-auto-testing 阶段 24-26

## 核心规则

微信小程序使用 `BackgroundAudioManager` 进行音频播放，需遵守以下规范以确保稳定性和兼容性。

### 生命周期管理
- `onLoad` 注册事件监听器（onPlay/onPause/onStop/onTimeUpdate）
- `onUnload` 必须清理所有监听器（offPlay/offPause/offStop/offTimeUpdate）
- 播放器单例模式：全局唯一 `audioManager` 实例

### 节流与防重叠（testing 阶段 25）
- `onTimeUpdate` 回调含时间戳节流（`lastTimeUpdate` 模式）
- 异步上报函数含 `inProgress` 防重叠标志 + `try/finally` 清标志
- seek 操作使用 `pendingSeek` 标志位模式（推荐）
- 高频 setter（playbackRate/volume）含 `lastApplied` 缓存判断

### iOS/Android 双端兼容（testing 阶段 26）
- `setPlaybackRate` 需 pause+play+seek 强制重新缓冲（iOS 必需）
- `resumePlay` 函数导出，跳转到详情页后自动恢复播放
- 列表页禁止内嵌播放卡片，必须 `wx.navigateTo` 跳转
- 频道切换时清空 script/segments/comments/bgCoverUrl

### URL 编码安全性（testing 阶段 24）
- 资源 URL 含中文必须 `encodeURI()` 编码
- 禁止 `encodeURIComponent()` 编码完整 URL（破坏结构）
- 后端返回的 audio_url/cover_url 需在生成时已编码

## 后端维度索引

- backend-review 维度 81-83：音频 URL 生成 + 小程序 API 契约

## 前端维度索引

- frontend-review 维度 81-83：小程序音频播放 + 生命周期配对

## 测试阶段索引

- testing 阶段 24：小程序 URL 编码安全性预检
- testing 阶段 25：高频回调节流与防重叠验证
- testing 阶段 26：iOS/Android 双端播放兼容性验证
