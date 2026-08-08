# MorningBrief 后端代码审查报告

## 基本信息

- **审查版本**：v1.0.0
- **审查模式**：增量审查（本次会话修改的后端文件）
- **审查范围**：`backend/app/routers/admin/audio.py`
- **审查文件数**：1 个
- **审查时间**：2026-08-05 15:26:00
- **审查人**：news-backend-code-review Skill
- **上次审查**：无（本次为首次针对 audio.py 的增量审查）

## 审查结果摘要

- 🔴 阻塞问题：0 个
- 🟠 严重问题：0 个（原 1 个 HIGH 已在本次走查中修复）
- 🟡 警告问题：1 个（建议修复）
- 🟢 优化建议：2 个（可选）

### 按 severity 分布

| Severity | 数量 |
|----------|------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 2 |
| INFO | 0 |

### 按 category 分布

| Category | 数量 |
|----------|------|
| security | 0（含 1 项正面实践） |
| error_handling | 0 |
| async_concurrency | 0（原 1 项 HIGH 已修复） |
| sqlalchemy | 0 |
| workflow | 0 |
| field_contract | 2 |
| fastapi | 0 |
| cache | 0 |
| config_driven | 0 |
| logging | 1 |
| performance | 1 |
| layering | 0 |
| naming | 0 |
| type_annotation | 0 |
| testability | 0 |

## 硬约束合规性检查结果

| 硬约束规则 | 状态 | 违规位置 |
|------------|------|----------|
| `deprecated_utcnow` | ✅ 通过 | - |
| `datetime_now_no_tzinfo` | ✅ 通过 | - |
| `bare_sql_injection` | ✅ 通过 | - |
| `enum_field_without_value` | ✅ 通过 | - |
| `create_task_no_reference` | ✅ 通过 | - |
| `sync_io_in_async` | ✅ 通过（已修复） | 原 `proxy_audio` 同步调用 COS SDK，已改为 `asyncio.to_thread` |
| `sync_requests_in_async` | ✅ 通过（已修复） | 同上 |
| `async_def_without_await` | ✅ 通过 | - |
| `finally_unconditional_release` | ✅ 通过 | - |
| `redis_non_atomic_lrange_ltrim` | ✅ 通过 | - |
| `token_compare_with_equals` | ✅ 通过 | - |
| `hardcoded_credentials` | ✅ 通过 | - |
| `sensitive_filter_not_initialized` | ✅ 通过 | - |
| `logout_missing` | ✅ 通过 | - |
| `builtin_exception_shadowing` | ✅ 通过 | - |
| `bare_except_pass` | ✅ 通过 | - |
| `exception_log_warning_fstring` | ✅ 通过 | - |
| `internal_route_no_auth` | ✅ 通过（不适用） | - |
| `print_statement` | ✅ 通过 | - |
| `print_traceback_format_exc` | ✅ 通过 | - |
| `os_getenv_direct` | ✅ 通过 | - |

**合并结论**：允许合并（无 CRITICAL / 阻塞级违规；原 HIGH 异步阻塞已闭环修复）

## 详细问题列表

### 🟡 警告问题（建议修复）

1. **proxy_audio 将整个 COS 对象读取进内存后一次性返回** → **已实施（2026-08-05 15:35）**
   - **位置**：`backend/app/routers/admin/audio.py` `proxy_audio`
   - **问题**：成品音频可达 10MB+，代理把对象全部读入内存再以 `Response` 返回，并发播放时内存峰值明显。
   - **实施**：改为 `StreamingResponse`，在 `asyncio.to_thread` 内分块（1MB）yield；保留 `get_object` 的**前置**执行（在生成器外、路由内 eagerly 调用），使 SSRF 校验与对象存在性错误仍能在返回 200 之前以 404 干净抛出，避免「已发响应头后再断流」产生损坏音频。

### 🟢 优化建议（可选）

1. **`episode_file_info.path` 在远端模式下为 `None`，前端展示"文件路径: null"** → **已实施（2026-08-05 15:35）**
   - **实施**：远端模式 `path` 置为 `"云端(COS)"`（可读文案），前端 `WorkflowDetail.vue` 的「文件路径」直接渲染该文案，不再出现字面 `null`；播放仍走 `url` + 代理。

2. **`proxy_audio` 异常日志保留堆栈** → **已实施（2026-08-05 15:35）**
   - **实施**：except 块 `logger.warning("音频代理失败 ...", workflow_id, key, exc_info=True)`，保留完整堆栈便于排障。

### 已修复项（本会话走查中闭环）

1. **🔴→已修复 异步事件循环阻塞（HIGH / async_concurrency）**
   - **原问题**：`proxy_audio` 在 `async def` 路由内直接 `client.get_object(...)` + `.get_raw_stream().read()`，COS SDK 为同步阻塞调用，会卡住整个事件循环，影响所有并发请求。
   - **修复**：依项目约定（`uploader.py` 文档与 `upload_to_cos` 均用 `asyncio.to_thread` 包裹 COS 同步调用），改为 `await asyncio.to_thread(client.get_object, ...)` 与 `await asyncio.to_thread(resp["Body"].get_raw_stream().read)`，并补 `import asyncio`。

2. **🟡→已修复 远端 TTS `size_bytes` 语义错误（MEDIUM / field_contract）**
   - **原问题**：回退分支用 `int(seg.get("duration", 0) or 0)` 把音频时长（秒）误当作字节数填入 `size_bytes`，前端"大小"列会显示错误数值。
   - **修复**：远端对象未知真实字节数，置 `size_bytes=0`（前端展示"大小未知"），并加注释说明。

3. **🟡→已修复 成品回退分支嵌套在 `if wf is not None` 内（MEDIUM / error_handling / field_contract）**
   - **原问题**：`list_audio` 的 Episode/Review 远端回退逻辑写在 `if wf is not None` 分支内，当 Workflow 记录缺失（但 Episode 已生成）时，成品面板会返回 `episode_file=None` 而空白——比原 bug 更隐蔽的边界。
   - **修复**：将 `episode_date_str` 解耦，本地成品 glob 与「本地无成品时的 Episode/Review 回退」并列在 `if ep_path / else` 结构中，回退**不再依赖 Workflow 是否存在**。生产环境（Workflow 存在）行为不变，仅新增「Workflow 缺失但成品存在」时的兜底。该修复由新增的 `test_list_audio_remote_fallback_no_null_path` 在无 Workflow 行的情况下验证。

## ✅ 好的实践

- **SSRF 防护到位（security）**：`proxy_audio` 仅放行项目配置的 COS 域名与 CDN 域名（`allowed_hosts`），对 `netloc` 做精确比对，且 Bucket 固定为 `settings.COS_BUCKET`，无法被用作通用代理；非法地址返回 `BizError` 而非 500。
- **二进制响应未包装 success()（fastapi / 维度 124）**：`proxy_audio` 返回 `StreamingResponse(..., media_type="audio/mpeg")`（分块流式），符合"二进制响应当裸返回、不包 `{code,message,data}`"的契约；`stream_tts`/`stream_episode` 也正确使用 `FileResponse` + 显式 `media_type`。
- **配置驱动（config_driven）**：COS 域名/桶/区域全部走 `settings.COS_BUCKET / COS_REGION / COS_CDN_DOMAIN`，无硬编码凭据或 URL。
- **错误处理规范（error_handling）**：`proxy_audio` 用 `except Exception` 兜底并映射为 `NotFoundError`（404），无裸 `except: pass`；`list_audio` 对 `episode_date` 为 `None` 的工作流做 `try/except` 兜底，避免 500 导致整个音频接口失败。
- **回退逻辑健壮性（field_contract）**：`list_audio` 回退 TTS 时先判 `if script and script.segments`，再逐段 `isinstance(seg, dict)` 过滤，避免非字典分段导致 `AttributeError`。
- **日志规范（logging）**：使用 `logging.getLogger(__name__)`，无 `print()`。

## 测试运行结果

- **py_compile 验证**：✅ 通过（`python -m py_compile backend/app/routers/admin/audio.py`）
- **前端契约测试**：✅ 通过（`admin-web/tests/workflow.spec.js` 新增「打包态(COS)下工作流详情三面板可展示内容」用例，8 passed；mock `workflowAudioResponse` 已同步新契约：`path="云端(COS)"`、`size_bytes=0`）
- **后端单元/集成测试**：✅ 新增 `backend/tests/test_audio_router.py`（4 passed）——覆盖 `proxy_audio` SSRF 拦截（非法主机 / 非 http(s) 协议）、配置 COS 域名放行 + 流式代理（mock `_get_client`）、以及 `list_audio` 打包态回退（无 Workflow 行时 Episode 远端回退不返回 `null`），mock 复用 `conftest` 的 `client`/`db_session`/`admin_token`。

## 审查结论

- [x] 有条件通过（仅警告与优化建议级别问题；原 HIGH 异步阻塞已修复）

## 修复验证

```powershell
# 1. 语法检查
python -m py_compile backend/app/routers/admin/audio.py

# 2. 前端契约回归
node_modules/.bin/playwright test tests/workflow.spec.js --project=chromium
```

## 报告归档

报告保存路径：`.workbuddy/skills/news-backend-code-review/reports/2026-08-05_152600_incremental_report.md`
