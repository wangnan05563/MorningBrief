# 测试流程复盘与最佳实践

> 本文档从 2026-08-05 会话中的测试实践提炼，落实用户对 news-auto-testing 的优化要求。
> 采用 **Sequential Thinking（顺序化推理）** 组织：先界定测试范围 → 再选执行策略 → 处理环境制品 → 验证 → 沉淀。
> 覆盖维度：成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用与不适用场景。

---

## 维度 1：成功执行测试任务的完整步骤（顺序化）

适用于"对一轮代码改动做全量回归"任务的标准路径：

1. **界定改动性质（Sequential Step 1）**：区分本轮改动是"后端 Python"还是"前端 Vue/小程序"。
   - 后端改动 → 执行后端 pytest；前端改动 → 执行 Playwright；两者皆有 → 都跑。
2. **选择执行策略（Step 2）**：
   - 后端：`backend/.venv/Scripts/python.exe -m pytest backend/tests/ -q`（项目受管 venv，非系统 Python）。
   - 前端：`node_modules/.bin/playwright test`（或 `npx playwright test`）按 `config.yaml#pages` / `api_endpoints` 执行。
3. **处理测试隔离（Step 3）**：依赖模块级文件路径/单例的测试，fixture 必须 `tmp_path` + `monkeypatch` 重定向（见维度 2 的 safe-delete 失败点）。
4. **执行并重试（Step 4）**：跑全量；对偶发/环境相关失败，先 git stash 验证是否预存，再决定是否重跑。
5. **重命名/重构完整性验证（Step 5）**：若改动含公共 API 重命名，grep 全仓库旧名 = 0 匹配（见维度 3 模板 T4）。
6. **报告（Step 6）**：输出通过/失败/阻塞计数；把"环境制品"与"代码失败"分开标注。

**关键教训**：步骤 1 的范围界定直接决定跑哪套测试——本会话后端改动经后端 pytest 374 passed 闭环，无需前端 Playwright；步骤 3 的隔离能避免 safe-delete 把"环境残留"伪装成"代码失败"。

## 维度 2：测试执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 测试状态泄漏（计数 +1） | `reset_budget()` 用 `file_path.unlink()` 清文件，被 safe-delete 拦截（FAIL CLOSED） | `test_ai_budget` 断言 `total_calls==1` 实得 2 | 隔离依赖真实文件系统删除成功；残留文件被 rollover 回填 | fixture 重定向 `_budget_file_path` 到 `tmp_path` |
| 预存环境制品 FAIL | `test_fix_integration.py::TestUserAvatar::test_upload_avatar_success` 的 teardown 被 safe-delete 拦截 | 历史运行中偶发 1 failed | 头像上传 teardown 删文件被拦截 | 区分"环境制品"，报告单独归类；非代码失败 |
| 重命名遗漏 ImportError | 删别名漏改某处调用/注释 | 启动 ImportError | grep 未全量验证 | 全仓库 grep 0 匹配（维度 3 T4） |
| Playwright 沙箱启动崩溃 | safe-delete 拦截启动时对 `test-results` 的清理 | Playwright 无法启动 | 删除旧目录被拦截 | `--output=test-results-$(date +%s)` 唯一目录，启动不再删旧目录 |
| 前端构建清理被拦截 | `vite build` 的 `emptyDir` 阶段批量删 `dist` | 本地构建验证受阻 | safe-delete 拦截批量删除 | 用全新输出目录（如 `dist_check`）绕过 |
| 多 Python 环境 pytest 缺失 | 用 `python -m pytest` 解析到无 pytest 的解释器 | No module named pytest | PATH 解析到错误 Python | 显式指定受管 venv 路径（见维度 3 T5） |

## 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 核心判断信号 | 落地方式 |
|------|--------------|----------|
| T1 改动范围判定 | 改动文件后缀：`.py` → pytest；`.vue`/`.js` → Playwright | 后端改 → pytest；前端改 → Playwright；两者皆改 → 都跑 |
| T2 测试隔离重定向 | 测试用 `unlink()`/`os.remove` 且依赖其成功 | `tmp_path` + `monkeypatch.setattr(module, "_file_path", lambda: tmp_path/...)`；autouse fixture 重置模块级状态 |
| T3 环境制品识别 | grep 失败用例名命中已知 teardown 依赖删除的用例 | 报告标 `环境制品`，不计入代码失败；必要时 git stash 验证预存 |
| T4 重命名完整性验证 | grep 旧名非零匹配 | 全仓库 grep（backend/ + docs/）旧名 = 0 匹配；清理矛盾注释；审计日志保留 |
| T5 显式 Python 路径 | 改动在 `backend/`，测试命令用裸 `python` | 用 `backend/.venv/Scripts/python.exe -m pytest`（受管 venv，含 pytest 8.4.2） |
| T6 Playwright 唯一输出目录 | 启动时删除 `test-results` 被 safe-delete 拦截 | `--output=test-results-$(date +%s)` 唯一目录 |

## 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| T1 改动范围判定 | 有明确后端/前端改动的回归测试 | 跨端联动改动需两套都跑；纯文档改动无需测试 |
| T2 测试隔离重定向 | 依赖模块级文件路径/单例的测试（ai_budget、TTLCache、_build_info） | 纯内存单元测试（无文件系统依赖） |
| T3 环境制品识别 | safe-delete 拦截 teardown、`unlink` 残留类失败 | 真实逻辑失败（断言明确指向代码路径） |
| T4 重命名完整性验证 | 公共 API / 工具函数删除或重命名 | 局部变量重命名 |
| T5 显式 Python 路径 | 项目用受管 venv 且系统 Python 无 pytest | venv 激活后的 shell、Docker 单一环境 |
| T6 Playwright 唯一输出目录 | 启用 safe-delete 拦截删除的工作区 | 允许删除旧目录的环境 |

---

## Sequential Thinking 优化要点（news-auto-testing 落地）

> 以下为本次对 news-auto-testing 技能的优化，全部遵循"无硬编码、参数配置化、通用泛化"原则。

### 1. 测试范围配置化（backend_test 区块）
- 新增 `config.yaml#backend_test` 区块：显式 Python 路径、venv 路径、pytest 命令模板、测试目录、隔离策略开关。
- 技能不再写死 `python -m pytest`，全部从配置读取，适配不同项目的 venv / 解释器 / 测试框架（pytest / unittest / jest）。

### 2. 后端 pytest 作为一等公民阶段
- 新增"阶段 99：后端 pytest 执行"，与前端页面/API/性能阶段并列，按 `backend_test.enabled` 开关激活。
- 支持"仅后端"（`--scope=backend`）、"仅前端"（`--scope=frontend`）、"全量"（`--scope=all`）三种模式，覆盖 T1 范围判定。

### 3. 重命名/别名完整性验证阶段
- 新增"阶段 100：重命名完整性 grep 验证"，读取 `config.yaml#rename_verification.deprecated_names` 列表，全仓库 grep 0 匹配才算通过（落实 T4）。

### 4. 测试隔离加固阶段
- 新增"阶段 101：测试隔离加固（safe-delete 环境制品）"，自动检测依赖 `unlink` 的测试并建议 `tmp_path` + `monkeypatch` 重定向（落实 T2/T3）；把已知环境制品用例列入 `known_environment_artifacts` 白名单，报告中单独归类。

### 5. 通用性与泛化
- 所有页面清单、API 端点、账号、阈值、扫描目录、隔离策略均已在 `config.yaml` 50 个区块管理；本次新增 `backend_test` / `rename_verification` / `test_isolation` 三个区块，以及部署层/小程序合规专项 `frozen_config_load_test` / `installer_secret_completeness_test` / `miniprogram_playback_coldstart_test` / `wechat_privacy_scope_test` 四个区块，保持同一范式。
- 技能描述从"前端自动化测试"扩展为"前端 + 后端自动化测试"，明确后端改动走 pytest、前端改动走 Playwright 的双轨约定，适配不同业务场景（纯前端 SPA / 纯后端 API / 全栈）。

### 6. 部署层 / 小程序合规专项测试（阶段 102-105，对应 DS-11~DS-14）
- 新增四个 `config.yaml` 区块 + 对应阶段，覆盖"代码写完但部署/合规层仍会失败"的四类真实问题（frozen `.env` 加载失败、安装包 `.env` 被 `Excludes` 静默丢弃、HLS 首播冷启动、微信剪贴板隐私未声明）。
- 全部为静态 grep + 步骤验证型测试，阈值/反模式/扫描目录均配置化，未写死业务值；`trigger_on_files` 与 `signals` 可适配任意项目路径与框架。

---

## 维度 1-4 延展：部署层 / 小程序合规专项测试（阶段 102-105）

> 对应 news-code-dev 诊断标准 DS-11 / DS-12 / DS-13 / DS-14。沿用上文四维框架，沉淀本轮新增的四类测试。

### 维度 1（延展）：部署/合规专项测试的成功步骤
1. **界定受影响产物**：区分本轮改动触及"冻结 exe 配置加载"（backend config.py）、"安装包构建"（installer.iss / build 脚本）、"小程序音频播放"（miniprogram 音频层）、"小程序隐私接口"（miniprogram 敏感 API 调用）。
2. **选对应阶段**：102（frozen 配置）→ 103（安装包）→ 104（HLS 首播）→ 105（隐私 scope），按 `config.yaml` 各区块 `enabled` 激活。
3. **跑静态 grep + 步骤验证**：每个阶段先 grep 反模式（signals），再执行 `test_steps` 人工/自动核对，产出 `pass_criteria` 判定。
4. **归类报告**：命中的 FAIL/WARN 标注对应 DS 编号，与代码缺陷同步进报告。

### 维度 2（延展）：不确定性与失败点
| 失败点 | 触发条件 | 影响 | 根因 | 修复方式 |
|--------|----------|------|------|----------|
| frozen 模式读不到 .env | `env_file` 用 cwd 相对路径且无 `sys.frozen` 分支 | exe 启动 appid missing | 冻结 exe 的 cwd 非代码目录 | 回退 `sys.executable` 同级 `.env`（DS-11） |
| 安装包缺 .env | `installer.iss` `Excludes` 静默丢弃或无显式 `Source` | 打包后配置缺失，appid missing | 隐藏文件被打包器忽略 | 显式 `Source` 包含 + `attrib -H`（DS-12） |
| HLS 首播误判致命 | `onError` 直接 `showToast` 并停 loading | 首播冷启动被报失败 | HLS 连接建立慢/解码冷启动 | 静默重试 `MAX_HLS_RETRY` + mp3 回退（DS-13） |
| 剪贴板隐私 fail | 调 `setClipboardData` 未授权且后台未声明 scope | 真机 `api scope is not declared` | 后台 scope 名与代码不一致 | 调前 `requirePrivacyAuthorize` + 后台声明「剪贴板」（DS-14） |

### 维度 3（延展）：可抽象的固定流程与判断逻辑
| 模板 | 核心判断信号 | 落地方式 |
|------|--------------|----------|
| T7 frozen 配置回退 | grep `env_file=` 无 `getattr(sys, "frozen")` 分支 | 冻结模式回退 `sys.executable` 同级 `.env`；非冻结回退开发态路径 |
| T8 安装包配置完整 | grep `Excludes:.*\.env` / 无显式 `Source .env` / 无 `attrib -H` | 显式包含 + 去隐藏；隐藏文件不被漏打包 |
| T9 HLS 首播静默重试 | grep `onError` 直接 `showToast` 无 `MAX_HLS_RETRY`/`mp3Url` | 首播失败静默重试 + mp3 回退 + 连续 loading |
| T10 隐私 scope 声明 | grep `setClipboardData`/`getClipboardData` 无 `requirePrivacyAuthorize` 包裹 | 调前授权；后台声明「剪贴板」（读写共用） |

### 维度 4（延展）：适用场景与不适用场景
| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| T7 frozen 配置回退 | PyInstaller/Nuitka 冻结 exe 部署 | 纯源码运行（无 `sys.frozen` 分支需求） |
| T8 安装包配置完整 | 含 `.env`/密钥的安装包（Inno Setup 等） | 配置全环境变量注入、无 `.env` 文件 |
| T9 HLS 首播静默重试 | 小程序/H5 用 BackgroundAudioManager 播 HLS(m3u8) 流式音频 | 纯本地 mp3 直链、无流式协议协商 |
| T10 隐私 scope 声明 | 微信小程序调用隐私接口（剪贴板/位置/相册等） | 非微信平台、接口不在隐私清单内 |

---

## 维度 1-4 延展：段间静音/bgm_gap_mode 测试复盘（T11-T12）

> 对应 news-code-dev 诊断标准 DS-15 / DS-16。沿用上文四维框架，沉淀本轮段间静音做成可开关 `bgm_gap_mode` 的测试经验。所有参数仍通过 `config.yaml` 各区块（如 `backend_test` / `test_isolation`）管理，无硬编码新增。

### 维度 1（延展）：段间静音/bgm_gap_mode 测试的成功步骤
1. **界定媒体特性边界**：确认本轮改动是"媒体开关语义"（bgm_gap_mode silence/bridge）还是"纯逻辑参数"，前者须做真静音 ffmpeg 实证。
2. **后端校验器单测**：用受管 venv 跑 `backend/tests/test_channel_bgm_gap_mode.py`，覆盖 accept / normalize / empty→None / invalid-reject 四类语义（见 DS-16）。
3. **媒体实证验证**：用真实函数生成 gap/main 音频，确认 silence 模式静音段无 BGM、bridge 模式连续 BGM（物理产出物验证，排除陈旧残留冒充新产出，见 DS-7）。
4. **前端构建验证**：`vite build` 到独立输出目录（如 `dist_bgmcheck`）避开 safe-delete 对 `emptyDir` 的拦截。
5. **归类报告**：预存的 safe-delete 环境制品（如 `test_upload_avatar_success`）单独归类，不计入代码失败。

### 维度 2（延展）：不确定性与失败点
| 失败点 | 触发条件 | 影响 | 根因 | 修复方式 |
|--------|----------|------|------|----------|
| 校验器/测试语义错位 | 校验器空串抛 `ValueError` 但测试期望 `None` | 单测 3 失败 | 空串语义未约定为"继承全局" | 空串→`None` + 重写测试覆盖四类（DS-16） |
| 媒体"看似无效"误判 | 缺物理产出物验证 | 误修参数而非修崩溃/语义 | 默认 bridge 掩盖静音 | 真静音 `amix duration=first` + 实证（DS-15） |
| 前端构建清理被拦截 | `vite build` 的 `emptyDir` 批量删 `dist` | 本地构建验证受阻 | safe-delete FAIL CLOSED | 独立输出目录（如 `dist_bgmcheck`）绕过 |

### 维度 3（延展）：可抽象的固定流程与判断逻辑
| 模板 | 核心判断信号 | 落地方式 |
|------|--------------|----------|
| T11 校验器/测试语义对齐 | 校验器空串抛错 / 合法值未归一化 / 与测试断言矛盾 | DS-16：空串→`None`；去空格归一化；非法→`ValueError`；重写测试覆盖四类 |
| T12 媒体特性实证验证 | 媒体开关改动无物理产出物验证 | DS-15：真实生成音频确认 silence/bridge 真语义；排除陈旧残留 |

### 维度 4（延展）：适用场景与不适用场景
| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| T11 校验器/测试语义对齐 | 所有带枚举/开关的 Pydantic Body 字段（含频道级覆盖字段） | 纯无约束字符串、必填不可空字段 |
| T12 媒体特性实证验证 | 媒体处理有"看似不生效"历史的特性（静音/BGM/混音开关） | 非媒体纯逻辑特性、无物理产出物可查 |
