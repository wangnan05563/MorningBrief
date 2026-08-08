---
name: "news-backend-code-review"
description: "对 MorningBrief 项目后端代码（backend/app/ 下 Python/FastAPI/SQLAlchemy 文件）进行全面评审与逻辑审查，覆盖分层架构、异步并发、数据库规约、安全、性能、错误处理、配置驱动、前后端字段契约、工作流编排、缓存一致性等维度。当用户要求'审查/检查/走查/把关/review/评估/看看对不对/规范不规范'后端 Python 代码、'.py 文件修改'、'迭代发布前后端走查'，或提到'后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审'时调用。仅审查后端 .py 文件；纯前端文件审查请改用 news-frontend-code-review。"
whenToUse: "需要审查 MorningBrief 后端代码（backend/app/ 下 .py 文件）是否符合项目规范"
triggers: "后端代码 走查/审查/审核/把关/review/检查/评估 | .py 文件 修改/变更/迭代 走查 | 迭代发布前 后端 代码 走查 | 这段后端代码 写得对不对/规范不规范 | 路由/服务/模型/工作流 代码 审查"
version: "3.2.0"
updated: "2026-08-08"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 后端代码审查

## 简介

本技能对 MorningBrief 项目后端代码（`backend/app/**/*.py`）进行系统性评审，覆盖 **149+ 个审查维度**：分层架构、命名规范、类型注解、FastAPI 规范、SQLAlchemy 2.0 规范、异步并发、缓存规约、安全、错误处理、配置驱动、工作流编排、字段契约、日志规范、性能、可测试性、外部服务降级、多 Provider 架构、TTS 语速联调、频道配置、定时任务、数据回填等。

适用技术栈：FastAPI + SQLAlchemy 2.0 async + aiomysql（或 aiosqlite）+ Redis（或 TTLCache）+ APScheduler + httpx + COS + 阿里云 TTS + 通义千问 LLM。

## 核心原则：配置驱动

**所有评审规则、阈值、白名单、关键字均通过 `config.yaml` 管理，技能本身不含任何硬编码业务值。**

主要配置节点：
- 评审范围与优先级 → `scope` / `priority`
- 硬约束规则 → `hard_constraints.rules`
- 维度开关 → `checklist` / `review_dimensions`
- 编码规范阈值 → `coding_standards`
- 工作流容错与降级 → `image_crawl_check` / `fallback_days_check` / `llm_semantic_fallback_check` / `llm_word_count_check` / `bgm_fallback_check`
- 监控告警 → `monitoring_thresholds_check` / `channel_health_dashboard_check` / `rss_reachability_check`
- 数据迁移与回填 → `backfill_script_check`

当 `config.yaml` 缺失时，使用 `config.example.yaml` 兜底。

## 审查模式

| 模式 | 触发方式 | 范围 | 适用场景 |
|------|----------|------|----------|
| 快速自检 | 运行 `scripts/auto-scan.ps1` | 全量 .py | 提交前预检阻塞级问题 |
| 增量审查 | git diff 比对变更文件 | 变更文件 | 日常迭代、PR 走查 |
| 指定文件审查 | 用户给出路径 | 指定文件 | 单文件深度审查 |
| 片段评审 | 用户粘贴代码片段 | 片段 | 即时反馈、Chat 模式 |
| 全量审查 | 扫描 `backend/app/**/*.py` | 全量 | 发版前走查、技术债盘点 |

**维度覆盖**：维度 1-15（核心）+ A-I（补充）默认全模式覆盖；维度 16-149 按需激活（全量审查和增量审查默认覆盖，片段评审仅在代码涉及相关主题时触发）。

## Input / Output 契约

### Input
- **必填**：审查范围（文件路径列表 / git diff / 代码片段）
- **可选**：审查模式（不指定时根据上下文自动选择）

### Output
- 报告文件：按 `templates/report-template.md` 格式输出到审查结果目录
- 控制台摘要：问题总数、各级别统计、阻塞项清单

## 审查流程

1. 读取 `config.yaml`，确认 scope 与开启的维度
2. 按模式收集待审查文件
3. 运行 `scripts/auto-scan.ps1` 预检阻塞级问题
4. 按核心维度 1-15 逐项审查
5. 按补充审查要点 A-I 逐项审查
6. 检查 SonarQube 规则交叉引用
7. 检查 SSE 安全端点（如项目涉及）
8. 按需激活扩展维度 16-149（参见 [dimensions.md](references/dimensions.md)）
9. 汇总结果填入 `templates/report-template.md`
10. 输出修复建议

## 失败处理

| 失败场景 | 判断信号 | 处理方式 |
|----------|----------|----------|
| config.yaml 缺失 | 启动时文件不存在 | 回退 config.example.yaml + WARN |
| 审查范围无文件 | git diff 为空或无匹配 .py | 退出码 0，输出"无变更文件" |
| 维度配置缺失 | config.yaml 对应节点为 null | 跳过该维度 + WARN |
| 硬约束命中 | Grep 扫描命中阻塞级 pattern | 标记 CRITICAL，阻止通过 |
| py_compile 失败 | 修复后语法错误 | 回滚修改，标记失败 |
| pytest 失败 | 修改破坏现有测试 | 回滚修改或修复测试 |

## 核心审查维度

> 下表为精简概览，每个维度的完整规则（检查项、判断信号、代码示例）见 [references/dimensions.md](references/dimensions.md)。

### 维度 1-15（默认全开）

| 编号 | 维度 | 关键检查点 | 严重级别 |
|------|------|-----------|----------|
| 1 | 分层架构 | routers→services→models→core 单向依赖；路由层禁业务逻辑 | CRITICAL |
| 2 | 命名规范 | snake_case/PascalCase；Service 类后缀；Router 前缀 | HIGH |
| 3 | 类型注解 | Python 3.11+ 语法；禁 Optional/List/Dict；函数签名完整 | HIGH |
| 4 | FastAPI 规范 | APIRouter 前缀；Pydantic Body 验证；success() 包装；Depends 注入 | CRITICAL |
| 5 | SQLAlchemy 2.0 | DeclarativeBase+Mapped；异步 session；禁旧式 Column；枚举 .value | CRITICAL |
| 6 | 异步并发 | async def 含 await；create_task 保留引用；禁同步 IO 阻塞 | CRITICAL |
| 7 | Redis 缓存规约 | cache-aside 模式；key 命名 `域:操作:参数`；Lua 原子操作 | HIGH |
| 8 | 安全 | JWT hmac.compare_digest；bcrypt 哈希；黑名单；参数化查询；敏感词初始化 | CRITICAL |
| 9 | 错误处理 | BizError 体系；禁覆盖内置异常；logger.exception() 保留 traceback；禁裸 except+pass | CRITICAL |
| 10 | 配置驱动 | 走过 settings 禁 os.getenv；禁硬编码 URL/密钥/TTL；禁明文凭据 | HIGH |
| 11 | 工作流编排 | 单实例锁；步骤状态机；失败重试+告警；finally 锁保护 | CRITICAL |
| 12 | 前后端字段契约 | ORM 字段名=API 字段名；枚举 .value；datetime ISO 格式；字段名一致 | CRITICAL |
| 13 | 日志规范 | logging.getLogger；禁 print()；异常用 logger.exception()；含上下文 | HIGH |
| 14 | 性能 | 分页 limit+offset；禁 N+1；joinedload；批量操作；WAL 模式 | HIGH |
| 15 | 可测试性 | Service 方法独立可测；mock 外部服务；conftest fixture；AsyncMock | MEDIUM |

### 补充审查要点（A-I）

| 编号 | 要点 | 关键检查点 | 严重级别 |
|------|------|-----------|----------|
| A | PriorityQueue 取消任务 | QueueEntry 含 cancelled 标记；id→entry 索引 | HIGH |
| B | Semaphore 管理 | try/finally 释放；_config_dirty 延迟重建；唤醒旧等待者 | HIGH |
| C | SQLite VACUUM | AUTOCOMMIT 隔离级别；禁在事务内 | HIGH |
| D | COS 同步幂等 | INSERT OR IGNORE + object_key 唯一约束 + 删除源对象 | HIGH |
| E | 文件上传校验 | Content-Type + 大小限制 | CRITICAL |
| F | 强制发布 | require_admin 权限 + 审计日志 | CRITICAL |
| G | V2.0 综合新增 (D91-100) | 封面 fallback / FALLBACK_DAYS / LLM 语义 fallback / 字数约束 / BGM 兜底 / 监控 / 健康度 / RSS 巡检 / 回填 / PWA | CRITICAL |
| H | V2.1 外部降级 (D113-115) | COS 降级本地存储 / WinError 10054 过滤 / 本地路径 URL | HIGH |
| I | V2.2 时区+dedup (D142-149) | func.now() 禁用 / dedup 联动清理 / 回溯 fallback / PowerShell r-string / DB 诊断 | CRITICAL |

### 扩展维度概览（16-149，按需激活）

| 编号范围 | 分组 | 代表维度 | 详细规则 |
|----------|------|----------|----------|
| 16-25 | 外部服务与配置 | 异常分类、配置一致性、批量诊断、路由优先级、时长约束 | [dimensions.md](references/dimensions.md#扩展维度16-149按需激活) |
| 26-28 | 模型名称与定价 | 第三方模型名、定价表同步、配置键一致 | 同上 |
| 29-32 | 批量删除与事务 | 事务原子性、权限校验、上限约束 | 同上 |
| 33-37 | 启动脚本与日志 | 路径空格、构建并发、日志格式、FFmpeg 依赖 | 同上 |
| 38-49 | 时区与数据对齐 | 时区一致性、级联清理、0 结果容错、动态注入、频道覆盖 | 同上 |
| 50-53 | 模型字段验证 | 字段名验证、统计口径、URL 配置化、Favorite 类型 | 同上 |
| 54-58 | 频道与 RSS 管理 | 数据隔离、RSS 同步、第三方依赖诊断、PowerShell 兼容 | 同上 |
| 59-62 | 模板与密钥 | 花括号转义、API Key 脱敏、错误码映射、Settings 同步 | 同上 |
| 63-72 | 数据库维护 | Inspector陷阱、导入完整性、敏感脱敏、级联删除、VACUUM、审计日志 | 同上 |
| 73-80 | SonarQube 规则 | 认知复杂度、async/await 验证、正则优化、未使用变量、数据驱动 | [dimensions.md](references/dimensions.md) |
| 81-83 | 小程序数据流 | cache_key 版本、segments 完整性、响应字段优先级 | 同上 |
| 84-88 | SonarQube 闭环 | NOSONAR 位置、扫描兼容性、并行核查、stash 验证、抑制决策 | 同上 |
| 89-90 | 跨项目迁移 | 单例缓存隔离、多版本 Python 测试执行 | 同上 |
| 91-100 | V2.0 综合 | 封面三级 fallback→FALLBACK_DAYS→LLM fallback→字数约束→BGM→监控→健康度→RSS→回填→PWA | 同上 |
| 101-105 | 小程序真机 | list 批量关联、聚合序号、CommentRequest 可选、play_count 批量、cache_key | 同上 |
| 106-112 | TTS 多 Provider | 抽象基类+注册表、降级链、凭证fallback、版本预检、TC3签名、类型转换、三层防护 | 同上 |
| 113-115 | 外部存储降级 | COS→本地降级、WinError过滤、本地路径URL | 同上 |
| 116-118 | SSE/静态文件 | SSE 断开检测、推送安全、静态文件 autofocus、诊断日志 | 同上 |
| 119-123 | AI 配置持久化 | Body 字段完整性、配置键一致性、时间本地化、预设JSON、恢复端点 | 同上 |
| 124-129 | 后端高频故障 | FileResponse 拦截器、工作流重跑语义、config_key 映射、时间基线、外键、凭证脱敏 | 同上 |
| 130-132 | 功能移植 | 函数对称性、服务重启验证、移植适配 | 同上 |
| 133-135 | 频道级配置 (V2.2) | LLM 超时公式化、频道覆盖全局、事件驱动 cron | 同上 |
| 136-141 | V2.8 三参数联动 | 配置全链路、估算联动、动态范围、错误诊断、双重验证、语速反算 | 同上 |
| 142-149 | 时区+dedup+fallback | func.now()禁用、dedup联动清理、回溯fallback、PowerShell、表结构预检、DB锁诊断、stitch兜底、时间显式赋值 | 同上 |
| J-P | V2.9 历史复盘 | Settings单例导入、测试断言对齐、文件上传安全、IntegrityError兜底、0结果阻断、编码探测、风格轮换 | 同上 |

## SonarQube 规则号交叉引用

| SonarQube 规则 | 审查维度 | news-code-dev 规范 | 严重级别 | 修复建议 |
|---------------|---------|-------------------|---------|----------|
| S7503 | 维度 74 | S52/R67 | CRITICAL | 转同步函数或补充 await |
| S6395 | 维度 75 | S53/R68 | WARNING | 改用非捕获组 `(?:...)` |
| S7504 | 维度 76 | S54/R69 | WARNING | 去掉多余 list() 转换 |
| S1481 | 维度 77 | S55/R70 | CRITICAL | 删除未使用变量/参数 |
| S1128 | 维度 78 | S55/R70 | WARNING | 删除未使用导入 |
| S2486 | 维度 80 | S59/R74 | WARNING | 添加日志或注释 |
| cognitive_complexity | 维度 73 | S51/R66 | CRITICAL | 抽取辅助函数或数据驱动重构 |
| - | 维度 79 | S56/R71 | SUGGESTION | 重构为 list[tuple] + 循环 |

## SSE 安全报告

> 如项目包含 SSE 端点，审查时生成以下诊断清单。

### SSE 端点清单
| 端点路径 | 文件位置 | 断开检测 | 推送频率 | 内容安全 | 心跳机制 |
|----------|----------|----------|----------|----------|----------|
| /api/sse/workflow | routers/sse.py:45 | ✓ | 1000ms | ✓ | 30s |
| /api/sse/notification | routers/sse.py:120 | ✗ | 无限制 | ✓ | 无 |

### 静态文件安全
| 文件路径 | autofocus | window.focus | location.href | 状态 |
|----------|-----------|--------------|---------------|------|
| admin-web/dist/index.html | ✗ | ✗ | ✗ | 通过 |
| admin-web/public/404.html | ✓ | ✗ | ✗ | 违规 |

### 诊断日志完整性
| 端点 | 客户端 IP | User-Agent | 请求上下文 | 生命周期日志 |
|------|-----------|------------|------------|--------------|
| /api/sse/workflow | ✓ | ✓ | ✓ | ✓ |
| /api/sse/notification | ✗ | ✗ | ✓ | ✗ |

### 修复建议优先级
1. [CRITICAL] SSE 端点无断开检测（资源泄漏风险）
2. [HIGH] 静态 HTML 含 autofocus（窗口激活风险）
3. [HIGH] SSE 推送频率无上限（UI 更新触发风险）
4. [MEDIUM] SSE 日志缺少客户端信息（诊断困难）
5. [MEDIUM] SSE 无心跳机制（长连接稳定性风险）

## 参考

- [dimensions.md](references/dimensions.md) — 所有审查维度的完整定义（检查项、判断信号、代码示例、严重级别）
- [_shared/references/](../_shared/references/) — 跨技能共享主题（安全基线的 OWASP 规则、SonarQube 通用规则等）

---

## V3.0 2026-08-05 会话复盘新增审查维度（维度 196-204）

> 来源：2026-08-05 会话中解决的真实问题（频道静音误判、AI 用量全 0、异常吞没、CancelledError 逃逸、fire-and-forget 泄漏、构建元数据失真、重命名泄漏、测试隔离泄漏、安装包图标）；另含 2026-08-05 第二轮：PyInstaller frozen 配置加载失败（DS-11）、安装包 `.env` 被 `Excludes` 静默丢弃（DS-12）。
> 对应 news-code-dev 诊断标准 DS-1~DS-14（详见 news-code-dev `references/diagnostic-standards.md`）。
> 所有规则参数通过 `config.yaml` 对应节点管理，技能本身不含硬编码业务值；报告中违规条目标注 `[V3.0 新增]` 便于追溯。

| 维度 | 审查项 | 严重级别 | 对应 DS | 配置节点 |
|------|--------|----------|---------|----------|
| 196 | 异常吞没 / traceback 保留：`except` 块仅 `str(e)` 无 `exc_info`；子进程/SDK 启动异常未转专用异常 | HIGH | DS-1 | `exception_swallow_check` |
| 197 | CancelledError 逃逸防护：`wait_for`/`create_task` 包裹函数 `except Exception` 前无 `except asyncio.CancelledError` | CRITICAL | DS-2 | `cancelled_error_guard_check` |
| 198 | fire-and-forget 保活与守卫：同步函数内 `create_task` 无模块级集合保活 / 无 `get_running_loop` 守卫 / 测试未禁用 | HIGH | DS-3 | `fire_and_forget_keepalive_check` |
| 199 | 构建/发布元数据单一真相源：`_build_info.py` 硬编码 `git_sha="unknown"`/`build_date`；生成器未被构建/发布脚本调用 | HIGH | DS-6 | `build_metadata_single_source_check` |
| 200 | 全量重命名/别名移除完整性：删除/重命名公共 API 后 grep 旧名非零匹配；矛盾注释未清理 | CRITICAL | DS-8 | `alias_rename_completeness_check` |
| 201 | 测试隔离与状态防泄漏：依赖模块级文件路径/单例的测试依赖 `unlink()` 成功，未重定向 `tmp_path` | HIGH | DS-9 | `test_isolation_safe_delete_check` |
| 202 | 安装包/构建配置完整性：`installer.iss` 缺 `SetupIconFile`；spec 与 iss 模板不一致 | MEDIUM | DS-10 | `packaging_config_completeness_check` |
| 203 | frozen 模式配置加载路径解析：`config.py` 的 `env_file` 为相对/固定路径、未用 `sys.executable` 同级解析（`sys.frozen` 时 `_MEIPASS` 无 `.env`） | CRITICAL | DS-11 | `frozen_config_load_check` |
| 204 | 安装包配置完整性：`installer.iss` 的 `Excludes` 含 `.env`/密钥、或 `Source:` 未显式包含 `.env`、构建脚本未 `attrib -H` | CRITICAL | DS-12 | `installer_secret_completeness_check` |

### 审查结果呈现优化（V3.0）

为提升审查结论的可执行性，报告（`templates/report-template.md`）在 V3.0 做以下增强：

1. **问题定性分层**：每条问题必须标注 `真缺陷 / 误报 / 环境制品` 三类之一。
   - 真缺陷：违反硬约束或明确反模式，需代码修复。
   - 误报：grep 信号命中但人工确认非问题（如 `from app.config import get_settings` 触发 `os_getenv_direct` 误报），须记录 `false_positive_hints` 理由。
   - 环境制品：safe-delete 拦截 teardown、`test_ai_budget` 的 `unlink` 残留等，与改动无关，报告单独归类并注明"非代码失败"。
2. **适用/不适用场景字段**：每条问题补充 `适用场景` 与 `不适用场景`（取自 DS 标准维度 4），避免把单测专用规则误用于不同上下文。
3. **严重级别判定理由**：阻塞级（CRITICAL）必须写明"为什么阻塞"（如 CancelledError 逃逸导致静默失败不可观测），而非仅给标签。
4. **与整体工作流一致**：审查发现的每条规则须能在 `config.yaml` 找到对应节点（无硬编码新增）；修复建议优先指向 news-code-dev 的 DS 标准与 meta-rules 编号。

## V3.1 2026-08-05 段间静音/bgm_gap_mode 复盘新增审查维度（维度 205-206）

> 来源：段间静音"看似无效"根因（bridge 模式让 BGM 在段间连续叠加、`amix` 把静音段淹没）→ 真静音 `amix=inputs=2:duration=first` → 可开关 `bgm_gap_mode`(silence/bridge) + 全局默认/频道覆盖双路径 + 幂等迁移；以及校验器/测试语义错位（空串抛 `ValueError` 但测试期望 `None` 继承）。
> 对应 news-code-dev 诊断标准 DS-15 / DS-16（详见 news-code-dev `references/diagnostic-standards.md`）。
> 所有规则参数通过 `config.yaml` 对应节点管理，技能本身不含硬编码业务值；报告中违规条目标注 `[V3.1 新增]` 便于追溯。

| 维度 | 审查项 | 严重级别 | 对应 DS | 配置节点 |
|------|--------|----------|---------|----------|
| 205 | 媒体特性可开关化：媒体开关字段须有 silence/bridge 双模式，且"静音"实现真静音（`amix=inputs=2:duration=first`，仅主音频有声时叠加 BGM） | HIGH | DS-15 | `bgm_gap_mode_check` |
| 205 | 全局默认/频道覆盖双路径：`channel.x or settings.X`（非 None 覆盖全局，None 继承），不得写死单一来源 | HIGH | DS-15 | `bgm_gap_mode_check.channel_override` |
| 205 | 新增列幂等迁移：`PRAGMA table_info` 检测后 `ALTER TABLE ADD COLUMN` | HIGH | DS-15 | `bgm_gap_mode_check.idempotent_migration` |
| 206 | 枚举/开关字段校验器语义：空串/`None`→继承 `None`；去空格后合法值→归一化；其余→`ValueError` | HIGH | DS-16 | `validator_semantic_check` |
| 206 | 校验器行为与测试断言一致：测试期望 `None` 时不得抛错；期望抛错时必须拒绝（避免语义错位导致单测失败或放宽校验） | HIGH | DS-16 | `validator_semantic_check.test_alignment` |
