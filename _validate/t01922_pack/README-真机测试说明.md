# T01922 真机起播兼容实测 · 物料包与记录表

物料由 `_validate/t01922_materials.py` 离线生成（源：本项目已发布成品 `ep100.mp3` 的第 30–90s 切片，
**全程不触发 TTS/LLM 付费链路**）。码流事实见 `_validate/t01922_pack_facts.json`。

## 一、物料清单与预期值（码流级取证，已实测）

| 文件 | 请求参数 | 帧头实测（关键） | 体积 | 容器时长 |
|---|---|---|---|---|
| `A0_published_copy.mp3` | 线上成品原码流逐帧拷贝（`-c copy`，零重编） | **MPEG-1 Layer III** / 44100 / mono / 128kbps | 960,931 | 60.029s |
| `A_baseline_128k_44100.mp3` | libmp3lame 128k@44100 | MPEG-1 III / 44100 / mono | 960,931 | 60.000s |
| `B_standard_64k_32000.mp3` | **当前默认档** 64k@32000 | **MPEG-1 Layer III** / 32000 / mono | 480,716 | 60.000s |
| `C_quality_96k_44100.mp3` | 96k@44100 | MPEG-1 III / 44100 / mono | 720,710 | 60.000s |
| `D_lean_48k_32000.mp3` | 48k@32000 | MPEG-1 III / 32000 / mono | 360,548 | 60.000s |
| `E_lsf_64k_24000.mp3` | 64k@24000 | **MPEG-2 Layer III（LSF，实测确认）** / 24000 / mono，带 Xing/Info 头 | 480,620 | 60.000s |
| `F_aac_64k_32000.m4a` | AAC-LC 64k@32000 | AAC **LC** / 32000 / mono / faststart | 489,073 | 60.000s |
| `G_hls_aac_64k_32000/` | 生产 `build_hls_cmd` 同参 | `#EXT-X-VERSION:3`、`TARGETDURATION:10`、7 个 mpegts 分片、分片内 AAC-LC@32000 | — | 60.032s |

三条已经确定的事实（不需要真机就能定）：

1. **默认档 standard（64k@32000）仍是 MPEG-1 Layer III**，与线上现状 128k@44.1k 同一格式族，
   只是采样率索引不同（32000 是 MPEG-1 合法值）→ 它**不引入新的解码器要求**，
   真机风险与已发布成品同级。
2. **24kHz 候选确实是 MPEG-2 Layer III（LSF）**（帧头 version bits=2、sample_rate_index=1 实测），
   并且 libmp3lame 只在 LSF 文件里写了 Xing/Info 头（MPEG-1 四档都没有）——
   这是唯一需要真机背书的格式，T01871 把它挡在默认链路外是对的。
3. **传输侧条件成立**：自有 COS 成品地址实测 `Accept-Ranges: bytes` + `Range` 请求返回 **206**
   （`Content-Range: bytes 0-1/9552918`，`Content-Type: audio/mpeg`）→ 进度条拖动/断点续播所需的
   Range 语义在生产侧可用，不是本单的阻塞项。（取证脚本 `_validate/t01922_cos_range.txt`）

## 二、还没被回答的（必须真机）

| 端 | 状态 | 为什么本环境做不了 |
|---|---|---|
| 微信小程序（Android 真机内置播放器） | **未覆盖** | 无 adb（`adb: command not found`，SDK 未装）、`Get-PnpDevice` 未见 Android/MTP 设备 |
| 微信小程序（iOS 真机） | **未覆盖** | 无 iOS 设备通道（Windows 机器） |
| iOS Safari / AVPlayer | **未覆盖** | 同上 |
| Android 系统播放器 / 第三方 App | **未覆盖** | 同上 |
| 微信开发者工具（小程序运行时，非真机） | **未覆盖** | `AppData/Local/微信开发者工具` 只剩 `User Data`，安装体与 `cli.bat` 均不存在 |
| Chromium 桌面内核（**旁证，不算任务指定端**） | 已实测 8/8 | `_validate/t01922_browser_check.mjs`，结果见下 |

Chromium（系统 Chrome 155，headless）实测：8 个物料（含 LSF mp3、m4a、m3u8）**全部起播成功**，
`duration` 报 60s（LSF/HLS 60.03s）、seek 到 30s 后时间继续推进（1,035–1,469ms 增量）、`MediaError.code` 全为 null。
> 口径提醒：Chromium 解码器 ≠ 微信 Android 的 NuPlayer/ExoPlayer，≠ iOS 的 AVPlayer。
> 这一组只能证明「码流规范、无结构损坏」，**不能替代真机结论**。

## 三、真机记录表（逐端 × 逐档填写）

播放方式：把本目录推到设备后用系统播放器播放；小程序侧走 `services/audio.js` 的
`wx.getBackgroundAudioManager()`（生产真实路径，含 `hls`→`mp3` onError fallback）。
建议起播 URL 用本机局域网静态服务或直接把文件传到测试用 COS 前缀。

| # | 文件 | 端 / 机型 / 系统 / 微信版本 | 能否起播 | 首帧耗时(s) | 是否有声 | `duration` 显示 | seek 30s 后是否继续 | 异常提示文案 | 判定(通过/不通过) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | A0_published_copy.mp3 | | | | | 60.03 | | | | |
| 2 | A_baseline_128k_44100.mp3 | | | | | 60.00 | | | | |
| 3 | B_standard_64k_32000.mp3 | | | | | 60.00 | | | | |
| 4 | C_quality_96k_44100.mp3 | | | | | 60.00 | | | | |
| 5 | D_lean_48k_32000.mp3 | | | | | 60.00 | | | | |
| 6 | E_lsf_64k_24000.mp3 | | | | | 60.00 | | | | |
| 7 | F_aac_64k_32000.m4a | | | | | 60.00 | | | | |
| 8 | G_hls_aac_64k_32000/playlist.m3u8 | | | | | 60.03 | | | | |

判定口径（四项全过才算该档通过）：
1. **起播**：点播放后 3s 内进入播放态，无 `音频加载失败，请稍后重试`（`services/audio.js:226` 的 toast）；
2. **有声**：非静音（LSF 档最容易表现为「进度条在走但没声音」）；
3. **时长上报**：播放器/浮条显示的总时长 ≈ 60s（±1s），与 `episode.duration` 口径一致
   ⚠ 注意本单另发现的 DB 时长偏差见「四」，别把它误算成解码问题；
4. **seek/进度**：拖到 30s 能继续播且进度条不倒退（`Accept-Ranges` 已在生产侧成立）。

设备覆盖最低要求：Android ≥ 2 台（含 1 台低端/老系统）、iOS ≥ 2 台，微信版本记录到小版本；
`E_lsf_64k_24000.mp3` 与 `G_hls_*` 是重点（前者是唯一非 MPEG-1，后者是生产在用的协议）。

### 三之二、同批顺带执行：duration 校正后的收听百分比复核（T01925 后续，见第四节派生单 T02029）

「四」里发现的 DB 时长偏差已由 T01925 修复并重算（ep100 `586→597`、ep58 `86→482`）。
`apps/miniprogram/services/audio.js` 用 `audioManager.duration`（真实文件时长）算 `finalPos`/已听秒数，
后端下发的是 DB 值，所以这一项只能真机看：

| # | 节目 | 端 / 机型 | 播到结尾进度条能否到 100% | 「听完」提示出现位置(距真实结尾秒数) | 已听秒数是否 > 下发 duration | 判定 |
|---|---|---|---|---|---|---|
| 1 | ep100（597s，原 DB 586） | | | | | |
| 2 | ep58（482s，原 DB 86，结尾是补足的 BGM 尾奏） | | | | | |

判定口径：进度条能走完；「听完」提示落在真实结尾 ±2s 内；上报已听秒数 ≤ 下发 duration（±1s）。
ep58 额外听一下那段 BGM 尾奏是否可接受（内容实长约 86s，其余为补足）。只读播放，不改小程序代码。

## 三之三、实测顺带发现的新问题（另建单，勿在本单里修）
已发布成品 DB 里的 `episode.duration` **比成品实际时长短**：
- ep100：文件 597.0s，`duration=586` → 少 11s
- ep99：文件 482.0s，`duration=452` → 少 30s

两期偏差不同（11s / 30s），不是固定尾段长度，指向「测量点与实际上传产物不一致」一类成因
（`concat.py` 是 `get_audio_duration(final_path)` 落库的，需查这批 20260727 产物走的哪条路径）。
影响面是**收听百分比、完播判定、进度环**（小程序侧 `duration` 用真实文件时长，后端用 DB 值）。
已按「有建议必有派生子任务」建单，来源写最初原单 T01845。
