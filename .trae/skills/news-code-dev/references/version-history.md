# 版本演进

本文档记录 MorningBrief 项目开发技能的版本演进和重要变更。

## v1.0.0 (2026-07-10)

### 初始版本

- 建立完整的开发技能体系
- 覆盖后端（FastAPI/SQLAlchemy）、前端（Vue 3/Element Plus）、小程序开发
- 定义 20 条元规范
- 提供标准化模板和指南

### 四维度复盘

#### 维度 1：架构设计

**做得好的**：
- 四层架构清晰，职责分离明确
- 配置驱动使代码具有良好的可移植性
- 缓存模式采用 cache-aside，简单有效

**待改进的**：
- 工作流编排可以考虑引入正式的状态机库（如 transitions）
- 缓存键命名规范需要进一步细化
- 内部接口鉴权机制需要加强

#### 维度 2：编码规范

**做得好的**：
- 类型注解覆盖全面，便于静态检查
- 异步规范统一，避免了混用同步/异步代码的问题
- 错误分类清晰，前端解析方便

**待改进的**：
- 日志格式需要进一步结构化（JSON 格式）
- 需要补充代码审查 checklist
- 前端组件拆分粒度需要统一标准

#### 维度 3：开发效率

**做得好的**：
- 模板文件覆盖了常见开发场景
- FAQ 文档解决了高频问题
- 元规范提供了明确的判断信号（grep 模式）

**待改进的**：
- 需要自动生成脚手架命令（如 `news-cli new router`）
- 测试覆盖率目标需要明确（如 80%）
- 需要补充性能基准测试

#### 维度 4：团队协作

**做得好的**：
- 前后端字段契约明确，减少沟通成本
- API 响应格式统一
- 数据库迁移使用 Alembic，版本可控

**待改进的**：
- 需要建立代码审查流程
- 需要补充 Git 分支管理规范
- 需要定义发布流程和回滚机制

### 未来规划

- [ ] 补充 API 文档自动生成（Swagger/OpenAPI）
- [ ] 增加性能监控和告警规范
- [ ] 完善小程序端开发指南
- [ ] 建立持续集成/持续部署规范
- [ ] 补充安全审计 checklist

## v1.1.0 (2026-07-12)

### 音频时长自动填充规范

- **问题**：stitch 步骤音频时长不足/超出范围时直接报错，重试无效
- **修复**：concat.py 增加自动填充（不足时追加静音）和切除（超出时裁剪）逻辑
- **新增元规范 23**：时长/容量约束的自动调整
- **新增元规范 24**：确定性失败的重试无效性
- **新增审查维度**：后端 23-25 维度（时长自动调整/重试有效性/临时资源清理），前端 21-25 维度（配置键一致性/批量失败诊断/路由优先级/参数规范化/Blob URL 清理）
- **新增编码规范**：coding-standards.md 补充时长自动调整规范和确定性失败重试规范
- **更新 config.yaml**：后端/前端审查技能增加 duration_auto_adjust、deterministic_failure_retry、temp_resource_cleanup 等审查配置
- **更新 project-config.json**：hardConstraints 增加时长约束相关 forbidden/required patterns

### 经验教训沉淀

- lessons-learned.md 补充音频时长自动填充完整复盘（含成功步骤/失败点/固定流程/适用场景）
- 外部服务异常分类粒度（维度 16）：NoAudioReceived 应分类为 TTSServiceError（可重试）
- 配置键一致性（维度 17）：前端 edge_rate 与后端 edge_tts_rate 不一致导致配置不生效
- 批量失败诊断信息（维度 18）：TTS 批量失败必须包含分段级错误摘要
- 分步重跑上游产物复用（维度 19）：retry 接口必须从指定步骤开始，复用上游产物

## v1.2.0 (2026-07-12)

### 开发模式登录失败修复（admin 用户 seed 路径不一致）

**问题**：开发模式启动后 admin/admin123 登录报"用户名或密码错误"

**根因**：`seed_admin.py` 默认数据库路径硬编码为 `dist/MorningBrief/data/news.db`（打包产物路径），与开发态运行时数据库 `backend/data/news.db` 不一致，导致开发态 `admin_user` 表永远为空

**修复**：
1. `seed_admin.py` 默认路径改用 `app.paths.resolve_db_path()`，与运行时路径解析保持一致
2. `main.py` lifespan 中新增 `_seed_default_admin()`，建表后自动 seed admin 用户（幂等），确保 dev/exe 模式均可登录
3. `start.ps1` 自动选择优先级从 `exe → venv → 系统 python` 调整为 `venv → 系统 python → exe`（默认开发模式）

**经验教训**：
- seed 脚本的默认路径必须通过 `paths.resolve_db_path()` 解析，禁止硬编码 `dist/` 路径
- 关键初始数据（admin 用户、默认配置）应在应用 lifespan 中自动 seed，不依赖外部脚本
- 数据库路径相关排查，优先检查 `paths.py` 的 `is_frozen()` 判定和 `get_app_root()` 返回值
- `app/models/__init__.py` 必须导入所有 ORM 模型，否则 `create_all` 无法建表（本次补充了 Channel/QueueConfig/Favorite/Feedback）

## v1.3.0 (2026-07-12)

### AI 服务商模型名称与配置持久化规范

**问题**：接入 DeepSeek 时发现模型名称大小写错误（deepseek-chat 应为 deepseek-v4-flash），预设切换后下拉框不反射选中状态，页面刷新后看不到当前使用的提供商。

**复盘内容**：
- 完整记录了成功执行步骤（需求分析→代码搜索→官网核对→后端修改→前端修改→语法验证→构建验证）
- 记录了 5 个不确定性与失败点（模型名称大小写不一致、PowerShell 字符串替换陷阱、预设切换下拉框不反射、页面刷新后看不到提供商、配置持久化返显不完整）
- 提炼了 2 个可抽象的固定流程（第三方服务接入标准流程、配置持久化与返显标准流程）
- 明确了适用场景与不适用场景

**编码规范新增**：
- 规范 25：第三方服务模型名称以官方文档为准（含已确认的 9 个提供商模型名称大小写对照表）
- 规范 26：配置持久化与返显完整性
- 规范 27：PowerShell 文件编辑安全
- 规范 28：模型定价表同步更新

**元规范新增**：
- 规范 25：第三方服务模型名称以官方文档为准（CRITICAL 优先级）
- 规范 26：配置持久化与返显完整性（HIGH 优先级）
- 规范 27：模型定价表同步更新（HIGH 优先级）

**审查技能更新**：
- 前端：新增维度 26-29（模型名称核对/下拉框反射/预设自动匹配/API Key 保护）
- 后端：新增维度 26-28（模型名称核对/定价表同步/配置键四者一致性）
- 前端 config.yaml：新增 model_name_verification / preset_switch_safety / page_load_preset_matching 配置
- 后端 config.yaml：新增 model_name_and_pricing / config_key_four_way_consistency 配置
- project-config.json：新增 model_name_official_source / pricing_table_sync 硬约束

**配置驱动**：所有模型名称清单、预设切换规则均通过 config.yaml 管理，技能本身不含硬编码值。

## v1.4.0 (2026-07-12)

### 工作流批量删除与事务级联规范

**需求**：工作流监控页面支持多选批量删除，删除时连带删除该条工作流相关所有内容（素材、稿件、审核、节目、播放日志、播放进度）。

**成功执行步骤**：
1. 需求分析与数据关系梳理（确认 workflow → steps/materials/scripts/reviews/episodes/play_logs/play_progress 的关联链）
2. 编写失败测试（Red 阶段）：覆盖级联删除、运行中拦截、缺失 ID 整批拒绝、管理员权限校验
3. 验证测试失败（确认测试真正检测新代码）
4. 实现事务级联删除服务（Green 阶段）：按依赖逆序删除，单事务保证原子性
5. 实现管理员批量删除端点（FastAPI 静态路由优先于动态路由）
6. 实现前端多选表格、确认对话框、批量删除按钮、分页修正
7. 端到端 Playwright 测试（Mock 路由隔离，避免列表桩吞掉详情请求）
8. 生产构建验证 + 完整回归测试

**不确定性与失败点**：
- 事务回滚验证：需确认任一 ID 不存在或运行中时整批不删除（通过测试验证）
- 前端路由冲突：列表页 el-link 点击后路由未变化，详情页不渲染（既有问题，本次未修复）
- E2E 测试路由匹配：**/workflows* 通配符过宽，吞掉详情请求，改为正则 \/admin\/api\/v1\/workflows(?:\?.*)?$
- 端口复用：Playwright reuseExistingServer 复用已有 dev server 导致页面指向错误项目
- 前端确认按钮文本：ElMessageBox 默认按钮为 "OK" 还是 "确认删除" 取决于 Element Plus 语言包
- 分页修正：删除后剩余记录可能少于当前页，需自动回退到上一页

**可抽象的固定流程**：
1. 批量删除标准流程：权限校验 → ID 存在性校验 → 运行状态校验 → 依赖逆序删除 → 事务提交 → 返回删除统计
2. 前端多选交互标准：selection-change 事件 → 选中状态跟踪 → 数量显示 → 二次确认 → 请求发送 → 清空选择 → 分页修正
3. 路由优先级标准：FastAPI 静态路由必须在动态路由之前定义；Vue Router 同理

**适用场景**：任何涉及多表关联数据的批量删除操作
**不适用场景**：仅单表的简单删除、软删除场景、需要保留审计追溯的场景

**新增元规范**：
- 规范 28：批量删除事务原子性（CRITICAL）
- 规范 29：前端多选交互规范（HIGH）
- 规范 30：路由静态路径优先级（已在规范 20 基础上强化）

**审查技能更新**：
- 后端：新增维度 29-31（批量删除事务原子性/路由优先级/权限校验）
- 前端：新增维度 30-32（多选交互/确认对话框/分页修正）
- 项目配置：新增 cascade_delete / batch_operation / route_priority 硬约束

## v1.5.0 (2026-07-12)

### 启动脚本安全、构建并发保护、共享构建依赖完整提取

**问题**：
1. 双击启动服务.bat默认启动 EXE 而非开发模式（优先级顺序错误）
2. 系统 Python 路径含空格（F:\Program Files\Python3.14\python.exe）导致 Start-Process 路径被截断
3. 构建打包时旧 EXE 占用 dist\MorningBrief 导致 PyInstaller COLLECT 阶段 PermissionError
4. FFmpeg 下载安装只提取两个 EXE，缺少配套 DLL 导致运行时 找不到 avdevice-63.dll
5. 日志仍使用 %s 占位符（旧版），Loguru 实际使用 {}，异常信息被吞

**成功执行步骤**：
1. 定位根因：start.ps1 自动选择顺序 exe → venv → 系统 python 改为 env → 系统 python → exe
2. 修复路径截断：Start-Process 使用 cmd /d /s /c 双层引号封装，-ArgumentList 传数组
3. 构建并发保护：uild-exe.ps1 增加 Stop-DistProcesses 函数，按可执行路径和命令行定位并终止占用进程
4. 共享构建依赖：fmpeg_service.py _extract_binaries 改为提取完整 bin 目录，提取前清除旧文件
5. 日志格式统一：确认源码已改为 {}，运行日志仍显示 %s 说明运行的是旧进程

**不确定性与失败点**：
- 第一次短超时测试终止了外层 PowerShell，遗留 PyInstaller 子进程导致第二次构建再次冲突
- pply_patch 匹配失败（编码问题），改用 exec_command 直接读取-修改-写入
- 前端 review SKILL.md 的 29 个维度 替换经过多次尝试才成功（PowerShell 字符串替换在某些环境下不生效）

**可抽象的固定流程**：
1. 启动脚本标准流程：优先虚拟环境 → 系统 Python → EXE 兜底；-Exe 参数始终强制 EXE
2. 路径安全封装：Start-Process 始终使用 cmd /d /s /c "" 四层引号封装
3. 构建并发保护：终止占用进程 → 等待退出 → 删除旧产物 → 验证删除成功
4. 共享构建提取：通过 EXE 定位 zip 内动态目录 → 提取 bin 下所有普通文件 → 清除旧文件 → 验证完整性
5. 日志格式验证：日志格式与源码版本必须一致，不一致说明运行旧构建产物

**适用场景**：所有 Windows 启动/构建脚本、共享构建压缩包解压、日志系统迁移
**不适用场景**：Linux/macOS 环境、static build（不依赖额外 DLL）

**新增元规范**：
- 规范 31：启动脚本路径含空格安全封装（CRITICAL）
- 规范 32：构建脚本并发保护（HIGH）

**新增编码规范**：
- 规范 33：共享构建依赖包完整提取（CRITICAL）
- 规范 34：日志格式与异常信息透传（HIGH）

**审查技能更新**：
- 后端：新增维度 33-38（启动脚本安全/构建并发/日志格式/运行环境一致性/共享构建依赖）
- 前端：新增维度 34-36（FFmpeg 依赖完整性/安装进度与超时/安装后自动检测）
- 项目配置：新增 shared_build_dll_dependency / loguru_placeholder_format / start_process_path_safety 硬约束

## v2.0.0 (2026-07-18)

### SonarQube 迭代闭环与三层测试验证规范

**背景**：基于 2026-07-18 完整的 SonarQube MCP 扫描 + 问题修复迭代闭环（23 个 OPEN→0）+ Playwright E2E 12/12 PASS + pytest 单元测试 146/146 PASS 的复盘，系统性地提炼编码规范与可复用流程，预防同类问题再次发生。

**新增编码规范（10 条，S51-S60）**：
- S51：认知复杂度阈值治理（cognitive_complexity ≤ 15）
- S52：async 函数必须含 await（SonarQube S7503）
- S53：正则表达式捕获组优化（SonarQube S6395）
- S54：list() 调用必要性检测（SonarQube S7504）
- S55：未使用变量、参数与导入检测（SonarQube S1481/S1128）
- S56：数据驱动重构模式（≥3 个 elif 重构为 list[tuple] + 循环）
- S57：import 语句组织规范（SonarQube S3863）
- S58：DOM API 现代化规范（SonarQube S7762）
- S59：SonarQube 扫描闭环规范（7 步 SQ-Loop 模式）
- S60：三层测试验证规范（unit + integration + E2E + SQ 回归）

**新增元规范（10 条，R66-R75）**：
- R66：认知复杂度阈值治理（CRITICAL）
- R67：async 函数必须含 await（CRITICAL）
- R68：正则表达式捕获组优化（HIGH）
- R69：list() 调用必要性检测（MEDIUM）
- R70：未使用变量/参数/导入检测（HIGH）
- R71：数据驱动重构模式（HIGH）
- R72：import 语句组织规范（MEDIUM）
- R73：DOM API 现代化规范（HIGH）
- R74：空 except 块禁止规范（HIGH）
- R75：SonarQube 扫描闭环规范（CRITICAL）

**可抽象的 4 类固定流程**：
1. **SonarQube 迭代闭环（SQ-Loop 模式）**：扫描→等待→拉取问题→分类→修复→单元测试→二次扫描回归
2. **认知复杂度治理**：检测→定位热点→抽取辅助函数/数据驱动重构→验证复杂度
3. **数据驱动重构**：识别 if/elif 链→提取 list[tuple]→循环匹配→配置化
4. **三层测试验证**：单元测试→集成测试→E2E 测试→SQ 二次扫描

**project-config.json 新增配置节**：
- `coding_standards.complexity`：复杂度阈值参数（max_function_lines/max_nesting/max_cognitive_complexity）
- `coding_standards.async_rules`：async/await 规则与例外
- `coding_standards.regex`：正则优化规则
- `coding_standards.unused_code`：未使用代码检测规则
- `coding_standards.data_driven_refactor`：数据驱动重构阈值
- `coding_standards.empty_catch`：空 except 块规则
- `coding_standards.import_organization`：import 组织规则
- `coding_standards.dom_api_modernization`：DOM API 现代化规则
- `sonarqube`：SonarQube 扫描配置（环境变量/projectKey/sources/exclusions/severity/max_regression_retries）
- `testing`：三层测试配置（min_unit_coverage/require_integration_test/require_e2e_test/e2e_p0_must_pass/命令）

**配置驱动原则**：所有新规范的阈值参数均通过 project-config.json 管理，不同项目可调整阈值不需修改技能代码。

**适用场景与不适用场景**：
- SQ-Loop 闭环：适用于发版前完整验证；不适用于 hotfix
- 认知复杂度治理：适用于 service/workflow 层；不适用于 models 层
- 数据驱动重构：适用于 ≥3 个相似 elif 分支；不适用于逻辑差异大或仅 1-2 个分支
- 三层测试验证：适用于中大型项目；不适用于小型项目（<5 个端点）

**跨技能同步更新**：
- news-backend-code-review v1.6.0 → v1.7.0：新增 8 个审查维度（73-80）
- news-frontend-code-review v1.7.0 → v1.8.0：新增 4 个审查维度（57-60）
- news-auto-testing v5 → v6：新增 4 个测试阶段（20-23）

## v3.0.0 (2026-07-22)

### 前端交互稳定性与编辑完整性复盘规范

**背景**：基于 2026-07-22 多轮修复经验（浏览器最小化自动弹出三轮修复 + Agnes AI 模型名大小写 + 工作流重跑状态轮询 + 步骤进度条可视化 + API Key 脱敏回退 + preset_configs 旧数据兼容 + Edit 工具文件损坏），按 Sequential Thinking 4 维度框架系统性地提炼编码规范与可复用流程，预防同类问题再次发生。

**新增元规范（9 条，R118-R126）**：
- R118：浏览器窗口最小化防护（CRITICAL）— router.push 替代 location.href、!document.hidden 检查、silent 请求、严格相等路径判断
- R119：异步路由参数时序处理（HIGH）— router.replace 异步、显式传参、detail.value 取最新值
- R120：列表数据动态轮询状态同步（HIGH）— 终态停止、运行态轮询、不可见暂停、silent 请求、重跑重置
- R121：第三方服务模型名称核对（CRITICAL）— 官方文档为准、大小写敏感、预设配置一致
- R122：API Key 脱敏回退链路（HIGH）— is_masked 检查、回退真实密钥、preset_configs 旧数据兼容
- R123：文件编辑完整性验证（HIGH）— Edit 后 Read 验证、损坏信号检测、Write 完整重写、构建产物 Grep 验证
- R124：步骤进度可视化（MEDIUM）— pending=0%/running=50%/success=100%、条纹动画、状态映射
- R125：跨流程组合应用场景（MEDIUM）— 详情页/配置页/测试连接的组合流程模板
- R126：配置驱动与通用性约束（HIGH）— 所有参数通过配置文件管理、禁止硬编码、新增场景只需修改配置

**可抽象的 7 类固定流程 + 5 类判断逻辑矩阵**：
1. **浏览器窗口最小化防护流程（Frontend-Minimize-Guard）**：router.push 替代 location.href、!document.hidden 检查、silent 请求、严格相等路径判断
2. **异步操作后路由参数时序处理流程（Route-Param-Timing）**：router.replace 异步、显式传参、detail.value 取最新值
3. **列表数据动态轮询流程（Polling-State-Sync）**：终态停止、运行态轮询、不可见暂停、silent 请求、重跑重置
4. **第三方服务模型名称核对流程（Model-Name-Verification）**：官方文档为准、大小写敏感、预设配置一致
5. **API Key 脱敏回退链路流程（Masked-Key-Fallback）**：is_masked 检查、回退真实密钥、preset_configs 旧数据兼容
6. **文件编辑完整性验证流程（Edit-Integrity-Verify）**：Edit 后 Read 验证、损坏信号检测、Write 完整重写、构建产物 Grep 验证
7. **步骤进度可视化流程（Step-Progress-Visualize）**：pending 0%、running 50%+条纹、success 100%、failed 100%+exception

判断逻辑矩阵：
1. 路由跳转方式选择矩阵（401/业务/重跑/外链）
2. 错误提示可见性判断矩阵（用户操作/轮询/不可见/401）
3. 异步数据加载参数来源矩阵（正常/replace后/轮询/重跑后）
4. 文件修改工具选择矩阵（小修改/大重写/损坏/验证）
5. 进度条状态映射矩阵（pending/running/retrying/success/failed）

**project-config.json 新增配置节**：
- `frontend_minimize_guard`：浏览器窗口最小化防护参数（forbid_location_href/require_hidden_check/silent_param/strict_path_match/login_path）
- `route_param_timing`：异步路由参数时序参数（explicit_param_mode/use_detail_value/await_after_replace）
- `polling_state_sync`：轮询状态同步参数（interval_ms/terminal_states/running_state/silent_param/pause_on_hidden/stop_before_restart）
- `model_name_verification`：模型名称核对参数（case_sensitive/official_source_required/sync_pricing_table/sync_frontend_presets）
- `masked_key_fallback`：API Key 脱敏回退参数（is_masked_check/fallback_to_db/preset_configs_storage/legacy_data_compat/masked_prefix）
- `edit_integrity_verify`：文件编辑完整性验证参数（verify_after_edit/corruption_signals/use_write_for_large_rewrite/build_grep_check/build_artifact_path）
- `step_progress_visualize`：步骤进度可视化参数（state_mapping/success_status/failed_status/stripe_anim_states/max_percentage）
- `cross_flow_combination`：跨流程组合参数（detail_page_combo/config_page_combo/test_connection_combo）
- `config_driven_universal`：配置驱动通用性参数（config_files/forbid_hardcoded/template_fixed/new_scenario_config_only）

**配置驱动原则**：所有新规范的阈值参数均通过 project-config.json 管理，不同项目可调整阈值不需修改技能代码。

**适用场景与不适用场景**：
- 浏览器窗口最小化防护：适用于 SPA 后台管理系统、需要轮询的页面；不适用于 SSR 应用、移动端 App
- 异步路由参数时序处理：适用于 SPA 路由跳转后立即加载新数据；不适用于同步路由、URL 直接访问
- 列表数据动态轮询：适用于工作流/任务监控；不适用于 WebSocket/SSE 实时推送
- 第三方服务模型名称核对：适用于接入第三方 LLM/TTS API；不适用于内部自研 API
- API Key 脱敏回退链路：适用于配置页面有 API Key 脱敏显示；不适用于无 API Key 的系统
- 文件编辑完整性验证：适用于使用 Edit 工具修改文件；不适用于全新文件创建
- 步骤进度可视化：适用于工作流步骤、批处理进度；不适用于实时数据流、瞬时操作

**跨技能同步更新**：
- news-frontend-code-review：新增 5 个审查配置区块（frontend_minimize_guard_check/route_param_timing_check/polling_state_sync_check/step_progress_visualize_check/edit_integrity_verify_check）
- news-backend-code-review：新增 3 个审查配置区块（model_name_case_check/masked_key_fallback_check/preset_configs_legacy_compat_check）
- news-auto-testing：新增 6 个测试阶段（stage_minimize_guard_test/stage_route_param_timing_test/stage_polling_state_sync_test/stage_step_progress_render_test/stage_edit_integrity_verify_test/stage_masked_key_fallback_test）

## v2.1.0 (2026-07-13)

### 编码规范系统性补充（7 条）

**背景**：基于最近解决的问题，系统性地提炼 7 条编码规范到 news-code-dev 技能中，覆盖前端响应拦截器、工作流重跑语义、配置字段命名、时区一致性、外键约束、凭证脱敏、内存泄漏防护等高频踩坑场景。

**新增编码规范（7 条）**：

1. **规范 76：响应拦截器特殊响应类型处理**（references/coding-standards.md）
   - 二进制响应类型（blob/arraybuffer）不走统一 `{code,message,data}` 解构
   - 拦截器开头判断 responseType，直接返回原始数据
   - 适用场景：文件下载、音频/视频流、图片二进制数据

2. **规范 2：工作流重跑/重试语义**（assets/guides/workflow-guide.md 第 9 节）
   - 重跑应在原工作流上执行，不创建新工作流
   - 固定流程：删除 from_step 及之后步骤记录 → 重置状态为 queued → 入队当前 workflow_id
   - 前驱校验：from_step 之前的步骤必须 success 且有 result
   - 不适用场景：全新工作流触发（应用 trigger_workflow）

3. **规范 77：配置字段命名一致性**（references/coding-standards.md）
   - config_key（前端字段名）= 逑名（如 edge_voice）
   - Settings 属性名 = 全大写下划线（如 EDGE_TTS_VOICE）
   - CONFIG_KEY_MAP 映射 config_key → Settings 属性名
   - 前后端字段名、路由层模型字段名、CONFIG_KEY_MAP 的 key 必须四者一致

4. **规范 78：时区一致性**（references/coding-standards.md）
   - 生产代码用 utcnow_naive()（本地时间），测试必须用 datetime.now()
   - 禁止测试用 datetime.utcnow()（UTC）与本地时间混用
   - 项目为单机部署（香港时区 UTC+8），所有时间字段存储为本地 naive datetime

5. **规范 5：外键约束防御性处理**（assets/rules/database.md）
   - 不依赖 SQLite PRAGMA foreign_keys 开关，手动处理关联表
   - 删除父记录前先 UPDATE 子表外键为 NULL
   - 测试环境默认未开启 PRAGMA foreign_keys，手动 UPDATE 保证行为一致

6. **规范 6：凭证脱敏规范**（assets/rules/security.md）
   - 正则保留 key 名只抹去 value：`(?i)((?:token|secret|key|password|appkey)\s*[:=]\s*)\S+`
   - 替换为 `m.group(1) + "***"` 而非整体替换为 `***`
   - 适用场景：日志输出、错误信息、测试断言

7. **规范 7：内存泄漏防护（Blob URL 释放）**（assets/rules/security.md）
   - blob URL 必须在组件卸载、列表刷新、删除操作时释放
   - 按需加载策略：首次点击才请求音频/文件数据，避免列表加载时并发请求
   - 适用场景：音频/视频播放、文件预览、图片二进制展示

**规范描述统一格式**：所有 7 条规范均包含「判断逻辑 + 固定流程 + 适用场景 + 不适用场景」四要素，确保可执行可验证。

**配置驱动原则**：所有规范与项目 V1.2 架构（SQLite + TTLCache + 单机 exe）一致，不硬编码具体业务字段名，用逑名表达（如「响应类型」而非「blob」）。

**适用场景与不适用场景**：
- 响应拦截器特殊响应类型处理：适用于二进制响应；不适用于 JSON API 响应
- 工作流重跑语义：适用于任意步骤重跑、断点续跑；不适用于全新工作流触发
- 配置字段命名一致性：适用于多 Provider 配置、全链路字段传递；不适用于内部变量名
- 时区一致性：适用于所有时间计算/比较的测试；不适用于明确存储 UTC 时间的场景
- 外键约束防御性处理：适用于测试环境与生产环境行为不一致的外键操作；不适用于明确开启外键约束且数据完整性要求高的场景
- 凭证脱敏规范：适用于日志输出、错误信息、测试断言；不适用于非凭证类文本
- 内存泄漏防护：适用于音频/视频播放、文件预览；不适用于静态资源 URL

**文档结构同步**：
- SKILL.md：version 2.0.0 → 2.1.0，updated 2026-07-18 → 2026-07-13
- references/coding-standards.md：新增规范 76/77/78
- assets/guides/workflow-guide.md：新增第 9 节「工作流重跑/重试语义」
- assets/rules/database.md：新增「外键约束防御性处理」章节
- assets/rules/security.md：新增「凭证脱敏规范」和「内存泄漏防护（Blob URL 释放）」章节
