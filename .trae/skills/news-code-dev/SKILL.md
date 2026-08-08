---
name: "news-code-dev"
description: "MorningBrief 项目的标准化开发技能，覆盖后端(FastAPI/SQLAlchemy)、前端(Vue 3/Element Plus/小程序)、工作流编排(LLM/TTS)、测试、优化和缺陷修复。同时包含 20_News 项目编码规范与部署标准（数据库初始化、多模式部署、环境配置、安全认证、前后端交互）。当用户要求'开发新功能/添加接口/修改代码/修复bug/重构/优化性能/写测试/部署排查'时调用。"
whenToUse: "需要开发新功能、修复缺陷、优化代码或编写测试时使用"
triggers: "开发新功能/添加接口/修改代码/修复bug/重构/优化性能/写测试/部署排查 | 开发/实现/添加/修改/修复/优化/重构/部署 | 后端/前端/小程序/工作流/测试/数据库 开发"
version: "3.2.0"
updated: "2026-08-05"
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

## 文档结构

```
news-code-dev/
├── SKILL.md                          ← 你在这里
├── config/project-config.json        ← 项目配置（路径/技术栈/硬约束）
├── references/
│   ├── meta-rules.md                 ← 元规范详解（grep 判断信号 + 完整规则）
│   ├── coding-standards.md           ← Python/Vue/小程序/数据库/API 规范
│   ├── architecture-patterns.md      ← 四层架构/工作流/缓存/认证/降级模式
│   ├── lessons-learned.md            ← 历史复盘与经验教训
│   ├── faq.md                        ← 常见问题解答
│   └── version-history.md            ← 版本演进记录
├── assets/
│   ├── guides/                       ← 开发指南（backend/frontend/workflow/testing）
│   ├── rules/                        ← 安全/异步/数据库/错误处理/配置驱动规则
│   └── templates/                    ← Python/Vue 代码模板
└── scripts/pre-commit-check.ps1      ← 提交前检查脚本
```

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
| [meta-rules.md](references/meta-rules.md) | 元规范详情（grep 判断信号 + 完整规则 + 优先级） |
| [coding-standards.md](references/coding-standards.md) | Python/Vue/小程序/数据库/API 契约详细规范 |
| [architecture-patterns.md](references/architecture-patterns.md) | 四层架构/工作流编排/缓存模式/认证模式/降级模式 |
| [lessons-learned.md](references/lessons-learned.md) | 历史复盘经验教训 |
| [faq.md](references/faq.md) | 添加 API/数据库表/工作流步骤/修改 Prompt 等常见问题 |

## Input / Output 契约

### Input
- **必填**：开发任务描述（功能需求/bug 描述/重构目标）
- **可选**：目标文件路径（不提供则根据任务自动定位）、修改范围限制（仅后端/仅前端/仅小程序）

### Output
- 修改后的代码文件（直接编辑）
- 如涉及数据库变更，附带迁移说明
- 如涉及前端变更，附带构建验证结果

## 执行步骤

1. **理解需求**：明确用户的目标（新功能/修复/重构），确认影响范围
2. **定位代码**：通过 grep/SearchCodebase 定位相关文件，读取上下文
3. **遵循规范**：对照下方核心规则速查表，逐条检查是否违反任何 CRITICAL/HIGH 规则
4. **执行修改**：优先编辑现有文件，最小化改动，遵循"为什么"注释原则
5. **验证**：后端修改后运行 py_compile，前端修改后运行 vite build，确认无语法错误

## 失败处理

| 失败场景 | 判断信号 | 处理方式 |
|----------|----------|----------|
| 规则冲突 | 两条 CRITICAL 规则同时适用 | 优先遵循编号更小的规则，记录冲突供人工评审 |
| 文件定位失败 | grep/SearchCodebase 无结果 | 先查 [faq.md](references/faq.md)，仍无解则请求用户指定文件 |
| 硬编码风险 | 修改中出现具体数值/URL/路径字面量 | 立即中止，引导到 config/project-config.json 或 settings.py |
| 数据库变更 | 涉及 models/*.py 修改 | 检查需要幂等迁移（PRAGMA table_info 检测），检查主从表级联清理 |
| 第三方库版本 | 添加新依赖 | 检查 [coding-standards.md](references/coding-standards.md) 版本约束 |

## 核心规则速查

以下为项目编码规范的精简速查（规则持续增补，当前 #1–#199），详细规则和完整上下文请参考 [meta-rules.md](references/meta-rules.md) 与 [diagnostic-standards.md](references/diagnostic-standards.md)。

| # | 规范 | 判断信号（grep） | 优先级 |
|---|------|------------------|--------|
| 1 | 配置驱动 | 搜索具体值如 `3600`、`http://` | CRITICAL |
| 2 | 复用优先 | 发现相似业务逻辑 | HIGH |
| 3 | 错误分类 | except 统一返回 500 | HIGH |
| 4 | 资源生命周期 | 资源创建后无清理 | HIGH |
| 5 | 异步安全 | `create_task(` 无赋值、`requests.get` | CRITICAL |
| 6 | 迁移幂等 | 无 `IF NOT EXISTS` | HIGH |
| 7 | JWT 安全 | `token ==` 而非 `hmac.compare_digest` | CRITICAL |
| 8 | 时区一致性 | `datetime.now(timezone.utc)` 与 `datetime.now()` 混用 | CRITICAL |
| 9 | 枚举 .value | `str(MyEnum.VALUE)` | MEDIUM |
| 10 | Redis Lua | 连续两次 Redis 操作 | HIGH |
| 11 | 内部接口鉴权 | 路由有 `internal` 标签但无 IP 校验 | HIGH |
| 12 | 敏感词初始化 | `AhoCorasick(` 在请求函数内 | HIGH |
| 13 | 异常不覆盖 | `class Error(Exception)` | MEDIUM |
| 14 | 日志 traceback | `logger.error(e)` 无 `exc_info` | HIGH |
| 15 | 分页必须 LIMIT | `.all()` 无 `.limit()` | HIGH |
| 16 | 前后端字段契约 | 前端使用 `snake_case` | HIGH |
| 17 | 缓存主动失效 | `redis.setex` 紧跟 `db.update` | MEDIUM |
| 18 | 工作流重试上限 | `while True` 或无 base case 的递归 | HIGH |
| 19 | 敏感信息不落地 | `logger.info.*password` | CRITICAL |
| 20 | 测试隔离 | 测试间共享全局状态 | MEDIUM |
| 23 | 时长/容量约束自动调整 | 搜索 duration 超出范围后直接 raise | CRITICAL |
| 24 | 确定性失败重试无效 | 步骤函数无外部状态依赖仍重试 | HIGH |
| 25 | 模型名称以官方为准 | 预设配置中的模型名与官网不符 | CRITICAL |
| 26 | 配置持久化完整返显 | 预设切换覆盖 API Key / 下拉框不反射 | HIGH |
| 27 | 模型定价表同步更新 | 新增模型名未同步定价表 | HIGH |
| 30 | 构建脚本并发保护 | 搜索多表删除无事务包裹 | CRITICAL |
| 31 | 启动脚本路径安全封装 | 搜索 el-table 无 selection 列 | HIGH |
| 32 | 共享构建依赖完整提取 | 搜索静态路由在动态路由之后 | CRITICAL |
| 33 | 时区一致性全局统一 | `datetime.now(timezone.utc)` 与 `datetime.now()` 混用 | CRITICAL |
| 34 | 主从表级联清理完整性 | `delete(Model)` 后无对从表的 update/delete | CRITICAL |
| 35 | 0 结果容错分支 | `if count == 0: raise` 无 fallback 检查 | HIGH |
| 36 | 动态注入而非硬编码条件 | `if config_flag and not template_text` 多条件跳过 | HIGH |
| 37 | 选题后关联关系更新 | `select(Material)` 后无 `update(Material).workflow_id=` | HIGH |
| 38 | blob/二进制响应错误解析 | `responseType: 'blob'` 无 `parseBlobError` | HIGH |
| 39 | 频道级配置覆盖全局 | `settings.X` 无 `if ch.x is not None` | HIGH |
| 40 | 定时任务频道级触发 | `_cron_trigger` 无遍历活跃频道列表 | HIGH |
| 41 | el-switch 类型契约 | `<el-switch` 无 `:active-value` 且后端字段为 int | HIGH |
| 42 | v-loading 状态恢复 | `handleVisibilityChange` 直接调用 load 无 nextTick | HIGH |
| 44 | 环境隔离与 URL 配置化 | 搜索 http://localhost 或 127.0.0.1 出现在代码中 | CRITICAL |
| 45 | 小程序页面四件套完整 | 页面目录缺少 .json/.js/.wxml/.wxss | HIGH |
| 46 | 事件绑定对称性 | 搜索 onPlay 无对应 offPlay 在 onUnload 中 | HIGH |
| 47 | 模型字段名验证 | 搜索 Workflow.workflow_id 等不存在的字段名 | CRITICAL |
| 48 | 统计口径校验 | 搜索 sum(PlayLog.duration) 用于统计实际收听时长 | HIGH |
| 50 | 频道级数据隔离严格性 | `OR.*channel_id IS NULL` 或 `channel_id.is_(None)` 兜底 | CRITICAL |
| 53 | RSS 源可达性诊断流程 | HTTP 200 但 feedparser 解析 0 条目 | HIGH |
| 55 | 频道级配置与素材同步 | 修改 rss.yaml name 后未同步数据库 channel.rss_sources | HIGH |
| 56 | SQLAlchemy Inspector run_sync 陷阱 | `run_sync` 回调内使用 `inspect(` 但无 `.connection()` 转换 | CRITICAL |
| 57 | main.py 导入完整性 | main.py 使用 RequestIdMiddleware 等符号但无对应 import | CRITICAL |
| 58 | CONFIRM_DELETE 令牌双重确认 | 危险操作端点未校验 `confirm_token` 参数 | CRITICAL |
| 59 | 敏感字段动态脱敏 | 导出函数无脱敏逻辑，或仅静态字段名匹配 | HIGH |
| 60 | 应用层级联删除策略 | `db.delete(main)` 后无对从表的 cascade/set_null 处理 | CRITICAL |
| 61 | VACUUM AUTOCOMMIT 模式 | `VACUUM` 在 `async with session.begin()` 事务块内 | CRITICAL |
| 62 | bindparam expanding IN 列表 | `IN (` 后跟字符串拼接而非 `bindparam(expanding=True)` | HIGH |
| 63 | 数据库维护白名单机制 | 表操作未检查白名单 | CRITICAL |
| 64 | dry_run 预览模式 | 清理函数不支持 `dry_run=True` 参数 | HIGH |
| 65 | 审计日志完整覆盖 | `db.delete` 后无 `audit_log` 记录 | HIGH |
| 66 | 认知复杂度阈值治理 | 函数行数>50 且嵌套>3 层；ruff C901 | CRITICAL |
| 67 | async 函数必须含 await | `async def` 后 50 行内无 `await`；SonarQube S7503 | CRITICAL |
| 68 | 正则表达式捕获组优化 | `re.match` 中 `(...)` 后续无 `group(N)`；SonarQube S6395 | HIGH |
| 70 | 未使用变量/参数/导入检测 | ruff F841/F401；SonarQube S1481/S1128 | HIGH |
| 71 | 数据驱动重构模式 | 同一函数内 ≥3 个 elif；函数行数>50 | HIGH |
| 72 | import 语句组织规范 | eslint `import/order`；isort I001；SonarQube S3863 | MEDIUM |
| 73 | DOM API 现代化规范 | `removeChild(`/`appendChild(`/`className =`；SonarQube S7762 | HIGH |
| 74 | 空 except 块禁止规范 | `except: pass` 或空 except 块；SonarQube S2486 | HIGH |
| 75 | SonarQube 扫描闭环规范 | 二次扫描 OPEN>0 或有新增问题 | CRITICAL |
| 76 | 含非 ASCII 字符的 URL 必须 encodeURI | `audioManager.src =` 后无 `encodeURI`；URL 含中文 | CRITICAL |
| 77 | iOS 倍速切换必须 pause+play+seek | `audioManager.playbackRate =` 后无 `pause()` | HIGH |
| 78 | onTimeUpdate 必须 setData 节流 | `onTimeUpdate` 内每次 `setData` 无时间戳判断 | HIGH |
| 79 | 异步上报必须有 in-progress 防重叠标志 | `reportProgress` 函数无 `if (progressReporting) return` | HIGH |
| 80 | seek 必须用 pendingSeek 标志位 | `onCanplay.*=>.*seek\(` 自清理模式 | HIGH |
| 82 | 列表页与详情页布局必须分离 | 列表页内 `<block wx:else>` 内嵌播放卡片 | HIGH |
| 83 | 频道/筛选切换必须清空关联状态 | `currentChannelId =` 后无清 `script`/`segments`/`comments` | HIGH |
| 84 | 跳转播放详情前必须 resumePlay 恢复 | `wx.navigateTo.*detail` 前无 `resumePlay()` | HIGH |
| 85 | 数据结构变更时 cache_key 加版本后缀 | `cache_key = f"...:{episode_id}"` 无 `:v{n}` 后缀 | HIGH |
| 86 | 跨项目模块迁移 7 步法 | 跳过架构对齐/测试执行/构建验证任一步骤 | HIGH |
| 87 | 前端嵌套目录相对路径校验 | `@use '../styles/'` 或 `import '../utils/'` 在 views 子目录下 | CRITICAL |
| 88 | UI 图标跨库迁移存在性验证 | 跨 UI 库图标迁移引用不存在的图标名 | HIGH |
| 89 | 模块级单例缓存测试隔离 | 测试用例间共享 TTLCache 模块级单例无 `_reset_cache_for_test()` | HIGH |
| 90 | 多版本 Python 环境测试执行 | `python -m pytest` 报 No module named pytest | HIGH |
| 91 | 图片封面三级 fallback 提取 | grep `og:image` 后无 `elif`/`try/except` fallback 逻辑 | HIGH |
| 92 | 装饰图过滤规则 | `cover_url` 提取逻辑无装饰图过滤（无 keyword_blacklist 检查） | HIGH |
| 93 | FALLBACK_DAYS 动态计算 | grep `FALLBACK_DAYS` 为硬编码数字 | HIGH |
| 94 | LLM 语义过滤 fallback | 关键词过滤后无 LLM fallback 分支 | CRITICAL |
| 95 | LLM 字数达标约束 | LLM 调用后无字数验证逻辑 | CRITICAL |
| 96 | BGM 时长不足兜底 | BGM 拼接逻辑无时长不足处理 | HIGH |
| 97 | 菜单分组与角色可见性 | 菜单数量 ≥10 但无 `meta.group` 字段 | HIGH |
| 98 | PWA 图标生成与 MIME 注册 | `manifest.json` 无 `maskable` purpose | HIGH |
| 99 | 关键指标监控告警 | 关键业务流程无 WARNING 阈值判断 | HIGH |
| 100 | 批量数据回填脚本规范 | ORM 模型新增字段但无对应 `backfill_*.py` 脚本 | HIGH |
| 101 | Page 对象方法名唯一性 | Page({}) 内 `onLoad` 出现两次或与 `bindload` 同名 | CRITICAL |
| 102 | list 接口批量关联覆盖 | `list_*` 返回 `c.user_name` 但未批量查 User 表覆盖 | HIGH |
| 103 | 微信 2.27+ 头像获取方式 | `wx.getUserProfile` 在新代码中 | CRITICAL |
| 104 | 小程序外链跳转 ActionSheet 兜底 | `wx.navigateTo.*webview` 后无 `wx.showActionSheet` 兜底 | HIGH |
| 105 | wxml 类名 wxss 定义对齐 | .wxml 引用的 class 在对应 .wxss 中无定义 | HIGH |
| 106 | 聚合列表序号独立计数 | `sources.append.*seq.*seg.get` 复用外部 seq | HIGH |
| 107 | 临时图片资源持久化 | `chooseAvatar`/`chooseImage` 后无 `wx.saveFile` 持久化 | MEDIUM |
| 108 | 列表页与详情页布局一致性 | 首页用 `.episode-row-card` 但历史页用 `.history-item` | HIGH |
| 109 | 多 Provider 抽象基类 + 工厂注册表 | `if provider ==` 多分支调用不同服务商 | CRITICAL |
| 110 | 自动降级链路设计 | `try.*except.*raise` 外部服务调用无 fallback 分支 | CRITICAL |
| 111 | 凭证 fallback 链模式 | `SECRET_ID.*=` 独立配置项未实现 fallback | HIGH |
| 112 | 第三方库版本兼容性预检 | requirements.txt 版本号与 PyPI 最新版差异大 | HIGH |
| 113 | 音色/模型语义映射 | `voice.*=` 前端硬编码各 provider 的音色 ID | HIGH |
| 116 | TC3-HMAC-SHA256 签名实现 | `tencentcloudapi.com` 但无 tencentcloud SDK 依赖 | CRITICAL |
| 117 | tenacity+Semaphore+check_budget 三层防护 | `retry(` 无 Semaphore 或 check_budget 调用 | CRITICAL |
| 127 | 外部服务降级本地存储模式 | `cos_client.put_object` 后无 try/except fallback | CRITICAL |
| 129 | 本地路径 URL 约定 | `download_file(url)` 无 `url.startswith('/audio/')` 分支 | HIGH |
| 130 | UI 异常环境隔离验证流程 | UI 异常直接进入代码修复而无三步验证 | CRITICAL |
| 134 | blur/visibilitychange 联合判断 | 单独 `addEventListener('blur')` 判定页面隐藏 | HIGH |
| 135 | SSE 隐藏断开机制 | `new EventSource(...)` 无 visibilitychange/blur 监听断开 | HIGH |
| 140 | el-switch 双向绑定值类型契约 | `<el-switch` 无 `:active-value` 且后端字段为 int | CRITICAL |
| 141 | 请求级超时覆盖全局 | `api.post` 无 `{ timeout: }` 且接口含 AI/上传/批量 | HIGH |
| 144 | Pydantic Body 字段声明完整性 | `class.*Body.*BaseModel` 缺少前端已提交的字段声明 | CRITICAL |
| 145 | 前端图标库版本可用性预检 | `meta.icon` 引用图标名在 `@element-plus/icons-vue` 中不存在 | HIGH |
| 146 | Vue Router query 跨页参数同步 | `router.push` 无 `query` 或目标页 `onMounted` 无 `route.query` | HIGH |
| 147 | 配置键命名一致性 | `CONFIG_KEY_MAP` 含 `edge_tts_*` 与 `edge_*` 混用 | CRITICAL |
| 148 | 工作流时间本地化一致性 | `datetime.now(timezone.utc)` 用于前端显示 | HIGH |
| 149 | 命令链语法适配 | `&&` 在 PS5 中不可用 | CRITICAL |
| 150 | 模块级函数对称性 | `from module import func_a, func_b` 但 func_b 未定义 | HIGH |
| 151 | 服务重启加载新代码验证 | 修改路由文件后未重启服务就测试新端点 | CRITICAL |
| 152 | API 认证验证矩阵 | 仅测试带 token 而未测试 401 拦截 | HIGH |
| 153 | 参考实现移植适配检查 | 移植代码保留源项目命名约定未适配 | HIGH |
| 154 | 测试三阶段执行 | 跳过静态/运行时/功能任一阶段直接交付 | CRITICAL |
| 156 | 配置项全链路注册 | config.py 新增字段但缺任一端注册 | CRITICAL |
| 157 | 估算参数与实际产出联动 | 估算公式中不含实际产出参数（如语速倍率） | CRITICAL |
| 158 | 校验范围动态计算 | grep `MIN_DURATION_SEC = 200` 等硬编码范围常量 | CRITICAL |
| 159 | 错误诊断信息完整性 | `raise.*Error.*超出.*范围` 但无目标值/配置来源 | HIGH |
| 160 | 前端 computed 命名避让内置属性 | computed 名称与 el-* 组件内置 prop 同名 | HIGH |
| 161 | 修改后双重验证流程 | 修改 .py 后未 py_compile / 修改 .vue 后未 vite build | CRITICAL |
| 162 | SQLite func.now() 时区一致性 | `server_default=func.now()` | CRITICAL |
| 163 | 去重表与业务表联动清理 | `DELETE FROM material` 后无 `DELETE FROM crawler_dedup` | HIGH |
| 164 | 当日查询 0 结果回溯 fallback | `if not rows:` 后直接 `raise` 无回溯查询 | HIGH |
| 165 | PowerShell Python 内联代码禁用 r-string | `python -c.*r['\"]` 在 .ps1/.bat 脚本中 | HIGH |
| 166 | sqlite3 表结构预检查 | `cursor.execute.*SELECT.*FROM` 前无 `PRAGMA table_info` | HIGH |
| 167 | SQLite 数据库锁诊断流程 | `database is locked` 异常处理无重试逻辑 | HIGH |
| 168 | 前端列表空数据分层诊断 | 前端空数据直接定性为渲染 bug 无分层诊断 | HIGH |
| 169 | stitch 时长不足兜底 | `duration < low` 后直接 `raise` 无兜底 | HIGH |
| 170 | SQLite 时间字段写入显式赋值 | `mapped_column.*default=func.now` 时间字段未显式赋值 | CRITICAL |
| 171 | 小程序用户态数据双层同步 | `app.globalData.userInfo =` 后无 `setToken` | CRITICAL |
| 172 | Pydantic Settings 单例导入模式 | `from app.config import settings`（直接导入实例） | HIGH |
| 173 | 统一响应模式测试断言对齐 | 测试中 `assert resp.status_code == 400` 或 `== 422` | HIGH |
| 174 | 小程序原生代码 4 维静态验证 | 修改 miniprogram/*.js 未做 4 维验证 | HIGH |
| 175 | 前后端字段契约验证清单 | 前端用后端不返回的字段名 | HIGH |
| 176 | 文件上传安全双重校验 | `UploadFile` 无扩展名白名单或无 content_type 校验 | CRITICAL |
| 177 | 小程序进度上报条件容错 | `if (duration <= 0) return` 在进度上报函数中 | HIGH |
| 178 | UNIQUE 约束冲突 IntegrityError 兜底 | `db.add()` 或 `db.flush()` 后无 `except IntegrityError` | HIGH |
| 179 | 状态属性与标志位一致性 | `def status` 属性中直接查询外部状态无标志位检查 | HIGH |
| 180 | 音频队列自动播放 | `onEnded` 无 `playNext` 调用 | MEDIUM |
| 181 | 工作流 0 结果阻断+失败详情可见 | `material_count == 0` 后无 `raise RuntimeError` | CRITICAL |
| 182 | 小程序分包配置校验 | app.json pages 路径以 subPackages[].root 为前缀 | HIGH |
| 183 | HTTP 编码探测 fallback | `resp.text` 或 `resp.encoding` 无 charset_normalizer fallback | HIGH |
| 184 | 启停脚本 PID 文件三级兜底 | stop 脚本仅用 PID 文件查找进程无兜底 | HIGH |
| 185 | 风格库顺序轮换去重 | `random.choice` 或 `candidates[0]` 在风格库选择中 | MEDIUM |
| 186 | 打包模式路径解析 | 列表接口中 `is_cos_configured()` 已配置但无本地回退分支 | CRITICAL |
| 187 | 外部存储列表回退 | `list_audio` 本地缓存空后直接 `return []` 无 DB 远程 URL 回退 | CRITICAL |
| 188 | 同步 SDK 异步安全 | `cos_client`/`uploader` 同步调用出现在 `async def` 且非 `to_thread` | CRITICAL |
| 189 | 二进制流式响应契约 | `return success(` 包裹 `.mp3`/`.wav` 音频响应体 | HIGH |
| 190 | 音频代理 SSRF 防护 | 代理外部音频 URL 无域名白名单校验（任意 host 透传） | CRITICAL |
| 191 | 字段契约(size_bytes/远程 path) | 远程资源 `path` 未返回语义值（如 `"云端(COS)"`）/ `size_bytes` 未处理 | HIGH |
| 192 | 详情面板懒加载 | 详情页素材/TTS/成品面板一次性加载无 `activePanels` + 变更处理器 | HIGH |
| 193 | 远程音频代理播放 | 远程(云端)音频直接拼接 COS URL，未走 `proxy_audio` 端点 | HIGH |
| 194 | 远程资源删除保护 | `path` 含云端标记但仍渲染删除/本地操作按钮 | HIGH |
| 195 | 字段契约展示一致性 | 前端对 `size_bytes=0`/远程 `path` 标签未正确展示（显示为空/异常） | MEDIUM |
| 196 | frozen 模式配置加载路径解析 | `config.py` 的 `env_file` 为相对/固定路径、未用 `sys.executable` 同级解析（`sys.frozen` 时 `_MEIPASS` 无 `.env`） | CRITICAL |
| 197 | 安装包配置完整性 | `installer.iss` 的 `Excludes` 含 `.env`/密钥、或 `Source:` 未显式包含 `.env`、构建脚本未 `attrib -H` | CRITICAL |
| 198 | HLS 首播冷启动静默重试 | 小程序音频 `onError` 无静默重试分支、无 mp3 回退、首播失败即停 loading/弹错误 | HIGH |
| 199 | 微信隐私合规 scope 声明 | `setClipboardData`/`getClipboardData` 调用前未 `requirePrivacyAuthorize`、后台未声明「剪贴板」scope | CRITICAL |
| 200 | TTS 朗读禁止透传 markdown 标记 | rewriter/synthesize 输出含 `**`/`*` 等标记未 strip 即送 TTS（导致朗读星号） | HIGH |
| 201 | 列表/面板空数据分层诊断 | 面板/列表空直接改渲染，未先查数据源（查询维度 / 字段回写 / 缓存兜底） | HIGH |
| 202 | TTS 合成后 audio_url 回写 | synthesize 成功未将 COS URL 回写 `script.segments[].audio_url`（按 seg_seq 匹配） | HIGH |
| 203 | 素材池查询维度正确 | `Material.workflow_id` 过滤而忽略 `channel_id`（素材是频道级池，终态 workflow_id 置 NULL） | CRITICAL |
| 204 | 历史数据回填安全闭环 | 回填脚本无 `--dry-run` 预览 / 无自动备份 / 会删除记录 / 非幂等 | HIGH |
| 205 | broad except 保留 traceback | `except` 块用 `logger.warning("…%s",e)` 丢栈；`# NOSONAR` 写在非 `def` 行 | HIGH |
| 206 | COS list_objects 健壮性 | 列举按 `NextMarker` 续传（无 Delimiter 时不返回）；列举未 `try/except` 保护瞬时错误 | MEDIUM |
| 207 | 频道 tab 动态生成 | 前端/小程序硬编码频道名列表（非来自后端 `/channels` 动态渲染） | CRITICAL |
| 208 | 后端可控排序/开关字段全链 | 新增"运营可调、前端免发版"字段未走 model+迁移+排序返回+缓存失效+前端控件 | HIGH |
| 209 | 前端字段契约透传 | 通用 axios 包装丢后端新增 snake_case 字段；列表无展示列 / 表单无控件 | HIGH |
| 210 | 测试落盘隔离 | 测试对 `data/` 下文件 `unlink`/`write` 未重定向 `tmp_path`（被 safe-delete 守卫拦截） | HIGH |
| 211 | 全量测试 flake 判别 | 全量偶发失败直接定性回归，未先单跑失败用例判别 flake/真缺陷 | HIGH |

**SQ 闭环补充**（SonarQube 相关实践要点）：
- NOSONAR 注释必须加在 `def` 行（末行 `# NOSONAR` 不生效）
- Windows + PS5 + SQ 扫描需预检 Node 版本（v24 不兼容 SonarJS bridge）
- 子代理报告"已加 NOSONAR"但 grep 未找到时需二次扫描验证
- git stash 后测试仍失败 → 预先存在问题；通过 → 本次回归
- 真缺陷（S5446/S930/S2817/S5886）必须修复；误报（S3776/S7503/S125）可 NOSONAR

**状态分类**：CRITICAL（必须遵守）/ HIGH（强烈建议）/ MEDIUM（建议）

## 2026-08-08 会话提炼编码规范（R200–R211）

> 来源：本会话连续解决的 7 类真实问题（TTS 星号、详情页双面板空、COS 历史 audio_url 回填、
> 代码审查发现、头像测试 flake、小程序频道 tab 动态、admin-web 展示排序）。
> 以下为标准整合，每条含**判断信号 + 适用/不适用场景**，与 `news-backend-code-review`（维度 207–213）、
> `news-frontend-code-review`（FE-202–FE-205）、`news-auto-testing`（flake/隔离流程）交叉引用。

### 1. 面板/列表"显示为空"——分层诊断（R201 / R202 / R203）

**固定流程（禁止直接定性渲染 bug）**：
1. 先确认前端是否真收到空（axios 解包后 `data` 是否空、请求参数是否正确）。
2. 再查数据源：DB 该实体是否真有数据？过滤条件字段是否与存储语义匹配？
   - 素材类：是**频道级池** → 按 `channel_id` 查；`workflow_id` 在终态被置 NULL，不能用它过滤。
   - 音频类：COS 模式下本地 `tts/` 目录为空 → 必须回写 `script.segments[].audio_url`，否则详情页无兜底。
3. 最后查渲染：`wx:for` / `v-for` 遍历字段名是否与响应字段一致。

**判断逻辑**：面板空 + DB 有数据 → 不是渲染问题，是**查询维度 / 字段回写**问题；COS 已配置但 segment 无 `audio_url` → 补回写逻辑，不是"音频丢了"。

**适用**：任何"列表/面板空""数据不显示"。**不适用**：明确的 404/500 接口错误（直接查路由）。

### 2. TTS 朗读禁止透传 markdown 标记（R200）

LLM 改写输出（含 `**`/`*`/列表符）不得原样送 TTS；在 rewriter 或 synthesize 边界做 strip。
历史脏数据用 `--dry-run` 预览 + 自动备份的回填脚本清洗（见 R204）。

### 3. 历史数据回填安全闭环（R204）

回填脚本必须：`--dry-run` 预览影响面 → 自动备份 DB/文件 → 实际执行（**只填缺失、不删、幂等、分批、进度日志**）
→ 二次 `--dry-run` 复核归零。异常项单独 `try/except` 跳过，不中断整批。

### 4. 后端可控排序/开关字段全链（R207 / R208 / R209）

让"运营可调、前端免发版"的字段（如频道 `display_order`、媒体开关）落地全链：
1. model 加字段（`NOT NULL DEFAULT`，避免 NULL 排序歧义）。
2. `main.py` 幂等迁移（`PRAGMA table_info` 检测后 `ALTER TABLE ADD COLUMN`）。
3. 列表接口按该字段排序返回 + 返回体带字段。
4. Service `create`/`update` 透传 + 失效对应缓存（与 admin `cache_manager` 同一单例）。
5. 前端：列表加展示列 + 表单加控件 + 通用 axios **直传不丢字段**（snake_case）。

**判断逻辑**：改动只影响展示顺序/开关 → 优先做"后端字段 + 缓存失效"，**最小化前端改动**。
**适用**：需运营可调、前端免发版。**不适用**：纯展示性、与后端无关的 UI 状态。

### 5. 错误处理与日志（R205，强化 #14）

`except Exception` 兜底块必须 `logger.exception(...)` 保留 traceback；`# NOSONAR` 必须写在 `def` 行（末行不生效）。
预期可恢复、需吞掉的单点错误仍应 `logger.warning` 带上下文，但不得静默丢弃栈。

### 6. COS list_objects 健壮性（R206）

COS v1 `list_objects` 无 `Delimiter` 时不返回 `NextMarker` → 回退到**末位 Key** 续传；列举必须 `try/except` 保护，
瞬时错误只跳过该工作流而非中断整批回填。

### 7. 测试隔离与 flake 判别（R210 / R211，详见 news-auto-testing）

- 测试内对 `data/` 下文件的 `unlink`/`write` 必须重定向到 `tmp_path`（OS-TEMP 路径 safe-delete 守卫放行，非 TEMP 路径 FAIL CLOSED）。
- 全量偶发 1 failed：**先单跑该用例**——通过=预存 flake（顺序/共享状态）→ 修根因；失败=真缺陷→定位代码。
- 全量 pytest 前设独立 `TEMP`（如 `backend/.pytest_tmp`），避开 pytest 自身 numbered-tempdir GC 触发守卫。

## 参考

- [meta-rules.md](references/meta-rules.md) — 元规范完整规则与上下文
- [coding-standards.md](references/coding-standards.md) — 各语言详细编码规范
- [lessons-learned.md](references/lessons-learned.md) — 历史复盘与经验教训
- [diagnostic-standards.md](references/diagnostic-standards.md) — 会话复盘提炼的诊断与编码标准（DS-1~DS-16：异常处理/时区/打包回退/元数据/重命名/测试隔离/安装包图标/frozen 配置加载/安装包配置完整性/HLS 冷启动/微信隐私合规/媒体特性可开关化与真静音/枚举校验器语义对齐，含四维度复盘）
- [faq.md](references/faq.md) — 常见问题解答
- [_shared/references/](../_shared/references/) — 跨技能共享主题
