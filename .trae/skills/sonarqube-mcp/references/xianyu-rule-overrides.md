# Xianyu 项目 SonarQube 规则豁免与误报处理

> **单一信息源**：硬约束规则的完整定义（pattern/severity/applies_to）见 [config/hard_constraints.json](file:///d:/code/otherProjects/17_xianyu/.trae/skills/sonarqube-mcp/config/hard_constraints.json)。本文件仅描述规则豁免标准、误报判断与修复方案。

## 规则豁免清单

以下规则在 Xianyu 项目中可豁免或标记为误报，因为它们与 FastAPI/React 框架设计冲突或属于已知的项目模式。

### 1. python:S1481 — 未使用的导入

**触发场景**：FastAPI 路由文件中导入的符号在静态分析中显示为未使用

**豁免原因**：FastAPI 装饰器模式（如 `@app.get()`、`@router.post()`）注册的路由处理函数，以及 Pydantic 模型字段，可能被框架在运行时通过反射调用，静态分析无法检测

**判断标准**：
- 文件包含 `@app.get/post/put/delete/patch` 或 `@router.get/post/put/delete/patch` 装饰器 → 豁免
- 导入的 Pydantic 模型用于类型注解 → 豁免
- 导入的 Depends/Auth 依赖 → 豁免
- 确实无任何调用且非装饰器使用 → 不豁免，需删除

**comment 模板**：
```
Xianyu 框架误报：FastAPI 路由装饰器模式，导入的符号在运行时通过反射调用。
```

---

### 2. python:S2949 — 可变默认参数

**触发场景**：FastAPI 依赖注入函数使用可变默认值

**豁免原因**：FastAPI 的 `Depends()` 返回的是依赖注入器，并非真正的可变对象

**判断标准**：
- 默认值为 `Depends(...)` → 豁免
- 默认值为 `Body(...)`、`Query(...)`、`Path(...)` → 豁免
- 默认值为 `[]`、`{}`、`set()` → 不豁免，需改为 `None` 并在函数内初始化

---

### 3. python:S3508 — 未使用的局部变量

**触发场景**：循环变量或解构变量未使用

**豁免原因**：Python 惯例使用 `_` 前缀表示有意忽略的变量

**判断标准**：
- 变量名以 `_` 开头（如 `_unused`、`_`）→ 豁免
- 确实未使用且无 `_` 前缀 → 不豁免，需添加 `_` 前缀或删除

---

### 4. typescript:S6488 — React Hook 优化建议

**触发场景**：useEffect/useMemo/useCallback 的依赖数组或返回值优化建议

**豁免原因**：React Hook 的依赖管理需要结合组件上下文判断，部分场景下显式依赖会导致无限渲染

**判断标准**：
- 依赖数组为空 `[]` 且组件仅需挂载时执行一次 → 豁免
- 使用了 ref 引用避免重新渲染 → 豁免
- 确实遗漏了依赖且会导致 stale closure → 不豁免，需补充依赖

---

### 5. typescript:S6486 — React 组件返回类型

**触发场景**：函数组件未显式声明返回类型 `React.ReactElement`

**豁免原因**：TypeScript 可通过 JSX 推导返回类型，显式声明增加冗余

**判断标准**：
- 函数返回 JSX → 豁免
- 高阶组件或泛型组件 → 不豁免，建议显式声明

---

### 6. python:S5843 — 正则表达式复杂度过高

**触发场景**：复杂正则表达式（如 URL 解析、HTML 提取）

**豁免原因**：部分业务场景（如闲鱼商品标题解析）需要复杂正则，拆分会降低可读性

**判断标准**：
- 正则用于解析复杂业务文本（商品标题、URL）→ 可豁免
- 正则可用简单字符串方法替代 → 不豁免，需重构
- 正则可拆分为多个简单正则 → 不豁免

---

## 不可豁免规则

以下规则在任何情况下都不可豁免，必须修复：

| 规则 | 原因 |
|------|------|
| secrets:S6702 | 密钥泄露直接威胁生产安全 |
| python:S2068 | 硬编码密码不可接受 |
| python:S2078 | SQL注入风险不可接受 |
| python:S3649 | 不安全的随机数影响 token 安全性 |
| python:S5803 | subprocess shell=True 存在命令注入风险 |
| python:S5332 | 不安全的 SSL/TLS 配置 |
| typescript:S5144 | XSS 漏洞不可接受 |
| python:S2259 | 空指针异常影响系统可靠性 |
| python:S2095 | 资源泄露导致系统不稳定 |

---

## Xianyu 硬约束规则的修复方案

> **规则定义**：完整的规则列表（pattern/severity/applies_to）见 [config/hard_constraints.json](file:///d:/code/otherProjects/17_xianyu/.trae/skills/sonarqube-mcp/config/hard_constraints.json)。本节仅提供修复方案。

### 凭据安全类（CRITICAL）

1. **no_hardcoded_credentials**：改用 `os.environ.get('VAR_NAME')` 或 `pydantic.BaseSettings`
2. **no_hardcoded_sonar_token**：从 `SONAR_TOKEN` 环境变量读取
3. **hmac_compare_digest_for_token**：使用 `hmac.compare_digest(stored_token, provided_token)`

### WebView2/Playwright 类（MAJOR）

4. **webview_no_devnull_redirect**：保留 stdout/stderr，使用 `CREATE_NEW_CONSOLE` 标志
5. **webview_create_new_console**：替换为 `subprocess.CREATE_NEW_CONSOLE`
6. **webview_private_mode_false**：`webview.start(private_mode=False, storage_path=f'webview_data_{pid}_{timestamp}')`

### 嵌入与服务类（MAJOR）

7. **hf_endpoint_mirror**：在模块顶层添加 `os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')`（必须在 import sentence_transformers 之前）
8. **kbmanager_whitelist_only**：仅索引 `.md/.py/.jsonl/.txt` 文件，排除 `web/static/`、`web/templates/`、`__pycache__/`、`node_modules/`、`.git/`、`dist/`、`build/`

### 认证与前端类（MAJOR）

9. **auth_whitelist_endpoints**：认证白名单必须包含 `/api/auth/cookie`、`/api/auth/me`、`/api/auth/import-from-browser`、`/import-from-browser/status`、`/api/events/stream`、`/api/notifications`、`/api/notifier/`、`/api/about`、`/api/about/check-update`
10. **fetch_credentials_include**：添加 `credentials: 'include'` 选项

---

## 误报处理流程

### Step 1：识别误报

扫描到问题后，先判断是否属于上述豁免清单中的规则。

### Step 2：验证误报

- 检查代码上下文，确认是否满足豁免条件
- 检查 FastAPI/React 框架基类或接口定义
- 确认运行时行为是否安全

### Step 3：标记误报

```
调用 change_sonar_issue_status(
  key=问题ID,
  status="falsepositive",
  comment="Xianyu 框架误报：[具体原因]"
)
```

### Step 4：记录豁免

将确认的豁免规则记录到本文件或 scan_config.json → `xianyu_framework_patterns.known_false_positive_rules`，保持文档更新。

---

## FastAPI/React 框架模式与 SonarQube 规则映射

### FastAPI 模式

| FastAPI 模式 | 可能触发的规则 | 处理方式 |
|--------------|---------------|----------|
| `@app.get()` 装饰器 | S1481（未使用导入） | 豁免：框架注册路由 |
| `Depends()` 默认值 | S2949（可变默认参数） | 豁免：依赖注入器 |
| `Body()`/`Query()`/`Path()` | S2949（可变默认参数） | 豁免：参数注入 |
| Pydantic 模型字段 | S116（命名规范） | 豁免：与 API 字段对应 |
| `async def` 路由处理 | S5332（异步安全） | 需结合上下文判断 |

### React 模式

| React 模式 | 可能触发的规则 | 处理方式 |
|------------|---------------|----------|
| `useEffect(() => {}, [])` | S6488（Hook 优化） | 豁免：仅需挂载时执行 |
| 函数组件无返回类型 | S6486（返回类型） | 豁免：JSX 类型推导 |
| `useCallback` 依赖数组 | S6488（Hook 优化） | 需结合上下文判断 |
| `dangerouslySetInnerHTML` | S5144（XSS） | 不豁免：需确认内容来源 |

---

## 修复策略配置

修复策略已配置在 `scan_config.json -> fix_strategies`：

| 规则 | 策略 | 自动修复提示 |
|------|------|-------------|
| python:S1192 | manual_review | （需人工判断提取为常量还是配置项） |
| python:S1481 | auto_fix | 删除未使用的 import 语句 |
| python:S3508 | auto_fix | 删除未使用的局部变量，若为循环变量改为 _ 前缀 |
| python:S5843 | manual_review | （需人工判断是否可简化正则） |
| typescript:S1192 | manual_review | （需人工判断提取为常量） |
| typescript:S1488 | auto_fix | 使用 const 声明并立即返回对象字面量 |
| typescript:S3504 | auto_fix | 删除未使用的 import 语句 |

### 策略说明

- **auto_fix**：可自动修复，子代理直接执行
- **manual_review**：需人工审查，子代理输出建议供用户决策
- **skip**：跳过修复，仅记录
