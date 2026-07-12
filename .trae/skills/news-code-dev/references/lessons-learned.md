# 经验教训与编码规范

本文档从 20_News 项目实际开发中遇到的问题提炼而成，每条规范均来源于真实踩坑案例。用于补充 [meta-rules.md](meta-rules.md) 的 20 条基础规范，编号从 21 开始。

## 四维度复盘总览

### 维度 1：成功执行任务的完整步骤

适用于所有功能开发与缺陷修复任务的标准流程：

1. **需求分析** → 明确可验证目标，将模糊指令转化为具体验收标准
2. **方案设计** → 评估技术方案，识别潜在风险点
3. **编码实现** → 按分层架构（routers → services → models → core）实现
4. **语法验证** → `py_compile` 检查 Python 语法 + `npm run build` 检查前端构建
5. **导入验证** → 实际运行 `from app.main import app` 验证模块导入（语法通过 ≠ 导入通过）
6. **数据库迁移** → ORM 模型变更必须配套 ALTER TABLE / CREATE TABLE 脚本
7. **服务启动** → 启动服务并观察启动日志是否有异常
8. **健康检查** → GET /api/health 验证服务可用性
9. **路由注册验证** → 新增端点返回 401（已注册）而非 404（未注册）
10. **API 测试** → 覆盖所有新增端点，验证 HTTP 状态码 + 业务 code
11. **页面遍历** → 导航每个页面，检查控制台 error + 预期文本匹配
12. **登录流程验证** → Token 获取 + URL 跳转 + 用户信息显示
13. **性能审计** → Lighthouse 审计 Accessibility/Best Practices/SEO
14. **问题分类** → code_defect / business_data / framework_behavior / environment
15. **修复 → 回归测试** → 修复后 ignoreCache 强制刷新重新验证
16. **报告生成** → 汇总结果，按问题分类记录修复方案

**关键教训**：步骤 4（语法验证）不能替代步骤 5（导入验证）；步骤 6（数据库迁移）必须与 ORM 模型变更同步；步骤 9（路由注册验证）是发现导入错误的最快方式。

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 导入不存在的函数 | `from app.core.response import fail` 但 response.py 只导出 `success/error` | 服务启动失败 ImportError | 仅做 py_compile 未做运行时导入测试 | 新增模块必须运行时导入验证 |
| ORM 模型变更未迁移 | 新增 `channel_id` 列但未执行 ALTER TABLE | 查询报 OperationalError: no such column | 迁移脚本与模型变更不同步 | 模型变更必须配套迁移脚本 |
| SPA 路由用 location.href | `location.href = '/login'` 导致全量刷新 | 最小化窗口被激活弹出 | 误用浏览器导航替代 SPA 路由 | 强制用 `router.push('/login')` |
| TTLCache 重启丢失 | 工作流 ID 依赖内存计数器，重启后从 0 开始 | workflow_id 重复，数据库完整性错误 | 内存缓存无持久化 | DB 当日最大序号校验补充 |
| 外部依赖缺失 | ffmpeg/ffprobe 未安装 | TTS 后处理 WinError 2 文件未找到 | 环境预检缺失 | 启动时检查依赖并提示安装 |
| 模块导出不完整 | `NotificationEvent` 未在 `__init__.py` 导出 | ImportError 无法导入 | `__init__.py` 遗漏导出 | 新增类必须同步更新 `__init__.py` |
| 文件编辑损坏 | Edit 工具修改变量名时截断（如 `reesponse`、`Mesror`） | 代码运行时崩溃 | 编辑后未做语法校验 | 编辑后必须 py_compile + 关键片段 diff |
| 框架预期 error 误判 | Element Plus MessageBox cancel 抛 error | 测试误判为代码缺陷 | 未建立 error 白名单 | 配置 console_error_whitelist |
| MCP 截图相对路径 | 截图路径相对于 MCP 工具 cwd 而非项目目录 | 截图保存到错误位置 | MCP 工具 cwd 与项目不同 | 强制使用绝对路径 |
| PowerShell curl 转义 | `curl.exe -d '{"key":"value"}'` JSON 解析失败 | API 测试无法发送 POST 请求 | PowerShell 双引号转义与 curl 不兼容 | 改用 `Invoke-RestMethod` |
| 并发 ID 生成冲突 | 多请求同时生成 workflow_id | 数据库唯一约束冲突 | TTLCache 计数器非原子 | asyncio.Lock 串行化入队 + DB 序号校验 |
| COS 未配置仍上传 | bucket 为占位符值时仍调用 COS API | 上传失败 'bucket format is illegal' | 缺少配置验证 | 配置检查 + 本地存储降级 |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 核心判断信号 | 落地方式 |
|------|--------------|----------|
| SPA 路由强制 router.push | grep `location\.href\s*=\s*['"]/login` | 替换为 `router.push('/login')` |
| 配置存储 DB 权威源 | grep 内存计数器无 DB 校验 | DB 查询当日最大序号补充缓存 |
| 外部服务降级 fallback | grep 外部 API 调用无配置检查 | 添加 `is_configured()` 检查 + 本地降级 |
| 模块导入完整性 | grep `__init__.py` 的 `__all__` 列表 | 新增类必须同步导出 |
| 文件编辑安全校验 | Edit 后 py_compile + grep 关键变量名 | 编辑后必须语法校验 |
| 框架 error 白名单 | 测试日志中 error 匹配白名单子串 | 配置 `console_error_whitelist` |
| MCP 绝对路径 | 截图/快照路径不以盘符开头 | 强制 `use_absolute_path: true` |
| PowerShell HTTP 请求 | grep `curl.exe -d` 在 PowerShell 脚本 | 替换为 `Invoke-RestMethod` |
| 并发入队串行化 | grep 入队操作无 asyncio.Lock | 添加 `async with self._trigger_lock` |
| COS 配置验证 | grep COS 上传无 `is_cos_configured()` | 添加配置检查 + 本地降级 |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| SPA 路由 router.push | Vue/React/Angular SPA 应用 | 多页应用（MPA）、SSR 首屏 |
| 配置存储 DB 权威源 | 需要重启恢复的 ID 生成器、计数器 | 纯缓存场景（丢失可接受） |
| 外部服务降级 fallback | COS/OSS/S3 上传、第三方 API 调用 | 核心业务逻辑（不可降级） |
| 模块导入完整性 | Python 包的 `__init__.py` | 单文件脚本、无需包导出 |
| 文件编辑安全校验 | 使用 Edit 工具修改代码后 | 全新文件（Write 工具） |
| 框架 error 白名单 | UI 组件库（Element Plus/Ant Design） | 自定义 error（需修复） |
| MCP 绝对路径 | MCP 工具截图/快照/文件操作 | 项目内相对路径操作 |
| PowerShell HTTP 请求 | Windows PowerShell 环境 | Linux/Mac shell 环境 |
| 并发入队串行化 | asyncio.PriorityQueue 入队操作 | 单线程无并发场景 |
| COS 配置验证 | 云存储上传场景 | 本地文件操作 |

---

## 规范 21：SPA 路由强制 router.push

**SPA 应用中所有页面跳转必须使用 router.push，禁止使用 location.href。**

- 适用：Vue/React/Angular 等 SPA 应用
- 不适用：多页应用（MPA）、SSR 首屏跳转
- 判断信号：grep 搜索 `location\.href\s*=\s*['"]/` 在前端代码中
- 正确做法：
  ```javascript
  // ✅ 正确：SPA 路由跳转
  import router from '../router'
  router.push('/login')
  
  // ❌ 错误：全量刷新激活窗口
  location.href = '/login'
  ```
- 真实案例：最小化浏览器窗口因 location.href 全量刷新被激活弹出，改为 router.push 后窗口保持最小化

## 规范 22：配置存储 DB 权威源

**需要重启恢复的状态（ID 生成器、计数器）必须以 DB 为权威源，内存缓存仅作补充。**

- 适用：workflow_id 生成、序号计数器、分布式 ID
- 不适用：纯缓存数据（丢失可接受）、临时计算结果
- 判断信号：grep 搜索内存计数器（如 `TTLCache` / `self._counter`）无 DB 校验
- 正确做法：
  ```python
  # ✅ 正确：DB 当日最大序号校验补充缓存
  def _get_next_seq(self, date_str: str) -> int:
      cache_seq = self._cache.get(f"seq:{date_str}", 0)
      db_max_seq = self._get_db_max_seq(date_str)  # DB 权威源
      seq = max(cache_seq, db_max_seq + 1)
      self._cache.set(f"seq:{date_str}", seq)
      return seq
  
  # ❌ 错误：纯内存计数器重启后丢失
  def _get_next_seq(self, date_str: str) -> int:
      seq = self._cache.get(f"seq:{date_str}", 0) + 1  # 重启后从 0 开始
      self._cache.set(f"seq:{date_str}", seq)
      return seq
  ```
- 真实案例：TTLCache 重启后 workflow_id 从 0001 开始，与 DB 已有记录冲突导致 IntegrityError

## 规范 23：外部服务降级 fallback

**调用外部服务（COS/OSS/S3/第三方 API）前必须检查配置有效性，未配置时降级到本地方案。**

- 适用：云存储上传、第三方 API 调用、外部依赖服务
- 不适用：核心业务逻辑（不可降级，应直接报错）
- 判断信号：grep 搜索外部服务调用无配置检查
- 正确做法：
  ```python
  # ✅ 正确：配置检查 + 本地降级
  def is_cos_configured() -> bool:
      return (settings.COS_BUCKET 
              and settings.COS_BUCKET != "<your-bucket>"
              and settings.COS_SECRET_ID 
              and settings.COS_SECRET_ID != "<your-secret-id>")
  
  if is_cos_configured():
      url = await cos_client.upload(file)
  else:
      # 降级到本地存储
      local_path = save_to_local(file)
      url = f"/audio/{filename}"
  
  # ❌ 错误：未检查配置直接调用
  url = await cos_client.upload(file)  # bucket 为占位符时报错
  ```
- 真实案例：COS bucket 为占位符值时上传报 'bucket format is illegal'，降级到本地 /audio/ 静态服务

## 规范 24：模块导入完整性验证

**新增模块必须通过运行时导入验证（`from app.main import app`），py_compile 语法通过不等于导入通过。**

- 适用：所有新增 Python 模块、修改 `__init__.py` 导出
- 不适用：纯脚本文件（不参与包导入）
- 判断信号：新增 `.py` 文件后仅运行 `py_compile` 未运行导入测试
- 正确做法：
  ```bash
  # ✅ 正确：语法检查 + 导入验证
  python -m py_compile new_module.py        # 语法检查
  python -c "from app.main import app; print('OK')"  # 导入验证
  
  # ❌ 错误：仅语法检查
  python -m py_compile new_module.py  # 通过但可能导入失败
  ```
- 常见导入失败原因：
  - 导入不存在的函数（如 `from app.core.response import fail` 但 response.py 只有 `error`）
  - `__init__.py` 遗漏导出（如 `NotificationEvent` 未在 `__init__.py` 导出）
  - 循环导入（A import B，B import A）
- 真实案例：queue.py 导入 `fail` 函数（response.py 只有 `error`），py_compile 通过但服务启动 ImportError

## 规范 25：ORM 模型变更配套迁移脚本

**ORM 模型新增/修改字段必须同步编写数据库迁移脚本（ALTER TABLE / CREATE TABLE）。**

- 适用：所有 ORM 模型变更（新增字段、新增表、修改字段类型）
- 不适用：仅修改业务逻辑不涉及表结构
- 判断信号：ORM 模型文件有 `mapped_column` 变更但无对应迁移脚本
- 正确做法：
  ```python
  # ✅ 正确：迁移脚本与模型变更同步
  # 1. 修改模型
  class Workflow(Base):
      channel_id: Mapped[int | None] = mapped_column(ForeignKey("channel.id"), nullable=True)
  
  # 2. 编写迁移脚本（幂等）
  def migrate():
      cursor.execute("PRAGMA table_info(workflow)")
      cols = [row[1] for row in cursor.fetchall()]
      if 'channel_id' not in cols:
          cursor.execute("ALTER TABLE workflow ADD COLUMN channel_id INTEGER")
  
  # ❌ 错误：模型新增字段但无迁移脚本
  class Workflow(Base):
      channel_id: Mapped[int | None] = mapped_column(...)  # 数据库无此列
  ```
- 迁移脚本必须幂等（`IF NOT EXISTS` 或存在性检查）
- 真实案例：Workflow 模型新增 `channel_id` 列但未迁移，查询报 OperationalError: no such column

## 规范 26：环境依赖预检

**依赖外部二进制（ffmpeg/ffprobe 等）的功能必须在启动时或调用前检查依赖可用性。**

- 适用：ffmpeg、imagemagick、wkhtmltopdf 等外部二进制依赖
- 不适用：Python 包依赖（由 pip 管理）
- 判断信号：grep 搜索 `subprocess.run(["ffmpeg"` 无前置依赖检查
- 正确做法：
  ```python
  # ✅ 正确：启动时检查依赖
  import shutil
  
  def check_ffmpeg() -> bool:
      return shutil.which("ffmpeg") is not None
  
  # 启动时检查
  if not check_ffmpeg():
      logger.warning("ffmpeg 未安装，TTS 后处理功能不可用。安装命令: winget install ffmpeg")
  
  # ❌ 错误：直接调用假设已安装
  subprocess.run(["ffmpeg", "-i", input, output])  # WinError 2 文件未找到
  ```
- 真实案例：ffmpeg 未安装导致 TTS 后处理 8 个片段全部 WinError 2 失败

## 规范 27：`__init__.py` 导出完整性

**新增类/函数必须在包的 `__init__.py` 中同步导出，否则 `from package import NewClass` 会 ImportError。**

- 适用：所有 Python 包的 `__init__.py`
- 不适用：私有模块（以下划线开头）
- 判断信号：新增 `class NotificationEvent` 但 `__init__.py` 的 `__all__` 或 import 未更新
- 正确做法：
  ```python
  # app/services/notifier/__init__.py
  
  # ✅ 正确：新增类同步导出
  from .notifier import Notifier, NotificationEvent  # 新增 NotificationEvent
  
  __all__ = ["Notifier", "NotificationEvent"]
  
  # ❌ 错误：新增类未导出
  from .notifier import Notifier  # NotificationEvent 遗漏
  __all__ = ["Notifier"]
  ```
- 真实案例：`NotificationEvent` 未在 `notifier/__init__.py` 导出，导致 `from app.services.notifier import NotificationEvent` ImportError

## 规范 28：文件编辑安全校验

**使用 Edit 工具修改代码后必须进行语法校验 + 关键变量名/函数名 diff 检查。**

- 适用：所有使用 Edit 工具的代码修改
- 不适用：使用 Write 工具创建全新文件
- 判断信号：Edit 工具修改后未运行 `py_compile` 或 `npm run build`
- 正确做法：
  ```bash
  # ✅ 正确：编辑后三重校验
  # 1. 语法校验
  python -m py_compile modified_file.py
  
  # 2. 关键变量名 grep（检查是否被截断）
  grep "expected_var_name" modified_file.py
  
  # 3. 构建验证（前端）
  npm run build
  
  # ❌ 错误：编辑后直接提交
  # 变量名可能被截断为 "reesponse"，函数名可能损坏为 "Mesror"
  ```
- 真实案例：Edit 工具修改 api/index.js 时变量名 `response` 被截断为 `reesponse`，函数名 `Message` 被损坏为 `Mesror`，代码 `return Promise.reject(ne  }` 被截断

## 规范 29：框架预期 error 白名单

**UI 组件库的预期 error（如 Element Plus MessageBox cancel）必须加入白名单，不算测试 FAIL。**

- 适用：前端测试、自动化测试中控制台 error 检查
- 不适用：自定义 error（需修复）、业务逻辑 error
- 判断信号：测试日志中 error 匹配白名单子串
- 正确做法：
  ```yaml
  # config.yaml
  assertions:
    console_error_whitelist:
      - "cancel"                    # Element Plus MessageBox 取消
      - "NavigationDuplicated"      # Vue Router 重复导航
      - "Navigation cancelled"      # Vue Router 导航取消
  ```
- 真实案例：Element Plus MessageBox 用户点击取消时框架抛 error，测试误判为代码缺陷

## 规范 30：MCP 工具绝对路径

**MCP 工具的截图、快照、文件操作必须使用绝对路径，MCP 工具 cwd 可能与项目目录不同。**

- 适用：所有 MCP 工具的文件操作（截图、快照、上传等）
- 不适用：项目内相对路径操作（Read/Edit/Write 工具）
- 判断信号：MCP 工具参数中路径不以盘符（Windows）或 `/`（Linux）开头
- 正确做法：
  ```yaml
  # ✅ 正确：配置强制绝对路径
  screenshot:
    use_absolute_path: true
    save_dir: "docs/test-reports/screenshots"  # 配置中相对路径
    # 实际调用时拼接为绝对路径
  ```
  ```python
  # 调用 MCP 时拼接绝对路径
  abs_path = os.path.abspath(os.path.join(project_root, config.save_dir, filename))
  ```
- 真实案例：MCP 截图用相对路径保存到 MCP 工具 cwd 而非项目目录，找不到截图文件

## 规范 31：PowerShell HTTP 请求规范

**Windows PowerShell 中 HTTP 请求必须用 `Invoke-RestMethod` / `Invoke-WebRequest`，禁止 `curl.exe -d`。**

- 适用：Windows PowerShell 环境的 HTTP 请求
- 不适用：Linux/Mac shell 环境（curl 正常工作）
- 判断信号：grep 搜索 `curl.exe -d` 在 PowerShell 脚本中
- 正确做法：
  ```powershell
  # ✅ 正确：PowerShell 原生命令
  $body = '{"username":"admin","password":"admin123"}'
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/login" -Method POST -ContentType "application/json" -Body $body
  
  # ❌ 错误：curl.exe 在 PowerShell 中 JSON 转义问题
  curl.exe -d '{"username":"admin","password":"admin123"}' http://127.0.0.1:8000/api/login
  ```
- 真实案例：PowerShell 中 `curl.exe -d '{"key":"value"}'` 双引号转义失败，JSON 解析错误

## 规范 32：并发入队串行化

**PriorityQueue 入队操作必须用 asyncio.Lock 串行化，防止并发入队导致 ID 冲突。**

- 适用：asyncio.PriorityQueue 入队、并发 ID 生成
- 不适用：单线程无并发场景、已用 DB 唯一约束兜底
- 判断信号：grep 搜索 `queue.put_nowait` 无 `async with lock`
- 正确做法：
  ```python
  # ✅ 正确：Lock 串行化入队
  class WorkflowScheduler:
      def __init__(self):
          self._trigger_lock = asyncio.Lock()
      
      async def trigger_workflow(self, ...):
          async with self._trigger_lock:  # 串行化入队
              workflow_id = self._gen_id()
              entry = QueueEntry(id=workflow_id, ...)
              await self._queue.put(entry)
  
  # ❌ 错误：无锁并发入队
  async def trigger_workflow(self, ...):
      workflow_id = self._gen_id()  # 并发下可能重复
      await self._queue.put(entry)
  ```
- 真实案例：多请求同时触发工作流，ID 生成器并发计数器冲突导致 workflow_id 重复

## 规范 33：配置热生效延迟重建

**运行时配置变更（如并发数调整）不能立即重建资源（如 Semaphore），必须标记 dirty 延迟到当前任务完成后重建。**

- 适用：Semaphore 重建、连接池重建、线程池重建
- 不适用：只读配置（立即生效无副作用）
- 判断信号：grep 搜索配置更新后立即重建资源
- 正确做法：
  ```python
  # ✅ 正确：延迟重建
  async def update_config(self, max_concurrent: int):
      self._max_concurrent = max_concurrent
      self._config_dirty = True  # 标记 dirty
  
  async def _run_workflow_with_release(self, ...):
      try:
          await self._run_workflow(...)
      finally:
          self._semaphore.release()
          if self._config_dirty:  # 任务完成后检查
              self._rebuild_semaphore()
              self._config_dirty = False
  
  # ❌ 错误：立即重建
  async def update_config(self, max_concurrent: int):
      self._max_concurrent = max_concurrent
      self._semaphore = asyncio.Semaphore(max_concurrent)  # 立即重建，当前任务释放旧信号量失败
  ```
- 真实案例：并行模式下调整 max_concurrent 立即重建 Semaphore，当前运行任务 finally 释放新信号量导致计数错乱

## 规范 34：最小化窗口不激活

**前端代码在页面不可见（document.hidden）时跳过 DOM 操作（如 ElMessage），避免激活最小化的浏览器窗口。**

- 适用：后台轮询、WebSocket 推送、定时刷新等非用户主动触发的 UI 更新
- 不适用：用户主动操作（点击/提交）的 UI 反馈
- 判断信号：grep 搜索 `ElMessage.error` 无 `document.hidden` 检查
- 正确做法：
  ```javascript
  // ✅ 正确：页面不可见时跳过 ElMessage
  if (!document.hidden) {
    ElMessage.error('请求失败')
  }
  
  // ❌ 错误：无条件弹出 ElMessage
  ElMessage.error('请求失败')  // 最小化窗口被激活弹出
  ```
- 真实案例：后台轮询 401 时无条件 ElMessage.error，导致最小化浏览器窗口被反复激活弹出

## 规范 35：权限模型分层

**查看类接口 admin + operator 均可访问，操作类接口（取消/修改/删除/配置）仅 admin。**

- 适用：所有管理后台 API 权限控制
- 不适用：C 端用户 API（无角色区分）
- 判断信号：grep 搜索路由依赖注入的权限校验函数
- 正确做法：
  ```python
  # ✅ 正确：查看用 get_current_admin（admin+operator），操作用 require_admin（仅 admin）
  @router.get("/tasks")
  async def list_tasks(admin: AdminPayload = Depends(get_current_admin)):  # 查看：admin+operator
      ...
  
  @router.post("/tasks/{id}/cancel")
  async def cancel_task(admin: AdminPayload = Depends(require_admin)):  # 操作：仅 admin
      ...
  
  # ❌ 错误：所有接口都用 require_admin（operator 无法查看）
  @router.get("/tasks")
  async def list_tasks(admin: AdminPayload = Depends(require_admin)):  # operator 被拒
      ...
  ```
- 真实案例：队列管理查看接口误用 `require_admin`，operator 角色无法查看队列状态

## 规范 36：PriorityQueue 取消任务标记法

**asyncio.PriorityQueue 不支持随机删除，取消任务必须用 cancelled 标记，worker 轮询时跳过已标记条目。**

- 适用：asyncio.PriorityQueue / asyncio.Queue 的任务取消场景
- 不适用：deque / list 等支持随机删除的数据结构
- 判断信号：grep 搜索 `queue.put_nowait` 配合任务取消逻辑，但无 `cancelled` 字段
- 正确做法：
  ```python
  # ✅ 正确：用 cancelled 标记，worker 跳过已取消任务
  @dataclass(order=True)
  class QueueEntry:
      priority: int
      id: str = field(compare=False)
      cancelled: bool = field(default=False, compare=False)  # 取消标记

  async def cancel_task(self, task_id: str) -> bool:
      # PriorityQueue 不支持随机删除，只能标记
      entry = self._entry_index.get(task_id)
      if entry:
          entry.cancelled = True  # 标记取消
          return True
      return False

  async def _worker(self):
      while True:
          entry = await self._queue.get()
          if entry.cancelled:  # 跳过已取消任务
              self._queue.task_done()
              continue
          await self._process(entry)

  # ❌ 错误：尝试从 PriorityQueue 随机删除（不支持）
  def cancel_task(self, task_id: str):
      self._queue.queue.remove(task_id)  # AttributeError / 破坏堆结构
  ```
- 真实案例：工作流取消时尝试从 PriorityQueue 删除条目，asyncio.PriorityQueue 底层是堆，不支持随机删除，导致取消失败且任务仍被执行

## 规范 37：Semaphore 延迟重建避免等待任务泄漏

**重建 asyncio.Semaphore 时，旧 Semaphore 上 acquire 阻塞的任务无法被新 Semaphore 唤醒，必须延迟重建或唤醒旧等待者。**

- 适用：asyncio.Semaphore 动态调整并发数的场景（与规范 33 互补：规范 33 解决运行中任务释放错乱，本规范解决等待中任务永久阻塞）
- 不适用：并发数固定不变的场景
- 判断信号：grep 搜索 `Semaphore(` 重新赋值时，旧 Semaphore 可能有 acquire 等待者
- 正确做法：
  ```python
  # ✅ 正确：延迟重建 + 等待者唤醒
  class ConcurrencyManager:
      def __init__(self, max_concurrent: int):
          self._max_concurrent = max_concurrent
          self._semaphore = asyncio.Semaphore(max_concurrent)
          self._config_dirty = False
          self._pending_waiters: list[asyncio.Future] = []

      async def acquire(self) -> bool:
          # 检查是否需要延迟重建（仅当无活跃持有时）
          if self._config_dirty and self._active_count == 0:
              self._rebuild_semaphore()
              self._config_dirty = False
          return await self._semaphore.acquire()

      def update_concurrency(self, new_max: int):
          self._max_concurrent = new_max
          self._config_dirty = True  # 标记 dirty，延迟到安全时机重建

      def _rebuild_semaphore(self):
          old_semaphore = self._semaphore
          self._semaphore = asyncio.Semaphore(self._max_concurrent)
          # 唤醒旧 Semaphore 上所有等待者（防止永久泄漏）
          for _ in range(old_semaphore._value):
              old_semaphore.release()

  # ❌ 错误：立即重建，旧 Semaphore 等待者永久阻塞
  def update_concurrency(self, new_max: int):
      self._semaphore = asyncio.Semaphore(new_max)  # 旧等待者泄漏
  ```
- 真实案例：调整 max_concurrent 后立即重建 Semaphore，旧 Semaphore 上有 3 个 acquire 阻塞的任务，这些任务永远无法被唤醒，导致工作流卡死

## 规范 38：SQLite VACUUM INTO 隔离级别

**SQLite VACUUM INTO 必须在 AUTOCOMMIT 隔离级别执行，不能在事务内执行（会报 operational error）。**

- 适用：SQLite 数据库备份（VACUUM INTO）、事务内执行 VACUUM 类操作
- 不适用：MySQL / PostgreSQL（VACUUM 语义不同）
- 判断信号：grep 搜索 `VACUUM INTO` 在 `async with session.begin()` 或 `async with session` 事务块内
- 正确做法：
  ```python
  # ✅ 正确：用 AUTOCOMMIT 隔离级别执行 VACUUM INTO
  from sqlalchemy import text

  async def backup_database(self, backup_path: str):
      # VACUUM INTO 不能在事务内执行，必须用 AUTOCOMMIT
      async with self._engine.connect() as conn:
          await conn.execution_options(isolation_level="AUTOCOMMIT")
          await conn.execute(text(f"VACUUM INTO '{backup_path}'"))

  # ❌ 错误：在事务内执行 VACUUM INTO
  async def backup_database(self, backup_path: str):
      async with self._engine.begin() as conn:  # 事务内
          await conn.execute(text(f"VACUUM INTO '{backup_path}'"))
          # OperationalError: cannot VACUUM from within a transaction
  ```
- 真实案例：数据库备份功能在 `async with session.begin()` 事务内执行 VACUUM INTO，报 "cannot VACUUM from within a transaction" 错误

## 规范 39：微信 API access_token 缓存

**微信 msgSecCheck 等 API 需要 access_token，必须缓存（TTL 7200s），禁止每次调用都重新获取。**

- 适用：微信开放平台 API（msgSecCheck、msgCheckText、内容安全检测等）
- 不适用：无 access_token 机制的 API
- 判断信号：grep 搜索 `access_token` 获取逻辑在每次 API 调用时执行，无缓存
- 正确做法：
  ```python
  # ✅ 正确：缓存 access_token，过期前提前刷新
  class WeChatContentSecurity:
      TOKEN_TTL_SEC = 7200  # 微信 access_token 有效期 2 小时
      TOKEN_REFRESH_AHEAD_SEC = 300  # 提前 5 分钟刷新，避免边界过期

      def __init__(self):
          self._token_cache: TTLCache = TTLCache(maxsize=1, ttl=self.TOKEN_TTL_SEC)

      async def get_access_token(self) -> str:
          cached = self._token_cache.get("access_token")
          if cached:
              return cached
          token = await self._fetch_access_token()
          self._token_cache.set("access_token", token)
          return token

      async def check_content(self, content: str) -> dict:
          token = await self.get_access_token()  # 命中缓存
          return await self._call_msg_sec_check(token, content)

  # ❌ 错误：每次调用都重新获取 token
  async def check_content(self, content: str) -> dict:
      token = await self._fetch_access_token()  # 每次都请求，浪费配额
      return await self._call_msg_sec_check(token, content)
  ```
- 真实案例：内容安全检测每次都调用 `/cgi-bin/token` 获取 access_token，触发微信接口调用频率限制（每日限额），导致内容审核批量失败

## 规范 40：COS 对象幂等同步

**COS 对象同步到数据库必须用 INSERT OR IGNORE + 删除源对象双重保障，避免重复同步和源对象残留。**

- 适用：COS / OSS / S3 对象同步到数据库的场景
- 不适用：需要更新已有记录的场景（用 INSERT OR REPLACE 或 UPSERT）
- 判断信号：grep 搜索 COS 对象同步逻辑，无 `INSERT OR IGNORE` 或无源对象删除
- 正确做法：
  ```python
  # ✅ 正确：INSERT OR IGNORE 幂等 + 删除源对象防止重复
  async def sync_cos_objects(self):
      objects = await self._cos_client.list_objects(prefix=settings.COS_SYNC_PREFIX)
      for obj in objects:
          # 幂等插入：已存在则跳过（INSERT OR IGNORE）
          await db.execute(
              text("INSERT OR IGNORE INTO cos_sync_log (object_key, synced_at) VALUES (:key, :ts)"),
              {"key": obj.key, "ts": utcnow_naive()}
          )
          await db.commit()
          # 删除源对象，防止下次重复同步
          await self._cos_client.delete_object(obj.key)
          logger.info(f"Synced and deleted COS object: {obj.key}")

  # ❌ 错误：无幂等保障 + 不删除源对象
  async def sync_cos_objects(self):
      objects = await self._cos_client.list_objects(prefix=settings.COS_SYNC_PREFIX)
      for obj in objects:
          await db.execute(text("INSERT INTO cos_sync_log (object_key) VALUES (:key)"), {"key": obj.key})
          # 不删除源对象 → 下次同步重复插入 → IntegrityError
  ```
- 真实案例：COS playlog 同步无幂等保障，服务重启后重复同步同一批对象导致 IntegrityError；源对象未删除导致每次都重复处理

## 规范 41：小程序 playbackRate 范围限制

**微信小程序 BackgroundAudioManager.playbackRate 仅支持 0.5-2.0 范围，超出范围会被静默忽略或报错。**

- 适用：微信小程序音频倍速播放
- 不适用：Web Audio API（范围更宽）、自定义音频播放器
- 判断信号：grep 搜索 `playbackRate` 赋值，无范围校验
- 正确做法：
  ```javascript
  // ✅ 正确：校验范围 + 配置驱动可选值
  const PLAYBACK_RATES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]  // 从配置读取

  function setPlaybackRate(rate) {
    // 微信 BackgroundAudioManager.playbackRate 范围 0.5-2.0
    if (rate < 0.5 || rate > 2.0) {
      console.warn(`playbackRate ${rate} 超出范围 [0.5, 2.0]，已忽略`)
      return
    }
    const audioManager = getApp().globalData.player
    audioManager.playbackRate = rate
  }

  // ❌ 错误：直接赋值无校验
  function setPlaybackRate(rate) {
    audioManager.playbackRate = rate  // 超出 0.5-2.0 被静默忽略
  }
  ```
- 真实案例：小程序倍速播放设为 3.0，BackgroundAudioManager 静默忽略不生效，用户反馈"倍速没用"

## 规范 42：canvas 验证码形近字符排除

**生成 canvas 验证码时必须排除形近字符（0/O、l/I/1、o/O 等），避免用户无法区分导致验证失败。**

- 适用：canvas / SVG 验证码生成、图片验证码
- 不适用：纯数字验证码（无字母）、短信验证码（用户输入而非识别）
- 判断信号：grep 搜索验证码字符集定义，包含 `0`、`O`、`l`、`I`、`1` 等形近字符
- 正确做法：
  ```javascript
  // ✅ 正确：排除形近字符的字符集
  // 排除 0/O/o、1/l/I/i、q/9、s/5 等易混淆字符
  const CAPTCHA_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'  // 从配置读取
  // 注意：已排除 I、L、O、Q（与 0/1 混淆）、S（与 5 混淆）、Z（与 2 混淆，可选）

  function generateCaptcha(length = 4) {
    let code = ''
    for (let i = 0; i < length; i++) {
      code += CAPTCHA_CHARS[Math.floor(Math.random() * CAPTCHA_CHARS.length)]
    }
    return code
  }

  // ❌ 错误：包含所有字母数字
  const CAPTCHA_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  // 用户分不清 0/O、1/I/l → 验证码通过率低
  ```
- 真实案例：验证码字符集包含 `0Oo1IlI`，用户输入 `O` 被判错（实际是 `0`），导致登录失败率升高

## 规范 43：Sortable.js 拖拽 el-table DOM 恢复顺序

**使用 Sortable.js 拖拽 el-table 时，onEnd 回调必须先恢复 DOM（将拖拽移动的节点插回原位），再修改数组，避免 Vue diff 冲突。**

- 适用：Sortable.js + Vue 3 el-table 拖拽排序
- 不适用：原生 HTML table 拖拽（无 Vue diff 机制）
- 判断信号：grep 搜索 `Sortable.create` + `el-table`，onEnd 回调中直接修改数组无 DOM 恢复
- 正确做法：
  ```javascript
  // ✅ 正确：先恢复 DOM 再改数组，让 Vue diff 一致
  import Sortable from 'sortablejs'

  Sortable.create(el.querySelector('.el-table__body-wrapper tbody'), {
    animation: 150,
    onEnd({ oldIndex, newIndex, item }) {
      // 关键：Sortable 已修改 DOM，需先恢复让 Vue 重新接管
      const tbody = el.querySelector('.el-table__body-wrapper tbody')
      tbody.removeChild(item)
      tbody.insertBefore(item, tbody.children[oldIndex])
      // DOM 恢复后再修改数组，Vue diff 不会冲突
      const movedItem = tableData.splice(oldIndex, 1)[0]
      tableData.splice(newIndex, 0, movedItem)
    }
  })

  // ❌ 错误：直接改数组，Sortable 已改 DOM，Vue diff 冲突
  Sortable.create(tbody, {
    onEnd({ oldIndex, newIndex }) {
      const movedItem = tableData.splice(oldIndex, 1)[0]
      tableData.splice(newIndex, 0, movedItem)
      // Sortable 已移动 DOM 节点，Vue 再移动一次 → 渲染错乱
    }
  })
  ```
- 真实案例：el-table 拖拽排序后表格渲染错乱，原因是 Sortable.js 已修改 DOM，Vue diff 再次移动导致重复操作

## 规范 44：el-table 拖拽取消 fixed 列

**el-table 在拖拽排序模式下必须取消 fixed 列，否则双 tbody（固定列 + 主表格）导致 Sortable 错位。**

- 适用：el-table + Sortable.js 拖拽排序
- 不适用：无 fixed 列的 el-table、非拖拽场景
- 判断信号：grep 搜索 `Sortable.create` + `el-table`，同时 el-table 有 `fixed` 属性列
- 正确做法：
  ```vue
  <!-- ✅ 正确：拖拽模式下取消 fixed 列 -->
  <el-table :data="tableData" row-key="id">
    <el-table-column type="index" width="50" />
    <el-table-column prop="name" label="名称" /><!-- 无 fixed -->
    <el-table-column prop="sort" label="排序" /><!-- 无 fixed -->
    <el-table-column label="操作" width="120">
      <template #default="{ row }">
        <el-button :icon="Rank" class="drag-handle" />
      </template>
    </el-table-column>
  </el-table>
  <!--
    为什么：el-table fixed 列会生成独立 tbody，Sortable 只绑定主 tbody，
    拖拽时固定列 tbody 不联动 → 行错位
  -->

  <!-- ❌ 错误：有 fixed 列时拖拽 -->
  <el-table :data="tableData" row-key="id">
    <el-table-column prop="name" label="名称" fixed="left" /><!-- fixed 列 -->
    <el-table-column prop="sort" label="排序" />
  </el-table>
  <!-- fixed 列生成独立 tbody，拖拽时固定列不跟随移动 → 错位 -->
  ```
- 真实案例：el-table 有 `fixed="left"` 列时启用拖拽，拖拽后固定列与主表格行错位，取消 fixed 后正常

---

## 与 meta-rules.md 的关系

| 来源 | 规范范围 | 编号 |
|------|----------|------|
| meta-rules.md | 基础规范（配置驱动、复用优先、错误分类等） | 1-22 |
| lessons-learned.md（本文档） | 经验教训规范（从实际踩坑提炼） | 21-44 |

两文档互补：meta-rules.md 是项目初期制定的预防性规范，lessons-learned.md 是项目迭代中从实际问题提炼的补充规范。代码审查时两个文档均需参考。

---

## 经验教训：TTS/Edge 语音合成故障与分步重跑实现

### 维度 1：成功执行任务的完整步骤

#### TTS/Edge 故障排查

1. **日志定位** → 搜索 logs/service-start.log 和 ackend/logs/ 中的 ffmpeg/tts/synth 关键词
2. **FFmpeg 独立验证** → 直接运行 fmpeg -version、fprobe -i audio.mp3、loudnorm 滤镜实测，确认工具本身正常
3. **工作流状态查询** → 从 workflow 表查到 wf-20260712-0003 的 tts 步骤失败，错误为  /6 成功率过低
4. **TTS 配置核查** → 从 i_config 表查到 provider=edge、voice=zh-CN-XiaoxiaoNeural、rate/volume/pitch 均为空
5. **Edge TTS 直接调用** → 用相同 Python 环境 + 相同 voice 参数调用 EdgeTTSProvider.synthesize()，复现 NoAudioReceived 错误
6. **网络连通性验证** → DNS 解析 + TCP 443 连接测试 speech.platform.bing.com，确认网络层正常
7. **参数隔离测试** → 分别测试无参数、有效参数、存储参数三种组合，确认无论参数如何均返回空音频
8. **根因确认** → Edge TTS 服务层拒绝返回音频（可能为代理/防火墙/服务策略），非代码 bug
9. **代码修复** → 将 NoAudioReceived 分类为可重试的 TTSServiceError，修复配置键不一致，添加分段失败摘要

#### 分步重跑实现

1. **前端行为观察** → 点击"语音合成重跑"后，新工作流 wf-20260712-0004 从 crawl 开始执行
2. **后端接口追踪** → 路由层接收 step 参数但注释写明"MVP 简化为重新触发完整工作流"
3. **调度器代码审查** → 	rigger_workflow() 不接受起始步骤参数，_run_workflow() 硬编码从 crawl 到 review 的顺序
4. **上游产物分析** → 确认 rewrite 产物 script_id 存储在 workflow_step.result 中，tts 需要此值
5. **方案设计与实现** → 让 retry 接口从原工作流提取上游成功产物，注入新工作流 context，仅执行选定步骤及后续

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| Edge TTS 空音频被分类为非重试异常 | NoAudioReceived 异常被包装为通用 TTSError | 整个 TTS 批次失败，无法重试或降级 | 异常分类粒度过粗 | 识别 NoAudioReceived 为 TTSServiceError |
| 配置键名不一致 | 前端用 edge_rate，后端映射用 edge_tts_rate | 前端保存的 Edge 参数不生效 | 字段命名缺乏统一规范 | 统一键名 + 兼容旧键名读取 |
| 批量失败缺少诊断信息 | TTS 6 段全部失败，仅返回  /6 | 无法定位失败原因 | 异常消息未包含分段级信息 | 添加 _summarize_segment_failures 函数 |
| 重跑接口忽略 step 参数 | MVP 简化实现，注释写明"重新触发完整工作流" | 重跑变成全量重跑，浪费时间 | 接口契约不完整 | 实现真正的分步重跑逻辑 |
| 旧版数值零参数导致 Edge 报错 | 前端保存 edge_rate=0.0，传给 edge-tts 报 Invalid rate | 特定用户配置无法使用 | 缺少参数规范化 | 添加 _normalize_edge_adjustment 函数 |
| 凭证明文存储在配置表 | i_config 表中 llm_api_key、	ts_api_key 明文 | 安全风险 | 缺少加密/环境变量隔离 | 建议轮换凭证，后续迁移到加密存储 |

### 维度 3：可抽象的固定流程与判断逻辑

#### 外部服务故障排查流程

`
日志关键词搜索 → 独立工具验证 → 工作流状态查询 → 
配置核查 → 直接调用复现 → 网络连通性测试 → 
参数隔离测试 → 根因确认 → 代码修复
`

**适用场景**：任何第三方 API / CLI 工具集成故障排查
**不适用场景**：纯代码逻辑 bug（无需外部验证）、已知服务端宕机

#### 外部服务异常分类判断逻辑

`
外部异常 → 检查异常类型/消息 → 
  ├─ NoAudioReceived / 空响应 → TTSServiceError（可重试）
  ├─ 429 / 限流 → TTSRateLimitError（触发预算检查）
  ├─ Timeout → TTSTimeoutError（可重试）
  ├─ 认证失败 → TTSError（不可重试）
  └─ 其他 → TTSError（不可重试）
`

**适用场景**：任何外部服务调用的异常分类
**不适用场景**：内部纯代码异常

#### 配置键一致性检查流程

`
前端表单字段名 → 路由模型字段名 → 数据库配置键名 → Settings 属性名
     ↓ 必须一致或存在明确映射
     ↓ 字段变更时保留旧键名兼容读取
     ↓ 写入前做参数规范化
`

**适用场景**：任何前端-后端配置交互
**不适用场景**：纯后端内部配置

### 维度 4：适用场景与不适用场景

| 流程/判断逻辑 | 适用场景 | 不适用场景 |
|--------------|----------|-----------|
| 外部服务故障排查流程 | 第三方 API、CLI 工具、WebSocket 服务集成 | 纯内存计算、无外部依赖的单元测试 |
| 外部服务异常分类 | 任何需要重试/降级决策的外部调用 | 一次性调用（无重试机制）、同步阻塞调用 |
| 配置键一致性检查 | 前端表单 ↔ 后端 API ↔ 数据库配置的完整链路 | 纯后端 CLI 工具、无用户界面的脚本 |
| 批量失败诊断摘要 | 循环处理中部分失败的批量操作 | 单任务处理、错误已由上层详细记录 |
| 分步重跑复用上游产物 | 多步骤流水线（ETL、工作流、批处理） | 单步骤操作、无状态操作 |

---

---

## 新增经验教训：音频时长自动填充规范

### 问题描述

工作流 stitch 步骤在音频拼接完成后进行时长校验（570-630 秒），当总时长超出范围时直接抛出 StitchError 并失败。重试机制（3 次）产生相同结果，因为输入数据不变。

**根因**：stitch 步骤只有"校验+报错"逻辑，没有"自动调整"逻辑。

### 成功执行的完整步骤

1. **日志分析** → 定位错误信息 最终音频时长 507s 超出允许范围 [570, 630]
2. **代码追踪** → 阅读 concat.py 的时长校验逻辑（第 8 步直接 raise StitchError）
3. **重试机制分析** → 阅读 workflow_scheduler.py 的 _run_step 方法，确认 3 次重试使用相同输入
4. **广告插入逻辑分析** → 阅读 ffmpeg_wrapper.py 的 build_mid_ad_cmd，确认广告插入会增加时长
5. **TTS 后处理分析** → 阅读 audio_postprocess.py 的 trim_silence，确认去静音会减少时长
6. **方案设计** → 在时长校验前添加自动填充/切除逻辑
7. **实现填充** → 不足时追加静音到末尾（generate_silence + build_full_concat_cmd）
8. **实现切除** → 超出时从末尾切除多余部分（ffmpeg atrim filter）
9. **二次校验** → 填充/切除后再次校验，确保落入范围
10. **语法验证** → py_compile 确认 Python 语法正确

### 不确定性分析与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 时长不足直接报错 | 音频内容 507s < 570s 下限 | 工作流失败，3 次重试均无效 | 无自动填充机制 | 追加静音填充 |
| 时长超限无处理 | 音频内容 > 630s 上限 | 工作流失败 | 无自动切除机制 | 从末尾切除 |
| 重试无效 | 同一输入产生同一结果 | 浪费 2 次重试机会 | 重试机制对确定性失败无意义 | 首次尝试即自动填充 |
| 填充后仍超限 | 极端情况下填充/切除后仍在范围外 | 二次校验报错 | 理论上不可能（填充至 570/切除至 630） | 保留二次校验兜底 |

### 可抽象的固定流程与判断逻辑

#### 时长自动调整流程

`
计算最终时长 → 
  ├─ duration < MIN_DURATION → 追加 (MIN - duration) 秒静音 → 重新计算
  ├─ duration > MAX_DURATION → 从末尾切除 (duration - MAX) 秒 → 重新计算
  └─ MIN <= duration <= MAX → 通过校验
↓
二次校验（兜底）→ 仍越界则报错
`

**适用场景**：任何有时间/大小/数量约束的拼接/聚合操作
**不适用场景**：实时流处理（不能追加）、精确时长要求（如音乐视频同步）

#### 工作流步骤重试有效性判断

`
步骤函数输入不变 → 重试无效（确定性失败）
步骤函数输入可变 → 重试有效（瞬态失败）
判断方法：检查步骤函数是否依赖外部状态（网络、文件、DB）
`

**适用场景**：设计工作流重试策略
**不适用场景**：纯计算步骤（重试无意义）

### 新增编码规范

#### 规范 23：时长/容量约束的自动填充与切除

所有有时间、容量、大小等硬性约束的拼接/聚合操作，必须在最终校验前实现自动调整能力：

- 不足时：追加填充物（静音、空白页、默认内容等）
- 超出时：从末尾切除多余部分
- 填充/切除后：必须进行二次校验作为兜底

**判断信号**：grep 搜索 duration.*超出.*范围 或 length.*exceed 直接 raise
**正确做法**：先计算差值，执行填充/切除，再二次校验

#### 规范 24：确定性失败的重试无效性

工作流步骤的重试只对瞬态失败（网络超时、临时 IO 错误）有意义。对于确定性失败（输入数据导致的结果不变），重试是无效的。

**判断信号**：grep 搜索步骤函数内部无外部状态依赖（无网络调用、无文件读写、无 DB 查询）
**正确做法**：在步骤函数内部实现自动调整能力，而非依赖重试机制

---

---

## 新增经验教训：AI 服务商模型名称与 API Key 持久化规范

### 问题描述

在接入 DeepSeek 等第三方 AI 服务商时，出现以下问题：

1. **模型名称大小写错误**：DeepSeek 预设默认模型使用了 deepseek-chat（旧模型），用户明确要求使用 deepseek-v4-flash（小写），但代码中未同步更新定价表
2. **API Key 切换覆盖**：不同服务商（通义千问 / DeepSeek / OpenAI）共用同一个 llm_api_key 配置项，切换提供商时如果预设模型名不匹配实际 API Key 归属，会导致鉴权失败
3. **前端预设切换未反射**：选择预设后下拉框未更新选中状态，用户不知道当前使用的是哪个提供商
4. **配置持久化返显不完整**：前端 loadConfig 后 selectedPreset 为空，页面刷新后看不到当前使用的是哪个预设提供商

**根因**：
- 模型名称是外部服务商提供的"事实源"，技能文档中没有将其列为需要核对的硬约束
- 预设切换逻辑只改了表单值，没有同步更新 UI 状态（selectedPreset）
- 配置加载后没有自动匹配预设的逻辑

### 成功执行的完整步骤

1. **问题定位** → 用户明确要求"默认模型选择 deepseek-v4-flash，注意是小写"
2. **代码搜索** → grep 搜索 deepseek 定位到 i_config_service.py 中的 LLM_PRESETS 和 MODEL_PRICING
3. **官网核对** → 逐个核对所有提供商模型名称大小写（通义千问 qwen-max、OpenAI gpt-4o-mini、智谱 glm-4-flash、Moonshot moonshot-v1-8k、百度 ernie-4.0-8k、豆包 doubao-pro-4k、Ollama qwen2.5:7b、Agnes Agnes-2.0-Flash）
4. **后端修改** → 修改预设默认模型 deepseek-chat → deepseek-v4-flash，同步添加定价条目
5. **前端修改** → pplyPreset 函数增加 selectedPreset.value = key
6. **前端修改** → loadConfig 函数增加基于 ase_url 的预设自动匹配逻辑
7. **语法验证** → Python st.parse 验证后端语法 + 
pm run build 验证前端构建
8. **后端验证** → python -c "import ast; ..." 确认 Python 语法 OK
9. **前端验证** → 
px vite build 确认构建通过

### 不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 模型名称大小写不一致 | 预设模型名与定价表键名不匹配 | 用量统计费用估算错误 | MODEL_PRICING 只保留了旧模型名 | 新增模型名必须同步添加定价条目 |
| PowerShell 字符串替换引入转义字符 | -replace 命令中的 \r\n 被当作字面量 | 文件内容损坏 | PowerShell 字符串替换的陷阱 | 使用索引直接赋值替代正则替换 |
| 前端构建时间长 | 大量 SCSS 编译 + Vite 打包 | 验证延迟 | 正常现象，非问题 | 接受长时间构建，关注 exit code |
| 预设切换后下拉框不反射 | pplyPreset 未设置 selectedPreset | 用户体验差，不知道当前选的是哪个 | 函数只改了表单值，没改状态 | 增加 selectedPreset.value = key |
| 页面刷新后看不到当前提供商 | loadConfig 后 selectedPreset 始终为空 | 用户无法确认配置归属 | 缺少基于 base_url 的自动匹配 | 增加预设自动匹配逻辑 |

### 可抽象的固定流程与判断逻辑

#### 第三方服务接入标准流程


1. 搜索现有预设配置 → grep 定位 LLM_PRESETS / MODEL_PRICING
2. 核对官方文档 → 确认模型名称大小写（事实源）
3. 修改预设默认值 → 更新 LLM_PRESETS 中对应项
4. 同步更新定价表 → MODEL_PRICING 添加新模型名条目
5. 更新前端预设逻辑 → applyPreset 同步 selectedPreset 状态
6. 增加预设自动匹配 → loadConfig 后基于 base_url 匹配
7. 语法验证 → 后端 py_compile / ast.parse + 前端 npm run build
8. 回归测试 → 切换预设验证表单值 + 下拉框状态


**适用场景**：任何第三方服务（LLM/TTS/存储）接入
**不适用场景**：内部自研服务

#### 配置持久化与返显标准流程


1. 后端 GET 接口返回完整配置 → api_key 脱敏 + 其他字段明文
2. 前端 Object.assign 回填表单 → 保留所有字段
3. 预设切换时 → 仅覆盖 base_url + model，保留 api_key
4. 保存时 → 前端回传完整表单值
5. 后端 _normalize_llm 处理 → api_key 脱敏值跳过（未修改），明文值写入
6. 页面刷新 → loadConfig 重新拉取 + 自动匹配预设


**适用场景**：所有配置管理场景（LLM/TTS/通知/存储）
**不适用场景**：一次性表单（无需持久化）

### 新增编码规范

#### 规范 25：第三方服务模型名称以官网为准

所有第三方 AI 服务商（LLM/TTS/存储）的模型名称、API 端点、密钥格式必须以官方文档为事实源，技能文档中不得自行编造或猜测。

**判断信号**：grep 搜索预设配置中的模型名，与官网文档逐字核对
**正确做法**：
- 新接入服务商时，先查阅官方文档确认模型名称大小写
- 修改预设默认模型时，同步更新 MODEL_PRICING 中的定价条目
- 模型名称是区分大小写的字符串，deepseek-v4-flash ≠ DeepSeek-V4-Flash

#### 规范 26：配置持久化与返显完整性

所有配置输入框的值必须完整持久化到数据库，并在页面加载时正确返显。预设切换时不应覆盖已保存的 API Key。

**判断信号**：grep 搜索预设切换函数，确认是否保留 api_key
**正确做法**：
- 预设切换只更新 ase_url 和 model，保留 pi_key
- 页面加载后自动匹配预设（基于 ase_url）
- 前端 selectedPreset 状态必须与下拉框实际选中值同步

#### 规范 27：PowerShell 文件编辑安全

使用 PowerShell 进行文件内容替换时，避免使用 -replace 操作符处理多行字符串，应使用索引直接赋值。

**判断信号**：grep 搜索 -replace 命令中是否包含 \r\n 等转义序列
**正确做法**：使用 $lines[index] = "new value" 直接赋值，而非正则替换

#### 规范 28：模型定价表同步更新

每当修改或新增模型名称时，必须同步检查 MODEL_PRICING 定价表中是否包含该模型条目。缺失定价条目的模型将使用默认费率（gpt-4o-mini），导致费用统计不准确。

**判断信号**：grep 搜索新增模型名是否在 MODEL_PRICING 中存在
**正确做法**：修改预设模型时，同时检查并更新定价表

---