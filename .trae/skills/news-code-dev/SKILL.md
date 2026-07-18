---
name: "news-code-dev"
description: "MorningBrief 项目的标准化开发技能，覆盖后端(FastAPI/SQLAlchemy)、前端(Vue 3/Element Plus/小程序)、工作流编排(LLM/TTS)、测试、优化和缺陷修复。同时包含 20_News 项目编码规范与部署标准（数据库初始化、多模式部署、环境配置、安全认证、前后端交互）。当用户要求'开发新功能/添加接口/修改代码/修复bug/重构/优化性能/写测试/部署排查'时调用。"
whenToUse: "需要开发新功能、修复缺陷、优化代码或编写测试时使用"
triggers: "开发新功能/添加接口/修改代码/修复bug/重构/优化性能/写测试/部署排查 | 开发/实现/添加/修改/修复/优化/重构/部署 | 后端/前端/小程序/工作流/测试/数据库 开发 | 这段代码怎么写/怎么改/怎么优化/怎么部署"
version: "2.0.0"
updated: "2026-07-18"
config: "config/project-config.json"
---


# MorningBrief 项目开发技能

AI 驱动的播客新闻分发平台标准化开发技能。

## 项目背景速查

| 维度 | 内容 |
|------|------|
| 产品定位 | AI 驱动的播客新闻分发平台 |
| 后端技术 | Python 3.12 + FastAPI + SQLAlchemy 2.0 + aiosqlite + TTLCache + APScheduler |
| 前端技术 | Vue 3 + Element Plus + Vite + Pinia |
| 小程序 | 微信小程序原生（JS/WXML/WXSS） |
| AI 服务 | 通义千问 LLM + 阿里云 TTS + 腾讯云 COS |
| 部署方式 | 单机 exe（PyInstaller 6.x）/ 开发模式（venv → 系统 Python） |
| 核心链路 | RSS/搜索抓取 → LLM 改写 → TTS 合成 → 音频拼接 → 审核发布 → 小程序播放 |

## 技术栈速查

### 后端
- **框架**：FastAPI（异步）
- **ORM**：SQLAlchemy 2.0（async）
- **数据库**：SQLite（aiosqlite 驱动，WAL 模式 + busy_timeout）
- **缓存**：TTLCache（进程内缓存，V1.2 替代 Redis）
- **调度**：APScheduler（AsyncIOScheduler）
- **HTTP 客户端**：httpx（AsyncClient）
- **打包**：PyInstaller 6.x（standalone exe）
- **测试**：pytest + aiosqlite

### 前端（运营后台）
- **框架**：Vue 3（`<script setup>` + Composition API）
- **UI 库**：Element Plus
- **构建工具**：Vite
- **状态管理**：Pinia
- **HTTP 客户端**：axios

### 小程序
- **框架**：微信小程序原生
- **音频**：wx.getBackgroundAudioManager
- **状态**：App.globalData

## 文档结构

```
.news-code-dev/
├── SKILL.md                          ← 你在这里（技能主文件）
├── config/
│   └── project-config.json           ← 项目配置（路径/技术栈/硬约束）
├── references/
│   ├── architecture-patterns.md      ← 四层架构/工作流/缓存/认证/降级模式
│   ├── coding-standards.md           ← Python/Vue/小程序/数据库/API 规范
│   ├── meta-rules.md                 ← 30 条元规范（配置驱动/异步安全/JWT 安全/批量删除/多选交互等）（配置驱动/异步安全/JWT 安全等）
│   ├── faq.md                        ← 11 个常见问题解答
│   └── version-history.md            ← 版本演进和复盘
├── assets/
│   ├── guides/
│   │   ├── backend-guide.md          ← 后端 10 节完整开发指南
│   │   ├── frontend-guide.md         ← 前端 8 节完整开发指南
│   │   ├── workflow-guide.md         ← 工作流 8 节完整开发指南
│   │   └── testing-guide.md          ← 测试 6 节完整开发指南
│   ├── templates/
│   │   ├── python/                   ← Python 模板（service/route/model）
│   │   └── vue/                      ← Vue 模板（page/api/store）
│   └── rules/
│       ├── security.md               ← 安全规则（JWT/XSS/SQL 注入等）
│       ├── async-concurrency.md      ← 异步规则（create_task/to_thread 等）
│       ├── database.md               ← 数据库规则（索引/事务/迁移等）
│       ├── error-handling.md         ← 错误处理规则（异常分类/日志等）
│       └── config-driven.md          ← 配置驱动规则（settings/env 等）
└── scripts/
    └── pre-commit-check.ps1          ← 提交前检查脚本（语法/构建/硬约束）
```

## 开发规范文档

### 指南文档（怎么做）

| 文档 | 用途 | 关键章节 |
|------|------|----------|
| [backend-guide.md](assets/guides/backend-guide.md) | 后端 FastAPI/SQLAlchemy 开发 | 路由/服务层/工作流/异步/安全 |
| [frontend-guide.md](assets/guides/frontend-guide.md) | 前端 Vue 3/Element Plus/小程序 | 组件/状态管理/API 调用/性能优化 |
| [workflow-guide.md](assets/guides/workflow-guide.md) | 工作流编排（RSS/LLM/TTS） | 状态机/分布式锁/重试/降级 |
| [testing-guide.md](assets/guides/testing-guide.md) | 测试编写（单元/集成/E2E） | pytest/fixtures/覆盖率 |

### 规则文档（不能做什么）

| 文档 | 关键规则 |
|------|----------|
| [security.md](assets/rules/security.md) | JWT 安全/hmac.compare_digest/SQL 注入防护/敏感信息保护 |
| [async-concurrency.md](assets/rules/async-concurrency.md) | create_task 保留引用/to_thread 阻塞操作/禁止 time.sleep |
| [database.md](assets/rules/database.md) | 索引规范/事务粒度/迁移幂等/LIMIT 必加 |
| [error-handling.md](assets/rules/error-handling.md) | 异常分类/日志级别/禁止吞异常 |
| [config-driven.md](assets/rules/config-driven.md) | 禁止硬编码/env 文件管理/多环境配置 |

### 参考文档（深入理解）

| 文档 | 关键内容 |
|------|----------|
| [architecture-patterns.md](references/architecture-patterns.md) | 四层架构/工作流编排/缓存模式/认证模式/降级模式 |
| [coding-standards.md](references/coding-standards.md) | Python/Vue/小程序/数据库/API 契约详细规范 |
| [meta-rules.md](references/meta-rules.md) | 24 条元规范（含 grep 判断信号） |
| [faq.md](references/faq.md) | 添加 API/数据库表/工作流步骤/修改 Prompt/开发模式登录失败等 |

## 工作流元规范速查

以下是 24 条核心元规范的精简版，详细规则请参考 [meta-rules.md](references/meta-rules.md)。

| # | 规范 | 适用场景 | 判断信号（grep） | 优先级 |
|---|------|----------|------------------|--------|
| 1 | 配置驱动 | 后端所有服务 | 搜索具体值如 `3600`、`http://` | CRITICAL |
| 2 | 复用优先 | 新增功能 | 发现相似业务逻辑 | HIGH |
| 3 | 错误分类 | 所有 API | except 统一返回 500 | HIGH |
| 4 | 资源生命周期 | 异步任务/锁/连接 | 资源创建后无清理 | HIGH |
| 5 | 异步安全 | 异步代码 | `create_task(` 无赋值、`requests.get` | CRITICAL |
| 6 | 迁移幂等 | 数据库迁移 | 无 `IF NOT EXISTS` | HIGH |
| 7 | JWT 安全 | Token 验证 | `token ==` 而非 `hmac.compare_digest` | CRITICAL |
| 8 | 时区一致性 | 跨模块时间判定（预算限流/调度/回溯/TTL） | `datetime.now(timezone.utc)` 与 `datetime.now()` 混用 | CRITICAL |
| 9 | 枚举 .value | 数据库存储 | `str(MyEnum.VALUE)` | MEDIUM |
| 10 | Redis Lua | 多步 Redis 操作 | 连续两次 Redis 操作 | HIGH |
| 11 | 内部接口鉴权 | localhost 接口 | 路由有 `internal` 标签但无 IP 校验 | HIGH |
| 12 | 敏感词初始化 | AC 自动机 | `AhoCorasick(` 在请求函数内 | HIGH |
| 13 | 异常不覆盖 | 自定义异常 | `class Error(Exception)` | MEDIUM |
| 14 | 日志 traceback | 错误日志 | `logger.error(e)` 无 `exc_info` | HIGH |
| 15 | 分页必须 LIMIT | 所有查询 | `.all()` 无 `.limit()` | HIGH |
| 16 | 前后端字段契约 | API 对接 | 前端使用 `snake_case` | HIGH |
| 17 | 缓存主动失效 | 写操作 | `redis.setex` 紧跟 `db.update` | MEDIUM |
| 18 | 工作流重试上限 | 工作流步骤 | `while True` 或无 base case 的递归 | HIGH |
| 19 | 敏感信息不落地 | 日志/数据库 | `logger.info.*password` | CRITICAL |
| 20 | 测试隔离 | 测试用例 | 测试间共享全局状态 | MEDIUM |
| 23 | 时长/容量约束自动调整 | 音频拼接/文档生成/报表 | 搜索 duration 超出范围后直接 raise | CRITICAL |
| 24 | 确定性失败重试无效 | 工作流编排/批处理 | 步骤函数无外部状态依赖仍重试 | HIGH
| 25 | 模型名称以官方为准 | 第三方服务接入 | 预设配置中的模型名与官网不符 | CRITICAL
| 26 | 配置持久化完整返显 | 配置管理页面 | 预设切换覆盖 API Key / 下拉框不反射 | HIGH
| 27 | 模型定价表同步更新 | LLM 服务商变更 | 新增模型名未同步定价表 | HIGH |

| 30 | 构建脚本并发保护 | 级联删除操作 | 搜索多表删除无事务包裹 | CRITICAL
| 31 | 启动脚本路径安全封装 | 批量操作表格 | 搜索 el-table 无 selection 列 | HIGH
| 32 | 共享构建依赖完整提取 | 所有路由定义 | 搜索静态路由在动态路由之后 | CRITICAL
| 33 | 时区一致性全局统一 | 跨模块时间判定 | `datetime.now(timezone.utc)` 与 `datetime.now()` 混用 | CRITICAL
| 34 | 主从表级联清理完整性 | 删除主表记录 | `delete(Model)` 后无对从表的 update/delete | CRITICAL
| 35 | 0 结果容错分支 | 查询返回 0 条 | `if count == 0: raise` 无 fallback 检查 | HIGH
| 36 | 动态注入而非硬编码条件 | LLM prompt/字段可选 | `if config_flag and not template_text` 多条件跳过 | HIGH
| 37 | 选题后关联关系更新 | 业务流程选取记录 | `select(Material)` 后无 `update(Material).workflow_id=` | HIGH
| 38 | blob/二进制响应错误解析 | 前端文件下载 | `responseType: 'blob'` 无 `parseBlobError` | HIGH
| 39 | 频道级配置覆盖全局 | 多频道场景 | `settings.X` 无 `if ch.x is not None` 频道级检查 | HIGH
| 40 | 定时任务频道级触发 | 多频道调度 | `_cron_trigger` 无遍历活跃频道列表 | HIGH
| 41 | el-switch 类型契约 | 前端开关字段 | `<el-switch` 无 `:active-value` 且后端字段为 int | HIGH
| 42 | v-loading 状态恢复 | visibility 切换 | `handleVisibilityChange` 直接调用 load 无 nextTick | HIGH
| 43 | 页面标题冗余 | 顶部导航已有页面名 | `<span class="page-title">` 且侧边栏已有同名菜单 | MEDIUM
| 44 | 环境隔离与 URL 配置化 | 真机测试/前后端联调 | 搜索 http://localhost 或 127.0.0.1 出现在代码中 | CRITICAL |
| 45 | 小程序页面四件套完整 | 小程序页面开发 | 页面目录缺少 .json/.js/.wxml/.wxss 任一文件 | HIGH |
| 46 | 事件绑定对称性 | 小程序页面生命周期 | 搜索 onPlay 无对应 offPlay 在 onUnload 中 | HIGH |
| 47 | 模型字段名验证 | ORM 查询编写 | 搜索 Workflow.workflow_id 等不存在的字段名 | CRITICAL |
| 48 | 统计口径校验 | 聚合查询 | 搜索 sum(PlayLog.duration) 用于统计实际收听时长 | HIGH |
| 49 | 工具层与代码层 bug 分离 | 问题诊断 | webviewId/mainframe 500 等工具 bug 误判为代码缺陷 | HIGH |
| 50 | 频道级数据隔离严格性 | 多频道/多租户查询 | `grep "OR.*channel_id IS NULL"` 或 `or_(... channel_id.is_(None))` 兜底 | CRITICAL |
| 51 | 第三方转换服务串行验证 | RSS 源/第三方 API 验证 | 并发验证 plink/rsshub 等转换服务出现 0 条目假阳性 | HIGH |
| 52 | PowerShell Python 脚本调用规范 | Windows + Python 工具链 | `python script.py` 在 PowerShell 中输出不可见 | HIGH |
| 53 | RSS 源可达性诊断流程 | RSS 抓取/爬虫系统 | HTTP 200 但 feedparser 解析 0 条目未做内容类型检查 | HIGH |
| 54 | 原生 RSS 优先原则 | RSS 源配置 | rss.yaml 优先使用 rsshub.app 第三方转换而非原生 RSS | HIGH |
| 55 | 频道级配置与素材同步 | 频道 RSS 源变更 | 修改 rss.yaml name 后未同步数据库 channel.rss_sources JSON | HIGH |

| 56 | SQLAlchemy Inspector run_sync 陷阱 | 动态表结构反射/数据库维护模块 | `run_sync` 回调内使用 `inspect(` 但无 `.connection()` 转换 | CRITICAL |
| 57 | main.py 导入完整性 | 服务启动/中间件注册 | main.py 中使用 `RequestIdMiddleware`/`setup_logging` 等符号但无对应 import | CRITICAL |
| 58 | CONFIRM_DELETE 令牌双重确认 | 危险操作（删表/清空/VACUUM） | 危险操作端点未校验 `confirm_token` 参数 | CRITICAL |
| 59 | 敏感字段动态脱敏 | 表数据导出/数据库维护 | 导出函数无脱敏逻辑，或仅静态字段名匹配 | HIGH |
| 60 | 应用层级联删除策略 | 删除主表记录 | `db.delete(main)` 后无对从表的 cascade/set_null 处理 | CRITICAL |
| 61 | VACUUM AUTOCOMMIT 模式 | SQLite 压缩/系统清理 | `VACUUM` 在 `async with session.begin()` 事务块内 | CRITICAL |
| 62 | bindparam expanding IN 列表 | IN 查询参数化 | `IN (` 后跟字符串拼接而非 `bindparam(expanding=True)` | HIGH |
| 63 | 数据库维护白名单机制 | 数据库管理后台 | 表操作未检查白名单（允许操作的表清单） | CRITICAL |
| 64 | dry_run 预览模式 | 清理/删除类操作 | 清理函数不支持 `dry_run=True` 参数 | HIGH |
| 65 | 审计日志完整覆盖 | 所有 DML 和清理操作 | `db.delete`/`db.execute(delete(...))` 后无 `audit_log` 记录 | HIGH |
| 66 | 认知复杂度阈值治理 | service/workflow 层复杂函数 | 函数行数>50 且嵌套>3 层；ruff C901 警告 | CRITICAL |
| 67 | async 函数必须含 await | 所有 async 函数 | `async def` 后 50 行内无 `await`；SonarQube S7503 | CRITICAL |
| 68 | 正则表达式捕获组优化 | 所有 re 模块代码 | `re.match` 中 `(...)` 后续无 `group(N)`；SonarQube S6395 | HIGH |
| 69 | list() 调用必要性检测 | for 循环代码 | `for x in list(...)` 模式；SonarQube S7504 | MEDIUM |
| 70 | 未使用变量/参数/导入检测 | 所有 Python/前端代码 | ruff F841/F401；SonarQube S1481/S1128 | HIGH |
| 71 | 数据驱动重构模式 | ≥3 个 elif 判断同一变量 | 同一函数内 ≥3 个 elif；函数行数>50 | HIGH |
| 72 | import 语句组织规范 | 所有 Python/前端代码 | eslint `import/order`；isort I001；SonarQube S3863 | MEDIUM |
| 73 | DOM API 现代化规范 | 前端 JS/TS 代码 | `removeChild(`/`appendChild(`/`className =`；SonarQube S7762 | HIGH |
| 74 | 空 except 块禁止规范 | 所有 try/except 代码 | `except: pass` 或空 except 块；SonarQube S2486 | HIGH |
| 75 | SonarQube 扫描闭环规范 | 发版前完整验证 | 二次扫描 OPEN>0 或有新增问题 | CRITICAL |

**状态分类**：CRITICAL（必须遵守）/ HIGH（强烈建议）/ MEDIUM（建议）/ LOW（可选）/ INFO（参考）

## 四维度复盘

### 维度 1：架构设计

**做得好的**：
- 四层架构（routers → services → models → core）清晰，职责分离
- 配置驱动（settings.py + .env）使代码具有良好可移植性
- cache-aside 缓存模式简单有效，配合主动失效保证一致性
- 工作流状态机 + 分布式锁 + 重试机制保障可靠性

**待改进的**：
- 工作流编排可考虑引入正式的状态机库（如 transitions）
- 缓存键命名规范需要进一步细化（避免 key 碰撞）
- 内部接口鉴权需加强（IP 校验 + 请求签名双重验证）
- 时长/容量约束操作需实现自动填充/切除（见元规范 23）
- 确定性失败不应依赖重试机制（见元规范 24）

### 维度 2：编码规范

**做得好的**：
- 类型注解覆盖全面，便于 mypy/ruff 静态检查
- 异步规范统一（async/await + httpx.AsyncClient + aiosqlite）
- 错误分类清晰（AuthError/BusinessError/SystemError），前端解析方便
- 日志规范统一（结构化日志 + traceback 保留）

**待改进的**：
- 日志格式可进一步 JSON 化，便于 ELK 采集
- 需要补充代码审查 checklist（PR 模板）
- 前端组件拆分粒度需要统一标准（单一职责 vs 组合组件）
- 工作流步骤的确定性失败需区分瞬态失败（可重试）和确定性失败（需自动调整）

### 维度 3：开发效率

**做得好的**：
- 模板文件覆盖常见开发场景（service/route/model/page/api/store）
- FAQ 文档解决高频问题（添加 API/数据库表/工作流步骤）
- 元规范提供可验证的判断信号（grep 模式），便于自动化检查
- pre-commit 脚本自动检查语法/构建/硬约束

**待改进的**：
- 需要 CLI 脚手架工具（`news-cli new router/module/page`）
- 测试覆盖率目标需要明确（后端 80% + 前端 70%）
- 需要补充性能基准测试（API 响应时间/工作流吞吐量）

### 维度 4：团队协作

**做得好的**：
- 前后端字段契约明确（snake_case ↔ camelCase 转换在序列化层）
- API 响应格式统一（`{code, message, data}`）
- 数据库迁移使用 Alembic，版本可控且支持回滚

**待改进的**：
- 需要建立正式的代码审查流程（PR template + review checklist，已集成 news-backend-code-review / news-frontend-code-review）
- 需要补充 Git 分支管理规范（git-flow/trunk-based）
- 需要定义发布流程和回滚机制（灰度发布 + 快速回滚）
- 需要建立监控告警体系（SLO/SLI + 告警分级）

### 维度 5：频道级数据隔离与第三方源依赖（2026-07-17 复盘）

**做得好的**：
- 频道级配置字段（rss_sources/keywords/channel_id）设计完整
- crawler 按频道隔离抓取，避免跨频道素材污染
- rss.yaml 集中管理所有 RSS 源，便于维护

**待改进的**：
- 历史遗留的 NULL channel_id 兜底逻辑（`OR channel_id IS NULL`）导致专门频道消费遗留素材，必须移除
- rsshub.app 公共实例在大陆被 DNS 污染 + TCP 阻断，所有依赖该服务的源全部失效
- 第三方转换服务（plink.anyfeeder.com）存在会话级限流，并发≥5 时部分源返回 0 条目
- PowerShell 调用 Python 脚本时 stdout 缓冲导致输出不可见

**新增规范**（详见元规范 50-55）：
- 元规范 50：频道级数据隔离严格性（专门频道严格过滤，NULL 仅全局可用）
- 元规范 51：第三方转换服务串行验证（避免并发限流假阳性）
- 元规范 52：PowerShell Python 脚本调用规范（`python -u` + `2>&1`）
- 元规范 53：RSS 源可达性诊断流程（HTTP 200+0 条目需检查内容类型）
- 元规范 54：原生 RSS 优先原则（避免依赖第三方转换服务）
- 元规范 55：频道级配置与素材同步（rss.yaml 变更必须同步数据库）

### 维度 6：新增元规范详解（50-55）

> 以下规范来源于 2026-07-17 频道级数据隔离修复与 RSS 源端到端验证复盘。

#### 元规范 50：频道级数据隔离严格性

**为什么**：多频道场景下，专门频道（channel_id 非空）配置了自己的 rss_sources 和 keywords，期望只抓取和消费本频道素材。如果查询时用 `OR channel_id IS NULL` 兜底，当专门频道的 RSS 源全部失败时，会消费 NULL 历史遗留素材（如 36氪/人民网），导致跨频道内容污染。

**规范**：
- 专门频道（channel_id 非空）查询必须严格按 `WHERE channel_id = ?` 过滤，禁止 `OR channel_id IS NULL` 兜底
- NULL channel_id 素材仅对全局工作流（channel_id=None）可见
- 专门频道 RSS 源全部失败时应显式报错，而非用 NULL 素材掩盖问题

**判断信号**：
- `grep -rn "OR.*channel_id IS NULL"` 在 services/ 或 workflow/ 目录
- `grep -rn "or_(.*channel_id.*is_(None))"` 在 services/ 或 workflow/ 目录
- `grep -rn "or_.*channel_id"` 检查是否有未使用的 or_ 导入残留

**适用场景**：多频道/多租户数据隔离系统
**不适用场景**：单频道系统（无 channel_id 字段）

#### 元规范 51：第三方转换服务串行验证

**为什么**：第三方 RSS 转换服务（如 plink.anyfeeder.com、rsshub.app）存在会话级限流。并发≥5 或串行间隔<1.5s 时，部分源会返回 0 条目（假阳性）。生产环境 crawler 单源串行抓取（每源间有文章提取 IO）天然避免此问题，但验证脚本并发测试会误判。

**规范**：
- 验证第三方转换服务可达性时，必须串行执行，间隔 ≥3s
- 并发验证出现 0 条目时，必须用串行模式复测确认
- 生产环境 crawler 单源串行抓取无需额外延迟（文章提取 IO 天然间隔）
- 验证脚本应区分"真失效"（多次串行仍 0 条目）和"限流假阳性"（串行恢复）

**判断信号**：
- 验证脚本使用 `asyncio.gather` 或 `concurrent.futures` 并发测试 plink/rsshub 源
- 并发测试结果与生产 crawler 结果不一致（生产正常，验证脚本 0 条目）

**适用场景**：依赖第三方转换服务（plink/rsshub 等）的 RSS 抓取系统
**不适用场景**：原生 RSS 源验证（无限流）、生产 crawler 流程（已有自然间隔）

#### 元规范 52：PowerShell Python 脚本调用规范

**为什么**：PowerShell 调用 Python 脚本时，stdout 默认是块缓冲（非行缓冲）。脚本输出在缓冲区满或脚本退出前不可见，导致长时间运行的脚本看起来"卡住"。同时 Python 的 logger.error 写入 stderr，PowerShell 会包装为 RemoteException 警告，但脚本继续执行。

**规范**：
- PowerShell 调用 Python 脚本必须用 `python -u script.py`（-u 禁用缓冲）
- 捕获 stderr 输出必须用 `2>&1` 重定向到 stdout
- 完整命令格式：`python -u script.py 2>&1`
- 不要因为 RemoteException 警告误判脚本失败（logger.error 是正常日志输出）

**判断信号**：
- PowerShell 中执行 `python script.py`（无 -u）后输出不可见或延迟
- 脚本"卡住"但实际正在运行（缓冲区未满）

**适用场景**：Windows + PowerShell + Python 工具链
**不适用场景**：bash/zsh（默认行缓冲）、IDE 内运行（IDE 处理缓冲）

#### 元规范 53：RSS 源可达性诊断流程

**为什么**：feedparser 解析 RSS 时，HTTP 200 但 0 条目不一定是 RSS 格式问题。可能原因：(1) 站点返回 HTML 页面（非 RSS）；(2) WAF 拦截；(3) 第三方转换服务限流；(4) 微信公众号被封禁（plink 源）；(5) UA 被拒绝（如 Steam 拒绝 bot UA）。直接判定"RSS 格式错误"会误导修复方向。

**规范**：
- HTTP 200 但 0 条目时，必须检查响应内容类型（Content-Type）和前 200 字符
- 响应为 HTML（`text/html`）→ 站点未提供 RSS，返回的是网页
- 响应为 RSS XML 但 0 条目 → 可能是限流或源被封禁
- 响应为空 → 网络/DNS 问题
- 验证 UA 兼容性：部分站点（如 Steam）拒绝 bot UA，需用浏览器 UA

**判断信号**：
- feedparser 返回 0 条目但 HTTP 200
- 响应 Content-Type 为 `text/html` 而非 `application/rss+xml` 或 `application/xml`
- 响应前 200 字符含 `<!DOCTYPE html>` 或 `<html>`

**适用场景**：所有 RSS 抓取系统、爬虫系统
**不适用场景**：API 接口（JSON 响应）

#### 元规范 54：原生 RSS 优先原则

**为什么**：第三方转换服务（rsshub.app、plink.anyfeeder.com）作为中间层，引入额外故障点：DNS 污染、TCP 阻断、会话限流、微信公众号封禁等。rsshub.app 公共实例在大陆被 DNS 污染 + TCP 阻断，所有依赖该服务的源全部失效。原生 RSS 更稳定可控。

**规范**：
- RSS 源配置优先使用站点原生 RSS（如 `https://www.gcores.com/rss`）
- 仅在站点无原生 RSS 时才考虑第三方转换服务
- 使用第三方转换服务时，必须在 rss.yaml 注释中标注"第三方转换，有限流风险"
- 定期审计第三方转换服务的可达性（建议每月一次）

**判断信号**：
- rss.yaml 中大量源 URL 含 `rsshub.app` 或 `plink.anyfeeder.com`
- 站点有原生 RSS 但配置了第三方转换 URL

**适用场景**：RSS 源配置、爬虫数据源管理
**不适用场景**：站点确实无原生 RSS 且无替代方案

#### 元规范 55：频道级配置与素材同步

**为什么**：rss.yaml 中的源 name 变更后，数据库 channel.rss_sources（JSON 数组）字段仍存储旧 name，导致 crawler 按 name 匹配时找不到源，返回 0 条素材。这是配置文件与数据库不同步的典型问题。

**规范**：
- 修改 rss.yaml 中源的 name 字段后，必须同步更新数据库 `channel.rss_sources` JSON 数组
- 修改 rss.yaml 中源的 URL 后，无需同步数据库（crawler 按 name 匹配，不按 URL）
- 新增源后，如需频道使用，必须更新对应频道的 `channel.rss_sources`
- 提供配置同步脚本：`python -m app.scripts.sync_rss_sources`（读取 rss.yaml，更新所有频道的 rss_sources）

**判断信号**：
- rss.yaml 中源 name 变更后，crawler 日志显示"未找到匹配的 RSS 源"
- channel.rss_sources JSON 数组中的 name 在 rss.yaml 中不存在

**适用场景**：频道级 RSS 源配置管理
**不适用场景**：全局 RSS 源（不按频道隔离）

### 维度 7：数据库维护模块开发与测试（2026-07-17 复盘）

> 以下复盘基于数据库维护 + 系统清理模块开发与 news-auto-testing 18/18 PASS 测试实践。

**成功执行任务的完整步骤**：

1. 需求确认（AskUserQuestion 明确 4 项决策：功能范围/表浏览范围/权限控制/危险操作策略）
2. 参考已有项目（17_xianyu）的设计模式
3. 后端开发：AuditLog 模型 → db_admin_service（白名单/反射/CRUD/级联/脱敏/审计）→ maintenance_service（dry_run/VACUUM/过期清理）→ 路由层 → 配置项
4. 前端开发：API 封装 → DatabaseAdmin.vue（左右分栏）→ Maintenance.vue（dry_run 预览）→ 路由注册
5. 测试（news-auto-testing）：配置路径核对 → 服务启动预检 → 6 阶段测试 18/18 PASS

**不确定性与失败点**：

| 失败点 | 根因 | 修复方式 | 对应规范 |
|--------|------|----------|----------|
| config.yaml 审计日志路径错误 | `/audit-logs`（复数）与后端 `/audit-log`（单数）不一致 | 修正配置文件 | 63 白名单 |
| main.py RequestIdMiddleware 未定义 | 既有代码使用但未导入 | 添加 `from app.middleware.request_id import RequestIdMiddleware` | 57 导入完整性 |
| main.py setup_logging 未定义 | 既有代码使用但未导入 | 添加 `from app.core.logging_setup import setup_logging` | 57 导入完整性 |
| SQLAlchemy Inspector 使用陷阱 | `run_sync` 回调参数是 Session 而非 Connection | 回调内先 `session.connection()` 获取 Connection 再传给 Inspector | 56 run_sync 陷阱 |
| VACUUM 操作失败 | 在事务内执行 VACUUM | 使用 AUTOCOMMIT 隔离级别或 `VACUUM INTO` | 61 VACUUM 模式 |
| 敏感字段脱敏不完整 | 静态字段名匹配无法覆盖 ai_config 等动态表 | 静态字段名 + 动态字段名匹配（含 password/secret/token/key） | 59 动态脱敏 |

**可抽象的固定流程**：

1. **数据库维护模块开发流程**：白名单机制（配置驱动）→ 动态反射表结构（Inspector + run_sync + .connection()）→ CRUD 操作（bindparam expanding）→ 应用层级联删除（cascade + set_null）→ 敏感字段动态脱敏 → 审计日志记录 → CONFIRM_DELETE 令牌双重确认
2. **系统清理模块开发流程**：dry_run 预览模式 → VACUUM AUTOCOMMIT → 过期记录清理（基于时间戳）→ 日志/缓存清理 → 审计日志记录
3. **测试预检流程**：配置文件路径核对（API 端点路径与后端路由一致）→ main.py 导入完整性检查（py_compile + import）→ 服务健康检查（轮询）→ 专项测试

**固定判断逻辑**：

- 数据库维护安全 = 表在白名单 + 敏感字段脱敏 + CONFIRM_DELETE 令牌
- 系统清理安全 = dry_run 预览 + 审计日志记录
- SQLAlchemy Inspector 正确使用 = `run_sync` 回调中先 `.connection()` 转换 Session 为 Connection
- VACUUM 正确执行 = AUTOCOMMIT 隔离级别（禁止在事务内）
- main.py 启动成功 = 所有使用到的中间件/函数都已显式导入

**适用场景与不适用场景**：

| 流程 | 适用场景 | 不适用场景 |
|------|---------|-----------|
| 数据库维护模块 | SQLite/MySQL 单机应用、需要可视化表管理的后台 | 分布式数据库、云数据库（已有原生管理工具） |
| 系统清理模块 | 长期运行的服务、SQLite 数据库、日志/缓存累积场景 | 内存数据库、无持久化数据的服务 |
| CONFIRM_DELETE 令牌 | 所有危险操作（删除表、清空数据、VACUUM） | 普通增删改查、只读操作 |
| SQLAlchemy Inspector 反射 | 动态表结构查询、未知表浏览 | 已知表结构（应直接用 ORM 模型） |
| VACUUM AUTOCOMMIT | SQLite 数据库压缩 | MySQL（用 OPTIMIZE TABLE）、PostgreSQL（用 VACUUM） |
| 应用层级联删除 | 需要精细控制级联策略的场景 | 简单外键关系（可用数据库级 ON DELETE CASCADE） |
| 敏感字段动态脱敏 | 表结构动态变化的场景 | 固定表结构（可用静态字段名匹配） |

### 维度 8：SonarQube 迭代闭环与三层测试验证（2026-07-18 复盘）

> 以下复盘基于 2026-07-18 SonarQube MCP 扫描（23 个 OPEN 问题→0）+ pytest 146 单元测试 + Playwright E2E 12/12 PASS 的完整迭代闭环。

**成功执行任务的完整步骤**（7 步 SQ-Loop 模式）：

1. 启动 SonarQube MCP 扫描：配置 projectKey/sources/exclusions
2. 等待分析完成：轮询 `tasks/search` API status=SUCCESS
3. 拉取问题：通过 `issues/search` API 获取 23 个 OPEN 问题
4. 问题分类（按 severity）：BLOCKER/CRITICAL → P0 必修；MAJOR → P1 应修；MINOR → P2 建议；INFO → P3 记录
5. 按问题类型应用修复模式：
   - 认知复杂度超标 → 抽取辅助函数（如 `_validate_tunnel_config`）
   - 冗余正则组 → 改为非捕获组 `(?:...)`
   - 未使用导入/变量 → 直接删除
   - async-no-await → 转同步函数（如 `async def mask_secret` → `def mask_secret`）
   - DOM API 废弃 → 替换为新 API（`removeChild` → `remove`）
   - 空 catch 块 → 添加 logger.exception 或显式注释
   - if/elif 链 → 数据驱动重构（`list[tuple]` + 循环）
6. 单元测试验证：`pytest --asyncio-mode=auto` → 146 PASS
7. 二次扫描回归：验证 OPEN 问题数 = 0，且无新增问题

**Playwright E2E 验证（12/12 PASS）**：
- API 健康检查 + 登录功能 + 内容审核 + 广告素材 + 统计 + 工作流 + 数据库维护 + 系统清理 + AI 配置 + 内网穿透 + 7 个 GET API 端点

**不确定性与失败点**：

| 失败点 | 根因 | 修复方式 | 对应规范 |
|--------|------|----------|----------|
| SonarQube scanner 路径错误 | SONAR_SCANNER_HOME 环境变量未配置 | 配置环境变量或使用 MCP 包装的扫描命令 | 75 SQ 闭环 |
| SONAR_TOKEN 缺失 | Token 未生成或未配置 | 在 SonarQube 控制台生成 token 并配置环境变量 | 75 SQ 闭环 |
| 单次修复后二次扫描出现新问题 | 修复方式引入新缺陷（如改 async 为 sync 后调用方未同步更新） | 二次扫描回归验证；max_regression_retries 控制 | 75 SQ 闭环 |
| exe 模式 vs 开发模式行为差异 | exe 模式下代码修改不生效，需重新构建 | 测试前确认当前模式；exe 模式触发重新构建 | 60 三层测试 |
| API 登录协议错误 | 测试脚本默认 form-urlencoded，但后端要 JSON | 用 JSON body + `Content-Type: application/json` | 60 三层测试 |
| 路由路径错误 | 测试脚本硬编码路径与实际路由前缀不一致 | 启动时验证路由前缀与实际一致 | 60 三层测试 |

**可抽象的固定流程**：

1. **SonarQube 迭代闭环**（SQ-Loop 模式）：扫描 → 等待 → 拉取问题 → 分类 → 修复 → 单元测试 → 二次扫描回归（详见规范 75）
2. **认知复杂度治理**：检测 → 定位热点 → 抽取辅助函数 / 数据驱动重构 → 验证复杂度 ≤ 15（详见规范 66）
3. **数据驱动重构模式**：识别 if/elif 链 → 提取 `list[tuple]` → 循环匹配 → 配置化（详见规范 71）
4. **三层测试验证**：单元测试 → 集成测试 → E2E 测试 → SQ 二次扫描（详见规范 60）

**适用场景与不适用场景**：

| 流程 | 适用场景 | 不适用场景 |
|------|---------|------------|
| SQ-Loop 闭环 | 发版前完整验证；已集成 SonarQube 的项目 | 热修复（hotfix）；未集成 SQ 的项目 |
| 认知复杂度治理 | 业务逻辑复杂的 service/workflow 层 | 纯数据声明的 models 层；配置常量文件 |
| 数据驱动重构 | 分支数 ≥3 且处理逻辑相似的函数 | 分支逻辑差异大；仅 1-2 个分支 |
| 三层测试验证 | 中大型项目（≥10 个 API 端点）的发版前验证 | 小型项目（<5 个端点）；hotfix |

**新增编码规范**（S51-S60 + R66-R75）：
- S51/R66：认知复杂度阈值治理
- S52/R67：async 函数必须含 await
- S53/R68：正则表达式捕获组优化
- S54/R69：list() 调用必要性检测
- S55/R70：未使用变量、参数与导入检测
- S56/R71：数据驱动重构模式
- S57/R72：import 语句组织规范
- S58/R73：DOM API 现代化规范
- S59/R74：空 except 块禁止规范
- S60/R75：SonarQube 扫描闭环规范 + 三层测试验证规范

**配置驱动原则**：所有新规范的阈值参数（max_function_lines/max_nesting/max_cognitive_complexity/min_elif_count/min_unit_coverage 等）均通过 `project-config.json#coding_standards`、`project-config.json#sonarqube`、`project-config.json#testing` 配置，不同项目可调整阈值不需修改技能代码。

### 附录：20_News 编码规范与部署标准

### 一、数据库与数据初始化

#### 1.1 数据库路径一致性

**问题背景**：开发态（ackend/data/news.db）与 exe 部署态（dist/20-news/data/news.db）使用不同数据库文件，导致数据隔离、登录失败。

**规范**：
- 所有数据库路径必须通过 pp.paths.resolve_db_path() 统一解析
- 
esolve_db_path() 根据运行模式（frozen/dev）自动选择正确路径
- 禁止在代码中硬编码数据库路径

#### 1.2 首次启动自动建表

**规范**：
- 在 FastAPI lifespan 中调用 _init_sqlite_schema() 执行 Base.metadata.create_all()
- 所有 ORM 模型必须在调用前通过 rom app import models 导入
- SQLite 索引名需规范化（加表名前缀）以适配全局唯一约束

#### 1.3 默认数据 Seed

**规范**：
- 所有需要初始数据的场景（如管理员账户、系统配置）必须在 lifespan 中执行 seed
- Seed 逻辑必须是幂等的（检查是否存在，存在则跳过）
- 密码必须使用 hash_password() 哈希后存储，禁止明文
- 默认凭证通过配置管理，不在代码中硬编码

**示例**：
```python
async def _seed_default_admin() -> None:
    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM admin_user WHERE username = ?', ('admin',))
        if cur.fetchone()[0] > 0:
            return  # 幂等：已存在则跳过
        cur.execute(
            'INSERT INTO admin_user (username, password_hash, role, status, nickname) VALUES (?, ?, ?, 1, ?)',
            ('admin', hash_password('admin123'), 'admin', 'Admin'),
        )
        conn.commit()
    finally:
        conn.close()
```

#### 1.4 数据库模型设计

**规范**：
- 使用 SQLAlchemy ORM 声明式基类
- 所有表必须包含 created_at、updated_at 时间戳
- 状态字段使用 CHECK 约束（如 status IN (0,1)）
- 角色字段使用 ENUM 或 CHECK 约束限制取值
- 唯一约束明确声明（如 unique=True）


### 二、多模式部署

#### 2.1 部署模式识别

项目支持三种运行模式：
1. **Dev 模式**：python backend/launcher.py，使用 .venv 或系统 Python
2. **Dev-sys 模式**：同上，但不强制 venv
3. **Exe 模式**：dist/20-news/20-news.exe，PyInstaller 打包

**规范**：
- 每种模式的数据库路径、配置加载路径必须正确解析
- 通过 sys.frozen 判断是否为 PyInstaller 打包模式
- 工作目录切换至 exe 同级目录，确保相对路径正确

#### 2.2 启动脚本规范

**规范**：
- 使用 launcher.py 作为统一入口，处理路径配置和环境初始化
- 启动脚本（start.ps1）必须包含健康检查逻辑（等待 30 秒）
- 启动脚本必须写入 PID 文件供后续管理（stop.ps1）
- 健康检查 URL 必须可配置（从 .env 读取 APP_HOST/APP_PORT）

#### 2.3 构建流水线

**规范**：
- uild-exe.ps1 负责：venv 创建、依赖安装、前端构建、PyInstaller 打包、资源复制
- 构建完成后必须执行 seed 步骤（初始化默认数据）
- 安装包（Inno Setup）必须排除 data\*、.env、logs\*
- 预创建运行时目录（data/、logs/），标记 uninsneverdelete


### 三、环境配置管理

#### 3.1 配置文件结构

**规范**：
- 所有配置通过 .env 文件管理，不硬编码
- .env.example 提供模板，.env 不入库
- 使用 pydantic-settings 的 BaseSettings 加载配置
- 敏感信息（JWT_SECRET、API_KEY）必须有占位符提示

#### 3.2 配置分类

| 类别 | 配置项 | 说明 |
|------|--------|------|
| 应用 | APP_ENV, APP_HOST, APP_PORT | 运行模式与网络绑定 |
| 数据库 | SQLITE_DB_PATH, SQLITE_JOURNAL_MODE | SQLite 嵌入式配置 |
| 缓存 | CACHE_DEFAULT_TTL_SEC, CACHE_MAXSIZE | 进程内 TTLCache |
| JWT | JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_DAYS | 认证令牌 |
| 微信 | WX_APPID, WX_SECRET | 小程序配置 |
| LLM | LLM_API_KEY, LLM_BASE_URL, LLM_MODEL | AI 服务 |
| TTS | ALIYUN_TTS_API_KEY, ALIYUN_TTS_VOICE | 语音合成 |
| COS | COS_SECRET_ID, COS_SECRET_KEY, COS_BUCKET | 对象存储 |
| 通知 | ALERT_WECOM_WEBHOOK, ALERT_SMS_* | 告警通道 |
| 日志 | LOG_LEVEL, LOG_DIR | 日志配置 |

#### 3.3 配置加载优先级

1. .env 文件（最高优先级）
2. pydantic-settings 默认值
3. 环境变量（最低优先级）


### 四、安全认证

#### 4.1 JWT 设计

**规范**：
- 无状态本地验签（性能优），仅登出/强制下线时写黑名单
- payload 包含 jti（唯一 ID）用于黑名单定位
- C 端有效期 7 天，B 端有效期 2 小时
- token_type 区分 C 端（user）和 B 端（admin）

#### 4.2 密码存储

**规范**：
- 使用 bcrypt 加盐哈希（cost=12）
- 禁止明文存储密码
- 密码验证使用 erify_password() 统一处理

#### 4.3 权限控制

**规范**：
- B 端角色分为 admin（超管）和 operator（运营）
- 通过 get_current_admin 依赖注入获取当前管理员
- 状态为 0 的账户禁止登录

### 五、前后端交互

#### 5.1 API 设计规范

**规范**：
- B 端接口前缀：/admin/api/v1/
- C 端接口前缀：/api/v1/
- 统一响应格式：{code: 0, message: 'success', data: {...}}
- 错误码：0 成功，非 0 失败

#### 5.2 前端请求封装

**规范**：
- 使用 axios 实例统一配置 baseURL 和 timeout
- 请求拦截器自动注入 Bearer token
- 响应拦截器解包统一响应格式
- 401 自动跳转登录，403 提示无权限

#### 5.3 SPA 部署

**规范**：
- 前端构建产物复制到 dist/20-news/admin-web/dist/
- FastAPI 通过 StaticFiles 挂载静态资源
- SPA history 模式 fallback 到 index.html
- API 路径不被 fallback 覆盖（检查 ull_path.startswith(('api/', 'admin/api/'))）


### 六、代码审查要点

#### 6.1 数据库审查
- [ ] 是否通过 
esolve_db_path() 获取数据库路径
- [ ] 是否包含 seed 逻辑（首次启动自动创建必要数据）
- [ ] Seed 逻辑是否幂等
- [ ] 密码是否使用 bcrypt 哈希
- [ ] 表结构是否包含时间戳和约束

#### 6.2 部署审查
- [ ] 启动脚本是否包含健康检查
- [ ] 构建流程是否执行 seed 步骤
- [ ] 安装包是否排除敏感文件和用户数据
- [ ] 是否支持 dev/exe 双模式

#### 6.3 安全审查
- [ ] 是否硬编码敏感信息
- [ ] JWT 配置是否从 .env 加载
- [ ] 密码验证是否使用统一函数
- [ ] 权限控制是否完整

#### 6.4 前后端交互审查
- [ ] API 路径是否符合规范
- [ ] 响应格式是否统一
- [ ] 前端是否正确处理 401/403
- [ ] SPA 部署是否正确配置 fallback

### 七、不适用场景

以下情况不适用本规范：
- 不使用 SQLite 的项目（使用 MySQL/PostgreSQL 等）
- 不涉及多模式部署的项目（仅单一部署方式）
- 不需要用户认证的系统
- 前端非 SPA 架构的项目


