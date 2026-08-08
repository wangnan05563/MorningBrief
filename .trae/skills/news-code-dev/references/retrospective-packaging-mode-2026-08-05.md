# 复盘：打包模式空列表缺陷 + 全量测试流程（2026-08-05）

> 本复盘基于本轮会话中解决的两个核心问题：
> 1. **打包模式（PyInstaller exe）下工作流详情页「素材 / TTS 片段 / 成品」三个面板为空** 的根因定位与修复；
> 2. **对以上修改做全量测试**（后端 pytest + 前端 Playwright），验证并沉淀可复用的测试流程。
>
> 采用 **Sequential Thinking（分步推理）** 完成：先逐层拆解成功步骤，再识别不确定性与失败点，最后抽象出可固化的固定流程/判断逻辑与适用边界，并据此更新四个技能（news-code-dev / news-backend-code-review / news-frontend-code-review / news-auto-testing）。

---

## 一、编码任务复盘（打包模式空列表缺陷）

### 维度 1：成功执行任务的完整步骤（顺序不可颠倒）

| 步 | 动作 | 关键产出 |
|----|------|----------|
| 1 | 复现现象 | dev 模式数据正常，exe 模式三面板为空 → 初步判定为「存储路径差异」而非「逻辑缺失」 |
| 2 | 分层定位根因 | 现象层（面板为空）→ 数据层（前端拿不到 items）→ 接口层（`list_audio` 返回空）→ 存储层（COS 配置了 → 只上传云端、无本地副本、本地缓存目录为空） |
| 3 | 确认模式开关 | `sys.frozen` 判定 exe 模式；`is_cos_configured()` 判定 COS 是否启用 → 双写仅在 dev 模式发生 |
| 4 | 修复后端 `list_audio` | 本地缓存为空时，回退到 DB 持久化的远程 URL（`Script.segments[].audio_url`、`Episode/Review.audio_url`） |
| 5 | 新增 `proxy_audio` 端点 | SSRF 域名白名单 + `asyncio.to_thread` 包裹同步 COS SDK + `StreamingResponse` 1MB 分块流式返回 |
| 6 | 修复前端面板 | `path` 返回 `"云端(COS)"`、远程项禁用删除、远程音频走 `proxy_audio` 播放 |
| 7 | 后端 code review | 关闭 async 阻塞 / size_bytes / 流式 / 远程 path / 日志 5 类问题 |
| 8 | 全量回归 | 后端 374 passed、前端 58 passed（10 个 spec） |
| 9 | 规范提炼 | 沉淀 R186–R195 共 10 条编码标准 + 对应代码审查维度 |

**关键教训**：步骤 2 的分层诊断（现象→数据→接口→存储）是定位此类「dev 正常 / 打包后异常」问题的唯一高效路径；直接改前端或加日志都会走弯路。

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响 | 根因 | 修复方式 |
|--------|----------|------|------|----------|
| 列表查不到内容 | exe 模式 COS 已配置，本地 `data/audio_cache` 为空，且接口只查本地 | 三面板全空 | 接口未回退 DB 远程 URL | `list_audio` 本地空→回退 DB URL |
| 异步路由阻塞 | `proxy_audio` 直接在 async 路由里调同步 COS SDK | 事件循环被占，并发请求排队 | 同步 SDK 未 `to_thread` | `await asyncio.to_thread(...)` |
| 大音频一次性返回 | 用 `Response` 一次性读全量字节 | 内存峰值高、易超时 | 未用分块流 | `StreamingResponse` 1MB 分块 |
| 二进制响应被信封包裹 | 音频响应走 `success({data: ...})` | 前端 `responseType:blob` 解析失败 | 复用 JSON 统一响应 | 原始 `StreamingResponse`/`FileResponse` |
| SSRF 风险 | 代理任意外部音频 URL | 内网探测 | 无域名白名单 | 复用 `uploader._get_client` + 配置域名白名单 |
| 远程项被误删 | 前端对云端资源提供删除 | 云端对象被误删且无法本地恢复 | 未区分本地/远程 | 远程 `path` 标记 + 删除保护 |
| 测试误报（打包模式） | 用 dev 模式跑测试，未覆盖 exe 行为 | 假阴性 | 未识别服务模式 | 服务模式自动检测（dev/exe/docker） |

### 维度 3：可抽象的固定流程与判断逻辑

```
打包模式空列表问题通用诊断流程（按序，命中即停）：
  面板为空
    → 前端是否收到 items？是/否
      ├─ 否 → 接口层问题
      │      ├─ 本地缓存是否为空？
      │      │    ├─ 是 → 是否回退 DB 持久化远程 URL？否 → 修复 list_audio 回退
      │      │    └─ 否 → 本地存储/路径问题
      │      └─ COS 是否配置（is_cos_configured）？
      │           └─ 是 → exe 模式双写缺失，需「本地缺失→云端回退」
      └─ 是 → 前端渲染/字段契约问题（size_bytes / path 语义 / 懒加载）

音频代理服务标准实现（判断信号）：
  grep 路由中调用同步 SDK（cos/uploader）
    → 是否在 asyncio.to_thread 内？否 → CRITICAL
  grep 二进制响应是否 success() 包裹？是 → 必须改为原始 StreamingResponse
  grep 代理外部 URL 是否校验域名白名单？否 → SSRF 风险
```

**落地判断信号（grep）**：
- 外部存储回退缺失：`list.*audio` 中本地空后直接 `return []`
- 同步 SDK 未包裹：`cos_client.get_object` 出现在 `async def` 且非 `to_thread`
- 二进制信封：`return success(` 包裹 `.mp3`/`.wav` 响应体
- 远程未保护：`path` 含 `cos` 但前端仍渲染删除按钮

### 维度 4：适用场景与不适用场景

| 固定流程 / 判断逻辑 | 适用场景 | 不适用场景 |
|----------------------|----------|------------|
| 本地缺失→云端回退 | 任何「COS/OSS/S3 已配置、本地无副本」的列表接口 | 纯本地文件服务、无云端双写 |
| 同步 SDK → to_thread | 在 FastAPI async 路由调用任意同步第三方 SDK | 同步框架（Flask）、SDK 本身已 async |
| 二进制原始响应 | 音频/图片/文件下载类端点 | JSON API、分页列表 |
| SSRF 域名白名单 | 代理/中转任意外部 URL 的端点 | 仅服务本地静态资源 |
| 服务模式自动检测 | 支持 dev/exe/docker 多模式部署的项目 | 单一运行模式 |

---

## 二、测试流程复盘（全量测试）

### 维度 1：成功执行任务的完整步骤

| 步 | 动作 |
|----|------|
| 1 | 识别测试范围：本次修改涉及后端 `audio.py`、前端 `audio.js`/`WorkflowDetail.vue` 及配套单测、E2E |
| 2 | 读取 `news-auto-testing/config.yaml`，确认 `service_mode_detection` 为 exe 模式 |
| 3 | 后端：用 `backend/.venv` 的 pytest（非 managed venv），`pytest backend/tests/test_audio_router.py` 4 passed |
| 4 | 前端：Playwright 跑全部 spec，**特定路由必须在 catch-all `**/admin/api/v1/workflows*` 之前注册**（注册顺序敏感） |
| 5 | 规避沙箱 safe-delete：Playwright 启动清理旧 `test-results` 触发沙箱保护 → 用唯一 `--output=test-results-$(date +%s)` |
| 6 | 全量回归：后端 374 passed（含 4 个新路由测试）、前端 58 passed（10 spec） |
| 7 | 结果分类与报告：code_defect / business_data / framework_behavior / environment 分层 |

### 维度 2：不确定性与失败点

| 失败点 | 触发条件 | 根因 | 修复 |
|--------|----------|------|------|
| 技能名误用 | 用户调用 `/xianyu-auto-testing`（属另一产品） | 技能不存在于本工作区 | 纠正为 `news-auto-testing` 并说明 |
| pytest 无此模块 | 用 managed venv（3.13.12）跑 pytest | 项目 pytest 装在 `backend/.venv` | 切到 `backend/.venv/Scripts/python.exe -m pytest` |
| 路由顺序误匹配 | catch-all 路由先于具体路由注册 | Playwright 按注册顺序匹配 | 具体路由前置 |
| 沙箱 safe-delete 崩溃 | Playwright 清理旧 `test-results` | 沙箱禁止删除保护 | 唯一 `--output` 目录 |
| 打包模式假阴性 | 仅 dev 模式测试 | 未识别服务模式 | 服务模式自动检测 + exe 模式专项断言 |

### 维度 3：可抽象的固定流程与判断逻辑

```
前端 E2E 路由 mock 注册顺序（判断信号）：
  grep 路由注册：具体路由（含 {id}）必须在 **/admin/api/v1/workflows* 之前
  → Playwright 按注册顺序匹配，catch-all 在前会吞掉具体路由

Playwright 沙箱安全删除规避（判断信号）：
  grep 启动脚本是否清理 test-results
    → 沙箱会拦截删除 → 改用 --output=test-results-<timestamp> 唯一目录

测试环境 Python 选择（判断信号）：
  grep 测试命令是否用 python -m pytest 且无显式路径
    → 项目 pytest 在 backend/.venv → 显式路径调用
```

### 维度 4：适用场景与不适用场景

| 流程 / 判断逻辑 | 适用场景 | 不适用场景 |
|------------------|----------|------------|
| 路由顺序前置 | 任何带 `{param}` 具体路由 + catch-all 的 Playwright mock | 无 catch-all 的纯具体路由 |
| 唯一 output 目录 | 沙箱/CI 中 Playwright 启动清理触发保护 | 本地无删除保护限制 |
| 服务模式自动检测 | dev/exe/docker 多模式项目测试 | 单模式项目 |
| 显式 Python 路径 | 多 Python 环境、pytest 装在指定 venv | 全局唯一 python 且已装 pytest |

---

## 三、本次沉淀的新编码标准（已整合进 news-code-dev / 审查技能）

| 编号 | 标准 | 优先级 | 对应审查维度 |
|------|------|--------|--------------|
| R186 | 打包模式路径解析：exe 模式 COS 双写缺失须配置驱动检测 | CRITICAL | 后端维度 136 |
| R187 | 外部存储列表回退：本地空须回退 DB 持久化远程 URL | CRITICAL | 后端维度 136 |
| R188 | 同步 SDK 异步安全：async 路由内同步 SDK 须 `to_thread` | CRITICAL | 后端维度 137 |
| R189 | 二进制流式响应契约：音频/文件须原始 `StreamingResponse` | HIGH | 后端维度 138 |
| R190 | 音频代理 SSRF 防护：代理外部 URL 须域名白名单 | CRITICAL | 后端维度 139 |
| R191 | 字段契约(size_bytes/远程 path)：远程 path 语义化、size_bytes=0 须前端正确展示 | HIGH | 后端维度 136 / 前端维度 122 |
| R192 | 详情面板懒加载：activePanels + 变更处理器按需加载 | HIGH | 前端维度 119 |
| R193 | 远程音频代理播放：远程音频走 proxy 端点，禁直连 COS | HIGH | 前端维度 120 |
| R194 | 远程资源删除保护：远程存储项禁用删除/本地操作 | HIGH | 前端维度 121 |
| R195 | 字段契约展示：size_bytes / 远程 path 标签正确展示 | MEDIUM | 前端维度 122 |

详细规则与 grep 判断信号见 [lessons-learned.md](lessons-learned.md) 规范 73–82，配置项见 [config/project-config.json](config/project-config.json)（`packaging_mode_storage` / `external_storage_list_fallback` / `binary_response_contract` / `audio_proxy_ssrf` / `detail_panel_lazy_load`）。
