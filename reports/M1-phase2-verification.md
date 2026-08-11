# M1 Phase 2 验证报告（业务范围扩展 MVP：T4–T12）

> 生成时间：2026-08-11 | 验证人：小搭（WorkBuddy）
> 运行环境：`backend/.venv/Scripts/python.exe`（Python 3.12，含全部依赖）

## 1. 验证范围

本轮完成 M1 后端扩展全部改造的**编译 + 单元验证**，覆盖：
- T4/T10 选题策略抽象（heat / outline / manual）
- T5 Channel 模型字段 + 启动迁移
- T6/T7 课程重写模板 + intro/outro 文案
- T8 concat 关广告守卫
- T9 课程手动触发入口（skip_crawl）

## 2. 编译检查（6 文件全通过）

| 文件 | 状态 |
|------|------|
| `app/models/channel.py` | OK |
| `app/main.py` | OK |
| `app/workflow/llm/rewriter.py` | OK（修 2 处语法/缩进 bug 后）|
| `app/workflow/stitch/concat.py` | OK |
| `app/services/workflow_scheduler.py` | OK |
| `app/routers/admin/workflows.py` | OK |

## 3. 单元测试结果：`temp/test_strategy_unit.py` —— 22/22 PASS

- `_parse_material_ids`：10 例（None/空/空白/`[]`/合法数组/含 null/字符串数字/`'3'` 单引号非法/非 JSON/非数组）✅
- `_select_top_materials`：7 例
  - heat：品类轮询第一轮 `[1,3,5]`、top_n 上限、超量返回全部 ✅
  - outline：按素材 id 升序切片 `[1,2,3]` ✅
  - manual：按指定顺序 `[4,2]`、空 ID→空选、默认 strategy=heat ✅
- channel 迁移：三列 `selection_strategy`/`enable_ad`/`manual_material_ids` 存在 + **幂等二次迁移无报错** + 可写入读回 `"manual",0,"[10,20]"` ✅

## 4. 本轮修复的缺陷（均为本阶段引入）

| # | 位置 | 现象 | 修复 |
|---|------|------|------|
| 1 | `rewriter.py` L942 | SyntaxError：旧 docstring 体串进代码位（全角冒号 `：`）| 删除孤儿 docstring 块 |
| 2 | `rewriter.py` `_fetch_channel_prompts` | IndentationError：`if ch is None:` 体丢失 4 空格缩进 | 补缩进 |
| 3 | `rewriter.py` 三处日志 | loguru 用 `%d`/`%r`（应为 `{}`），告警丢失变量 | 改为 `{}` |

## 5. 静态确认项

- **course 模板接线**：`rewrite()` 已消费 `rewrite_template`/`intro_prompt`/`outro_prompt`（既有字段），课程频道只需配置 `rewrite_template="rewrite_course.txt"` + intro/outro 文案，T6/T7 **无新增接线代码**。
- **关广告守卫**：`concat.py:294-312` 查 `Channel.enable_ad`，缺省 1（兼容存量），仅显式 `0` 跳过广告查询。
- **手动触发**：`workflow_scheduler.trigger_workflow(...,skip_crawl)` 预置成功 crawl Step；`TriggerRequest` 增 `skip_crawl`/`episode_date`。

## 6. 待办 / 决策点

1. **【决策】list 去重口径**：当前为**全局 `content_hash`**（与频道无关，同一文档传不同频道也 409）。若需频道级隔离，需把 `channel_id` 加入 `(source_type, dedup_key)` 查重条件 —— 待用户拍板。
2. **【待执行】课程全链路真实 HTTP 闭环**：上传文档 → T3 入库 → skip_crawl 触发 → 课程模板 rewrite → tts → stitch 无广告 → publish 可播放。需运行中的 `uvicorn` + 真实 LLM/TTS 凭证 + ffmpeg，**沙箱无凭证，留待部署后手动验证**。
3. **任务状态**：#10(T6/T7)、#11(T8)、#12(T9) 已标记 completed；#13(T11/T12 复用+端到端)、#7(M1 验证) 仍 pending（等部署后手动 e2e）。

## 7. 部署后手动 e2e 清单

```bash
# 1) 启服务（单 worker，进程内优化约束）
uvicorn app.main:app --workers 1 --host 127.0.0.1 --port 8000

# 2) 配一个课程频道（admin）：selection_strategy=outline, enable_ad=0,
#    rewrite_template=rewrite_course.txt, intro_prompt/outro_prompt=课程文案

# 3) 上传文档（逐章入库）
curl -F "file=@doc.md" -F "channel_id=<cid>" http://127.0.0.1:8000/admin/api/v1/materials/upload

# 4) 手动触发（跳过爬虫，从 rewrite 起）
curl -X POST http://127.0.0.1:8000/admin/api/v1/workflows/trigger \
  -H 'Content-Type: application/json' \
  -d '{"channel_id":<cid>,"skip_crawl":true,"episode_date":"2026-08-11"}'

# 5) 断言：episode 可播放、无广告段、按文档章节顺序、课程口吻
```

## 8. 补充（2026-08-11 续）

### 8.1 去重口径决策
用户确认 **list 去重维持全局 content_hash**（与频道无关）。`models/material.py` 的 `(source_type, dedup_key)` 查重即全局语义，无需改动。

### 8.2 T5 API 暴露缺口修复（重要）
原 admin 频道 API（`ChannelCreateRequest` / `ChannelUpdateRequest` / `ChannelService.create_channel` / `update_channel`）**未暴露** `selection_strategy` / `enable_ad` / `manual_material_ids`，导致课程频道无法经 API 配成 outline+关广告（只能直改 DB）。已补齐：
- `routers/admin/channels.py`：两请求体加三字段 + 两 `field_validator`（`selection_strategy`∈{heat,outline,manual}、`enable_ad`∈{0,1}）+ `_channel_to_dict` 序列化三字段 + 两个端点透传。
- `services/channel_service.py`：`create_channel`/`update_channel` 签名与赋值补齐。
- 验证：`py_compile` 通过；`ChannelCreateRequest`/`ChannelUpdateRequest` 构造+非法值拦截单测通过。

### 8.3 一键 e2e 脚本
新增 `scripts/e2e_course_channel.sh`（curl + python 解析，无 jq 依赖）：登录 → 配置/更新课程频道(outline+enable_ad=0+rewrite_course.txt+intro/outro) → 上传文档(multipart) → `skip_crawl` 触发 → 轮询 workflow 至 success → 断言节目发布。`bash -n` 通过。
前置：运行中的 uvicorn(--workers 1) + 真实 LLM/TTS 凭证 + ffmpeg + 有效 admin 账号。
用法：

```bash
PYTHON=python BASE_URL=http://127.0.0.1:8000 \
  ADMIN_USER=admin ADMIN_PASS='******' \
  DOC_PATH=/path/to/doc.md [CHANNEL_ID=123] \
  bash scripts/e2e_course_channel.sh
```

不传 CHANNEL_ID 时自动新建临时课程频道（名称含 `E2E_` 前缀）并打印 ID，便于事后清理。
