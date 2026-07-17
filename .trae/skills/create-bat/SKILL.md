---
name: "create-bat"
description: "Windows bat/ps1 脚本生成与诊断技能：覆盖纯 ASCII 策略、编码三元组、工具兼容性矩阵、依赖冲突排查、工具链 fallback、冒烟测试验证。Invoke when user asks to create/fix .bat or .ps1 scripts on Windows, especially with Chinese content, PowerShell calls, dependency management, or packaging workflows."
---

# Create Bat

Windows 中文环境下 .bat + .ps1 脚本的**生成、诊断、修复**技能。基于实战复盘抽象出固定流程，无硬编码，所有参数配置驱动。核心策略：.bat 纯 ASCII（零编码风险），.ps1 UTF-8 BOM（含中文业务逻辑）。

## 核心规则（必须遵守）

### 规则 1：编码策略（.bat 与 .ps1 规则不同）

**核心原则**：.bat 文件只含 ASCII 字符，所有中文输出委托给 .ps1。从源头消除编码问题，而非用编码三元组（文件编码 + chcp + BOM）补偿。

**.bat 文件**——cmd.exe 始终按系统 ANSI（中文 Win 为 GBK）解析 .bat 文件字节流，`chcp` 只改控制台输出代码页，**不影响 cmd 解析 .bat 文件本身**。但 .bat 委托 .ps1 输出中文时，`chcp` 必须与 .ps1 的 `[Console]::OutputEncoding` 匹配，否则 .ps1 输出的中文在 cmd 窗口乱码：

| 文件编码 | chcp | BOM | 非 ASCII 字节 | 状态 |
|----------|------|-----|-------------|------|
| 纯 ASCII（无中文输出） | 不需要 | 无 BOM | 0 | ✅ **首选-纯英文场景**（零编码风险，Write/Edit 工具可直接创建） |
| 纯 ASCII（委托 .ps1 输出中文） | `chcp 65001` | 无 BOM | 0 | ✅ **首选-中文输出场景**（.bat 仍纯 ASCII，chcp 让 cmd 控制台正确显示 .ps1 的 UTF-8 中文输出） |
| GBK（CP936） | `chcp 936` | 无 BOM | >0 | ⚠️ 备选（需 PowerShell `WriteAllText` 写入，Write/Edit 工具不支持 GBK） |
| UTF-8 | `chcp 65001` | 无 BOM | >0 | ❌ 不可靠（cmd 仍按 ANSI 解析文件，中文行被当作命令执行） |
| UTF-8 + BOM | 任意 | 有 BOM | >0 | ❌ 禁止（BOM 让 `@` 不在行首，`@echo off` 失效） |

**关键区分**：`chcp 65001` 对 .bat 文件本身的解析无影响（cmd 仍按 ANSI 解析文件字节），但对 .ps1 输出的中文显示有影响——控制台代码页必须与 .ps1 输出编码匹配。因此"纯 ASCII + chcp 65001"是安全组合（.bat 字节仍按 ANSI 解析，纯 ASCII 与 ANSI 兼容；控制台切到 UTF-8 后能正确显示 .ps1 的 UTF-8 输出）。

**.ps1 文件**——PowerShell 5.1（Win10 默认）按 BOM 判断编码，无 BOM 时按系统 ANSI（GBK）解析：

| 文件编码 | BOM | 状态 |
|----------|-----|------|
| UTF-8 with BOM | 有（`EF BB BF`） | ✅ 推荐（PS 5.1 + 7+ 均兼容） |
| UTF-8 无 BOM | 无 | ❌ PS 5.1 按 GBK 解析导致中文乱码 + 语法错误 |
| GBK | 无 | ⚠️ 仅纯英文可用 |

**工具兼容性矩阵**——选择编码策略时必须考虑创建/修改工具的限制：

| 工具 | 能写纯 ASCII？ | 能写 GBK？ | 能写 UTF-8 BOM？ | 能写 UTF-8 无 BOM？ |
|------|--------------|-----------|----------------|-------------------|
| Write | ✅ | ❌（默认 UTF-8） | ❌（默认无 BOM） | ✅（默认） |
| Edit | ✅ | ❌（默认 UTF-8） | ❌（默认无 BOM） | ✅（默认） |
| PowerShell `WriteAllText` | ✅ | ✅ | ✅ | ✅ |

**绝对禁止**：
- .bat 含 BOM（任何编码）
- .bat 含非 ASCII 字符且用 UTF-8 编码（cmd 按 GBK 解析导致乱码）
- .ps1 无 BOM 且含中文（PS 5.1 会乱码）
- 编码与 chcp 不匹配（中文 echo 行被当作命令执行）
- LF 行尾（cmd 不依赖 LF 作行边界，多字节字符被错误切分）

### 规则 2：强制 CRLF 行尾

所有 .bat 和 .ps1 文件**必须** CRLF（`\r\n`）。LF 会让 cmd 错误切分含多字节字符的行。

验证：文件中 `\x0A` 前必须有 `\x0D`，即孤立 LF 数应为 0。

### 规则 3：无硬编码，配置文件驱动

所有可变参数（项目名、版本号、路径、依赖列表、工具链路径、版本约束等）必须从配置文件读取。

配置文件格式选择：
- **JSON**：跨语言通用，但 bat 难解析（需 ps1 读取后透传）
- **ps1 变量文件**（`.ps1` 后缀，只含变量赋值）：可被 `. ps1` 直接加载，无需解析
- **YAML**：可读性好，但需额外依赖（PowerShell 内置无 YAML 解析器）

### 规则 4：分层架构

```
config.json          ← 声明式配置（所有参数）
  ↓
入口.bat (GBK)        ← 仅 echo 提示 + 调用 ps1，不含业务逻辑
  ↓
主逻辑.ps1 (UTF-8 BOM) ← 参数解析、步骤编排、工具调用、错误处理
  ↓
installer.iss (如需)  ← 安装包声明式配置
```

### 规则 5：进度反馈规范

长时间命令必须显示进度：
- 移除 `--quiet` 等压制输出的参数
- 每个步骤前加"预计耗时"提示
- 子步骤用编号（[1/9]、[2.1]、[2.2]）
- 失败时输出可操作的修复建议（不是泛泛的"失败了"）

### 规则 6：容错 fallback 链

外部工具查找必须多路径 fallback，不能假设单一安装位置。优先级：

1. **已验证版本的 $toolExe 同目录**（避免 PATH 中旧版优先，如 nodejs14 vs nodejs24）
2. PATH 中的命令（`Get-Command`）
3. 配置的常见安装路径（Program Files / LOCALAPPDATA）
4. winget 自动安装（`winget install --id <id> --silent`）
5. 直接下载静默安装
6. 跳过并提示用户手动安装

### 规则 7：依赖版本约束管理

Python 项目的依赖安装必须处理传递依赖冲突：

- pip 升级基础工具时固定版本约束（如 `setuptools<82` 兼容 torch 2.12+）
- 安装可能引入冲突的包后，显式降级冲突包（如 chromadb→huggingface-hub→typer<0.26.0）
- requirements.txt 锁文件必须与 ps1 中的版本约束保持一致
- 冒烟测试必须覆盖所有直接 import 的第三方包，不能只测 5 个

---

## 生成流程

### 步骤 1：需求分析

询问用户：
1. 脚本用途（打包/部署/启动/清理/环境配置等）
2. 调用链（bat → ps1 → 其他？）
3. 是否涉及中文 echo / 中文注释
4. 是否需要安装依赖工具链（Python/Node/Inno Setup 等）
5. 是否有传递依赖冲突需要处理
6. 配置文件位置与格式偏好

### 步骤 2：生成配置文件

生成 `config.json`，**所有字段使用占位符**，不含任何具体项目信息：

```json
{
  "project": {
    "name": "<PROJECT_NAME>",
    "version_source": "<PATH_TO_VERSION_FILE>",
    "root": "."
  },
  "runtime": {
    "python_min_version": [3, 10],
    "node_min_version": [18, 0],
    "venv_dir": "<VENV_DIR_NAME>",
    "venv_build_dir": "<VENV_BUILD_DIR_NAME>"
  },
  "dependencies": {
    "requirements_file": "requirements.txt",
    "pyproject_file": "pyproject.toml",
    "core_packages": [],
    "optional_packages": [],
    "version_constraints": {
      "<PACKAGE_NAME>": "<VERSION_CONSTRAINT>"
    }
  },
  "tools": {
    "<TOOL_NAME>": {
      "search_paths": [
        "<PATH_1>",
        "<PATH_2>"
      ],
      "winget_id": "<WINGET_ID>",
      "download_url": "<DOWNLOAD_URL>",
      "min_version": [0, 0, 0]
    }
  },
  "build": {
    "dist_dir": "<DIST_DIR>",
    "exe_name": "<EXE_NAME>",
    "spa_output_dir": "<SPA_OUTPUT_DIR>"
  },
  "service": {
    "name": "<SERVICE_NAME>",
    "port": <PORT>,
    "module": "<PYTHON_MODULE>",
    "args": "<STARTUP_ARGS>",
    "window_title": "<WINDOW_TITLE>",
    "stop_script": "<STOP_SCRIPT_FILENAME>",
    "port_wait_max_seconds": <PORT_WAIT_MAX_SECONDS>,
    "startup_max_retries": <STARTUP_MAX_RETRIES>,
    "startup_timeout": <STARTUP_TIMEOUT_SECONDS>,
    "log_file": "logs/<service>.log",
    "pid_file": "logs/<service>.pid"
  },
  "installer": {
    "enabled": false,
    "iss_file": "<ISS_FILE>",
    "output_dir": "<OUTPUT_DIR>"
  },
  "scan": {
    "enabled": false,
    "root_dir": "<DIST_DIR>",
    "non_recursive": true,
    "recursive_subdirs": ["config", "scripts", "static"],
    "exclude_dirs": ["_internal", "build", ".git"],
    "patterns": [
      {
        "name": "api_key",
        "regex": "sk-[A-Za-z0-9]{20,}",
        "description": "OpenAI/DeepSeek API Key 前缀"
      },
      {
        "name": "keyring_placeholder",
        "regex": "__MIGRATED_TO_KEYRING__",
        "description": "Keyring 迁移占位符"
      }
    ],
    "binary_extensions": [".exe", ".dll", ".pak", ".bin", ".dat", ".node", ".pyd", ".so"]
  },
  "global_params": {
    "<PARAM_NAME>": {
      "old_value": "<OLD_VALUE>",
      "new_value": "<NEW_VALUE>",
      "exclude_patterns": ["<EXCLUDE_REGEX_1>", "<EXCLUDE_REGEX_2>"],
      "scan_dirs": ["src", "scripts", "frontend/src", "config", "docs"],
      "exclude_dirs": ["node_modules", ".git", "__pycache__", "dist", "build"]
    }
  },
  "port_conflict": {
    "kill_same_project": true,
    "kill_other_project": false,
    "default_strategy": "ask_user",
    "fallback_port": null,
    "port_release_wait_seconds": 5
  },
  "encoding": {
    "bat_strategy": "<ascii|gbk>",
    "bat_chcp": "<CHCP_VALUE_OR_EMPTY>",
    "ps1_output_encoding": "<UTF8|GBK>",
    "ps1_bom": true,
    "line_ending": "CRLF"
  }
}
```

**config.json 字段说明**：

**config.json 字段说明**：完整字段定义见 config/schema.json。常用字段分组：project（名称/版本/描述）、encoding（编码策略）、entries（脚本入口数组）、	oolchain（工具链配置）、deploy（部署配置）、diagnoses（诊断规则）、uild_pipeline（构建流水线）、global_params（全局参数变更）、port_conflict（端口冲突策略）。所有字段均有默认值，按需覆盖。
### 步骤 3：生成 .bat 入口脚本

模板文件：	emplates/entry.bat.tmpl（普通入口）或 	emplates/build-entry.bat.tmpl（构建入口）。所有占位符从 config/template-meta.json 读取。

**编码**：纯 ASCII + CRLF + 无 BOM。所有 echo 内容为英文，中文输出委托 .ps1。

**关键规则**：
- <CHCP> 取值：委托 .ps1 输出中文 -> 65001；纯英文 -> 留空；GBK 备选 -> 936
- 所有占位符值必须为纯 ASCII
- setlocal 隔离环境变量
- 成功分支末尾用 pause >nul + exit /b 0（陷阱 8）

### 步骤 4：生成 .ps1 主逻辑脚本

模板文件：	emplates/main.ps1.tmpl。所有参数从 config.json 读取，无硬编码。

**编码**：UTF-8 with BOM + CRLF。

**关键规则**：
- 开头设置 [Console]::OutputEncoding 与 .bat chcp 匹配（陷阱 35）
- 工具查找：PATH -> 配置 search_paths -> winget 安装（陷阱 6）
- 依赖冲突：从 config.dependencies.version_constraints 读取版本约束
- 冒烟测试：验证 config.dependencies.smoke_test_modules 可导入
### 步骤 5：生成验证脚本

生成 `verify.ps1`（UTF-8 with BOM），用于验证所有文件规范：

```powershell
# 验证 .bat / .ps1 文件编码、行尾、BOM、非 ASCII 字节是否符合规范
# 用法: powershell -File verify.ps1 -TargetDir <DIR>

param(
    [Parameter(Mandatory=$true)][string]$TargetDir
)

$utf8Bom = [byte[]](0xEF, 0xBB, 0xBF)
$gbk = [System.Text.Encoding]::GetEncoding(936)
$pass = 0; $fail = 0

function Test-FileEncoding {
    param($path, $expectedEncoding, $expectBom)
    $b = [System.IO.File]::ReadAllBytes($path)
    $hasBom = ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
    $issues = @()

    # BOM 检查
    if ($expectBom -and -not $hasBom) { $issues += "Missing BOM" }
    if (-not $expectBom -and $hasBom) { $issues += "Unexpected BOM" }

    # 行尾检查（孤立 LF）
    $lf = 0
    for ($i=0; $i -lt $b.Length; $i++) {
        if ($b[$i] -eq 0x0A -and ($i -eq 0 -or $b[$i-1] -ne 0x0D)) { $lf++ }
    }
    if ($lf -gt 0) { $issues += "$lf orphan LF line endings" }

    # .bat 专有：非 ASCII 字节检查（纯 ASCII 策略）
    if ($expectedEncoding -eq 'ASCII') {
        $nonAscii = 0
        foreach ($byte in $b) {
            if ($byte -gt 127) { $nonAscii++ }
        }
        if ($nonAscii -gt 0) { $issues += "$nonAscii non-ASCII bytes (must be 0 for .bat)" }
    }

    # 编码可解码性（GBK 备选模式时检查）
    if ($expectedEncoding -eq 'GBK') {
        try { $null = $gbk.GetString($b) } catch { $issues += "Cannot decode as GBK" }
    }

    return @{ issues = $issues; hasBom = $hasBom; lf = $lf }
}

# 验证所有 .bat（纯 ASCII + 无 BOM）
Get-ChildItem $TargetDir -Filter '*.bat' -Recurse | ForEach-Object {
    $r = Test-FileEncoding $_.FullName 'ASCII' $false
    if ($r.issues.Count -eq 0) { Write-Host "[PASS] $($_.Name)" -ForegroundColor Green; $script:pass++ }
    else { Write-Host "[FAIL] $($_.Name): $($r.issues -join ', ')" -ForegroundColor Red; $script:fail++ }
}

# 验证所有 .ps1（UTF-8 + BOM）
Get-ChildItem $TargetDir -Filter '*.ps1' -Recurse | ForEach-Object {
    $r = Test-FileEncoding $_.FullName 'UTF8' $true
    if ($r.issues.Count -eq 0) { Write-Host "[PASS] $($_.Name)" -ForegroundColor Green; $script:pass++ }
    else { Write-Host "[FAIL] $($_.Name): $($r.issues -join ', ')" -ForegroundColor Red; $script:fail++ }
}

Write-Host ""
Write-Host "Total: $pass PASS, $fail FAIL" -ForegroundColor $(if ($fail -eq 0) {'Green'} else {'Red'})
exit $(if ($fail -eq 0) {0} else {1})
```

### 步骤 6：语法校验

```powershell
# .ps1 语法校验（PS 5.1 Parser）
$errors = $null; $tokens = $null
[System.Management.Automation.Language.Parser]::ParseFile($ps1Path, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Host "Line $($_.Extent.StartLineNumber): $($_.Message)" }
}
```

### 步骤 7：Edit 后 BOM 与编码验证

如使用 Edit 工具修改了 .ps1 文件，必须执行 BOM 检查流程（见"Edit 工具修改后的 BOM 检查流程"小节）。如修改了 .bat 文件，必须检查非 ASCII 字节数仍为 0。

验证清单：
- [ ] .bat 文件无 BOM（前 3 字节非 EF BB BF）
- [ ] .bat 文件非 ASCII 字节数 = 0（纯 ASCII 策略）
- [ ] .ps1 文件有 BOM（前 3 字节为 EF BB BF）
- [ ] .ps1 语法校验通过（PS Parser 无错误）
- [ ] 中文显示正确（.ps1 用 UTF-8 BOM 解码验证）

---

## 诊断流程（从报错识别问题）

### 决策速查表

按症状关键词快速定位问题类型和修复方向：

| 症状关键词 | 文件类型 | 首要检查 | 修复方向 |
|-----------|---------|---------|---------|
| 'XX' is not recognized | .bat | 前 6 字节（BOM/null残留） | 移除 BOM 或转纯 ASCII |
| 中文乱码 | .bat/.ps1 | 编码×chcp×BOM 三元组 | 见编码匹配矩阵 |
| ersion conflict / equires | 任意 | pip show + 约束方向 | 加版本约束重装 |
| 
pm ci / iscc 失败 | 任意 | lockfileVersion vs 工具版本 | 对齐版本或换已验证工具 |
| Ignoring invalid distribution ~ | venv | site-packages 中 ~前缀目录 | 删除残留目录 |
| 启动超时 / 端口占用 | 启动脚本 | 日志 -> netstat -> PID 归属 | 杀进程/换端口/加等待循环 |

### 编码匹配矩阵（.bat chcp <-> .ps1 OutputEncoding）

| .bat chcp | .ps1 OutputEncoding | 结果 | 修复 |
|-----------|-------------------|------|------|
| 65001 | UTF8 | OK | - |
| 936 | GBK | OK | - |
| 65001 | 未设置/GBK | FAIL | .ps1 加 [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 |
| 936 | UTF8 | FAIL | 统一为 chcp 65001 + UTF8 |
| 无 chcp | 未设置 | WARN | 显式设置 chcp |

### 端口冲突多进程处理要点

netstat 返回多行时：提取所有 PID（去重）-> Get-CimInstance Win32_Process 查命令行 -> 按是否含本项目路径判断归属 -> 同项目直接杀，其他项目询问 -> 杀后循环检测端口释放。

### 启动脚本健壮性检查清单

- [ ] 启动命令重定向到日志（> logs\<service>.log 2>&1）
- [ ] 启动前清空旧日志
- [ ] 端口清理后增加等待释放循环
- [ ] 失败时自动输出日志尾部到控制台
- [ ] PID 文件记录（供停止脚本复用）
- [ ] 进程存活验证（启动后检查 PID 是否运行）
---

## 全局参数变更流程

当项目中的全局参数（如端口、路径、版本号、API 端点）需要变更时，必须按以下流程执行，确保所有引用点同步更新，避免遗漏导致运行时错误。

### 步骤 1：扫描（Grep 全工作空间）

```
Grep pattern="<OLD_VALUE>" path="<PROJECT_ROOT>" output_mode="content" -n=true
```

- 扫描整个工作空间，找出所有包含旧值的位置
- 使用 `glob` 参数排除 `node_modules`、`.git` 等目录
- 记录所有匹配结果的文件路径和行号

### 步骤 2：分类（A/B/C/D 四类）

将扫描结果按影响范围分类：

| 类别 | 定义 | 处理方式 | 示例 |
|------|------|----------|------|
| **A 类（必改）** | 代码中的默认值、fallback 值、配置读取逻辑、测试断言、脚本中的实际使用 | 必须修改 | `port: int = 8000`、`assert cfg.port == 8000` |
| **B 类（必改）** | 部署配置文件（Docker、CI/CD、systemd） | 必须修改 | `docker-compose.yml` 的端口映射、`Dockerfile` 的 EXPOSE |
| **C 类（建议改）** | 文档中的示例 URL、启动命令说明、操作手册 | 建议修改（保持文档一致性） | `http://localhost:8000/app/` |
| **D 类（不改）** | 无关数值（金额、字符数、时间戳、API 常量、毫秒数、节点数） | 不修改 | `"amount": 8000`、`max_context_chars: 8000`、`0x80000000` |

**分类判断逻辑**：

1. 读取匹配行的上下文（前后各 2 行）
2. 判断该值是否为参数引用：
   - 是 → A/B/C 类
   - 否（金额/字符数/时间戳等）→ D 类
3. 判断文件类型：
   - 代码/脚本/测试 → A 类
   - Docker/CI/部署配置 → B 类
   - `.md` 文档 → C 类

### 步骤 3：询问（确认修改范围）

向用户展示分类结果，询问修改范围：
- 全部修改（A+B+C，推荐）
- 仅代码/脚本（A）
- 代码 + Docker（A+B）
- 不修改

### 步骤 4：修改（批量替换）

**修改规则**：

1. **同一文件的多个 Edit 必须顺序执行**（并行 Edit 存在竞争条件，后写入会覆盖先写入）
2. **不同文件的 Edit 可并行执行**
3. **使用 subagent 处理大量文档修改时**，明确告知「同一文件的多个 Edit 必须顺序执行」
4. **replace_all 替换时注意格式多样性**：
   - `:8000`（URL 中的端口）
   - `port 8000`（命令行参数）
   - `8000 端口`（中文描述）
   - `LocalPort 8000`（PowerShell 参数）
   - `port=8000`（Python 赋值）
   - `port: 8000`（YAML 配置）
   - 不能只替换单一格式，必须扫描所有出现位置并逐一确认
5. **Edit 工具修改 .bat 文件后必须重新读取验证**（Edit 默认 UTF-8 编码写回，.bat 需 GBK，可能导致修改未持久化）

### 步骤 5：验证（重新扫描确认无遗漏）

```
Grep pattern="<OLD_VALUE>" path="<PROJECT_ROOT>" output_mode="content" -n=true
```

- 重新扫描整个工作空间
- 确认剩余出现均为 D 类无关数值（金额、字符数、时间戳等）
- 若发现遗漏的 A/B/C 类引用 → 返回步骤 4 修复

**全局参数变更扫描检查清单**：

修改全局参数时，必须检查以下位置是否包含旧值引用：

- [ ] **配置文件**：config.yaml、config.example.yaml、.env.example
- [ ] **代码默认值**：Pydantic/BaseModel 字段默认值、typer.Option 默认值
- [ ] **代码 fallback 值**：try/except 中的兜底值、config 读取失败时的默认值
- [ ] **代码注释**：模块文档字符串中的启动示例、函数注释中的 URL
- [ ] **测试断言**：`assert cfg.port == <OLD_VALUE>`、测试固件中的端口引用
- [ ] **启动脚本**：.bat/.ps1 中的 `--port` 参数、netstat 端口扫描、echo 提示
- [ ] **停止脚本**：端口扫描、taskkill 命令
- [ ] **Docker 配置**：docker-compose.yml 端口映射、Dockerfile EXPOSE、healthcheck
- [ ] **CI/CD 配置**：.github/workflows、Jenkinsfile 中的端口引用
- [ ] **前端配置**：vite.config.ts 代理目标、package.json scripts
- [ ] **文档**：README.md、部署指南、操作手册中的示例 URL
- [ ] **其他脚本**：launcher.py、automation.ps1、setup-env.ps1、测试脚本

---

## 编码写入方法规范


**编码写入方法**：完整规范见 config/encoding-write-methods.md。核心原则：.bat 纯 ASCII 用 ASCII 编码写；.ps1 UTF-8 BOM 用 WriteAllText(path, text, UTF8Encoding(True))；Edit 修改 .ps1 后必须检查 BOM。



## Sandbox 限制处理策略


受限环境中执行脚本验证的限制及处理方式见 config/sandbox-strategies.md。核心原则：无法用 cmd /c 时用 PowerShell 直接读取字节验证；内联变量被吞时用临时 .ps1 文件。



## 常见陷阱与规避


**完整陷阱记录（37 条）**见 config/traps.md。


**高频陷阱速查**：


| 编号 | 症状 | 规避 |
|------|------|------|
| T1 | UTF-8 BOM 让 .bat @echo off 失效 | .bat 禁止任何 BOM |
| T2 | .ps1 无 BOM 在 PS 5.1 乱码 | .ps1 必须 UTF-8 BOM |
| T3 | chcp 65001 不能修复 .bat 乱码 | .bat 用纯 ASCII 策略 |
| T4 | LF 行尾切分多字节字符 | 强制 CRLF |
| T5 | PATH 旧版工具优先 | 用已验证版本的同目录路径 |
| T6 | 传递依赖冲突 | 用 version_constraints 固定 |
| T7 | lockfileVersion 与 npm 不匹配 | 检查 npm >= 7 |
| T8 | winget 装到用户目录 | 检查 ProgramFiles 目录 |
| T9 | pip 卸载残留 ~前缀目录 | 启动脚本加自动清理 |
| T10 | 冒烟测试覆盖不全 | 从 config.dependencies 读取完整列表 |
| T11 | UTF8Encoding.GetBytes 不写 BOM | 用 WriteAllText 而非 GetBytes |
| T12 | GetEncoding 三参数不支持 | 用默认 GetEncoding(936) |
| T13 | 启动命令未重定向日志 | 加 > logs 重定向 |
| T14 | 端口释放延迟 | 加等待释放循环 |
| T15 | Edit 修改 .ps1 后丢失 BOM | 修改后检查并重写 BOM |
| T16 | wmic 查询输出为空 | 用 Get-CimInstance 替代 |
| T17 | replace_all 格式遗漏 | 先 Grep 扫描所有位置 |
| T18 | subagent 并行修改竞争 | 同文件 Edit 顺序执行 |
| T19 | 全局参数变更遗漏默认值 | 参照 traps.md 检查清单 |
| T20 | netstat 多进程监听 | 提取所有 PID 去重处理 |
| T21 | Edit 修改 .bat 未持久化 | 改用纯 ASCII 策略 |
| T22 | chcp 65001 不能使 cmd 用 UTF-8 解析 .bat | .bat 坚持纯 ASCII |
| T23 | Write 工具无法创建 GBK .bat | 用 PowerShell WriteAllText |
| T24 | UTF-8 无 BOM + chcp 65001 仍乱码 | .bat 用纯 ASCII |
| T25 | ESM 模式下 __dirname 未定义 | 添加 __dirname 回退 |
| T26 | BOM 修复失败 null 字节残留 | 用 UTF8Encoding(True) |
| T27 | 修复后文件被旧版本覆盖 | 修复后立即验证 + git status |
| T28 | .bat chcp 与 .ps1 输出编码不匹配 | 见编码匹配矩阵 |
| T29 | pip 升级传递依赖冲突 | 用 version_constraints 固定 |
| T30 | Inno Setup 编译失败未终止 | 每步检查 LASTEXITCODE + throw |
| T31 | CJS 打包 import.meta 为空 | 添加 __dirname 回退 |
| T32 | Inno Setup 语言文件缺失 | 仅注册实际安装的语言文件 |
| T33 | Inno Setup 架构标识符弃用 | 用 x64compatible |
| T34 | 双击 .bat 窗口立即关闭 | 用 pause >nul + exit /b 0 |
| T35 | 应用启动后窗口关闭 | 同上 |
| T36 | 服务端口冲突 | 端口检查逻辑 + 等待释放 |
| T37 | 路径含中文未引号包裹 | 中文路径必须用双引号 |



## 模板套件


本技能生成以下文件套件：


**模板文件**：	emplates/entry.bat.tmpl、	emplates/build-entry.bat.tmpl、	emplates/main.ps1.tmpl。所有占位符映射见 config/template-meta.json。


**服务启动脚本模板**：包含端口清理、依赖检查、启动、日志重定向、PID 记录、存活验证等完整健壮性要素。完整模板见 config/service-startup-template.md。


**全局参数变更扫描脚本模板**：从 config.json 读取参数配置，支持 scan/verify 模式。完整模板见 config/scan-global-params-template.md。


**端口冲突诊断脚本模板**：多进程端口冲突诊断，区分同项目/其他项目进程。完整模板见 config/port-conflict-template.md。


## 适用场景

- Windows 中文环境下的 .bat + .ps1 自动化脚本生成
- AI 辅助编程环境（Write/Edit 工具默认 UTF-8，不支持 GBK 写入）
- 需要 .bat + .ps1 分层架构的项目（.bat 纯 ASCII 入口 + .ps1 UTF-8 BOM 业务逻辑）
- 需兼容 PowerShell 5.1（Win10 默认）的脚本
- PyInstaller 打包项目
- 需要自动安装依赖工具链的场景（Python/Node/Inno Setup）
- 有传递依赖冲突的 Python 项目环境配置
- 需要制作 Inno Setup 安装包的项目
- 需要从报错诊断编码/依赖/工具问题的场景
- **服务启动脚本生成（含端口管理、日志重定向、失败诊断）**
- **服务启动失败排查（端口占用、日志缺失、进程崩溃）**
- **用 PowerShell 操作文件编码（GBK/UTF-8 BOM 转换）**
- **受限环境（Sandbox）下的脚本验证**
- **全局参数变更（端口/路径/版本号/API端点等全局替换，含扫描→分类→修改→验证闭环）**
- **多项目端口冲突诊断（区分同项目旧进程 vs 其他项目进程，自动或交互式处理）**
- **ESM/CJS 模块兼容（__dirname 在 ESM 下的派生）**

## 不适用场景

- 跨平台脚本（应改用 Python/Node 跨平台方案）
- Linux/macOS 环境（无 cmd、无 chcp、PS 7+ 默认 UTF-8）
- 手动用记事本创建 GBK .bat 文件（可直接用 GBK + chcp 936，无需纯 ASCII 策略）
- 纯 .ps1 脚本无 .bat 入口（无需 .bat 编码规则，但仍需 .ps1 BOM）
- 仅 PowerShell 7+ 专用项目（默认 UTF-8 无需 BOM）
- 单次性配置变更（如修改 config.yaml 一个字段，无需全局扫描）
- 跨仓库参数变更（需多仓库协调，超出单工作空间范围）

---
## 调用示例

以上述生成流程和诊断流程为主，以下为典型场景的快速索引：

| 场景 | 用户指令示例 | 对应流程 |
|------|------------|---------|
| 创建打包脚本 | 创建 PyInstaller 打包脚本 | 生成流程（步骤1-7） |
| 诊断编码报错 | '脚本' is not recognized | 诊断流程 A（编码问题） |
| 诊断依赖冲突 | pip version conflict | 诊断流程 B（依赖冲突） |
| 诊断启动失败 | 服务启动超时 | 诊断流程 E（服务启动） |
| 批量修复乱码 | 所有脚本中文乱码 | 编码写入规范 + 模板套件 |
| 全局参数变更 | 端口从 8000 改为 8001 | 全局参数变更流程 |
| 端口冲突诊断 | 端口被占用 | 诊断流程 E + 多进程处理 |

详细步骤参见上方各流程章节。

## 快速参考：常见陷阱速查

### 陷阱 1：双击 .bat 后 "xxx 不是内部或外部命令"
- **根因**：.bat 中调用的命令不在 PATH 中，或路径含中文但未引号包裹
- **规避**：.bat 开头用 call 激活 venv 或设置 PATH；中文路径必须用双引号

### 陷阱 2：.bat 中中文乱码
- **根因**：文件编码与 chcp 不匹配
- **规避**：.bat 用 GBK 编码 + chcp 936 + 无 BOM + CRLF

### 陷阱 3：.ps1 中中文乱码或语法错误
- **根因**：UTF-8 无 BOM 导致 PS 5.1 按 GBK 解析
- **规避**：.ps1 必须 UTF-8 with BOM + CRLF

### 陷阱 4：.ps1 执行策略阻止运行
- **根因**：ExecutionPolicy 为 Restricted
- **规避**：.bat 中调用时使用 powershell -ExecutionPolicy Bypass -File xxx.ps1

### 陷阱 5：LF 行尾导致多字节字符被切分
- **根因**：cmd 不依赖 LF 作为行边界
- **规避**：所有脚本强制 CRLF，用 verify-encoding.ps1 检查

### 陷阱 6：config.json 路径硬编码
- **根因**：脚本中写死了 config.json 的路径
- **规避**：使用 $PSScriptRoot 或 Resolve-Path 相对路径动态计算

### 陷阱 7：.bat 中 %ERRORLEVEL% 被后续命令覆盖
- **根因**：powershell 之后插入了其他命令
- **规避**：powershell 执行后立即读取 %ERRORLEVEL%，存入变量

### 陷阱 8：应用启动后 .bat 窗口立即关闭
- **现象**：双击 .bat 后窗口一闪而过
- **根因**：成功分支末尾是 exit 而非 pause
- **规避**：.bat 成功分支使用 pause >nul + exit /b 0

### 陷阱 9：服务端口冲突
- **现象**：服务启动失败，提示 Address already in use
- **规避**：在 config.json 中配置端口检查逻辑

### 陷阱 10：Inno Setup 编译失败未终止构建
- **现象**：iscc 失败但脚本继续执行，最终显示成功
- **根因**：使用 Write-Warn 而非 throw 处理编译失败
- **规避**：每个子步骤检查 $LASTEXITCODE 并使用 throw

### 陷阱 11：CJS 打包时 import.meta.url 为空
- **现象**：esbuild 打包为 CJS 后，运行时报 Cannot read property url of undefined
- **根因**：CJS 格式不支持 import.meta
- **规避**：添加 __dirname 优先回退逻辑

### 陷阱 12：Inno Setup 语言文件缺失
- **现象**：Could not open include file ChineseSimplified.isl
- **根因**：安装的 Inno Setup 不包含简体中文翻译文件
- **规避**：仅注册系统实际安装的语言文件，使用 compiler:Default.isl 兜底

### 陷阱 13：Inno Setup 架构标识符弃用
- **现象**：Architecture identifier x64 is deprecated
- **根因**：Inno Setup 6.7+ 引入了新的架构标识符规范
- **规避**：使用 x64compatible 替代 x64



## 补充规则（来自源版本）

### 规则：CJS 打包 import.meta 兼容性
当使用 esbuild 将 ESM 代码打包为 CJS 时，import.meta.url 会变为空对象。
修复方式：添加 __dirname 优先回退逻辑：
```typescript
const here = typeof __dirname === "string"
  ? __dirname
  : path.dirname(fileURLToPath(import.meta.url));
```
在 config 中通过 `import_meta_compat: true` 标记需要此兼容性的步骤。

### 规则：Inno Setup 架构标识符
Inno Setup 6.7+ 弃用了 x64 标识符，改用 x64compatible。
在 `config.deploy.installer.architecture` 中配置，默认值为 `x64compatible`。

### 规则：构建流水线配置化
多步骤构建（如 pkg+esbuild+Inno Setup）应通过 `config.build_pipeline` 定义：
- `steps[].id`：步骤唯一 ID，用于依赖追踪
- `steps[].depends_on`：前置步骤 ID
- `steps[].on_fail`：失败处理策略（stop/warn/skip）
- `steps[].skip_flag`：对应的跳过标志（如 -SkipSPA）
- `artifacts[].required`：产物是否必需

### 规则：工具链多路 fallback
外部工具查找必须多路 fallback，不能假设单一安装位置。优先级：
1. 已验证版本的同目录
2. PATH 中的命令
3. 配置的常见安装路径
4. winget 自动安装
5. 直接下载静默安装
6. 跳过并提示用户手动安装

