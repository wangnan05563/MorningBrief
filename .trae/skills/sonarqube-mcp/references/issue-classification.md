# Xianyu 项目 SonarQube 问题分类与判断标准

## 问题分类体系

### 一、按质量维度分类

#### SECURITY（安全类）

| 规则ID | 规则名称 | Xianyu 场景说明 |
|--------|----------|----------------|
| secrets:S6702 | 硬编码密钥/Token | 检查 .env、config.yaml 中的敏感信息 |
| python:S2068 | 硬编码密码 | 检查数据库连接、API认证等 |
| python:S2078 | SQL注入 | 检查 SQLAlchemy 原生 SQL 拼接 |
| python:S5146 | Open Redirect | 检查 FastAPI 重定向 |
| python:S5042 | 路径遍历 | 检查文件操作相关代码 |
| typescript:S2078 | SQL注入 | 检查前端拼接到后端的 SQL 参数 |
| typescript:S5144 | XSS | 检查 React dangerouslySetInnerHTML |
| python:S3649 | 不安全的随机数 | 检查 token 生成是否使用 secrets 模块 |

#### RELIABILITY（可靠性类）

| 规则ID | 规则名称 | Xianyu 场景说明 |
|--------|----------|----------------|
| python:S2259 | 空指针异常 | 检查 Pydantic 模型取值、数据库查询结果未判空 |
| python:S2095 | 资源泄露 | 检查文件句柄、数据库连接未关闭 |
| python:S5332 | 不安全的 SSL/TLS | 检查 httpx/aiohttp 客户端配置 |
| python:S5803 | subprocess shell=True | 检查 Playwright/WebView2 子进程调用 |
| python:S2949 | 可变默认参数 | 检查 FastAPI 依赖注入的默认值 |
| typescript:S2814 | 重复函数声明 | 检查 React 组件重复定义 |
| typescript:S3776 | 认知复杂度过高 | 检查 useEffect 内部逻辑 |

#### MAINTAINABILITY（可维护性类）

| 规则ID | 规则名称 | Xianyu 场景说明 |
|--------|----------|----------------|
| python:S3776 | 认知复杂度过高 | Service 方法拆分，提取私有方法 |
| python:S1192 | 字符串重复定义 | 提取为常量或配置项 |
| python:S1481 | 未使用的 import | 删除无用导入 |
| python:S3508 | 未使用的局部变量 | 删除或改为 _ 前缀 |
| python:S5843 | 正则复杂度过高 | 简化正则表达式 |
| typescript:S1192 | 字符串重复定义 | 提取为常量 |
| typescript:S1488 | 数组方法优化 | 使用 const 声明并立即返回 |
| typescript:S3504 | 未使用的 import | 删除无用导入 |
| typescript:S6488 | React Hook 优化 | 使用 useCallback/useMemo 优化 |

---

### 二、按 Xianyu 项目上下文分类

#### 真实问题（必须修复）

特征：
- 直接影响系统安全性或可靠性
- 违反 Python/TypeScript 编码基本规范
- 不依赖 FastAPI/React 框架特性即可判断

示例：
- 空指针未检查
- SQL注入风险
- 硬编码敏感信息
- 资源泄露
- subprocess shell=True 安全风险

#### 框架误报（可标记 falsepositive）

特征：
- 由 FastAPI/React 框架模式触发
- 代码在运行时环境下是安全的
- SonarQube 不理解框架的依赖注入机制

常见误报模式：

| 规则 | 触发场景 | 误报原因 |
|------|----------|----------|
| python:S1481 | FastAPI 路由装饰器导入的符号 | 装饰器模式无法静态检测使用 |
| typescript:S6488 | useEffect 依赖数组 | React Hook 依赖管理需结合上下文 |
| python:S2949 | FastAPI Depends 默认值 | Depends() 返回的是依赖注入器 |
| typescript:S6486 | React 组件返回类型 | JSX 推导类型无需显式声明 |

标记 falsepositive 的 comment 模板：
```
Xianyu 框架误报：[说明原因]。该代码在 FastAPI/React 运行时环境下[解释为何安全/正确]。
```

#### 可接受债务（标记 accept）

特征：
- 业务需要但不符合最佳实践
- 修复成本高于收益
- 已有补偿措施

标记 accept 的 comment 模板：
```
可接受技术债务：[说明业务原因]。补偿措施：[已有的替代方案]。
```

---

### 三、问题严重级别判定矩阵

| 严重级别 | 安全类 | 可靠性类 | 可维护性类 |
|----------|--------|----------|-----------|
| BLOCKER | 密码泄露、SQL注入 | 数据丢失风险 | - |
| CRITICAL | 敏感信息暴露、token 硬编码 | 空指针崩溃、资源泄露、subprocess shell=True | 认知复杂度严重超标 |
| MAJOR | 潜在XSS | 异常处理不当、可变默认参数 | 字符串重复、命名不规范、未使用代码 |
| MINOR | 信息泄露 | 边界条件 | TODO标记、注释缺失 |
| INFO | - | - | 代码风格建议 |

---

### 四、Xianyu 项目特有检查项

> **规则定义**：硬约束规则的完整 pattern/severity/applies_to 见 [config/hard_constraints.json](file:///d:/code/otherProjects/17_xianyu/.trae/skills/sonarqube-mcp/config/hard_constraints.json)。本节仅描述检查项分类与判断标准。

以下检查项不在 SonarQube 标准规则中，但对 Xianyu 项目质量至关重要：

| 分类 | 检查项 | 严重级别 |
|------|--------|----------|
| 凭据安全 | no_hardcoded_credentials / no_hardcoded_sonar_token / hmac_compare_digest_for_token | CRITICAL |
| WebView2 | webview_no_devnull_redirect / webview_create_new_console / webview_private_mode_false | MAJOR |
| 嵌入与服务 | hf_endpoint_mirror / kbmanager_whitelist_only | MAJOR |
| 认证与前端 | auth_whitelist_endpoints / fetch_credentials_include | MAJOR |

#### 项目特有约定（不在 hard_constraints.json，但需在代码评审中检查）

- **database_indexes**：必须在 `task_id`、`seller_id`、`first_seen`、`publish_time`、`created_at`、`request_id` 上建立索引，并建立复合索引优化 Dashboard 查询
- **count_query_merge**：`_overview()` 中的 COUNT 查询必须使用 CASE WHEN 聚合查询合并，减少 DB 调用 67%
- **web_process_browser_mode**：Web 进程必须使用 `with_browser=False` 模式节省内存
- **unauthorized_json_response**：401 响应必须返回 JSON 格式 `{"detail": "Unauthorized"}` 而非纯文本
- **module_level_imports**：缺失的 import（如 `re`、`threading`、`logging`）必须添加到模块级别，防止运行时 NameError
- **no_redundant_function_imports**：函数内冗余 import 必须移至模块级别
- **token_log_no_sensitive**：敏感字段（如 token 长度）不得记录日志，仅记录布尔匹配结果
- **token_write_failure_alert**：Token 写入失败必须触发 `logging.warning()` 告警
- **embedding_version_compat**：`sentence-transformers` 5.x 将 `get_sentence_embedding_dimension` 重命名为 `get_embedding_dimension`，必须使用 `getattr` 回退实现跨版本兼容
