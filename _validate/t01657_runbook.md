# T01657 听书频道 30 分钟保底 · 真跑复验手册

## 0. 本环境判定：**不可在本环境落地**（不是代码问题，是外部条件缺失）

| 前置 | 现状（2026-10-09 实测，只读） | 结论 |
|---|---|---|
| MorningBrief 运行实例在跑 | `8000/8001/8010/8200` 全部无监听，`netstat` 无本服务端口 | ✗ 实例未运行 |
| 频道类型正确（任务第 1 条） | channel 11「历史故事·每日听书(自动生成)」`channel_type=audiobook`、`is_active=1`、`schedule_time=04:00:00`、`min_duration_sec=NULL` | ✓ 已满足，无需改 |
| 听书保底口径生效 | `app/workflow/duration.py:18` `AUDIOBOOK_DEFAULT_MIN_SEC=1800`，`resolve_channel_min_duration_sec()` 在 `min_duration_sec=None` 时对 audiobook 兜底 1800s；`duration_range_sec()` 同步抬高上限为 `max(全局600,1800)×1.2=2160`（避免历史「区间倒挂 [1800,720]」） | ✓ T00914 二轮的代码链路完整 |
| 书池/素材充足 | channel 11 `material` 105 条 | ✓ 够 |
| LLM 可用 | 最近两次听书工作流（`wf-20260901-0001`、`wf-20260905-0001`）rewrite 失败：`APIStatusError 402 - Sorry, your account balance is insufficient`；全库 `workflow.error like '%402%'` **16 条** | ✗ **LLM 账户余额不足** |
| 实例近期是否产出 | `workflow` 按月：2026-07 success 53 / 2026-08 success 28 + failed 19 / **2026-09 failed 24，success 0**；最后一条工作流 `2026-09-05`；最后一条 episode `2026-07-29 22:30` | ✗ 流水线已停摆约 34 天 |
| 人工试听（任务 3.4） | 需要人耳判断段间衔接是否有书外素材嫁接/新闻套话 | ✗ 不可代判 |
| TTS 通道 | `wf-20260819-0013`：`tts 成功 2/9（<50%）`，`Edge-TTS Cannot connect to host speech.platform.bing.com:443`（代理不可用） | ⚠ 需复核网络 |

所以本单**不标 done**：主体（真跑一期 + 抽查）必须在用户的运行实例上执行，
且要先解决 LLM 余额与实例停摆。本手册与 `_validate/t01657_verify_run.py` 是把复验压成一条命令。

## 1. 关键设计：为什么断言不走日志（重要）

任务第 3 条要求「当日日志出现 `时长/字数联动 target_sec=1800`」与
「没有出现 `时长不足兜底 … 补足 Ns（BGM=…）`（补足 >120s 视为改写侧字数不足）」。
实测这两行的源代码是 **loguru + %-style 占位符**：

- `app/workflow/llm/rewriter.py:1853` `logger.info("时长/字数联动 target_sec=%d rate=%.2f 目标段数=%d …")`
- `app/workflow/stitch/concat.py:445` `logger.info("时长不足兜底 workflow_id=%s 时长=%ds < 下限=%ds，补足 %ds（BGM=%s）", …)`

loguru 用 `{}` 格式化，不做 `%` 替换（已在本机用同一 venv 复现：
`logger.info("… target_sec=%d …", 1800, …)` 输出仍是 `%d` 字面量）。
→ **只要 T01678（全仓 loguru %-style 修复）未落地，日志里的数值就永远读不到**，
「补足 >120s」这类判据不可判定（功能可能完全正常，日志却显示 `%ds`）。

对策（已写进脚本）：把可判定口径全部改走数据库，日志只作存在性 grep：

| 任务口径 | 日志口径（现被 T01678 屏蔽） | 脚本使用的替代断言 |
|---|---|---|
| 3.1 成品 ≥1800s | — | `episode.duration`（并在能定位本地文件时用 ffprobe 实测） |
| 3.2 联动 target_sec=1800 | `时长/字数联动 target_sec=%d` | `script.estimated_duration ≥ 1800×0.8` + 段数/每段字数分布 |
| 3.3 无超长/StitchError | raise 文案是 f-string（可用） | `workflow_step.stitch.status` 与 `error` 文本 |
| 3.3 无大段 BGM 硬凑（>120s） | `时长不足兜底 … 补足 %ds` 数值丢失 | `estimated_duration≥1440 且 duration≥1800` ⇒ 未触发兜底；另 grep 「时长不足兜底」出现即告警 |
| 3.4 人工试听 | — | 脚本打印前 4 段的起/止 40 字，供试听定位，不代判 |

## 2. 真跑前修复清单（按顺序，全部走管理端接口，不改 `.env`、不直写库）

1. **LLM 余额/供应商**：管理端「AI 服务配置」检查 `llm_base_url`（当前 siliconflow）与余额；
   必要时切到 `llm_preset_configs` 里的另一路预设并 `llm_selected_model` 生效。
   ⚠ 该表里存有 api_key 明文，本手册与回传**不复述其值**；建议顺带确认是否需要轮换。
2. **起实例**：`python launcher.py`（默认 `APP_ROLE=all`、workers=1）；
   确认 cron 已注册（日志 `Added job` 且 `[startup] 进程角色=all`）。
   若同时开 workers>1，走 T01660 的 launcher 自动编排（1 sched + N api），
   定时任务只在 sched 进程注册，不会重复触发听书工作流（这是重复消耗的真实风险点）。
3. **TTS 通道**：`tts_provider=edge` 依赖 `speech.platform.bing.com` 可达；
   08-19 曾因代理不可用失败 7/9 段。先跑一小段合成验证再跑整期。
4. **（可选但强烈建议）先修 T01678 的两行**：只改 rewriter/concat 这两处为 f-string 即可
   让 3.2/3.3 的日志数值口径恢复可判定，成本远低于整仓修复。

## 3. 执行（一条命令）

```bash
# 只读预检（零副作用、零花费）——先看前置是否齐
backend/.venv/Scripts/python.exe _validate/t01657_verify_run.py --channel-id 11

# 真跑一期并复验（会消耗 LLM/TTS 预算并写入实例数据库）
set T01657_ADMIN_PASSWORD=***        # 口令只走环境变量，不落盘
backend/.venv/Scripts/python.exe _validate/t01657_verify_run.py \
    --trigger --base http://127.0.0.1:8000 --channel-id 11 --timeout-sec 5400

# 事后复验某期（不花钱）
backend/.venv/Scripts/python.exe _validate/t01657_verify_run.py --workflow-id wf-YYYYMMDD-NNNN
```

脚本行为：登录管理端 → `POST /admin/api/v1/workflows/trigger {channel_id, episode_date, skip_crawl:false}`
→ 轮询 `workflow`/`workflow_step` 到终态 → 按 §1 的替代断言出 PASS/FAIL →
落 `_validate/t01657_verify_result.json` → 退出码（0 达标 / 2 未达标）。

## 4. 任务第 4 条（段数不足时）

若 10 段 × ~975 字仍达不到 1800s（脚本会在 §3.2 断言失败时打印提示）：
管理端把 `ai_config.llm_max_script_segments` 调到 **18~20**（运行时热调，无需改码）后复跑一期，
并把「段数 / 每段字数 / estimated_duration / 最终 duration」四列对照记进
`_validate/t01657_verify_result.json` 的两次运行。

## 5. 残留限制

- 成品 `duration` 由拼接阶段写入，音频在 COS 时脚本无法 ffprobe 实测（打印「不可得」），
  严格意义的「实测非估算」仍需人把音频拉到本地再跑一次 `--db` 指向含 `audio_cache` 的目录。
- 人工试听（3.4）不可自动化。
- 本手册所有历史失败结论取自 `backend/data/news.db` 只读查询，未写入任何东西。
