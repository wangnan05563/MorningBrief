---
name: "news-auto-testing"
description: "前端自动化测试：使用 Playwright MCP + Chrome DevTools MCP 对 Web 应用做全面功能/性能/API 测试。当用户要求'测试前端/全面测试/系统测试/回归测试'或提到 'news-auto-testing / 前端测试' 时调用。"
whenToUse: "需要前端测试/全面测试/回归测试/性能测试时使用"
triggers: "测试前端/全面测试/系统测试/回归测试/API测试/性能测试 | news-auto-testing | 前端测试"
version: "3.0.0"
updated: "2026-07-31"
config: "config.yaml"
---

# 前端自动化测试

使用 Playwright MCP + Chrome DevTools MCP 对 Web 应用进行全面测试，所有参数通过 `config.yaml` 管理。

## 配置文件

所有测试参数通过配置文件管理：
- 模板：`config.example.yaml`
- 实际：`config.yaml`（从模板复制后按项目修改）

配置文件分为 39 个区块：

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
| `issue_classification` | 问题分类（code_defect/business_data/framework_behavior/environment/tool_layer_bug/data_isolation_violation/rss_source_unreachable/third_party_rate_limit） |
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
| `url_safety_test` | 小程序 URL 编码安全性预检（非 ASCII 字符检测、encodeURI 强制） |
| `miniprogram_playback_test` | 小程序播放安全测试（高频回调节流 + iOS/Android 双端兼容） |
| `nosonar_positioning_test` | NOSONAR 注释位置正确性验证（多行函数定义首行 + 前端按文件类型匹配注释语法） |
| `sonarqube_environment_check` | SonarQube 扫描环境兼容性预检（Node.js 版本 + PowerShell .bat 封装） |
| `parallel_subagent_verification` | 并行子代理修复结果二次核查（grep 验证 NOSONAR 实际写入 + 文件组互斥） |
| `cross_project_migration_test` | 跨项目模块迁移 7 步法验证（需求/架构/后端/前端/测试编写/测试执行/构建验证） |
| `frontend_nested_paths_test` | 前端嵌套目录相对路径校验（views/<module>/<Page>.vue 结构的 @use/import 层级） |
| `icon_migration_test` | UI 图标跨库迁移存在性验证（构建前用 node -e 验证图标名在目标库中存在） |
| `cache_test_isolation_test` | 模块级单例缓存测试隔离验证（TTLCache/dict/lru_cache 的 _reset_cache_for_test 调用） |
| `python_env_test_check` | 多版本 Python 环境测试执行预检（显式 Python 路径 + pytest 依赖 + requirements-dev.txt） |
| `menu_grouping_test` | 菜单分组与角色可见性测试（el-sub-menu 分组、meta.group、角色控制、手风琴效果） |
| `pwa_icon_test` | PWA 图标与 manifest 测试（manifest.json 完整性、favicon、icon-192/512、theme-color） |
| `cover_image_rendering_test` | 图片封面渲染与降级测试（按段渲染、加载失败降级、lazy-load、CLS） |
| `about_help_module_test` | About/Help 模块完整性测试（元数据展示、检查更新、锚点导航、搜索过滤） |
| `monitoring_thresholds_test` | 关键指标监控告警测试（关键词命中率、LLM 字数达成率、TTS 成功率、工作流成功率） |
| `channel_health_dashboard_test` | 频道素材健康度仪表盘测试（channel-health 端点、健康度三级判定、rss-health 端点） |
| `command_chain_syntax_check` | 命令链语法适配预检（PowerShell && 检测、分隔符自动适配） |
| `function_symmetry_check` | 模块级函数对称性预检（导入符号存在性验证、对称函数对检查） |
| `service_restart_verification` | 服务重启加载新代码验证（停止旧服务→启动新服务→openapi.json 端点验证） |
| `auth_verification_matrix` | API 认证验证矩阵（带 token 200 + 不带 token 401 + 可选过期/无效 token） |

## Input / Output 契约

### Input

- 必填：无（从 `config.yaml` 读取全部参数）
- 可选：测试范围（`all`/`api`/`performance`/`regression`）、目标 URL 覆盖

### Output

- 测试报告文件（Markdown，输出到 `report.output_dir`）
- 控制台摘要（通过/失败/阻塞问题数）
- 退出码：0=全部通过 / 1=有 FAIL / 2=有阻塞问题

## 测试流程

默认执行 6 个核心阶段，辅助阶段（7-95，共 89 个）按 `config.yaml` 各区块的 `enabled` 字段按需激活。完整阶段定义见 [stages.md](references/stages.md)。

### 阶段 1：环境预检

1. 读取 `config.yaml` 获取所有配置参数
2. 如 `workflow.auto_start_service=true`，执行 `service.start_script` 启动服务
3. 健康检查：轮询 `GET service.base_url + service.health_endpoint`，超时 = `service.health_timeout` 秒
4. MCP 工具可用性检查：验证 primary_tool 可用，失败时切换 fallback_tool
5. 如使用 Playwright，检查浏览器是否安装（失败时运行 `install_command`）

### 阶段 2：页面遍历测试

对 `pages` 清单中每个 `skip: false` 的页面执行：
1. 导航到 `base_url + page.path`（支持菜单点击 + URL fallback）
2. 截图（全页优先，超时自动降级为视口截图；路径必须为绝对路径）
3. 获取页面快照（超 `snapshot.max_size_kb` 时保存到文件避免截断）
4. 检查控制台消息：error 级别消息如匹配 `assertions.console_error_whitelist`，归类为 framework_behavior
5. 检查网络请求（排除 pending）
6. 判断页面加载成功：无非白名单 error + 网络 200 + 预期文本匹配
7. 如 `page.buttons` 非空，执行按钮交互测试（点击 → 验证 expected_action → 超时重检目标状态）
8. 记录结果：PASS / WARN / FAIL / SKIP

### 阶段 3：登录流程测试

1. 导航到 `credentials.admin.login_page`
2. 获取表单 HTML，确认选择器有效
3. 填写用户名、密码，点击登录按钮
4. 检查：`POST login_endpoint` 返回 200 + token 返回 + URL 跳转 + 用户名/角色显示
5. 登录失败时查找 `fix_strategies` 匹配的修复策略

### 阶段 4：API 端点测试

1. 按 `test_priority.execution_order`（P0→P1→P2→P3）排序测试用例
2. 替换占位符（内置：`${current_date}`/`${timestamp}`/`${username}`/`${password}` 等 + 自定义：`placeholders` 区块）
3. 如 `requires_auth=true`，先登录获取 token
4. 发送 HTTP 请求，检查 `status == expected_status` + `JSON.code` 在 `acceptable_codes`
5. P0 失败时如 `fail_action=block_release`，立即停止后续低优先级用例

### 阶段 5：性能审计

1. Lighthouse（如 `performance.lighthouse_enabled=true`）：对 `lighthouse_pages` 审计，支持隔离 context 避免登录态干扰
2. Performance Trace（如 `performance.trace_enabled=true`）：检查 LCP/CLS/TTFB 阈值，Trace 失败降级为仅 Lighthouse 结果
3. 所有性能指标为 WARN 级别，不阻止测试通过

### 阶段 6：报告生成

1. 汇总所有结果，按 `severity_levels` 分级统计
2. 按 `issue_classification` 分类问题（code_defect / business_data / framework_behavior / environment 等）
3. 按 `test_priority` 分组展示（P0 红色/阻塞发布，P1 橙色/发版前修复，P2 黄色/下迭代修复，P3 灰色/仅记录）
4. 生成 Markdown 报告到 `report.output_dir`

## 修复流程

当测试发现 `code_defect` 类问题且 `workflow.auto_fix=true` 时：
1. 查找 `fix_strategies` 中匹配的修复策略
2. 实施代码修复
3. 如 `build_before_regression.enabled=true`：检查依赖 → 执行构建 → 失败时重装依赖
4. 如 `regression_cache_strategy.ignore_cache=true`：回归测试使用 `ignoreCache` 强制刷新
5. 对修复项重新执行测试（`regression_after_fix=true`）
6. 如仍失败且未超过 `max_fix_attempts`，重试

**注意**：非 code_defect 类问题不触发代码修复流程，仅在报告中标注。

## 判断逻辑

### 页面加载成功

| 条件 | 严重级别 |
|------|---------|
| 无控制台 error（排除白名单）+ 网络 200 + 文本匹配 | PASS |
| 有控制台 warn 但功能正常 | WARN |
| 有控制台 error（非白名单）或网络非 200 | FAIL |
| dev_only 页面在生产模式下 | SKIP |

- 文本匹配模式（`assertions.text_match_mode`）：`any_substring`（默认）/ `exact` / `regex`
- 控制台 error 白名单：匹配 `assertions.console_error_whitelist` 中任一子串时归为 framework_behavior

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

### 问题分类

| 分类 | 含义 | 处理方式 |
|------|------|----------|
| code_defect | 代码缺陷 | 触发修复流程，修改源码 |
| business_data | 业务数据问题 | 报告中标注解决方案，不修改代码 |
| framework_behavior | 框架预期行为 | 报告中记录，无需修复 |
| environment | 环境问题 | 报告中标注，需环境层面修复 |
| tool_layer_bug | 开发工具版本 bug | 报告中标注工具名+受影响版本+修复步骤，不修改代码 |
| data_isolation_violation | 数据隔离违规（OR NULL 兜底） | 触发代码修复流程 |
| rss_source_unreachable | RSS 源不可达 | 报告中标注源名+失效原因+替代方案 |
| third_party_rate_limit | 第三方服务限流 | 报告中标注服务名+限流特性+串行验证建议 |

### 测试用例优先级

| 优先级 | 名称 | 颜色标识 | 失败处理 | 执行顺序 |
|--------|------|----------|----------|----------|
| P0 | 阻塞性 | 红色 | block_release（阻止发布） | 最先执行 |
| P1 | 高优先级 | 橙色 | fix_before_release（发版前修复） | P0 之后 |
| P2 | 中优先级 | 黄色 | fix_next_iteration（下个迭代修复） | P1 之后 |
| P3 | 低优先级 | 灰色 | log_only（仅记录） | 最后执行 |

P0 失败阻塞后续低优先级用例；未标注 `priority` 的用例按 `default_priority`（默认 P2）归类。

## 常见问题修复策略

### FAIL 级（必须修复）

1. **前端页面 404**：后端未挂载前端静态文件 → 检查 `paths.py` 的 `resolve_admin_dist()` 路径
2. **JS MIME 类型错误**：Windows mimetypes 缺失 → `main.py` 添加 `mimetypes.add_type()`
3. **健康检查超时**：服务初始化阻塞 → 增加 `health_timeout` 或检查 lifespan
4. **登录失败无账号**：数据库无管理员 → bcrypt 哈希后 INSERT

### WARN 级（可继续测试）

1. **Playwright 浏览器未安装**：运行 `npx playwright install chromium`
2. **Playwright 版本不匹配**：创建目录 junction 链接
3. **Chrome DevTools 元素交互超时**：改用直接导航 URL
4. **PowerShell curl 转义**：改用 `Invoke-RestMethod`
5. **全页截图超时**：降级为视口截图（`screenshot.full_page=false`）
6. **快照输出过大被截断**：保存到文件后读取（`snapshot.save_dir`）
7. **菜单点击不跳转 URL**：自动改用 navigate_page（`menu_click_fallback`）
8. **UI 组件库废弃 API 警告**（如 el-radio label）：升级为新 API 用法
9. **图表插件未注册**（如 Chart.js Filler）：import 并 register 缺失插件

### framework_behavior 级（无需修复）

1. **Element Plus MessageBox cancel error**：用户取消确认框时框架抛出 cancel，加入 `console_error_whitelist`
2. **Vue Router 首次导航重定向**：SPA 应用路由守卫重定向属正常行为

### business_data 级（需配置/数据修复）

1. **工作流执行失败**：外部 API 凭证未配置（如 LLM API key 为占位符），需在 `.env` 填入真实凭证
2. **API 返回空数据**：数据库无初始数据，需执行种子数据脚本

### environment 级（需环境修复）

1. **node_modules 不完整**：删除问题包后重装（`npm install <package>`）
2. **前端构建失败**：检查依赖版本兼容性

修复后如 `workflow.regression_after_fix=true`，对失败项重新执行测试。

## 失败处理

| 失败场景 | 判断信号 | 处理方式 |
|----------|----------|----------|
| 服务不可达 | 健康检查失败 | 自动启动服务（如 `workflow.auto_start_service=true`） |
| 登录失败 | 登录后预期文本未出现 | 记录 FAIL，继续后续测试（如 `workflow.continue_on_failure=true`） |
| 页面加载超时 | 页面 30s 未完成加载 | 重试 2 次 → FAIL |
| 配置缺失 | config.yaml 不存在 | 回退 config.example.yaml + 提示用户复制 |
| Playwright 浏览器不匹配 | 版本号不一致 | 创建 junction 目录链接 |
| MCP 截图路径错误 | 相对路径解析失败 | 强制使用绝对路径 |
| 快照截断 | a11y 树过大 | 保存文件后读取 |
| 菜单点击不跳转 | URL 未变化 | `navigate_page` fallback |
| 修复后缓存旧 JS | 回归测试加载旧版本 | `ignoreCache` 强制刷新 |
| P0 用例失败 | 阻塞性失败 | 停止低优先级用例，立即报告 |

## 技能调用示例

### 全面测试

1. 读取 `config.yaml`
2. 启动服务（如 `auto_start_service=true`）
3. 按顺序执行 6 阶段测试
4. 遇到问题按 `fix_strategies` 修复
5. 生成报告到 `report.output_dir`

### 仅 API 测试

1. 读取 `config.yaml` 的 `api_endpoints` 部分
2. 跳过阶段 2（页面遍历）和阶段 5（性能审计）
3. 执行阶段 4（API 测试），输出结果

### 回归测试

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
6. **占位符替换**：API 路径和请求体支持内置占位符（`${current_date}`/`${current_month}`/`${current_year}`/`${timestamp}`/`${username}`/`${password}`）和自定义占位符
7. **配置优先**：所有参数从 `config.yaml` 读取，不修改配置文件外的任何硬编码值
8. **截图路径**：MCP 工具的相对路径基于其自身 cwd，必须使用绝对路径
9. **截图降级**：全页截图超时时自动降级为视口截图
10. **快照落盘**：快照输出超过 `snapshot.max_size_kb` 时自动保存到文件
11. **error 白名单**：框架预期 error 通过白名单过滤，不触发 FAIL
12. **回归缓存**：修复后回归测试使用 `ignoreCache` 强制刷新
13. **问题分类**：只有 code_defect 类触发代码修复流程
14. **优先级执行**：API 测试按 P0→P1→P2→P3 执行，P0 失败阻塞后续
15. **优先级报告**：报告按优先级分组展示，含各级通过率摘要

## 参考

- [stages.md](references/stages.md) — 全部 95 个测试阶段详解（含判断逻辑、触发条件、配置节点）
- [config.example.yaml](config.example.yaml) — 配置模板（所有阈值、页面清单、修复策略的默认值）
- [_shared/references/](../_shared/references/) — 跨技能共享主题（PowerShell 兼容性、编码规范等）
