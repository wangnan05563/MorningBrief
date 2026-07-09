---
name: "xianyu-hunter-dev"
description: "闲鱼猎人（XianyuHunter）项目增量功能开发、Bug 修复、代码重构、测试编写与架构改造的标准化开发技能，严格遵循项目四层分层架构（domain → infra → modules → web）、异步并发模型与编码规范。当用户要求在闲鱼项目里'写/做/添加/实现/新增/修改/重构/优化/修复/对接'功能、接口、页面、组件、Hook、路由、仓储、调度器、配置、数据库迁移时调用。注意：纯代码评审出报告请改用 xianyu-backend-code-review 或 xianyu-frontend-code-review；服务启停请改用 xianyu-automation-startserver。"
whenToUse: "用户要求在闲鱼猎人项目（d:/code/otherProjects/17_xianyu）进行任何代码层面的开发/修改/重构/修复/测试编写工作，包括后端 Python/FastAPI 代码、前端 React/TS 代码、数据库迁移、配置文件、调度器、API 接口实现"
triggers:
  - "在 闲鱼/闲鱼猎人/XianyuHunter 项目 写/做/添加/实现/新增/开发 一个 功能/接口/页面/组件"
  - "修复/解决 闲鱼/XianyuHunter bug/问题/缺陷/报错/异常"
  - "闲鱼 项目 重构/优化/改造/升级 现有代码"
  - "闲鱼 项目 编写 测试/路由/仓储/Hook/组件/页面/调度器"
  - "闲鱼 项目 配置 config.yaml/.env/部署/Docker"
  - "闲鱼 项目 实现/对接 注册式资源三件套（菜单+路由+页面+API+后端）"
  - "闲鱼 项目 涉及 数据库迁移/索引/SQLAlchemy 模型"
  - "闲鱼 项目 涉及 调度器/后台任务/定时任务/APScheduler"
  - "闲鱼 项目 涉及 智能客服/RAG/Agent/向量库"
version: "4.38.0"
updated: "2026-07-08"
config: "config/tech-stack.json"
---


# 闲鱼猎人个性化开发 Skill

## Skill 职责

本 Skill 用于闲鱼猎人（XianyuHunter）项目的个性化开发，遵循项目四层分层架构（domain → infra → modules → web）、异步并发模型与 SonarQube 代码质量规范，提供标准化的开发流程、代码模板与参考知识库。

## 项目背景速查

| 项 | 值 |
|---|---|
| 项目代号 | XianyuHunter / 闲鱼猎人 |
| 当前版本 | 0.3.0（SemVer） |
| 项目根 | `d:\code\otherProjects\17_xianyu` |
| 后端入口 | `src/xianyu_hunter/__main__.py`（Typer CLI） |
| Web 入口 | `src/xianyu_hunter/web/app.py`（FastAPI 工厂） |
| 前端入口 | `frontend/src/main.tsx`（React 18 + Vite） |
| 配置文件 | `config/config.yaml` + `config/eval.yaml` + `.env` |
| 数据库 | SQLite（WAL）+ ChromaDB（向量库） |
| 部署 | Docker 三阶段构建 / Windows bat / Linux systemd |
| 单元测试 | 148/148 通过（pytest + vitest） |

## 技术栈速查

| 类别 | 技术 | 版本 |
|---|---|---|
| 后端语言 | Python | >=3.10（Docker 3.12-slim） |
| Web 框架 | FastAPI | 0.136.3 |
| ASGI | uvicorn[standard] | 0.48.0 |
| CLI | typer | 0.26.6 |
| ORM | SQLAlchemy | 2.0.50（DeclarativeBase + Mapped） |
| 数据验证 | pydantic | 2.13.4 |
| 配置 | pydantic-settings | 2.14.1 |
| 浏览器自动化 | Playwright | 1.60.0 |
| HTTP | httpx 0.28.1 / aiohttp 3.14.0 | - |
| 调度 | APScheduler | 3.11.2 |
| 日志 | loguru | 0.7.3 |
| 密钥 | keyring | 25.7.0（Windows DPAPI） |
| 重试 | tenacity | 9.1.4 |
| 加密 | cryptography | 49.0.0（Chrome Cookie AES-256-GCM） |
| 向量库 | chromadb | >=1.0.0 |
| 测试 | pytest 9.0.3 / pytest-asyncio 1.4.0 | - |
| 前端语言 | TypeScript | ^5.5.0 |
| 前端框架 | React | ^18.3.1 |
| UI 库 | Ant Design | ^5.21.0 |
| 状态管理 | Zustand | ^4.5.0 |
| 路由 | react-router-dom | ^6.26.0 |
| HTTP | axios | ^1.7.0 |
| 图表 | echarts | ^5.5.0 |
| 拖拽 | @dnd-kit/core | ^6.1.0 |
| 构建 | Vite | ^5.4.0 |
| PWA | vite-plugin-pwa | ^1.3.0 |
| 测试 | Vitest | ^4.1.9 |

详细版本与依赖关系参见 [config/tech-stack.json](config/tech-stack.json)。

## 文档结构

```
xianyu-hunter-dev/
├── SKILL.md                          # 本文件 - Skill 定义（精简版，编码规范已归档）
├── README.md                         # 使用说明
├── config/
│   └── tech-stack.json               # 技术栈版本、路径与硬约束配置
├── assets/
│   ├── guides/
│   │   ├── frontend-guide.md         # 前端开发指南（React/TS/AntD/Zustand）
│   │   ├── backend-guide.md          # 后端开发指南（FastAPI/SQLAlchemy/async）
│   │   ├── database-guide.md         # 数据库开发指南（SQLite/索引/迁移）
│   │   ├── chatbot-guide.md          # 智能客服开发指南（RAG/Agent/KB）
│   │   ├── sonarqube-rules-guide.md  # SonarQube 规则速查（16+ 条规则 + 复盘）
│   │   └── coding-rules/             # 🆕 编码规范归档（178 step 按主题分 13 文件）
│   │       ├── _step-index.md        # step 索引表（主题速查 + step 编号查找）
│   │       ├── _step-index.json      # step→topic 映射（机读）
│   │       ├── security.md           # 安全（token/脱敏/SQL注入）
│   │       ├── concurrency.md        # 并发（asyncio/锁/超时/降级）
│   │       ├── state-management.md   # 状态管理（一致性/同步/生命周期）
│   │       ├── error-handling.md     # 错误处理（粒度/重试/dump）
│   │       ├── database.md           # 数据库（迁移/索引/SQLite）
│   │       ├── config-driven.md      # 配置驱动（功能开关/全链路）
│   │       ├── frontend-ui.md        # 前端 UI（AntD/状态/三态）
│   │       ├── testing.md            # 测试（隔离/mock/fixture）
│   │       ├── scheduler.md          # 调度器（APScheduler/启动可见）
│   │       ├── llm-ai.md             # LLM/AI（响应解析/能力派发）
│   │       ├── browser-automation.md # 浏览器自动化（Playwright/Cookie）
│   │       └── general-engineering.md # 通用工程（注释/复用/现代化）
│   └── templates/                    # 代码模板
│       ├── python/
│       │   ├── route.py              # FastAPI 路由模板
│       │   ├── repository.py         # 仓储 Mixin 模板
│       │   └── domain.py             # 领域模型模板
│       └── typescript/
│           ├── api.ts                # API 模块模板
│           ├── hook.ts               # 自定义 Hook 模板
│           └── store.ts              # Zustand store 模板
└── references/                       # 参考文档
    ├── project-rules.md              # 项目硬约束（强制规则）
    ├── architecture-patterns.md      # 架构模式知识库
    ├── meta-rules.md                 # 🆕 元规范（63 条：20 条通用规则 + 43 条工作流模板规则）
    ├── version-history.md            # 🆕 版本历史（v4.14.0 → v4.27.0 复盘）
    ├── faq.md                        # 常见问题与最佳实践
    └── ...                           # 其他专题参考文档
```

## 开发规范文档

本 Skill 遵循分层加载策略：主文件仅保留流程，编码规范按需从主题文件加载。

### 分领域开发指南

| 领域 | 文档 | 内容 |
|---|---|---|
| 前端 | [frontend-guide.md](assets/guides/frontend-guide.md) | 命名约定、组件设计、Hook 模式、Zustand store、AntD 主题、PWA、SonarQube 规则 |
| 后端 | [backend-guide.md](assets/guides/backend-guide.md) | 分层架构、路由/仓储/领域模型模板、异步并发、安全约束、错误处理 |
| 数据库 | [database-guide.md](assets/guides/database-guide.md) | SQLite 引擎配置、表设计、索引策略、幂等迁移、SQLAlchemy 2.0 风格 |
| 智能客服 | [chatbot-guide.md](assets/guides/chatbot-guide.md) | RAG 引擎、Agent 工具调用、KB 管理、向量存储、降级链 |
| SonarQube | [sonarqube-rules-guide.md](assets/guides/sonarqube-rules-guide.md) | 16+ 条规则详解、修复模式、实战案例、复盘总结 |

### 编码规范（188 step 按主题归档）

> **按需加载策略**：AI 根据当前任务主题加载对应文件，避免一次性加载 188 step 全量内容。

| 主题文件 | 内容 | step 数 | 适用场景 |
|---|---|---|---|
| [security.md](assets/guides/coding-rules/security.md) | token 校验/脱敏/SQL注入/外部链接 | 13 | 涉及认证、加密、外部 API |
| [concurrency.md](assets/guides/coding-rules/concurrency.md) | asyncio/锁/超时/降级 | 9 | 涉及异步、并发、后台任务 |
| [state-management.md](assets/guides/coding-rules/state-management.md) | 一致性/同步/生命周期 | 20 | 涉及状态机、缓存、跨组件同步 |
| [error-handling.md](assets/guides/coding-rules/error-handling.md) | 粒度/重试/dump/原因传递 | 19 | 涉及错误处理、重试、诊断 |
| [database.md](assets/guides/coding-rules/database.md) | 迁移/索引/SQLite | 11 | 涉及 DB schema 变更、迁移 |
| [config-driven.md](assets/guides/coding-rules/config-driven.md) | 功能开关/全链路/阈值/字段契约 | 21 | 涉及配置项、参数管理、字段对齐 |
| [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) | AntD/状态/三态/类型对齐 | 28 | 涉及 React 组件、UI 交互 |
| [testing.md](assets/guides/coding-rules/testing.md) | 隔离/mock/fixture/Windows 编码 | 9 | 涉及测试编写、mock 数据、跨平台 |
| [scheduler.md](assets/guides/coding-rules/scheduler.md) | APScheduler/启动/状态可见 | 14 | 涉及后台调度、定时任务 |
| [llm-ai.md](assets/guides/coding-rules/llm-ai.md) | 响应解析/能力派发/降级 | 4 | 涉及 LLM 调用、多模态 |
| [browser-automation.md](assets/guides/coding-rules/browser-automation.md) | Playwright/Cookie/子进程 | 13 | 涉及浏览器自动化、Cookie 管理 |
| [general-engineering.md](assets/guides/coding-rules/general-engineering.md) | 注释/复用/现代化/死代码/事件过滤/重启验证/修复协议/字段契约/列表聚合/联动开关/precheck结构化/配置兜底 | 37 | 通用编码规范 |

**完整 step 索引**（按 step 编号查找归档位置）：参见 [编码规范索引](assets/guides/coding-rules/_step-index.md)

### 元规范与历史

| 文档 | 内容 |
|---|---|
| [meta-rules.md](references/meta-rules.md) | 🆕 63 条元规范（20 条通用规则 + 43 条工作流模板规则，覆盖错误处理/熔断/资源/状态同步/数据契约/注册式资源/规范治理/列表聚合/跨层契约/调度器治理/工程闭环/异步与资源安全） |
| [version-history.md](references/version-history.md) | 🆕 版本历史（v4.14.0 → v4.27.0 各版本复盘详情） |
| [project-rules.md](references/project-rules.md) | 项目硬约束（强制规则） |
| [architecture-patterns.md](references/architecture-patterns.md) | 架构模式知识库 |
| [faq.md](references/faq.md) | 常见问题与最佳实践 |

### 工作流元规范速查（meta-rules #21-65）🆕 v4.39.0

> 与「分领域开发指南」和「编码规范」不同，工作流元规范是**跨主题的高频判断逻辑**，适用于「任务执行 → 修复 → 沉淀」全流程。
>
> 详细配置节点与适用/不适用场景见 [`docs/standards/四维度复盘方法论与历史教训集成.md`](../../../../docs/standards/四维度复盘方法论与历史教训集成.md)。
>
> 🆕 v4.30.0 新增 6 条「数据契约与时序」维度元规范（#25-30）。🆕 v4.31.0 新增 2 条「状态恢复与日志降噪」维度元规范（#31-32）。🆕 v4.32.0 新增 3 条「注册式资源契约」维度元规范（#33-35）。🆕 v4.33.0 新增 2 条「规范治理」维度元规范（#36-37）。🆕 v4.34.0 新增 5 条「列表聚合与状态联动」维度元规范（#38-42）。🆕 v4.35.0 新增 5 条「跨层契约与测试同步」维度元规范（#43-47）。🆕 v4.36.0 新增 4 条「调度器运行时治理」维度元规范（#48-51）。🆕 v4.37.0 新增 5 条「工程闭环」维度元规范（#52-56），覆盖参数链闭环/模式纵向链路/外部页面解析容错/mock 同步/过滤结果透明化。🆕 v4.38.0 新增 7 条「异步与资源安全」维度元规范（#57-63），覆盖 async/await 同步性/资源池性能基准/HTTP 状态码精细化/CSS 选择器降级/异常日志语义/外部资源生命周期/数据库写入身份追溯。🆕 v4.39.0 新增 2 条 experimental 元规范（#64-65），覆盖 URL↔状态同步失败回退/SW 缓存版本同步。

| # | 元规范 | 一句话规则 | 关键判断信号 | 落地位置 |
|---|---|---|---|---|
| 21 | 错误处理决策树 | 关键路径必 `logger.exception()`，业务路径按 reason_code 三层 | `grep "except" <file>` 关键路径缺 `exception` | error-handling.md / B-REVIEW-CRITICAL-PATH-NO-SWALLOW |
| 22 | 批处理熔断模板 | 熔断必 `save_progress()`，剩余项标 pending，续传从 cursor 恢复 | `grep "consecutive failure" <file>` 无 `save_progress()` | scheduler.md / B-REVIEW-CIRCUIT-BREAKER-PERSIST |
| 23 | 资源生命周期 | Proxy/Observer/Task 必持实例属性，必 cleanup | `grep "new (Proxy\|MutationObserver\|IntersectionObserver\|ResizeObserver)"` 局部变量 | browser-automation.md / B-REVIEW-RESOURCE-CLEANUP-HOOK |
| 24 | 跨组件/跨源状态同步 🆕v4.29 | 前端：单一可信源 + 统一 refetch + SSE 推送（禁 TTL 兜底）；后端：YAML/keyring/EventRow/业务表多源必显式同步 | 前端：`grep "usePersistentState"` 但后端有 GET；后端：`grep "keyring"` 与 `grep "yaml"` 同凭据无 `_sync_` 函数 | state-management.md / F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND / B-REVIEW-BACKEND-MULTI-SOURCE-SYNC |
| 25 🆕v4.30 | 批量处理四要素 | 熔断必四要素齐备（失败计数+进度持久化+续传入口+日志对称），与用户停止分支对称 | `grep "consecutive failure"` 无 `save_progress()`，或 `grep "paused"` 实际 `break` 跳出 | scheduler.md / B-REVIEW-BATCH-CIRCUIT-BREAKER-4ELEMENTS |
| 26 🆕v4.30 | 关键路径异常保留 traceback | `_on_startup` / `run_migrations` / `_init_*` 外层 except 必用 `logger.exception()`，禁 `logger.warning(f"...{e}")` 丢堆栈 | `grep "logger.warning.*f\".*{e}\"\|logger.error.*f\".*{e}\""` 在关键路径 | error-handling.md / B-REVIEW-CRITICAL-PATH-EXCEPTION-LOG |
| 27 🆕v4.30 | datetime 统一时区策略 | 存储 UTC、算术前 unify tzinfo、序列化带 tzinfo；禁 `datetime.now()` 无 tzinfo 与 `utcnow()` | `grep "datetime.utcnow()"` 或 `grep "datetime.now()"` 无 `tzinfo` | general-engineering.md / F-REVIEW-DATETIME-RENDER-CONTRACT |
| 28 🆕v4.30 | 跨进程状态同步六步法 | 写端写状态+写 marker、同步器扫描、读端不读 marker、启动检查、异常保留 marker、配置驱动 | `grep "write_marker"` 无 `scan_marker` 配对，或启动函数无 `process_pending_markers` | state-management.md / B-REVIEW-MARKER-PROCESS-PAIRING |
| 29 🆕v4.30 | 前端错误按 error_code 分支 | 禁 substring 判断（`msg.includes('expired')`），用 `switch (err.error_code)`，前后端常量集中管理 | 前端：`grep "if.*message.includes"`，后端：响应缺 `error_code` 字段 | frontend-ui.md / F-REVIEW-ERROR-CODE-BRANCH |
| 30 🆕v4.30 | 业务关键字常量集中管理 | 业务关键字（已售/已删除/登录过期）禁散落代码，统一从 config/constants 读取，前端后端必须等价 | `grep "['\"](已售\|已删除\|宝贝不存在\|卖掉了)['\"]" <file>` 命中 | general-engineering.md / F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION |
| 31 🆕v4.31 | 状态恢复前置校验 | pause→resume 必校验根因消除，异常pause设冷却期，禁止无条件恢复 | grep "def resume\|def start\|def unpause" 缺 precheck | state-management.md / B-REVIEW-157 / F-REVIEW-116 |
| 32 🆕v4.31 | 多阶段降级链日志合并 | 同一逻辑链多阶段日志合并为1条结构化WARNING，中间步骤DEBUG化 | grep "logger.warning.*尝试\|刷新\|回退\|重试" 多条无合并 | error-handling.md / B-REVIEW-158 |
| 33 🆕v4.32 | 注册式资源三件套契约 | 菜单/路由/页面/API/后端五层必须齐备，任一层缺失=CRITICAL | `python scripts/check_registration.py` 全部路径必通过 | references/registration-completeness.md / B-REVIEW-159 / F-REVIEW-117 |
| 34 🆕v4.32 | 修复前全链路根因扫描 | 修复前先列≥3根因 + 修复后反查全链路 | `grep` 修过的关键 pattern 至少 3 处全部更新 | references/root-cause-protocol.md / B-REVIEW-160 / F-REVIEW-118 |
| 35 🆕v4.32 | 前后端字段契约单一可信源 | 后端 Pydantic/DB Row 为权威源，前端 types.ts 必须显式标注派生来源 | 后端字段变更但前端 types.ts 无对应注释更新 | references/contract-single-source.md / B-REVIEW-161 / F-REVIEW-119 |
| 36 🆕v4.33 | 规范沉淀门槛（防过度规范化） | ≥3 个相似 bug 才立规范，单一 bug 用 experimental 标签预沉淀，安全/数据丢失/付费受损豁免 | `grep "experimental" meta-rules.md` 标签超 1 季度未升级 → 废弃候选 | meta-rules.md #36 / B-REVIEW-162 / F-REVIEW-120 |
| 37 🆕v4.33 | 规范退化机制（防规范膨胀） | 利用率 < 3 次/季度则标记待合并/待废弃，1 季度观察期后废弃，安全类永不退化 | `grep "待废弃" meta-rules.md` 标记超 1 季度未处理 → 废弃流程卡住 | meta-rules.md #37 / B-REVIEW-163 / F-REVIEW-121 |
| 38 🆕v4.34 | 全局聚合任务级过滤 | 全局视图（无 task_id）列表查询必须按各任务个体配置范围过滤，禁止只用全局默认范围 | `grep "task_id.*None" <file>` 但无 `_filter_by_per_task` 调用 | general-engineering.md / B-REVIEW-164 / F-REVIEW-122 |
| 39 🆕v4.34 | 列表交叉数据批量注入 | 列表交叉其他数据源必须批量查询 + TTL 缓存，禁止 N+1 单条查询 | `grep "for.*in.*items:" <file>` 后跟 `db.query` 单条查询 | general-engineering.md / B-REVIEW-165 / F-REVIEW-123 |
| 40 🆕v4.34 | 多字段联动开关范式 | 联动字段必须声明「主开关→过滤器」优先级矩阵，主开关失效时子过滤器自动禁用 | `grep "mode.*notify\|mode.*auto_buy" <file>` 但无优先级矩阵注释 | general-engineering.md / B-REVIEW-166 / F-REVIEW-124 |
| 41 🆕v4.34 | 状态恢复前置校验结构化响应 | precheck 必须返回 5 字段结构化 dict 不抛异常，API 层直接透传 | `grep "def precheck_" <file>` 函数体内含 `raise` → 视为违规 | general-engineering.md / B-REVIEW-167 / F-REVIEW-125 |
| 42 🆕v4.34 | 配置化阈值兜底范式 | 从 config 读取的阈值必须有 try/except 兜底默认值，禁止配置缺失即崩溃 | `grep "get_config\(\)\.\w+\.\w+" <file>` 但无 `try.*except` 包裹 | config-driven.md / B-REVIEW-168 / F-REVIEW-126 |
| 43 🆕v4.35 | 事件多发布点字段对齐 | 业务事件在多层（worker/service/route/template）有发布点时，每处 payload 字段集必须一致 | `grep "<event_type>" src/` 命中 ≥2 处但 `grep "<required_field>"` 不全命中 → 字段未对齐 | meta-rules.md #43 / B-REVIEW-173（v4.35 待落地）/ F-REVIEW-131（v4.39 待落地） |
| 44 🆕v4.35 | 前端路由三重注册同步 | 新增路由必须同步注册 L1 App.tsx Route + L2 sheetRegistry + L3 useSheetSync | `git diff` 新增 `<Route>` 但 sheetRegistry 无对应条目 → L2 同步缺失 | meta-rules.md #44 / B-REVIEW-174（v4.35 待落地）/ F-REVIEW-132（v4.39 待落地） |
| 45 🆕v4.35 | 外部回链 query string 保留 | URL 同步 Hook 必须 `location.pathname + location.search`，findSheetMeta 必须剥离 query string | `grep "location.pathname" frontend/src/hooks/` 但无 `location.search` → query string 丢失 | meta-rules.md #45 / B-REVIEW-175（v4.35 待落地）/ F-REVIEW-133（v4.39 待落地） |
| 46 🆕v4.35 | 测试同步责任原则 | 接口签名变更/异步同步重构/mock 字段集/外部依赖必须同步更新测试 | `git diff` 生产代码方法签名变更但同 PR `tests/` 无修改 → 同步缺失 | meta-rules.md #46 / B-REVIEW-176（v4.35 待落地）/ F-REVIEW-134（v4.39 待落地） |
| 47 🆕v4.35 | 外部依赖隔离测试可重复性 | 测试中 keyring/env/file/network 必须显式 patch，禁止依赖生产 fallback | `grep "get_secret\|os.environ\[" tests/` 但无 `patch(..., return_value=None)` → 未隔离 | meta-rules.md #47 / B-REVIEW-177（v4.35 待落地）/ F-REVIEW-135（v4.39 待落地） |
| 48 🆕v4.36 | 调度器运行时开关对称性 | update_config(enabled=False) 必立即 remove_job + 入口 double-check；enabled=True 必恢复 job，开关操作必须对称 | `grep "def update_config" <file>` 缺 `remove_job` 或缺 double-check | scheduler.md / B-REVIEW-178 / F-REVIEW-136 |
| 49 🆕v4.36 | 时间参数配置化 | 异常重试等待/轮询间隔/超时秒数等时间参数必须从 config 读取，禁止硬编码 | `grep "time\.sleep\|asyncio\.sleep" <file>` 参数为字面量数字 | config-driven.md / B-REVIEW-179 / F-REVIEW-137 |
| 50 🆕v4.36 | 长生命周期对象状态清理 | 长生命周期对象（scheduler/container）持 task 级状态字典必须提供 drop_task_state 方法，删除 task 时调用 | `grep "def delete_task\|def unregister" <file>` 无 `drop_task_state` 调用 | state-management.md / B-REVIEW-180 / F-REVIEW-138 |
| 51 🆕v4.36 experimental | 用户输入时间表达式校验 | cron 表达式必须校验最小间隔 ≥ 反爬最小延迟，禁止 1 秒一次的滥用表达式 | `grep "CronTrigger" <file>` 无 min_interval 校验 | scheduler.md / B-REVIEW-181 / F-REVIEW-139 |
| 52 🆕v4.37 | 参数链闭环验证 | 过滤类参数必须存在消费点（SQL WHERE/条件分支/函数调用），禁止"参数已接收但未被消费" | `grep "<param_name>" <file>` 仅命中签名和 return 但未命中函数调用 | config-driven.md / B-REVIEW-182 / F-REVIEW-140 |
| 53 🆕v4.37 | 业务模式纵向链路一致性 | 业务模式枚举必须在决策/事件/通知/路由/接口/状态机 6 层纵向一致传递，任一层缺失即退化 | `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事件 payload/通知模板/路由/endpoint 中未命中 | state-management.md / B-REVIEW-183 / F-REVIEW-141 |
| 54 🆕v4.37 | 外部页面解析容错 | 解析第三方 DOM 必须三级 fallback selector（结构化→属性→文本扫描），全部失败才 dump | `grep "querySelector\|querySelectorAll"` 无 `try/except` 或 `or []` fallback | browser-automation.md / B-REVIEW-184 |
| 55 🆕v4.37 | mock 同步与边界精确性 | mock 类型与被 mock 对象同步/异步特性一致，patch 实际调用点，mock 数据覆盖完整字段集 | `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数 | testing.md / B-REVIEW-185 / F-REVIEW-143 |
| 56 🆕v4.37 | 过滤结果透明化 UI | ≥2 个过滤参数的列表 UI 必须透明化展示当前生效的过滤规则组合 | `grep "filter.*range\|market.*ratio"` 在列表 UI 但无 `Tooltip`/`filter_summary` | frontend-ui.md / F-REVIEW-142 |
| 57 🆕v4.38 | async/await 同步性静态检查 | async def 方法体内若不含 await 表达式，必须改为同步 def；调用点同步移除 await | `grep "async def" <file>` 后检查方法体内是否含 `await` | concurrency.md / B-REVIEW-182 / F-REVIEW-148 |
| 58 🆕v4.38 | 资源池配置性能基准与决策 | 数据库/HTTP/浏览器资源池配置必须有性能基准数据支持，docstring 记录选择理由与对比数据 | `grep "poolclass=" <file>` 无 docstring 说明；或慢查询日志中系统开销>50ms | database.md / B-REVIEW-183 / — |
| 59 🆕v4.38 | HTTP 状态码精细化映射表 | 底层模块返回多原因的 None/错误时，必须建立 reason_code → status_code 映射表；底层设置 last_*_failure_reason；上游按映射查找状态码；前端按状态码提供本地化消息 | `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 多原因汇聚同一码 | error-handling.md / B-REVIEW-184 / F-REVIEW-149 |
| 60 🆕v4.38 | CSS 选择器多级降级策略 | 依赖第三方网站 DOM 的选择器必须有 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描）；每级失败自动降级；调试 dump 触发条件收窄到核心字段失败 | `grep "querySelectorAll\|querySelector" <file>` 选择器单一；或 dump 文件频繁生成 | browser-automation.md / B-REVIEW-185 / — |
| 61 🆕v4.38 | 异常日志语义保留规范 | except 块内必须用 logger.exception('描述') 保留完整 traceback，禁用 logger.warning(f'...{e}') 丢失堆栈；非 except 块用 warning + exc_info=True；多阶段降级链合并为单条结构化 WARNING | `grep "logger.warning.*f\".*{e}\"" <file>` 或 `grep "logger.exception.*f\"" <file>` 在 except 块内 | error-handling.md / B-REVIEW-186 / F-REVIEW-150 |
| 62 🆕v4.38 | 外部资源生命周期配对管理 | 外部传入的资源（Page/Connection/Lock）必须配对调用 register/unregister，且在 finally 块 unregister 避免泄漏；并发场景下资源不被误关 | `grep "reuse_page\|external_page\|register_external" <file>` 未配对 register/unregister | concurrency.md / B-REVIEW-187 / F-REVIEW-151 |
| 63 🆕v4.38 | 数据库写入函数身份追溯与类型安全 | 数据库写入函数必须含 user_id 参数用于跨用户隔离；converter 函数处理 re.Match 对象必须显式调用 m.group(1) 再转型，禁用 int(m) | `grep "def upsert_\|def insert_\|def update_" <file>` 无 user_id；`grep "lambda m: int"` 无 group(1) | database.md / B-REVIEW-188 / — |
| 64 🆕v4.39 experimental | URL↔状态同步失败回退 | openSheet 失败时（路径未注册/栈满）必须回退 URL 到当前 active sheet 的 path，避免 useParams 漂移 | `grep "useSheetSync" frontend/src/hooks/` 但无 `useNavigate` 引入或无 `navigate(activeSheet.path)` | state-management.md / F-REVIEW-152（预沉淀） |
| 65 🆕v4.39 experimental | Service Worker 缓存版本同步 | PWA 应用构建时生成版本哈希，运行时版本检测不一致时触发 skipWaiting 强制更新 | `grep "navigator.serviceWorker.getRegistration" frontend/src/` 缺失或无 `SKIP_WAITING` 触发 | frontend-ui.md / F-REVIEW-153（预沉淀） |

### 规范沉淀 SOP（meta-rule #36 落地）🆕 v4.33.0

> 新立编码规范（meta-rule / step / B-REVIEW / F-REVIEW）必须遵循 5 步沉淀流程，避免单一 bug 立规范导致规范膨胀。详细规则见 [meta-rules.md #36](references/meta-rules.md)。

**5 步沉淀流程**：

1. **相似 bug 收集**：在 `docs/standards/编码规范复盘.md` 记录每次 bug 的根因、文件、模块、时间。同一根因在不同文件/模块出现 ≥ `config.yaml#meta_rules_governance.sedimentation_threshold`（默认 3）次才可立规范，时间窗口 ≤ 6 个月
2. **门槛校验**：立规范前必须 grep 历史教训段，确认相似 bug 计数达标。未达标但希望预沉淀的，标 `experimental` 标签 + 1 季度观察期
3. **例外豁免**：安全漏洞 / 数据丢失 / 付费受损类 bug 可立即立规范，无需 ≥3 次，但必须标注豁免原因
4. **规范编写**：达标后写入 meta-rules.md（详情）+ SKILL.md（速查表）+ 对应 step 文件 + B/F-REVIEW 检查点 + config.yaml 配置节点
5. **防回归**：加 unit test 覆盖规范触发条件 + 更新 version-history.md

**关键判断**：
- 单一 bug 立规范（无 experimental 标签）→ 规范膨胀风险
- experimental 标签超 1 季度未升级为正式 → 废弃候选
- 例外豁免立规范但未标注豁免原因 → 无法审计

### 规范退化清理 SOP（meta-rule #37 落地）🆕 v4.33.0

> 每季度统计各 step / B-REVIEW / F-REVIEW 利用率，利用率 < 3 次/季度则标记"待合并"或"待废弃"，避免规范垃圾堆积。详细规则见 [meta-rules.md #37](references/meta-rules.md)。

**季度清理流程**：

1. **利用率统计**：每季度末统计各 step / B-REVIEW / F-REVIEW 在审查报告中的命中次数，输出利用率排行榜
2. **退化标记**：利用率 < `config.yaml#meta_rules_governance.degradation_threshold`（默认 3 次/季度）则标记"待合并"或"待废弃"
3. **合并优先**：相似 step 优先合并（如 3 个 datetime 相关 step 合并为 1 个），废弃是最后手段
4. **观察期**：标记"待废弃" → 1 季度观察期（`observation_period_quarters`，默认 1） → 确认无命中 → 废弃
5. **废弃归档**：废弃的 step / B-REVIEW 移入 `version-history.md` 的 Deprecated 章节，保留历史记录

**安全类豁免**：token 比较 / 加密 / 认证白名单等安全类规范永不退化，即使 0 命中也保留。

### 规范适用边界（meta-rule #2 落地）

> 每条编码规范必须明确说明**适用场景**与**不适用场景**，确保通用性，避免审查时误用于不适用场景。详细规则见 [meta-rules.md #2](references/meta-rules.md)。

**适用边界声明模板**（每条 meta-rule / step / B-REVIEW / F-REVIEW 必须包含）：

```
**适用**：<具体场景列表，如"任务调度器 pause/resume、登录会话失效/恢复">
**不适用**：<排除场景列表，如"用户主动 pause、一次性任务、纯函数重试">
```

**边界声明检查清单**：
- [ ] 适用场景具体（非"所有场景"这种模糊描述）
- [ ] 不适用场景明确（列出排除项）
- [ ] 不适用场景有替代方案（如"用 xxx 替代"）
- [ ] 边界与 config 参数对齐（如"≤3 个 item 的小批量操作不适用"对应 `batch_size` 参数）

**常见不适用场景**（通用排除项）：
- 纯样式 bug（颜色/间距/字号）
- 单行 typo（错别字/标点）
- 纯构建错误（依赖缺失/版本冲突）
- 性能 hot path（持久化/校验开销不可接受）
- 实验性 feature 试错（故意频繁失败）
- 用户主动操作（非异常触发）

## 执行步骤

### 第一阶段：需求分析与规范确认

1. **需求理解**
   - 仔细阅读用户需求，明确功能目标与验收标准
   - 识别涉及的层（domain / infra / modules / web / frontend）
   - 评估是否需要数据库迁移、API 路由新增、前端组件改造

2. **规范检查【强制】**
   - 必须先阅读 [project-rules.md](references/project-rules.md) 了解项目硬约束
   - 后端开发：必须检查是否触及认证白名单、安全约束、并发模型
   - 前端开发：必须检查 SonarQube 规则（S2004/S3358/S6757/S7784/S6848/S1128/S4325/S3776）
   - 数据库开发：必须检查索引策略与迁移幂等性

3. **参考分析**
   - 同类功能实现：在 `src/xianyu_hunter/` 与 `frontend/src/` 中搜索相似模式
   - 设计文档：查阅 `docs/01-仪表盘/` 至 `docs/08-移动端/` 对应模块的详细设计
   - 历史教训：参考 [architecture-patterns.md](references/architecture-patterns.md) 中的踩坑记录

4. **开发指南参考【强制】**
   - **前端开发**: 必须参考 [前端开发指南](assets/guides/frontend-guide.md)
   - **后端开发**: 必须参考 [后端开发指南](assets/guides/backend-guide.md)
   - **数据库开发**: 必须参考 [数据库开发指南](assets/guides/database-guide.md)
   - **智能客服开发**: 必须参考 [智能客服开发指南](assets/guides/chatbot-guide.md)
   - **🆕 SonarQube 规则预防**: 编码时主动对照 [SonarQube 规则速查](assets/guides/sonarqube-rules-guide.md) 预防问题（认知复杂度 ≤ 15、嵌套 ≤ 4、不必要 `async`、可访问性等）
   - **项目规则**: 必须遵守 [项目规则](references/project-rules.md)
   - **架构模式**: 涉及并发、事件、调度、登录等场景，必须参考 [架构模式知识库](references/architecture-patterns.md)
   - **FAQ**: 遇到问题先查阅 [faq.md](references/faq.md)

### 第二阶段：开发实施

1. **后端开发**
   - **指南参考**: 先参考 [后端开发指南 - 代码模板](assets/guides/backend-guide.md#二代码模板) 章节
   - **路由层**: 新增 `src/xianyu_hunter/web/routes/api_<域>.py`，使用 `APIRouter(prefix="/api/<域>", tags=["<域>"])`
   - **业务模块**: 新增/修改 `src/xianyu_hunter/modules/<域>.py` 或 `modules/<域>/` 子包
   - **仓储层**: 新增 `src/xianyu_hunter/infra/repo_<域>.py` Mixin，并在 `infra/repository.py` 中聚合
   - **领域模型**: 新增/修改 `src/xianyu_hunter/domain/<域>.py`，dataclass + Enum，无 IO 依赖
   - **依赖注入**: 在 `container.py` 中装配新依赖（Composition Root）
   - **启动钩子**: 涉及后台调度器，在 `web/startup.py` 注册 startup/shutdown

2. **前端开发**
   - **指南参考**: 先参考 [前端开发指南 - 代码模板](assets/guides/frontend-guide.md#二代码模板) 章节
   - **API 模块**: 新增 `frontend/src/api/<域>.ts`，导出 `<域>Api`，在 `api/index.ts` re-export
   - **类型定义**: 在 `api/types.ts` 按业务域分组追加类型
   - **页面**: 新增 `frontend/src/pages/<域>/index.tsx`，在 `App.tsx` 注册路由（`lazyRetry`）
   - **菜单**: 在 `MainLayout.tsx` 的 `menuItems` 注册，在 `sheetRegistry.tsx` 维护 path → component 映射
   - **Hook**: 复用现有 `hooks/use*.ts`，必要时新增 `use<Feature>.ts`
   - **Store**: 涉及跨页状态，新增 `stores/<feature>Store.ts`，导出 `use<Feature>Store`

3. **数据库开发**
   - **指南参考**: 必须参考 [数据库开发指南](assets/guides/database-guide.md)
   - **新增表**: 在 `infra/db_models.py` 中定义 `*Row(Base)` 类，遵循 SQLAlchemy 2.0 `Mapped[T] + mapped_column` 风格
   - **新增字段**: 在 `init_db()` 中追加 `_migrate_add_column` 调用（幂等，列已存在则跳过）
   - **新增索引**: 在 `init_db()` 中追加 `_migrate_create_index` 调用（幂等）
   - **修改列类型**: SQLite 不支持 ALTER COLUMN，使用 `_migrate_make_column_nullable` 表重建模式
   - **仓储方法**: 在 `infra/repo_<域>.py` 中实现 CRUD，JSON 字段需在 `RepositoryBase._row_to_dict` 白名单中注册

4. **智能客服开发**
   - **指南参考**: 必须参考 [智能客服开发指南](assets/guides/chatbot-guide.md)
   - **新工具**: 在 `modules/chatbot/tools/` 新增工具类，继承 `BaseTool`，在 `tool_registry.py` 注册
   - **KB 数据源**: 修改 `KBManager._scan_and_chunk` 的扫描规则（白名单：`.md/.py/.jsonl/.txt`）
   - **降级链**: 在 `ChatbotOrchestrator._handle_*` 中追加降级分支，发布 `CHATBOT_DEGRADED` 事件


---

### ⚡ 编码规范（按需加载）

> **本节原包含 178 step 编码规范（约 30 万字符），已按主题归档到 `assets/guides/coding-rules/` 下 12 个文件。**
> 
> **加载策略**：
> 1. **AI 根据任务主题主动加载**：例如前端任务加载 `frontend-ui.md`，数据库任务加载 `database.md`
> 2. **元规范优先**：所有任务先加载 [meta-rules.md](references/meta-rules.md)（51 条规则，约 8K 字符）
> 3. **按 step 编号查找**：通过 [编码规范索引](assets/guides/coding-rules/_step-index.md) 定位特定 step
> 4. **版本演进**：通过 [version-history.md](references/version-history.md) 了解各规范的历史背景

**主题速查表**：

| 任务类型 | 应加载的规范文件 |
|---|---|
| 认证/加密/外部 API | security.md + meta-rules.md |
| 异步/并发/后台任务 | concurrency.md + meta-rules.md |
| 状态管理/缓存 | state-management.md + meta-rules.md |
| 错误处理/重试 | error-handling.md + meta-rules.md |
| DB schema 变更 | database.md + meta-rules.md |
| 配置项管理 | config-driven.md + meta-rules.md |
| React 组件/UI | frontend-ui.md + meta-rules.md |
| 测试编写 | testing.md + meta-rules.md |
| 调度器/定时任务 | scheduler.md + meta-rules.md |
| LLM 调用 | llm-ai.md + meta-rules.md |
| 浏览器自动化 | browser-automation.md + meta-rules.md |
| 通用编码 | general-engineering.md + meta-rules.md |

---

### 第三阶段：验证与交付

1. **类型检查**
   - 后端：`mypy` 未启用，依赖 Pydantic 运行时校验
   - 前端：`cd frontend; npx tsc -b`（构建前强制类型检查）

2. **测试执行**
   - 后端：`pytest tests/`（asyncio_mode=auto 自动识别 async 测试）
   - 前端：`cd frontend; npx vitest run`

3. **代码审查**
   - 前端代码审查：调用 `xianyu-frontend-code-review` Skill
   - 后端代码审查：调用 `xianyu-backend-code-review` Skill
   - SonarQube 扫描：调用 `xianyu-sonarqube-mcp` Skill

4. **常见问题排查**
   - 遇到问题先查阅 [faq.md](references/faq.md)
   - 涉及架构疑问查阅 [architecture-patterns.md](references/architecture-patterns.md)
   - 涉及反爬/登录/Cookie 链路，参考 `xianyu-automation-startserver` Skill 与 `docs/04-系统维护/反爬登录管理-详细设计.md`

### 第四阶段：Git 操作规范与 Bug 修复

1. **合并前检查【强制】**
   - 检查 `.git/index.lock` 是否残留（失败 git 操作可能留下锁文件导致后续操作全失败）
   - 检查工作区是否干净（有 modified 文件时先 stash）
   - 检查当前分支是否正确（`git branch --show-current`）
   - 检查是否有产物文件被 git track（`.scannerwork/`、`__pycache__/` 等）

2. **产物文件清理【强制】**
   - `.scannerwork/`、`node_modules/`、`dist/`、`__pycache__/` 等产物不应被 git track
   - 发现已被 track 时用 `git rm -r --cached <dir>` 清理（不删除工作区文件）
   - 确认 `.gitignore` 已包含对应路径
   - 清理后提交独立的 chore commit，再进行合并

3. **stash 操作注意事项**
   - stash 前确认无大目录（如 `.scannerwork/`）被 modified，避免权限问题导致 stash 失败
   - stash 失败后必须检查 `.git/index.lock` 是否残留
   - PowerShell 中 `stash@{0}` 必须加引号：`git stash pop 'stash@{0}'`（避免哈希表解析错误）

4. **.git 目录操作**
   - PowerShell 和 `cmd /c` 可能被安全策略阻止操作 `.git` 目录
   - 替代方案：用 Python `os.remove()` 删除 `.git` 下文件，或用 git 命令本身操作
   - 示例：`python -c "import os; os.remove('.git/index.lock')"`

5. **冲突解决原则**
   - 保留更新版本（如 main 的 `await` 异步版本优于 feat 的同步版本）
   - 同一功能两分支都有修改时，选择语义更完整的版本
   - cherry-pick 后的合并冲突：main 已有 cherry-pick 的改动，feat 有原始改动，保留 main 版本

6. **Bug 修复流程【强制】**
   - **根因定位**：读取相关文件 → 追踪数据流 → 定位最小修改点
   - **最小修改**：只修改必要的部分，不顺便重构（遵循精确编辑原则）
   - **验证策略**：`tsc --noEmit` 验证类型 → 运行专项测试 → 必要时手动验证
   - **状态一致性检查**：修复状态管理 bug 时，检查操作是否同步更新所有相关状态字段

7. **测试环境兼容性**
   - Node v24 + vitest 4.x 存在 worker 启动超时问题，测试命令必须加 `--no-isolate`
   - antd 组件（Drawer/Grid/Skeleton）在 jsdom 中需要 `window.matchMedia` mock
   - vitest 卡在 RUN 阶段时，用 `tsc --noEmit` 作为类型验证的备选手段
   - 测试命令示例：`node node_modules/vitest/vitest.mjs run --no-isolate <test-file>`


## 相关 Skills 协作

| Skill | 协作场景 |
|---|---|
| `xianyu-automation-startserver` | 启停服务、构建、状态检查 |
| `xianyu-backend-code-review` | 后端代码评审（Python/FastAPI） |
| `xianyu-frontend-code-review` | 前端代码评审（React/TypeScript） |
| `xianyu-sonarqube-mcp` | SonarQube 代码质量扫描与问题修复 |
| `xianyu-logs-review` | 运行时日志分析与 WARNING/ERROR 排查 |

## 阶段交接声明

- 当前阶段：v4.39.0 experimental 元规范（#64-65）✅ 已完成
- 下一阶段：v4.40.0 规划（基于实际复盘事件触发）
- 下一阶段智能体：bemp-personalized-developer 或 xianyu 代码审查相关智能体
- 下一阶段技能：xianyu-hunter-dev / xianyu-frontend-code-review / xianyu-backend-code-review
- 交接上下文：本轮基于"URL↔状态同步失败回退、Service Worker 缓存版本同步"2 类问题复盘，案例数<3 次，按 meta-rule #36 门槛规则标 experimental 标签预沉淀（观察期 2026-07-08 至 2026-10-08）。新增 2 条 experimental 元规范：#64 URL↔状态同步失败回退（openSheet 失败时必须回退 URL 到 active sheet 的 path）+ #65 SW 缓存版本同步（版本不一致时触发 skipWaiting 强制更新）。配置节点：url_state_sync_fallback / sw_cache_version_sync。前端检查点：F-REVIEW-152/153（预沉淀）。

## 版本历史

> 版本历史已外移到 [references/version-history.md](references/version-history.md)。
> 
> 覆盖范围：v4.14.0 → v4.29.0，包含每个版本的：
> - 新增 step 编号与规范标题
> - 复盘方法（Sequential Thinking N 步法）
> - 代码修复点
> - 审查技能同步落地情况
> - 历史教训
