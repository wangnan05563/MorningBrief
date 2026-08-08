# 测试阶段详解

> 本文档包含全部 101 个测试阶段的详细定义，从 SKILL.md 迁移而来。


## 核心阶段（1-6，默认执行）


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


## 辅助阶段（7+，按需激活）


### 阶段 37-42 判断逻辑速查

| 阶段 | PASS 条件 | WARN 条件 | FAIL 条件 |
|------|----------|----------|----------|
| 37 菜单分组 | 分组数量匹配 + 手风琴效果 + 角色可见性 + 路由自动展开 | group 字段硬编码 | 手风琴失效 / 角色控制失效 / meta.group 缺失 |
| 38 PWA 图标 | manifest + favicon + icon-192/512 全可访问 + Content-Type 正确 + HTML meta 完整 | manifest Content-Type 为 text/plain / 缺 maskable purpose / 缺 theme-color | manifest 不可访问 / icon-192/512 不可访问 / 缺 192/512 尺寸 |
| 39 图片封面 | segments 渲染 + lazy-load + 固定宽高比 + 失败降级 + CLS 阈值内 | 缺 lazy-load / CLS 超阈值 / 无固定宽高比 | 失败显示错误图标 / 未隐藏容器 |
| 40 About/Help | 元数据完整 + 检查更新成功 + 失败降级 + 锚点导航 + 章节高亮 + 搜索过滤 | 元数据缺字段 / 章节未高亮 / 搜索无结果 | 检查更新未降级 / 锚点无响应 / 搜索报错 |
| 41 监控告警 | 4 指标触发 WARNING 日志 + 格式完整 | 日志缺阈值/当前值 / 级别为 ERROR | 指标超阈值未触发 / 接口不可用 / 日志不可访问 |
| 42 健康度仪表盘 | 两端点 200 + 字段完整 + 健康度判定正确 + RSS 可用性判定正确 | 部分频道缺字段 / RSS availability 缺失 | 端点非 200 / 健康度判定错误 / 可用性判定错误 |

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

### 阶段 27：NOSONAR 注释位置正确性验证

**配置节点**：`config.yaml#nosonar_positioning_test`

**为什么**：本次 SonarQube 扫描修复中发现 18 处 NOSONAR 注释被错误加在多行函数定义的末行（`def func_name(\n  ...\n) -> ReturnType:  # NOSONAR`），导致 SonarQube 仍报告问题；正确位置应在首行 `def func_name(` 行尾。前端则需按文件类型匹配注释语法。本阶段通过静态扫描提前发现位置错误。

**触发条件**：`nosonar_positioning_test.enabled: true` 且扫描范围包含 Python 文件或前端文件

**流程**：
```
1. 扫描后端 Python 文件（scan_files.backend_patterns）：
   a. 对每个 .py 文件 grep 所有含 NOSONAR 的行
   b. 对每个 NOSONAR 行回溯判断所属语法结构：
      - 若属于多行函数定义（def ... -> 后跟冒号），检查 NOSONAR 是否在 def 行：
        - 在 def 行尾：PASS
        - 在返回类型行尾（-> ReturnType: 行）：FAIL（位置错误，SonarQube 不识别）
      - 若属于单行 def：PASS
      - 若属于其他行（if/for/with/赋值）：PASS（单行场景无歧义）
   c. 校验大小写敏感（require_case_sensitive）：必须为大写 NOSONAR
   d. 校验前导空格（require_leading_space）：# 前必须有至少一个空格
2. 扫描前端文件（scan_files.frontend_patterns），按文件类型匹配注释语法：
   - .js / .vue <script>：// NOSONAR 或 /* NOSONAR */
   - .vue <template>：<!-- NOSONAR -->
   - .wxml：<!-- NOSONAR -->
   - .wxss：/* NOSONAR */
   - 校验大小写和前导空格
3. 记录违规清单：文件路径 + 行号 + 当前位置 + 期望位置
4. 如违规数 > 0 且 severity_on_violation=FAIL：阻塞后续扫描
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| Python 多行 def 的 NOSONAR 在返回类型行 | FAIL | 阻塞扫描，要求移到 def 行 |
| 前端 .js 使用 HTML 注释 `<!-- NOSONAR -->` | FAIL | 阻塞扫描（语法错误） |
| 前端 .wxml 使用 JS 注释 `// NOSONAR` | FAIL | 阻塞扫描（语法错误） |
| NOSONAR 大小写错误（nosonar / NoSonar） | FAIL | 阻塞扫描（SonarQube 不识别） |
| # 前无空格（如 `pass# NOSONAR`） | WARN | 建议修复（部分场景不识别） |
| 单行 def 的 NOSONAR | PASS | 正常通过 |

**配置示例**：
```yaml
nosonar_positioning_test:
  enabled: true
  case_sensitive: true
  require_leading_space: true
  require_on_multiline_def_first_line: true
  scan_files:
    backend_patterns:
      - "backend/app/**/*.py"
    frontend_patterns:
      - "admin-web/src/**/*.vue"
      - "admin-web/src/**/*.js"
      - "miniprogram/**/*.js"
      - "miniprogram/**/*.wxml"
      - "miniprogram/**/*.wxss"
  valid_patterns:
    python_multiline_def: "\\bdef\\s+\\w+\\(.*#\\sNOSONAR\\s*$"
    python_single_line_def: "\\bdef\\s+\\w+\\(.*\\).*:\\s*#\\sNOSONAR\\s*$"
    js_line: "//\\s*NOSONAR\\s*$"
    js_block: "/\\*\\s*NOSONAR\\s*\\*/"
    vue_template: "<!--\\s*NOSONAR\\s*-->"
    wxss: "/\\*\\s*NOSONAR\\s*\\*/"
  invalid_patterns:
    - "\\)\\s*->\\s*.*:\\s*#\\sNOSONAR"
    - "//\\s*nosonar"
    - "//\\s*NoSonar"
  severity_on_violation: "FAIL"
```

### 阶段 28：SonarQube 扫描环境兼容性预检

**配置节点**：`config.yaml#sonarqube_environment_check`

**为什么**：本次扫描过程中遇到两类环境兼容问题：
1. Node.js v24 与 SonarJS bridge 不兼容（报 `Cannot find module './globals-IVYI6PB4.json'`），导致前端代码扫描失败
2. PowerShell 5 直接执行 `sonar-scanner -Dsonar.xxx=yyy` 时参数被错误解析，需用 .bat 文件封装
本阶段在正式扫描前预检环境兼容性，避免扫描中途失败浪费时间。

**触发条件**：`sonarqube_environment_check.enabled: true` 且即将执行 SonarQube 扫描

**流程**：
```
1. 检查 Node.js 版本（node_version_check）：
   a. 执行 `node --version` 获取当前版本
   b. 与 incompatible_versions 列表比对（如 v24.x.x）
   c. 如命中不兼容版本：
      - 检查 recommended_versions 中的版本是否可用（nvm list）
      - 输出切换命令（nvm use <version>）
      - 如无法切换：FAIL 阻塞扫描
2. 检查 PowerShell 版本（powershell_version_check）：
   a. 执行 `$PSVersionTable.PSVersion` 获取版本
   b. 如 PSVersion < 6（PowerShell 5.x），检查扫描命令是否使用了 -D 参数：
      - 如直接使用 -D sonar.xxx=yyy：FAIL（建议封装为 .bat 文件）
      - 如已封装为 .bat：PASS
3. 检查 SonarQube 服务可达性（server_reachability_check）：
   a. GET scanner_path_env_var 配置的 SonarQube URL
   b. 检查响应是否为 200
   c. 如不可达：FAIL（需先启动 SonarQube 服务）
4. 检查 SONAR_TOKEN 环境变量（token_check）：
   a. 读取 token_env_var 指定的环境变量
   b. 如为空或为占位符：FAIL（需配置真实 token）
5. 检查 scanner 路径（scanner_path_check）：
   a. 验证 SONAR_SCANNER_HOME 环境变量指向的目录存在
   b. 验证 bin/sonar-scanner 可执行
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| Node.js 版本在不兼容列表中（v24.x） | FAIL | 阻塞扫描，要求切换到 v20 LTS |
| PowerShell 5.x 直接使用 -D 参数 | FAIL | 阻塞扫描，要求封装为 .bat |
| SonarQube 服务不可达 | FAIL | 阻塞扫描，需启动服务 |
| SONAR_TOKEN 未配置或为占位符 | FAIL | 阻塞扫描，需配置真实 token |
| SONAR_SCANNER_HOME 路径不存在 | FAIL | 阻塞扫描，需重新安装 scanner |
| Node.js 版本为推荐版本（v20 LTS） | PASS | 正常通过 |

**配置示例**：
```yaml
sonarqube_environment_check:
  enabled: true
  node_version_check:
    enabled: true
    incompatible_versions:
      - "v24"
    recommended_versions:
      - "v20"
      - "v18"
    version_command: "node --version"
    fallback_strategy: "nvm use"
  powershell_version_check:
    enabled: true
    require_bat_wrapper_on_ps5: true
    ps_version_command: "$PSVersionTable.PSVersion.ToString()"
    ps5_threshold: "6.0"
  server_reachability_check:
    enabled: true
    server_url: "http://localhost:9000"
    expected_status: 200
  token_check:
    enabled: true
    token_env_var: "SONAR_TOKEN"
    forbidden_placeholder_values:
      - "your-sonar-token"
      - "<token>"
  scanner_path_check:
    enabled: true
    scanner_home_env_var: "SONAR_SCANNER_HOME"
    required_bin: "bin/sonar-scanner"
  severity_on_violation: "FAIL"
```

### 阶段 29：并行子代理修复结果二次核查

**配置节点**：`config.yaml#parallel_subagent_verification`

**为什么**：本次修复过程中使用了并行子代理（每个子代理负责一组文件），发现两类问题：
1. 子代理报告"已加 NOSONAR"但实际未加（遗漏）
2. 子代理把 NOSONAR 加在错误位置（多行函数定义末行）
本阶段对所有子代理修复结果进行二次 grep 验证，确保修复实际落地且位置正确。

**触发条件**：`parallel_subagent_verification.enabled: true` 且使用了并行子代理执行修复

**流程**：
```
1. 收集所有子代理的修复报告（subagent_reports）：
   a. 每个报告应包含：file_list（修复的文件列表）+ fix_summary（修复内容）
   b. 校验报告完整性（require_report_fields）
2. 对每个子代理报告执行核查：
   a. 文件存在性核查（verify_file_exists）：
      - 对 file_list 中每个文件，检查是否真实存在
      - 如不存在：FAIL（子代理虚构文件）
   b. NOSONAR 实际写入核查（verify_nosonar_written）：
      - 对 file_list 中每个文件，grep NOSONAR 关键字
      - 比对实际 NOSONAR 数量与报告声明的 fix_count
      - 如数量不符：FAIL（子代理声称修复但实际未写入）
   c. NOSONAR 位置正确性核查（verify_nosonar_position）：
      - 调用阶段 27 的 nosonar_positioning_test 逻辑
      - 对每个 NOSONAR 行验证位置是否正确
      - 如位置错误：FAIL（子代理修复位置错误）
   d. 文件组互斥核查（verify_file_group_exclusive）：
      - 检查不同子代理的 file_list 是否有交集
      - 如有交集：FAIL（子代理重复修复同一文件，可能覆盖）
3. 汇总核查结果：
   - 总文件数 / 实际修复数 / 位置正确数 / 遗漏数 / 位置错误数
4. 如有任一 FAIL：阻塞后续扫描，要求重新修复
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| 子代理报告 file_list 中的文件不存在 | FAIL | 阻塞扫描（子代理虚构修复） |
| 实际 NOSONAR 数量 < 报告声明的 fix_count | FAIL | 阻塞扫描（子代理遗漏修复） |
| NOSONAR 位置错误（多行 def 末行） | FAIL | 阻塞扫描（子代理位置错误） |
| 不同子代理 file_list 有交集 | FAIL | 阻塞扫描（文件组未互斥） |
| 所有文件存在 + 数量匹配 + 位置正确 + 互斥 | PASS | 正常通过 |

**配置示例**：
```yaml
parallel_subagent_verification:
  enabled: true
  require_report_fields:
    - "file_list"
    - "fix_summary"
    - "fix_count"
  verify_items:
    - "file_exists"
    - "nosonar_written"
    - "nosonar_position"
    - "file_group_exclusive"
  verify_nosonar_keyword: "NOSONAR"
  require_position_correct: true
  require_file_group_exclusive: true
  severity_on_violation: "FAIL"
```

### 阶段 30：测试失败 git stash 验证

**配置节点**：`config.yaml#test_failure_diagnosis`

**为什么**：本次扫描修复后运行测试，发现 4 个测试失败。初判为修复引入的回归，但实际是预先存在的测试与多频道实现不同步问题。如不区分回归 vs 预先存在问题，会导致误判修复方案错误。本阶段通过 `git stash` 验证失败是否为预先存在。

**触发条件**：`test_failure_diagnosis.enabled: true` 且测试失败数 > 0

**流程**：
```
1. 记录当前失败的测试用例列表（failed_tests_initial）
2. 执行 git stash（git stash push -u）保存当前所有变更
3. 在 stashed 状态下重新运行测试：
   a. 运行 failed_tests_initial 中的测试用例
   b. 记录结果（failed_tests_stashed）
4. 执行 git stash pop 恢复变更
5. 比对两次结果：
   a. failed_tests_initial == failed_tests_stashed：
      - 判定为预先存在问题（preexisting_failure）
      - 归类为 business_data 或 code_defect（历史欠账）
      - 不阻塞当前修复流程
   b. failed_tests_initial > failed_tests_stashed：
      - 判定为修复引入的回归（regression_introduced）
      - 必须修复回归后才能继续
   c. failed_tests_initial < failed_tests_stashed：
      - 异常情况（stash 恢复后测试状态变化）
      - WARN 提示需人工核查
6. 检查失败测试的 indicators_of_preexisting_failure 信号：
   - 测试用例引用了已删除的字段/方法
   - 测试用例 mock 了不存在的服务
   - 测试用例断言了旧版本的响应结构
   - 测试文件 last_modified 时间早于最近一次代码重构
   如命中任一信号，进一步佐证为预先存在问题
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| stash 前后失败用例一致（preexisting_failure） | WARN | 标注为历史欠账，不阻塞当前修复 |
| stash 后失败用例减少（regression_introduced） | FAIL | 阻塞流程，必须修复回归 |
| stash 后失败用例增多（异常状态） | WARN | 提示人工核查 |
| 命中 indicators_of_preexisting_failure 信号 | INFO | 进一步佐证为预先存在 |
| 无失败用例 | PASS | 正常通过 |

**配置示例**：
```yaml
test_failure_diagnosis:
  enabled: true
  stash_command: "git stash push -u"
  pop_command: "git stash pop"
  test_command: "pytest --asyncio-mode=auto"
  indicators_of_preexisting_failure:
    - "测试用例引用已删除的字段"
    - "测试用例 mock 了不存在的服务"
    - "测试用例断言旧版本响应结构"
    - "测试文件 last_modified 早于最近重构"
  classification:
    preexisting_failure: "business_data"
    regression_introduced: "code_defect"
  severity_on_regression: "FAIL"
  severity_on_preexisting: "WARN"
```

### 阶段 31：NOSONAR 抑制 vs 代码修复决策验证

**配置节点**：`config.yaml#nosonar_decision_matrix`

**为什么**：本次修复过程中发现部分规则适合用 NOSONAR 抑制（如 S3776 认知复杂度高但重构成本高、S125 注释掉的代码），部分规则必须修复（如 S5446 裸 except、S930 函数参数缺失、S2817 硬编码 SQL、S5886 Optional 缺失、S3699 从未执行的 Promise）。如不做决策验证，可能误用 NOSONAR 抑制真缺陷，导致代码质量风险。

**触发条件**：`nosonar_decision_matrix.enabled: true` 且扫描发现 NOSONAR 注释

**流程**：
```
1. 扫描所有 NOSONAR 注释（含规则标识，如 # NOSONAR S3776）
2. 对每个 NOSONAR 提取关联的规则 ID（rule_id）
3. 检查 rule_id 是否在 must_fix_rules 列表中：
   - 如在 must_fix_rules：FAIL（真缺陷禁止用 NOSONAR 抑制）
   - 输出建议：应修复代码而非抑制
4. 检查 rule_id 是否在 can_suppress_rules 列表中：
   - 如在 can_suppress_rules：检查是否包含原因注释（require_reason_comment）
   - 如 require_reason_comment=true 但无原因注释：WARN（建议补充原因）
   - 原因注释格式：# NOSONAR S3776: 认知复杂度高，重构成本超过收益
5. 检查 rule_id 是否在 unknown_rules 列表中（既不在 must_fix 也不在 can_suppress）：
   - 如在 unknown_rules：WARN（需人工决策）
6. 汇总决策验证结果：
   - must_fix 抑制数 / can_suppress 抑制数 / unknown 抑制数 / 缺原因注释数
7. 如有 must_fix 被抑制：FAIL 阻塞扫描
```

**判断逻辑**：

| 检查项 | 严重级别 | 失败动作 |
|--------|---------|---------|
| must_fix_rules 被 NOSONAR 抑制（如 S5446/S930/S2817） | FAIL | 阻塞扫描，要求修复代码 |
| can_suppress_rules 被抑制但无原因注释 | WARN | 建议补充原因注释 |
| unknown_rules 被抑制（需人工决策） | WARN | 提示人工评审 |
| can_suppress_rules 被抑制且含原因注释 | PASS | 正常通过 |
| NOSONAR 无关联规则 ID | WARN | 建议补充规则 ID |

**配置示例**：
```yaml
nosonar_decision_matrix:
  enabled: true
  require_reason_comment: true
  reason_comment_format: "# NOSONAR {rule_id}: {reason}"
  must_fix_rules:
    - "S5446"  # 裸 except，必须修复
    - "S930"   # 函数参数缺失，必须修复
    - "S2817"  # 硬编码 SQL，必须修复
    - "S5886"  # Optional 缺失，必须修复
    - "S3699"  # 从未执行的 Promise，必须修复
  can_suppress_rules:
    - "S3776"  # 认知复杂度高，重构成本高时可抑制
    - "S7503"  # 重复代码，重构成本高时可抑制
    - "S125"   # 注释掉的代码，可抑制（待清理）
    - "S6353"  # 字符串字面量重复，可抑制
  unknown_rules_action: "warn"  # warn | fail | manual
  severity_on_must_fix_suppressed: "FAIL"
  severity_on_missing_reason: "WARN"
```

### 阶段 32：跨项目模块迁移 7 步法验证

```
1. 读取 config.yaml#cross_project_migration_test 获取必经步骤清单
2. 验证 7 步是否全部执行：
   a. requirement_confirm：检查是否存在需求文档或对话记录
   b. architecture_align：检查 5 项对齐（目录结构/技术栈/依赖库/命名约定/路径风格）
   c. backend_dev：检查后端代码是否落地
   d. frontend_dev：检查前端代码是否落地
   e. test_write：检查测试用例是否编写
   f. test_execute：检查测试是否实际执行（非仅编写）
   g. build_verify：检查构建是否通过（前端 npm run build / 后端 pyinstaller）
3. 缺失任一步骤：标记 FAIL，输出缺失步骤名
4. 输出报告：7 步执行情况表（✅/❌）+ 缺失步骤详情
```

**判断信号**：

```bash
# 信号 1：缺少测试执行步骤（仅编写未执行）
grep -rn "test_write" .trae/skills/news-code-dev/ && \
  grep -rn "test_execute" .trae/skills/news-code-dev/

# 信号 2：缺少构建验证步骤
grep -rn "build_verify" .trae/skills/news-code-dev/
```

**配置节点**：`config.yaml#cross_project_migration_test`

---

### 阶段 33：前端嵌套目录相对路径校验

```
1. 读取 config.yaml#frontend_nested_paths_test 获取嵌套目录模式和扫描目录
2. 扫描 frontend_src_dirs 下所有 .vue/.ts/.js/.scss 文件
3. 对每个文件：
   a. 计算文件相对 frontend_src_dirs 的层级深度
   b. 若深度 >= parent_level_required（默认 2，即 views/<module>/<Page>.vue）
   c. 提取所有 @use 和 import 语句
   d. 验证相对路径层级是否正确：
      - views/about/About.vue 引用 styles/ 应为 '../../styles/'
      - 错误模式：'../styles/'（少一层）
4. 发现错误模式：标记 FAIL，输出文件路径和错误行
5. 如 build_verify_required=true，自动执行前端构建验证路径正确性
```

**判断信号**：

```bash
# 信号 1：views 子目录下使用 ../ 应为 ../../
grep -rn "@use\s\+'\.\./" frontend/src/views/*/

# 信号 2：import 路径层级错误
grep -rn "from\s\+'\.\./utils/" frontend/src/views/*/
```

**配置节点**：`config.yaml#frontend_nested_paths_test`

---

### 阶段 34：UI 图标跨库迁移存在性验证

```
1. 读取 config.yaml#icon_migration_test 获取目标图标库和验证命令
2. 执行 verify_command 获取目标图标库的所有图标名清单
3. 扫描 frontend_src_dirs 下所有 .vue/.ts/.js 文件
4. 提取所有 from 'target_icon_library' 的 import 语句中的图标名
5. 对每个图标名：
   a. 检查是否在目标图标库的图标清单中
   b. 不存在：查找 icon_mapping 是否有映射建议
   c. 输出修复建议：图标名 → fallback_icon 或映射后的图标名
6. 如 verify_before_build=true，构建前必须通过此验证
```

**判断信号**：

```bash
# 信号 1：从目标图标库 import 不存在的图标
grep -rn "from\s\+'@element-plus/icons-vue'" frontend/src/ | \
  grep -v "MagicStick\|Plus\|Search\|..."

# 信号 2：图标名在目标库中不存在
node -e "const icons = require('@element-plus/icons-vue'); console.log(Object.keys(icons))"
```

**配置节点**：`config.yaml#icon_migration_test`

---

### 阶段 35：模块级单例缓存测试隔离验证

```
1. 读取 config.yaml#cache_test_isolation_test 获取扫描范围和缓存类型清单
2. 扫描 backend_src_dirs 下所有 .py 文件
3. 对每个文件：
   a. 用 module_cache_patterns 正则匹配模块级缓存容器定义
   b. 如发现模块级缓存，检查同文件是否有 _reset_cache_for_test 函数
   c. 如有 _reset_cache_for_test，检查对应测试文件是否在 fixture 中调用
4. 缺失情况：
   a. 模块级缓存无 _reset_cache_for_test：FAIL
   b. _reset_cache_for_test 存在但测试未调用：WARN
   c. 测试调用了但未用 autouse=True：WARN
5. 输出报告：模块级缓存清单 + 重置函数存在性 + 测试调用情况
```

**判断信号**：

```bash
# 信号 1：模块级缓存容器定义
grep -rn "^_[a-z_]*_cache\s*[:=]\|^_[a-z_]*_dict\s*[:=]" backend/app/

# 信号 2：_reset_cache_for_test 未在测试中调用
grep -rn "_reset_cache_for_test" backend/tests/ | wc -l
```

**配置节点**：`config.yaml#cache_test_isolation_test`

---

### 阶段 36：多版本 Python 环境测试执行预检

```
1. 读取 config.yaml#python_env_test_check 获取系统 Python 路径和必需依赖清单
2. 预检步骤：
   a. 验证 system_python_path 路径存在
   b. 执行 verify_command 验证 pytest 已安装
   c. 检查 dev_requirements_file 是否存在且包含所有 required_test_deps
   d. 扫描测试脚本和 CI 配置，检测是否使用 forbidden_patterns（如 python -m pytest 无显式路径）
3. 失败处理：
   a. Python 路径不存在：FAIL，输出 system_python_path
   b. pytest 未安装：FAIL，输出安装命令
   c. 依赖缺失：WARN，输出缺失依赖清单
   d. 脚本使用 forbidden_patterns：WARN，输出建议的显式路径写法
4. 通过后：执行 test_run_command 运行测试
```

**判断信号**：

```bash
# 信号 1：测试脚本使用 python 而非显式路径
grep -rn "^python -m pytest" scripts/ .github/workflows/

# 信号 2：requirements-dev.txt 缺失
ls backend/requirements-dev.txt 2>/dev/null

# 信号 3：pytest 未安装
python -c "import pytest" 2>&1 | grep "No module named pytest"
```

**配置节点**：`config.yaml#python_env_test_check`

---

### 阶段 37：菜单分组与角色可见性测试

**配置节点**：`config.yaml#menu_grouping_test`

**为什么**：菜单数量 ≥10 时需用 el-sub-menu 分组避免扁平化难以查找；同时不同角色（admin/operator）可见分组需差异化控制。本次菜单分组功能开发中发现手风琴效果失效、角色过滤不生效等问题，本阶段通过 UI 验证 + 配置校验闭环。

**测试场景**：
- 菜单数量 ≥ `min_menu_count_for_grouping`（默认 10）时验证 el-sub-menu 分组结构
- 验证 `meta.group` 字段配置正确（每个路由都有 group 字段）
- 验证 `groupConfig` 数组从配置读取（非硬编码）
- 验证角色可见性控制（admin 可见所有分组，operator 仅可见部分）
- 验证 `unique-opened` 手风琴效果（同时只展开一个子菜单）
- 验证路由变化时自动展开当前分组

**测试步骤**：
```
1. 登录 admin 账号（credentials.admin），导航到主页面
2. 获取侧边栏快照，截图保存到 screenshot.save_dir/menu_admin.png
3. 验证菜单分组数量与 menu_grouping_test.expected_group_count 一致
4. 对每个分组执行：
   a. 点击分组标题，验证子菜单展开
   b. 再点击另一分组，验证前一分组自动收起（手风琴效果）
   c. 检查同时只有一个 el-sub-menu 处于展开状态
5. 静态扫描路由配置文件（route_config_files）：
   a. 提取所有路由的 meta.group 字段
   b. 验证 group 字段值都在 groupConfig 中定义
   c. 检查无硬编码 group 字符串（应从 groupConfig 读取）
6. 退出 admin，登录 operator 账号（credentials.operator）
7. 获取侧边栏快照，截图保存到 screenshot.save_dir/menu_operator.png
8. 验证 operator 可见分组数 ≤ admin 可见分组数
9. 验证 operator 不可见的分组不在 DOM 中或 display:none
10. 导航到具体页面（如 /review），验证所属分组自动展开
11. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 分组数量匹配 + 手风琴效果生效 + 角色可见性正确 + 路由变化自动展开 | PASS |
| groupConfig 从配置读取但 group 字段有硬编码 | WARN（代码整洁性） |
| 手风琴效果失效（多个分组同时展开） | FAIL（用户体验问题） |
| 角色可见性控制失效（operator 看到 admin 专属分组） | FAIL（权限漏洞） |
| meta.group 字段缺失或与 groupConfig 不匹配 | FAIL（配置不一致） |
| 菜单数量 < min_menu_count_for_grouping | SKIP（不需要分组） |

**配置示例**：见 `config.yaml#menu_grouping_test`

---

### 阶段 38：PWA 图标与 manifest 测试

**配置节点**：`config.yaml#pwa_icon_test`

**为什么**：PWA 安装到桌面依赖 manifest.json 和 icons 资源完整。本次图标设计任务中发现 manifest.json Content-Type 错误、icons 缺少 maskable purpose、index.html 缺少 theme-color meta 等问题，本阶段通过 HTTP 检查 + HTML 解析闭环。

**测试场景**：
- 验证 `/manifest.json` 可访问且 Content-Type 为 `application/manifest+json`
- 验证 manifest.json 含 `icons` 数组（192x192 和 512x512）
- 验证 icons 含 `"purpose": "any maskable"`（Android 自适应图标）
- 验证 `/favicon.ico` 可访问且 Content-Type 为 `image/x-icon`
- 验证 `/icon-192.png` 和 `/icon-512.png` 可访问
- 验证 index.html 含 `<link rel="manifest">` 和 `<meta name="theme-color">`

**测试步骤**：
```
1. GET {service.base_url}/manifest.json
   a. 验证状态码 == 200
   b. 验证响应头 Content-Type 包含 "application/manifest+json"
   c. 解析 JSON，验证包含 name/short_name/start_url/display 字段
2. 验证 manifest.json 的 icons 数组：
   a. 遍历 icons，检查 sizes 包含 "192x192" 和 "512x512"
   b. 检查每个 icon 的 purpose 字段，至少一个含 "maskable"
   c. 检查 src 路径不为空
3. GET {service.base_url}/favicon.ico
   a. 验证状态码 == 200
   b. 验证响应头 Content-Type 包含 "image/x-icon" 或 "image/vnd.microsoft.icon"
4. GET {service.base_url}/icon-192.png
   a. 验证状态码 == 200
   b. 验证响应头 Content-Type 包含 "image/png"
5. GET {service.base_url}/icon-512.png
   a. 验证状态码 == 200
   b. 验证响应头 Content-Type 包含 "image/png"
6. GET {service.base_url}/（首页 HTML）
   a. 抓取 HTML 内容
   b. grep `<link rel="manifest"` 存在
   c. grep `<meta name="theme-color"` 存在且 content 含 # 颜色值
   d. grep `<link rel="apple-touch-icon"` 存在（iOS 支持）
7. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| manifest.json + favicon.ico + icon-192/512.png 全部可访问 + Content-Type 正确 + HTML 含 manifest link 和 theme-color | PASS |
| manifest.json Content-Type 为 text/plain | WARN（部分浏览器仍可解析） |
| icons 数组缺少 maskable purpose | WARN（Android 自适应图标不支持） |
| manifest.json 不可访问（404） | FAIL（PWA 安装功能不可用） |
| favicon.ico 不可访问 | WARN（不影响 PWA，影响浏览器标签） |
| icon-192/512.png 不可访问 | FAIL（PWA 安装图标缺失） |
| index.html 缺少 theme-color meta | WARN（Android 状态栏颜色未配置） |
| icons 数组缺少 192x192 或 512x512 | FAIL（PWA 安装要求未满足） |

**配置示例**：见 `config.yaml#pwa_icon_test`

---

### 阶段 39：图片封面渲染与降级测试

**配置节点**：`config.yaml#cover_image_rendering_test`

**为什么**：图片爬虫功能开发后，小程序详情页按段渲染图文（segments 含 cover_url 时显示图片）。本次测试发现图片加载失败时显示错误图标影响用户体验、图片无 lazy-load 导致首屏加载慢、图片容器无固定宽高比导致 CLS 累积。本阶段通过 UI 验证 + 网络拦截 + 性能测量闭环。

**测试场景**：
- 小程序详情页按段渲染图文（segments 含 cover_url 时显示图片）
- 图片加载失败时自然降级（隐藏容器，不显示错误图标）
- 图片使用 lazy-load 模式
- 图片容器有固定宽高比（无 CLS）

**测试步骤**：
```
1. 导航到详情页（detail_page_path），获取页面快照
2. 验证 segments 渲染：
   a. 检查 segments 数量与预期一致
   b. 对含 cover_url 的 segment，验证 <image> 标签存在
   c. 验证 image 的 src 属性指向 cover_url
3. 静态扫描详情页 wxml 文件：
   a. grep <image> 标签，检查含 lazy-load 属性
   b. 检查 image 容器有固定宽高比（aspect-ratio 或 width/height 同时设置）
   c. 检查 image 标签含 binderror 事件绑定（用于降级处理）
4. 模拟图片加载失败（通过 Playwright 路由拦截）：
   a. 拦截 cover_url 的请求，返回 404
   b. 重新加载详情页
   c. 检查失败的 image 容器是否被隐藏（display:none 或 wx:if 移除）
   d. 检查不显示错误图标（broken-image class）
5. 测量图片加载前后的布局偏移（CLS）：
   a. 启动 Performance Trace
   b. 等待图片加载完成
   c. 读取 CLS 指标
   d. 验证 CLS ≤ cover_image_rendering_test.max_cls
6. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| segments 按段渲染 + lazy-load + 固定宽高比 + 加载失败降级 + CLS 在阈值内 | PASS |
| 缺少 lazy-load 属性 | WARN（首屏性能差） |
| 加载失败显示错误图标 | FAIL（用户体验差） |
| 加载失败未隐藏容器 | FAIL（显示 broken image） |
| CLS > max_cls | WARN（布局偏移大） |
| 图片容器无固定宽高比 | WARN（CLS 风险） |

**配置示例**：见 `config.yaml#cover_image_rendering_test`

---

### 阶段 40：About/Help 模块完整性测试

**配置节点**：`config.yaml#about_help_module_test`

**为什么**：About/Help 模块是用户获取系统信息和帮助文档的入口。本次 About/Help 模块开发中发现"检查更新"失败时未降级显示"本地"来源、Help 侧边栏锚点点击无响应、搜索过滤功能失效等问题。本阶段通过 UI 验证 + 接口测试闭环。

**测试场景**：
- About 页面展示：产品名、版本号、构建日期、Git SHA、Python 版本、平台
- About 页面"检查更新"功能可点击且返回结果
- 检查更新失败时降级显示"本地"来源
- Help 页面侧边栏锚点导航可点击
- Help 页面滚动时高亮当前章节
- Help 页面搜索过滤功能可用

**测试步骤**：
```
1. 导航到 About 页面（about_page_path）
2. 验证 About 页面元数据展示完整：
   a. 检查包含 expected_metadata 中的所有字段（产品名/版本号/构建日期/Git SHA/Python 版本/平台）
   b. 截图保存到 screenshot.save_dir/about.png
3. 点击"检查更新"按钮（check_update_button_selector）：
   a. 等待按钮恢复（按 async_interaction.response_timeout_ms）
   b. 验证返回结果含版本号或"已是最新"提示
4. 模拟"检查更新"失败（拦截 update_check_endpoint 返回 500）：
   a. 重新加载 About 页面
   b. 点击"检查更新"按钮
   c. 验证降级显示"本地"来源（fallback_source_text）
5. 导航到 Help 页面（help_page_path）
6. 验证侧边栏章节列表：
   a. 获取侧边栏快照
   b. 检查章节数量与 expected_section_count 一致
7. 点击侧边栏锚点：
   a. 点击任一章节锚点
   b. 验证页面滚动到对应章节（URL 含 #anchor 或 scrollPosition 变化）
8. 滚动页面，验证当前章节高亮：
   a. 慢速滚动到下一章节
   b. 验证侧边栏对应章节高亮（active class）
9. 在搜索框（help_search_selector）输入关键词（test_search_keyword）：
   a. 验证过滤结果数量 > 0
   b. 验证结果与关键词相关
   c. 清空搜索框，验证恢复全部章节
10. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 元数据完整 + 检查更新成功 + 失败降级 + 锚点导航 + 章节高亮 + 搜索过滤 | PASS |
| 元数据缺失部分字段（如 Git SHA） | WARN（构建信息不全） |
| 检查更新失败但未降级显示"本地" | FAIL（用户体验差） |
| 锚点点击无响应 | FAIL（导航功能失效） |
| 滚动时章节未高亮 | WARN（辅助功能缺失） |
| 搜索过滤无结果 | WARN（可能搜索索引未建立） |
| 搜索功能异常报错 | FAIL（功能缺陷） |

**配置示例**：见 `config.yaml#about_help_module_test`

---

### 阶段 41：关键指标监控告警测试

**配置节点**：`config.yaml#monitoring_thresholds_test`

**为什么**：P0 改进实施引入关键指标监控告警，要求关键词命中率 < 10%、LLM 字数达成率 < 80%、TTS 成功率 < 90%、工作流成功率 < 95% 时记录 WARNING 日志。本阶段通过触发不同场景 + 查询日志验证告警机制有效。

**测试场景**：
- 关键词命中率低于 `keyword_hit_rate_threshold`（默认 10%）时记录 WARNING 日志
- LLM 字数达成率低于 `llm_word_achievement_threshold`（默认 80%）时记录 WARNING 日志
- TTS 成功率低于 `tts_success_rate_threshold`（默认 90%）时记录 WARNING 日志
- 工作流成功率低于 `workflow_success_rate_threshold`（默认 95%）时记录 WARNING 日志

**测试步骤**：
```
1. 触发关键词命中率为 0 的工作流：
   a. 调用工作流触发接口（workflow_trigger_endpoint），传入不含任何关键词的内容
   b. 等待工作流执行完成（按 workflow_completion_timeout_sec）
   c. 查询日志文件（log_file_path）或日志接口（log_query_endpoint）
   d. grep WARNING + keyword_hit_rate 关键词
   e. 验证日志含命中率为 0 和阈值 threshold_value
2. 触发 LLM 调用（字数为目标 50%）：
   a. 调用 LLM 测试接口（llm_test_endpoint），传入 max_tokens=5
   b. 等待响应完成
   c. 查询日志，grep WARNING + llm_word_achievement
   d. 验证日志含字数达成率 < 80%
3. 触发 TTS 调用（模拟失败）：
   a. 通过 route 拦截 TTS 服务接口，返回 500
   b. 调用 TTS 测试接口（tts_test_endpoint）
   c. 等待响应完成
   d. 查询日志，grep WARNING + tts_success_rate
   e. 验证日志含 TTS 失败信息
4. 查询工作流历史，计算成功率：
   a. 调用工作流历史接口（workflow_history_endpoint），查询最近 N 条
   b. 计算成功率 = 成功数 / 总数
   c. 如成功率 < 95%，验证日志含 WARNING + workflow_success_rate
5. 验证日志格式：
   a. 每条 WARNING 日志含指标名 + 当前值 + 阈值 + 时间戳
   b. 日志级别为 WARNING（非 ERROR）
6. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 4 个指标触发条件都能产生 WARNING 日志 + 日志格式完整 | PASS |
| WARNING 日志缺阈值或当前值 | WARN（日志信息不全） |
| 指标超过阈值但未产生 WARNING 日志 | FAIL（监控失效） |
| 日志级别为 ERROR（应为 WARNING） | WARN（日志级别错误） |
| 工作流触发接口不可用 | FAIL（无法测试） |
| 日志文件/接口不可访问 | FAIL（无法验证告警） |

**配置示例**：见 `config.yaml#monitoring_thresholds_test`

---

### 阶段 42：频道素材健康度仪表盘测试

**配置节点**：`config.yaml#channel_health_dashboard_test`

**为什么**：P1 改进实施新增频道素材健康度仪表盘，需验证 /channel-health 和 /rss-health 端点返回完整数据、健康度三级判定符合阈值配置。本阶段通过 API 测试 + 数据完整性验证闭环。

**测试场景**：
- `/channel-health` 端点返回 200 和完整数据
- 健康度三级判定正确（healthy/warning/critical）
- 健康度数据包含：频道 ID、频道名、素材总数、近 7 天素材数、健康等级
- `/rss-health` 端点返回 200 和 RSS 源状态
- RSS 源状态包含：URL、HTTP 状态码、响应时间、可用性

**测试步骤**：
```
1. GET {service.base_url}{channel_health_endpoint}
   a. 验证状态码 == 200
   b. 验证响应 JSON 含 channels 数组
   c. 验证数组非空（如配置了 expected_channel_count，验证数量一致）
2. 对每个频道数据验证字段完整性：
   a. 检查包含 required_channel_fields 中的所有字段
     - channel_id
     - channel_name
     - material_count
     - recent_7d_count
     - health_level
3. 验证健康度三级判定：
   a. 对每个频道，根据 material_count 和 recent_7d_count 计算预期健康度
   b. 计算 rule：
      - recent_7d_count >= healthy_threshold.recent_7d_min 且 material_count >= healthy_threshold.material_min → healthy
      - recent_7d_count >= critical_threshold.recent_7d_min 或 material_count >= critical_threshold.material_min → warning
      - 否则 → critical
   c. 比对预期健康度与实际 health_level
4. GET {service.base_url}{rss_health_endpoint}
   a. 验证状态码 == 200
   b. 验证响应 JSON 含 sources 数组
5. 对每个 RSS 源数据验证字段完整性：
   a. 检查包含 required_rss_fields 中的所有字段
     - url
     - http_status
     - response_time_ms
     - availability
6. 验证 RSS 源可用性判定：
   a. http_status == 200 且 response_time_ms <= rss_response_time_threshold → availability 为 "available"
   b. http_status != 200 或 response_time_ms > rss_response_time_threshold → availability 为 "unavailable"
7. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 两个端点 200 + 字段完整 + 健康度判定正确 + RSS 可用性判定正确 | PASS |
| 部分频道缺字段（如 recent_7d_count） | WARN（数据不完整） |
| 健康度判定与阈值配置不符 | FAIL（判定逻辑错误） |
| /channel-health 返回非 200 | FAIL（端点不可用） |
| /rss-health 返回非 200 | FAIL（端点不可用） |
| RSS 源 availability 字段缺失 | WARN（数据不完整） |
| RSS 源可用性判定与实际不符 | FAIL（判定逻辑错误） |

**配置示例**：见 `config.yaml#channel_health_dashboard_test`

---

### 阶段 43：小程序 Page 方法名唯一性测试（对应 R101）

**配置区块**：`config.yaml#stage_43_page_method_uniqueness`

**测试目标**：验证小程序 Page 对象内方法名唯一，特别是生命周期方法（onLoad/onUnload/onShow）不与 bindload/binderror 等回调方法重名。

**测试步骤**：

1. 扫描 `miniprogram/pages/**/*.js` 所有 Page 文件
2. 解析 `Page({...})` 对象的所有键名
3. 检查是否出现同名键（如 onLoad 出现两次）
4. 检查生命周期方法（onLoad/onShow/onReady/onHide/onUnload）是否与 WXML 绑定的回调方法重名
5. 模拟器打开对应页面，验证生命周期是否被正确触发（非被覆盖）

**判断逻辑**：

| 判断 | 条件 | 严重级别 |
|------|------|---------|
| FAIL | Page 对象内同名键出现两次以上（如 `onLoad` 定义两次） | CRITICAL |
| FAIL | 生命周期方法名与 wxml `bindload`/`binderror` 回调方法重名 | CRITICAL |
| WARN | 生命周期方法名与自定义方法重名（但未被 wxml 绑定） | HIGH |
| PASS | 所有方法名唯一，生命周期未被覆盖 | - |

**配置参数**：

```yaml
stage_43_page_method_uniqueness:
  enabled: true
  scan_glob: "miniprogram/pages/**/*.js"
  lifecycle_methods:
    - onLoad
    - onShow
    - onReady
    - onHide
    - onUnload
    - onPullDownRefresh
    - onReachBottom
  wxml_callback_patterns:
    - bindload
    - binderror
    - bindtap
    - bindinput
  forbid_duplicate_keys: true
  forbid_lifecycle_collision: true
```

**适用场景**：所有小程序页面开发；wxml 含 bindload/binderror 等回调绑定的页面
**不适用场景**：Component 组件（用 lifetimes attached/detached，不会冲突）；纯 API 服务

---

### 阶段 44：小程序外链 ActionSheet 兜底测试（对应 R104）

**配置区块**：`config.yaml#stage_44_external_link_fallback`

**测试目标**：验证小程序点击外链跳转时，业务域名未配置场景下有 ActionSheet 兜底（复制链接 + 在小程序内打开），避免白屏。

**测试步骤**：

1. 扫描 `miniprogram/pages/**/*.js` 中所有 `wx.navigateTo.*webview` 调用
2. 检查调用前是否有 `wx.showActionSheet` 兜底逻辑
3. 在模拟器中点击节目来源链接，验证：
   - 业务域名未配置时弹出 ActionSheet（"复制链接" + "在小程序内打开"）
   - 选择"复制链接"后剪贴板含正确 URL
   - 选择"在小程序内打开"后跳转 webview 页面
4. 验证 `wx.navigateTo` 的 `fail` 回调是否回退到复制链接

**判断逻辑**：

| 判断 | 条件 | 严重级别 |
|------|------|---------|
| FAIL | `wx.navigateTo.*webview` 后无 `wx.showActionSheet` 兜底 | HIGH |
| FAIL | `wx.navigateTo` 无 `fail` 回调或 fail 回调未复制链接 | HIGH |
| WARN | ActionSheet itemList 缺少"复制链接"选项 | MEDIUM |
| PASS | 外链点击弹出 ActionSheet，复制链接成功 | - |

**配置参数**：

```yaml
stage_44_external_link_fallback:
  enabled: true
  scan_glob: "miniprogram/pages/**/*.js"
  nav_patterns:
    - "wx.navigateTo.*webview"
    - "wx.navigateTo.*url.*http"
  require_action_sheet: true
  require_fail_callback: true
  required_actions:
    - "复制链接"
    - "在小程序内打开"
  fallback_to_clipboard: true
  test_urls:
    - "https://example.com/article/1"
    - "https://example.com/article/中文路径"
```

**适用场景**：小程序含外链跳转（节目来源/关于我们/帮助文档等）；业务域名未配置或部分域名未配置
**不适用场景**：纯内部跳转（无外链）；已配置业务域名的项目（但仍建议保留兜底）

---

### 阶段 45：跨页布局一致性测试（对应 R108）

**配置区块**：`config.yaml#stage_45_cross_page_layout_consistency`

**测试目标**：验证列表页（首页/历史页）和详情页之间的布局风格一致，避免用户切换页面时视觉跳跃。

**测试步骤**：

1. 扫描 `miniprogram/pages/index/index.wxml` 和 `miniprogram/pages/history/history.wxml`
2. 提取两个页面使用的卡片类名（如 `.episode-row-card` / `.history-item`）
3. 检查类名是否一致（应使用同一套卡片类）
4. 在模拟器中分别打开首页和历史页，截图对比：
   - 卡片宽度一致
   - 卡片高度比例一致
   - 文字字号一致
   - 间距一致
5. 验证 `_enrichEpisode` 是否在两个页面同步补充 `date_label` / `duration_label` 等字段

**判断逻辑**：

| 判断 | 条件 | 严重级别 |
|------|------|---------|
| FAIL | 首页用 `.episode-row-card` 但历史页用 `.history-item` 不一致 | HIGH |
| FAIL | 两个页面 _enrichEpisode 补充的字段不一致（缺 date_label/duration_label） | HIGH |
| WARN | 卡片类名一致但样式参数有差异（如 padding 不同） | MEDIUM |
| PASS | 两个页面卡片类名一致，样式参数一致 | - |

**配置参数**：

```yaml
stage_45_cross_page_layout_consistency:
  enabled: true
  page_pairs:
    - source: "pages/index/index"
      target: "pages/history/history"
      shared_card_class: "episode-row-card"
    - source: "pages/index/index"
      target: "pages/detail/detail"
      shared_card_class: "episode-row-card"
  require_enrich_episode_sync: true
  required_fields:
    - date_label
    - duration_label
    - play_count
  screenshot_compare: true
  diff_threshold: 0.1
```

**适用场景**：所有列表-详情页场景；跨页面布局统一需求
**不适用场景**：单页面应用（无跨页跳转）；明确需要不同布局的页面（如全屏播放页）

---

### 阶段 46：聚合序号独立计数测试（对应 R106）

**配置区块**：`config.yaml#stage_46_aggregated_seq_independence`

**测试目标**：验证后端拼装列表数据（sources/chapters/timestamps）的序号从 1 重新编号，不复用外部 segment.seq。

**测试步骤**：

1. 调用 `GET /api/v1/episodes/{id}/script` 获取稿件
2. 检查 `sources` 数组的 `seq` 字段是否从 1 开始递增
3. 检查 `sources` 数组的 `seq` 是否与 `segments` 的 `seq` 重合（若重合说明复用了外部 seq）
4. 对比 `sources.length` 与最大 `seq` 值是否相等（若不等说明有跳号）
5. 在小程序详情页查看节目来源，验证序号从 1 开始

**判断逻辑**：

| 判断 | 条件 | 严重级别 |
|------|------|---------|
| FAIL | sources[0].seq != 1（从 2 或其他值开始） | HIGH |
| FAIL | sources 的 seq 与 segments 的 seq 重合 | HIGH |
| WARN | sources 长度与最大 seq 不等（跳号） | MEDIUM |
| PASS | sources 从 1 开始连续递增 | - |

**配置参数**：

```yaml
stage_46_aggregated_seq_independence:
  enabled: true
  api_endpoint: "/api/v1/episodes/{id}/script"
  aggregated_fields:
    - sources
    - chapters
    - timestamps
  require_start_from_one: true
  forbid_reuse_segment_seq: true
  require_continuous: true
  test_episode_ids:
    - 1
    - 2
    - 3
```

**适用场景**：所有返回聚合列表数据的 API（sources/chapters/timestamps）；多段新闻稿件
**不适用场景**：直接返回 ORM 模型列表（序号由前端生成）；无聚合需求的简单列表

---

### 阶段 47：TTS 多 Provider 单元测试

> 对应 news-code-dev 元规范 R109（多 Provider 抽象基类 + 工厂注册表）。
> 配置节点：`config.yaml#tts_multi_provider_unit_test`

对 `tts_multi_provider_unit_test.providers` 清单中每个 Provider 执行：

```
1. 检查 Provider 类是否继承抽象基类 TTSProvider
   - grep 'class.*Provider.*TTSProvider' backend/app/workflow/tts/
   - 缺失继承 → FAIL（违反 R109）
2. 检查 Provider 是否实现 synthesize 抽象方法
   - grep 'async def synthesize' backend/app/workflow/tts/<provider>_client.py
   - 缺失实现 → FAIL
3. 检查 Provider 是否实现 test_connection 方法
   - grep 'async def test_connection' backend/app/workflow/tts/<provider>_client.py
   - 缺失实现 → WARN（推荐但非强制）
4. 单元测试每个 Provider 的 synthesize 方法
   - mock 外部 API 响应，验证返回 bytes 类型
   - 测试空文本输入的处理（应返回空 bytes 或报明确错误）
   - 测试超长文本输入的处理（应截断或报明确错误）
5. 单元测试异常分类
   - TTSProviderError：Provider 内部错误（如凭证无效）
   - TTSRateLimitError：频率/预算超限
   - TTSTimeoutError：请求超时
   - TTSServiceError：服务端错误（5xx）
   - 验证异常类型与可重试性匹配（TTSProviderError 不可重试，其余可重试）
6. 检查 _PROVIDER_REGISTRY 注册表完整性
   - grep '_PROVIDER_REGISTRY' backend/app/workflow/tts/tts_factory.py
   - 验证所有已实现的 Provider 均已注册
   - 未注册的 Provider → FAIL
7. 记录结果
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| 所有 Provider 继承基类 + 实现接口 + 注册表完整 + 异常分类正确 | PASS |
| 缺少 test_connection 方法 | WARN |
| Provider 未继承基类 / 未实现接口 / 未注册 | FAIL |

### 阶段 48：降级链路验证测试

> 对应 news-code-dev 元规范 R110（自动降级链路设计）。
> 配置节点：`config.yaml#tts_fallback_chain_verification_test`

```
1. 检查 _parse_fallback_chain 函数存在
   - grep '_parse_fallback_chain' backend/app/workflow/tts/synthesizer.py
   - 缺失 → FAIL（违反 R110）
2. 检查降级链路配置驱动
   - grep 'TTS_FALLBACK_PROVIDERS' backend/app/config.py
   - 硬编码降级顺序 → FAIL
3. 模拟主 Provider 失败（mock raise TTSProviderError）
   - 验证自动降级到 fallback Provider
   - 验证降级成功 logger.warning 记录（含主 Provider 和降级 Provider 名称）
   - 无降级 → FAIL
4. 模拟所有 Provider 失败
   - 验证抛出 TTSError（含尝试顺序信息）
   - 错误信息不含尝试顺序 → WARN
5. 模拟主 Provider 成功
   - 验证不触发降级（无 logger.warning 降级日志）
   - 误触发降级 → FAIL
6. 验证降级循环内不重复 check_budget
   - grep 代码确认 check_budget 在降级循环外（synthesize_segment 顶部）
   - 循环内重复 check_budget → WARN（性能问题）
7. 记录结果
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| 降级链路配置驱动 + 主失败自动降级 + 所有失败抛终极异常 + 降级日志完整 | PASS |
| 降级循环内重复 check_budget / 错误信息缺尝试顺序 | WARN |
| 无降级链路 / 硬编码降级顺序 / 降级不触发 | FAIL |

### 阶段 49：edge-tts 版本预检测试

> 对应 news-code-dev 元规范 R112（第三方库版本兼容性预检）。
> 配置节点：`config.yaml#edge_tts_version_precheck_test`

```
1. 检查 edge-tts 库版本
   - 执行 pip show edge-tts（或读取 requirements.txt）
   - 版本 < edge_tts_version_precheck_test.min_version（默认 7.2.8）→ FAIL
   - 原因：6.1.9 的 TrustedClientToken 已被微软封禁，返回 403 Forbidden
2. 验证 save() API 可用
   - 执行 edge_tts.Communicate('测试', 'zh-CN-XiaoxiaoNeural').save('test_tts.mp3')
   - 403 Forbidden / WSServerHandshakeError → FAIL
   - 成功生成音频文件 → PASS
3. 验证 stream() API 可用
   - 执行 async for chunk in edge_tts.Communicate('测试', 'zh-CN-XiaoxiaoNeural').stream()
   - 403 Forbidden → FAIL
   - 成功返回音频流 → PASS
4. 检查 requirements.txt 版本锁定
   - grep 'edge-tts' backend/requirements.txt
   - 版本号与实际安装版本不一致 → WARN
   - 未锁定版本（无 ==） → WARN
5. Windows 环境额外检查
   - 检查 cacert.pem 文件是否被占用（多个 Python 进程）
   - 文件被占用 → WARN（升级时需 --no-deps）
6. 记录结果（含版本号和测试结果）
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| 版本 ≥ 7.2.8 + save() 可用 + stream() 可用 + requirements.txt 锁定 | PASS |
| requirements.txt 未锁定 / Windows cacert.pem 被占用 | WARN |
| 版本 < 7.2.8 / 403 Forbidden / WSServerHandshakeError | FAIL |

### 阶段 50：凭证 fallback 链测试

> 对应 news-code-dev 元规范 R111（凭证 fallback 链模式）。
> 配置节点：`config.yaml#credentials_fallback_chain_test`

```
1. 检查凭证 fallback 链实现
   - grep 'or settings.COS_SECRET_ID' backend/app/workflow/tts/tencent_client.py
   - 缺失通用配置 fallback → FAIL（违反 R111）
2. 测试显式参数优先
   - 传入 secret_id='explicit_id'，验证使用显式参数
   - 未使用显式参数 → FAIL
3. 测试专用配置 fallback
   - 不传显式参数，设置 TENCENT_TTS_SECRET_ID='tencent_id'
   - 验证使用专用配置
   - 未使用专用配置 → FAIL
4. 测试通用配置 fallback
   - 不传显式参数，TENCENT_TTS_SECRET_ID 为空，COS_SECRET_ID='cos_id'
   - 验证使用通用配置
   - 未使用通用配置 → FAIL
5. 测试所有凭证均空
   - 所有凭证均为空
   - 验证报明确错误（不能默认空字符串静默通过）
   - 静默通过 → FAIL
6. 检查 fallback 优先级文档
   - grep 'TENCENT_TTS_SECRET_ID' backend/.env.example
   - 缺少 fallback 优先级说明 → WARN
7. 记录结果
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| 三级 fallback 完整 + 显式参数优先 + 专用配置 fallback + 通用配置 fallback + 全空报错 | PASS |
| 缺少 fallback 优先级文档 | WARN |
| 无 fallback 链 / 全空静默通过 / 优先级错误 | FAIL |

### 阶段 51：前端 Provider UI 联调测试

> 对应 news-code-dev 元规范 R109/R110/R113/R115（多 Provider 架构/降级链路/音色映射/缓存热更新）。
> 配置节点：`config.yaml#tts_provider_ui_integration_test`

对 `tts_provider_ui_integration_test.pages` 清单中的页面执行：

```
1. 导航到 AI 配置页面（如 /ai-config）
2. 验证 Provider 切换控件存在
   - 快照中查找 el-radio-group 或 el-select 含 'aliyun'/'edge'/'tencent'
   - 缺失 → FAIL
3. 切换 Provider 验证表单联动
   - 点击不同的 Provider 选项
   - 重新获取快照，验证表单字段按 Provider 条件渲染
   - 切换到 aliyun：应显示阿里云专属字段（AppKey/Token/Voice）
   - 切换到 edge：应显示 Edge-TTS 专属字段（Voice/Rate/Volume）
   - 切换到 tencent：应显示腾讯云专属字段（VoiceType/Region/SampleRate）
   - 表单不联动 → FAIL
4. 验证音色下拉框按 Provider 动态渲染
   - 切换 Provider 后检查音色选项
   - 阿里云：XiaoxiaoNeural/YunxiNeural 等
   - Edge-TTS：zh-CN-XiaoxiaoNeural 等
   - 腾讯云：101011/101013 等
   - 音色列表不随 Provider 变化 → FAIL
5. 验证降级链路配置区块
   - 快照中查找 TTS_FALLBACK_PROVIDERS 输入框
   - 缺失 → FAIL
   - 输入框 placeholder 提示逗号分隔格式
   - 缺少提示 → WARN
6. 验证测试连接按钮
   - 点击测试连接按钮
   - 检查网络请求按当前 Provider 分发
   - 未按 Provider 分发 → FAIL
7. 验证图标导入完整性
   - 检查页面无图标未导入报错（如 Connection undefined）
   - 控制台 error 含 "is not defined" 且为图标名 → FAIL
8. 验证配置保存后反射回显
   - 修改配置并保存
   - 刷新页面，验证配置回填到表单
   - 不回填 → FAIL
9. 记录结果
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| Provider 切换控件 + 表单联动 + 音色动态渲染 + 降级配置 + 测试连接分发 + 图标完整 + 配置回显 | PASS |
| 降级配置缺 placeholder / 缺少 fallback 优先级文档 | WARN |
| 无 Provider 切换 / 表单不联动 / 音色不动态 / 无降级配置 / 测试连接不分发 / 图标报错 / 不回显 | FAIL |

---

### 阶段 52：TTS COS 降级本地存储测试（对应后端维度 113 + 前端维度 96）

如 `external_storage_fallback_test.enabled=true`，在阶段 51 之后执行：

**测试步骤**：
```
1. 模拟 COS 未配置场景
   - 清空 COS_SECRET_ID / COS_SECRET_KEY 配置
   - 重启后端服务使配置生效
   - 验证 is_cos_configured() 返回 false
2. 触发 TTS 工作流
   - 通过 API 或定时任务触发一个完整的 TTS 工作流
   - 等待工作流执行到 stitch 步骤
3. 验证音频文件落盘
   - 检查 data/audio_cache/ 目录是否有新生成的音频文件
   - 文件名格式：episodes/{yyyymmdd}/{channel_slug}_{workflow_id}.mp3
   - 文件不存在 → FAIL
4. 验证返回的 audio_url 格式
   - 调用 /api/episodes/today 接口
   - 检查 audio_url 字段以 /audio/ 开头（相对路径）
   - URL 为绝对路径（https://...） → FAIL（降级未生效）
5. 前端播放器加载验证
   - Playwright 打开小程序或 admin-web 播放页面
   - 加载该 audio_url
   - 播放器报错"无法加载资源" → FAIL
6. 验证管理后台降级提示
   - Playwright 打开配置页
   - 检查 el-alert[type=warning] 降级提示是否显示
   - 检查提示文案包含"本地存储"
   - 无降级提示 → FAIL
7. 记录结果
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| 文件落盘 + URL 为相对路径 + 前端可播放 + 降级提示显示 | PASS |
| 降级提示文案不规范 / 缺少切换指引 | WARN |
| 文件未落盘 / URL 为绝对路径 / 前端无法播放 / 无降级提示 | FAIL |

### 阶段 53：Windows asyncio 异常过滤测试（对应后端维度 114）

如 `asyncio_exception_filter_test.enabled=true` 且当前平台为 win32，在阶段 52 之后执行：

**测试步骤**：
```
1. 启动后端服务
   - 确认 main.py 已注册 loop.set_exception_handler
   - grep 'loop.set_exception_handler' backend/app/main.py
   - 未注册 → FAIL（前置条件不满足）
2. Playwright 打开音频播放页面
   - 导航到包含 audio 标签的页面
   - playwright_navigate 到播放页
   - 触发音频播放
3. 模拟浏览器提前关闭连接
   - 播放开始后 2 秒内 playwright_close 关闭页面
   - 或直接 playwright_close 关闭浏览器上下文
4. 检查后端日志
   - 读取后端最新日志（loguru 输出）
   - 搜索 'ConnectionResetError' 或 'WinError 10054'
   - 搜索 'ProactorBasePipeTransport'
5. 验证日志级别
   - 匹配到的日志行级别应为 DEBUG
   - 出现 ERROR 或 WARNING 级别 → FAIL
   - 出现完整 traceback 堆栈 → FAIL
6. 记录结果
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| 日志无 ERROR 级别 ConnectionResetError + 仅 DEBUG 记录 | PASS |
| 日志有 WARNING 级别（但无 ERROR） | WARN |
| 日志有 ERROR 级别 ConnectionResetError 堆栈 | FAIL |

### 阶段 54：本地路径 URL 约定测试（对应后端维度 115 + 前端维度 95）

如 `local_path_url_test.enabled=true`，在阶段 53 之后执行：

**测试步骤**：
```
1. 造数构造本地路径 URL
   - 确保存在 data/audio_cache/test_local_url.mp3 测试文件
   - 构造 URL: /audio/test_local_url.mp3
2. 调用 download_file 函数
   - 通过单元测试或 API 调用 download_file('/audio/test_local_url.mp3', dest)
   - 监控网络请求（确保无 httpx.get 发起）
3. 验证无 httpx 自回路请求
   - 检查网络请求日志
   - 出现 httpx.get('http://localhost*/audio/') → FAIL
   - 出现 httpx.get('http://127.0.0.1*/audio/') → FAIL
4. 验证文件拷贝
   - 检查目标位置 dest 是否存在文件
   - 文件不存在 → FAIL
5. 验证内容一致性
   - 比对源文件与目标文件的 MD5
   - MD5 不一致 → FAIL
6. 前端 URL 适配性验证
   - grep 'audio.*src.*http' admin-web/src/ 确认支持相对路径
   - grep 'new URL.*http' admin-web/src/ 确认未对相对路径调用 new URL()
   - 仅匹配绝对 URL → FAIL
7. 记录结果
```

**判断逻辑**：
| 条件 | 严重级别 |
|------|---------|
| 无 httpx 调用 + 文件拷贝成功 + 内容一致 + 前端支持相对路径 | PASS |
| 文件拷贝但未校验内容一致性 | WARN |
| 发起 httpx.get localhost 请求 / 文件未拷贝 / 内容不一致 / 前端仅匹配绝对 URL | FAIL |

### 阶段 64：el-switch 状态持久化测试

验证所有使用 el-switch 的页面在状态切换后刷新页面仍保持状态，且初始化时不误触发 change 事件。

**测试步骤**：

```
1. 读取 config.yaml#switch_persistence_test 获取测试配置
2. 对 switch_persistence_test.pages 中每个页面执行：
   a. 导航到页面
   b. 获取所有 el-switch 的当前状态（通过 snapshot 或 evaluate_script）
   c. 点击每个 el-switch 切换状态
   d. 验证 @change 回调被触发（通过网络请求或 UI 反馈）
   e. 验证切换后的状态与预期一致（active-value 对应值）
   f. 刷新页面（navigate_page 重新加载）
   g. 验证 el-switch 状态与刷新前一致（持久化验证）
   h. 验证初始化时未误触发 change 事件（检查网络请求无多余 PUT/POST）
3. 记录结果：PASS / FAIL / SKIP
```

**判断标准**：
- 切换后刷新，状态保持 → PASS
- 切换后刷新，状态恢复 → FAIL（持久化失败）
- 初始化时触发 change 事件 → FAIL（误触发禁用提示）
- @change 回调参数类型与 active-value 不一致 → FAIL（类型契约违反）

**配置参数**：`config.yaml#switch_persistence_test`

### 阶段 65：AI 长耗时接口超时测试

验证 AI 生成类接口在配置的超时时间内正常响应，无 timeout 报错。

**测试步骤**：

```
1. 读取 config.yaml#ai_timeout_test 获取测试配置
2. 对 ai_timeout_test.endpoints 中每个端点执行：
   a. 登录获取 token（如 requires_auth=true）
   b. 发送请求到 AI 生成接口
   c. 记录请求开始时间
   d. 等待响应（超时 = expected_max_response_sec * 1000 + buffer_ms）
   e. 验证响应状态码 == 200
   f. 验证响应包含预期字段（如 intro_prompt/outro_prompt）
   g. 记录实际响应时间
   h. 验证实际响应时间 ≤ expected_max_response_sec
   i. 验证前端无 timeout 报错（检查 console_messages 无 "timeout" 关键词）
3. 测试不同 LLM_TIMEOUT_SEC 配置下的行为（如适用）
4. 记录结果：PASS / FAIL / SKIP
```

**判断标准**：
- 响应时间 ≤ expected_max_response_sec → PASS
- 响应时间 > expected_max_response_sec → WARN（接近超时）
- 响应超时或 timeout 报错 → FAIL
- 响应缺失预期字段 → FAIL

**配置参数**：`config.yaml#ai_timeout_test`

### 阶段 66：频道级配置覆盖测试

验证频道级配置字段优先于全局配置，频道字段变更联动定时任务，频道字段为空时 fallback 到全局。

**测试步骤**：

```
1. 读取 config.yaml#channel_config_override_test 获取测试配置
2. 频道级配置优先测试：
   a. 创建测试频道，配置 intro_prompt/outro_prompt 等字段
   b. 触发该频道的工作流
   c. 验证工作流 rewrite 步骤使用频道级提示词（检查日志或 step output）
   d. 验证生成的稿件包含频道级提示词特征
3. 频道字段为空 fallback 测试：
   a. 创建测试频道，清空 intro_prompt 等字段
   b. 触发该频道的工作流
   c. 验证工作流 rewrite 步骤使用全局默认提示词
4. 频道变更联动定时任务测试：
   a. 修改频道的 schedule_time 为近期时间（如当前时间 +2 分钟）
   b. 等待 cron 任务触发（或验证日志中 cron 任务已重注册）
   c. 验证频道级 cron 任务按新 schedule_time 触发
   d. 清空 schedule_time，验证 cron 任务已移除
5. 频道禁用取消 queued 工作流测试：
   a. 创建测试频道并触发工作流（queued 状态）
   b. 禁用该频道（is_active=0）
   c. 验证 queued 工作流被取消（status=cancelled）
6. 记录结果：PASS / FAIL / SKIP
```

**判断标准**：
- 频道级配置优先于全局 → PASS
- 频道字段为空时 fallback 到全局 → PASS
- schedule_time 变更后 cron 任务重注册 → PASS
- 频道禁用后 queued 工作流被取消 → PASS
- 任一条件不满足 → FAIL

**配置参数**：`config.yaml#channel_config_override_test`

### 阶段 64-66 配置节点速查

| 阶段 | 配置节点 | 关键参数 |
|------|---------|----------|
| 64 el-switch 状态持久化 | `switch_persistence_test` | `pages`、`switches.active_value`、`switches.inactive_value`、`require_no_change_event_on_init`、`require_state_persist_after_refresh` |
| 65 AI 长耗时接口超时 | `ai_timeout_test` | `endpoints.path`、`endpoints.expected_max_response_sec`、`endpoints.expected_fields`、`buffer_ms`、`timeout_keyword` |
| 66 频道级配置覆盖 | `channel_config_override_test` | `channel_fields`、`test_steps`、`cron_wait_timeout_sec` |

---

### 阶段 67：Pydantic 字段持久化往返测试（对应 R144）

如 `pydantic_field_roundtrip_test.enabled=true`，在阶段 66 之后执行：

```
1. 读取 config_endpoints 获取测试的配置端点清单
2. 对每个配置端点：
   a. GET 当前配置，备份原始值（如 backup_before_test=true）
   b. 构造测试请求体，将 test_fields 中的字段替换为 test_value
   c. POST 提交测试配置
   d. GET 重新读取配置
   e. 对比 test_fields 中每个字段的 GET 返回值与 test_value
   f. 如值不一致，检查是否被 Pydantic extra='ignore' 静默丢弃
3. 如 restore_after_test=true，恢复原始配置
4. 记录结果：PASS（所有字段往返一致）/ FAIL（字段被静默丢弃或值不匹配）
```

**判断逻辑**：
- POST 返回 200 但 GET 返回值 != 提交值 → FAIL（静默丢弃）
- POST 返回 200 且 GET 返回值 == 提交值 → PASS
- POST 返回非 200 → FAIL（提交失败）

### 阶段 68：Element Plus 图标库可用性预检（对应 R145）

如 `icon_library_existence_test.enabled=true`，在阶段 67 之后执行：

```
1. 读取 icon_libraries 获取图标库配置清单
2. 对每个图标库：
   a. 扫描 scan_files 中所有文件
   b. 用 icon_extract_pattern 正则提取所有 icon 引用名
   c. 对每个图标名，执行 verify_command（替换 {icon_name} 占位符）
   d. 如命令退出码非 0，标记图标名不存在
3. 如 report_nonexistent_icons=true，生成不存在的图标清单
4. 如 suggest_alternative_icons=true，从 semantic_match_suggestions 查找替代建议
5. 记录结果：PASS（所有图标存在）/ FAIL（存在不存在的图标名）
```

**判断逻辑**：
- verify_command 退出码 0 → 图标存在 → PASS
- verify_command 退出码非 0 → 图标不存在 → FAIL
- 图标名在 known_nonexistent_icons 中 → 直接标记 FAIL

### 阶段 69：参数计算器跨页同步测试（对应 R146）

如 `cross_page_param_sync_test.enabled=true`，在阶段 68 之后执行：

```
1. 读取 cross_page_scenarios 获取跨页面参数传递场景清单
2. 对每个场景：
   a. 导航到 source_page.path
   b. 填写计算器参数（按 verify_synced_fields 中的字段）
   c. 点击 trigger_button 触发跳转
   d. 验证 URL 包含 expected_query_params 中的参数
   e. 等待 target_page 加载完成
   f. 验证 target_page 表单字段已同步（按 verify_synced_fields）
   g. 验证 URL 中 query 参数已被清除（router.replace）
   h. 验证页面显示 expected_feedback 视觉反馈
3. 记录结果：PASS（所有场景同步成功）/ FAIL（参数未传递或未同步）
```

**判断逻辑**：
- URL 包含 query 参数 + 表单字段已同步 + query 已清除 + 有视觉反馈 → PASS
- URL 不含 query 参数 → FAIL（router.push 未传参）
- 表单字段未同步 → FAIL（onMounted 未读取 query）
- query 未清除 → WARN（刷新可能重复应用）
- 无视觉反馈 → WARN（用户无感知）

### 阶段 70：配置键一致性测试（对应 R147）

如 `config_key_consistency_test.enabled=true`，在阶段 69 之后执行：

```
1. 读取 config_ends 获取四端配置来源清单
2. 对每端：
   a. 如有 scan_files，扫描文件并用 field_extract_pattern 提取字段名
   b. 如有 api_endpoint，发送 API 请求并从 response_key_path 提取键名
3. 对比四端字段集：
   a. 如 require_four_end_match=true，四端字段集必须完全一致
   b. 如 forbid_mixed_prefix=true，检查 prefix_style_check.forbidden_mixed_pairs
   c. 如 require_legacy_key_map_on_change=true，检查 LEGACY_KEY_MAP 兼容映射
4. 记录结果：PASS（四端一致）/ FAIL（字段集不一致或前缀混用）
```

**判断逻辑**：
- 四端字段集完全一致 + 无混用前缀 + 有 LEGACY_KEY_MAP → PASS
- 任一端字段集缺失 → FAIL（CRITICAL）
- 存在混用前缀 → FAIL（CRITICAL）
- 配置键变更无 LEGACY_KEY_MAP → WARN

### 阶段 67-70 配置节点速查

| 阶段 | 配置节点 | 关键参数 |
|------|---------|----------|
| 67 Pydantic 字段持久化往返 | `pydantic_field_roundtrip_test` | `config_endpoints`、`test_fields`、`backup_before_test`、`restore_after_test`、`roundtrip_assertions`、`silent_drop_signals` |
| 68 图标库可用性预检 | `icon_library_existence_test` | `icon_libraries`、`verify_command`、`scan_files`、`icon_extract_pattern`、`known_nonexistent_icons`、`semantic_match_suggestions` |
| 69 跨页参数同步 | `cross_page_param_sync_test` | `cross_page_scenarios`、`source_page`、`target_page`、`expected_query_params`、`verify_synced_fields`、`test_steps`、`failure_signals` |
| 70 配置键一致性 | `config_key_consistency_test` | `config_ends`、`field_extract_pattern`、`consistency_assertions`、`prefix_style_check`、`forbidden_mixed_pairs`、`failure_signals` |

### 阶段 67-70 复盘：测试流程的抽象与适用场景

### 阶段 71：响应拦截器 blob 响应兼容性测试

**配置节点**：`config.yaml#blob_interceptor_compat_test`

**场景描述**：验证 axios 响应拦截器对 blob/arraybuffer 响应类型的处理兼容性，避免二进制流响应被误按 `{code, message, data}` 解构、触发 `ElMessage.error` 误报。

**验证步骤**：
```
1. 读取 config.yaml#blob_interceptor_compat_test 获取测试配置
2. 构造 blob 响应测试用例：
   a. mock 后端返回 responseType='blob' 的响应，响应体为二进制数据（如 PDF/MP3 文件字节流）
   b. 通过前端 axios 实例发起请求，config.responseType 设置为 'blob'
   c. 等待响应拦截器链路完成
3. 验证拦截器分支选择：
   a. grep 拦截器源码，确认存在 response.config.responseType 分支判断
   b. 缺少分支判断 → FAIL（违反兼容性要求）
   c. 验证 blob 响应直接返回 response.data（Blob 对象），不进入 {code,message,data} 解构
   d. 解构尝试读取 .code 会抛异常 → FAIL
4. 验证 ElMessage.error 不误报：
   a. 监听前端 console.error 和 ElMessage 调用
   b. blob 响应路径下不应出现 error 调用
   c. 出现 "code undefined" 或 "message undefined" 错误 → FAIL（误按 JSON 解构）
5. 构造 json 响应对照测试：
   a. mock 后端返回 responseType='json' 的响应，响应体为 {code:0, message:'ok', data:{...}}
   b. 等待响应拦截器链路完成
   c. 验证正常解构流程不受影响
   d. 验证返回值为 response.data.data
   e. 解构失败或返回值不正确 → FAIL
6. 验证 arraybuffer 响应类型：
   a. 重复步骤 2-4，将 responseType 改为 'arraybuffer'
   b. 验证同样走直接返回分支，不误报
7. 记录结果：PASS / FAIL / SKIP
```

**预期结果**：
- blob/arraybuffer 响应直接返回，不走 `{code,message,data}` 解构
- JSON 响应正常解构，无误报
- 拦截器源码包含 responseType 分支判断

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| blob 直接返回 + JSON 正常解构 + 无 ElMessage 误报 + 拦截器含 responseType 分支 | PASS |
| arraybuffer 同样处理但未在分支列表中 | WARN（遗漏类型） |
| blob 响应触发 ElMessage.error 误报 / 拦截器无 responseType 分支 / JSON 解构失败 | FAIL |

### 阶段 72：工作流重跑前后状态验证

**配置节点**：`config.yaml#workflow_retry_state_test`

**场景描述**：验证工作流重跑（retry）操作在原工作流上执行，不创建新工作流，且前驱步骤保留、后续步骤删除、状态正确重置并入队。

**验证步骤**：
```
1. 读取 config.yaml#workflow_retry_state_test 获取测试配置
2. 准备工作流快照：
   a. 创建一个含多步骤的工作流（含 success/failed/queued 多种状态）
   b. 记录重跑前的步骤记录快照：list of {step_name, status, result}
   c. 记录工作流当前状态（如 failed/error，含 error 字段和 finished_at 字段）
3. 调用重跑接口：
   a. 调用 retry_workflow(workflow_id, from_step, triggered_by)
   b. 记录返回的 workflow_id
4. 验证不创建新工作流：
   a. 返回的 workflow_id 与传入的 workflow_id 相同
   b. 不相同 → FAIL（错误地创建了新工作流）
5. 验证步骤记录处理：
   a. 查询当前步骤记录
   b. 验证 from_step 及其之后的步骤记录被删除
   c. 未删除 → FAIL
   d. 验证 from_step 之前的步骤保留
   e. 验证保留的步骤 status=success，result 字段完整
   f. 保留步骤状态变化或 result 丢失 → FAIL
6. 验证工作流状态重置：
   a. 查询工作流当前状态
   b. 验证 status 重置为 queued（或配置的 initial_status）
   c. 验证 error 字段被清空（None）
   d. 验证 finished_at 字段被清空（None）
   e. 任一字段未重置 → FAIL
7. 验证工作流入队：
   a. mock PriorityQueue.put 方法
   b. 验证 retry_workflow 调用后 PriorityQueue.put 被调用一次
   c. 验证传入参数含正确的 workflow_id
   d. 未入队或入队参数错误 → FAIL
8. 记录结果：PASS / FAIL / SKIP
```

**预期结果**：
- 原工作流状态正确重置（status=queued, error=None, finished_at=None）
- 前驱步骤保留且 status=success、result 完整
- from_step 及之后步骤删除
- 工作流重新入队

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 不创建新工作流 + 前驱保留 + 后续删除 + 状态重置 + 入队调用 | PASS |
| error 字段保留历史错误 / finished_at 未清空 | WARN（字段清空不彻底） |
| 创建新工作流 / 前驱步骤丢失 / 后续步骤未删除 / 状态未重置 / 未入队 | FAIL |

### 阶段 73：时区敏感测试基线对齐

**配置节点**：`config.yaml#timezone_baseline_alignment_test`

**场景描述**：验证时间相关测试的时间基线与生产代码一致，避免因 `datetime.utcnow()` 与 `datetime.now()` 混用导致的时区差 flaky 失败。

**验证步骤**：
```
1. 读取 config.yaml#timezone_baseline_alignment_test 获取测试配置
2. 全文搜索测试文件中的时间调用：
   a. grep 'datetime\.utcnow\(\)' 在 test_*.py 文件中
   b. 每命中一处 → WARN（测试代码使用了 utcnow）
3. 确认生产代码时间函数：
   a. grep 生产代码中时间函数定义（如 utcnow_naive）
   b. 读取函数实现，确认返回本地时间（datetime.now()）或 UTC 时间
   c. 生产代码使用 utcnow_naive()（返回本地时间） → 测试基线必须用 datetime.now() 对齐
4. 对齐时间基线：
   a. 测试代码中的时间基线必须与生产代码一致
   b. 生产用 datetime.now() → 测试用 datetime.now()
   c. 生产用 utcnow_naive() → 测试用 datetime.now()（utcnow_naive 返回本地时间）
   d. 不一致 → FAIL（时区差 8 小时会导致 flaky）
5. 时间比较近似断言：
   a. grep 测试代码中的 == 时间比较
   b. 改用近似断言：abs(actual - expected) < epsilon（默认 epsilon=1.0 秒）
   c. 精确等于断言 → WARN（可能因微秒级差导致 flaky）
6. 稳定性验证：
   a. 连续运行测试 stability_run_count 次（默认 3 次）
   b. 全部通过 → PASS
   c. 出现偶发失败 → FAIL（仍存在 flaky 根因）
7. 记录结果：PASS / FAIL / SKIP
```

**预期结果**：
- 测试文件中不使用 `datetime.utcnow()`
- 测试时间基线与生产代码一致（均用 `datetime.now()` 或均用对齐的时间函数）
- 时间比较使用近似断言（abs diff < epsilon）
- 连续运行 3 次稳定通过

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 无 utcnow + 基线对齐 + 近似断言 + 连续 3 次稳定 | PASS |
| 测试代码含精确等于时间断言 | WARN（精度风险） |
| 测试用 utcnow / 基线不对齐 / 连续运行出现 flaky | FAIL |

### 阶段 74：外键关联删除验证

**配置节点**：`config.yaml#foreign_key_cascade_delete_test`

**场景描述**：验证删除父记录时子表外键正确处理（置 NULL 或级联删除），且行为在测试/生产环境一致（不依赖 PRAGMA foreign_keys 开关）。

**验证步骤**：
```
1. 读取 config.yaml#foreign_key_cascade_delete_test 获取测试配置
2. 创建测试数据：
   a. 创建父记录（如 channel/category/user）
   b. 创建关联的子记录，子表外键指向父记录
   c. 记录父记录 id 和子记录 id 列表
3. 验证 PRAGMA foreign_keys 默认未开启：
   a. 查询 SQLite PRAGMA foreign_keys
   b. 测试环境默认应为 0（未开启）
   c. 如已开启 → WARN（测试环境与生产环境不一致，需说明）
4. 调用删除父记录方法：
   a. 调用后端删除接口或 ORM delete 方法
   b. 等待删除完成
5. 验证子表外键处理：
   a. 查询子记录当前状态
   b. 按配置的 expected_cascade_action 验证：
      - 'set_null'：子记录外键字段被置为 NULL，子记录保留
      - 'cascade'：子记录同步被删除
      - 'restrict'：删除被阻止，抛 IntegrityError
   c. 实际行为与 expected_cascade_action 不符 → FAIL
6. 验证父记录已删除：
   a. 查询父记录
   b. 父记录不存在 → PASS
   c. 父记录仍存在 → FAIL
7. 验证不依赖 PRAGMA 开关：
   a. 关闭 PRAGMA foreign_keys（默认状态）
   b. 重复步骤 2-6，验证行为一致
   c. 行为依赖 PRAGMA 开关 → FAIL（测试/生产环境不一致风险）
8. 记录结果：PASS / FAIL / SKIP
```

**预期结果**：
- 删除父记录后子表外键按预期处理（NULL 或级联）
- 行为不依赖 PRAGMA foreign_keys 开关
- 测试环境与生产环境行为一致

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 外键处理符合 expected_cascade_action + 父记录已删除 + 不依赖 PRAGMA | PASS |
| 测试环境 PRAGMA 已开启（与生产可能不一致） | WARN（需说明配置差异） |
| 外键未处理 / 父记录未删除 / 行为依赖 PRAGMA 开关 | FAIL |

### 阶段 75：flaky 测试根因修复验证

**配置节点**：`config.yaml#flaky_root_cause_fix_test`

**场景描述**：验证偶发失败测试的根因已修复，通过稳定性验证确认 flaky 消除。

**验证步骤**：
```
1. 读取 config.yaml#flaky_root_cause_fix_test 获取测试配置
2. 识别 flaky 测试：
   a. 从历史测试报告中筛选偶发失败的测试用例
   b. 或从 known_flaky_tests 配置清单获取
   c. 无 flaky 测试 → SKIP（无需验证）
3. 分析失败原因：
   a. 按根因分类（root_cause_categories）：
      - 'timezone'：时区差（utcnow vs now）
      - 'concurrency'：并发竞态
      - 'random'：随机数未固定
      - 'time_precision'：时间精度（微秒差）
      - 'test_order'：测试执行顺序依赖
      - 'resource_leak'：资源泄漏（文件/连接未释放）
   b. 无法分类 → WARN（根因不明，需进一步分析）
4. 对齐时间基线或 mock 时间源：
   a. 时区类根因：按阶段 73 流程对齐时间基线
   b. 时间精度类根因：改用近似断言（epsilon 默认 1.0 秒）
   c. 随机类根因：用 random.seed() 固定随机种子
   d. 并发类根因：mock 并发原语或串行化执行
5. 用近似断言替代精确断言：
   a. grep 测试代码中的 == 时间比较
   b. 改为 abs(actual - expected) < epsilon
   c. epsilon 值通过 config.yaml#flaky_root_cause_fix_test.epsilon_seconds 配置
6. 稳定性验证：
   a. 连续运行 stability_run_count 次（默认 3 次）
   b. 全部通过 → PASS
   c. 出现偶发失败 → FAIL（根因未消除）
7. 确认修复不引入新的测试失败：
   a. 运行完整测试套件
   b. 对比修复前后测试结果
   c. 新增失败用例 → FAIL（修复引入回归）
8. 记录结果：PASS / FAIL / SKIP
```

**预期结果**：
- flaky 测试连续运行 3 次稳定通过
- 根因已消除（时区/并发/随机/精度）
- 修复不引入新的测试失败

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 根因已消除 + 连续 3 次稳定 + 无新失败 | PASS |
| 根因分类不明确 | WARN（需进一步分析） |
| 连续运行出现 flaky / 修复引入新失败 / 根因未消除 | FAIL |

### 阶段 76：三参数联动验证测试（对应 R157）

**配置节点**：`config.yaml#three_param_linkage_test`

**场景描述**：验证 TTS 语速/时长/字数三参数联动公式正确，调整任一参数时其他参数自动反算。

**验证步骤**：
```
1. 读取 config.yaml#three_param_linkage_test 获取测试配置
2. 验证联动公式：
   a. 设置目标时长 600s + 语速 1.0 → 验证反算字数 = 600 × 210 × 1.0 / 60 = 2100 字
   b. 设置目标时长 600s + 语速 1.5 → 验证反算字数 = 600 × 210 × 1.5 / 60 = 3150 字
   c. 设置目标时长 300s + 语速 1.5 → 验证反算字数 = 300 × 210 × 1.5 / 60 = 1575 字
3. 验证 Provider 语速解析：
   a. edge provider + EDGE_TTS_RATE="+50%" → 倍率 1.5
   b. tencent provider + TENCENT_TTS_SPEED=2 → 倍率 1.2
   c. aliyun provider → 倍率 1.0
4. 验证 clamp 范围：
   a. 语速倍率超出 [0.5, 2.5] 时被 clamp
   b. 目标时长超出 [180, 1800] 时被 clamp
5. 验证估算与实际产出偏差：
   a. 生成稿件后估算时长 vs 实际 TTS 时长，偏差应 < 15%
   b. 偏差超过 15% → WARN（记录偏差率供运维评估）
6. 记录结果：PASS / FAIL / SKIP
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 联动公式正确 + Provider 解析正确 + clamp 生效 + 偏差 < 15% | PASS |
| 估算与实际偏差 15%-25% | WARN |
| 联动公式错误 / Provider 解析错误 / clamp 未生效 / 偏差 > 25% | FAIL |

### 阶段 77：动态范围校验测试（对应 R158）

**配置节点**：`config.yaml#dynamic_range_validation_test`

**场景描述**：验证时长校验范围基于目标值动态计算，禁止硬编码固定范围。

**验证步骤**：
```
1. 读取 config.yaml#dynamic_range_validation_test 获取测试配置
2. 验证动态范围函数：
   a. 目标 600s → 范围 [max(180, 510), 690] = [510, 690]
   b. 目标 300s → 范围 [max(180, 255), 345] = [255, 345]
   c. 目标 180s → 范围 [max(180, 153), 207] = [180, 207]
3. 验证目标值 fallback：
   a. settings.TARGET_DURATION_SEC 为 None → fallback 到默认 600
   b. settings.TARGET_DURATION_SEC 为非数字 → fallback 到默认 600
4. 验证无硬编码范围：
   a. grep `MIN_DURATION_SEC = \d+` 应无结果
   b. grep `MAX_DURATION_SEC = \d+` 应无结果
   c. grep `_get_duration_range` 函数应存在
5. 边界测试：
   a. 时长 = 范围下限 → PASS（边界值通过）
   b. 时长 = 范围上限 → PASS（边界值通过）
   c. 时长 = 范围下限 - 1 → FAIL（触发 StitchError）
   d. 时长 = 范围上限 + 1 → FAIL（触发 StitchError）
6. 记录结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 动态范围正确 + 无硬编码 + fallback 生效 + 边界正确 | PASS |
| 存在硬编码范围常量 | FAIL |
| 动态范围计算错误 / fallback 缺失 | FAIL |

### 阶段 78：错误诊断信息完整性测试（对应 R159）

**配置节点**：`config.yaml#error_diagnostic_completeness_test`

**场景描述**：验证校验类异常信息包含目标值、实际值、允许范围、配置来源四要素。

**验证步骤**：
```
1. 读取 config.yaml#error_diagnostic_completeness_test 获取测试配置
2. 触发校验失败（如生成超范围时长的音频）：
   a. 制造一个时长 276s 的音频，目标 600s
   b. 触发 stitch 校验
   c. 捕获 StitchError 异常信息
3. 验证异常信息四要素：
   a. 包含实际值（如 "276s"）→ PASS
   b. 包含允许范围（如 "[510, 690]"）→ PASS
   c. 包含目标值（如 "目标时长 600s"）→ PASS
   d. 包含范围计算依据（如 "±15%"）→ PASS
4. grep 异常信息格式：
   a. grep `raise.*Error.*超出.*范围` 但无目标值 → FAIL
   b. grep `raise.*Error.*时长` 但无配置来源 → FAIL
5. 记录四要素完整性检查结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 四要素全部包含 | PASS |
| 缺少 1 个要素（如仅有实际值和范围） | WARN |
| 缺少 2 个及以上要素 | FAIL |

### 阶段 79：配置项全链路注册测试（对应 R156）

**配置节点**：`config.yaml#config_full_chain_test`

**场景描述**：验证新增配置项贯穿 config.py → ai_config_service 五端，缺任一端则配置"断链"。

**验证步骤**：
```
1. 读取 config.yaml#config_full_chain_test 获取测试配置
2. 扫描 config.py 中的配置字段列表
3. 对每个配置字段验证五端注册：
   a. config.py 有 X_FIELD 定义
   b. ai_config_service.py CONFIG_KEY_MAP 有 "x_field" → "X_FIELD" 映射
   c. INT_KEYS/FLOAT_KEYS 有 "x_field"（按类型）
   d. _normalize_llm 有 "x_field" 处理分支
   e. get_config_for_frontend 有 "x_field" 序列化输出
4. 端到端验证：
   a. 前端修改配置值 → 保存
   b. 后端读取配置值 → 验证与前端一致
   c. 重启服务后 → 验证配置值持久化
5. 记录断链字段列表
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有配置字段五端注册完整 + 端到端一致 | PASS |
| 个别字段缺少 1 端但功能正常 | WARN |
| 字段缺少 2 端及以上 / 端到端不一致 | FAIL |

### 阶段 80：前端 computed 命名安全测试（对应 R160）

**配置节点**：`config.yaml#frontend_computed_naming_test`

**场景描述**：验证 Vue 3 computed/ref/reactive 名称不与 Element Plus 组件内置 prop 冲突。

**验证步骤**：
```
1. 读取 config.yaml#frontend_computed_naming_test 获取冲突 prop 列表
2. 扫描 admin-web/src/ 下所有 .vue 文件
3. 对每个 .vue 文件：
   a. 提取所有 computed/ref/reactive 定义名称
   b. 提取模板中使用的 el-* 组件及其 prop
   c. 检查 computed 名称是否与同文件 el-* 组件 prop 同名
4. 检查已知冲突名称（duration/size/type/placeholder 等）
5. 记录冲突列表
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 无 computed 名称与 el-* prop 冲突 | PASS |
| computed 名称与已知冲突列表匹配但未与组件 prop 冲突 | WARN |
| computed 名称与同文件 el-* 组件 prop 同名 | FAIL |

### 阶段 81：双重验证流程测试（对应 R161）

**配置节点**：`config.yaml#dual_verification_workflow_test`

**场景描述**：验证代码修改后执行 py_compile（后端）和 vite build（前端）双重验证。

**验证步骤**：
```
1. 读取 config.yaml#dual_verification_workflow_test 获取验证命令配置
2. 后端验证：
   a. 收集所有修改的 .py 文件列表
   b. 对每个文件执行 python -m py_compile {file}
   c. 任一文件失败 → FAIL（报告失败文件和错误信息）
   d. 全部通过 → 进入前端验证
3. 常量去重检查：
   a. grep 修改文件中的常量定义（UPPER_SNAKE_CASE）
   b. 检查是否有重复定义（同一常量名出现多次）
   c. 发现重复 → FAIL（报告重复常量名和行号）
4. 前端验证：
   a. 在 admin-web 目录执行 npm run build
   b. 构建失败 → FAIL（报告构建错误）
   c. 构建成功 → 验证新增路由 chunk 生成
5. 记录验证结果（含每步耗时）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| py_compile 全部通过 + 无重复常量 + vite build 成功 | PASS |
| py_compile 通过但存在重复常量 | WARN |
| py_compile 失败 / vite build 失败 | FAIL |

### 阶段 82：SQLite 时区一致性测试（对应 R162 / R170）

**配置节点**：`config.yaml#timezone_consistency_test`

**场景描述**：验证 ORM 模型时间字段不使用 `func.now()` 作为 default（SQLite `func.now()` 返回 UTC 时间，与项目本地时间查询不一致），且时间字段写入时显式赋值项目统一时区源函数。

**验证步骤**：
```
1. 读取 config.yaml#timezone_consistency_test 获取：
   - forbidden_default_patterns（禁止的 default 模式列表，如 func.now()、datetime.utcnow）
   - required_import_source（项目统一时区源函数路径，如 app.core.timeutil.utcnow_naive）
   - scan_glob（扫描的文件 glob，如 backend/app/models/*.py）
   - excluded_models（白名单模型列表，如 AuditLog）
2. 扫描 scan_glob 下所有 .py 文件
3. 对每个文件：
   a. 提取所有 mapped_column 定义中的 default 参数
   b. 检查 default 是否匹配 forbidden_default_patterns
   c. 若匹配 → 记录违规（文件路径 + 行号 + 字段名 + 违规模式）
4. 反向校验：检查时间字段写入处是否显式赋值 required_import_source
   a. grep `\.add\(` 调用，提取被添加对象的字段
   b. 若时间字段未显式赋值且无 default → WARN（依赖数据库默认值，跨日查询风险）
5. 白名单跳过：excluded_models 中的模型不参与检查
6. 输出报告（含违规清单 + 反向校验结果）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 无 mapped_column 使用 forbidden_default_patterns + 时间字段显式赋值 | PASS |
| mapped_column 使用 forbidden_default_patterns 但模型在白名单 | SKIP |
| 时间字段未显式赋值但无 default（依赖 DB 默认值） | WARN |
| mapped_column 使用 forbidden_default_patterns 且不在白名单 | FAIL |

### 阶段 83：dedup 残留清理验证测试（对应 R163）

**配置节点**：`config.yaml#dedup_cleanup_test`

**场景描述**：验证业务表清空时去重表（如 crawler_dedup）联动清理，且去重表具备 TTL 自动清理机制，避免出现「业务表为空但去重表残留 N 条」导致后续抓取全部被误判为重复的状态。

**验证步骤**：
```
1. 读取 config.yaml#dedup_cleanup_test 获取：
   - business_tables（业务表清单，如 [material, episode]）
   - dedup_tables（去重表清单，如 [crawler_dedup]）
   - cleanup_link_map（业务表 → 去重表映射，如 {material: crawler_dedup}）
   - ttl_required（是否要求 TTL 自动清理，true/false）
   - threshold_ratio（残留比阈值，如 0.1，即 dedup 记录数不得超过 business 记录数 × 10%）
   - scan_glob（清理脚本扫描路径，如 backend/app/workflow/**/cleanup*.py）
2. 静态扫描：
   a. grep `DELETE FROM {business_table}` 或 `db.execute(delete({Model}))` 在 scan_glob 下
   b. 对每个清理点检查同文件/同函数内是否有对应的 `DELETE FROM {dedup_table}` 联动清理
   c. 无联动清理 → 记录违规
3. TTL 机制验证（ttl_required=true 时）：
   a. grep dedup_tables 中的表名在 models/*.py 中的定义
   b. 检查是否有 TTL 字段（如 created_at + 索引）或清理 cron
   c. 无 TTL 机制 → WARN
4. 动态验证（可选，需数据库连接）：
   a. 查询 dedup_tables 中各表的记录数
   b. 查询对应 business_tables 的记录数
   c. 若 dedup_table 记录数 > business_table 记录数 × threshold_ratio → WARN（残留超标）
5. 输出报告（含静态违规清单 + TTL 缺失警告 + 动态残留统计）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 业务表清理点均有联动 dedup 清理 + TTL 机制存在 + 动态残留比 < threshold_ratio | PASS |
| 业务表清理点均有联动但无 TTL 机制 | WARN |
| 业务表清理点缺联动清理 | FAIL |
| 动态残留比 ≥ threshold_ratio（如 dedup 347 条 vs material 0 条） | FAIL |

### 阶段 84：rewrite fallback 触发条件测试（对应 R164）

**配置节点**：`config.yaml#rewrite_fallback_test`

**场景描述**：验证按日期筛选的业务查询返回 0 条时，必须尝试回溯最近 N 天查询；回溯仍 0 条才允许 raise。避免「当日无 pending 素材」直接报错阻塞工作流，应自动回溯历史素材。

**验证步骤**：
```
1. 读取 config.yaml#rewrite_fallback_test 获取：
   - query_patterns（需校验的查询模式，如 [pending 素材查询、当日 episode 查询]）
   - fallback_days（回溯天数，如 3）
   - fallback_query_required（是否要求回溯查询，true/false）
   - scan_glob（扫描路径，如 backend/app/workflow/llm/*.py）
   - excluded_functions（白名单函数列表，如 _get_immediate_items）
2. 静态扫描：
   a. grep query_patterns 在 scan_glob 下
   b. 对每个查询点检查后续 30 行内是否有回溯查询逻辑（如 for days in range(1, fallback_days+1) 或 date_offset += timedelta）
   c. 检查 raise 前是否有回溯尝试
   d. 无回溯且 raise → 记录违规
3. fallback_days 一致性校验：
   a. grep `FALLBACK_DAYS` 或 `fallback_days` 在代码中的引用
   b. 检查是否硬编码（如直接写 `for days in range(1, 4)` 而非读取配置）
   c. 硬编码 → WARN（应通过配置管理）
4. 边界验证：
   a. 模拟当日查询返回 0 条的场景
   b. 验证是否触发回溯查询最近 fallback_days 天
   c. 验证回溯仍 0 条时是否 raise（而非静默返回 None）
5. 输出报告（含静态违规清单 + 硬编码警告 + 边界验证结果）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 所有查询点均有回溯逻辑 + fallback_days 从配置读取 + 边界验证通过 | PASS |
| 有回溯逻辑但 fallback_days 硬编码 | WARN |
| 查询点无回溯且直接 raise | FAIL |
| 回溯后 0 条未 raise（静默返回 None） | FAIL |

### 阶段 85：PowerShell + Python 工具链兼容性测试（对应 R165）

**配置节点**：`config.yaml#powershell_python_compat_test`

**场景描述**：验证 PowerShell 调用 Python 时禁用 r-string（`python -c "...r'd:\...'"` 中 r 前缀会被 PowerShell 吞掉，导致路径转义失败），必须使用脚本文件方式或双反斜杠转义。

**验证步骤**：
```
1. 读取 config.yaml#powershell_python_compat_test 获取：
   - forbidden_patterns（禁止的模式，如 [python -c.*r['\"]、python -c.*r\\]）
   - scan_glob（扫描路径，如 [**/*.ps1, **/*.bat]）
   - recommended_approach（推荐方式，如 script_file 或 double_backslash）
   - excluded_files（白名单文件列表）
2. 静态扫描：
   a. 扫描 scan_glob 下所有文件
   b. grep forbidden_patterns
   c. 对每个匹配点记录（文件路径 + 行号 + 违规模式 + 上下文）
3. 替代方案验证：
   a. 若使用 python -c，检查是否使用 recommended_approach
   b. 推荐脚本文件方式：grep `python\s+\S+\.py` 在同文件内是否有替代调用
   c. 推荐双反斜杠方式：grep `\\\\` 在 python -c 字符串内
4. 跨平台兼容性验证（可选）：
   a. 在 Windows PowerShell 执行违规命令
   b. 验证输出是否丢失 r 前缀（路径解析失败）
   c. 在 Linux bash 执行同样命令验证差异
5. 输出报告（含违规清单 + 替代方案覆盖率 + 跨平台差异验证）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 无 forbidden_patterns 匹配 + 所有 python 调用使用脚本文件方式 | PASS |
| 使用 python -c 但采用双反斜杠转义（非 r-string） | PASS |
| 使用 python -c 且匹配 forbidden_patterns | FAIL |
| 跨平台验证发现 PowerShell 丢失 r 前缀 | FAIL |

### 阶段 86：SQLite 数据库锁重试验证测试（对应 R167）

**配置节点**：`config.yaml#sqlite_lock_retry_test`

**场景描述**：验证 SQLite `database is locked` 异常处理包含重试逻辑（WAL 模式 + busy_timeout + 指数退避重试），禁止直接报错退出。SQLite 单机部署并发写入场景下，长事务持锁会导致后续写入全部失败。

**验证步骤**：
```
1. 读取 config.yaml#sqlite_lock_retry_test 获取：
   - lock_error_patterns（锁错误模式，如 [database is locked、SQLITE_BUSY、SQLITE_LOCKED]）
   - required_retry_count（要求的最小重试次数，如 3）
   - required_backoff_strategy（退避策略，如 exponential 或 fixed）
   - required_busy_timeout_ms（busy_timeout 最小值，如 5000）
   - wal_mode_required（是否要求 WAL 模式，true/false）
   - scan_glob（扫描路径，如 backend/app/**/*.py）
2. 静态扫描：
   a. grep lock_error_patterns 在 scan_glob 下
   b. 对每个匹配点检查 except 块内是否有重试逻辑（如 for attempt in range 或 while retry_count <）
   c. 检查重试次数是否 ≥ required_retry_count
   d. 检查退避策略是否匹配 required_backoff_strategy
   e. 无重试逻辑 → 记录违规
3. WAL 模式 + busy_timeout 配置验证（wal_mode_required=true 时）：
   a. grep `PRAGMA journal_mode` 在数据库初始化代码中
   b. 验证值为 WAL
   c. grep `PRAGMA busy_timeout` 验证值 ≥ required_busy_timeout_ms
   d. 缺失或值不符 → WARN
4. 动态验证（可选，需数据库连接）：
   a. 模拟并发写入场景（多线程/多进程同时写入）
   b. 验证是否触发锁错误
   c. 验证重试逻辑是否生效（最终写入成功）
   d. 验证重试日志是否记录（attempt N/total）
5. 输出报告（含静态违规清单 + WAL/busy_timeout 配置警告 + 动态验证结果）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 锁错误处理含重试逻辑 + 重试次数 ≥ 阈值 + 退避策略匹配 + WAL + busy_timeout 配置正确 | PASS |
| 有重试逻辑但 WAL/busy_timeout 配置缺失 | WARN |
| 锁错误处理无重试逻辑（直接 raise/exit） | FAIL |
| 重试次数 < required_retry_count | WARN |
| 退避策略不匹配（如 fixed 而非 exponential） | WARN |

### 阶段 87：小程序原生代码 4 维静态验证测试（对应 R174）

**配置节点**：`config.yaml#miniprogram_static_check`

**场景描述**：小程序原生代码（miniprogram/）无法用 Playwright 直接测试，需通过语法/接口/契约/渲染 4 维静态验证覆盖。修改 miniprogram/ 下任一 .js/.wxml/.wxss/.json 文件后必须执行本阶段。

**验证步骤**：
```
1. 读取 config.yaml#miniprogram_static_check 获取 4 维配置
2. 收集本次修改的 miniprogram/ 文件列表（git diff）
3. 语法维（syntax）：
   a. 对每个修改的 .js 文件执行 node --check {file}
   b. 任一文件语法错误 → FAIL（报告错误文件和行号）
   c. 全部通过 → 进入接口维
4. 接口维（interface）：
   a. 提取修改文件中所有 require() 调用
   b. 验证 require 路径存在（文件存在性）
   c. 验证导出函数名与调用方一致（grep module.exports vs 调用点）
   d. 验证参数个数与签名一致
   e. 验证返回值结构与使用方一致
   f. 任一不一致 → FAIL
5. 契约维（contract）：
   a. 提取修改文件中所有 API 调用（wx.request / 服务封装）
   b. 对照后端路由定义（backend/app/routers/）验证：
      - 请求字段名 vs 后端 Pydantic Model 字段名
      - 响应字段名 vs 前端使用字段名
      - snake_case / camelCase 一致性
   c. 不一致 → WARN（契约问题不阻塞但需修复）
6. 渲染维（render）：
   a. 对每个修改的 .wxml 文件提取 {{field}} 绑定
   b. 验证 field 在对应 .js 的 data 或 setData 中存在
   c. 验证 wx:for 绑定的数组名在 data 中存在
   d. 验证 bindtap/bindload 等绑定的函数名在 Page/Component methods 中存在
   e. 不一致 → WARN
7. 输出 dimension_table 格式报告（dimension/status/issues/file/line）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 4 维全部通过 | PASS |
| 语法维或接口维失败 | FAIL（阻塞性） |
| 契约维或渲染维失败 | WARN（非阻塞性） |
| 修改了小程序代码但跳过 4 维验证 | FAIL（severity_on_skip=FAIL） |

**跳过检测**：grep `node --check` 在 git commit message 或 PR description 中无记录 → 判定为跳过。

### 阶段 88：前后端字段契约验证清单测试（对应 R175）

**配置节点**：`config.yaml#field_contract_check`

**场景描述**：规范 R16 定义了"前后端字段契约"原则，本阶段补充可操作的验证清单。任何涉及前后端交互的 API 变更（后端路由/Schema 修改 或 前端 api.js 修改）后必须执行本阶段。

**验证步骤**：
```
1. 读取 config.yaml#field_contract_check 获取验证清单
2. 检测 API 变更：
   a. 后端变更：git diff 匹配 backend/app/routers/**/*.py 或 backend/app/schemas/**/*.py
   b. 前端变更：git diff 匹配 admin-web/src/api/**/*.js 或 miniprogram/services/*.js
   c. 无变更 → 跳过本阶段（PASS with skip reason）
3. 请求字段对齐（request_fields）：
   a. 提取前端 api.js 中请求 payload 字段名
   b. 对照后端 Pydantic Schema 字段定义
   c. 字段名不一致（snake_case vs camelCase）→ FAIL
   d. 前端发送后端未定义的字段 → FAIL
   e. 后端必填字段前端未发送 → FAIL
4. 响应字段对齐（response_fields）：
   a. 提取后端路由返回 dict 的字段名
   b. 对照前端 res.xxx 取值
   c. 前端使用了后端未返回的字段名 → FAIL
   d. 字段名大小写/下划线不一致 → FAIL
5. 兜底链数据源验证（fallback_chain）：
   a. 提取前端代码中的 || 兜底链（如 avatar_url || avatar || avatarUrl）
   b. 对链中每个字段名，验证至少一个数据源（后端响应/前端 data/globalData）返回
   c. 链中存在任何数据源都不返回的字段名 → WARN（冗余字段需清理）
6. 已知字段对核对（known_field_pairs）：
   a. 遍历 config.yaml#field_contract_check.known_field_pairs
   b. 前端使用了 frontend_wrong 字段 → 按 severity 报告
   c. allow_fallback=true 的字段验证 fallback 链完整性
7. 输出 contract_matrix 格式报告（api_endpoint/field_name/backend_definition/frontend_usage/status/severity/suggestion）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 请求/响应字段全部对齐 + 兜底链完整 + 无 known_field_pairs 违规 | PASS |
| 兜底链有冗余字段 | WARN |
| 请求/响应字段不对齐 / 使用了 known_field_pairs 中的 frontend_wrong | FAIL |

**与 news-frontend-code-review 联动**：本阶段配置 `cross_reference_config: "news-frontend-code-review/config.yaml#field_contract_frontend"`，与前端代码审查的 `field_contract_frontend.known_field_pairs` 保持字段对一致，形成「开发 → 审查 → 测试」闭环。

### 阶段 89：多页面共享状态 onShow 同步测试（对应规范 66）

**测试目标**：验证跨页面共享的状态（用户偏好、筛选条件、登录态）在 onShow 时从权威源重新读取，而非仅依赖 data 镜像或单信号时间戳。

**信号 1**：onShow 中涉及 isPreferredMode/currentChannelId 但无 localData./getApp().globalData. 调用
**信号 2**：onShow 中仅用时间戳判断状态变更，无内容比对

**测试步骤**：
1. 设置偏爱频道 → 切换到其他 Tab → 切回 → 验证 UI 显示正确的过滤后数据
2. 清空偏爱频道 → 切换到其他 Tab → 切回 → 验证显示空状态引导提示
3. 在设置页修改偏爱 → 返回原页面 → 验证立即刷新

**判断标准**：
- PASS：切 Tab 后 UI 数据与权威源一致
- FAIL：切 Tab 后残留旧数据或显示空状态

### 阶段 90：过滤模式防御性二次过滤测试（对应规范 67）

**测试目标**：验证列表渲染层按当前过滤条件对数据二次校验，即使上游承诺已过滤。

**信号 1**：_applyXxxData 函数中无 .filter() 调用
**信号 2**：偏爱模式下传入全量数据，UI 仍显示全部频道

**测试步骤**：
1. 设置偏爱频道 A、B → 触发 onLoad 预渲染（globalData 残留全量）→ 验证 UI 只显示 A、B
2. 清空偏爱 → 传入全量数据 → 验证 UI 显示空状态

**判断标准**：
- PASS：偏爱模式下无论上游返回什么，UI 只显示偏爱频道
- FAIL：偏爱模式下显示全部频道

### 阶段 91：空状态显式标记测试（对应规范 68）

**测试目标**：验证数据加载函数在所有分支显式设置 xxxEmpty 标志。

**信号 1**：loadXxx 函数中无 Empty 标志设置
**信号 2**：切 Tab 后空状态残留（false→true 未触发）

**测试步骤**：
1. 未设置偏爱 → 进入页面 → 验证显示空状态引导
2. 切换到其他 Tab → 切回 → 验证仍显示空状态引导（非残留数据）
3. 设置偏爱 → 进入页面 → 验证显示过滤后数据（非空状态）

**判断标准**：
- PASS：每次加载后空状态标志与实际数据一致
- FAIL：切 Tab 后空状态标志残留导致显示错误

### 阶段 92：时间戳+内容双校验变更检测测试（对应规范 69）

**测试目标**：验证跨页面状态变更检测采用"时间戳 OR 内容"双校验。

**信号 1**：onShow 中仅用 _lastPreferredTs !== xxxChanged 判断
**信号 2**：普通 Tab 切换（不更新时间戳）后不刷新

**测试步骤**：
1. 修改偏爱 → 返回原页面 → 验证时间戳变化触发刷新
2. 不修改偏爱 → 切 Tab → 切回 → 验证内容比对触发刷新（即使时间戳未变）

**判断标准**：
- PASS：Tab 切换和数据修改都能触发刷新
- FAIL：仅时间戳变化触发刷新，Tab 切换漏刷新

### 阶段 93：异步窗口本地存储直接读取测试（对应规范 70）

**测试目标**：验证数据加载函数入口直接从 localData 读取，不依赖 this.data 镜像。

**信号 1**：loadXxx 函数入口读取 this.data.preferredIds
**信号 2**：onShow 中 setData 后立即调用 loadXxx，loadXxx 读到旧值

**测试步骤**：
1. 修改偏爱 → onShow 中 setData → 立即调用 loadXxx → 验证 loadXxx 读到最新值
2. 清空偏爱 → onShow 中 setData（preferredIds=[]）→ 立即调用 loadXxx → 验证 loadXxx 正确判断为空

**判断标准**：
- PASS：loadXxx 始终从 localData 读取最新值
- FAIL：loadXxx 读 this.data 拿到旧值导致误判

### 阶段 94：globalData 与 data 镜像同步测试（对应规范 71）

**测试目标**：验证清空/更新 data 镜像时同步清空/更新 globalData。

**信号 1**：setData({ todayList: [] }) 后无 globalData.todayList = []
**信号 2**：切回页面 onLoad 从 globalData 读到残留数据

**测试步骤**：
1. 清空偏爱 → loadPreferred 清空 data.todayList → 验证 globalData.todayList 也被清空
2. 切到其他页面 → 切回 → 验证 onLoad 不从 globalData 读到残留

**判断标准**：
- PASS：data 和 globalData 始终同步
- FAIL：globalData 残留导致切回页面显示旧数据

### 阶段 95：页面生命周期刷新策略测试（对应规范 72）

**测试目标**：验证 onShow 同步状态后强制重新加载当前模式数据。

**信号 1**：onShow 中 setData 同步 preferredIds 但无 loadXxx 调用
**信号 2**：切 Tab 后状态同步但 UI 仍显示旧数据

**测试步骤**：
1. 修改偏爱 → 返回原页面 → 验证 onShow 调用 loadPreferred/loadHistory
2. 切 Tab → 切回 → 验证 onShow 在偏爱模式下调用 loadXxx

**判断标准**：
- PASS：onShow 同步状态后立即触发数据重载
- FAIL：仅同步状态不重载，UI 显示旧数据


## 2026-08-05 新增：打包模式/路由顺序/测试环境专项（阶段 96-98）

> 来源：打包模式空列表缺陷全量测试复盘。配置节点见 `config.yaml` 对应字段，技能本身不硬编码任何路径/版本。

### 阶段 96：Playwright 输出目录沙箱安全删除绕过

**测试目标**：避免 Playwright 在部分沙箱中启动时尝试安全删除固定 `test-results` 目录导致崩溃。

**配置节点**：`mcp_tools.playwright.output_dir_strategy` / `output_dir_template` / `output_dir_timestamp_fmt`，工具层特征见 `tool_bug_signatures.Playwright sandbox safe-delete crash`。

**信号**：启动 Playwright 时报 `safe-delete` / `EBUSY` / `cannot remove test-results`。

**测试步骤**：
1. 读取 config.yaml，确认 `output_dir_strategy == "timestamped"`
2. 运行时将 `{timestamp}` 按 `output_dir_timestamp_fmt` 展开，生成唯一目录（如 `test-results-20260805100146`）
3. 启动 Playwright，确认不再复用固定 `test-results` 目录

**判断标准**：
- PASS：每次运行使用唯一输出目录，启动清理不再崩溃
- FAIL：复用固定目录且启动崩溃

### 阶段 97：路由 mock 注册顺序（具体优先于通配）

**测试目标**：Playwright `route()` 按注册顺序匹配，通配路由必须晚于具体路由注册，否则含 `{id}` 的接口会被通配覆盖返回错误数据。

**配置节点**：`route_mock_order.require_specific_before_catchall` / `specific_route_patterns` / `catchall_route_patterns`，工具层特征见 `tool_bug_signatures.Playwright route order conflict`。

**信号**：对 `/admin/api/v1/workflows/{id}` 的请求被 `**/admin/api/v1/workflows*` 通配路由拦截并返回列表页 mock 体。

**测试步骤**：
1. 读取 config.yaml，确认具体路由（含 `{id}`）在通配路由之前注册
2. 对具体接口发起请求，验证返回的是具体 mock 而非通配 mock
3. 若命中 `conflict_signal`，按 `fix_hint` 重排注册顺序后回归

**判断标准**：
- PASS：具体接口走具体 mock，通配接口走通配 mock，互不干扰
- FAIL：通配覆盖具体接口，返回错误响应体

### 阶段 98：测试 Python 环境 venv 优先选择

**测试目标**：本项目 pytest 实际运行于 `backend/.venv`，而非受管 venv 3.13.12 或系统 Python3.14；必须显式选择正确解释器，否则依赖缺失/版本不符。

**配置节点**：`python_env_test_check.venv_discovery` / `prefer_venv_over_system` / `system_python_path`（作为 fallback），命令模板 `{python_path}` 由发现结果填充。

**信号**：执行 `pytest` 报 `ModuleNotFoundError: pytest` 或 `pytest-asyncio` 缺失；或测试连接到错误 Python 版本。

**测试步骤**：
1. 按 `venv_discovery` 顺序探测 `backend/.venv/Scripts/python.exe`（Windows）/ `backend/.venv/bin/python`（Linux/macOS）
2. 命中即作为 `{python_path}`；全部未命中才回退 `system_python_path`
3. 用解析出的 `{python_path}` 执行 `verify_command` 校验 pytest 版本
4. 执行 `test_run_command`（模板内含 `{python_path}`）

**判断标准**：
- PASS：使用 `backend/.venv` 解释器，pytest 及测试依赖齐全
- FAIL：误用系统/受管 Python 导致依赖缺失或断言环境不符

### 阶段 96-98 配置节点速查

| 阶段 | 配置节点 | 关键开关 | 关联规范/维度 |
|------|----------|----------|---------------|
| 96 | `mcp_tools.playwright.output_dir_strategy` | `timestamped` | 工具层 bug 特征库 |
| 97 | `route_mock_order.require_specific_before_catchall` | `true` | 后端维度 136 / 前端维度 118 |
| 98 | `python_env_test_check.venv_discovery` | `backend/.venv` 优先 | news-code-dev R186 复盘 |

---

## 2026-08-05 新增：后端 pytest 双轨 / 重命名完整性 / 测试隔离（阶段 99-101）

> 来源：测试过程四维度复盘（见 testing-playbook.md）+ news-code-dev 诊断标准 DS-8（全量重命名完整性）、DS-9（测试隔离与状态防泄漏）。
> 三项均为 config-driven，技能本身不硬编码任何路径/版本/旧名清单，可适配不同后端项目的 pytest 套件与重命名治理。

### 阶段 99：后端 pytest 套件执行（对应 news-code-dev DS-9 / 测试双轨约定）

**配置节点**：`config.yaml#backend_test`

**为什么**：后端改动必须通过 pytest 回归，而非误用前端 Playwright 技能。项目 pytest 实际运行于 `backend/.venv`（受管 venv），直接使用系统 Python 会 `ModuleNotFoundError: pytest`。需先解析 `{python_path}` 并校验 pytest 就绪，再展开命令模板执行，避免环境错配。

**触发条件**：`backend_test.enabled=true` 且改动含 `backend/**/*.py`（见 SKILL.md 测试范围双轨约定 scope=backend/all）。

**测试步骤**：
```
1. 读取 config.yaml#backend_test 获取：
   - python_path（显式解释器路径，默认 backend/.venv/Scripts/python.exe）
   - pytest_command（命令模板，含 {python_path}/{test_dir}/{extra_args} 占位符）
   - test_dir（测试目录，默认 backend/tests）
   - isolation_strategy（隔离策略，默认 tmp_path_and_monkeypatch）
   - default_extra_args（默认额外参数，如 --tb=short）
2. 解析解释器：
   a. 用解析出的 {python_path} 执行 verify_command（如 -c "import pytest; print(pytest.__version__)"）
   b. 失败 → FAIL（前置条件不满足，报告缺失 venv / 依赖）
3. 展开 pytest_command 模板：
   a. 替换 {python_path} / {test_dir} / {extra_args}（extra_args 可由 --scope 参数或 default_extra_args 拼接）
   b. 在项目根目录执行（cwd = 项目根）
4. 解析结果：
   a. 捕获 passed / failed / error 计数
   b. 解析失败用例名（test_file.py::Class::method）
5. 隔离校验：
   a. 按 isolation_strategy 要求，检查失败用例是否因未用 tmp_path+monkeypatch 重定向模块级路径导致
   b. 属隔离类失败 → 归类为 environment / 环境制品，不计入代码缺陷
6. 输出报告：PASS（全部通过）/ FAIL（failed/error>0）
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| pytest 就绪 + passed 全过 + 0 failed/error | PASS |
| pytest 未就绪（venv/依赖缺失） | FAIL（前置条件不满足） |
| failed/error > 0 且为真实断言失败 | FAIL（code_defect） |
| failed 用例因未隔离（依赖 unlink 成功） | WARN → 归类为 environment，要求修复测试隔离 |

**与阶段 98 关系**：阶段 98 负责"选对 venv"，阶段 99 负责"用该 venv 跑 pytest 并解析结果"，两者衔接构成后端回归双步。

**适用场景**：所有后端 Python 改动回归；引入新 pytest 套件的项目（覆盖 python_path / test_dir 即可）。
**不适用场景**：纯前端改动（admin-web/src / miniprogram）时 `backend_test.enabled=false`，仅跑 Playwright（阶段 2-4）。

---

### 阶段 100：重命名/别名完整性 grep 验证（对应 news-code-dev DS-8）

**配置节点**：`config.yaml#rename_verification`

**为什么**：全量重命名（如 `utcnow_naive` → `localnow_naive`）若未彻底，会留下半吊子引用，导致"函数已删但旧名仍在调用/注释"的混淆，甚至 import 失败。须确保 `deprecated_names` 在扫描范围内 0 匹配，仅 `preserve_paths` 豁免（如历史审计日志有意保留原貌）。

**触发条件**：`rename_verification.enabled=true` 且本次改动含"全量重命名/别名移除"动作（见 testing-playbook.md 维度：重命名完整性验证阶段）。

**测试步骤**：
```
1. 读取 config.yaml#rename_verification 获取：
   - deprecated_names（待核查旧名清单，如 [utcnow_naive]）
   - scan_paths（扫描范围，如 [backend, docs]）
   - preserve_paths（豁免目录，如 [docs/sonar-reports]）
   - stale_comment_pattern（失效引用注释信号，如指向已删除别名的"与 X 保持一致"）
2. 对每个 deprecated_name 在 scan_paths 执行 grep（排除 preserve_paths）：
   a. 命中 → 记录（文件路径 + 行号 + 旧名）
   b. 全部命中数汇总
3. 失效注释检查：
   a. 在 scan_paths 内 grep stale_comment_pattern
   b. 命中 → WARN（可能指向已删除别名的失效引用，需人工确认）
4. 输出残留清单 + 失效注释清单
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| scan_paths 内 deprecated_names 0 匹配 + 无失效注释 | PASS |
| scan_paths 内命中 deprecated_name | FAIL（重命名不完整） |
| preserve_paths 内命中 deprecated_name | SKIP（白名单豁免，不阻断） |
| 命中 stale_comment_pattern 失效引用注释 | WARN（需人工确认是否仍有效） |

**配置示例**：见 `config.yaml#rename_verification`（deprecated_names / scan_paths / preserve_paths / stale_comment_pattern 全部 config 驱动，无硬编码）。

**适用场景**：全量重命名、别名移除、弃用函数清理后的一致性校验；任意项目可复用（覆盖 deprecated_names 即可）。
**不适用场景**：局部小改动（单文件重命名）；无重命名动作的纯新增功能（enabled=false 跳过）。

---

### 阶段 101：测试隔离加固 / safe-delete 环境制品（对应 news-code-dev DS-9）

**配置节点**：`config.yaml#test_isolation`

**为什么**：WorkBuddy safe-delete 安全删除 shim 为 FAIL CLOSED（拦截 `unlink`/`Remove-Item`/`emptyDir`），导致两类伪失败：① 测试 teardown 删文件被拦截 → 残留文件被"按日 rollover 回填"造成计数泄漏（如 `test_ai_budget` 历史 `assert 2==1`）；② Playwright 启动删 `test-results` 崩溃、`vite build` 的 `emptyDir` 批量删除受阻。须显式重定向 + 唯一目录 + 白名单归类，避免把环境制品误判为代码失败。

**触发条件**：`test_isolation.enabled=true`（默认开启，所有含文件/目录操作的测试场景）。

**测试步骤**：
```
1. 读取 config.yaml#test_isolation 获取：
   - known_environment_artifacts（已知 safe-delete 环境制品用例清单）
   - require_tmp_path_redirect（是否要求 tmp_path+monkeypatch 重定向模块级文件操作）
   - playwright_unique_output（是否要求唯一输出目录）
   - playwright_output_template（唯一目录模板，如 test-results-{timestamp}）
2. 隔离要求校验：
   a. require_tmp_path_redirect=true 时，检查测试中 unlink/os.remove 是否经 tmp_path+monkeypatch 重定向
   b. 仍依赖 unlink 成功 → FAIL（隔离不达标，环境制品会污染）
3. Playwright 输出隔离：
   a. playwright_unique_output=true 时，确认运行用 playwright_output_template 展开的唯一目录
   b. 关联阶段 96（Playwright 输出目录沙箱安全删除绕过）确认不再复用固定 test-results
4. 环境制品归类：
   a. 将 known_environment_artifacts 中用例的失败/残留单独归类为"环境制品"
   b. 报告中单列一节，不计入 code_defect / 不触发代码修复流程
5. 输出隔离校验结果
```

**判断逻辑**：

| 条件 | 严重级别 |
|------|---------|
| 隔离要求满足（tmp_path 重定向）+ Playwright 唯一目录 + 环境制品单独归类 | PASS |
| 测试依赖 unlink 成功且未重定向 | FAIL（隔离不达标） |
| 环境制品被误计入代码失败（未单列） | WARN（报告呈现问题，要求修正归类） |
| Playwright 复用固定 test-results 目录导致启动崩溃 | FAIL（关联阶段 96 未生效） |

**与阶段 96/99 联动**：阶段 96 解决 Playwright 启动期 safe-delete 崩溃；阶段 99 执行 pytest 时按本阶段要求校验隔离；本阶段兜底 teardown 期 safe-delete 拦截导致的计数泄漏与归类。

**适用场景**：所有含文件/目录创建删除的测试；Playwright/vite 构建清理场景；引入新测试需 tmp_path 隔离的项目。
**不适用场景**：纯内存计算测试（无文件操作）；只读测试（无 teardown 删除）。

### 阶段 99-101 配置节点速查

| 阶段 | 配置节点 | 关键开关 | 关联规范/维度 |
|------|----------|----------|---------------|
| 99 | `backend_test` | `python_path` / `pytest_command` 模板 / `test_dir` / `isolation_strategy` | news-code-dev DS-9 / 测试双轨约定 |
| 100 | `rename_verification` | `deprecated_names` / `scan_paths` / `preserve_paths` / `stale_comment_pattern` | news-code-dev DS-8 |
| 101 | `test_isolation` | `known_environment_artifacts` / `require_tmp_path_redirect` / `playwright_unique_output` | news-code-dev DS-9 / 阶段 96 |

## 2026-08-05 新增：部署层 / 小程序合规专项（阶段 102-105）

> 来源：frozen 模式 .env 加载失败（appid missing）、安装包 .env 被 Excludes 静默丢弃、HLS 首播冷启动失败、微信剪贴板隐私 scope 未声明四类真实问题。对应 news-code-dev 诊断标准 DS-11 / DS-12 / DS-13 / DS-14。所有阈值/路径/反模式均由 `config.yaml` 对应区块管理，无硬编码业务值；`trigger_on_files` 与 signals 可适配任意项目。

### 阶段 102：frozen 模式配置加载路径解析测试（对应 DS-11）
- **配置节点**：`config.yaml#frozen_config_load_test`
- **触发**：`backend/**/config.py` / `backend/**/settings.py` 变更
- **判断逻辑**：
  - 【FAIL】`config.py` 的 `env_file` 为相对/固定路径，且整个文件无 `getattr(sys, "frozen")` 回退分支（exe 模式读不到 `.env`，表现 appid missing）
  - 【WARN】`env_file` 依赖 cwd 相对路径（冻结 exe 下 `_MEIPASS` 解析失败）
- **测试步骤**：定位 `SettingsConfigDict(env_file=...)` → 确认存在 `sys.frozen` 分支回退 `sys.executable` 同级 `.env` → 模拟冻结模式验证路径解析
- **通过标准**：冻结模式经 `sys.executable` 同级解析 `.env`；非冻结回退开发态路径；禁止仅依赖 cwd 相对 `env_file`
- **适用/不适用**：适用 PyInstaller/Nuitka 冻结 exe；不适用纯源码运行

### 阶段 103：安装包配置完整性测试（对应 DS-12）
- **配置节点**：`config.yaml#installer_secret_completeness_test`
- **触发**：`installer.iss` / `build/**` / `scripts/**` 变更
- **判断逻辑**：
  - 【FAIL】`installer.iss` 用 `Excludes` 静默丢弃 `.env` / 密钥
  - 【FAIL】`installer.iss` 未显式 `Source` 包含 `.env`
  - 【WARN】构建脚本拷贝 `.env` 后无 `attrib -H` 去隐藏属性
- **测试步骤**：检查 `Excludes` 是否含 `.env` → 检查 `Source` 是否显式包含 `.env` → 检查拷贝后是否 `attrib -H`
- **通过标准**：不 `Excludes` `.env`；显式 `Source` 包含 `.env`；拷贝后 `attrib -H`
- **适用/不适用**：适用含 `.env`/密钥的安装包；不适用配置全环境变量注入

### 阶段 104：小程序 HLS 首播冷启动静默重试测试（对应 DS-13）
- **配置节点**：`config.yaml#miniprogram_playback_coldstart_test`
- **触发**：`miniprogram/**/*.js` 变更
- **判断逻辑**：
  - 【FAIL】音频 `onError` 直接 `showToast`，且无 `MAX_HLS_RETRY` / `mp3Url` / `_applyProtocol` 静默重试或回退分支
  - 【WARN】首播失败即停 `loading`（`onError` 紧跟 `loading=false`）
- **测试步骤**：定位 `onError` 处理 → 确认首播失败静默重试（`MAX_HLS_RETRY`）→ 确认耗尽回退 mp3 直链 → 确认 `loading` 保持连续
- **通过标准**：首播失败静默重试一次不弹错；耗尽回退 mp3；不中断连续 loading
- **适用/不适用**：适用小程序/H5 播 HLS(m3u8) 流式音频；不适用纯本地 mp3 直链

### 阶段 105：微信隐私合规 scope 声明测试（对应 DS-14）
- **配置节点**：`config.yaml#wechat_privacy_scope_test`
- **触发**：`miniprogram/**/*.js` 变更
- **判断逻辑**：
  - 【FAIL】直接调用 `setClipboardData` 且无 `requirePrivacyAuthorize` 授权流程包裹
  - 【FAIL】直接调用 `getClipboardData` 且无 `requirePrivacyAuthorize` 授权流程包裹
- **测试步骤**：grep `setClipboardData`/`getClipboardData` 调用点 → 确认调用前有 `requirePrivacyAuthorize`/`onNeedPrivacyAuthorization` → 核对后台隐私清单含「剪贴板」scope（读写共用，非「写入剪贴板」字面量）
- **通过标准**：敏感 API 调用前完成隐私授权；后台声明对应 scope
- **适用/不适用**：适用微信小程序调用隐私接口；不适用非微信平台

### 阶段 102-105 配置节点速查

| 阶段 | 配置节点 | 关键开关 | 关联规范 |
|------|----------|----------|----------|
| 102 | `frozen_config_load_test` | `no_frozen_fallback` / `relative_env_file_breaks_in_exe` signals / `applicable_scenarios` | news-code-dev DS-11 |
| 103 | `installer_secret_completeness_test` | `excludes_env` / `no_explicit_env_source` / `no_attrib_unhide` signals | news-code-dev DS-12 |
| 104 | `miniprogram_playback_coldstart_test` | `onerror_direct_toast` / `loading_stop_on_first_fail` signals | news-code-dev DS-13 |
| 105 | `wechat_privacy_scope_test` | `clipboard_without_authorize` / `getclipboard_without_authorize` signals | news-code-dev DS-14 |

