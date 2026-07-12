---
name: "news-auto-testing"
description: "前端自动化测试：使用 Playwright MCP + Chrome DevTools MCP 对 Web 应用做全面功能/性能/API 测试。当用户要求'测试前端/全面测试/系统测试/回归测试'或提到 'news-auto-testing / 前端测试' 时调用。"
---

# 前端自动化测试

使用 Playwright MCP + Chrome DevTools MCP 对 Web 应用进行全面测试，覆盖页面加载、登录流程、API 接口、性能审计四个维度，所有参数通过 `config.yaml` 管理。

## 配置文件

所有测试参数（URL、账号、页面清单、API 清单、性能阈值、修复策略）均通过配置文件管理：

- 模板：`config.example.yaml`
- 实际：`config.yaml`（从模板复制后按项目修改）

配置文件分为 15 个区块：

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
| `issue_classification` | 问题分类（代码缺陷/业务数据/框架行为/环境） |
| `fix_strategies` | 常见问题修复策略表 |
| `workflow` | 流程控制（自动启停、失败继续、自动修复、回归构建、菜单 fallback） |
| `report` | 报告输出配置 |
| `test_priority` | 测试用例优先级分类（P0-P3，控制执行顺序和报告分组） |

## 测试流程（6 阶段）

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
