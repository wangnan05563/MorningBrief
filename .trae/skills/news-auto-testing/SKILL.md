---
name: "news-auto-testing"
description: "前端自动化测试：使用 Playwright MCP + Chrome DevTools MCP 对 Web 应用做全面功能/性能/API 测试。当用户要求'测试前端/全面测试/系统测试/回归测试'或提到 'news-auto-testing / 前端测试' 时调用。"
version: "6"
updated: "2026-07-18"
config: "config.yaml"
---

# 前端自动化测试

使用 Playwright MCP + Chrome DevTools MCP 对 Web 应用进行全面测试，覆盖页面加载、登录流程、API 接口、性能审计四个维度，所有参数通过 `config.yaml` 管理。

## 配置文件

所有测试参数（URL、账号、页面清单、API 清单、性能阈值、修复策略）均通过配置文件管理：

- 模板：`config.example.yaml`
- 实际：`config.yaml`（从模板复制后按项目修改）

配置文件分为 23 个区块：

| 区块 | 作用 |
|------|------|
| `service` | 服务基础 URL、健康检查、启停脚本 |
| `mcp_tools` | Playwright / Chrome DevTools 工具配置 |
| `credentials` | 测试账号、登录选择器、token 路径 |
| `pages` | 页面清单（路径、预期文本、是否需登录、按钮交互） |
| `api_endpoints` | API 端点清单（方法、路径、期望状态码/code、priority） |
| `placeholders` | 自定义占位符映射（扩展内置占位符） |
| `performance` | Lighthouse 审计 + Performance Trace 阈值 |
| `screenshot` | 截图策略（全页/视口、绝对路径、超时） |
| `snapshot` | 快照策略（大小阈值、落盘） |
| `assertions` | 判断逻辑（页面/API/登录成功标准、error 白名单、文本匹配模式） |
| `issue_classification` | 问题分类（代码缺陷/业务数据/框架行为/环境/工具层 bug/数据隔离违规/RSS 源不可达/第三方限流） |
| `fix_strategies` | 常见问题修复策略表 |
| `workflow` | 流程控制（自动启停、失败继续、自动修复、回归构建、菜单 fallback） |
| `report` | 报告输出配置 |
| `test_priority` | 测试用例优先级分类（P0-P3，控制执行顺序和报告分组） |
| `rss_source_check` | RSS 源可达性预检（串行验证、内容类型检查、UA 兼容性） |
| `data_isolation_check` | 频道级数据隔离预检（OR NULL 兜底检测、channel_id 严格过滤） |
| `powershell_compat_check` | PowerShell Python 脚本调用兼容性检查（-u 参数、2>&1 重定向） |
| `third_party_service_check` | 第三方转换服务依赖诊断（rsshub/plink 限流、DNS 污染、UA 拒绝） |
| `service_mode_detection` | 服务模式自动检测（dev/exe/docker 模式识别 + 未构建变更警告） |
| `login_protocol` | API 登录协议自动适配（form/json Content-Type 切换） |
| `route_verification` | 路由路径预验证（APIRouter prefix 与 api_endpoints 声明一致性） |
| `sonarqube_regression` | SonarQube 二次扫描回归（OPEN 问题 diff + BLOCKER/CRITICAL 守门） |

## 测试流程（6 核心 + 17 辅助 = 23 阶段）

### 阶段 1：环境预检

```
1. 读取 config.yaml 获取所有配置参数
2. 如 workflow.auto_start_service=true，执行 service.start_script 启动服务
3. 健康检查：GET service.base_url + service.health_endpoint
   - 轮询等待，超时 = service.health_timeout 秒
   - 成功条件：HTTP 200 + JSON.code == service.health_expected_code
4. MCP 工具可用性检查：
   - 读取 mcp_tools.playwright_server / chrome_devtools_server 的工具 schema
   - 尝试用 primary_tool 导航到一个简单页面验证可用性
   - 如 primary_tool 失败，切换到 fallback_tool
5. 如使用 Playwright，检查浏览器是否安装（失败时运行 install_command）
```

### 阶段 2：页面遍历测试

对 `pages` 清单中每个 `skip: false` 的页面执行：

```
1. 导航到 base_url + page.path
   - 菜单点击导航（如 workflow.menu_click_fallback.enabled=true）：
     a. 先尝试点击菜单项
     b. 点击后比对 URL，如 URL 未变化则自动改用 navigate_page 直接导航
     c. 记录菜单点击是否成功（用于报告）
2. 截图（按 screenshot 策略）：
   - 如 screenshot.full_page=true，先尝试全页截图
   - 如全页截图超时（screenshot.timeout_ms），自动降级为视口截图
   - 截图路径必须为绝对路径（MCP 工具 cwd 可能与项目目录不同）
3. 获取页面快照（按 snapshot 策略）：
   - 如快照大小 > snapshot.max_size_kb，自动保存到 snapshot.save_dir 下的文件
   - 从文件读取必要信息，避免输出截断
4. 检查控制台消息（list_console_messages / playwright_console_logs）
   - 过滤 error 级别消息
   - 如 error 消息匹配 assertions.console_error_whitelist 中任一子串，归类为"框架预期行为"不算 FAIL
5. 检查网络请求（list_network_requests）
6. 判断页面是否加载成功：
   - 无控制台 error（排除白名单） 
   - 页面网络请求返回 200（排除 pending 的请求需等待重试）
   - 页面可见文本包含至少一个 expected_texts（按 assertions.text_match_mode 匹配）
7. 如 page.buttons 非空，执行按钮交互测试（见下文）
8. 记录结果：PASS / WARN / FAIL / SKIP
```

#### 按钮交互测试（子流程）

对 `page.buttons` 清单中每个 `skip: false` 的按钮执行：

```
1. 从最新快照中定位按钮（按 uid_hint 或按钮文本匹配）
2. 点击按钮
3. 按 expected_action 验证交互结果：
   - dialog_open：重新获取快照，检查是否出现 dialog 角色
   - url_change：比对点击前后 URL 是否变化
   - state_change：重新获取快照，检查元素状态变化（如 selected/checked）
   - no_op：仅验证点击不报错（用于"取消"类按钮）
4. 如 expected_action=dialog_open 且 close_after=true：
   - 在新快照中定位取消/关闭按钮并点击
   - 如取消按钮点击超时，尝试按 ESC 键关闭
5. 如按钮点击超时但重新快照发现目标状态已达成（如对话框已弹出），判定为 PASS
   （UI 组件库按钮可能在 click 回调完成前已更新 DOM）
6. 记录按钮交互结果
```

**需登录的页面**：先执行阶段 3 登录流程，再遍历。

**dev_only 页面**：仅在开发模式（APP_ENV=development）下测试，生产模式跳过。

### 阶段 3：登录流程测试

```
1. 导航到 credentials.admin.login_page
2. 获取表单 HTML，确认选择器有效
3. 填写用户名（username_selector）
4. 填写密码（password_selector）
5. 点击登录按钮（submit_selector）
6. 等待页面跳转（expected_redirect）
7. 检查网络请求：POST login_endpoint 返回 200
8. 检查响应包含 token（token_path）
9. 检查页面显示用户名和角色信息
10. 记录结果
```

**登录失败处理**：查找 `fix_strategies` 中匹配的修复策略，按 `workflow.auto_fix` 决定是否自动修复。

### 阶段 4：API 端点测试

对 `api_endpoints` 清单中每个 `skip: false` 的端点执行：

```
1. 按 test_priority.execution_order 排序测试用例（P0 → P1 → P2 → P3）
   - 未标注 priority 的用例按 test_priority.default_priority 归类
   - 同优先级内按 config.yaml 中的声明顺序执行
2. 替换路径和请求体中的占位符：
   - 内置占位符：
     - ${username} → credentials.admin.username
     - ${password} → credentials.admin.password
     - ${current_date} → 当天日期 YYYY-MM-DD
     - ${current_month} → 当月 YYYY-MM
     - ${current_year} → 当年 YYYY
     - ${timestamp} → 当前 Unix 时间戳（秒）
   - 自定义占位符：从 placeholders 区块读取，键值对映射
   - 占位符替换顺序：先自定义占位符，再内置占位符（避免冲突）
3. 如 requires_auth=true，先登录获取 token，设置 Authorization: Bearer <token>
4. 发送 HTTP 请求（method + base_url + path）
5. 检查状态码 == expected_status
6. 检查 JSON.code == expected_code 或在 acceptable_codes 中
7. 记录结果（含 priority 字段，用于报告分组）
```

**PowerShell 注意**：POST 请求的 JSON body 在 PowerShell 中用 `Invoke-RestMethod` 而非 `curl.exe -d`，避免引号转义问题。

**优先级执行策略**：
- P0 用例失败时，如 `test_priority.P0.fail_action=block_release`，立即停止后续低优先级用例执行并报告阻塞
- P1 用例失败时，记录并继续执行，发版前必须修复
- P2/P3 用例失败时，仅记录，不阻塞流程

### 阶段 5：性能审计

```
1. 如 performance.lighthouse_enabled=true：
   - Lighthouse 审计前准备（如 performance.lighthouse_isolated_context.enabled=true）：
     a. 如审计页面 requires_auth=false 但当前已登录，打开新隔离 context 标签页
     b. 在隔离 context 中导航到审计页面，避免登录态干扰
     c. 审计完成后关闭隔离标签页
   - 对 lighthouse_pages 中的页面执行 lighthouse_audit
   - 设备类型 = lighthouse_device
   - 检查分数 ≥ lighthouse_thresholds
2. 如 performance.trace_enabled=true：
   - 对 trace_pages 中的页面执行 performance_start_trace
   - 检查 LCP ≤ metrics_thresholds.lcp_max_ms
   - 检查 CLS ≤ metrics_thresholds.cls_max
   - 检查 TTFB ≤ metrics_thresholds.ttfb_max_ms
   - 如 Trace 执行失败或超时，按 performance.trace_failure_degrade=true 降级为仅 Lighthouse 结果（记录为 WARN，不阻止通过）
3. 记录结果
```

### 阶段 6：报告生成

```
1. 汇总所有测试结果
2. 按 severity_levels 分级统计
3. 按 issue_classification 对发现的问题分类：
   - code_defect：代码缺陷（需修改源码修复）
   - business_data：业务数据问题（需配置/数据修复，非代码缺陷）
   - framework_behavior：框架预期行为（如 Element Plus cancel error，无需修复）
   - environment：环境问题（如依赖缺失、端口占用）
4. 如 test_priority.group_by_priority=true，按优先级分组展示测试结果：
   - P0 阻塞性：红色标识，失败时标注"阻止发布"
   - P1 高优先级：橙色标识，失败时标注"发版前修复"
   - P2 中优先级：黄色标识，失败时标注"下个迭代修复"
   - P3 低优先级：灰色标识，失败时标注"仅记录"
5. 如 report.output_dir 非空，生成 markdown 报告到该目录
6. 报告内容：
   - 测试概览（总数/通过/失败/跳过，按优先级统计通过率）
   - 页面测试详情表（含按钮交互结果）
   - API 测试详情表（含 priority 列，按优先级排序）
   - 性能审计数据
   - 发现的问题及分类（按 issue_classification 归类）
   - 发现的问题及修复建议（如 include_fix_suggestions=true）
   - 修复后的回归测试结果（如执行了修复）
   - 优先级通过率摘要（P0/P1/P2/P3 各级通过率）
```

### 修复流程（如 workflow.auto_fix=true）

当测试发现 code_defect 类问题时，执行修复流程：

```
1. 查找 fix_strategies 中匹配的修复策略
2. 实施代码修复
3. 如 workflow.build_before_regression.enabled=true：
   a. 如 build_before_regression.check_node_modules=true，先检查依赖完整性
   b. 执行 build_before_regression.command（如 npm run build）
   c. 如构建失败且为依赖问题，尝试重装依赖后重新构建
4. 如 workflow.regression_cache_strategy.ignore_cache=true：
   - 回归测试时使用 ignoreCache 选项强制刷新页面
5. 对修复项重新执行测试（如 workflow.regression_after_fix=true）
6. 如回归测试仍失败且未超过 max_fix_attempts，回到步骤 1 重试
```

**注意**：business_data 类问题不触发代码修复流程，仅在报告中标注解决方案（如"配置真实 API key"）。

## 判断逻辑

### 页面加载成功

| 条件 | 严重级别 |
|------|---------|
| 无控制台 error（排除白名单）+ 网络 200 + 文本匹配 | PASS |
| 有控制台 warn 但功能正常 | WARN |
| 有控制台 error（非白名单）或网络非 200 | FAIL |
| dev_only 页面在生产模式下 | SKIP |

**控制台 error 白名单**：如 error 消息包含 `assertions.console_error_whitelist` 中任一子串，归类为 framework_behavior，不触发 FAIL。

**文本匹配模式**（`assertions.text_match_mode`）：
- `any_substring`（默认）：expected_texts 中任一文本作为子串出现在页面可见文本中即匹配
- `exact`：expected_texts 中任一文本与页面可见文本完全匹配
- `regex`：expected_texts 中任一文本作为正则表达式匹配页面可见文本

### 按钮交互成功

| 条件 | 严重级别 |
|------|---------|
| 点击成功 + 预期动作达成（dialog/url/state） | PASS |
| 点击超时但重新快照发现目标状态已达成 | PASS（UI 组件库异步更新） |
| 点击成功但预期动作未达成 | FAIL |
| 按钮不可见或不可点击 | FAIL |

### API 调用成功

| 条件 | 严重级别 |
|------|---------|
| status == expected_status + code 在 acceptable_codes | PASS |
| status == 200 但 code 不在 acceptable_codes | FAIL |
| status != expected_status | FAIL |

### 登录成功

| 条件 | 严重级别 |
|------|---------|
| API 200 + token 返回 + URL 跳转 + 用户信息显示 | PASS |
| API 200 + token 返回但 URL 未跳转 | WARN |
| API 非 200 或无 token | FAIL |

### 性能合格

| 指标 | 阈值 | 严重级别 |
|------|------|---------|
| Lighthouse Accessibility | ≥ 85 | < 85 → WARN |
| Lighthouse Best Practices | ≥ 85 | < 85 → WARN |
| Lighthouse SEO | ≥ 75 | < 75 → WARN |
| LCP | ≤ 2500ms | > 2500 → WARN |
| CLS | ≤ 0.1 | > 0.1 → WARN |
| TTFB | ≤ 800ms | > 800 → WARN |

所有性能指标为 WARN 级别，不阻止测试通过，但会在报告中标注。

### 问题分类（issue_classification）

| 分类 | 含义 | 处理方式 |
|------|------|----------|
| code_defect | 代码缺陷 | 触发修复流程，修改源码 |
| business_data | 业务数据问题 | 报告中标注解决方案，不修改代码 |
| framework_behavior | 框架预期行为 | 报告中记录，无需修复 |
| environment | 环境问题 | 报告中标注，需环境层面修复 |

### 测试用例优先级分类（P0-P3）

通过 `test_priority` 配置节管理测试用例优先级，控制执行顺序和报告分组展示。每个 API 测试用例可在 `api_endpoints` 中标注 `priority` 字段，未标注的按 `default_priority` 归类。

| 优先级 | 名称 | 颜色标识 | 失败处理 | 执行顺序 |
|--------|------|----------|----------|----------|
| P0 | 阻塞性 | 红色 | block_release（阻止发布） | 最先执行 |
| P1 | 高优先级 | 橙色 | fix_before_release（发版前修复） | P0 之后 |
| P2 | 中优先级 | 黄色 | fix_next_iteration（下个迭代修复） | P1 之后 |
| P3 | 低优先级 | 灰色 | log_only（仅记录） | 最后执行 |

**执行顺序**：按 `test_priority.execution_order`（默认 `["P0", "P1", "P2", "P3"]`）排序，同优先级内按 config.yaml 声明顺序执行。

**P0 阻塞策略**：P0 用例失败时立即停止后续低优先级用例执行，报告中标注"阻止发布"。

**新增测试用例覆盖范围**（均通过 config.yaml 管理，无硬编码）：

| 端 | 测试用例 | 优先级 | 说明 |
|----|---------|--------|------|
| C端-小程序 | 播放进度上报 | P1 | 验证 playlogs/progress 接口 |
| C端-小程序 | 倍速播放设置 | P2 | 验证 playback_rate 参数 |
| C端-小程序 | 快进快退-seek操作 | P2 | 验证 position 参数边界 |
| C端-小程序 | 收藏节目 | P1 | 验证 favorites POST 接口 |
| C端-小程序 | 取消收藏 | P1 | 验证 favorites DELETE 接口 |
| C端-小程序 | 收藏列表 | P2 | 验证 favorites 列表查询 |
| C端-小程序 | 提交反馈 | P1 | 验证 feedback 提交接口 |
| C端-小程序 | 频道筛选-列表 | P2 | 验证 channel 筛选参数 |
| B端-前端 | 验证码获取 | P1 | 验证 captcha 生成接口 |
| B端-前端 | 拖拽排序-更新 | P2 | 验证 placements/sort 接口 |
| B端-前端 | 柱状图数据-播放统计 | P2 | 验证 stats/chart 接口 |
| B端-前端 | 90天统计-趋势 | P2 | 验证 90d 范围趋势查询 |
| B端-后端 | 内容安全检测 | P0 | 验证 moderation/check 接口 |
| B端-后端 | 数据库备份 | P0 | 验证 db-admin/backup 接口 |
| B端-后端 | feedback同步-COS | P1 | 验证 sync-feedback 接口 |
| B端-后端 | 批量删除-节目 | P1 | 验证 batch-delete 接口 |

## 常见问题修复策略

测试过程中遇到问题时，按 `fix_strategies` 表匹配并修复：

### FAIL 级问题（必须修复）

1. **前端页面 404**：后端未挂载前端静态文件 → 检查 `paths.py` 的 `resolve_admin_dist()` 路径
2. **JS MIME 类型错误**：Windows mimetypes 缺失 → `main.py` 添加 `mimetypes.add_type()`
3. **健康检查超时**：服务初始化阻塞 → 增加 `health_timeout` 或检查 lifespan
4. **登录失败无账号**：数据库无管理员 → bcrypt 哈希后 INSERT

### WARN 级问题（可继续测试）

1. **Playwright 浏览器未安装**：运行 `npx playwright install chromium`
2. **Playwright 版本不匹配**：创建目录 junction 链接
3. **Chrome DevTools 元素交互超时**：改用直接导航 URL
4. **PowerShell curl 转义**：改用 `Invoke-RestMethod`
5. **全页截图超时**：降级为视口截图（screenshot.full_page=false）
6. **快照输出过大被截断**：保存到文件后读取（snapshot.save_dir）
7. **菜单点击不跳转 URL**：自动改用 navigate_page（menu_click_fallback）
8. **UI 组件库废弃 API 警告**（如 el-radio label）：升级为新 API 用法
9. **图表插件未注册**（如 Chart.js Filler）：import 并 register 缺失插件

### framework_behavior 级问题（无需修复）

1. **Element Plus MessageBox cancel error**：用户取消确认框时框架抛出 cancel，属预期行为，加入 console_error_whitelist
2. **Vue Router 首次导航重定向**：SPA 应用的路由守卫重定向属正常行为

### business_data 级问题（需配置/数据修复）

1. **工作流执行失败**：外部 API 凭证未配置（如 LLM API key 为占位符），需在 .env 填入真实凭证
2. **API 返回空数据**：数据库无初始数据，需执行种子数据脚本

### environment 级问题（需环境修复）

1. **node_modules 不完整**：删除问题包后重装（npm install <package>）
2. **前端构建失败**：检查依赖版本兼容性

修复后如 `workflow.regression_after_fix=true`，对失败项重新执行测试。

## 复盘：测试流程的抽象与适用场景

### 成功执行任务的完整步骤

1. **服务启动**：调用 startserver 技能 → 健康检查验证
2. **工具准备**：读取 MCP 工具 schema → 安装浏览器（如需）
3. **页面遍历**：导航（菜单点击 + URL fallback）→ 截图（全页+超时降级）→ 快照（大文件落盘）→ 控制台/网络检查（error 白名单）
4. **按钮交互**：定位按钮 → 点击 → 验证预期动作（dialog/url/state）→ 关闭对话框 → 超时重试验证
5. **登录测试**：获取选择器 → 填表单 → 提交 → 验证跳转和 token
6. **API 测试**：按 P0-P3 优先级排序 → 占位符替换（内置+自定义）→ HTTP 调用 → 状态码+code 验证 → P0 失败阻塞后续
7. **性能审计**：Lighthouse（隔离 context）+ Performance Trace（失败降级）
8. **问题修复**：问题分类 → 代码修复 → 依赖检查 → 前端构建 → 缓存清除 → 回归验证
9. **报告生成**：汇总结果 → 问题分类 → 优先级分组展示 → 生成 markdown 报告

### 任务执行中的不确定性与失败点

| 不确定性 | 发生场景 | 应对策略 |
|---------|---------|---------|
| Playwright 浏览器版本不匹配 | MCP 期望版本与安装版本不一致 | 创建 junction 目录链接 |
| Chrome DevTools 元素交互超时 | UI 组件库菜单项非标准可点击元素 | 改用直接导航 URL |
| 按钮点击超时但操作已生效 | UI 组件库异步更新 DOM | 重新快照验证目标状态 |
| 菜单点击成功但 URL 不跳转 | Element Plus el-menu 路由未触发 | URL 对比检测 + navigate_page fallback |
| MCP 截图相对路径错误 | MCP 工具 cwd 与项目目录不同 | 强制使用绝对路径 |
| 全页截图超时 | 页面 DOM 复杂导致 captureScreenshot 超时 | 降级为视口截图 |
| 快照输出被截断 | a11y 树过大（如日历组件） | 保存到文件后读取 |
| wait_for 文本匹配失败 | a11y 树将文本切分为多个节点 | 使用子串匹配模式 |
| 框架预期 error 误判 | Element Plus MessageBox cancel | console_error_whitelist 过滤 |
| PowerShell curl JSON 转义 | `-d '{"key":"value"}'` 在 PowerShell 中解析失败 | 改用 `Invoke-RestMethod` |
| 前端静态文件路径变化 | V1.2 架构从 Docker 迁移到单机 exe | 配置文件中的路径可配置 |
| 数据库无初始账号 | 首次部署或数据库重置 | fix_strategies 中提供修复脚本 |
| exe 模式 vs 开发模式 | exe 模式下修改代码不生效 | config.yaml 支持 start_args 切换模式 |
| 排期日历 API pending | API 响应慢导致快照时仍在 pending | 等待后重试或检查请求状态 |
| 修复后浏览器缓存旧 JS | 回归测试加载的是旧版本 | ignoreCache 强制刷新 |
| node_modules 不完整 | 依赖包部分文件缺失 | 删除问题包后重装 |
| Lighthouse 在已登录态审计 | 审计页面被路由守卫重定向 | 隔离 context 审计 |
| 业务数据问题误判为代码缺陷 | 工作流因 API key 未配置而失败 | issue_classification 分类 |
| P0 用例失败阻塞后续测试 | 阻塞性用例（如内容安全/备份）失败 | 按 fail_action=block_release 停止低优先级用例，立即报告 |
| 未标注 priority 的用例归类 | 新增测试用例未标注优先级字段 | 按 default_priority（默认 P2）归类 |

### 可抽象的固定流程

**适用于所有 SPA 应用的固定流程**：

1. 环境预检 → 2. 页面遍历（含按钮交互）→ 3. 登录流程 → 4. API 测试（按 P0-P3 优先级排序）→ 5. 性能审计 → 6. 报告（含问题分类+优先级分组）

**固定判断逻辑**：

- 页面成功 = 无 error（排除白名单）+ 网络 200 + 文本匹配（子串/正则）
- 按钮成功 = 点击成功 + 预期动作达成（或超时但状态已达成）
- API 成功 = HTTP 200 + 业务 code 匹配
- 登录成功 = token 返回 + URL 跳转 + 用户信息显示
- 性能合格 = LCP/CLS/TTFB 在阈值内
- 问题分类 = code_defect / business_data / framework_behavior / environment
- 优先级执行 = P0 失败阻塞发布 → P1 发版前修复 → P2 下迭代修复 → P3 仅记录

### 适用场景

- ✅ SPA 应用功能测试（Vue/React/Angular）
- ✅ REST API 接口测试
- ✅ 前端性能审计
- ✅ 登录流程验证
- ✅ 多页面遍历测试
- ✅ UI 组件交互测试（对话框/表单/tab/radio/菜单）
- ✅ 迭代发布前回归测试
- ✅ 代码修改后验证无回归（含前端构建+缓存清除）
- ✅ 控制台警告/错误诊断（区分框架行为与代码缺陷）

### 不适用场景

- ❌ 移动端原生应用测试（需 Appium）
- ❌ 跨浏览器兼容性测试（需 BrowserStack）
- ❌ 大规模压力测试（需 JMeter）
- ❌ 实时通信测试（WebSocket/WebRTC 需特殊处理）
- ❌ 文件上传/下载深度测试
- ❌ 视觉回归测试（像素级对比）
- ❌ 安全渗透测试

## 技能调用示例

### 示例 1：全面测试

用户说"测试前端"：

1. 读取 `config.yaml`
2. 启动服务（如 auto_start_service=true）
3. 按顺序执行 6 阶段测试
4. 遇到问题按 fix_strategies 修复
5. 生成报告到 `report.output_dir`

### 示例 2：仅 API 测试

用户说"测试 API"：

1. 读取 `config.yaml` 的 `api_endpoints` 部分
2. 跳过阶段 2（页面遍历）和阶段 5（性能审计）
3. 执行阶段 4（API 测试）
4. 输出结果

### 示例 3：回归测试

用户说"修改后回归测试"：

1. 读取 `config.yaml`
2. 跳过阶段 1 中已运行的服务启动
3. 对修改涉及的页面/API 执行测试
4. 对比上次结果，报告差异

## 注意事项

1. **工作目录**：所有命令在项目根目录下执行，使用 RunCommand 的 `cwd` 参数
2. **PowerShell 语法**：不支持 `&&`，多命令用 `;` 分隔
3. **MCP 工具优先级**：primary_tool 失败时自动切换 fallback_tool
4. **编码**：截图和报告使用 UTF-8 编码
5. **超时**：页面导航 15s，元素交互 10s，健康检查 30s（均可配置）
6. **占位符替换**：API 路径和请求体支持内置占位符（`${current_date}`、`${current_month}`、`${current_year}`、`${timestamp}`、`${username}`、`${password}`）和自定义占位符（placeholders 区块）
7. **配置优先**：所有参数从 `config.yaml` 读取，不修改配置文件外的任何硬编码值
8. **截图路径**：MCP 工具的相对路径基于其自身 cwd（可能与项目目录不同），必须使用绝对路径
9. **截图降级**：全页截图超时时自动降级为视口截图，避免阻塞测试流程
10. **快照落盘**：快照输出超过 `snapshot.max_size_kb` 时自动保存到文件，避免输出截断
11. **error 白名单**：框架预期 error（如 Element Plus cancel）通过白名单过滤，不触发 FAIL
12. **回归缓存**：修复后回归测试使用 `ignoreCache` 强制刷新，避免加载旧版本静态资源
13. **问题分类**：发现的问题按 issue_classification 分类，只有 code_defect 触发代码修复流程
14. **优先级执行**：API 测试按 `test_priority.execution_order`（P0→P1→P2→P3）顺序执行，P0 失败阻塞后续低优先级用例
15. **优先级报告**：如 `test_priority.group_by_priority=true`，报告按优先级分组展示，含各级通过率摘要
16. **默认优先级**：未标注 `priority` 的测试用例按 `test_priority.default_priority`（默认 P2）归类

## 补充章节：基于实战复盘的优化（v2，2026-07-17）

本章节基于真机测试、工具层 bug 识别、小程序专项检查等实战复盘，补充以下内容：
- 新增配置区块：`env_isolation_check`、`miniprogram_check`、`tool_bug_signatures`、`realdevice_check`
- 新增测试阶段：阶段 7-9
- 新增判断逻辑：环境隔离、页面四件套、事件对称、工具层 bug 识别
- 新增问题分类：`tool_layer_bug`
- 补充修复策略、复盘内容、适用场景、注意事项

### 配置文件新增区块

| 区块 | 作用 |
|------|------|
| `env_isolation_check` | 环境隔离检查（扫描硬编码 localhost/127.0.0.1） |
| `miniprogram_check` | 小程序专项检查（页面四件套、事件对称、401 重试防护） |
| `tool_bug_signatures` | 工具层 bug 特征库（识别开发工具版本 bug） |
| `realdevice_check` | 真机测试预检（服务暴露、IP 可达性、域名校验） |

### 阶段 7：环境隔离与配置一致性检查

如 `env_isolation_check.enabled=true` 且 `check_phase=pre_test`，在阶段 1 之后执行：

```
1. 遍历 env_isolation_check.scan_files 中每个文件：
   a. 读取文件内容
   b. 检查是否包含 hardcoded_patterns 中的任一模式
   c. 如命中，记录违规：文件路径 + 命中模式 + expected_source
2. 检查 .env 中的 required_fields：
   a. APP_HOST 是否为 0.0.0.0（真机测试必须）
   b. AUDIO_BASE_URL 是否为 http://<lan_ip>:8000 格式
3. 如违规且 severity_on_violation=FAIL，标记测试阻塞
4. 如需自动检测 LAN IP，执行 lan_ip_detect_command
5. 记录环境隔离检查结果（PASS/WARN/FAIL + 违规清单）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有文件无硬编码 localhost + .env 字段正确 | PASS |
| .env 字段值不匹配但无硬编码 | WARN |
| 代码文件中存在硬编码 localhost | FAIL（真机测试阻塞） |

### 阶段 8：小程序专项预检

如 `miniprogram_check.enabled=true`，在阶段 7 之后执行：

#### 8.1 页面四件套完整性检查

```
1. 列出 miniprogram_check.root_dir/pages_dir 下所有页面目录
2. 对每个页面目录，检查 required_extensions 中的文件是否存在
3. 如缺失，记录违规：页面名 + 缺失文件后缀
4. 如 severity_on_missing=FAIL，标记测试阻塞
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有页面四件套齐全 | PASS |
| 缺失 .wxss（样式文件，可降级） | WARN |
| 缺失 .json/.js/.wxml（核心文件） | FAIL |

#### 8.2 事件绑定对称性检查

```
1. 遍历 event_binding_check.scan_files 中每个文件
2. grep bind_prefixes（如 onPlay/onPause）出现的次数和位置
3. grep 对应的 unbind_prefixes（如 offPlay/offPause）是否出现
4. 检查 unbind_location（onUnload/onHide）中是否调用了解绑方法
5. 如绑定未解绑，记录违规：文件 + 方法 + 绑定位置
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有 onXxx 都有对应 offXxx 且在 onUnload/onHide 中调用 | PASS |
| 有 onXxx 但无 offXxx（可能在 onUnload 中用匿名函数无法检测） | WARN |
| 明确在 onLoad 绑定但 onUnload 中无解绑代码 | WARN（异步回调堆积风险） |

#### 8.3 401 重试循环防护检查

```
1. 读取 auth_retry_check.scan_files 中的 api.js
2. 检查 required_patterns 是否都存在：
   - _retried 标志（防止单次请求无限重试）
   - startsWith('/auth/') 排除（防止 /auth/login 401 触发 refreshToken 死循环）
3. 如缺失，记录违规
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 同时存在 _retried 标志和 /auth/ 路径排除 | PASS |
| 缺失任一模式 | FAIL（可能导致 401 无限循环） |

### 阶段 9：真机测试预检

如 `realdevice_check.enabled=true`，在阶段 8 之后执行：

```
1. 遍历 realdevice_check.preflight_checks 中每个预检项
2. 按 check 类型执行：
   - http_get：GET target，检查响应是否为 expected
   - env_field：读取 .env 中 target 字段，检查值是否匹配 expected
   - file_pattern：读取 target 文件，检查是否包含 pattern
   - manual：提示用户手动验证 instruction
3. 如检查失败且 severity_on_fail=FAIL，标记真机测试阻塞
4. 记录真机测试预检结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有预检项通过 | PASS（可进行真机测试） |
| manual 项未确认 | WARN（需用户确认） |
| http_get/env_field/file_pattern 项失败 | FAIL（真机测试阻塞） |

### 新增问题分类：tool_layer_bug

在 `issue_classification` 中新增分类：

| 分类 | 含义 | 处理方式 |
|------|------|----------|
| tool_layer_bug | 开发工具版本 bug（如微信开发者工具 3.17.0 webview 路由 bug） | 报告中标注工具名称+受影响版本+修复步骤，不修改代码 |

**识别流程**：
1. 收集控制台 error/warn 日志
2. 遍历 `tool_bug_signatures` 中每个特征库
3. 如日志包含任一 `signature_keywords`，匹配为对应工具 bug
4. 检查工具版本是否在 `affected_versions` 范围内
5. 如匹配，归类为 `tool_layer_bug`，输出 `fix_steps`

### 新增修复策略

补充以下修复策略到 `fix_strategies`：

#### FAIL 级（必须修复）

1. **真机测试网络异常**：硬编码 localhost 不可达 → 检查 `env_isolation_check` 违规清单，替换为局域网 IP
2. **小程序页面跳转失败**：缺 .json 文件 → 检查 `miniprogram_check.page_files_check` 违规清单，补全四件套
3. **401 重试无限循环**：api.js 缺 _retried 标志或 /auth/ 排除 → 按 `auth_retry_check.required_patterns` 补全
4. **后端统计字段误用**：用 PlayLog.duration 而非 PlayProgress.position → 验证 ORM 字段语义

#### WARN 级（可继续测试）

1. **微信开发者工具 webview 路由 bug**：3.17.0 灰度版 → 降级基础库至 3.7.x/3.6.0，清缓存，重启
2. **Edge 最小化自动恢复**：用户配置损坏 → 重命名 User Data 目录重置配置
3. **事件绑定泄漏**：onLoad 绑定未在 onUnload 解绑 → 补全 offXxx 调用
4. **navigateTo 失败**：页面 .json 缺失 → 补全 .json 或降级为 reLaunch

### 补充复盘：测试流程的不确定性与失败点

基于本次实战复盘新增的不确定性：

| 不确定性 | 发生场景 | 应对策略 |
|---------|---------|---------|
| 工具层 bug 误判为代码 bug | 微信开发者工具 3.17.0 报 webviewId 错误 | `tool_bug_signatures` 特征匹配，归类为 `tool_layer_bug` |
| localhost 多处硬编码 | 真机测试报网络异常，难以定位所有位置 | `env_isolation_check` 扫描所有配置文件 |
| 小程序页面文件缺失不报错 | 缺 .json 文件，功能异常但无错误日志 | `page_files_check` 主动检查四件套完整性 |
| 事件绑定泄漏无即时错误 | onLoad 重复绑定导致回调堆积 | `event_binding_check` 检查 on/off 对称性 |
| 401 重试无限循环 | /auth/login 返回 401 触发 refreshToken 死循环 | `auth_retry_check` 检查 _retried + /auth/ 排除 |
| 真机 vs 模拟器差异 | 模拟器可用 localhost，真机不可达 | `realdevice_check` 预检所有真机必需配置 |
| 后端统计字段语义混淆 | PlayLog.duration vs PlayProgress.position | 代码审查阶段验证 ORM 字段语义 |
| navigateTo 静默失败 | 缺页面 .json 时跳转无反应 | `page_files_check` 预检 + navigateTo 失败降级 reLaunch |

### 补充可抽象的固定流程

**新增固定流程**（适用于所有小程序+后端项目）：

1. **环境隔离预检流程**：扫描代码硬编码 → 检查 .env 字段 → 检测 LAN IP → 输出违规清单
2. **小程序专项预检流程**：页面四件套检查 → 事件绑定对称性检查 → 401 重试防护检查
3. **真机测试预检流程**：服务暴露检查 → IP 可达性验证 → 域名校验关闭确认 → 小程序配置同步
4. **工具层 bug 识别流程**：日志特征匹配 → 版本范围验证 → 归类为 tool_layer_bug → 输出修复步骤

**新增固定判断逻辑**：

- 环境隔离合格 = 代码无硬编码 localhost + .env 字段正确
- 页面四件套完整 = 每个页面目录都有 .json/.js/.wxml/.wxss
- 事件绑定对称 = 每个 onXxx 都有对应 offXxx 且在 onUnload/onHide 调用
- 401 重试安全 = 存在 _retried 标志 + /auth/ 路径排除
- 真机预检通过 = http_get + env_field + file_pattern 全部 PASS + manual 项已确认
- 工具 bug 识别 = 日志匹配 signature_keywords + 版本在 affected_versions 范围内

### 补充适用场景

新增适用场景：

- ✅ 小程序真机测试前预检（环境隔离、IP 可达性、域名校验）
- ✅ 小程序页面文件完整性自动检查（四件套）
- ✅ 小程序事件绑定泄漏检测（on/off 对称性）
- ✅ 401 重试无限循环预防
- ✅ 开发工具版本 bug 快速识别（微信开发者工具/Edge）
- ✅ 环境配置一致性验证（前后端 URL 同步）

新增不适用场景：

- ❌ 小程序原生组件单元测试（需 Jest + miniprogram-simulate）
- ❌ 小程序云函数测试（需云开发测试框架）
- ❌ 小程序包体积分析（需微信开发者工具内置工具）

### 补充注意事项

17. **环境隔离预检**：真机测试前必须执行 `env_isolation_check`，扫描所有硬编码 localhost
18. **页面四件套检查**：小程序每个页面必须有 .json/.js/.wxml/.wxss，缺失会导致功能异常
19. **事件绑定对称性**：onLoad 中的 onXxx 必须在 onUnload 中有对应 offXxx，防止回调堆积
20. **401 重试防护**：api.js 中 request 函数必须有 _retried 标志 + /auth/ 路径排除，防止无限循环
21. **工具层 bug 识别**：遇到 webviewId/mainframe 500 等错误，先检查 `tool_bug_signatures` 是否匹配，避免误判为代码 bug
22. **真机测试预检**：真机测试前必须执行 `realdevice_check`，确认 APP_HOST=0.0.0.0、AUDIO_BASE_URL 配置正确、域名校验已关闭
23. **ORM 字段语义验证**：聚合查询前必须确认字段语义（如 PlayLog.duration 是节目总时长 vs PlayProgress.position 是实际收听位置）
24. **navigateTo 失败降级**：navigateTo 失败时应降级为 reLaunch，避免页面跳转静默失败

## 补充章节：基于频道级隔离与 RSS 源验证复盘的优化（v3，2026-07-17）

本章节基于频道级数据隔离修复、RSS 源端到端验证、PowerShell 工具链兼容性等实战复盘，补充以下内容：
- 新增配置区块：`rss_source_check`、`data_isolation_check`、`powershell_compat_check`、`third_party_service_check`
- 新增测试阶段：阶段 10-13
- 新增判断逻辑：RSS 源可达性诊断、频道级数据隔离、PowerShell 脚本兼容性、第三方服务限流识别
- 新增问题分类：`data_isolation_violation`、`rss_source_unreachable`、`third_party_rate_limit`
- 补充修复策略、复盘内容、适用场景、注意事项

### 配置文件新增区块

| 区块 | 作用 |
|------|------|
| `rss_source_check` | RSS 源可达性预检（串行验证、内容类型检查、UA 兼容性） |
| `data_isolation_check` | 频道级数据隔离预检（OR NULL 兜底检测、channel_id 严格过滤） |
| `powershell_compat_check` | PowerShell Python 脚本调用兼容性检查（-u 参数、2>&1 重定向） |
| `third_party_service_check` | 第三方转换服务依赖诊断（rsshub/plink 限流、DNS 污染、UA 拒绝） |

### 阶段 10：RSS 源可达性预检

如 `rss_source_check.enabled=true` 且 `check_phase=pre_test`，在阶段 9 之后执行：

```
1. 读取 rss_source_check.sources_config（如 rss.yaml 路径）
2. 加载所有 RSS 源配置（name/url/category）
3. 按 verify_mode 执行验证：
   - serial（默认）：串行验证，间隔≥interval_sec（默认 3.0s），避免第三方服务限流
   - parallel：并发验证（仅限原生 RSS，第三方转换服务禁用）
4. 对每个源执行 diagnose_rss_source：
   a. HTTP GET 请求（按 ua_config 配置 UA）
   b. 分类诊断结果：
      - ok：HTTP 200 + RSS XML + 条目>0
      - not_rss：HTTP 200 但 Content-Type 为 text/html
      - zero_entries：HTTP 200 + 0 条目（可能限流，需串行复测）
      - not_found：HTTP 404（源被封禁或路径错误）
      - forbidden：HTTP 403（WAF 拦截或 UA 被拒绝）
      - dns_error：ConnectError（DNS 污染或 TCP 阻断）
      - timeout：TimeoutException（连接超时）
5. 如第三方转换服务源（按 third_party_service_check.services 配置识别）验证失败，自动切换串行模式复测
6. 统计结果：可达源数/失效源数/限流源数
7. 如失效源数 > max_failure_ratio（默认 0.1），标记测试阻塞
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有源可达（或失效比例 < max_failure_ratio） | PASS |
| 第三方转换服务源限流（串行复测后恢复） | WARN（标注限流风险） |
| 原生 RSS 源失效（HTTP 404/DNS 错误） | FAIL（测试阻塞） |
| 第三方转换服务源持续失效（串行复测仍 0 条目） | FAIL（源被封禁） |
| 源返回 HTML 而非 RSS（Content-Type: text/html） | FAIL（站点未提供 RSS） |

### 阶段 11：频道级数据隔离预检

如 `data_isolation_check.enabled=true`，在阶段 10 之后执行：

```
1. 遍历 data_isolation_check.scan_dirs 中每个目录（如 backend/app/services/、backend/app/workflow/）
2. 对每个 .py 文件，grep 检查：
   a. or_(.*channel_id.*is_(None))：SQLAlchemy or_ 兜底逻辑
   b. OR.*channel_id IS NULL：SQL 原生 OR NULL 兜底
   c. or_.*channel_id：未使用的 or_ 导入残留
3. 如命中，记录违规：文件路径 + 行号 + 命中模式 + severity
4. 检查 crawler 0-count 逻辑：
   a. grep if count == 0 或 if material_count == 0
   b. 检查后续是否有 OR NULL 兜底查询
5. 如违规且 severity_on_violation=FAIL，标记测试阻塞
6. 记录数据隔离检查结果（PASS/WARN/FAIL + 违规清单）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有查询严格按 channel_id 过滤，无 OR NULL 兜底 | PASS |
| 全局工作流（channel_id=None）查询用 IS NULL（正常） | PASS |
| 专门频道查询含 OR channel_id IS NULL 兜底 | FAIL（跨频道污染风险） |
| crawler 0-count 检查含 OR NULL 兜底 | FAIL（跨频道污染风险） |
| or_ 导入但未使用（修复后未清理） | WARN（代码整洁性） |

### 阶段 12：PowerShell Python 脚本调用兼容性检查

如 `powershell_compat_check.enabled=true` 且当前环境为 Windows + PowerShell，在阶段 11 之后执行：

```
1. 遍历 powershell_compat_check.scan_files 中每个文件（如 *.ps1、package.json）
2. 对 .ps1 文件，grep 检查：
   a. python script.py（无 -u 参数）→ 违规
   b. python -u script.py 后无 2>&1 重定向 → 违规
   c. 因 RemoteException 警告而 exit 1 的逻辑 → 违规（logger.error 是正常日志）
3. 对 package.json，grep 检查 scripts 字段中 python 调用规范
4. 如违规且 severity_on_violation=WARN，记录警告
5. 如违规且 severity_on_violation=FAIL，标记测试阻塞
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有 Python 脚本调用使用 `python -u script.py 2>&1` | PASS |
| Python 脚本调用无 -u 参数（stdout 缓冲风险） | WARN（输出可能不可见） |
| Python 脚本调用无 2>&1 重定向（stderr 丢失） | WARN（logger.error 输出丢失） |
| 因 RemoteException 警告而 exit 1（误判脚本失败） | FAIL（logger.error 是正常日志） |

### 阶段 13：第三方转换服务依赖诊断

如 `third_party_service_check.enabled=true`，在阶段 12 之后执行：

```
1. 读取 third_party_service_check.services 配置（含 service_name/url_pattern/dns_check/tcp_check 等字段）
2. 遍历 rss.yaml 中所有源，按 url_pattern 识别依赖第三方服务的源：
   a. URL 匹配 url_pattern → 依赖对应第三方服务
   b. 支持多个第三方服务配置（如 rsshub/plink 等，均通过 config.yaml 管理）
3. 对每个第三方服务执行诊断：
   a. DNS 解析检查：nslookup <service_domain>（域名从 url_pattern 提取）
   b. TCP 连接检查：Test-NetConnection <service_domain> -Port 443
   c. HTTP 可达性检查：GET <service_domain>，检查响应
4. 分类诊断结果（分类标准通过 config.yaml 的 result_categories 配置）：
   - dns_polluted：DNS 解析失败（DNS 污染）
   - tcp_blocked：TCP 连接失败（TCP 阻断）
   - rate_limited：HTTP 200 但并发时部分源 0 条目（会话级限流）
   - service_down：服务完全不可达
   - ok：服务正常
5. 如第三方服务 dns_polluted 或 tcp_blocked，标记所有依赖该服务的源为失效
6. 如第三方服务 rate_limited，标注"验证时需串行间隔≥interval_sec"
7. 生成第三方服务依赖报告：服务名/状态/影响源数/建议
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有第三方服务正常可达 | PASS |
| 第三方服务限流（串行复测后恢复） | WARN（标注限流风险） |
| 第三方服务 DNS 污染或 TCP 阻断 | FAIL（所有依赖源失效） |
| 第三方服务完全不可达 | FAIL（所有依赖源失效） |

### 新增问题分类

在 `issue_classification` 中新增分类：

| 分类 | 含义 | 处理方式 |
|------|------|----------|
| data_isolation_violation | 数据隔离违规（如 OR NULL 兜底导致跨频道污染） | 触发代码修复流程，移除兜底逻辑 |
| rss_source_unreachable | RSS 源不可达（DNS 污染/TCP 阻断/源被封禁） | 报告中标注源名+失效原因+替代方案，不修改代码 |
| third_party_rate_limit | 第三方服务限流（plink 并发限流假阳性） | 报告中标注服务名+限流特性+串行验证建议 |

**识别流程**：
1. RSS 源验证返回 dns_error/timeout/not_found → `rss_source_unreachable`
2. RSS 源验证返回 zero_entries 但串行复测恢复 → `third_party_rate_limit`
3. 代码扫描发现 OR channel_id IS NULL → `data_isolation_violation`

### 新增修复策略

补充以下修复策略到 `fix_strategies`：

#### FAIL 级（必须修复）

1. **频道级数据隔离违规**：专门频道查询含 OR NULL 兜底 → 移除兜底逻辑，严格按 channel_id 过滤
2. **RSS 源 DNS 污染**：rsshub.app 等服务被 DNS 污染 → 替换为原生 RSS，避免依赖第三方转换服务
3. **RSS 源返回 HTML 而非 RSS**：站点未提供 RSS → 移除该源或寻找原生 RSS 替代
4. **PowerShell 脚本误判 logger.error 为异常**：因 RemoteException 警告而 exit 1 → 理解 stderr 包装机制，不因警告中断

#### WARN 级（可继续测试）

1. **第三方转换服务限流**：plink 并发验证时部分源 0 条目 → 改用串行模式，3s 间隔复测
2. **PowerShell Python 脚本无 -u 参数**：stdout 缓冲风险 → 添加 -u 参数和 2>&1 重定向
3. **or_ 导入未使用**：修复后未清理 import 残留 → 移除未使用的 or_ 导入
4. **RSS 源 UA 被拒绝**：bot UA 访问 Steam 等站点被拒 → 切换为浏览器 UA

### 补充复盘：测试流程的不确定性与失败点

基于本次实战复盘新增的不确定性：

| 不确定性 | 发生场景 | 应对策略 |
|---------|---------|---------|
| 频道级 OR NULL 兜底误用 | 专门频道查询含 OR channel_id IS NULL | `data_isolation_check` 扫描所有 services/workflow 目录 |
| rsshub.app 全站失效 | 大陆环境 DNS 污染 + TCP 阻断 | `third_party_service_check` 诊断第三方服务可达性 |
| plink 并发限流假阳性 | 验证脚本并发≥5 测试 plink 源 | `rss_source_check.verify_mode=serial` 串行验证 |
| PowerShell stdout 缓冲 | `python script.py` 输出不可见 | `powershell_compat_check` 检查 -u 参数和 2>&1 重定向 |
| feedparser HTTP 200+0 条目 | 站点返回 HTML/限流/源被封禁 | `rss_source_check` 分类诊断（not_rss/zero_entries/not_found） |
| rss.yaml name 变更未同步数据库 | channel.rss_sources JSON 数组存储旧 name | `rss_source_check` 比对 rss.yaml 与数据库 name 一致性 |
| UA 被站点拒绝 | bot UA 访问 Steam 等站点 | `rss_source_check.ua_config` 配置浏览器 UA |
| 第三方服务源被封禁 | plink 源返回 404（微信公众号封禁） | `third_party_service_check` 识别 404 并标注替代方案 |

### 补充可抽象的固定流程

**新增固定流程**（适用于所有 RSS 抓取系统 + 多频道系统）：

1. **RSS 源可达性预检流程**：加载 rss.yaml → 串行验证（3s 间隔）→ 分类诊断（ok/not_rss/zero_entries/not_found/dns_error/timeout）→ 统计失效比例 → 生成报告
2. **频道级数据隔离预检流程**：扫描 services/workflow 目录 → grep OR NULL 兜底 → 检查 crawler 0-count 逻辑 → 记录违规清单
3. **PowerShell 脚本兼容性检查流程**：扫描 .ps1/package.json → 检查 python -u + 2>&1 → 检查 RemoteException 误判 → 记录警告
4. **第三方服务依赖诊断流程**：识别依赖第三方服务的源 → DNS/TCP/HTTP 诊断 → 分类（dns_polluted/tcp_blocked/rate_limited/service_down）→ 标注影响源数

**新增固定判断逻辑**：

- RSS 源可达 = HTTP 200 + RSS XML + 条目>0（或串行复测后恢复）
- 频道级隔离合格 = 专门频道查询无 OR NULL 兜底 + crawler 0-count 无 OR NULL 回退
- PowerShell 兼容 = Python 脚本调用含 -u + 2>&1 + 不因 RemoteException 中断
- 第三方服务健康 = DNS 解析成功 + TCP 连接成功 + HTTP 可达（或限流但串行恢复）
- 数据隔离违规 = grep 命中 `OR.*channel_id IS NULL` 或 `or_(.*channel_id.*is_(None))`

### 补充适用场景

新增适用场景：

- ✅ RSS 抓取系统源可达性预检（串行验证、内容类型检查、UA 兼容性）
- ✅ 多频道系统数据隔离预检（OR NULL 兜底检测、channel_id 严格过滤）
- ✅ Windows + PowerShell 工具链兼容性检查（Python 脚本调用规范）
- ✅ 第三方转换服务依赖诊断（rsshub/plink 限流、DNS 污染、UA 拒绝）
- ✅ rss.yaml 与数据库配置同步性验证（name 一致性检查）

新增不适用场景：

- ❌ API 接口可达性测试（非 RSS 源，需用 API 测试流程）
- ❌ 单频道系统数据隔离预检（无 channel_id 字段）
- ❌ bash/zsh 环境脚本兼容性检查（默认行缓冲，无 -u 需求）
- ❌ 纯 Node.js 工具链脚本兼容性检查（无 Python 依赖）

### 补充注意事项

25. **RSS 源串行验证**：第三方转换服务（按 `third_party_service_check.services` 配置识别）必须串行验证，间隔≥`rss_source_check.interval_sec`，避免并发限流假阳性
26. **RSS 源内容类型检查**：HTTP 200 但 0 条目时，必须检查 Content-Type，区分 HTML 响应与 RSS 格式问题
27. **频道级数据隔离**：专门频道查询禁止 OR NULL 兜底，NULL 素材仅全局工作流可用
28. **PowerShell Python 脚本调用**：必须用 `python -u script.py 2>&1`，避免 stdout 缓冲和 stderr 丢失
29. **第三方服务诊断**：第三方转换服务（按 `third_party_service_check.services` 配置）如出现 DNS 污染或 TCP 阻断，所有依赖该服务的源需替换为原生 RSS
30. **rss.yaml 与数据库同步**：rss.yaml name 变更后必须同步数据库 channel.rss_sources JSON 数组
31. **UA 兼容性**：部分站点（如 Steam）拒绝 bot UA，需通过 `rss_source_check.ua_config` 配置浏览器 UA
32. **RemoteException 非异常**：PowerShell 包装 Python logger.error 为 RemoteException 警告是正常行为，不应中断脚本

## 补充章节：基于 AI 服务模块测试经验的优化（v4，2026-07-17）

本章节基于 AI 服务模块（TTS/LLM）测试过程中遇到的异步交互、会话保持、脱敏值回传、错误码可读化等实战问题，补充以下内容：
- 新增配置区块：`async_interaction`、`session_persistence`、`config_form_testing`、`service_restart_verification`、`ai_service_testing`
- 新增测试阶段：阶段 14-18
- 新增判断逻辑：异步交互结果、会话保持、配置表单可用性、脱敏值回传、服务重启验证
- 补充修复策略、复盘内容、适用场景、注意事项

### 配置文件新增区块

| 区块 | 作用 |
|------|------|
| `async_interaction` | 异步交互测试（按钮 disabled/ready 信号、响应超时、轮询间隔） |
| `session_persistence` | 会话保持测试（重启后登录态失效检测、自动重新登录） |
| `config_form_testing` | 配置表单可用性测试（脱敏值前缀、模糊标签黑名单、密钥获取链接） |
| `service_restart_verification` | 服务重启验证（前端构建后重启后端、健康检查重试） |
| `ai_service_testing` | AI 服务测试扩展（LLM/TTS 测试参数、阿里云 NLS 错误码映射、LLM 预设列表） |

### 阶段 14：异步交互测试

对所有异步按钮（如"测试连接"、"AI 生成"、"批量操作"）执行：

```
1. 点击异步按钮
2. 检查按钮是否变为 button_busy_signal（disabled）状态
3. 轮询等待：
   - 轮询间隔 = async_interaction.poll_interval_ms
   - 总超时 = async_interaction.response_timeout_ms
   - 成功条件：按钮恢复 button_ready_signal（not disabled）
4. 读取页面快照，检查是否出现结果文本（成功提示/错误提示）
5. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 按钮 disabled → 恢复 → 结果文本出现 | PASS |
| 按钮恢复但无结果文本 | WARN（可能结果渲染慢） |
| 超时后按钮仍 disabled | FAIL（API 无响应） |
| 出现错误提示文本 | 按 error 内容分类（business_data / code_defect） |

**适用场景**：所有异步按钮（测试连接、AI 生成、批量操作）
**不适用场景**：同步按钮（导航、筛选）

### 阶段 15：会话保持测试

如 `session_persistence.relogin_after_restart=true`，在服务重启后执行：

```
1. 服务重启后访问受保护页面（如 /ai-config）
2. 检查页面响应是否出现 session_persistence.auth_failure_signals 中的信号：
   - HTTP 500
   - "未授权"
   - "登录已过期"
3. 如出现失效信号且 session_persistence.auto_relogin=true：
   a. 从 credentials.admin 读取账号
   b. 执行阶段 3 登录流程
4. 重新访问目标页面，验证可访问性
5. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 重启后受保护页面可正常访问 | PASS |
| 出现失效信号 → 自动 relogin → 重新访问成功 | PASS（自动恢复） |
| 出现失效信号但 auto_relogin=false | FAIL（需手动登录） |
| 自动 relogin 后仍无法访问 | FAIL（认证服务异常） |

**适用场景**：服务重启、长时间测试后 token 过期
**不适用场景**：首次测试（无历史登录态）

### 阶段 16：配置表单可用性测试

对所有配置管理页面（AI 服务、TTS、存储配置等）执行：

```
1. 遍历所有配置表单字段
2. 检查字段标签是否在 config_form_testing.ambiguous_labels 黑名单中：
   - "API Key"
   - "App Key"
   - "Secret"
3. 检查密钥字段是否有配套的 el-link 超链接（require_key_acquisition_link）
4. 检查第三方错误码是否可读化（third_party_error_code_readable）：
   - 触发测试连接，观察错误提示
   - 对照 ai_service_testing.aliyun_nls_error_hints 检查错误码是否被翻译
5. 记录违规清单
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有字段标签具体 + 密钥字段有获取链接 + 错误码可读化 | PASS |
| 字段标签含模糊词（如 "API Key"） | FAIL（用户易误填） |
| 密钥字段无获取链接 | WARN（用户不知从哪获取） |
| 第三方错误码未可读化 | FAIL（用户不知如何修复） |

**适用场景**：所有配置管理页面（AI 服务、TTS、存储配置等）
**不适用场景**：非配置类页面（列表、详情）

### 阶段 17：脱敏值回传测试

对含密钥字段的测试连接功能执行：

```
1. 加载配置页面，记录密钥字段值（应为 ****xxxx 脱敏形式）
2. 不修改密钥字段，直接点击测试连接
3. 检查后端响应：
   - 成功：后端识别脱敏值并回退到已保存的真实密钥
   - 失败：后端将脱敏值当作真实 token，报 token invalid
4. 修改密钥字段为明文新值，点击测试连接
5. 检查后端是否使用新明文值（响应应为成功或新值的鉴权失败）
6. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 脱敏值测试连接成功（后端回退）+ 明文值测试连接使用新值 | PASS |
| 脱敏值测试连接报 token invalid | FAIL（后端未识别脱敏值） |
| 明文值测试连接仍使用旧密钥 | FAIL（后端未更新密钥） |

**适用场景**：所有含密钥字段的测试连接功能
**不适用场景**：无密钥字段的测试功能

### 阶段 18：服务重启验证测试

如 `service_restart_verification.rebuild_requires_backend_restart=true`，在前端代码变更后执行：

```
1. 执行前端构建（workflow.build_before_regression.command）
2. 停止后端服务（service.stop_script）
3. 启动后端服务（service.start_script）
4. 轮询健康检查端点：
   - 最多重试 service_restart_verification.health_check_retries 次
   - 每次间隔 1 秒
   - 总超时 = service_restart_verification.ready_timeout_sec
5. 健康检查通过后访问页面，验证新代码已加载（页面包含新功能文本）
6. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 健康检查 200 + 页面包含新功能文本 | PASS |
| 健康检查 200 但页面仍为旧代码 | FAIL（静态文件挂载缓存） |
| 健康检查超时 | FAIL（服务启动失败） |

**适用场景**：开发模式下前端代码变更后的验证
**不适用场景**：exe 模式（需重新打包，非重启）

### 新增修复策略

补充以下修复策略到 `fix_strategies`：

#### FAIL 级（必须修复）

1. **异步按钮结果未出现**：点击后立即读快照 → 增加 `async_interaction.response_timeout_ms` 等待
2. **服务重启后页面 500**：登录态丢失 → 自动重新登录（`session_persistence.auto_relogin`）
3. **脱敏值被当作真实 token**：前端回传 ****xxxx → 后端 `_is_masked` 判断 + 回退到真实密钥
4. **错误码不可读**：阿里云 NLS 40000001 → 添加 `ai_service_testing.aliyun_nls_error_hints` 映射
5. **字段标签模糊**："API Key" 标签 → 改为 "AccessToken" 等具体名称
6. **前端构建后未加载新代码**：构建后未重启后端 → 执行 `service_restart_verification` 流程

#### WARN 级（可继续测试）

1. **按钮恢复但无结果文本**：结果渲染慢 → 增加 `response_timeout_ms` 或重新快照
2. **密钥字段无获取链接**：用户不知从哪获取 → 添加 el-link 超链接指向官方文档

### 补充复盘：测试流程的不确定性与失败点

基于本次 AI 服务模块测试复盘新增的不确定性：

| 不确定性 | 发生场景 | 应对策略 |
|---------|---------|---------|
| 异步按钮结果未出现 | 点击后立即读快照 | `async_interaction.response_timeout_ms` 等待 |
| 服务重启后页面 500 | 服务重启后访问受保护页面 | `session_persistence.auto_relogin` 自动登录 |
| 脱敏值被当作真实 token | 前端回传 ****xxxx | 后端 `_is_masked` 判断 + 回退 |
| 错误码不可读 | 阿里云 NLS 40000001 | `ai_service_testing.aliyun_nls_error_hints` 映射 |
| 字段标签模糊 | "API Key" 标签 | `config_form_testing.ambiguous_labels` 黑名单 |
| 前端构建后未加载新代码 | 构建后未重启后端 | `service_restart_verification` 重启流程 |

### 补充可抽象的固定流程

**新增固定流程**（适用于所有含异步交互+配置管理的系统）：

1. **异步交互测试流程**：点击 → 检查 disabled → 轮询等待 → 检查 ready → 读快照
2. **会话保持测试流程**：访问受保护页 → 检测失效信号 → 自动登录 → 重新访问
3. **配置表单测试流程**：遍历字段 → 检查标签 → 检查链接 → 检查错误码可读化
4. **脱敏值回传测试流程**：记录脱敏值 → 不修改直接测试 → 检查后端回退 → 修改明文测试
5. **服务重启验证流程**：构建 → 停止 → 启动 → 健康检查轮询 → 页面验证

**新增固定判断逻辑**：

- 异步交互成功 = 按钮 disabled → 恢复 → 结果文本出现
- 会话保持成功 = 重启后自动 relogin → 受保护页可访问
- 配置表单合格 = 标签具体 + 密钥字段有获取链接 + 错误码可读化
- 脱敏值回传正确 = 脱敏值测试连接成功（后端回退）+ 明文值测试连接使用新值
- 服务重启验证通过 = 健康检查 200 + 页面包含新功能文本

### 补充适用场景

新增适用场景：

- ✅ 异步按钮交互测试（测试连接、AI 生成、批量操作）
- ✅ 服务重启后会话恢复验证（自动重新登录）
- ✅ 配置表单可用性测试（字段标签、密钥获取链接、错误码可读化）
- ✅ 脱敏值回传测试（密钥字段的安全回退验证）
- ✅ 前端构建后服务重启验证（开发模式代码变更生效）

新增不适用场景：

- ❌ 同步按钮交互测试（无 disabled/ready 状态变化）
- ❌ 首次测试的会话保持（无历史登录态）
- ❌ 无密钥字段的脱敏值测试（无脱敏值回传需求）
- ❌ exe 模式的服务重启验证（需重新打包）

### 补充注意事项

33. **异步按钮等待响应**：测试连接按钮点击后必须等待 `async_interaction.response_timeout_ms`，否则快照看不到错误提示
34. **服务重启后重新登录**：服务重启后登录态丢失，需通过 `session_persistence.auto_relogin` 自动重新登录
35. **脱敏值识别**：前端回传 ****xxxx 脱敏值时，后端必须通过 `_is_masked` 判断并回退到真实密钥
36. **错误码可读化**：第三方错误码（如阿里云 NLS 40000001）必须通过 `ai_service_testing.aliyun_nls_error_hints` 映射为可读提示
37. **字段标签具体化**：密钥字段标签禁止使用 "API Key" 等模糊词，应改为 "AccessToken" / "SecretKey" 等具体名称
38. **前端构建后重启后端**：开发模式下前端构建产物在 admin-web/dist，后端静态文件挂载需重启才生效
39. **密钥获取链接**：密钥字段必须配套 el-link 超链接，指向官方获取入口
40. **LLM 预设一致性**：测试时选择的 LLM 预设必须与后端 `LLM_PRESETS` 一致（通过 `ai_service_testing.llm_presets` 管理）

## 四维度复盘总览（基于 AI 服务模块测试经验）

### 维度 1：成功执行任务的完整步骤（AI 服务测试）

1. 健康检查 → 确认服务可用
2. API 端点测试 → 4 个 AI 服务 API 全部返回 200 + code=0
3. 页面遍历 → /ai-config 页面包含"AI 服务配置"文本
4. 预设选择器测试 → 9 个预设全部可选，表单自动填充
5. 密钥获取链接测试 → 链接指向正确 URL，target=_blank
6. TTS 字段标签测试 → 标签为"AccessToken"非"API Key"
7. 异步按钮测试 → 测试连接点击后 disabled → 恢复 → 结果文本出现
8. 脱敏值回传测试 → 不修改密钥直接测试，后端回退到真实密钥
9. 错误码可读化测试 → NLS 40000001 显示"请确认填写的是 NLS AccessToken"
10. Lighthouse 性能审计 → Accessibility/Best Practices/SEO 达标

### 维度 2：不确定性与失败点

| 失败点 | 触发条件 | 影响 | 根因 | 修复 |
|--------|----------|------|------|------|
| 异步按钮结果未出现 | 点击后立即读快照 | 看不到错误提示 | 未等待响应 | 增加 `response_timeout_ms` 等待 |
| 服务重启后页面 500 | 服务重启后访问受保护页面 | 无法测试 | 登录态丢失 | 自动重新登录 |
| 脱敏值被当作真实 token | 前端回传 ****xxxx | 测试连接报 token invalid | 后端未识别脱敏值 | `_is_masked` 判断 + 回退 |
| 错误码不可读 | 阿里云 NLS 40000001 | 用户不知如何修复 | 无错误码映射表 | `aliyun_nls_error_hints` 映射 |
| 字段标签模糊 | "API Key" 标签 | 用户误填 AccessKey Secret | 通用标签无歧义消除 | 改为"AccessToken" |
| 前端构建后未加载新代码 | 构建后未重启后端 | 测试的还是旧代码 | 静态文件挂载缓存 | 重启后端 |

### 维度 3：可抽象的固定流程

- **异步交互测试流程**：点击 → 检查 disabled → 等待 → 检查 ready → 读快照
- **会话保持测试流程**：访问受保护页 → 检测失效信号 → 自动登录 → 重新访问
- **配置表单测试流程**：遍历字段 → 检查标签 → 检查链接 → 检查错误码可读化
- **服务重启验证流程**：构建 → 停止 → 启动 → 健康检查轮询 → 页面验证

### 维度 4：适用场景与不适用场景

| 流程 | 适用 | 不适用 |
|------|------|--------|
| 异步交互测试 | 所有异步按钮 | 同步按钮 |
| 会话保持测试 | 服务重启、token 过期 | 首次测试 |
| 配置表单测试 | 配置管理页面 | 列表/详情页 |
| 脱敏值回传测试 | 含密钥字段的测试连接 | 无密钥字段 |
| 服务重启验证 | 开发模式前端变更 | exe 模式（需重新打包） |

## 补充章节：基于数据库维护模块测试经验的优化（v5，2026-07-17）

本章节基于数据库维护 + 系统清理模块开发的 18/18 PASS 测试实践，补充以下内容：
- 新增配置区块：`db_admin_check`、`maintenance_check`、`confirm_token_check`
- 新增测试阶段：阶段 19
- 新增判断逻辑：白名单验证、CONFIRM_DELETE 令牌、dry_run 预览、审计日志、VACUUM 预检
- 补充修复策略、复盘内容、适用场景、注意事项

### 配置文件新增区块

| 区块 | 作用 |
|------|------|
| `db_admin_check` | 数据库维护页面预检（白名单表数、表浏览、CRUD、级联删除、导出导入） |
| `maintenance_check` | 系统清理页面预检（dry_run 预览、VACUUM、过期记录清理、审计日志） |
| `confirm_token_check` | CONFIRM_DELETE 令牌验证（令牌输入、hmac.compare_digest） |

### 阶段 19：数据库维护模块专项测试

如 `db_admin_check.enabled=true`，在阶段 18 之后执行：

```
1. 数据库维护页面遍历（db_admin_check.page_path）：
   a. 导航到数据库维护页面
   b. 检查页面包含 db_admin_check.expected_text（如"数据库维护"）
   c. 检查左侧表列表是否加载（白名单表数 == db_admin_check.expected_table_count）
   d. 点击表名，检查右侧表数据是否加载
2. CRUD 操作测试：
   a. 新增记录：填写表单 → 提交 → 检查列表新增一行
   b. 编辑记录：点击编辑 → 修改字段 → 提交 → 检查字段已更新
   c. 删除记录：点击删除 → 输入 CONFIRM_DELETE 令牌 → 检查列表减少一行
3. 级联删除预览测试：
   a. 选择有外键关联的记录 → 点击删除
   b. 检查是否弹出级联预览（显示受影响的从表和记录数）
   c. 确认删除后检查从表记录是否同步处理
4. 导出导入测试：
   a. 点击导出 → 检查返回的 JSON/CSV 数据
   b. 检查导出数据中敏感字段是否脱敏（****）
   c. 导入数据 → 检查记录是否新增
5. 系统清理页面测试（maintenance_check.page_path）：
   a. 导航到系统清理页面
   b. dry_run 预览：开启预览开关 → 点击执行 → 检查返回预览结果（记录数）
   c. 实际清理：关闭预览开关 → 输入 CONFIRM_DELETE → 点击执行 → 检查记录已删除
   d. VACUUM 测试：点击 VACUUM 按钮 → 检查数据库文件大小是否减小
6. 审计日志验证：
   a. 查询审计日志 API（confirm_token_check.audit_log_endpoint）
   b. 检查最近 N 条审计日志是否包含上述操作记录
   c. 检查审计日志字段完整性（action/table_name/record_id/operator/created_at）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 白名单表数匹配 + CRUD 成功 + 级联预览展示 + 导出脱敏 + dry_run 预览 + 审计日志完整 | PASS |
| 白名单表数不匹配 | FAIL（白名单配置错误） |
| 敏感字段未脱敏 | FAIL（安全漏洞） |
| CONFIRM_DELETE 令牌未校验 | FAIL（危险操作无双重确认） |
| dry_run 预览不生效 | FAIL（清理操作无预览） |
| 审计日志缺失 | WARN（操作不可追溯） |
| VACUUM 在事务内执行 | FAIL（OperationalError） |

**新增问题分类**：

| 分类 | 含义 | 处理方式 |
|------|------|----------|
| db_admin_violation | 数据库维护安全违规（无白名单/未脱敏/无令牌） | 触发代码修复流程 |
| maintenance_violation | 系统清理安全违规（无 dry_run/审计缺失） | 触发代码修复流程 |

### 新增修复策略

补充以下修复策略到 `fix_strategies`：

#### FAIL 级（必须修复）

1. **白名单表数不匹配**：db_admin_check 配置的 expected_table_count 与实际不符 → 检查 settings.DB_ADMIN_ALLOWED_TABLES 配置
2. **敏感字段未脱敏**：导出数据含明文密码 → 补充静态+动态字段名匹配脱敏逻辑
3. **CONFIRM_DELETE 令牌未校验**：危险操作端点无 confirm_token 参数 → 添加令牌校验 + hmac.compare_digest
4. **VACUUM 在事务内执行**：OperationalError: cannot VACUUM → 改用 AUTOCOMMIT 隔离级别
5. **SQLAlchemy Inspector 使用错误**：run_sync 回调直接传 Session → 先 .connection() 转换
6. **main.py 导入缺失**：NameError: name 'xxx' is not defined → 补充 import 语句 + 启动前预检

#### WARN 级（可继续测试）

1. **审计日志缺失**：DML 操作无审计记录 → 补充 AuditLog 记录
2. **dry_run 预览不生效**：清理函数不支持 dry_run 参数 → 添加 dry_run 分支
3. **级联预览未展示**：删除操作无级联影响预览 → 添加级联预览 API 调用

### 补充复盘：测试流程的不确定性与失败点

基于数据库维护模块测试复盘新增的不确定性：

| 不确定性 | 发生场景 | 应对策略 |
|---------|---------|---------|
| config.yaml API 路径与后端路由不一致 | 测试审计日志 API 返回 404 | 配置文件路径核对（复数/单数差异） |
| main.py 导入缺失导致服务启动失败 | NameError 崩溃，日志为空 | 启动前预检 `python -c "from app.main import app"` |
| SQLAlchemy Inspector 使用陷阱 | 表结构反射返回不完整 | run_sync 回调内先 .connection() 转换 |
| VACUUM 在事务内执行失败 | OperationalError | 改用 AUTOCOMMIT 隔离级别 |
| 敏感字段脱敏不完整 | 导出数据含明文密钥 | 静态+动态字段名匹配双重策略 |
| 后端服务意外停止 | 网络请求 ERR_CONNECTION_REFUSED | 检查服务进程 + 健康检查轮询 |

### 补充可抽象的固定流程

**新增固定流程**（适用于所有数据库维护模块测试）：

1. **数据库维护模块测试流程**：白名单验证 → 表浏览 → CRUD → 级联预览 → 导出脱敏 → 导入 → CONFIRM_DELETE 令牌验证
2. **系统清理模块测试流程**：dry_run 预览 → 实际清理 → VACUUM 验证 → 审计日志完整性检查
3. **服务启动预检流程**：config.yaml 路径核对 → main.py 导入完整性 → 健康检查轮询

**新增固定判断逻辑**：

- 数据库维护安全 = 白名单表数匹配 + 敏感字段脱敏 + CONFIRM_DELETE 令牌校验
- 系统清理安全 = dry_run 预览生效 + 审计日志完整
- 服务启动成功 = main.py 导入完整 + 健康检查 200
- SQLAlchemy Inspector 正确 = run_sync 回调内有 .connection() 转换
- VACUUM 正确执行 = AUTOCOMMIT 隔离级别

### 补充适用场景

新增适用场景：

- ✅ 数据库维护模块测试（表浏览/CRUD/级联/导出导入）
- ✅ 系统清理模块测试（dry_run 预览/VACUUM/过期清理）
- ✅ 危险操作双重确认测试（CONFIRM_DELETE 令牌）
- ✅ 敏感字段脱敏验证（导出数据安全检查）
- ✅ 审计日志完整性验证（DML 操作可追溯）

新增不适用场景：

- ❌ 分布式数据库测试（需专门的数据库测试工具）
- ❌ 数据库性能压测（需 JMeter/sysbench）
- ❌ 数据库迁移测试（需专门的迁移验证工具）

### 补充注意事项

41. **config.yaml 路径核对**：测试前必须核对 config.yaml 中的 API 端点路径与后端路由是否一致（注意单复数差异，如 `/audit-log` vs `/audit-logs`）
42. **main.py 导入预检**：服务启动前必须执行 `python -c "from app.main import app"` 预检，避免因导入缺失导致服务启动失败
43. **SQLAlchemy Inspector 验证**：测试表结构反射功能时，必须验证 run_sync 回调内是否先 .connection() 转换 Session 为 Connection
44. **VACUUM 执行验证**：测试 VACUUM 功能时，必须验证是否在 AUTOCOMMIT 隔离级别执行，禁止在事务内执行
45. **敏感字段脱敏验证**：测试导出功能时，必须检查 password_hash/token/secret/api_key 等字段是否脱敏为 ****
46. **CONFIRM_DELETE 令牌验证**：测试危险操作时，必须验证是否要求输入 CONFIRM_DELETE 令牌，且比较使用 hmac.compare_digest
47. **审计日志完整性**：测试 DML 操作后，必须查询审计日志 API 验证操作记录是否完整（action/table_name/record_id/operator/created_at）
48. **dry_run 预览优先**：测试清理操作时，必须先测试 dry_run 预览模式，确认预览结果正确后再测试实际清理

## 阶段 20-23：2026-07-18 SonarQube 迭代闭环复盘新增测试阶段

> 以下阶段来源于 2026-07-18 webapp-testing 12/12 PASS + SonarQube 扫描闭环复盘。所有参数通过 config.yaml 管理，禁止硬编码业务值。

### 阶段 20：服务模式自动检测

**为什么**：项目支持 dev 和 exe 两种运行模式，代码修改后行为差异显著（dev 即时生效，exe 需重新构建），测试前必须确认当前模式以避免"修改了代码但测试还是旧逻辑"的假阳性。

**流程**：
1. 读取 `service.start_script` 命令字符串
2. 按 `service_mode_detection.patterns` 关键词匹配模式：
   - 含 `python -m uvicorn` / `python app/main.py` / `python -m app.main` → dev 模式
   - 含 `.exe` 后缀 → exe 模式
   - 含 `docker run` / `docker compose` → docker 模式
3. 如检测到 exe 模式且代码有未构建的变更（git diff 含 `backend/app/**/*.py` 或 `admin-web/src/**/*.{vue,js,ts}`）：
   - 输出 WARN 提示需重新构建
   - 按 `service_mode_detection.rebuild_command` 给出重建命令
4. 记录当前模式到测试报告

**判断逻辑**：
- dev 模式 + 代码变更 → 测试可继续
- exe 模式 + 代码变更 → WARN 提示重建
- exe 模式 + 无代码变更 → 测试可继续

**配置项**（`config.yaml#service_mode_detection`）：
```yaml
service_mode_detection:
  enabled: true
  patterns:
    dev: ["python -m uvicorn", "python app/main.py", "python -m app.main"]
    exe: [".exe"]
    docker: ["docker run", "docker compose"]
  warn_on_unbuilt_changes: true
  unbuilt_change_patterns:
    - "backend/app/**/*.py"
    - "admin-web/src/**/*.{vue,js,ts}"
  rebuild_command: "构建打包.bat"
```

### 阶段 21：API 登录协议自动适配

**为什么**：本项目登录接口要求 `Content-Type: application/json`，而旧版测试脚本默认用 `application/x-www-form-urlencoded`，导致登录失败返回 422。测试前需按配置确认协议。

**流程**：
1. 读取 `credentials.admin.login_content_type`（form | json）
2. 按协议类型准备请求体：
   - form: `data={'username': '...', 'password': '...'}`
   - json: `data=json.dumps({...}), headers={'Content-Type': 'application/json'}`
3. 调用 Playwright `page.request.post(login_endpoint, ...)` 或 `Invoke-RestMethod`
4. 解析响应中的 token（按 `credentials.admin.token_path`）
5. 后续 API 测试在 Authorization 头注入 `Bearer <token>`

**PowerShell 注意**：
- form 模式可用 `Invoke-RestMethod -ContentType "application/x-www-form-urlencoded"`
- json 模式必须 `Invoke-RestMethod -ContentType "application/json" -Body $json`
- 禁止用 `curl.exe -d '{"k":"v"}'`（PowerShell 引号转义问题）

**配置项**（`config.yaml#credentials.admin`）：
```yaml
credentials:
  admin:
    login_content_type: "json"  # form | json
    login_endpoint: "/api/auth/login"
    username_selector: "input[placeholder*=用户]"
    password_selector: "input[type=password]"
    submit_selector: "button[type=submit]"
    token_path: "data.token"
```

### 阶段 22：路由路径预验证

**为什么**：测试脚本中硬编码的 API 路径（如 `/api/auth/login`）可能与后端实际路由前缀不一致，导致 404 假阳性。需启动时验证。

**流程**：
1. 读取 `route_verification.router_files` 列表
2. 对每个文件用 grep 提取 `APIRouter(prefix=...)` 声明
3. 构建 `{router_name: prefix}` 映射表
4. 与 `api_endpoints` 中声明的路径前缀对比
5. 不一致时 → FAIL 并列出差异

**判断逻辑**：
- 所有路径与实际路由前缀一致 → PASS
- 路径不一致 → FAIL 并报告差异详情
- 路由文件缺失 → WARN（跳过验证）

**配置项**（`config.yaml#route_verification`）：
```yaml
route_verification:
  enabled: true
  router_files:
    - "backend/app/routers/api/auth.py"
    - "backend/app/routers/admin/ads.py"
    - "backend/app/routers/internal/workflow.py"
  expected_prefixes:
    auth: "/api/auth"
    ads: "/api/admin/ads"
    workflow: "/api/internal"
  require_strict_match: true
  allow_suffix_only: false
```

### 阶段 23：SonarQube 二次扫描回归

**为什么**：测试通过不代表代码质量达标。需在测试后触发 SonarQube 扫描，验证修复未引入新问题，形成"测试→代码质量"闭环。本次迭代中首次扫描发现 23 个 OPEN 问题，修复后二次扫描又出现新问题（修复引入新缺陷），证明必须执行回归扫描。

**流程**（7 步 SQ-Loop 模式）：
1. 读取 `sonarqube_regression.scanner_command` 命令
2. 执行扫描命令（路径与 token 走环境变量 `SONAR_SCANNER_HOME`/`SONAR_TOKEN`）
3. 等待扫描完成：轮询 `tasks/search` API status=SUCCESS，超时 `max_wait_seconds`
4. 拉取 OPEN 问题列表：调用 `issues/search` API + `componentKeys=` 过滤
5. 与上次扫描的 OPEN 集合 diff，识别新增问题
6. 判断：
   - `new_issues > max_new_issues` → FAIL
   - OPEN 数量减少或持平 → PASS
   - 出现 BLOCKER/CRITICAL 新问题 → FAIL（即使总数减少）
7. 报告中展示前 10 个 OPEN 问题 + 全部新增问题

**判断逻辑**：
- 二次扫描 OPEN 数量减少 → 继续验证
- 二次扫描 OPEN 数量持平或增加 → 触发回滚检查（修复方式错误）
- 二次扫描出现新问题 → 修复引入新缺陷，需重新修复
- 超过 `max_regression_retries`（默认 3）→ 报告失败

**配置项**（`config.yaml#sonarqube_regression`）：
```yaml
sonarqube_regression:
  enabled: true
  scanner_command: "sonar-scanner -Dsonar.projectKey=20_News -Dsonar.sources=backend/app,admin-web/src"
  token_env_var: "SONAR_TOKEN"
  scanner_path_env_var: "SONAR_SCANNER_HOME"
  task_search_endpoint: "http://localhost:9000/api/ce/tasks?component=20_News"
  issues_search_endpoint: "http://localhost:9000/api/issues/search?componentKeys=20_News"
  max_new_issues: 0
  max_wait_seconds: 300
  severity_must_fix: ["BLOCKER", "CRITICAL"]
  severity_should_fix: ["MAJOR"]
  max_regression_retries: 3
```

## 报告模板新增区块

阶段 6 报告生成时，新增 4 个报告区块：
1. **服务模式检测结果**：显示当前模式 + 未构建变更警告
2. **API 登录协议**：显示使用的 Content-Type（form/json）
3. **路由路径验证**：显示路径一致性检查结果（通过数/失败数/差异详情）
4. **SonarQube 回归扫描**：显示 OPEN 问题数 + 新增问题数 + 严重级别分布 + 前 10 个问题列表

## 测试流程优化总结

新增 4 个阶段后，完整测试流程从 19 阶段扩展到 23 阶段，覆盖：
- 服务模式检测（阶段 20）
- API 登录协议适配（阶段 21）
- 路由路径预验证（阶段 22）
- SonarQube 二次扫描回归（阶段 23）

所有新增阶段均可通过 `enabled: false` 禁用，不影响原有流程。

## 补充章节：基于小程序播放与跨端数据流复盘的优化（v6，2026-07-20）

> 以下阶段来源于 2026-07-20 微信小程序「今日要闻」迭代修复完整复盘：覆盖播放卡顿、倍速不生效、URL 静默失败、布局不统一、缓存版本缺失等 11 类问题的测试经验。所有阈值通过 `config.yaml#miniprogram_playback_test`、`config.yaml#url_safety_test`、`config.yaml#cache_version_test` 配置管理。

### 阶段 24：小程序 URL 编码安全性预检

**配置节点**：`config.yaml#url_safety_test`

**触发条件**：`url_safety_test.enabled: true` 且扫描范围包含 `miniprogram/**/*.js`

```
1. 扫描所有小程序 .js 文件中的资源 URL 赋值：
   - audioManager.src =
   - <image src>（wxml）
   - wx.downloadFile({ url: ... })
   - <web-view src>
2. 对每个 URL 赋值点检查：
   a. URL 字面量含非 ASCII 字符（中文字符）→ FAIL：未编码
   b. URL 变量赋值前无 encodeURI() 包裹 → WARN：可能未编码
   c. 使用 encodeURIComponent() 编码 URL → FAIL：破坏 URL 结构
3. 检查后端返回的 URL 字段（如 audio_url、cover_url）是否在生成时已编码：
   - 调用后端 API 拉取一个 episode 对象
   - 检查 audio_url 是否含未编码的中文字符
4. 记录违规位置 + 修复建议
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| URL 字面量含中文未编码 | FAIL | 阻塞测试，要求修复后重测 |
| URL 变量赋值前无 encodeURI | WARN | 记录但不阻塞，建议修复 |
| 使用 encodeURIComponent 编码 URL | FAIL | 阻塞测试（会破坏 URL 结构） |
| 后端返回的 URL 含未编码中文 | WARN | 提示后端修复 |

**配置示例**：
```yaml
url_safety_test:
  enabled: true
  scan_dirs:
    - miniprogram/**/*.js
    - miniprogram/**/*.wxml
  url_assignment_patterns:
    - "audioManager\\.src\\s*="
    - "src\\s*=\\s*[\"']http"
    - "wx\\.downloadFile\\(.*?url:"
    - "web-view.*src"
  require_encode_function: "encodeURI"
  forbidden_encode_function: "encodeURIComponent"
  non_ascii_pattern: "[\\u4e00-\\u9fa5]"
  backend_url_fields_to_check:
    - audio_url
    - cover_url
    - source_url
```

### 阶段 25：高频回调节流与防重叠验证

**配置节点**：`config.yaml#miniprogram_playback_test.throttle_check`

**触发条件**：`miniprogram_playback_test.enabled: true` 且 `throttle_check.enabled: true`

```
1. 静态扫描小程序 onTimeUpdate 回调：
   - 检查回调内是否含时间戳节流逻辑（lastTimeUpdate 模式）
   - 检查回调内 setData 调用频率（通过代码静态分析估算）
2. 静态扫描异步上报函数（reportProgress、reportEvent、reportStats）：
   - 检查函数内是否含 if (progressReporting) return 防重叠判断
   - 检查函数内是否含 try/finally 清标志逻辑
3. 静态扫描 seek 操作：
   - 检查是否使用 pendingSeek 标志位模式（推荐）
   - 检查是否使用 onCanplay+offCanplay 自清理模式（已废弃）
4. 静态扫描高频 setter（playbackRate、volume）：
   - 检查是否含 lastApplied 缓存判断
5. 动态验证（如配置了真机调试）：
   - 播放音频 30 秒，监控 console 日志中 setData 调用频率
   - 实际触发节流间隔（默认 800ms）vs 配置阈值对比
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| onTimeUpdate 回调无时间戳节流 | WARN | 建议修复 |
| 异步上报无 in-progress 标志 | WARN | 建议修复 |
| seek 使用 onCanplay 自清理模式 | WARN | 建议改为 pendingSeek 模式 |
| 高频 setter 无 lastApplied 缓存 | INFO | 仅记录 |
| 动态验证 setData 频率 > 2 次/秒 | WARN | 建议加大节流间隔 |

**配置示例**：
```yaml
miniprogram_playback_test:
  enabled: true
  throttle_check:
    enabled: true
    update_interval_ms: 800
    max_setdata_per_sec: 2
    require_in_progress_flag: true
    require_pending_seek_pattern: true
    forbid_oncanplay_self_cleanup: true
    require_last_applied_cache: true
    cached_fields:
      - playbackRate
      - volume
  scan_dirs:
    - miniprogram/services/audio.js
    - miniprogram/pages/detail/detail.js
```

### 阶段 26：iOS/Android 双端播放兼容性验证

**配置节点**：`config.yaml#miniprogram_playback_test.cross_platform_check`

**触发条件**：`miniprogram_playback_test.enabled: true` 且 `cross_platform_check.enabled: true` 且配置了真机调试账号

```
1. 检查 setPlaybackRate 函数实现：
   - 是否包含 pause+play+seek 强制重新缓冲逻辑（iOS 必需）
   - 是否仅在 !audioManager.paused && currentTime > 0 时触发
2. 检查 resumePlay 函数导出：
   - services/audio.js 是否导出 resumePlay 函数
   - 浮动按钮/历史页 onTap 内是否调用 resumePlay 后再 navigateTo
3. 真机验证（如配置了 iOS + Android 设备）：
   a. iOS 设备：播放含中文 channel_slug 的音频，验证 onPlay/onCanplay 是否触发
   b. Android 设备：同上验证（应正常播放）
   c. iOS 设备：切换倍速，验证进度条/声音是否同步变化
   d. iOS 设备：跳转到详情页，验证是否自动播放（resumePlay 生效）
4. 检查列表页与详情页布局分离：
   - 列表页（pages/index/、pages/history/）禁止内嵌 <player-card> 组件
   - 列表项 onTapEpisode 内必须 wx.navigateTo 跳转
5. 检查频道切换状态清理：
   - initData(force=true) 时必须清空 script/segments/comments/bgCoverUrl
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| setPlaybackRate 无 pause+play+seek | FAIL | 阻塞测试（iOS 倍速不生效） |
| services/audio.js 未导出 resumePlay | FAIL | 阻塞测试（跳转后不播放） |
| 列表页内嵌播放卡片 | WARN | 建议重构为 navigateTo 跳转 |
| 频道切换未清关联状态 | WARN | 建议修复（数据串台） |
| iOS 真机含中文 URL 不触发 onPlay | FAIL | 阻塞测试（要求 encodeURI） |
| iOS 真机切换倍速不生效 | FAIL | 阻塞测试（要求 pause+play+seek） |

**配置示例**：
```yaml
miniprogram_playback_test:
  cross_platform_check:
    enabled: true
    ios_device_required: true
    android_device_required: false  # Android 可选（行为与配置一致）
    require_pause_play_seek_for_rate: true
    require_resume_play_export: true
    forbid_inline_player_card: true
    require_state_clear_on_channel_switch: true
    clear_fields_expected:
      - script
      - segments
      - comments
      - commentsTotal
      - bgCoverUrl
    test_episodes_with_chinese_slug: true
```

## 阶段 24-26 配置节点速查

| 阶段 | 配置节点 | 关键参数 |
|------|---------|----------|
| 24 URL 编码预检 | `url_safety_test` | `scan_dirs`、`url_assignment_patterns`、`require_encode_function`、`forbidden_encode_function`、`non_ascii_pattern`、`backend_url_fields_to_check` |
| 25 高频回调节流验证 | `miniprogram_playback_test.throttle_check` | `update_interval_ms`、`max_setdata_per_sec`、`require_in_progress_flag`、`require_pending_seek_pattern`、`forbid_oncanplay_self_cleanup`、`require_last_applied_cache`、`cached_fields` |
| 26 iOS/Android 双端兼容 | `miniprogram_playback_test.cross_platform_check` | `ios_device_required`、`android_device_required`、`require_pause_play_seek_for_rate`、`require_resume_play_export`、`forbid_inline_player_card`、`require_state_clear_on_channel_switch`、`clear_fields_expected`、`test_episodes_with_chinese_slug` |

## 阶段 24-26 复盘：测试流程的抽象与适用场景

### 维度 1：成功执行任务的完整步骤

本次小程序测试扩展在静态扫描 + 动态验证两个层面闭环，关键成功路径：

1. **静态扫描**：用 Grep 工具扫描小程序代码中的反模式（URL 未编码、回调未节流、上报无标志位等）
2. **配置驱动**：通过 `config.yaml#miniprogram_playback_test` 配置开启的检查项与阈值
3. **动态验证**（如配置真机）：实际播放音频触发回调，监控 console 日志验证行为
4. **跨端对比**：iOS + Android 真机验证行为差异（iOS 是 URL 编码、倍速切换差异的唯一可重现端）
5. **报告生成**：按严重级别分类输出，FAIL 阻塞测试，WARN 建议修复

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| URL 编码违规未检出 | 静态扫描仅检查字面量，未检查变量赋值 | iOS 静默失败未发现 | 扫描模式单一 | 增加变量赋值前的 encodeURI 检查（阶段 24） |
| 高频回调未节流未检出 | 静态扫描无法判断运行时频率 | UI 卡顿未发现 | 缺少动态验证 | 增加动态监控 setData 频率（阶段 25 步骤 5） |
| iOS 倍速不生效未检出 | 仅在 Android 测试 | iOS 用户反馈倍速失效 | 测试覆盖端不全 | 强制要求 iOS 真机验证（阶段 26） |
| 列表页内嵌播放卡片未检出 | 仅看渲染效果，未审 wxml 结构 | 布局不统一未发现 | 缺少结构性检查 | 增加 wxml 结构扫描（阶段 26 步骤 4） |
| 频道切换状态残留未检出 | 仅测试单频道场景 | 数据串台未发现 | 测试场景不全 | 增加多频道切换测试场景（阶段 26 步骤 5） |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 对应阶段 | 核心判断信号 | 落地配置节点 |
|------|----------|--------------|--------------|
| URL 编码安全性预检 | 阶段 24 | grep `audioManager\.src\s*=\s*[^e]` 在小程序代码中 | `url_safety_test` |
| 高频回调节流验证 | 阶段 25 | grep `onTimeUpdate.*=>.*setData` 无时间戳判断 | `miniprogram_playback_test.throttle_check` |
| iOS/Android 双端兼容 | 阶段 26 | grep `setPlaybackRate` 无 `pause\(\)` 调用 | `miniprogram_playback_test.cross_platform_check` |

### 维度 4：适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|------|---------|------------|
| URL 编码预检 | 小程序含中文资源路径；后端动态生成 URL | 纯 ASCII 路径；后端已编码 URL |
| 高频回调节流验证 | 小程序 audioManager；类似 onScroll/onTouchMove | 低频事件（onPlay/onPause）；Web 端 |
| iOS/Android 双端兼容 | 微信小程序音频/视频功能；跨端行为差异场景 | 纯 Web 端；服务端逻辑；无音频功能的小程序 |

## 测试流程优化总结（v6 更新）

新增 3 个阶段后，完整测试流程从 23 阶段扩展到 26 阶段，覆盖：
- URL 编码安全性预检（阶段 24）
- 高频回调节流与防重叠验证（阶段 25）
- iOS/Android 双端播放兼容性验证（阶段 26）

所有新增阶段均可通过 `enabled: false` 禁用，不影响原有流程。

