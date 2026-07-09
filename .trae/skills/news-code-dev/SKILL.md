---
name: "news-code-dev"
description: "20_News 项目的标准化开发技能，覆盖后端(FastAPI/SQLAlchemy)、前端(Vue 3/Element Plus/小程序)、工作流编排(LLM/TTS)、测试、优化和缺陷修复。当用户要求'开发新功能/添加接口/修改代码/修复bug/重构/优化性能/写测试'时调用。"
whenToUse: "需要开发新功能、修复缺陷、优化代码或编写测试时使用"
triggers: "开发新功能/添加接口/修改代码/修复bug/重构/优化性能/写测试 | 开发/实现/添加/修改/修复/优化/重构 | 后端/前端/小程序/工作流/测试 开发 | 这段代码怎么写/怎么改/怎么优化"
version: "1.0.0"
updated: "2026-07-10"
config: "config/project-config.json"
---

# 20_News 项目开发技能

AI 驱动的播客新闻分发平台标准化开发技能。

## 项目背景速查

| 维度 | 内容 |
|------|------|
| 产品定位 | AI 驱动的播客新闻分发平台 |
| 后端技术 | Python 3.11 + FastAPI + SQLAlchemy 2.0 + aiomysql + Redis + APScheduler |
| 前端技术 | Vue 3 + Element Plus + Vite + Pinia |
| 小程序 | 微信小程序原生（JS/WXML/WXSS） |
| AI 服务 | 通义千问 LLM + 阿里云 TTS + 腾讯云 COS |
| 部署方式 | Docker Compose（nginx/app/mysql/redis） |
| 核心链路 | RSS/搜索抓取 → LLM 改写 → TTS 合成 → 音频拼接 → 审核发布 → 小程序播放 |

## 技术栈速查

### 后端
- **框架**：FastAPI（异步）
- **ORM**：SQLAlchemy 2.0（async）
- **数据库**：MySQL（aiomysql 驱动）
- **缓存**：Redis（redis.asyncio）
- **调度**：APScheduler（AsyncIOScheduler）
- **HTTP 客户端**：httpx（AsyncClient）
- **测试**：pytest + aiosqlite + fakeredis

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
│   ├── meta-rules.md                 ← 20 条元规范（配置驱动/异步安全/JWT 安全等）
│   ├── faq.md                        ← 10 个常见问题解答
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
| [meta-rules.md](references/meta-rules.md) | 20 条元规范（含 grep 判断信号） |
| [faq.md](references/faq.md) | 添加 API/数据库表/工作流步骤/修改 Prompt 等 |

## 工作流元规范速查

以下是 20 条核心元规范的精简版，详细规则请参考 [meta-rules.md](references/meta-rules.md)。

| # | 规范 | 适用场景 | 判断信号（grep） | 优先级 |
|---|------|----------|------------------|--------|
| 1 | 配置驱动 | 后端所有服务 | 搜索具体值如 `3600`、`http://` | CRITICAL |
| 2 | 复用优先 | 新增功能 | 发现相似业务逻辑 | HIGH |
| 3 | 错误分类 | 所有 API | except 统一返回 500 | HIGH |
| 4 | 资源生命周期 | 异步任务/锁/连接 | 资源创建后无清理 | HIGH |
| 5 | 异步安全 | 异步代码 | `create_task(` 无赋值、`requests.get` | CRITICAL |
| 6 | 迁移幂等 | 数据库迁移 | 无 `IF NOT EXISTS` | HIGH |
| 7 | JWT 安全 | Token 验证 | `token ==` 而非 `hmac.compare_digest` | CRITICAL |
| 8 | 时间 UTC | 所有时间字段 | `datetime.now()`、`datetime.utcnow()` | HIGH |
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

### 维度 2：编码规范

**做得好的**：
- 类型注解覆盖全面，便于 mypy/ruff 静态检查
- 异步规范统一（async/await + httpx.AsyncClient + aiomysql）
- 错误分类清晰（AuthError/BusinessError/SystemError），前端解析方便
- 日志规范统一（结构化日志 + traceback 保留）

**待改进的**：
- 日志格式可进一步 JSON 化，便于 ELK 采集
- 需要补充代码审查 checklist（PR 模板）
- 前端组件拆分粒度需要统一标准（单一职责 vs 组合组件）

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
- 需要建立正式的代码审查流程（PR template + review checklist）
- 需要补充 Git 分支管理规范（git-flow/trunk-based）
- 需要定义发布流程和回滚机制（灰度发布 + 快速回滚）
- 需要建立监控告警体系（SLO/SLI + 告警分级）
