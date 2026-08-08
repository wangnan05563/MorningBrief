# 诊断与编码标准（会话复盘提炼）

> 本文档从 2026-08-05 会话中解决的若干真实问题提炼而成，作为 [lessons-learned.md](lessons-learned.md) 与 [meta-rules.md](meta-rules.md) 的补充。
> 涵盖问题：频道级静音参数"看似不生效"、AI 用量统计全 0、打包模式三面板空白、关于页 SHA/版本失真、安装包默认图标、后端走查发现的异步阻塞、`localnow_naive` 全量重命名、测试隔离泄漏（`test_ai_budget` 失败）。
> 另含 **2026-08-05 第二轮补充（DS-11~DS-14）**：PyInstaller frozen 模式 `.env` 加载失败（appid missing）、安装包 `.env` 被 `Excludes` 静默丢弃、HLS 首播冷启动失败、微信剪贴板隐私 scope 未声明。
>
> 每条标准均按 **四维度复盘（维度 1-4）** 组织：成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用与不适用场景。

---

## 四维度复盘总览

### 维度 1：成功执行任务的完整步骤（通用闭环）

适用于"诊断一个疑似 bug → 定位根因 → 修复 → 验证"类任务的标准路径：

1. **复现与界定**：用真实函数/真实数据最小复现，区分"真 bug"与"陈旧数据幻觉"（见 DS-7）。
2. **定位链路**：grep + Read 顺着调用链定位到具体文件/行（路由 → 服务 → 模型/工具）。
3. **对照规范**：逐条比对 [meta-rules.md](meta-rules.md) 与本文档 DS 系列，判断是否为已知反模式。
4. **最小修复**：优先编辑现有文件，保持"为什么"注释；涉及公共 API（如工具函数）改名时走 DS-8 全量重命名流程。
5. **语法/导入验证**：后端 `py_compile` + 实际 `from app.main import app`；前端 `vite build`。
6. **测试隔离**：依赖模块级文件路径/单例的测试必须走 DS-9（`tmp_path` + `monkeypatch` 重定向），不得依赖 `unlink()` 成功。
7. **全量回归**：后端改 → 跑 pytest；前端改 → 跑 Playwright（见 news-auto-testing 约定）。
8. **报告与归档**：输出审查/测试报告，把新规律沉淀进本文件（DS 编号递增）。

**关键教训**：步骤 1 的"陈旧数据幻觉"排查能避免把"流水线崩溃无新产出"误判为"参数无效"；步骤 6 的测试隔离能避免环境制品伪装成代码失败。

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 异常被吞（空错误） | `except Exception: logger.error(str(e))` | 真因被吞，日志只有空串 | 只记录 `str(e)`，未保留类型与 traceback | 包裹启动调用，抛出带类型+cmd 的专用异常（DS-1） |
| CancelledError 逃逸 | `asyncio.wait_for` 超时 / 任务被取消，`except Exception` 在前 | 协程静默失败、空 error、空 failed_step | Python 3.12+ 中 `CancelledError` 是 `BaseException` 子类 | `except` 链中 `Exception` 之前补 `except asyncio.CancelledError`（DS-2） |
| fire-and-forget 协程被 GC | 同步签名函数内裸 `create_task` 无保活 | 落库/副作用丢失，无告警 | 局部变量无生命周期，asyncio 不持有强引用 | 模块级集合保活 + `get_running_loop()` 守卫（DS-3） |
| 时区偏差导致统计全 0 | SQLite `func.now()` 返回 UTC，按本地日期切分"今日" | 当日聚合全 0 | 写入端未显式赋本地时间 | 写入端用 `localnow_naive()` 显式赋值（DS-4） |
| 打包模式面板空白 | `sys.frozen` + COS 已配置，TTS/成品不上本地副本 | 前端读本地目录返回空 | 列表接口无 DB 远程 URL 回退 | 本地空回退 `audio_url`（DS-5） |
| 版本/SHA 失真 | `_build_info.py` 硬编码默认值，构建/发布脚本未刷新 | 关于页永远 unknown / 固定日期 | 缺少单一真相源 + 脚本未调用生成器 | 生成器派生 + 脚本刷新（DS-6） |
| "参数不生效"误判 | 旧音频（默认值）残留，新音频从未产出 | 误修参数而非修崩溃 | 陈旧残留冒充新产出 | 先验证产出物时间戳/参数（DS-7） |
| 重命名泄漏 ImportError | 删别名但漏改某处调用/注释 | 启动 ImportError / NameError | grep 未全量验证 | 全仓库 grep 0 匹配（DS-8） |
| 测试状态泄漏 | `reset_budget()` 用 `unlink()` 清文件被安全删除拦截 | 计数器 +1 泄漏，断言 `2==1` | 隔离依赖真实文件系统删除成功 | `tmp_path` + `monkeypatch` 重定向（DS-9） |
| 安装包默认图标 | `installer.iss` 缺 `SetupIconFile` | 安装包显示系统默认图标 | exe 图标已配，安装包未配 | `SetupIconFile` 复用产品图标（DS-10） |
| frozen 模式 .env 加载失败 | PyInstaller 冻结 exe，`config.py` 用相对/固定 `env_file` 路径 | 微信登录 appid missing（`Settings` 读不到 `WX_APPID`） | `_MEIPASS` 临时目录无 `.env`，相对路径解析失败 | `sys.executable` 同级解析 `.env`（DS-11） |
| 安装包静默丢弃 .env | `installer.iss` 的 `Excludes` 含 `.env` 或构建脚本未显式包含 | 重打包后 appid 仍 missing（包内无 `.env`） | `Excludes` 静默排除、未 `Source:` 显式包含 | 显式 `Source: "dist\...\env"` + 去隐藏属性（DS-12） |
| HLS 首播冷启动失败 | 小程序 `BackgroundAudioManager` 首次播放 HLS 流 | 首次播放失败、重试/切集后成功 | HLS 首次建立连接冷启动超时/解码延迟 | 静默重试（`MAX_HLS_RETRY`）+ 回退 mp3（DS-13） |
| 微信剪贴板隐私 scope 未声明 | 调用 `setClipboardData` 但未在微信后台声明"剪贴板" scope | `setClipboardData:fail api scope is not declared in the privacy agreement` | 后台隐私接口清单缺"剪贴板"项（读写共用一 scope） | 后台声明 + 调用前 `requirePrivacyAuthorize`（DS-14） |
| 媒体静音/桥接语义误判 | 媒体特性默认 bridge 模式让 BGM 在段间连续叠加，`amix` 把静音段与连续 BGM 混音 | 段间静音"看似无效"（设 2.5s 听起来像 0.5s） | 默认 bridge 掩盖静音；缺乏物理产出物验证 | 真静音用 `amix=inputs=2:duration=first` 仅主轨有声时叠加 BGM；做成可开关 silence/bridge（DS-15） |
| 枚举/开关校验器语义错位 | 校验器对空串抛 `ValueError` 但测试期望 `None`（继承全局） | 单测失败或被迫放宽校验 | 空串语义未约定为"继承全局" | 空串→`None`；合法值去空格归一化；非法值 `ValueError`；与测试断言对齐（DS-16） |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 核心判断信号 | 落地方式 |
|------|--------------|----------|
| 异常吞没检测 | grep `except Exception` 后仅 `str(e)` / 无 `exc_info` | DS-1：`logger.exception()` 或抛专用异常 |
| CancelledError 分支检测 | grep `wait_for`/`create_task` 包裹函数，`except` 顺序缺 `CancelledError` | DS-2：在 `Exception` 前补分支 |
| fire-and-forget 模式 | grep 同步函数内 `create_task` 无 `_tasks.add` / 无 `get_running_loop` 守卫 | DS-3：集合保活 + 运行循环守卫 + 测试禁用 |
| 时区显式赋值检测 | grep 时间字段 `default=func.now()` 或写入端用 `datetime.now(timezone.utc)` | DS-4：`localnow_naive()` 显式赋值 |
| 打包模式回退检测 | grep `is_cos_configured`/`sys.frozen` 无本地缺失回退分支 | DS-5：DB 远程 URL 回退 + SSRF 代理 |
| 元数据单一源检测 | grep `git_sha="unknown"` / 硬编码 `build_date` / `_build_info.py` 未被生成器覆盖 | DS-6：生成器派生 + 脚本刷新 |
| 参数有效性验证三步法 | 用户报"配了 X 却像 Y" | DS-7：定位真实产出物 → 验证参数落地 → 陈旧则查崩溃 |
| 重命名完整性验证 | grep 旧名非零匹配 | DS-8：全仓库 0 匹配 + 注释清理 + 审计日志保留 |
| 测试隔离重定向 | 测试用 `file_path.unlink()` 且依赖其成功 | DS-9：`tmp_path` + `monkeypatch` 重定向模块级路径 |
| 安装包图标完整性 | grep `installer.iss` 无 `SetupIconFile` | DS-10：复用产品图标 |
| frozen 模式配置加载 | grep `config.py` 的 `env_file` 为相对/固定路径、未用 `sys.executable` 同级解析 | DS-11：`_resolve_env_file()` 按 frozen 模式回退 |
| 安装包配置完整性 | grep `installer.iss` 的 `Excludes` 含 `.env`/密钥、或 `Source:` 未显式包含 `.env` | DS-12：显式包含 + 去隐藏属性 |
| HLS 首播冷启动 | grep 小程序音频播放 `onError` 无静默重试分支、无 mp3 回退 | DS-13：首次失败静默重试 + 协议回退 |
| 微信隐私 scope 声明 | grep `setClipboardData`/`wx.getClipboardData` 调用点，核对后台隐私清单含"剪贴板" | DS-14：后台声明 + 调用前授权 |
| 媒体特性可开关化 | grep 媒体开关字段无 silence/bridge 双模式 + `amix duration=first` 真静音实现 | DS-15：真静音 amix + 全局默认/频道覆盖双路径 + 幂等迁移 |
| 枚举/开关字段校验器语义 | grep 校验器对空串抛错或非法值静默接受、与测试断言不一致 | DS-16：空串→继承 None、去空格归一化、非法→ValueError、与断言对齐 |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 异常吞没检测 | 所有外部进程 / SDK / 子进程调用 | 明确要忽略的可恢复异常（须注释原因） |
| CancelledError 分支检测 | Python 3.10+（3.12+ 尤为关键）异步项目 | 纯同步代码、asyncio 旧版（3.8 前 CancelledError 属 Exception） |
| fire-and-forget 模式 | 同步签名函数内派发后台任务（不改变签名） | 直接 `await` 的协程、短期 `gather` 并发 |
| 时区显式赋值 | SQLite 下按本地日期做按日分桶的项目 | 多时区分布式服务（需显式 tz 存储） |
| 打包模式回退 | PyInstaller 冻结 exe / COS 已配置的生产部署 | 开发模式（无 COS，本地优先） |
| 元数据单一源 | 有版本发布流程的项目 | 无发布流程的一次性脚本 |
| 参数有效性验证 | 任何"配置不生效"类排查 | 纯逻辑错误（无物理产出物可查） |
| 重命名完整性验证 | 公共 API / 工具函数删除或重命名 | 局部变量重命名（影响范围小） |
| 测试隔离重定向 | 依赖模块级文件路径 / 单例的测试 | 纯内存单元测试（无文件系统依赖） |
| 安装包图标完整性 | Windows Inno Setup 安装包 | 非 Windows 发布 / 绿色版 |
| frozen 模式配置加载 | PyInstaller / Nuitka 等冻结 exe 部署 | 纯源码运行（解释器同目录即 `.env` 所在） |
| 安装包配置完整性 | 含密钥/配置（`.env`/证书）的安装包 | 配置全部走环境变量注入、包内无敏感文件 |
| HLS 首播冷启动 | 小程序/H5 用 `BackgroundAudioManager` 播 HLS(m3u8) | 纯本地 mp3 直链、无流式协议 |
| 微信隐私 scope 声明 | 微信小程序调用 `setClipboardData`/`getClipboardData` 等隐私接口 | 非微信平台、或接口无需隐私声明 |
| 媒体特性可开关化 | 媒体处理有"看似不生效"历史的特性（静音/BGM/混音开关） | 非媒体纯逻辑特性、无物理产出物可查 |
| 枚举/开关字段校验器语义 | 所有带枚举/开关的 Pydantic Body 字段（含频道级覆盖字段） | 纯无约束字符串、必填不可空字段 |

---

## 规范 DS-1：异常处理必须保留异常类型与 traceback（禁吞异常）

**外部进程 / SDK / 子进程调用必须包裹 try/except，抛出带异常类型与上下文（cmd）的专用异常；禁止 `except Exception as e: logger.error(str(e))` 吞掉真因。**

- 适用：所有 `subprocess` / `create_subprocess_exec` / 第三方 SDK 调用
- 不适用：明确要忽略的可恢复异常（须注释 `为什么可忽略`）
- 判断信号：`except Exception` 块内仅 `logger.warning(f"...{e}")` / `str(e)` 且无 `exc_info=True`；`create_subprocess_exec` 外层无 try/except
- 正确做法：
  ```python
  # ✅ 正确：启动异常统一转专用异常，保留类型 + cmd
  try:
      proc = await asyncio.create_subprocess_exec(*cmd, ...)
      await proc.communicate()
  except Exception as e:                       # 启动失败（文件缺失/权限/参数）
      raise StitchError(f"FFmpeg 启动失败({type(e).__name__}): {' '.join(cmd)}") from e

  # ❌ 错误：只记 str(e)，空串异常被吞
  except Exception as e:
      logger.error(str(e))                     # Aug 4 真因被吞，日志只有空串
  ```
- 真实案例：`ffmpeg_wrapper.run_ffmpeg` 启动异常 `str()` 为空，导致 Aug 4 工作流全部"步骤重试 error="空，真因长期不可见。

## 规范 DS-2：Python 3.12+ CancelledError 逃逸防护

**`asyncio.wait_for(func, timeout)` 包裹或任务可能被取消的场景，必须在 `except Exception` 之前补 `except asyncio.CancelledError`，记录 `exc_info` 并转为可读失败（取消不可重试，须 break）。**

- 适用：Python 3.10+（3.12+ 中 `CancelledError` 是 `BaseException` 子类，`except Exception` 捕获不到）；异步任务编排
- 不适用：纯同步代码；asyncio 3.8 之前（`CancelledError` 属 `Exception`，会被正常捕获）
- 判断信号：grep `wait_for` / `create_task` 的包裹函数，`except` 块顺序为 `Exception` 在前且无 `CancelledError` 分支
- 正确做法：
  ```python
  # ✅ 正确：CancelledError 在 Exception 之前
  try:
      await asyncio.wait_for(self._run_step(step), timeout=1800)
  except asyncio.CancelledError:
      logger.exception("步骤 %s 被取消（可能单步超时 1800s 或任务被外部取消）")
      step.status = "failed"; step.error = "步骤被取消"; break   # 取消不可重试
  except Exception as e:
      logger.exception("步骤 %s 执行失败: %s", step.id, e)
  ```
- 真实案例：Aug 5 工作流以空 error、空 failed_step 静默失败——正是 `CancelledError` 逃逸到任务层所致（完美匹配"0 步骤重试/完成、空错误"）。

## 规范 DS-3：异步 fire-and-forget 任务保活与守卫

**同步签名函数内派发后台协程时：仅在 `asyncio.get_running_loop()` 存在时派发；将任务加入模块级集合保活（asyncio 不持有 `create_task` 强引用，会被 GC 静默丢弃）；测试环境禁用派发；写库/外部调用失败仅 warning 不向上抛。**

- 适用：不改变同步签名的"落库/上报"副作用（如 `record_call` → `record_usage`）
- 不适用：直接 `await` 的协程；短期 `asyncio.gather` 并发（自动等待）
- 判断信号：grep 同步函数内 `asyncio.create_task` 无 `_tasks.add(...)` / 无 `get_running_loop()` 守卫
- 正确做法：
  ```python
  _DB_USAGE_DISPATCH_ENABLED = "pytest" not in sys.modules   # 测试禁用

  def record_call(record):
      ...  # 同步内存更新（不改变签名）
      if _DB_USAGE_DISPATCH_ENABLED and asyncio.get_running_loop():
          try:
              _db_usage_tasks.add(asyncio.create_task(_persist_usage_to_db(record)))
          except RuntimeError:
              pass   # 无运行循环（CLI/单测）直接跳过

  async def _persist_usage_to_db(record):
      try:
          async with AsyncSessionLocal() as s:
              await AIConfigService.record_usage(s, record)
      except Exception:
          logger.warning("落库失败（不拖垮主流程）", exc_info=True)
  ```
- 真实案例：`ai_budget.record_call` 从不调 `record_usage`，导致 `ai_usage_log` 永远空、用量统计全 0；修复引入 fire-and-forget 但须保活 + 测试禁用。

## 规范 DS-4：时区一致性（本地 naive 约定）与规范命名

**项目单机 UTC+8，所有时间存本地 naive datetime。SQLite 下模型 `server_default=func.now()` 返回 UTC，而按本地日期切分"今日"的区间会偏差 ~8h——写入端必须显式赋本地时间（`localnow_naive()`），不能依赖 `func.now()` 默认值。命名必须反映真实语义：删除 `utcnow_naive` 这类"名实不符"的误导别名。**

- 适用：按本地日期做按日分桶的统计/预算（如 `ai_budget_timezone` 规则）
- 不适用：多时区分布式服务（需显式 tz 存储与转换）
- 判断信号：grep 时间字段 `default=func.now()` 且无显式写入；grep 别名名与行为矛盾（如 `utcnow_naive` 实际返回 `datetime.now()`）
- 正确做法：
  ```python
  # timeutil.py：唯一规范实现
  def localnow_naive() -> datetime:
      """返回本地 naive datetime（香港 UTC+8，无夏令时）。"""
      return datetime.now()

  # 写入端显式赋值，规避 SQLite func.now() 的 UTC 偏差
  record.created_at = localnow_naive()
  ```
- 真实案例：AI 用量统计全 0 的根因之一——`server_default=func.now()` 返回 UTC 与本地"今日"区间错位；`localnow_naive()` 全量重命名消除"名实不符"误导。

## 规范 DS-5：打包模式（frozen/COS）路径解析与外部存储回退

**`sys.frozen`（PyInstaller 冻结 exe）且 COS 已配置时，TTS/成品不保留本地副本，前端 `list_audio` 读本地目录会返回空。列表接口本地缓存空后必须回退 DB 持久化远程 URL（`Script.segments[].audio_url` / `Episode`/`Review.audio_url`）；代理外部音频必须 SSRF 域名白名单 + 流式分块；前端对远程资源：`path` 返回语义值（如 `"云端(COS)"`）、`size_bytes` 未知置 0、删除按钮 `v-if` 排除远程。**

- 适用：exe / 打包部署且 `COS_BUCKET` 已配置
- 不适用：开发模式（无 COS，本地优先）
- 判断信号：grep `is_cos_configured` / `sys.frozen` 无本地缺失回退分支；grep `size_bytes` 远程未处理；grep 代理端点无 host 白名单
- 正确做法：
  ```python
  # 后端 list_audio：本地 tts 为空 → 回退 Script.segments[].audio_url（带 remote:true）
  # 新增 GET /{wf}/audio/proxy?url=：鉴权后代理拉取 COS 对象，SSRF 仅放行配置域名
  # 前端 ensureTtsBlob：remote 项走代理；删除按钮 v-if="!row.remote"
  ```
- 真实案例：打包模式工作流详情页"素材/TTS/成品"三面板空白——远端音频 URL 其实已在 DB，只是前端只读本地目录。

## 规范 DS-6：构建/发布元数据单一真相源

**版本号 / Git SHA / build_date 必须由生成器（`build_info.py`）从 `VERSION` 文件 + `git rev-parse` 派生；构建脚本（PyInstaller）与发布脚本（GitHub 发布）必须调用生成器刷新 `_build_info.py`；前端展示真实发布日需把 GitHub ISO 转 UTC+8。禁止在 `_build_info.py` 写死默认常量（`git_sha="unknown"` / `build_date="2026-07-20"`）。**

- 适用：有版本发布流程的项目
- 不适用：无发布流程的一次性脚本
- 判断信号：grep `git_sha="unknown"` / 硬编码 `build_date=` / `_build_info.py` 未被生成器覆盖
- 正确做法：
  ```python
  # build_info.py：version 优先级 = VERSION 文件 > 最近 git tag > 兜底 1.0.0
  #               git_sha = git rev-parse --short HEAD；build_date = UTC+8 当天
  # build-exe.ps1 在 PyInstaller 前跑；push_to_github.ps1 在收集文件前刷新
  # 前端 About.vue：_formatPublishedAt(iso) GitHub ISO → UTC+8 YYYY-MM-DD
  ```
- 真实案例：关于页 SHA 永远 unknown、版本永远显示"发布于 2026-07-20"——`_build_info.py` 长期未刷新，检查更新基于过期 `version="1.0.0"` 不可靠。

## 规范 DS-7：参数有效性验证（排除陈旧数据幻觉）

**怀疑"参数未生效"时，先定位真实产出物（音频文件时长/时间戳/日志参数）验证参数是否真正落地，再查整条流水线是否崩溃导致无新产出。陈旧残留冒充新产出是常见误判源——用户感知的"参数无效"往往是"从未产出新版本"。**

- 适用：任何"我配了 X 却像 Y"类排查（静音时长、语速、BGM 等）
- 不适用：纯逻辑错误（无物理产出物可查）
- 判断信号：用户报"配置了 X 但行为像默认值 Y"；优先查产出物时间戳与日志落参
- 正确做法：
  ```text
  1. 定位真实产出物：直接调用真实函数生成 gap.mp3 / main.mp3，确认参数（1.5s/2.5s）确实生效
  2. 验证参数落地：grep 日志确认 "段间静音=%.1fs" 记录的是新值
  3. 若产出物陈旧/缺失 → 不是参数问题，而是流水线在某步崩溃（查那一步的错误）
  ```
- 真实案例：频道静音设 2.5 听起来像 0.5——实因拼接/整条流水线崩溃，新 2.5 音频从未产出，旧 0.5 默认值残留。

## 规范 DS-8：全量重命名 / 别名移除完整性

**删除或重命名公共 API / 工具函数（如 `utcnow_naive` → `localnow_naive`）必须 grep 全仓库验证 0 匹配（覆盖 import、`default=`、调用、注释）；清理失效的矛盾注释（如"与 utcnow_naive 保持一致"）；历史审计日志（sonar 报告）保留原貌不重写。**

- 适用：公共 API / 工具函数删除或重命名（影响范围大）
- 不适用：局部变量重命名（影响范围小，IDE 即可）
- 判断信号：grep 旧名非零匹配（API import + `default=` + `()` 调用 + 注释）
- 正确做法：
  ```bash
  # 1. 一次性脚本批量替换（排除规范实现文件本身），用完即删
  # 2. 全仓库 grep 旧名 = 0 匹配，确认无 ImportError/NameError 泄漏
  grep -rn "utcnow_naive" backend/ docs/   # 期望：仅历史 sonar 报告（有意保留）
  # 3. 修正重命名后新出现的矛盾注释 + 文档示例
  ```
- 真实案例：`utcnow_naive` 全量重命名后，全量 pytest 374 passed / 0 failed，证明所有引用正确切换、删除别名无遗漏。

## 规范 DS-9：测试隔离与状态防泄漏（safe-delete 环境制品）

**依赖模块级文件路径 / 单例的测试，隔离不得依赖 `unlink()` 成功或真实文件系统状态——WorkBuddy safe-delete shim 会拦截删除（FAIL CLOSED）导致文件残留，进而被"按日 rollover 回填"逻辑读取造成计数泄漏。正确做法：用 `tmp_path` + `monkeypatch` 重定向模块级文件路径；autouse fixture 重置模块级单例/状态（计数、`_last_persist_date` 等）；报告中区分"代码失败" vs "环境制品"。**

- 适用：依赖模块级文件路径 / 单例的测试（如 `ai_budget`、TTLCache、`_build_info`）
- 不适用：纯内存单元测试（无文件系统依赖）
- 判断信号：测试用 `file_path.unlink()` 且依赖其成功；模块级文件路径未重定向到 `tmp_path`
- 正确做法：
  ```python
  @pytest.fixture(autouse=True)
  def _reset_ai_budget(tmp_path, monkeypatch):
      monkeypatch.setattr(ai_budget, "_budget_file_path", lambda: tmp_path / "ai_budget.json")
      ai_budget.reset_budget(); ai_budget._last_persist_date = ""
      yield
      ai_budget.reset_budget()
  ```
- 真实案例：`test_ai_budget` 两项断言 `total_calls==1` 实得 2——`reset_budget()` 的 `unlink()` 被 safe-delete 拦截，残留文件被 rollover 回填 +1 泄漏；重定向 `tmp_path` 后消失。

## 规范 DS-10：打包 / 安装配置完整性

**Windows Inno Setup 安装包必须配置 `SetupIconFile` 复用产品图标（`installer.iss` [Setup] 段）；exe 图标在 `MorningBrief.spec` 的 `EXE(..., icon=...)` 配置；构建脚本自动生成 `installer.iss` 的模板须同步加入同一行，保证重新生成一致。**

- 适用：Windows Inno Setup 安装包
- 不适用：非 Windows 发布 / 绿色免安装版
- 判断信号：grep `installer.iss` 无 `SetupIconFile`；`MorningBrief.ico` 为有效多尺寸 ICO（与 exe 同源）
- 正确做法：
  ```ini
  ; installer.iss [Setup]
  SetupIconFile=assets\MorningBrief.ico
  ```
- 真实案例：构建打包后 `setup.exe` 显示系统默认图标——exe 图标正确但安装包缺少 `SetupIconFile`。

## 规范 DS-11：PyInstaller frozen 模式配置加载路径解析

**PyInstaller（或 Nuitka）冻结的 exe 运行时，工作目录是 `_MEIPASS` 临时解压目录，而非 `.env` 所在目录。从配置加载（`python-dotenv` / Pydantic `BaseSettings`）必须按 frozen 模式回退到 `sys.executable` 同级目录解析 `.env`；禁止写死相对路径或固定路径，否则 exe 模式下 `Settings` 读不到 `WX_APPID` 等凭据，表现为"appid missing"。**

- 适用：PyInstaller / Nuitka 等冻结 exe 部署（单机 exe 是本项目标准部署方式）
- 不适用：纯源码运行（`python app/main.py`，解释器同级即 `.env` 所在，普通相对解析即可）
- 判断信号：`config.py` 中 `env_file` 为相对字符串（如 `env_file=".env"` 依赖 cwd）或固定绝对路径；未检查 `getattr(sys, 'frozen', False)`
- 正确做法：
  ```python
  # ✅ 正确：按 frozen 模式回退到 exe 同级目录解析 .env
  def _resolve_env_file() -> str:
      exe_dir = Path(sys.executable).parent          # 开发：venv/Scripts；冻结：dist/MorningBrief/
      if getattr(sys, "frozen", False):
          # PyInstaller 把 exe 放到 dist/MorningBrief/，.env 同目录随包分发
          candidate = exe_dir / ".env"
      else:
          candidate = Path(__file__).resolve().parents[2] / ".env"  # 开发：backend/.env
      return str(candidate)

  class Settings(BaseSettings):
      model_config = SettingsConfigDict(env_file=_resolve_env_file(), extra="ignore")
  # 验证：Settings().WX_APPID == 'wx1b4d58afd98bf2f6'

  # ❌ 错误：env_file 依赖进程 cwd，exe 模式下 cwd 是 _MEIPASS，找不到 .env
  class Settings(BaseSettings):
      model_config = SettingsConfigDict(env_file=".env")   # 冻结后读不到
  ```
- 真实案例：打包安装后微信登录一直 appid missing——`_MEIPASS` 临时目录无 `.env`，`config.py` 的相对 `env_file` 解析失败；改为 exe 同级解析后 `Settings().WX_APPID` 恢复为 `wx1b4d58afd98bf2f6`。

## 规范 DS-12：安装包配置完整性（.env / 密钥随包分发）

**Inno Setup（`installer.iss`）的 `Excludes` 会静默丢弃匹配文件，若把 `.env`（或证书/密钥文件）列入排除或构建脚本未显式 `Source:` 包含，打包后的安装包内将缺失该文件，运行时等同于 DS-11 的"读不到配置"。`Excludes` 清单必须与"随包分发的敏感/配置文件"清单双向核对；构建脚本拷贝 `.env` 后须清除其隐藏属性（`attrib -H`），否则 Inno Setup 可能因隐藏属性跳过包含。**

- 适用：含 `.env` / 证书 / 密钥的安装包（本项目 exe 部署依赖包内 `.env`）
- 不适用：配置全部通过环境变量注入、包内不含任何敏感/配置文件
- 判断信号：grep `installer.iss` 的 `Excludes` 含 `.env`/`*.env`/密钥；或 `Source:` 列表中无 `.env`；构建脚本拷贝 `.env` 后无 `attrib -H`
- 正确做法：
  ```ini
  ; installer.iss —— 禁止把 .env 列入 Excludes；显式包含随包 .env
  [Files]
  Source: "dist\MorningBrief\.env"; DestDir: "{app}"; Flags: ignoreversion
  ; 若有 Excludes，务必排除 .env：
  ; Excludes: "*.log;*.tmp"   ; 不得含 .env / *.env
  ```
  ```powershell
  # scripts/build-exe.ps1 —— 拷贝后去除隐藏属性，避免被安装包跳过
  Copy-Item "backend/.env" "dist/MorningBrief/.env" -Force
  attrib -H "dist/MorningBrief/.env"
  ```
- 真实案例：修好 DS-11（代码路径）后重打包仍 appid missing——`installer.iss` 的 `Excludes` 静默丢弃了 `.env`，包内无该文件；移除排除项并显式 `Source:` 包含 + `attrib -H` 后问题解决。

## 规范 DS-13：HLS / 音频首播冷启动静默重试与降级

**小程序 `BackgroundAudioManager` 首次播放 HLS（m3u8）流时，常因连接建立慢 / 解码器冷启动导致首播 `onError` 失败，但切集或重试后又能成功（"播放失败→成功"现象）。播放层必须对首播错误做**静默重试**（不向用户弹错误、不中断连续 loading 态），并在重试耗尽后回退到稳定协议（如 mp3 直链）；禁止把首播冷启动失败直接当作致命错误上报。**

- 适用：小程序 / H5 使用 `BackgroundAudioManager` 播 HLS(m3u8) 流式音频
- 不适用：纯本地 mp3 直链、无流式协议协商
- 判断信号：grep 音频 `onError` 处理直接 `showToast`/中断播放、无 `_retryHls` 重试分支、无 mp3 回退；`playEpisode` 在首播失败即停 loading
- 正确做法：
  ```javascript
  // ✅ 正确：首播 HLS 失败静默重试一次，耗尽回退 mp3；loading 持续
  const MAX_HLS_RETRY = 1;
  function _applyProtocol(episode) {
    return episode.hlsUrl && retryCount < MAX_HLS_RETRY ? episode.hlsUrl : episode.mp3Url;
  }
  audioManager.onError(() => {
    if (currentRetry < MAX_HLS_RETRY) {        // 静默重试，不弹错误
      currentRetry++;
      audioManager.src = _applyProtocol(episode);   // 回退 mp3
      audioManager.play();
    } else {
      wx.showToast({ title: '播放失败', icon: 'none' });
    }
  });
  // ❌ 错误：onError 直接 showToast 并停 loading，首播冷启动被误判为致命失败
  ```
- 真实案例：小程序首次播放某集失败、重试或切集后成功——正是 HLS 首播冷启动；加 `_retryHls` + `MAX_HLS_RETRY=1` + mp3 回退 + 连续 loading 后，首播失败自动恢复。

## 规范 DS-14：微信隐私合规（剪贴板等敏感 API 的 scope 声明）

**微信小程序调用 `setClipboardData` / `getClipboardData` 等隐私接口前，必须：(1) 在微信公众平台后台「用户隐私保护指引」中勾选对应接口类型并声明使用目的；(2) 代码侧在调用前触发隐私授权（`wx.requirePrivacyAuthorize` / `onNeedPrivacyAuthorization`），否则真机会报 `setClipboardData:fail api scope is not declared in the privacy agreement`。注意：后台接口类型名为「剪贴板」（读写共用同一 scope），并非「写入剪贴板」或 `setClipboardData` 字面量——声明名称要与后台一致。**

- 适用：微信小程序调用 `setClipboardData` / `getClipboardData` / 位置/相册等需隐私声明的接口
- 不适用：非微信平台、或接口不在微信隐私接口清单内
- 判断信号：grep `setClipboardData`/`wx.getClipboardData` 调用点，核对后台隐私清单是否含「剪贴板」；代码调用前无 `requirePrivacyAuthorize` 授权流程
- 正确做法：
  ```javascript
  // ✅ 正确：复制前先完成隐私授权（后台已声明「剪贴板」scope）
  function copyText(text) {
    wx.requirePrivacyAuthorize({
      success: () => wx.setClipboardData({ data: text, success: () => wx.showToast({ title: '已复制' }) }),
      fail: () => wx.showToast({ title: '复制被拒绝', icon: 'none' }),
    });
  }
  // 后台：用户隐私保护指引 → 勾选「剪贴板」并记录使用目的（读写同一 scope）
  // ❌ 错误：直接 setClipboardData 且后台未声明 → 真机 fail(api scope is not declared)
  ```
- 真实案例：小程序复制文案真机报 `setClipboardData:fail api scope is not declared in the privacy agreement`——后台隐私清单缺「剪贴板」声明（曾误搜「写入剪贴板」「setClipboardData」找不到，正确名称是「剪贴板」）；`copyText` 改为先 `requirePrivacyAuthorize` 后再复制。

## 规范 DS-15：媒体特性可开关化与真静音实现（silence/bridge + ffmpeg amix + 双路径覆盖 + 幂等迁移）

**媒体处理特性（段间静音/BGM/混音）的"默认行为"可能掩盖用户配置——用户感知的"参数无效"往往是缺省 bridge 模式把静音段淹没在连续 BGM 里。这类特性必须做成可开关（如 `bgm_gap_mode: silence|bridge`），全局默认值 + 频道级覆盖（双路径），且"静音"必须实现真静音语义（ffmpeg `amix=inputs=2:duration=first`，仅主音频有声时叠加 BGM，静音段自然无 BGM）。新增列必须幂等迁移（PRAGMA 检测后 `ALTER TABLE ADD COLUMN`）。**

- 适用：媒体处理有"看似不生效"历史的特性（静音时长/BGM/混音开关）
- 不适用：非媒体纯逻辑特性；无物理产出物（音频/视频文件）可查的参数
- 判断信号：
  - grep 媒体开关字段无 `silence`/`bridge` 双模式分支，或 `amix` 未用 `duration=first` 导致静音段仍叠加 BGM
  - grep 频道级字段覆盖未走"非 None 覆盖全局、None 继承"双路径（见 维度 114 / 规范 #39）
  - grep 新增列迁移无 `PRAGMA table_info` 幂等检测
- 正确做法：
  ```python
  # 后端：bgm_gap_mode 默认值在 settings（全局），频道表列允许 NULL 表示"继承全局"
  # 取值解析：channel.bgm_gap_mode or settings.BGM_GAP_MODE   # 双路径：非 None 覆盖
  # 真静音：仅主音频有声时在静音段叠加 BGM，静音段自然无 BGM
  #   ffmpeg ... -i main.mp3 -i bgm_loop.mp3 -filter_complex "
  #     [1:a]aloop=loop=-1:size=2e9[bgm];
  #     [0:a][bgm]amix=inputs=2:duration=first[out]" -map "[out]" out.mp3
  #   # duration=first → 输出长度=主音频；静音段（主音频无声）不额外引入 BGM
  # 迁移（幂等）：
  #   cols = [r[1] for r in cur.execute("PRAGMA table_info(channel)").fetchall()]
  #   if "bgm_gap_mode" not in cols:
  #       cur.execute("ALTER TABLE channel ADD COLUMN bgm_gap_mode VARCHAR(16)")
  ```
- 真实案例：频道段间静音设 2.5s 听起来像 0.5s——默认 bridge 模式让 BGM 在段间连续叠加，`amix` 把静音段与连续 BGM 混音，静音被 BGM 覆盖；改为 `bgm_gap_mode` 可开关（默认 silence 真静音）+ 频道级覆盖后，静音段不再被 BGM 淹没，且全局默认与单频道定制互不冲突。

## 规范 DS-16：枚举/开关字段校验器语义与测试断言对齐（空串→继承 None）

**所有带枚举/开关的 Pydantic Body 字段（含频道级覆盖字段）必须定义清晰的归一化语义：空串/`None` → 继承全局（返回 `None`，表示"跟随 settings 默认值"）；去空格后命中合法值 → 归一化为规范值；其余 → 抛 `ValueError`。校验器的归一化行为必须与单元测试断言、前端"继承/自定义"往返严格一致——测试期望 `None` 时校验器不得抛错，测试期望抛错时校验器必须拒绝。**

- 适用：所有带枚举/开关的 Pydantic Body 字段（含频道级覆盖字段，如 `bgm_gap_mode`）
- 不适用：纯无约束自由字符串；必填且不可为空的字段
- 判断信号：
  - grep 校验器对空串 `""` 抛 `ValueError`（应改为返回 `None` 表示继承）
  - grep 校验器对 `" bridge "`（带空格合法值）未 `.strip()` 归一化，或归一化后测试却期望抛错（语义错位）
  - 测试断言与校验器行为矛盾（一方期望 `None`、另一方抛错）
- 正确做法：
  ```python
  # ✅ 正确：空串/None → 继承全局（None）；去空格合法 → 归一化；其他 → ValueError
  @field_validator("bgm_gap_mode")
  @classmethod
  def _v(cls, v):
      if v is None:
          return None
      v = v.strip()
      if v == "":                      # 兜底前端 inherit 发送的脏输入 → 继承
          return None
      if v not in ("silence", "bridge"):
          raise ValueError("bgm_gap_mode 仅支持 silence / bridge")
      return v                        # 已归一化为规范小写

  # 测试必须与之对齐：
  #   assert validate("") is None          # 继承
  #   assert validate(" bridge ") == "bridge"   # 归一化
  #   with pytest.raises(ValueError): validate("weird")   # 拒绝
  ```
- 真实案例：`test_channel_bgm_gap_mode` 初版 3 失败——校验器对空串抛 `ValueError` 但测试期望 `None`；校验器把 `" bridge "` 归一化为 `"bridge"` 但测试期望抛错。根因是校验器语义与测试断言未对齐；修复为"空串→`None`"并重写测试覆盖 accept/normalize/empty→None/invalid-reject 四类的 22 条用例，全部通过。
