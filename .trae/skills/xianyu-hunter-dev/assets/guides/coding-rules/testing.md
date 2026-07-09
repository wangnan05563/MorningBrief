# Testing 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「testing」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 10：测试编写【强制】

10. **测试编写【强制】**
    - **后端**: 在 `tests/` 新增 `test_<被测模块>.py`，遵循 `asyncio_mode = "auto"`，命名 `test_<scenario>` 或 `test_<issue>_fix`
    - **前端**: 在组件/hook 同级目录新增 `__tests__/<Component>.test.tsx`
    - **Cookie 隔离**: 后端测试自动应用 `isolate_cookie_json` fixture（conftest.py）
    - **E2E**: 涉及全链路验证，参考 `tests/test_e2e.py` 用 Fake 依赖注入 Container
    - **覆盖率目标**: 关键业务模块 80%+，无测试不合并


---

### step 37：Windows 测试环境 Mock 模式【强制】🆕v4.4

37. **Windows 测试环境 Mock 模式【强制】🆕v4.4**
    - 测试代码中 Windows 环境变量（`LOCALAPPDATA`/`APPDATA`/`USERPROFILE`）必须用 `tmp_path` 正确 mock，路径结构需与实现一致
    - **判断信号**：测试涉及 Windows 文件系统路径 + 使用环境变量 + 实现依赖 `Path(LOCALAPPDATA)` 等构造路径
    - **修复模式**：`monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))` → 测试 fixture 创建 `tmp_path / "Microsoft" / "Edge" / "User Data"` 完整路径结构 → 与实现路径完全对齐
    - **配置参数**：测试 fixture 路径模板、环境变量映射在 `tests/conftest.py` 管理
    - **适用**：Windows 文件系统路径测试、浏览器 profile 发现测试、配置文件加载测试
    - **不适用**：Linux/Mac 路径测试、不涉及环境变量的路径测试、纯函数测试
    - **历史教训**：测试代码创建 `tmp_path / "Edge" / "User Data"` 但实现用 `Path(LOCALAPPDATA) / "Microsoft" / "Edge" / "User Data"`，路径结构不一致导致测试失败；调整测试 fixture 路径结构对齐实现后通过


---

### step 38：第三方插件依赖预检模式【强制】🆕v4.4

38. **第三方插件依赖预检模式【强制】🆕v4.4**
    - 使用 pytest 插件（如 `pytest-timeout`）前必须验证项目已安装，避免运行时报错；插件依赖列表需在 `pyproject.toml` 显式声明
    - **判断信号**：使用 pytest 命令行参数（如 `--timeout`）+ 依赖第三方插件 + 未在 `pyproject.toml` 声明
    - **修复模式**：`pyproject.toml` `[tool.pytest.ini_options]` 显式声明 `addopts` + `requirements-dev.txt` 列出插件依赖 → 运行前用 `pytest --version` + 插件检查脚本验证
    - **配置参数**：插件依赖列表在 `pyproject.toml` 管理，预检脚本在 `scripts/check-deps.ps1`
    - **适用**：所有 pytest 插件依赖（`pytest-timeout`/`pytest-cov`/`pytest-asyncio`）、 tox/nox 多环境测试
    - **不适用**：pytest 内置功能（无需预检）、CI 环境固定镜像（依赖明确）
    - **历史教训**：使用 `pytest --timeout=60` 报错 `unrecognized arguments`，项目未安装 `pytest-timeout` 插件；移除 `--timeout` 标志后通过，但应预检插件依赖

### 第三阶段：验证与交付

---

### step 53：过滤逻辑场景区分【强制】🆕v4.7

53. **过滤逻辑场景区分【强制】🆕v4.7**
    - 同一查询函数被多个场景复用时，过滤逻辑必须**参数化场景标志**（如 `include_failed` / `include_deleted` / `scope`），调用方按使用场景传值，**禁止**一刀切过滤导致展示页看不到完整数据
    - **判断信号**：函数命名含 `list_*` / `get_*` / `query_*` 且 grep 多个调用点 → 检查过滤逻辑是否硬编码（如 `if status == 'failed': continue`）→ 必须改为参数化
    - **修复模式**：
      ```python
      def list_orders_by_item_ids(
          self, item_ids: list[str], include_failed: bool = False
      ) -> dict[str, dict]:
          """批量查询多个商品的最新订单状态

          include_failed 控制是否包含 failed 订单：
          - False（默认）：跳过 failed 订单，用于「是否允许重新抢单」判断
          - True：保留 failed 订单，用于评估明细展示完整订单历史
          """
          if not item_ids:
              return {}
          result: dict[str, dict] = {}
          with self.engine.connect() as conn:
              stmt = (
                  select(OrderRow)
                  .where(OrderRow.item_id.in_(item_ids))
                  .order_by(OrderRow.created_at.desc())
              )
              for row in conn.execute(stmt).all():
                  order = self._row_to_dict(row)
                  iid = order.get("item_id")
                  if not iid or iid in result:
                      continue
                  if not include_failed and order.get("status") == "failed":
                      continue
                  result[iid] = order
          return result
      ```
    - **关键约束**：
      - 场景标志必须**默认安全**（`include_failed=False` 默认跳过失败，避免影响现有逻辑）
      - 函数 docstring 必须说明**两种场景**的用途（操作判断 vs 展示历史）
      - 调用方必须**显式传值**（如 `include_failed=True`），不依赖默认值
      - 必须新增**回归测试**覆盖两种场景（参考 `test_list_orders_by_item_ids_failed_filter`）
    - **配置参数**：`scenario_flag_field`（默认 `include_failed`）、`status_whitelist`（默认 `['succeeded', 'pending']`）、`multi_scene_callsites`（多场景调用点列表）在 `config.yaml` 的 `filter_scenario` 节点管理
    - **适用**：同一查询被"操作判断"与"展示历史"两种场景复用，尤其是订单/任务/日志类查询
    - **不适用**：单一场景的查询（如报表统计只看成功）、有独立 Repo 方法的查询、权限过滤（应单独抽取）
    - **历史教训**：`list_orders_by_item_ids` 无条件 `if status == 'failed': continue`，导致评估明细页看不到失败订单记录，用户点击抢单失败后刷新页面看到 "—"，误以为没下过单而反复触发抢单。修复后增加 `include_failed` 参数，评估明细调用传 `True`


---

### step 66：pytest 模块重复 import 隔离规范【强制】🆕v4.11

66. **pytest 模块重复 import 隔离规范【强制】🆕v4.11**
    - pytest 在 `sys.modules` 中可能以 `test_xxx`（无包前缀）和 `tests.test_xxx`（带包前缀）两种名字持有同一测试文件的不同模块对象，conftest.py patch 模块属性时**禁止**硬编码模块名列表，必须遍历 `sys.modules` 找所有持目标属性的模块全部 patch
    - **关键约束**：
      1. **禁止硬编码模块名列表**：如 `for name in ["cookie_rotator", "api_tasks"]: patch(sys.modules[name])` —— 一旦新增模块需手动同步列表，极易遗漏
      2. **必须遍历 sys.modules**：用 `hasattr(mod, TARGET_ATTR)` 动态识别所有持目标属性的模块，全部 patch
      3. **禁止用 `__import__`**：`__import__("a.b")` 返回顶层包 `a` 而非子模块 `a.b`，必须用 `importlib.import_module` 正确返回子模块
      4. **patch 后验证**：patch 完成后必须 `assert hasattr(mod, TARGET_ATTR)` 验证 patch 生效
    - **判断信号**：
      - conftest.py 含 `for name in [...]: monkeypatch.setattr(sys.modules[name], ...)` 硬编码列表 → 视为违规
      - 测试用例 `import tests.test_xxx` 后修改模块属性，但被测代码 `from test_xxx import YYY` 读取的是另一份模块对象 → 典型症状
      - 代码含 `__import__("a.b")` 且后续操作期望得到子模块 → 视为违规
    - **修复模式**：
      ```python
      # ✅ 正确：遍历 sys.modules 找所有持目标属性的模块
      import sys
      TARGET_ATTR = "_COOKIE_JSON"

      def patch_all_modules_with_cookie(tmp_path):
          patched = []
          for mod in sys.modules.values():
              if mod is None:
                  continue
              if hasattr(mod, TARGET_ATTR):
                  # patch 到 tmp_path 隔离生产数据
                  setattr(mod, TARGET_ATTR, str(tmp_path / "cookies.json"))
                  patched.append(mod.__name__)
          assert patched, f"未找到持 {TARGET_ATTR} 属性的模块"
          return patched

      # ✅ 正确：importlib.import_module 替代 __import__
      import importlib
      mod = importlib.import_module("xianyu_hunter.modules.cookie_rotator")

      # ❌ 错误：硬编码模块名列表
      for name in ["cookie_rotator", "api_tasks", "auth_middleware"]:
          monkeypatch.setattr(sys.modules[name], "_COOKIE_JSON", ...)

      # ❌ 错误：__import__ 返回顶层包
      mod = __import__("xianyu_hunter.modules.cookie_rotator")  # 返回 xianyu_hunter 而非 cookie_rotator
      ```
    - **配置参数**：`pytest_isolation.target_attr_pattern`（默认 `_COOKIE_JSON`，支持正则）、`pytest_isolation.module_name_prefixes`（默认 `[]` 表示全扫，可选限制如 `["xianyu_hunter", "tests"]`）、`pytest_isolation.use_importlib`（默认 `true`，强制使用 `importlib.import_module`）在 `config.yaml` 的 `pytest_isolation` 节点管理
    - **适用**：pytest conftest.py 全局 fixture patch 模块属性；多模块共享同一配置文件路径的场景；任何需要 patch 跨模块共享状态的测试
    - **不适用**：单模块测试（直接 monkeypatch 即可）；非 pytest 测试框架；patch 对象属性（非模块属性）
    - **历史教训**：`conftest.py` 硬编码 `[cookie_rotator]` 列表 patch `_COOKIE_JSON`，但 pytest 以 `test_cookie_rotator` 和 `tests.test_cookie_rotator` 两种名字持有同一文件的两个模块对象，patch 只命中其中一个，导致生产 `data/cookies.json` 被测试数据污染。修复后改为遍历 `sys.modules` 找所有持 `_COOKIE_JSON` 属性的模块全部 patch


---

### step 68：测试 fixture 生产隔离与数据污染应急规范【强制】🆕v4.11

68. **测试 fixture 生产隔离与数据污染应急规范【强制】🆕v4.11**
    - conftest.py 必须 patch 生产路径（如 `data/cookies.json`、`*.db`）到 `tmp_path`，fixture 数据需带可识别特征（如 `test_fixture_` 前缀），数据污染应急必须按 5 步流程执行
    - **关键约束**：
      1. **生产路径 patch**：所有 fixture 必须用 `tmp_path` 隔离生产路径，**禁止**直接读写生产文件（如 `data/cookies.json`）
      2. **fixture 数据可识别特征**：测试数据必须带前缀/后缀（如 `test_fixture_user_`、`__test__cookie`），便于污染后定位
      3. **数据污染应急 5 步流程**：
         - **步骤 1 停止服务**：立即停止所有可能读写污染文件的服务（避免污染扩散）
         - **步骤 2 删除污染文件**：删除被测试数据污染的生产文件（如 `data/cookies.json`）
         - **步骤 3 修复 conftest**：修复 conftest.py 隔离逻辑（参考 step 66 遍历 sys.modules patch）
         - **步骤 4 重跑测试**：重跑全部测试验证修复有效（`pytest` 全绿）
         - **步骤 5 通知用户**：明确告知用户哪些文件被污染、已删除、需重新初始化
      4. **patch 验证**：fixture 加载后必须 `assert not os.path.exists(production_path)` 验证生产路径未被写入
      5. **fixture 作用域**：跨测试共享的 fixture 用 `scope="session"`，单测试用 `scope="function"`，**禁止**用模块级全局变量持有测试数据
    - **判断信号**：
      - conftest.py 含 `open("data/cookies.json", "w")` 直接写生产路径 → 视为违规
      - 测试数据无前缀/后缀特征（如 `user_id = "abc123"` 而非 `user_id = "test_fixture_abc123"`）→ 视为违规
      - 生产文件含测试数据（如 `data/cookies.json` 含 `test_fixture_` 前缀的 cookie）→ 典型污染症状
    - **修复模式**：
      ```python
      # ✅ 正确：tmp_path 隔离 + 可识别特征 + patch 验证
      @pytest.fixture(scope="session")
      def isolated_cookie_path(tmp_path_factory):
          cookie_path = tmp_path_factory.mktemp("data") / "cookies.json"
          # 写入带 test_fixture_ 前缀的测试数据
          cookie_path.write_text('{"token": "test_fixture_token_xxx"}')
          # patch 所有持 _COOKIE_JSON 属性的模块
          patched = []
          for mod in sys.modules.values():
              if mod is not None and hasattr(mod, "_COOKIE_JSON"):
                  setattr(mod, "_COOKIE_JSON", str(cookie_path))
                  patched.append(mod.__name__)
          assert patched, "未找到持 _COOKIE_JSON 属性的模块"
          return cookie_path

      # 数据污染应急流程（按 config.yaml 的 test_isolation.pollution_recovery_steps 执行）
      # 1. 停止服务：xianyu-automation-startserver stop
      # 2. 删除污染文件：rm data/cookies.json
      # 3. 修复 conftest：参考 step 66 遍历 sys.modules patch
      # 4. 重跑测试：pytest
      # 5. 通知用户：告知污染文件清单
      ```
    - **配置参数**：`test_isolation.production_path_patterns`（默认 `["data/cookies.json", "data/*.db", "data/*.json"]`）、`test_isolation.test_data_markers`（默认 `["test_fixture_", "__test__"]`）、`test_isolation.pollution_recovery_steps`（默认 5 步流程列表）、`test_isolation.fixture_scope_default`（默认 `function`）、`test_isolation.assert_no_production_write`（默认 `true`，加载 fixture 后断言生产路径未写入）在 `config.yaml` 的 `test_isolation` 节点管理
    - **适用**：所有 pytest fixture 涉及文件 IO 的场景；conftest.py 全局 fixture；CI/CD 测试环境
    - **不适用**：纯内存测试（无文件 IO）；mock 替代真实文件的测试；一次性脚本测试
    - **历史教训**：`conftest.py` 未隔离 `data/cookies.json`，测试用例直接写入生产文件，导致生产 cookie 被测试数据污染（含 `test_fixture_` 前缀的 token）。应急流程：停止服务 → 删除 `data/cookies.json` → 修复 conftest 遍历 sys.modules patch → 重跑 pytest 全绿 → 通知用户重新初始化 cookie


---

### step 128：测试 mock 同步规范（test mock synchronization）【强制】🆕v4.27

**背景**：修改接口前置条件（如新增 cookie 完整性预检）后，原测试未同步更新 mock，导致测试失败或测试通过但实际逻辑错误。

**问题**：`_collect_detail_only` 新增 `_check_detail_cookie_completeness` 预检后，原测试 `test_detail_only_collection_preserves_old_title_and_syncs_display` 未 mock `container.browser.get_cookies`，预检读不到 cookie 抛 401，测试失败。

**规范**：

1. **修改前置条件时同步更新测试 mock【强制】**：接口新增前置检查（如 cookie 完整性、token 有效性、配置加载）时，必须同步更新测试 mock 让前置检查通过：

   ```python
   # 修改前：原测试 mock
   container = MagicMock()
   container.collector.detail = AsyncMock(return_value=detail)

   # 修改后：新增 cookie 预检，需 mock browser.get_cookies
   container.browser.get_cookies = AsyncMock(return_value=[
       {"name": n, "value": "v"} for n in [
           "cookie2", "sgcookie", "unb", "_m_h5_tk",
           "cna", "tracknick", "_tb_token_", "t", "tfstk",
           "xlly_s", "_samesite_flag_", "KLNotice",
       ]
   ])
   ```

2. **mock 数据必须覆盖完整字段集【强制】**：mock 数据必须覆盖前置检查的所有关键字段（如 cookie 预检的 identity + session 双类 cookie），避免单类 mock 导致预检通过但实际逻辑错误。

3. **测试失败时优先检查前置条件变更【强制】**：测试失败时优先检查是否是前置条件变更导致（如新增预检、新增参数、新增依赖），而非测试逻辑本身错误。

4. **mock 数据集中管理【强制】**：测试 mock 数据集中的常量（如完整 cookie 集清单）应提取为测试模块级常量，避免散落多个测试函数：

   ```python
   # test_collection_service.py 模块级
   _COMPLETE_COOKIE_MOCK = [
       {"name": n, "value": "v"} for n in [
           "cookie2", "sgcookie", "unb", "_m_h5_tk",
           "cna", "tracknick", "_tb_token_", "t", "tfstk",
       ]
   ]

   # 测试函数复用
   container.browser.get_cookies = AsyncMock(return_value=_COMPLETE_COOKIE_MOCK)
   ```

**配置驱动**：mock 数据清单、前置条件检查项、测试失败排查步骤等参数在 `config.yaml` 的 `test_mock_synchronization` 节点管理，包含 `complete_mock_data` / `precheck_fields` / `failure_debug_steps` 等，不硬编码在技能中。

**适用场景**：
- 接口新增前置检查（cookie/token/config 完整性）
- 接口新增依赖（如新增 browser.get_cookies 调用）
- 接口签名变更（新增参数）
- mock 数据需覆盖多类字段的场景

**不适用场景**：
- 纯函数测试（无外部依赖）
- 已有完整 mock 的接口（无需新增）
- 一次性脚本测试（无长期维护需求）

**历史教训**：`_collect_detail_only` 新增 cookie 完整性预检后，原测试 `test_detail_only_collection_preserves_old_title_and_syncs_display` 未 mock `container.browser.get_cookies`，预检读不到 cookie 抛 401，测试失败。修复后添加 12 个 cookie 的 mock 数据（覆盖 identity + session 双类），测试通过。

**判断信号（review 触发条件）**：
- 接口新增前置检查但测试未更新 mock
- 测试失败原因是 `AttributeError: 'MagicMock' object has no attribute '<new_method>'`
- mock 数据只覆盖单类字段（如只有 identity cookie 无 session cookie）
- 测试 mock 数据散落多个函数而非集中常量


---

### step 133：Windows 终端编码与 Shell 语法兼容规范【强制】🆕v4.29

**背景**：项目部署在 Windows 环境，默认终端 PowerShell 存在编码（cp936/gbk）和 shell 语法（`&&` 不支持/`stash@{0}` 哈希表解析）差异，导致脚本调用 API 时中文乱码、git 操作失败、命令拼接报错。

**问题**：
1. PowerShell 默认编码 cp936/gbk，外部脚本批量调用 `POST /api/chatbot/faq` 时中文 body 被转换为 `?`，导致数据库存储乱码（如「你好」变成 `??`）
2. PowerShell 不支持 `&&` 语法（如 `cd dir && npm run build` 报错），需用 `;` 或分步执行
3. `git stash@{0}` 在 PowerShell 中被解析为哈希表语法，需加引号 `'stash@{0}'`
4. PowerShell 输出重定向默认编码与 Python `print` 中文编码不一致，导致日志文件乱码

**规范**：

1. **PowerShell 编码设置【强制】**：脚本启动时必须显式设置 UTF-8 编码，**禁止**依赖默认 cp936/gbk：
   ```powershell
   # ✅ 正确：脚本开头设置 UTF-8 编码
   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   $OutputEncoding = [System.Text.Encoding]::UTF8
   chcp 65001 > $null  # 设置控制台代码页为 UTF-8

   # 调用 API 时显式设置 Content-Type 和 body 编码
   $body = @{ question = "你好"; answer = "世界" } | ConvertTo-Json -Depth 10
   $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/chatbot/faq" -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes

   # ❌ 错误：依赖默认编码，中文变 ?
   # Invoke-RestMethod -Uri "..." -Method Post -Body ($body | ConvertTo-Json)  # 中文被 cp936 编码为 ?
   ```

2. **PowerShell 语法兼容【强制】**：命令拼接必须用 `;` 而非 `&&`，含特殊字符的参数必须加引号：
   ```powershell
   # ✅ 正确：用 ; 分隔命令
   cd frontend; npm run build

   # ✅ 正确：stash@{0} 加引号避免哈希表解析
   git stash apply 'stash@{0}'

   # ❌ 错误：用 && 分隔命令（PowerShell 不支持）
   # cd frontend && npm run build  # 报错：The token '&&' is not a valid statement separator

   # ❌ 错误：stash@{0} 不加引号
   # git stash apply stash@{0}  # 报错：解析为哈希表
   ```

3. **Python 脚本输出编码【强制】**：Python 脚本在 Windows 环境必须显式设置 stdout 编码：
   ```python
   # ✅ 正确：脚本开头设置 stdout 编码
   import sys
   sys.stdout.reconfigure(encoding='utf-8')  # Python 3.7+
   # 或用环境变量 PYTHONIOENCODING=utf-8

   # ❌ 错误：依赖默认编码，print 中文到日志文件乱码
   # print("处理完成")  # 日志文件可能是 cp936 编码
   ```

4. **跨平台脚本兼容【强制】**：脚本必须同时支持 Windows 和 Linux，用条件判断而非硬编码路径分隔符：
   ```python
   # ✅ 正确：用 pathlib 跨平台
   from pathlib import Path
   log_path = Path("logs") / "startup.log"

   # ✅ 正确：用 os.path 跨平台
   import os
   log_path = os.path.join("logs", "startup.log")

   # ❌ 错误：硬编码路径分隔符
   # log_path = "logs\\startup.log"  # Linux 不兼容
   ```

**配置驱动**：编码设置、shell 语法兼容规则、跨平台路径处理等参数在 `config.yaml` 的 `cross_platform` 节点管理，包含 `encoding` / `shell_quoting` / `path_separator` / `command_separator` 等，不硬编码在技能中。

**适用场景**：
- Windows PowerShell 脚本调用 API（含中文 body）
- Python 脚本在 Windows 环境输出中文到日志
- git 操作（stash/branch 等含特殊字符的参数）
- 跨平台部署的脚本（Windows + Linux）

**不适用场景**：
- Linux/Mac 环境的 shell 脚本（默认 UTF-8）
- Docker 容器内脚本（容器内默认 UTF-8）
- 纯英文内容的脚本（无编码问题）

**历史教训**：
- 外部脚本批量调用 `POST /api/chatbot/faq` 时 PowerShell 默认 cp936 编码，中文 body 被转换为 `?`，导致数据库存储 3 条乱码记录（id=1/2/3），需手动删除。修复：脚本显式设置 UTF-8 编码 + body 用字节数组传递
- `git stash apply stash@{0}` 在 PowerShell 中报错「解析为哈希表」，修复：加引号 `'stash@{0}'`
- `cd frontend && npm run build` 报错「`&&` 不是有效的语句分隔符」，修复：改用 `;`

**判断信号（review 触发条件）**：
- `grep "cp936\|gbk" <file>` 出现编码硬编码 → 视为可疑
- `grep "&&" <ps1_file>` PowerShell 脚本含 `&&` → 视为违规
- `grep "stash@" <ps1_file>` 不加引号的 stash@{N} → 视为违规
- 数据库存储中文为 `?` → 编码问题可疑
- 日志文件中文乱码 → 编码问题可疑


---

### step 167：MOCK-01 测试 Mock 数据集中管理与字段完整性规范【强制】🆕v4.29

**背景**：测试 mock 数据散落在多个测试函数内部，修改前置条件（如 cookie 完整字段集）时需逐函数修改，漏改即导致测试通过但实际运行失败；mock 数据字段不完整，缺少关键字段（如 `domain`/`path`/`expires`）导致测试无法覆盖真实场景。

**问题**：mock 数据散落多处时，前置条件变更需逐处修改，漏改即测试与实际脱节；mock 字段不完整导致测试「绿但不可信」，掩盖真实 bug。

**规范**：

1. **mock 数据集中为模块级常量【强制】**：测试 mock 数据必须集中为测试模块级常量（`MOCK_COOKIE_FULL` / `MOCK_TASK_COMPLETE`），禁止散落在各测试函数内部：
   ```python
   # ✅ 正确：集中常量，复用 + 易维护
   MOCK_COOKIE_FULL = {
       "name": "_m_h5_tk", "value": "abc123", "domain": ".taobao.com",
       "path": "/", "expires": 1893456000, "secure": True, "httponly": False,
   }

   def test_cookie_layer_sync():
       result = sync_layer(MOCK_COOKIE_FULL)
       assert result.is_valid

   # ❌ 错误：散落函数内部，字段不完整
   # def test_cookie_layer_sync():
   #     cookie = {"name": "_m_h5_tk", "value": "abc123"}  # 缺 domain/path/expires
   #     result = sync_layer(cookie)
   ```

2. **mock 字段必须覆盖完整字段集【强制】**：mock 数据必须覆盖被测对象的完整字段集（参照 ORM 模型 / Pydantic model / TS interface），禁止用部分字段 mock 测全字段逻辑。

3. **前置条件变更必须同步更新 mock【强制】**：修改前置条件（如新增字段/变更字段类型/变更校验规则）时必须同步更新所有相关 mock 常量，并通过 grep 验证无遗漏。

4. **测试失败优先检查前置条件变更【强制】**：测试失败时必须优先检查前置条件是否变更（grep 最近的 schema/model 变更），而非优先怀疑测试本身逻辑错误。

**配置驱动**：`coding_standards.test_mock.centralize`（`true`）、`required_full_fields`（`true`）、`sync_on_precondition_change`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 单元测试 mock 数据（cookie/task/order 等）
- 集成测试 fixture 数据
- mock 数据需随前置条件变更而更新

**不适用场景**：
- 一次性测试数据（仅单个测试用，无需复用）
- 随机生成的测试数据（用 factory 模式）
- 第三方库的 mock（由库提供）

**历史教训**：cookie 同步测试的 mock 数据散落在 5 个测试函数中，新增 `domain`/`path`/`expires` 字段为必填后，仅更新了 2 个函数的 mock，其余 3 个测试通过但实际运行时因字段缺失失败。修复后提取 `MOCK_COOKIE_FULL` 常量，5 处复用。

**判断信号（review 触发条件）**：
- `grep "def test_" <test_file>` 函数内部含 mock 数据字面量
- mock 数据字段数 < ORM 模型字段数
- 测试通过但实际运行失败（mock 与实际脱节）
- 前置条件变更后未 grep 更新 mock


---

### step 192：mock 同步与边界精确性规范【强制，meta-rule #55 落地】🆕v4.37

192. **mock 同步与边界精确性规范【强制，meta-rule #55 落地】🆕v4.37**
    - 修改被测代码后必须同步更新 mock：mock 类型与被 mock 对象的同步/异步特性必须一致，patch 必须 patch **实际调用点**而非定义点，mock 数据必须覆盖完整字段集，测试必须断言"副作用未发生"
    - **与 step 128 测试 mock 同步规范的边界**：
      - step 128 关注"接口新增前置检查时同步更新 mock 数据"
      - 本规范关注"mock 类型/patch 路径/字段完整性/副作用断言"的精确性
    - **类型匹配矩阵**：
      | 被 mock 函数签名 | 正确 mock 类型 | 错误 mock 类型 | 症状 |
      |------------------|----------------|----------------|------|
      | `def f(): ...` | `MagicMock` | `AsyncMock` | `await` 在同步对象上失败 |
      | `async def f(): ...` | `AsyncMock` | `MagicMock` | `coroutine never awaited` |
      | `@property` | `PropertyMock` | `MagicMock` | 属性访问返回 mock 对象本身 |
    - **patch 边界**：必须 patch **实际调用点**（如 `worker.get_secret`）而非定义点（如 `secrets.get_secret`），因为 Python 的 `from x import f` 会在导入时绑定引用
      ```python
      # ❌ 错误：patch 定义点，但 worker.py 已 from secrets import get_secret
      patch("xianyu_hunter.modules.secrets.get_secret", return_value=None)

      # ✅ 正确：patch 实际调用点
      patch("xianyu_hunter.modules.worker.get_secret", return_value=None)
      ```
    - **字段完整性**：mock 数据必须覆盖被测代码访问的所有字段，禁止部分 mock，否则测试通过但运行时 NPE
    - **副作用断言**：测试必须断言"副作用未发生"
      ```python
      # ✅ 正确：断言未发起真实网络请求
      mock_post.assert_not_called()

      # ✅ 正确：断言未写文件
      assert not Path("data/cookies.json").exists()
      ```
    - **判断信号**：
      - `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数（无 `async def`）→ 违规
      - `grep "MagicMock" <test_file>` 但被 mock 函数是 `async def` → 违规
      - `patch("module.function")` 但实际调用是 `from module import function; function()` → patch 边界错误
      - mock 数据字段数 < 被测代码访问的字段数 → 不完整
      - 测试未断言副作用未发生（如未 `assert_not_called()`）→ 不完整
    - **修复模式**：
      ```python
      # ✅ 正确：类型匹配 + patch 调用点 + 完整字段 + 副作用断言
      def test_dingtalk_notify_skipped_when_secret_empty(monkeypatch):
          # worker.py 的 filter_new 是同步函数 → 用 MagicMock
          monkeypatch.setattr(worker, "filter_new", MagicMock(return_value=[]))
          # patch 调用点 worker.get_secret 而非定义点 secrets.get_secret
          monkeypatch.setattr(worker, "get_secret", lambda k: None)
          # mock 完整字段（覆盖 notifier 访问的所有字段）
          mock_notifier = MagicMock()
          mock_notifier.enabled = False
          mock_notifier.webhook_url = ""
          mock_notifier.secret = ""
          # 副作用断言：未发起真实钉钉请求
          mock_post = MagicMock()
          monkeypatch.setattr("xianyu_hunter.modules.notifier.requests.post", mock_post)

          result = run_notify_flow()

          assert result.skipped is True
          mock_post.assert_not_called()  # 副作用断言

      # ❌ 错误：AsyncMock 用于同步函数
      # monkeypatch.setattr(worker, "filter_new", AsyncMock(return_value=[]))  # 同步函数

      # ❌ 错误：patch 定义点
      # monkeypatch.setattr("xianyu_hunter.modules.secrets.get_secret", lambda k: None)
      ```
    - **配置参数**：`mock_sync.type_check`（默认 `true`，启用类型匹配检查）、`mock_sync.required_fields_check`（默认 `true`，启用字段完整性检查）、`mock_sync.side_effect_assert`（默认 `true`，强制副作用断言）、`mock_sync.patch_boundary_strict`（默认 `true`，patch 必须命中调用点）、`mock_sync.exemption_list`（豁免列表，如快照测试）在 `config.yaml` 的 `mock_sync` 节点管理
    - **适用**：所有 unit test / 集成测试中的 mock 替身
    - **不适用**：E2E 测试（应使用真实环境）、快照测试（snapshot test）
    - **历史教训**：`test_dingtalk_notify_integration.py` 用 `AsyncMock` 但 `worker.py` 的 `filter_new` 已改为同步实现，导致 `await` 在同步对象上失败。`test_notifier_new_channels.py` patch `get_secret` 位置错误导致 webhook_url/secret 实际不为空，测试发起真实钉钉请求。修复：AsyncMock 改 MagicMock 对齐同步实现 / patch get_secret 返回 None 确保真正为空 / test_manual_takeover_lock 构造 mock request 含 user_id


---

