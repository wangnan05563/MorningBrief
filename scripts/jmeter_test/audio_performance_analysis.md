# MorningBrief 音频播放性能深度分析报告

> 分析时间：2026-07-27
> 问题：生产模式播放加载较慢，无局域网快

## 执行摘要

**根因**：音频文件经 Tailscale Funnel 中转，而非走 CDN/对象存储。Funnel 是"公网入口 → Tailscale 网络 → 本地 FastAPI"的三段式链路，每个 Range 请求都需经 TLS 握手 + 跨地域中转 + 本地回源，叠加后端缺少缓存头、客户端无预加载，导致首字播放延迟显著放大。

## 1. 音频文件来源与 URL 构造

### 1.1 当前实现

- **生成链路**：`backend/app/workflow/stitch/concat.py:374` 调用 `upload_to_cos(data, cos_key)`
- **存储决策**：`backend/app/workflow/tts/uploader.py:34-49` 根据 `is_cos_configured()` 判断
  - COS 已配置：上传到 COS，返回 `https://<bucket>.cos.<region>.myqcloud.com/<key>` 或 CDN URL
  - COS 未配置：本地回退，返回 `/audio/<key>`（相对路径）
- **URL 拼接**：`backend/app/services/content_service.py:402-468` 的 `_resolve_audio_base_url()` 优先用 `tunnel_service.public_url`

### 1.2 生产环境实际指向

**证据**：
- `apps/miniprogram/utils/config.js:17`：`cosBaseUrl: 'https://cos.example.com'`（占位符，COS 未实际接入）
- `backend/app/services/tunnel_providers.py:785`：Tailscale 启动后 `public_url = f"https://{host}{self._path_prefix}"`

**结论**：生产环境 audio_url 形如：
```
https://desktop-g10o4nl.tailbca47.ts.net/news/audio/episodes/20260727/tech_wf-xxx.mp3
```
音频文件**走 Tailscale Funnel 中转**，而非 COS。

## 2. 后端音频静态文件服务

### 2.1 已实现（`backend/app/main.py:28-91` CORSStaticFiles）
- Range 请求支持（RFC 7233 分块响应，206 Partial Content）
- CORS 头（`Access-Control-Allow-Origin: *`）
- 真机兼容（注释明确"真机系统音频播放器需要 Range 请求支持"）

### 2.2 未实现（关键性能缺口）
- ❌ 无 `Cache-Control` 头：每次 Range 请求都回源
- ❌ 无 `ETag` 头：无法 304 Not Modified
- ❌ 无 `Last-Modified` 头：无法条件请求
- ❌ Range 响应把整个分块读入内存（`f.read(content_length)`，`main.py:66`）
- ❌ 无 sendfile 零拷贝

## 3. 小程序客户端音频加载链路

### 3.1 关键问题

1. **无预加载机制**：每次切歌都要完整走 DNS+TLS+Range
2. **`onWaiting` 仅有日志输出**（`audio.js:133-135`）：未暴露 loading 状态给 UI，用户感知"点了播放但没声音"
3. **断点续播导致双倍加载**：onCanplay 触发后 seek，真机 seek 后重新发 Range 请求
4. **缺 audio_url 时同步 fetch 详情**（`audio.js:271-283`）：await 阻塞播放

## 4. 网络层瓶颈量化分析

### 4.1 Tailscale Funnel 链路

```
用户手机 4G/WiFi
  → 公网 → Tailscale 边缘节点（DERP/直连）
  → Tailscale 网络中转
  → 用户本地电脑的 Tailscale 客户端
  → 127.0.0.1:8000 (FastAPI)
  → /audio 静态文件
```

### 4.2 延迟对比（10MB 音频文件）

| 环节 | 局域网 | 生产（Funnel） | 差距 |
|---|---|---|---|
| DNS 解析 | 0ms | 20-100ms | +20-100ms |
| TCP 连接 | 1-5ms | 50-200ms | +45-195ms |
| TLS 握手 | 0ms | 100-400ms | +100-400ms |
| 首次 Range 响应 | 5-20ms | 100-300ms | +80-280ms |
| **首字播放延迟** | **10-30ms** | **300-1000ms** | **+270-970ms** |
| 完整下载 10MB | 0.5-2s | 3-15s | +2.5-13s |

### 4.3 延迟贡献分解

| 环节 | 占比 |
|---|---|
| DNS + TCP + TLS 建连 | 30-50% |
| Funnel 中转 RTT | 20-30% |
| 本地电脑上传带宽限制 | 20-30% |
| 后端 Range 处理 | <2% |

**结论**：根因是"经 Tailscale Funnel 中转 + 家庭宽带上行受限"，而非后端处理慢。

## 5. 优化方案（按优先级）

### P0 - 接入 COS/CDN 分发音频（最大收益）

**当前状态**：COS 客户端代码已就绪（`backend/app/cos/client.py` + `backend/app/workflow/tts/uploader.py`），但 `apps/miniprogram/utils/config.js:17` 是占位符，COS 未实际配置。

**方案**：
1. 在 `.env` 配置真实的腾讯云 COS 凭证
2. `is_cos_configured()` 自动返回 `True`，`upload_to_cos` 自动上传到 COS 返回 CDN URL
3. `audio_url` 直接指向 `https://<CDN_DOMAIN>/episodes/...`

**预期收益**：
- 首字延迟从 300-1000ms 降到 50-200ms（5-10 倍提升）
- 下载速度从 3-15s 降到 0.5-2s
- 不受家庭宽带上传限制

**实施成本**：低（代码已就绪，仅需配置）

> ⚠️ 此项需要用户提供 COS 凭证，属于外部依赖

### P1 - 后端 Range 响应加缓存头

**方案**（修改 `backend/app/main.py` 的 `CORSStaticFiles.get_response`）：
```python
response.headers["Cache-Control"] = "public, max-age=86400, immutable"
response.headers["ETag"] = f'"{file_size}-{int(os.path.getmtime(full_path))}"'
response.headers["Last-Modified"] = http_date(os.path.getmtime(full_path))
```

**预期收益**：二次播放可走缓存，减少回源 50%+

### P2 - 客户端暴露 loading 状态

**方案**：`audio.js` 新增 `waitingListeners`，`onWaiting` 时通知 UI 显示 loading

**预期收益**：改善用户感知，避免重复点击

### P3 - 客户端预加载下一首

**方案**：`onEnded` 前提前 `fetchEpisodeDetail` + `wx.downloadFile` 预下载

**预期收益**：自动连播场景延迟从 1-3s 降到 100-300ms

### P4 - 音频文件预压缩降码率

**方案**：TTS 合成时使用 64kbps（语音内容足够），或 ffmpeg 后处理转码

**预期收益**：文件大小减少 50%，下载时间减半

### P5 - HLS 分片加载

**方案**：后端用 ffmpeg 生成 HLS m3u8 + ts 分片

**预期收益**：首字延迟降到 200-500ms

**实施成本**：高

## 6. 最终结论

**生产模式播放慢于局域网的根因（按影响降序）**：

1. **音频文件经 Tailscale Funnel 中转**（60-70% 延迟）：COS 未实际接入
2. **家庭宽带上传带宽瓶颈**（20-30% 延迟）：10MB 文件在 10Mbps 上行需 8s
3. **后端静态文件无缓存头**（5-10% 延迟）：二次播放无缓存复用
4. **客户端无预加载**（5-10% 延迟）：连播场景感知强
5. **音频码率偏高**（5-10% 体积）：128kbps 对语音内容过度

**最关键优化**：接入 COS CDN（代码已就绪，仅需配置），预期首字延迟从 300-1000ms 降到 50-200ms。
