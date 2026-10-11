## 根因

T01845 的实测把矛盾点挑明了：成品内容上限只有约 10kHz（TTS 源 24kHz 被上采样到 44.1kHz），
而链路里码率与采样率是**两处各写各的**——码率走 `AUDIO_BITRATE` 配置，采样率在拼接侧写死
`_STITCH_SAMPLE_RATE="44100"`（T01870 为单变量复验刻意保留），在 TTS 后处理侧又跟随
`ALIYUN_TTS_SAMPLE_RATE`。结果是：64k 的预算被拿去描述 10kHz 以上根本不存在的内容，
PCM 中间态还按 88KB/s 落盘。参数没错，错在「两个必须成组调的参数被拆成三个来源」。

## 影响范围

- `backend/app/core/audio_profile.py`（新增）：档位真相源
- `backend/app/config.py`：`AUDIO_PROFILE` 新字段，`AUDIO_BITRATE` 默认值改为空（跟随档位），新增 `AUDIO_SAMPLE_RATE`
- `backend/app/workflow/stitch/ffmpeg_wrapper.py`：`_STITCH_SAMPLE_RATE` 常量删除，改 `_stitch_sample_rate()`
- `backend/app/workflow/tts/audio_postprocess.py`：后处理不再跟随 provider 采样率
- `backend/app/routers/admin/ai_config.py`：新增只读端点
- `apps/admin-web/src/views/ai/AIConfig.vue`：TTS 页顶部只读档位块
- `backend/.env.example`、`app/workflow/tts/voices.yaml`、`docs/详细设计说明书.md`：口径同步
- 不影响：段缓存 COS 对象格式（仍 mp3）、时长保底口径（`duration.py` 未动）、前端与小程序契约

## 修复（绝对路径与改动点）

1. `D:\code\otherProjects\20_News\backend\app\core\audio_profile.py`（新增）
   - `AUDIO_PROFILES`：`quality=96k@44100` / `standard=64k@32000`（默认）/ `lean=48k@32000`；
   - `resolve_encoding(settings)` 返回 `AudioEncoding(profile,label,bitrate,sample_rate,overridden)`，
     `AUDIO_BITRATE` / `AUDIO_SAMPLE_RATE` 保留为逃生阀，非空即覆盖并在返回值里标 `overridden`；
   - `normalize_profile()` 非法值回退 standard（与 `audio_modes.normalize_gap_mode` 同口径）；
   - 采样率只取 MPEG-1 Layer III 合法值（32000/44100）。24kHz 属 MPEG-2 Layer III（LSF），
     微信内置播放器与部分 Android 解包器支持参差，真机未实测前不进默认链路——这是本单与
     T01845 建议（「24k 更优」）之间刻意保留的保守边界。

2. `D:\code\otherProjects\20_News\backend\app\config.py:378-386`
   - `AUDIO_PROFILE: str = "standard"`；`AUDIO_BITRATE: str = ""`（留空=跟随档位）；
     `AUDIO_SAMPLE_RATE: int = 0`。`.env` 未设这三项，故默认即 standard；未改 `.env` 本体。

3. `D:\code\otherProjects\20_News\backend\app\workflow\stitch\ffmpeg_wrapper.py`
   - `_STITCH_SAMPLE_RATE` 常量 → `_stitch_sample_rate()`（读档位）；`_pcm_args()` /
     `_encode_args()` / `generate_silence` 的 `anullsrc` / `build_hls_cmd` 全部改调该函数；
   - 模块 docstring 更新为「采样率与码率都取自档位套餐，本文件不再写死数值」。

4. `D:\code\otherProjects\20_News\backend\app\workflow\tts\audio_postprocess.py:88-96`
   - `postprocess_segment` 的 `-ar` 由 `settings.ALIYUN_TTS_SAMPLE_RATE` 改为档位采样率、
     `-b:a` 由 `settings.AUDIO_BITRATE` 改为档位码率；每次调用现取 `get_settings()`（热更新生效），
     模块级 `settings` 单例引用随之删除。provider 侧请求参数（`ALIYUN_TTS_SAMPLE_RATE`）刻意不动：
     它是「向上游要什么」，与「交付什么」解耦，多要的部分在后处理一次性降掉。

5. `D:\code\otherProjects\20_News\backend\app\routers\admin\ai_config.py:265-299`
   - `GET /admin/api/v1/ai/audio-profile`：返回当前档位、实际生效码率/采样率、`overridden`、
     PCM 落盘速率与三档表；**不提供写接口**（改档必须走 `.env` + 真机与试听收口），
     并有 `test_audio_profile_is_read_only` 锁死「该路径只注册 GET」。

6. `D:\code\otherProjects\20_News\apps\admin-web\src\views\ai\AIConfig.vue`
   - TTS 标签页顶部 `el-alert` 只读块：当前档位名 + 码率@采样率 + 三档 chip + PCM 体积提示；
     `loadConfig()` 里独立 try 拉取（取不到不影响配置页主流程）；被 `.env` 覆盖时显示「已被单独覆盖」。

7. `D:\code\otherProjects\20_News\backend\.env.example:195-205`、
   `D:\code\otherProjects\20_News\backend\app\workflow\tts\voices.yaml:3-4`、
   `D:\code\otherProjects\20_News\docs\详细设计说明书.md` §5.5 编码口径块：同步档位口径。

## 验证（实测证据）

A. 真实成品上的档位对比（`_validate/t01871_profile_verify.py`，ep100 第 30s 起 300s，
   参考=该成品解码 PCM，四候选均为**同代**编码，覆盖 307s）：

| 档位 | segSNR 均值 | p10 | LSD | 300s 字节 | 频谱截止 |
|---|---|---|---|---|---|
| 64k@44100（旧口径） | 23.37 | 14.98 | 5.834 | 2,400,591 | 8936 Hz |
| **64k@32000（standard）** | **24.78** | **15.91** | **5.731** | 2,400,812 | 9410 Hz |
| 48k@32000（lean） | 19.57 | 12.19 | 9.251 | 1,800,620 | 7579 Hz |
| 96k@44100（quality） | 33.22 | 22.98 | 3.464 | 3,600,866 | 9754 Hz |

   - 结论 1：同码率下降采样率**确实提质**——+1.41dB segSNR、+474Hz 有效截止，体积差 221 字节（≈0）。
     与 T01845 的 23.86→24.77 一致（本次起点 23.37 略低，因参考是已发布的 128k 成品解码再编，
     比 T01845 多一世代际；**同代横向对比不受影响**）。
   - 结论 2：`lean=48k@32k` 只有 19.57dB，低于 64k 一档的代际基准，**不具备设为默认的条件**，
     仅作弱网可选项保留（本单不删档，但默认仍是 standard）。

B. 链路真跑（同一脚本，离线真跑生产函数 `concat()` 正常分支，24 段 + 头中尾广告 + BGM + HLS）：

   | 档位 | 段缓存采样率 | 成品采样率/码率 | 成品时长 | 临时目录峰值 | 泄漏 |
   |---|---|---|---|---|---|
   | standard | 32000 | 32000 / 64016bps | 346s | 27.94 MB | 0 |
   | quality | 44100 | 44100 / 96020bps | 346s | 39.23 MB | 0 |

   - 档位贯通到两端（段缓存与成品采样率同步跟随），成品时长口径 346s 两档一致（未动 `duration.py`）；
   - PCM 中间态峰值 39.23MB→27.94MB（-28.7%，与 32/44.1 比例吻合），无临时目录泄漏。

C. 自动化测试：新增 `backend/tests/test_audio_profile.py`（21 例：三档解析、非法回退、
   覆盖标记、体积口径、拼接/HLS/后处理命令跟随档位、端点鉴权与只读性）；
   `test_stitch_lossless_intermediates.py` 的 `-ar` 断言由 44100 改 32000（防止回退到硬编码）。
   后端全量 `pytest -q` → **1039 passed**（原 1018 + 本单 21）。

D. 管理端 UI 实测（`_validate/t01871_ui_check.mjs`，Playwright + 系统 Chrome，
   隔离后端=副本库 + `APP_ROLE=api` + 8000，vite=5173，未触碰生产库与真实用户）：
   - 接口实调返回 `standard / 64k / 32000 / overridden=false / 三档表`（`_validate/t01871_api_profile.json`）；
   - 页面 TTS 标签顶部渲染：`成品输出档位：标准（64k @ 32000Hz）`，三档 chip 齐全，
     块内可编辑控件数 `EDITABLE_CONTROLS=0`（截图 `_validate/t01871_ui_profile.png`）；
   - 验证后已停掉自拉的 vite/uvicorn 并确认端口释放，含明文 JWT 的临时目录已删除。

E. 提交：`c3c7200 feat(audio): 码率+采样率收敛为档位套餐并只读展示（T01871）`（17 文件）。

## 本次回写

- 本环境**不可落地**两项（原文任务项 3、4），已按「有建议必有派生子任务」建单，`derivedFrom` 写最初原单 T01845：
  - **T01922**【AI回写待审核】32k/24k 与 AAC 档位的真机起播兼容实测（小程序/iOS/Android）
  - **T01923**【AI回写待审核】standard 档人工 A/B 试听收口（3 个衔接点 + 片头 BGM 垫乐段 + 齿音段）
  - 建单前已按 REST `/api/tasks` 全量查重（news 项目 41 单，含归档），无同题单。
- 观察项（仅观察不建单）：provider 请求采样率仍为 `ALIYUN_TTS_SAMPLE_RATE=44100`，与交付档位解耦，
  上游多下的样本在后处理一次降掉；段缓存是 mp3 按码率计费，体积不受采样率影响，故不单独派生。

## 下一步建议

1. 档位定为默认前，必须先有 **standard 档的真实新成品**：当前已发布成品全是 128k@44.1k 旧产物，
   本单 A 段的参考因此带一世代际。前置 T01696（工作流恢复、LLM 402/爬取/TTS 三类失败恢复）——
   该依赖已由 T01696 自身承载，本单不重复建单。
2. 派生单 **T01922**（真机兼容）与 **T01923**（人工试听）完成后，再决定是否把 `lean` 暴露给频道级选择，
   以及是否值得为 24kHz 单开一档（需 MPEG-2 LSF 真机结论）。
