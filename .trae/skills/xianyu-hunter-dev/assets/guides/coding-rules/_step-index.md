# 编码规范索引（auto-generated）

> 本索引用于快速定位 204 step 编码规范的归档位置。
> 完整规范已按主题归档到 `assets/guides/coding-rules/` 目录下 13 个文件。
> 元规范（63 条通用规则）见 [meta-rules.md](../../../references/meta-rules.md)。

---

### 主题速查表（按主题加载）

| 主题文件 | 内容 | step 数 | step 范围 |
|---|---|---|---|
| [security.md](assets/guides/coding-rules/security.md) | 安全（token 校验/脱敏/SQL注入/外部链接/数据库写入身份隔离） | 14 | 5-204 |
| [concurrency.md](assets/guides/coding-rules/concurrency.md) | 并发（asyncio/锁/超时/降级/async-await 静态检查/外部资源生命周期配对） | 11 | 27-203 |
| [state-management.md](assets/guides/coding-rules/state-management.md) | 状态管理（一致性/同步/生命周期/状态恢复前置校验/长生命周期对象状态清理） | 22 | 11-197 |
| [error-handling.md](assets/guides/coding-rules/error-handling.md) | 错误处理（粒度/重试/dump/原因传递/降级链日志合并/HTTP 状态码精细化/异常日志语义保留） | 22 | 23-202 |
| [database.md](assets/guides/coding-rules/database.md) | 数据库（迁移/索引/SQLite/资源池基准/写入身份追溯） | 13 | 32-204 |
| [config-driven.md](assets/guides/coding-rules/config-driven.md) | 配置驱动（功能开关/全链路/阈值/字段契约/时间参数配置化） | 22 | 15-196 |
| [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) | 前端 UI（AntD/状态/三态/类型对齐） | 28 | 8-166 |
| [testing.md](assets/guides/coding-rules/testing.md) | 测试（隔离/mock/fixture/Windows 编码） | 9 | 10-167 |
| [scheduler.md](assets/guides/coding-rules/scheduler.md) | 调度器（APScheduler/启动/状态可见/运行时开关对称性/cron 最小间隔校验） | 16 | 33-195 |
| [llm-ai.md](assets/guides/coding-rules/llm-ai.md) | LLM/AI（响应解析/能力派发/降级） | 4 | 72-114 |
| [browser-automation.md](assets/guides/coding-rules/browser-automation.md) | 浏览器自动化（Playwright/Cookie/子进程/CSS 选择器多级降级） | 14 | 36-201 |
| [general-engineering.md](assets/guides/coding-rules/general-engineering.md) | 通用工程（注释/复用/现代化/死代码/事件过滤/重启验证/修复协议/字段契约/列表聚合/联动开关/precheck结构化/配置兜底） | 37 | 6-188 |
| [multi-user-auth.md](assets/guides/coding-rules/multi-user-auth.md) | 多用户与认证安全（资源隔离/中间件/会话token/覆盖决策） | 4 | 134-137 |
---

### step 索引表（按 step 编号查找）

| step | 标题 | 主题文件 |
|---|---|---|
| 5 | 功能实现约束 | [security.md](assets/guides/coding-rules/security.md) |
| 6 | 注释项检查 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 7 | 安全调用检查 | [security.md](assets/guides/coding-rules/security.md) |
| 8 | SonarQube 规则检查【强制，前端必做】 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 9 | 代码修改后的编译→部署→重启流程 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 10 | 测试编写 | [testing.md](assets/guides/coding-rules/testing.md) |
| 11 | 状态管理一致性 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 12 | 容器适配原则 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 13 | 文件扩展名判断 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 14 | 多视图切换与 state 提升 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 15 | 动态资源映射分离 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 16 | 事件触发时机 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 17 | 字段覆盖策略 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 18 | 幂等性设计 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 19 | 搜索接口标准化 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 20 | 注释与代码一致性 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 21 | 显式样式优于隐式间距 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 22 | IIFE 反模式禁止 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 23 | 会话失效处理与错误粒度区分 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 24 | UI 状态独立性原则 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 25 | 跨字段一致性校验 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 26 | 硬编码属性禁用 | [security.md](assets/guides/coding-rules/security.md) |
| 27 | 死代码与资源生命周期 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 28 | 跨组件状态同步 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 29 | 提示信息可操作性 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 30 | 加密升级退化策略模式 | [security.md](assets/guides/coding-rules/security.md) |
| 31 | 多配置文件发现模式 | [security.md](assets/guides/coding-rules/security.md) |
| 32 | 文件锁绕过模式 | [database.md](assets/guides/coding-rules/database.md) |
| 33 | 独立调度器隔离模式 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 34 | 配置驱动功能开关模式 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 35 | 降级链模式 | [concurrency.md](assets/guides/coding-rules/concurrency.md) |
| 36 | Chrome 136+ 限制适配模式 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 37 | Windows 测试环境 Mock 模式 | [testing.md](assets/guides/coding-rules/testing.md) |
| 38 | 第三方插件依赖预检模式 | [testing.md](assets/guides/coding-rules/testing.md) |
| 39 | 错误提示语义准确性 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 40 | 配置全链路生效验证 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 41 | 快速模式降级重试 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 42 | 硬编码阈值禁用 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 43 | 参数透传链路完整性 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 44 | 多源状态同步统一入口 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 45 | 状态条件区分'从未初始化'与'主动失效' | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 46 | 浏览器内存兜底同步模式 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 47 | Update vs Upsert 语义区分 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 48 | 写后钩子规范 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 49 | 死代码检测与清理 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 50 | 异步操作整体超时保护 | [concurrency.md](assets/guides/coding-rules/concurrency.md) |
| 51 | 异步操作用户反馈三态 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 52 | 数据流转完整性 5 点追踪 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 53 | 过滤逻辑场景区分 | [testing.md](assets/guides/coding-rules/testing.md) |
| 54 | 复用既有模式原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 55 | AntD 主题 token 动态覆盖模式 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 56 | 孤岛模块检测规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 57 | 时间敏感场景的延迟/统计分离规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 58 | Orchestrator 便捷方法封装规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 59 | 辅助功能异常日志级别规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 60 | 状态机设计规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 61 | 资源生命周期规范 | [concurrency.md](assets/guides/coding-rules/concurrency.md) |
| 62 | 双链路一致性规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 63 | 并发安全规范 | [concurrency.md](assets/guides/coding-rules/concurrency.md) |
| 64 | Python 现代化规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 65 | 过滤结果可见性规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 66 | pytest 模块重复 import 隔离规范 | [testing.md](assets/guides/coding-rules/testing.md) |
| 67 | 日志库占位符一致性规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 68 | 测试 fixture 生产隔离与数据污染应急规范 | [testing.md](assets/guides/coding-rules/testing.md) |
| 69 | 配置项边界值校验 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 70 | DB 迁移失败处理 | [database.md](assets/guides/coding-rules/database.md) |
| 71 | 状态码语义精细化 | [security.md](assets/guides/coding-rules/security.md) |
| 72 | LLM 响应防御性三层级解析 | [llm-ai.md](assets/guides/coding-rules/llm-ai.md) |
| 73 | 调度器状态与 DB 同步 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 74 | 后台任务健康监控 | [concurrency.md](assets/guides/coding-rules/concurrency.md) |
| 75 | 文本数值提取模式 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 76 | 前后端错误码契约与超时识别 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 77 | 前端可重试错误集与退避策略 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 78 | 多层兜底链模式 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 79 | 失败诊断 dump 机制 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 80 | 关键路径计时埋点 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 81 | 凭证前置校验与并行采集 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 82 | 前端过滤与后端分类一致性验证 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 83 | 过滤+分页适配流程 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 84 | 空状态边界条件处理规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 85 | 系统行为派生与用户配置正交原则 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 86 | 浏览器自动化资源拦截粒度规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 87 | Cookie 层依赖关系信号匹配规范 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 88 | DEBUG 代码清理规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 89 | 子进程创建标志规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 90 | 配置驱动原则强化 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 91 | 缓存失效传播规范 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 92 | 状态判定需区分'未检测'与'已检测未失效' | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 93 | SQLite DDL 修改列约束必须用表重建 + 事务安全 | [database.md](assets/guides/coding-rules/database.md) |
| 94 | 前后端字段契约对齐规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 95 | 长耗时异步请求 race condition 防护规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 96 | 除零兜底禁止凑数规范 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 97 | 重复错误处理抽取规范 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 98 | 元数据单源管理与跨端显示对齐规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 99 | 选择器仓库同步与单一数据源规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 100 | 外部系统文本特征集中管理规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 101 | 关键调度器启动状态可见性规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 102 | Pydantic 模型字段完整性规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 103 | 凭据同步桥接规范 | [security.md](assets/guides/coding-rules/security.md) |
| 104 | 脱敏策略场景区分规范 | [security.md](assets/guides/coding-rules/security.md) |
| 105 | 第三方平台 API 兼容性规范 | [security.md](assets/guides/coding-rules/security.md) |
| 106 | 事件发布完整性规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 107 | 启动钩子完整性检查规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 108 | 任务历史持久化三层状态保护规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 109 | 业务自增计数器 DB MAX 初始化规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 110 | APScheduler interval 触发器首次执行控制规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 111 | CLI 默认参数友好性规范 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 112 | 能力驱动派发规范 | [llm-ai.md](assets/guides/coding-rules/llm-ai.md) |
| 113 | 共享工具函数规范 | [llm-ai.md](assets/guides/coding-rules/llm-ai.md) |
| 114 | 静默降级预检规范 | [llm-ai.md](assets/guides/coding-rules/llm-ai.md) |
| 115 | 用户偏好类 UI 状态持久化强制复用 usePersistentState 规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 116 | 数据库迁移块独立容错与关键路径异常可见性规范 | [database.md](assets/guides/coding-rules/database.md) |
| 117 | API 更新接口三态语义规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 118 | 字段全链路消费规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 119 | 共享单例局部变量规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 120 | 跨前后端类型对齐规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 121 | 前端错误处理规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 122 | 默认值操作符规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 123 | 失败原因传递链规范 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 124 | 数据完整性预检规范 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 125 | 合并写入 vs 覆盖写入决策规范 | [security.md](assets/guides/coding-rules/security.md) |
| 126 | 文案常量集中管理规范 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 127 | 修改-验证-部署闭环规范 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 128 | 测试 mock 同步规范 | [testing.md](assets/guides/coding-rules/testing.md) |
| 129 | 业务关键字常量集中管理规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 130 | 事件类型过滤精确匹配规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 131 | 前后端字段名大小写敏感检查规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 132 | 服务重启验证清单规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 133 | Windows 终端编码与 Shell 语法兼容规范 | [testing.md](assets/guides/coding-rules/testing.md) |
| 134 | 多用户资源隔离规范 | [multi-user-auth.md](assets/guides/coding-rules/multi-user-auth.md) |
| 135 | 认证中间件多路校验规范 | [multi-user-auth.md](assets/guides/coding-rules/multi-user-auth.md) |
| 136 | 会话 token 安全管理规范 | [multi-user-auth.md](assets/guides/coding-rules/multi-user-auth.md) |
| 137 | 快照与实时数据覆盖决策规范 | [multi-user-auth.md](assets/guides/coding-rules/multi-user-auth.md) |
| 138 | DATETIME-TZ-01 时区一致性三步检查法 | [database.md](assets/guides/coding-rules/database.md) |
| 139 | DATETIME-TZ-02 原生 SQL 返回值防御 | [database.md](assets/guides/coding-rules/database.md) |
| 140 | MIGRATE-01 迁移步骤独立性原则 | [database.md](assets/guides/coding-rules/database.md) |
| 141 | NULL-01 NOT NULL 字段防御原则 | [database.md](assets/guides/coding-rules/database.md) |
| 142 | QUERY-01 数据查询条件精确性原则 | [database.md](assets/guides/coding-rules/database.md) |
| 143 | ENUM-01 状态值枚举一致性原则 | [database.md](assets/guides/coding-rules/database.md) |
| 144 | ATTRIB-01 错误归因精细化原则 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 145 | EXCEPT-01 异常传播原则 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 146 | ERROR-01 错误消息透传原则 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 147 | RETRY-01 重试策略配置化原则 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 148 | LOG-NOISE-01 已知场景日志降噪原则 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 149 | CIRCUIT-01 熔断器持久化对称性原则 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 150 | STATE-01 状态切换原子性原则 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 151 | CONSISTENCY-01 多源失效判定一致性原则 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 152 | FALLBACK-01 缺失数据回退策略 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 153 | SYNC-01 多源状态同步标记机制 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 154 | RACE-01 异步竞态防护原则 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 155 | PARAM-CHAIN-01 参数传递链完整性原则 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 156 | KEYWORD-01 业务关键词集中管理原则 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 157 | PERSIST-01 用户可配置开关持久化原则 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 158 | CREDENTIAL-01 凭证多存储同步原则 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 159 | EFFECT-01 useEffect 副作用清理与依赖完整性规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 160 | SSE-01 SSE 事件流生命周期管理规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 161 | THEME-01 AntD 主题 token 单一数据源规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 162 | LAYOUT-01 布局响应式与最小宽度规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 163 | REGISTRY-01 注册表单一数据源规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 164 | FILTER-02 过滤条件与分页状态同步规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 165 | UI-SEMANTICS-01 UI 语义与行为一致性规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 166 | SOURCE-01 前端数据源单一可信源规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 167 | MOCK-01 测试 Mock 数据集中管理与字段完整性规范 | [testing.md](assets/guides/coding-rules/testing.md) |
| 168 | COOKIE-01 Cookie 完整保留与导入规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 169 | PARSER-01 解析器多层兜底规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 170 | KEYWORD-01 爬虫关键词集中管理规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 171 | NAMING-01 命名一致性与歧义消除规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 172 | CONTRACT-01 前后端契约对齐规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 173 | SEMANTICS-01 语义一致性规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 174 | FILTER-01 过滤逻辑精确匹配规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 175 | DRY-01 重复代码抽取规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 176 | ENCODING-01 编码一致性规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 177 | DATACLASS-01 数据类使用规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 178 | STARTUP-01 启动钩子完整性规范 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 179 | RESUME-01 状态恢复前置校验原则 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 180 | LOGMERGE-01 降级链日志合并原则 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 181 | REGISTRATION-01 注册式资源三件套契约原则 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 182 | ROOTCAUSE-01 修复前全链路根因扫描协议原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 183 | CONTRACT-SSO-01 前后端字段契约单一可信源原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 184 | GLOBAL-AGG-01 全局聚合任务级过滤原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 185 | CROSS-INJECT-01 列表交叉数据批量注入原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 186 | LINKED-SWITCH-01 多字段联动开关范式原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 187 | PRECHECK-STRUCT-01 状态恢复前置校验结构化响应原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 188 | CONFIG-FALLBACK-01 配置化阈值兜底范式原则 | [general-engineering.md](assets/guides/coding-rules/general-engineering.md) |
| 189 | PARAM-CHAIN-EXEC-01 参数链闭环验证规范 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 190 | MODE-VERTICAL-CHAIN-01 业务模式纵向链路一致性规范 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 191 | PARSER-FALLBACK-01 外部页面解析容错规范 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 192 | MOCK-SYNC-01 mock 同步与边界精确性规范 | [testing.md](assets/guides/coding-rules/testing.md) |
| 193 | FILTER-TRANS-01 过滤结果透明化 UI 规范 | [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) |
| 194 | SCHEDULER-RUNTIME-TOGGLE-SYMMETRY 调度器运行时开关对称性 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 195 | CRON-MIN-INTERVAL-CHECK 用户输入时间表达式校验 | [scheduler.md](assets/guides/coding-rules/scheduler.md) |
| 196 | TIME-PARAM-CONFIG-DRIVEN 时间参数配置化 | [config-driven.md](assets/guides/coding-rules/config-driven.md) |
| 197 | LIFECYCLE-RESOURCE-CLEANUP 长生命周期对象状态清理 | [state-management.md](assets/guides/coding-rules/state-management.md) |
| 198 | ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检查 | [concurrency.md](assets/guides/coding-rules/concurrency.md) |
| 199 | RESOURCE-POOL-BENCHMARK 资源池配置性能基准与决策 | [database.md](assets/guides/coding-rules/database.md) |
| 200 | HTTP-STATUS-CODE-MAPPING HTTP 状态码精细化映射表 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 201 | CSS-SELECTOR-FALLBACK CSS 选择器多级降级策略 | [browser-automation.md](assets/guides/coding-rules/browser-automation.md) |
| 202 | EXCEPTION-LOG-SEMANTIC 异常日志语义保留规范 | [error-handling.md](assets/guides/coding-rules/error-handling.md) |
| 203 | EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对管理 | [concurrency.md](assets/guides/coding-rules/concurrency.md) |
| 204 | DB-WRITE-IDENTITY-TRACE 数据库写入函数身份追溯与类型安全 | [database.md](assets/guides/coding-rules/database.md) / [security.md](assets/guides/coding-rules/security.md) |
