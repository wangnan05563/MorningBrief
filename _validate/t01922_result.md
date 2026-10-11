## 根因

本单的判据是「24kHz MP3（MPEG-2 LSF）与 AAC 档位在微信小程序/iOS/Android **真机**能不能起播」，
而本环境没有设备通道：`adb` 不存在（SDK 未装）、`Get-PnpDevice` 只见到两个通用 `USB Composite Device`
（无 Android/MTP/iPhone 接口）、`AppData/Local/微信开发者工具` 只剩 `User Data`（安装体与 `cli.bat` 都没有）。
所以真机那一格**填不了**，这是环境事实，不是可以绕过的实现问题。

能绕过的部分是另一件事：真机之前，「档位到底产出了什么码流」「传输侧条件是否成立」这两项
一直没人钉死过。T01871 把 24k 挡在默认链路外，理由写的是「真机未测、支持参差」——
这是**保守边界**，但没有码流级证据支撑它到底特殊在哪。本轮把证据补上，
真机同学只需按预期值播放，不必再猜。

## 影响范围

- 只新增 `_validate/` 下的取证物料与脚本，**不改任何生产代码、不改 `.env`、不写库**；
- 影响的是决策依据：`backend/app/core/audio_profile.py` 的档位表边界（24k 是否进默认、
  `lean` 是否可对外）现在有了「哪一档真的引入新解码要求」的结论；
- 顺带发现一个**与档位无关的线上新问题**（DB 时长比成品实际时长短 11~30s），已另建单，见「本次回写」。

## 修复（交付物，绝对路径与内容）

1. `D:\code\otherProjects\20_News\_validate\t01922_materials.py` —— 物料生成 + 手写帧头解析取证。
   源料用已发布成品 `_validate/t01845_samples/ep100.mp3` 的 30–90s 切片（只读 HTTPS GET 拉取，
   走 `_validate/t01845_fetch_samples.py` 既有只读通道），**全程离线、不触发 TTS/LLM 付费链路**。
   产出 `_validate/t01922_pack/`：线上原码流逐帧拷贝 1 份 + 4 个 MP3 档 + m4a(AAC-LC) +
   生产同参 HLS 包（7 个 mpegts 分片），结果落 `_validate/t01922_pack_facts.json`。
2. `D:\code\otherProjects\20_News\_validate\t01922_pack\README-真机测试说明.md` —— 真机可执行包：
   物料清单与**每档预期值**、覆盖/未覆盖端矩阵、逐端×逐档记录表（8 行）、四项判定口径
   （起播 3s 内、非静音、时长显示 ≈60s±1s、seek 后不倒退）、设备最低覆盖要求（Android≥2、iOS≥2、记微信小版本）。
3. `D:\code\otherProjects\20_News\_validate\t01922_browser_check.mjs` +
   `_validate/t01922_browser_results.json` —— 本机唯一可用播放端口的实测（系统 Chrome 155，
   Playwright 驱动，本地静态服务 8123 只服务本物料目录）。
4. `D:\code\otherProjects\20_News\_validate\t01922_cos_range.txt` —— 自有 COS 的 Range 语义取证
   （只读 GET，含 `Range` 与不带两版对照）。

## 验证（实测证据）

A. **码流级取证**（`t01922_pack_facts.json`，帧头由脚本手写字节解析，不依赖 ffprobe 推测）：

| 物料 | 帧头实测 | 关键结论 |
|---|---|---|
| `A0_published_copy.mp3` | MPEG-1 Layer III / 44100 / mono / 128k | 线上现状基准 |
| `B_standard_64k_32000.mp3` | **MPEG-1 Layer III** / 32000 / mono | 32000 是 MPEG-1 合法值 → **默认档不引入任何新解码器要求**，与线上同格式族 |
| `C_quality_96k_44100.mp3` / `D_lean_48k_32000.mp3` | 均 MPEG-1 Layer III / mono | 同上 |
| `E_lsf_64k_24000.mp3` | **MPEG-2 Layer III，LSF=true**（version bits=2、sr_index=1） | 24k **确实**是 LSF——T01871 的保守边界成立；且它是 5 个 MP3 里**唯一带 Xing/Info 头**的（MPEG-1 四档都没有），seek/进度条行为要重点看它 |
| `F_aac_64k_32000.m4a` | AAC **LC** / 32000 / mono / faststart | 标准配置，非 HE-AAC |
| `G_hls_aac_64k_32000/` | `#EXT-X-VERSION:3`、`TARGETDURATION:10`、7×mpegts、分片内 AAC-LC@32000 | 与生产 `build_hls_cmd`（T01870 后从 PCM 直编 AAC）同参复现 |

  时长口径：容器 60.000s vs 帧算 60.056~60.084s（差 ≤84ms，属 padding 帧），无异常。

B. **Chromium 桌面内核实测**（8/8，`t01922_browser_summary.txt`）：
   `A0/A/B/C/D/E_lsf/F_m4a/G_m3u8` **全部起播**（`started=true`、`MediaError.code=null`），
   `duration` 报 60.00s（LSF 60.00、HLS 60.032），seek 到 30s 后时间继续推进 1,035~1,469ms。
   ⚠ **口径**：Chromium 解码器 ≠ Android NuPlayer/ExoPlayer ≠ iOS AVPlayer，
   这组只能证明「码流规范、无结构损坏」，**不能替代真机**，也不据此标 verified。

C. **传输侧条件成立**（自有 COS 公开成品地址，只读取证）：
   `Range: bytes=0-1` → **206**、`Accept-Ranges: bytes`、`Content-Range: bytes 0-1/9552918`、
   `Content-Type: audio/mpeg`（ep100 与 ep99 两期一致）→ 进度条拖动/断点续播不依赖本单再验，
   小程序侧若出现「进度条不动」应先从播放器/容器侧找，不是 CDN 语义缺失。

D. 清理：本地静态服务（PID 38120，端口 8123）测完已 `taskkill` 并确认端口无监听；
   未新增任何含凭据的落盘文件（物料是公开成品再编，无 token）。二进制物料按仓库惯例不入库
   （只提交脚本/取证 JSON/说明表），复现命令写在 README。

## 本次回写

- **新建 1 张派生单**（来源写最初原单 T01845，`derivedFrom=T01845`）：
  实测顺带发现的线上新问题——**已发布成品的实际时长比库里 `episode.duration` 长**
  （ep100：文件 597.0s vs DB 586，差 11s；ep99：482.0s vs 452，差 30s；偏差非固定值，
  排除「固定片尾长度」解释），影响收听百分比/完播判定/进度环与 30 分钟保底校验。
  正文 `_validate/t01922_d1.md`，编号：见下（建单在 MTask 通道恢复后执行）。
- **本环境未覆盖（必须真机，属本单自身的人工执行步骤，不再派生）**：
  微信小程序（Android/iOS 真机）、iOS Safari/AVPlayer、Android 系统播放器与第三方 App、
  微信开发者工具运行时。所需接入手段：Android 侧装 platform-tools（`adb`）+ 开 USB 调试
  （或无线调试 `adb pair`），iOS 侧需真机 + Mac/Xcode 或至少装一次微信开发者工具。
  执行入口就是 `README-真机测试说明.md` 第「三」节的表。

## 下一步建议

1. 拿到设备后按 README 矩阵跑 8×N 记录，重点两格：`E_lsf_64k_24000.mp3`（唯一非 MPEG-1）与
   `G_hls_*`（生产在用协议）。**这是本单未闭环的主体，不另建单**（避免把同一件事拆两张）。
2. 真机若全端通过 → 可考虑把 24kHz 作为 `lean24` 单档加进 `AUDIO_PROFILES`（需重跑
   `_validate/t01871_profile_verify.py` A 段口径）；不通过 → 维持现状并在
   `backend/app/core/audio_profile.py` 注释里记「24k 因 MPEG-2 LSF 真机不兼容撤除」。
   （条件性动作，取决于第 1 条结论，暂不建空单）
3. `lean=48k@32000` 是否暴露给频道级选择，取决于 T01923 的人工试听结论（已由 T01871 派生，不重复建单）。
