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

| 配置段 | 字段 | 含义 | 示例值 |
|--------|------|------|--------|
| `project` | `name` | 项目名称 | `"XianyuHunter"` |
| `project` | `version_source` | 版本号文件路径 | `"src/xianyu_hunter/__init__.py"` |
| `runtime` | `venv_dir` | 虚拟环境目录名 | `".venv"` |
| `service` | `port` | 服务监听端口 | `8001` |
| `service` | `module` | Python 启动模块 | `"xianyu_hunter"` |
| `service` | `args` | 启动参数 | `"web --port 8001"` |
| `service` | `port_wait_max_seconds` | 端口等待释放最大秒数 | `5` |
| `service` | `startup_max_retries` | 启动就绪检测重试次数 | `15` |
| `service` | `startup_timeout` | 启动超时秒数（=重试次数 × 2） | `30` |
| `scan` | `enabled` | 是否启用敏感信息扫描 | `true` |
| `scan` | `root_dir` | 扫描根目录 | `"dist/xianyu-hunter"` |
| `scan` | `non_recursive` | 根目录是否非递归扫描 | `true` |
| `scan` | `recursive_subdirs` | 递归扫描的子目录列表 | `["config", "scripts", "static"]` |
| `scan` | `exclude_dirs` | 排除扫描的目录列表 | `["_internal", "build"]` |
| `scan` | `patterns` | 扫描正则模式列表 | `[{"name": "api_key", "regex": "sk-[A-Za-z0-9]{20,}"}]` |
| `scan` | `binary_extensions` | 跳过的二进制文件扩展名 | `[".exe", ".dll", ".pak"]` |
| `global_params` | `<PARAM_NAME>` | 全局参数名（如 port、host、path） | `"port"` |
| `global_params` | `old_value` | 参数旧值（扫描目标） | `"8000"` |
| `global_params` | `new_value` | 参数新值（替换为） | `"8001"` |
| `global_params` | `exclude_patterns` | 排除的正则模式（金额/字符数/时间戳等无关数值） | `["max_context_chars.*8000", "amount.*8000"]` |
| `global_params` | `scan_dirs` | 扫描目录列表 | `["src", "scripts", "docs"]` |
| `global_params` | `exclude_dirs` | 排除目录列表 | `["node_modules", ".git"]` |
| `port_conflict` | `kill_same_project` | 是否自动杀同项目旧进程 | `true` |
| `port_conflict` | `kill_other_project` | 是否自动杀其他项目进程（false=询问用户） | `false` |
| `port_conflict` | `default_strategy` | 端口冲突默认策略（ask_user/kill/change_port） | `"ask_user"` |
| `port_conflict` | `fallback_port` | 换端口时的备用端口号（null=自动递增） | `null` |
| `port_conflict` | `port_release_wait_seconds` | 杀进程后等待端口释放的最大秒数 | `5` |
| `encoding` | `bat_strategy` | .bat 编码策略（ascii=纯 ASCII 首选 / gbk=GBK 备选） | `"ascii"` |
| `encoding` | `bat_chcp` | .bat 中的 chcp 值（委托 .ps1 输出中文填 `"65001"`，纯英文填 `""`，GBK 模式填 `"936"`） | `"65001"` |
| `encoding` | `ps1_output_encoding` | .ps1 控制台输出编码（UTF8=匹配 chcp 65001 / GBK=匹配 chcp 936） | `"UTF8"` |
| `encoding` | `ps1_bom` | .ps1 是否带 UTF-8 BOM（PS 5.1 需要 BOM 解析中文） | `true` |
| `encoding` | `line_ending` | 行尾格式（CRLF 固定，cmd 解析 .bat 必须） | `"CRLF"` |

### 步骤 3：生成 .bat 入口脚本

模板（纯 ASCII + CRLF + 无 BOM）。`<CHCP>` 占位符由 config.json 的 `encoding.bat_chcp` 决定（委托 .ps1 输出中文时填 `65001`，纯英文项目填空）。所有占位符值也必须为 ASCII（中文输出由 .ps1 处理）：

```bat
@echo off
REM <SCRIPT_DESCRIPTION>
REM Keep this entry script ASCII-only for reliable cmd.exe parsing.
chcp <CHCP> >nul 2>&1
setlocal

cd /d "%~dp0.."

echo ============================================
echo   <PROJECT_NAME> <SCRIPT_PURPOSE>
echo ============================================
echo.
echo <FLOW_DESCRIPTION>
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0<main>.ps1" %*
set "ENTRY_EXIT_CODE=%ERRORLEVEL%"

if not "%ENTRY_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] <ERROR_MESSAGE>
    pause
    exit /b %ENTRY_EXIT_CODE%
)

echo.
echo Press any key to close this window...
pause >nul
exit /b 0
```

**占位符规则**：
- `<PROJECT_NAME>`、`<SCRIPT_PURPOSE>`、`<FLOW_DESCRIPTION>`、`<ERROR_MESSAGE>` 必须为纯 ASCII（英文）。如需中文提示，在 .ps1 中用 `Write-Host` 输出。
- `<CHCP>` 取值规则（从 config.json `encoding.bat_chcp` 读取，生成时注入）：
  - 委托 .ps1 输出中文 → `65001`（控制台切 UTF-8，匹配 .ps1 的 UTF-8 输出）
  - 纯英文项目 → 留空（生成时移除 `chcp` 行，或写 `chcp >nul 2>&1` 无操作）
  - 备选 GBK 模式 → `936`（不推荐，需 .bat 含 GBK 中文且 .ps1 输出 GBK）
- `setlocal` 保证 .bat 内的环境变量不泄漏到调用方 shell，`endlocal` 在 .bat 结束时自动调用。

### 步骤 4：生成 .ps1 主逻辑脚本

模板（UTF-8 with BOM + CRLF）。从 config.json 的 `encoding` 段读取控制台输出编码，确保 .ps1 中文输出与 .bat 的 `chcp` 匹配：

```powershell
#Requires -Version 5.1
# <SCRIPT_DESCRIPTION>
# 配置驱动：所有参数从 config.json 读取，无硬编码

param(
    [string]$ConfigPath = "$PSScriptRoot\config.json",
    [switch]$Force,
    [switch]$SkipSystem,
    [switch]$SkipFrontend
)

# 加载配置
if (-not (Test-Path $ConfigPath)) { throw "配置文件不存在: $ConfigPath" }
$Config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

# --- 控制台输出编码对齐 ---
# 从 cmd.exe 调用时，.ps1 默认按系统 ANSI 输出，与 .bat 的 chcp 65001 不匹配导致中文乱码
# 必须强制 .ps1 输出编码与 .bat 的 chcp 一致（encoding.ps1_output_encoding 配置）
try {
    $outputEncName = if ($Config.encoding.ps1_output_encoding) { $Config.encoding.ps1_output_encoding } else { 'UTF8' }
    if ($outputEncName -eq 'UTF8') {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $OutputEncoding = [System.Text.Encoding]::UTF8
    } elseif ($outputEncName -eq 'GBK') {
        $gbkEnc = [System.Text.Encoding]::GetEncoding(936)
        [Console]::OutputEncoding = $gbkEnc
        $OutputEncoding = $gbkEnc
    }
} catch {
    # 某些宿主（如 ISE、VS Code 终端）不支持设置输出编码，忽略错误
    # 此时中文显示取决于宿主自身的编码配置
}

# --- 工具函数 ---
function Find-Tool {
    param($ToolConfig)
    # 1. 已验证版本的 $toolExe 同目录（调用方传入时优先）
    # 2. PATH
    $cmd = Get-Command $ToolConfig.name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    # 3. 配置的搜索路径
    foreach ($p in $ToolConfig.search_paths) {
        $expanded = $ExecutionContext.InvokeCommand.ExpandString($p)
        if (Test-Path $expanded) { return $expanded }
    }
    return $null
}

function Install-ToolViaWinget {
    param($ToolConfig)
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
    winget install --id $ToolConfig.winget_id --silent --accept-package-agreements --accept-source-agreements
    # 刷新 PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    return $true
}

function Invoke-Safe {
    param([scriptblock]$Block, [string]$Description)
    Write-Host "[进行中] $Description ..." -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        throw "[FAIL] $Description 失败：退出码 $LASTEXITCODE"
    }
    Write-Host "[OK] $Description" -ForegroundColor Green
}

# --- 依赖冲突管理 ---
# pip 升级基础工具时固定版本约束（从 config.dependencies.version_constraints 读取）
$upgradeArgs = @("install", "--upgrade", "pip")
foreach ($pkg in $Config.dependencies.version_constraints.PSObject.Properties.Name) {
    $upgradeArgs += "$pkg$($Config.dependencies.version_constraints.$pkg)"
}
Invoke-Safe { & $VenvPython -m pip @upgradeArgs } "升级基础工具"

# 清理 pip 卸载残留（~前缀目录）
$brokenDists = Get-ChildItem (Join-Path $VenvDir "Lib\site-packages") -Directory -Filter '~*' -ErrorAction SilentlyContinue
if ($brokenDists) {
    foreach ($d in $brokenDists) { Remove-Item -Recurse -Force $d.FullName -ErrorAction SilentlyContinue }
}

# --- 冒烟测试（覆盖所有直接 import 的第三方包）---
$smokeModules = $Config.dependencies.smoke_test_modules -join ", "
$importCheck = (& $VenvPython -c "import $smokeModules; print('ok')" 2>&1) -join "`n"
if ($importCheck -notmatch 'ok$') {
    throw "Python 依赖校验失败：$importCheck"
}
```

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

### 诊断流程 A：编码问题（"'XX' is not recognized" 或中文乱码）

```
症状："'脚本' is not recognized" / 中文显示乱码 / '锘緻echo' is not recognized / .ps1 输出中文在 cmd 窗口乱码
  │
  ├─ 出错文件类型？
  │   ├─ .bat
  │   │   ├─ 读前 6 字节（检测 BOM + null 残留）
  │   │   │   ├─ 00 00 00 → null 字节残留（前次 BOM 修复失败），先移除前 3 字节
  │   │   │   ├─ EF BB BF → 含 BOM，需移除（BOM 让 @echo off 失效）
  │   │   │   └─ 非 EF BB BF → 检查非 ASCII 字节数
  │   │   ├─ 检查非 ASCII 字节数
  │   │   │   ├─ = 0 → 纯 ASCII，.bat 文件本身编码无问题
  │   │   │   │   ├─ 检查 chcp 行是否与 .ps1 输出编码匹配（见下方"编码匹配检查"）
  │   │   │   │   └─ 如 .bat 委托 .ps1 输出中文，chcp 应为 65001 且 .ps1 应设 UTF8 输出
  │   │   │   └─ > 0 → 含非 ASCII 字符（cmd 按 GBK 解析导致乱码）
  │   │   │       ├─ 检查 chcp 行
  │   │   │       │   ├─ chcp 65001 → ❌ 不可靠（cmd 仍按 ANSI 解析文件本身，陷阱 30/32）
  │   │   │       │   └─ chcp 936 + GBK → 可行但 Write/Edit 工具不支持 GBK
  │   │   │       └─ 推荐修复：移除所有非 ASCII 字符，中文委托给 .ps1
  │   │   └─ 修复优先级：
  │   │       1. 【首选】改纯 ASCII + chcp 65001（移除中文 echo/注释，中文输出移至 .ps1）
  │   │       2. 【备选】转 GBK + chcp 936（需 PowerShell WriteAllText，非 Write 工具）
  │   │
  │   └─ .ps1
  │       ├─ 读前 6 字节（检测 BOM + null 残留）
  │       │   ├─ 00 00 00 → null 字节残留，先移除前 3 字节再检测 BOM
  │       │   ├─ EF BB BF → ✅ 有 BOM
  │       │   └─ 非 EF BB BF → 缺 BOM，PS 5.1 按 GBK 解析
  │       ├─ 检查 [Console]::OutputEncoding 是否设置
  │       │   ├─ 已设置且与 .bat chcp 匹配 → 编码无问题（查其他原因）
  │       │   └─ 未设置或不匹配 → .ps1 中文输出在 cmd 窗口乱码（陷阱 35）
  │       │       └─ 修复：.ps1 开头加 [Console]::OutputEncoding 设置块
  │       └─ 修复：加 UTF-8 BOM + 加 [Console]::OutputEncoding 设置
  │
  ├─ 编码匹配检查（.bat chcp ↔ .ps1 OutputEncoding）：
  │   ├─ 读 .bat 的 chcp 行（如 `chcp 65001 >nul 2>&1`）
  │   ├─ 读 .ps1 是否含 [Console]::OutputEncoding 设置
  │   ├─ 匹配矩阵：
  │   │   ├─ chcp 65001 + .ps1 UTF8 输出 → ✅ 匹配
  │   │   ├─ chcp 936 + .ps1 GBK 输出 → ✅ 匹配
  │   │   ├─ chcp 65001 + .ps1 未设置/GBK 输出 → ❌ 不匹配（中文乱码）
  │   │   ├─ chcp 936 + .ps1 UTF8 输出 → ❌ 不匹配（中文乱码）
  │   │   └─ .bat 无 chcp + .ps1 未设置 → ⚠️ 依赖系统默认（GBK），不可靠
  │   └─ 修复：.bat 加 chcp 65001 + .ps1 加 [Console]::OutputEncoding = UTF8
  │
  └─ 验证：Parser::ParseFile 无错误 + 非 ASCII 字节数符合预期 + chcp 与 OutputEncoding 匹配 + 中文字符正常显示
```

### 诊断流程 B：依赖版本冲突（pip 报 version conflict）

```
症状："X requires Y<version, but you have Y<another_version>"
  │
  ├─ 读约束方向：A requires B<constraint
  ├─ 查 B 当前版本：pip show B
  ├─ 查 B 版本来源：
  │   ├─ requirements.txt 锁定 → 需同步更新锁文件
  │   ├─ pip install --upgrade → 需加版本约束
  │   └─ 传递依赖引入 → 需显式降级
  ├─ 修复：
  │   ├─ pip install "B<constraint"
  │   └─ 同步更新 requirements.txt 中 B 的版本
  └─ 验证：pip check 无冲突
```

### 诊断流程 C：工具版本不兼容（npm ci / iscc 失败）

```
症状：npm ci 报 "Cannot read property 'X' of undefined"
  │
  ├─ 检查 package-lock.json 的 lockfileVersion
  │   ├─ v3 → 需 npm 7+
  │   ├─ v2 → 需 npm 5+
  │   └─ v1 → 需 npm 1+
  ├─ 检查实际 npm 版本（where.exe npm / npm --version）
  │   └─ 若 PATH 中旧版优先 → 调整查找优先级
  ├─ 修复：优先用已验证版本的 $nodeExe 同目录 npm
  └─ 验证：npm --version >= 7
```

### 诊断流程 D：pip 残留警告（Ignoring invalid distribution）

```
症状："Ignoring invalid distribution ~etuptools"
  │
  ├─ 定位 venv 的 site-packages 目录
  ├─ 查找 ~前缀目录（pip 卸载残留）
  ├─ 删除 ~前缀目录
  └─ 在 setup 脚本中加自动清理逻辑（防止复发）
```

### 诊断流程 E：服务启动失败（端口占用 / 日志缺失 / 进程崩溃）

```
症状：启动脚本输出 "[ERROR] Web 服务在 N 秒内未启动成功"
  │
  ├─ 步骤 1：检查日志文件是否存在
  │   ├─ 不存在 → 启动命令未重定向到日志文件
  │   │   ├─ 读取启动脚本中的启动命令行
  │   │   ├─ 检查是否含 "> <log_file>" 重定向
  │   │   ├─ 修复：添加 "> logs\<service>.log 2>&1" 重定向
  │   │   └─ 同时直接运行启动命令观察输出（不依赖日志文件）
  │   └─ 存在 → 读日志尾部（最后 30 行）识别错误类型
  │       │
  │       ├─ "error while attempting to bind on address" / "Errno 10048"
  │       │   → 端口被占用
  │       │   ├─ netstat -aon | findstr ":<PORT>.*LISTENING" 查占用 PID
  │       │   │   ⚠️ 可能返回多行（多进程监听同一端口不同地址，如 0.0.0.0:<PORT> 和 127.0.0.1:<PORT>）
  │       │   ├─ 对每个 PID 查询进程命令行判断归属：
  │       │   │   ├─ 优先用 Get-CimInstance（wmic 在某些 Windows 版本输出为空）
  │       │   │   │   Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" | Select CommandLine
  │       │   │   ├─ 同项目旧进程（命令行含本项目路径）→ 直接 taskkill /F /T /PID <PID>
  │       │   │   ├─ 其他项目进程（命令行含其他项目路径）→ 询问用户：杀掉/换端口
  │       │   │   └─ 无法确定归属 → 通过进程内存/绑定地址推断，或询问用户
  │       │   ├─ 杀进程后等待端口释放（循环 netstat 检测，最多 N 秒）
  │       │   ├─ 若端口仍被占用 → 可能有多个进程监听，返回步骤 1 继续处理
  │       │   └─ 修复启动脚本：增加端口等待释放逻辑
  │       │
  │       ├─ "ImportError" / "ModuleNotFoundError"
  │       │   → 依赖缺失 → pip install -r requirements.txt
  │       │
  │       ├─ "PermissionError"
  │       │   → 权限不足 → 以管理员身份运行
  │       │
  │       └─ "Address already in use" (非 10048)
  │           → 端口冲突 → 换端口或杀进程
  │
  ├─ 步骤 2：日志不存在或无明确错误 → 直接运行启动命令观察输出
  │   ├─ 用 RunCommand 后台运行启动命令（非阻塞）
  │   ├─ CheckCommandStatus 轮询输出，识别启动过程中的错误
  │   └─ sandbox 限制无法用 cmd /c → 用 PowerShell 直接执行
  │
  └─ 步骤 3：修复后验证
      ├─ 编码验证（verify.ps1）
      ├─ 语法校验（PS Parser）
      └─ 实际启动验证（后台运行 + 端口监听检测）
```

**端口冲突多进程处理要点**：

netstat 可能返回多个进程监听同一端口的不同地址（如 `0.0.0.0:8000` 和 `127.0.0.1:8000`），绑定时 `127.0.0.1` 优先接收连接，掩盖了 `0.0.0.0` 的存在。杀掉 `127.0.0.1` 的进程后，`0.0.0.0` 的进程才暴露出来。处理时必须：

1. `netstat -aon | findstr ":<PORT>.*LISTENING"` 返回多行时，提取所有 PID（去重）
2. 对每个 PID 用 `Get-CimInstance Win32_Process -Filter "ProcessId=<PID>"` 查询命令行
3. 按命令行判断归属：包含本项目路径 → 同项目；包含其他项目路径 → 其他项目
4. 同项目进程直接杀；其他项目进程询问用户
5. 杀进程后循环检测端口是否释放，若仍被占用可能有未处理的进程

**启动脚本健壮性检查清单**（生成/修复启动脚本时必须逐项确认）：

- [ ] 启动命令重定向到日志文件（`> logs\<service>.log 2>&1`）
- [ ] 启动前清空旧日志（避免新旧日志混淆）
- [ ] 端口清理后增加等待释放循环（避免 TCP 栈释放延迟）
- [ ] 失败时自动输出日志尾部到控制台（便于快速定位）
- [ ] PID 文件记录（便于停止脚本复用）
- [ ] 进程存活验证（启动后检查 PID 是否在运行）

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

用 PowerShell 操作文件编码时，**写入方法的选择至关重要**，错误的方法会导致 BOM 丢失或编码错误。

### 方法对照表

| 目标编码 | 编码对象构造 | 正确写入方法 | 错误写入方法（BOM 丢失） |
|----------|-------------|-------------|------------------------|
| GBK 无 BOM | `[System.Text.Encoding]::GetEncoding(936)` | `WriteAllText(path, text, enc)` | — |
| UTF-8 with BOM | `New-Object System.Text.UTF8Encoding($true)` | `WriteAllText(path, text, enc)` | `enc.GetBytes(text)` + `WriteAllBytes`（BOM 丢失） |
| UTF-8 无 BOM | `New-Object System.Text.UTF8Encoding($false)` | `WriteAllText(path, text, enc)` | — |

### 关键规则

1. **`UTF8Encoding($true).GetBytes(text)` 不会自动添加 BOM**：`emitBOM` 参数只在 `WriteAllText` / `WriteAllBytes` 配合 preamble 时生效。必须用 `[System.IO.File]::WriteAllText($path, $text, $utf8WithBom)` 才能正确写入 BOM。

2. **`GetEncoding(936)` 在 PS 5.1 不支持 3 参数重载**：`GetEncoding(int, EncoderFallback, DecoderFallback)` 在 PS 5.1 的 .NET API 中不可用。改用默认的 `GetEncoding(936)`（带 `DecoderReplacementFallback`），通过检查解码结果是否含 `U+FFFD` 替换字符判断合法性。

3. **`System.Text.Encoding` 是抽象基类不能实例化**：`New-Object System.Text.Encoding` 会报错。必须用静态方法 `[System.Text.Encoding]::GetEncoding()` 或 `[System.Text.Encoding]::UTF8`。

4. **行尾转换**：写入前必须将 LF 转为 CRLF：`$crlf = $text -replace "`r?`n", "`r`n"`

### 写入纯 ASCII .bat 文件的完整模式（首选）

```powershell
# 1. 准备内容（纯 ASCII，不含任何非 ASCII 字符）
$content = @'
@echo off
echo Build started
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
'@

# 2. 转换行尾为 CRLF
$crlf = $content -replace "`r?`n", "`r`n"

# 3. 用 ASCII 编码写入（无 BOM）
# ASCII 编码天然无 BOM，且 Write/Edit 工具默认 UTF-8 也兼容纯 ASCII
$ascii = [System.Text.Encoding]::ASCII
[System.IO.File]::WriteAllText($targetPath, $crlf, $ascii)
```

**注意**：纯 ASCII 内容用 Write 工具直接创建也可（UTF-8 编码的 ASCII 子集与纯 ASCII 字节相同）。

### 写入 GBK .bat 文件的完整模式（备选，仅当 .bat 必须含中文时）

```powershell
# 1. 准备内容（UTF-8 字符串，含中文）
$content = @'
@echo off
chcp 936 >nul 2>&1
echo 中文提示
'@

# 2. 转换行尾为 CRLF
$crlf = $content -replace "`r?`n", "`r`n"

# 3. 用 GBK 编码写入（无 BOM）
# ⚠️ Write/Edit 工具不支持 GBK，必须用 PowerShell WriteAllText
$gbk = [System.Text.Encoding]::GetEncoding(936)
[System.IO.File]::WriteAllText($targetPath, $crlf, $gbk)
```

### 写入中文 .ps1 文件的完整模式

```powershell
# 1. 准备内容
$content = @'
Write-Host "中文提示"
'@

# 2. 转换行尾为 CRLF
$crlf = $content -replace "`r?`n", "`r`n"

# 3. 用 UTF-8 with BOM 编码写入
$utf8WithBom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($targetPath, $crlf, $utf8WithBom)
```

### Edit 工具修改后的 BOM 检查流程

用 Edit 工具修改 .ps1 文件后，**必须**检查 BOM 是否丢失（Edit 工具默认 UTF-8 无 BOM 写回）。同时检测 null 字节残留（前次 BOM 修复失败可能留下 `00 00 00` 前缀）：

```powershell
# 1. 读取修改后文件的前 6 字节（检测 BOM + null 残留）
$bytes = [System.IO.File]::ReadAllBytes($ps1Path)
$head = "{0:X2} {1:X2} {2:X2} {3:X2} {4:X2} {5:X2}" -f $bytes[0], $bytes[1], $bytes[2], $bytes[3], $bytes[4], $bytes[5]

# 2. 检测 null 字节残留（前次 BOM 修复失败导致 00 00 00 前缀）
#    根因：[byte[]](0xEF,0xBB,0xBF) 在 PS 5.1 创建 null 数组（陷阱 36），写入后留 null 字节
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0 -and $bytes[1] -eq 0 -and $bytes[2] -eq 0) {
    Write-Host "[WARN] 检测到 null 字节残留（00 00 00 前缀），清理中..." -ForegroundColor Yellow
    # 移除前 3 个 null 字节
    $bytes = $bytes[3..($bytes.Length - 1)]
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $content = $utf8NoBom.GetString($bytes)
    # 重新写入（暂无 BOM，下一步添加）
    [System.IO.File]::WriteAllText($ps1Path, $content, $utf8NoBom)
    # 重新读取
    $bytes = [System.IO.File]::ReadAllBytes($ps1Path)
}

# 3. 检查 BOM 是否丢失，如丢失则重新添加
$bom = "{0:X2} {1:X2} {2:X2}" -f $bytes[0], $bytes[1], $bytes[2]
if ($bom -ne "EF BB BF") {
    # 用 UTF-8 无 BOM 读取当前内容（避免二次转码损坏）
    $content = [System.IO.File]::ReadAllText($ps1Path, [System.Text.UTF8Encoding]::new($false))
    # 用 UTF-8 with BOM 重新写入（必须用 WriteAllText，不能用 GetBytes+WriteAllBytes，见陷阱 11）
    $utf8WithBom = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($ps1Path, $content, $utf8WithBom)
}

# 4. 验证 BOM 已恢复
$bytes2 = [System.IO.File]::ReadAllBytes($ps1Path)
$bom2 = "{0:X2} {1:X2} {2:X2}" -f $bytes2[0], $bytes2[1], $bytes2[2]
if ($bom2 -eq "EF BB BF") { Write-Host "BOM preserved" } else { Write-Host "BOM STILL MISSING" -ForegroundColor Red }
```

**关键规则**：
- 检查 BOM 时用 `ReadAllBytes` 读字节，不要用 `Get-Content`（Get-Content 会自动解码）
- **先检测 null 残留再检测 BOM**：null 字节（`00 00 00`）会干扰 BOM 判断，必须先清理
- 重新添加 BOM 时用 `UTF8Encoding($false)` 读取当前内容（避免用错误编码读取已损坏内容）
- 用 `UTF8Encoding($true)` + `WriteAllText` 写回（不能用 `GetBytes` + `WriteAllBytes`，见陷阱 11）
- **不要用 `[byte[]](0xEF,0xBB,0xBF)` 创建 BOM 字节数组**：PS 5.1 中此语法创建 null 数组（陷阱 36），必须用 `New-Object 'byte[]' 3` + 逐字节赋值

---

## Sandbox 限制处理策略

在受限环境中执行脚本验证时，可能遇到以下限制及对应处理方式：

| 限制 | 现象 | 处理方式 |
|------|------|----------|
| `cmd /c` 被阻止 | "invalid command: The use of 'cmd /c' is blocked" | 改用 PowerShell 直接读取文件字节 + 编码对象解码验证中文 |
| 嵌套 `powershell.exe` 被阻止 | 无法 Start-Job 或嵌套调用 | 在当前会话用 `&` 直接执行，用临时文件捕获输出 |
| 内联 `$变量` 被外层 shell 吞掉 | 变量值为空 | 改用临时 .ps1 脚本文件（全英文代码避免 BOM 问题） |
| `>nul` 重定向不兼容 | PowerShell 终端中 cmd 重定向报错 | 改用 `2>&1 \| Out-Null` |
| 临时 .ps1 无 BOM 中文乱码 | PS 5.1 按 GBK 解析无 BOM 脚本 | 临时脚本全用英文代码；需中文时用 `[char]0xXXXX` 构造 |

### 验证中文显示的替代方案（无法用 cmd /c 时）

```powershell
# 读取文件字节，用对应编码解码显示，验证中文正确性
$gbk = [System.Text.Encoding]::GetEncoding(936)
$utf8 = New-Object System.Text.UTF8Encoding($true)

$targets = @(
    @{ Path = '<BAT_FILE>'; Enc = $gbk },     # .bat 用 GBK 解码
    @{ Path = '<PS1_FILE>'; Enc = $utf8 }     # .ps1 用 UTF-8 BOM 解码
)

foreach ($t in $targets) {
    $b = [System.IO.File]::ReadAllBytes($t.Path)
    $text = $t.Enc.GetString($b)
    $lines = $text -split "`r`n"
    $lines | Select-Object -First 8 | ForEach-Object { Write-Host $_ }
}
```

---

## 常见陷阱与规避

### 陷阱 1：UTF-8 BOM 让 .bat 的 @echo off 失效
- **现象**：所有命令被回显，`>echo ===` 出现在输出
- **根因**：BOM 字节 `EF BB BF` 让 `@` 不在行首
- **规避**：.bat 文件**永远不要 BOM**

### 陷阱 2：.ps1 无 BOM 在 PS 5.1 中文乱码
- **现象**：`Missing property name after reference operator` + 中文乱码
- **根因**：PS 5.1 按 GBK 解析无 BOM 的 .ps1，UTF-8 中文被错误拆分，`$var.prop` 被误判为属性引用
- **规避**：.ps1 含中文时**必须 UTF-8 with BOM**

### 陷阱 3：chcp 65001 不能修复 .bat 乱码
- **现象**：加了 `chcp 65001` 仍报 `'脚本' is not recognized`
- **根因**：`chcp` 只改控制台输出代码页，**不影响 cmd 解析 .bat 文件本身**（cmd 始终按系统 ANSI 解析）
- **规避**：.bat 文件改纯 ASCII（首选），或转 GBK + chcp 936（备选，需 PowerShell WriteAllText）

### 陷阱 4：LF 行尾让中文行被切分
- **现象**：`'up' is not recognized`（来自 "Setup" 被切断）
- **根因**：cmd 不依赖 LF 作行边界，多字节字符 + LF 导致错误切分
- **规避**：强制 CRLF，生成后验证孤立 LF 数 = 0

### 陷阱 5：PATH 中旧版工具优先
- **现象**：winget 装了 Node 24，但 `npm --version` 显示 6.14（nodejs14 优先）
- **根因**：PATH 中旧版路径排序在前
- **规避**：工具查找优先用已验证版本的 $toolExe 同目录推导，不依赖 PATH

### 陷阱 6：传递依赖冲突
- **现象**：pip install A 后，B 报 version conflict
- **根因**：A 的依赖 C 要求 B<version，但项目锁定 B 更高版本
- **规避**：安装可能引入冲突的包后，显式降级冲突包；requirements.txt 同步更新

### 陷阱 7：lockfileVersion 与 npm 版本不匹配
- **现象**：npm ci 报 `Cannot read property 'X' of undefined`
- **根因**：lockfileVersion 3 需 npm 7+，npm 6 的 lock-verify 不兼容
- **规避**：检查 lockfileVersion，确保 npm 版本兼容

### 陷阱 8：winget 装到用户目录
- **现象**：winget 报"已成功安装"但找不到工具
- **根因**：winget 默认用户级安装到 `$env:LOCALAPPDATA\Programs\...`
- **规避**：Find-Tool 必须包含用户级路径

### 陷阱 9：pip 卸载残留 ~前缀目录
- **现象**：`Ignoring invalid distribution ~etuptools`
- **根因**：pip 卸载包时先重命名为 ~xxx，中断后残留
- **规避**：setup 脚本中加自动清理逻辑（`Get-ChildItem -Filter '~*'`）

### 陷阱 10：冒烟测试覆盖不全
- **现象**：setup 成功但运行时报 ImportError
- **根因**：冒烟测试只测 5 个包，遗漏的包安装失败不报警
- **规避**：冒烟测试覆盖所有直接 import 的第三方包

### 陷阱 11：UTF8Encoding.GetBytes 不写入 BOM
- **现象**：用 `UTF8Encoding($true).GetBytes(text)` + `WriteAllBytes` 写入后，验证 BOM=False
- **根因**：`emitBOM` 参数只在 `WriteAllText` 配合 preamble 时生效，`GetBytes()` 不会自动添加 BOM 字节
- **规避**：必须用 `[System.IO.File]::WriteAllText($path, $text, $utf8WithBom)` 写入

### 陷阱 12：GetEncoding 3 参数重载在 PS 5.1 不支持
- **现象**：`Cannot find an overload for "GetEncoding" and the argument count: "3"`
- **根因**：PS 5.1 的 .NET API 不支持 `GetEncoding(int, EncoderFallback, DecoderFallback)` 重载
- **规避**：改用默认的 `GetEncoding(936)`（带 DecoderReplacementFallback），通过检查解码结果是否含 U+FFFD 替换字符判断合法性

### 陷阱 13：System.Text.Encoding 抽象基类不能实例化
- **现象**：`New-Object System.Text.Encoding` 报 "A constructor was not found"
- **根因**：`System.Text.Encoding` 是抽象基类，不能直接实例化
- **规避**：用静态方法 `[System.Text.Encoding]::GetEncoding(936)` 或 `[System.Text.Encoding]::UTF8`

### 陷阱 14：启动命令未重定向日志导致无法排查
- **现象**：启动失败提示"请查看 logs\web.log"，但该文件不存在
- **根因**：启动命令 `start "..." cmd /c "... 2>&1 & pause"` 把输出留在弹出的 cmd 窗口里，未重定向到文件
- **规避**：启动命令必须重定向 `> logs\<service>.log 2>&1`；启动前清空旧日志；失败时自动输出日志尾部

### 陷阱 15：端口释放延迟导致绑定失败
- **现象**：杀掉旧进程后立即启动新进程，报 `Errno 10048` / `Address already in use`
- **根因**：Windows TCP 栈释放端口有延迟，`taskkill` 后端口不会立即可用
- **规避**：端口清理后增加等待释放循环（`netstat` 检测端口是否仍被占用，最多等待 N 秒）

### 陷阱 16：Sandbox 阻止 cmd /c 导致无法验证 .bat
- **现象**：`cmd /c <script>.bat` 报 "invalid command: The use of 'cmd /c' is blocked"
- **根因**：受限环境安全策略禁止 cmd /c 调用
- **规避**：改用 PowerShell 直接读取文件字节，用 GBK/UTF-8 编码对象解码显示，验证中文正确性

### 陷阱 17：临时 .ps1 脚本无 BOM 导致自身中文乱码
- **现象**：临时验证脚本中的中文输出乱码，或报 `TerminatorExpectedAtEndOfString`
- **根因**：PS 5.1 按 GBK 解析无 BOM 的 .ps1，中文被错误拆分导致语法错误
- **规避**：临时脚本全用英文代码；需输出中文路径时用 `[char]0xXXXX` 构造（如 `启动服务.bat` = `[char]0x542F + [char]0x52A8 + [char]0x670D + [char]0x52A1 + '.bat'`）

### 陷阱 18：内联 PowerShell 命令 $变量 被外层 shell 吞掉
- **现象**：`powershell -Command "$var = ..."` 中 `$var` 变为空值
- **根因**：外层 shell（如 bash/安全包装器）先解析了 `$var`，PowerShell 收到的是空字符串
- **规避**：改用临时 .ps1 脚本文件（`-File` 参数），避免内联命令的转义问题

### 陷阱 19：cmd 重定向语法在 PowerShell 终端不兼容
- **现象**：`taskkill /F /IM python.exe >nul 2>&1` 在 PowerShell 终端报错
- **根因**：PowerShell 不支持 cmd 的 `>nul` 重定向语法，`nul` 被当作文件名
- **规避**：在 PowerShell 终端中用 `2>&1 | Out-Null` 或 `*> $null`

### 陷阱 20：Write 工具默认 UTF-8 无 BOM，不适合写中文 .bat
- **现象**：用 Write 工具创建含中文 echo 的 .bat 文件，执行报错 `'哄共鍑€' 不是内部或外部命令`
- **根因**：Write 工具默认 UTF-8 无 BOM 编码，cmd 按系统 ANSI（GBK）解析 .bat 文件字节流，UTF-8 中文被错误拆分为 GBK 字节序列
- **规避**：含中文的 .bat 文件必须用 PowerShell `[System.IO.File]::WriteAllText(path, text, [System.Text.Encoding]::GetEncoding(936))` 写入；纯英文 .bat 可用 Write 工具但建议统一用 PowerShell 写入保持一致性

### 陷阱 21：扫描正则误报（sha256 hash 片段匹配 API Key 模式）
- **现象**：扫描 PyInstaller 产物时中止构建，报"在 torch RECORD 中发现疑似 API Key 痕迹"
- **根因**：第三方库 dist-info/RECORD 文件含 sha256 hash（如 `9szU7E4S6KxiPatLJsk-trKzjJE0tUMSAsSlfOiR_3c`），其中 `sk-trKzjJE0tUMSAsSlfOiR_3c`（24 字符）匹配 `sk-[A-Za-z0-9]{20,}` 正则
- **规避**：扫描逻辑按目录层级区分递归策略——项目级文件（exe 同级）不递归（避免进入 `_internal/` 第三方库目录），项目子目录（config/scripts/static）递归；或扫描时排除 `*_RECORD` / `*.dist-info` 文件

### 陷阱 22：用错误编码读取已损坏内容后转码（二次破坏）
- **现象**：.ps1 文件丢失 BOM 后中文乱码，用 GBK 读取再转 UTF-8 BOM 后文件内容彻底损坏
- **根因**：文件已被错误编码解码后，中文字符已变为乱码 Unicode 码点，再转 UTF-8 BOM 只是给乱码内容加了 BOM 头，无法恢复原始中文
- **规避**：文件内容损坏时必须从版本控制恢复（`git checkout <file>`），不要尝试用编码转换修复已损坏的内容；转码前先验证源文件编码正确（读前 3 字节判 BOM + 用对应编码解码验证中文显示）

### 陷阱 23：Edit 工具修改 .ps1 后丢失 BOM
- **现象**：用 Edit 工具修改 build-exe.ps1 后，BOM 从 `EF BB BF` 变为 `23 20 73`（文件首字节，即 `# ` 的 UTF-8 编码）
- **根因**：Edit 工具默认以 UTF-8 无 BOM 编码写回文件，不保留原文件的 BOM
- **规避**：用 Edit 工具修改 .ps1 文件后，必须检查 BOM 是否丢失——读前 3 字节，如不是 `EF BB BF` 则用 `[System.IO.File]::WriteAllText(path, content, [New-Object System.Text.UTF8Encoding($true)])` 重新写入

### 陷阱 24：wmic 查询进程命令行输出为空
- **现象**：`wmic process where "ProcessId=<PID>" get CommandLine /format:list` 输出为空
- **根因**：wmic 在某些 Windows 版本/权限下可能不返回结果，且 wmic 在 Windows 11 22H2+ 已被标记为弃用
- **规避**：优先用 PowerShell 的 `Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" | Select-Object ProcessId, Name, CommandLine | Format-List`

### 陷阱 25：replace_all 替换格式遗漏
- **现象**：用 `replace_all` 替换 `:8000` → `:8001` 后，发现 `port 8000`、`8000 端口`、`LocalPort 8000`、`port=8000`、`port: 8000` 等格式未被替换
- **根因**：`replace_all` 只替换精确匹配的字符串，不同上下文的端口引用格式不同（冒号前缀、空格前缀、等号前缀、中文描述等）
- **规避**：批量替换端口号时，不能用单一模式 `replace_all`，必须先用 Grep 扫描所有出现位置，逐一确认上下文后精确替换；或对每种格式分别执行 `replace_all`

### 陷阱 26：subagent 并行修改同一文件竞争
- **现象**：subagent 并行修改同一文件的多个位置时，部分修改被覆盖丢失（如 14 处修改只生效了 3 处）
- **根因**：对同一文件的并行 Edit 存在竞争条件——后写入的 Edit 基于旧版文件内容，覆盖了先写入的 Edit
- **规避**：同一文件的多个 Edit 必须顺序执行（前一个完成后再执行下一个）；不同文件的 Edit 可并行。使用 subagent 时明确告知此约束

### 陷阱 27：全局参数变更扫描遗漏代码默认值
- **现象**：端口从 8000 改为 8001 后，第一轮扫描和修改完成，但最终验证发现 `yaml_config.py` 中 `port: int = 8000`（ServerConfig 默认值）、`templates.py` 中 `port = 8000`（config 读取失败时的 fallback）、`app.py` 注释中的启动示例、测试断言 `assert cfg.port == 8000` 均未修改
- **根因**：扫描时只关注了配置文件和脚本，忽略了代码中的默认值、fallback 值、注释、测试断言
- **规避**：全局参数变更时，必须参照「全局参数变更扫描检查清单」逐项检查，特别关注：Pydantic/BaseModel 字段默认值、typer.Option 默认值、try/except 中的兜底值、模块文档字符串中的启动示例、测试断言

### 陷阱 28：netstat 多进程监听同一端口不同地址
- **现象**：杀掉占用 `127.0.0.1:8000` 的旧进程后，端口仍被 `0.0.0.0:8000` 的另一个进程监听
- **根因**：netstat 可能返回多个进程监听同一端口的不同地址。`127.0.0.1:8000` 优先接收连接，掩盖了 `0.0.0.0:8000` 的存在。杀掉前者后，后者的 `0.0.0.0:8000` 暴露出来
- **规避**：`netstat -aon | findstr ":<PORT>.*LISTENING"` 返回多行时，提取所有 PID（去重），逐一查询进程命令行判断归属后处理

### 陷阱 29：Edit 工具修改 .bat 文件后修改未持久化
- **现象**：用 Edit 工具修改 `启动服务.bat` 第 78 行后，重新读取发现修改未生效
- **根因**：Edit 工具默认 UTF-8 编码写回，而 .bat 文件需要 GBK 编码。编码不匹配可能导致文件写入异常或内容被覆盖
- **规避**：.bat 文件改用纯 ASCII 编码后，Edit 工具可正常修改（ASCII 是 UTF-8 的子集，无编码冲突）。若 .bat 必须含中文（GBK），Edit 工具修改后必须重新读取验证，未持久化时用 PowerShell `WriteAllText` 以 GBK 编码写入

### 陷阱 30：chcp 65001 不能让 cmd.exe 用 UTF-8 解析 .bat 文件
- **现象**：.bat 文件含中文，加了 `chcp 65001`，仍报 `'绔瀯寤哄畬鎴?echo' 不是内部或外部命令`
- **根因**：`chcp 65001` 只改变控制台输出代码页，**不影响 cmd.exe 读取 .bat 文件内容的编码方式**。cmd.exe 始终按系统默认 ANSI（中文 Win 为 GBK）解析 .bat 文件字节流。UTF-8 编码的中文字节被 GBK 错误解码，导致命令被截断和乱码
- **规避**：.bat 文件不含中文（纯 ASCII），中文输出委托给 .ps1（UTF-8 BOM）。不要依赖 `chcp 65001` 解决 .bat 文件编码问题

### 陷阱 31：Write 工具无法创建 GBK 编码的 .bat 文件
- **现象**：用 Write 工具创建含中文 echo 的 .bat 文件，执行报错 `'哄共鍑€' 不是内部或外部命令`
- **根因**：Write 工具默认 UTF-8 无 BOM 编码写入文件，不支持 GBK 编码。cmd.exe 按系统 ANSI（GBK）解析 .bat 文件，UTF-8 中文被错误拆分为 GBK 字节序列
- **规避**：.bat 文件用纯 ASCII（Write 工具可直接创建）。若 .bat 必须含中文（GBK），必须用 PowerShell `[System.IO.File]::WriteAllText(path, text, [System.Text.Encoding]::GetEncoding(936))` 写入

### 陷阱 32：UTF-8 无 BOM + chcp 65001 仍导致 .bat 中文乱码
- **现象**：.bat 文件转为 UTF-8 无 BOM，设置 `chcp 65001`，移除了 BOM，但中文行仍被当作命令执行
- **根因**：cmd.exe 解析 .bat 文件内容的编码不受 `chcp` 影响（陷阱 30）。`chcp 65001` 只改变控制台输出代码页。即使移除 BOM，UTF-8 编码的中文仍被 cmd.exe 按 GBK 错误解码
- **规避**：.bat 文件不含非 ASCII 字符（纯 ASCII），从源头消除编码问题。三种组合都不可靠：UTF-8+BOM（BOM 破坏 @echo off）、UTF-8 无 BOM+chcp 65001（cmd 仍按 GBK 解析）、UTF-8 无 BOM 无 chcp（同前）

### 陷阱 33：ESM 模式下 __dirname 未定义
- **现象**：Node.js 项目 `package.json` 声明 `"type": "module"` 后，运行时报 `ReferenceError: __dirname is not defined`
- **根因**：ESM 模式下 Node.js 不提供 `__dirname` 和 `__filename` 全局变量，它们是 CJS 模式的专有变量
- **规避**：用 `import.meta.url` 派生 `__dirname`，并兼容 CJS 模式：
  ```typescript
  declare const __dirname: string;
  const dirname = typeof __dirname !== 'undefined'
    ? __dirname
    : path.dirname(fileURLToPath(import.meta.url));
  ```

### 陷阱 34：BOM 修复失败导致 null 字节残留
- **现象**：修复 .ps1 BOM 后，文件前 3 字节为 `00 00 00`，PS 5.1 报 `ParserError` 或中文仍乱码
- **根因**：用 `[byte[]](0xEF,0xBB,0xBF)` 创建 BOM 字节数组时，PS 5.1 将字面量列表解释为类型转换而非数组构造，结果创建了一个长度为 3 的 null 数组（所有元素为 0）。写入文件后留下 `00 00 00` 前缀，后续 BOM 检测看到 `00 00 00` 而非 `EF BB BF`，误判 BOM 仍丢失
- **规避**：BOM 修复流程必须先检测 null 残留（前 3 字节为 `00 00 00`）并移除，再添加 BOM。创建 BOM 字节数组用 `New-Object 'byte[]' 3` + 逐字节赋值（`$b[0]=0xEF; $b[1]=0xBB; $b[2]=0xBF`），不要用 `[byte[]](...)` 字面量语法

### 陷阱 35：.bat chcp 与 .ps1 输出编码不匹配导致中文乱码
- **现象**：.bat 设置 `chcp 65001`，.ps1 用 `Write-Host` 输出中文，cmd 窗口显示乱码（如 `锘?` 或 `???`）
- **根因**：.bat 的 `chcp 65001` 只改变 cmd 控制台的输出代码页为 UTF-8，但 .ps1 从 cmd.exe 调用时默认按系统 ANSI（GBK）输出到控制台。控制台用 UTF-8 解码 GBK 字节流，导致乱码。反方向（.bat chcp 936 + .ps1 UTF-8 输出）同样乱码
- **规避**：.ps1 开头必须强制对齐输出编码，与 .bat 的 chcp 匹配：
  - .bat `chcp 65001` ↔ .ps1 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
  - .bat `chcp 936` ↔ .ps1 `[Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding(936)`
  - 用 try-catch 包裹（ISE/VS Code 终端等宿主不支持设置输出编码）

### 陷阱 36：PS 5.1 中 [byte[]](0xEF,0xBB,0xBF) 创建 null 数组
- **现象**：`$bom = [byte[]](0xEF,0xBB,0xBF); $bom.Length` 返回 3，但 `$bom[0]` 为 0（应为 0xEF）。用此数组写入文件后前 3 字节为 `00 00 00`
- **根因**：PS 5.1 的类型转换语义中，`[byte[]](0xEF,0xBB,0xBF)` 将整数字面量列表转换为 byte 数组时，发生隐式类型转换异常，结果创建为全 0 数组而非预期的 `[0xEF, 0xBB, 0xBF]`
- **规避**：用 `New-Object 'byte[]' 3` 创建数组 + 逐字节赋值：
  ```powershell
  $bomBytes = New-Object 'byte[]' 3
  $bomBytes[0] = 0xEF
  $bomBytes[1] = 0xBB
  $bomBytes[2] = 0xBF
  ```
  或直接用 `[System.IO.File]::WriteAllText(path, content, [New-Object System.Text.UTF8Encoding($true)])` 避免 byte 数组操作

### 陷阱 37：修复后的文件被还原为旧乱码版本
- **现象**：修复 .bat 乱码后（已转为纯 ASCII + chcp 65001），重新检查发现文件又变回旧的 GBK 乱码版本
- **根因**：可能原因——(1) 其他工具/脚本（如 git checkout、IDE 文件监视器、自动化构建）覆盖了修复后的文件；(2) subagent 并行修改同一文件时后写入覆盖先写入（陷阱 26 的变体）；(3) 桌面快捷方式指向旧路径，用户实际运行的是旧文件
- **规避**：
  1. 修复后立即用 `Read` 工具重新读取文件前 3 字节验证（不要假设修复已持久化）
  2. 多文件批量修复时，同一文件的多次修改必须顺序执行
  3. 检查桌面快捷方式（.lnk）的目标路径：`$sh = New-Object -ComObject WScript.Shell; $lnk = $sh.CreateShortcut('<lnk_path>'); $lnk.TargetPath`
  4. 如文件被 git 跟踪，用 `git status` 确认修改未被回滚

---

## 模板套件

本技能生成以下文件套件：

| 文件 | 作用 | 编码 | 行尾 | BOM |
|------|------|------|------|-----|
| `config.json` | 参数配置（无硬编码） | UTF-8 | 任意 | 任意 |
| `scripts/<entry>.bat` | 入口脚本 | 纯 ASCII | CRLF | 无 |
| `scripts/<main>.ps1` | 主逻辑 | UTF-8 | CRLF | 有 |
| `scripts/verify.ps1` | 验证脚本 | UTF-8 | CRLF | 有 |
| `scripts/<startup>.bat` | 服务启动脚本（如需） | 纯 ASCII | CRLF | 无 |
| `scripts/scan-global-params.ps1` | 全局参数变更扫描脚本（如需） | UTF-8 | CRLF | 有 |
| `scripts/diagnose-port-conflict.ps1` | 端口冲突诊断脚本（如需） | UTF-8 | CRLF | 有 |
| `<installer>.iss` | 安装包配置（如需） | UTF-8 | 任意 | 任意 |

### 服务启动脚本模板（纯 ASCII + CRLF + 无 BOM）

生成服务启动脚本时必须包含以下健壮性要素（参考诊断流程 E 的检查清单）。所有 echo 内容为英文，中文提示由 .ps1 输出：

```bat
@echo off
REM <SCRIPT_DESCRIPTION>
cd /d "%~dp0.."
setlocal enabledelayedexpansion

echo ========================================
echo   <PROJECT_NAME> Starting...
echo ========================================

REM [1/N] Clean old process (PID file + port scan)
echo [1/N] Cleaning old process...

if exist "logs\<service>.pid" (
    for /f "tokens=*" %%a in (logs\<service>.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    del "logs\<service>.pid" >nul 2>&1
)

REM Kill process occupying port (fallback when PID file missing)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":<PORT>.*LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

REM Wait for port release (max N seconds), avoid bind failure after kill
set /a portWait=0
:wait_port_release
netstat -aon | findstr ":<PORT>.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    set /a portWait+=1
    if !portWait! lss <MAX_WAIT_SECONDS> (
        timeout /t 1 >nul 2>&1
        goto wait_port_release
    )
    echo [WARN] Port <PORT> still in use, startup may fail
)

timeout /t 1 >nul 2>&1

REM [2/N] Check dependencies
echo [2/N] Checking dependencies...

if not exist "<VENV_DIR>\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv <VENV_DIR>
    pause
    exit /b 1
)

if not exist "logs" mkdir logs

REM [3/N] Start service (redirect to log file for troubleshooting)
echo [3/N] Starting <SERVICE_NAME>...

REM Clear old log to avoid confusion
if exist "logs\<service>.log" del "logs\<service>.log" >nul 2>&1

REM Start service and redirect output to log file
start "<WINDOW_TITLE>" cmd /c "<VENV_DIR>\Scripts\python.exe -m <MODULE> <ARGS> > logs\<service>.log 2>&1"

REM Wait for port ready (max N seconds)
echo Waiting for service ready...
set /a tries=0
:wait_service
set /a tries+=1
ping -n 2 127.0.0.1 >nul 2>&1
netstat -aon | findstr ":<PORT>.*LISTENING" >nul 2>&1
if errorlevel 1 (
    if !tries! lss <MAX_RETRIES> goto wait_service
    echo [ERROR] Service failed to start within <TIMEOUT> seconds!
    echo.
    echo ====== Last 30 lines of log ======
    if exist "logs\<service>.log" (
        powershell -NoProfile -Command "Get-Content 'logs\<service>.log' -Tail 30 -Encoding UTF8"
    ) else (
        echo Log file not generated, process may have crashed on startup
    )
    echo ==============================
    echo Full log: logs\<service>.log
    pause
    exit /b 1
)

REM Record PID
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":<PORT>.*LISTENING"') do (
    echo %%a> "logs\<service>.pid"
)

REM [N/N] Verify process alive
echo [N/N] Verifying service...

set SERVICE_ALIVE=0
if exist "logs\<service>.pid" (
    for /f "tokens=*" %%a in (logs\<service>.pid) do (
        tasklist /FI "PID eq %%a" 2>nul | findstr "%%a" >nul 2>&1
        if not errorlevel 1 (
            set SERVICE_ALIVE=1
            echo   [OK] Service PID %%a
        )
    )
)

if "!SERVICE_ALIVE!"=="0" (
    echo   [FAIL] Service process not running!
    echo   Check logs\<service>.log for details
    pause
    exit /b 1
)

echo.
echo ========================================
echo   <PROJECT_NAME> Service Started
echo ========================================
echo   URL:  http://127.0.0.1:<PORT>
echo   Log:  logs\<service>.log
echo.
echo To stop: run scripts\<stop_script>.bat
echo.

start "" http://127.0.0.1:<PORT>/
timeout /t 3 >nul 2>&1
exit
```

**模板占位符说明**（所有参数从 config.json 读取，无硬编码）：

| 占位符 | 含义 | config.json 字段 |
|--------|------|-----------------|
| `<PROJECT_NAME>` | 项目名称 | `project.name` |
| `<SCRIPT_DESCRIPTION>` | 脚本用途说明 | — |
| `<SERVICE_NAME>` | 服务名称 | `service.name` |
| `<PORT>` | 监听端口 | `service.port` |
| `<VENV_DIR>` | 虚拟环境目录 | `runtime.venv_dir` |
| `<MODULE>` | Python 启动模块 | `service.module` |
| `<ARGS>` | 启动参数 | `service.args` |
| `<MAX_WAIT_SECONDS>` | 端口等待最大秒数 | `service.port_wait_max_seconds` |
| `<MAX_RETRIES>` | 端口就绪检测重试次数 | `service.startup_max_retries` |
| `<TIMEOUT>` | 启动超时秒数 | `service.startup_timeout` |
| `<WINDOW_TITLE>` | 窗口标题 | `service.window_title` |
| `<stop_script>` | 停止脚本文件名 | `service.stop_script` |

### 全局参数变更扫描脚本模板（UTF-8 BOM + CRLF）

用于全局参数变更流程的步骤 1（扫描）和步骤 5（验证），从 config.json 读取参数配置：

```powershell
#Requires -Version 5.1
# 全局参数变更扫描脚本
# 用法: powershell -File scan-global-params.ps1 -ConfigPath config.json -Mode scan|verify

param(
    [string]$ConfigPath = "$PSScriptRoot\config.json",
    [ValidateSet("scan","verify")][string]$Mode = "scan"
)

# 加载配置
if (-not (Test-Path $ConfigPath)) { throw "配置文件不存在: $ConfigPath" }
$Config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not $Config.global_params) {
    Write-Host "config.json 中未配置 global_params，无需扫描" -ForegroundColor Yellow
    exit 0
}

# 收集所有匹配结果
$results = @()
$excludeDirs = @("node_modules", ".git", "__pycache__", "dist", "build")

foreach ($paramName in $Config.global_params.PSObject.Properties.Name) {
    $paramConfig = $Config.global_params.$paramName
    $oldValue = $paramConfig.old_value
    $scanDirs = if ($paramConfig.scan_dirs) { $paramConfig.scan_dirs } else { @(".") }
    $paramExcludeDirs = if ($paramConfig.exclude_dirs) { $paramConfig.exclude_dirs } else { $excludeDirs }

    Write-Host "扫描参数 '$paramName' (旧值: $oldValue)..." -ForegroundColor Cyan

    foreach ($dir in $scanDirs) {
        $fullDir = Join-Path $Config.project.root $dir
        if (-not (Test-Path $fullDir)) { continue }

        $files = Get-ChildItem $fullDir -Recurse -File
        foreach ($file in $files) {
            # 排除目录
            $skip = $false
            foreach ($ex in $paramExcludeDirs) {
                if ($file.FullName -like "*\$ex\*") { $skip = $true; break }
            }
            if ($skip) { continue }

            # 读取文件内容搜索
            $content = $null
            try { $content = [System.IO.File]::ReadAllText($file.FullName) } catch { continue }
            if ($content -notmatch [regex]::Escape($oldValue)) { continue }

            # 逐行匹配，记录行号和内容
            $lines = $content -split "`r?`n"
            for ($i = 0; $i -lt $lines.Length; $i++) {
                if ($lines[$i] -match [regex]::Escape($oldValue)) {
                    # 检查排除模式
                    $excluded = $false
                    if ($paramConfig.exclude_patterns) {
                        foreach ($pattern in $paramConfig.exclude_patterns) {
                            if ($lines[$i] -match $pattern) { $excluded = $true; break }
                        }
                    }
                    $results += [PSCustomObject]@{
                        File = $file.FullName
                        Line = $i + 1
                        Content = $lines[$i].Trim()
                        Param = $paramName
                        Excluded = $excluded
                    }
                }
            }
        }
    }
}

# 输出结果
if ($Mode -eq "scan") {
    Write-Host "`n=== 扫描结果 ===" -ForegroundColor Cyan
    $results | Where-Object { -not $_.Excluded } | Format-Table File, Line, Param -AutoSize
    Write-Host "总计: $($results | Where-Object { -not $_.Excluded } | Measure-Object | Select-Object -ExpandProperty Count) 处需修改"
    Write-Host "排除（无关数值）: $($results | Where-Object { $_.Excluded } | Measure-Object | Select-Object -ExpandProperty Count) 处"
} elseif ($Mode -eq "verify") {
    $remaining = $results | Where-Object { -not $_.Excluded }
    if ($remaining.Count -eq 0) {
        Write-Host "[PASS] 所有参数引用已更新，无遗漏" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "[FAIL] 发现 $($remaining.Count) 处未更新的参数引用:" -ForegroundColor Red
        $remaining | Format-Table File, Line, Content -AutoSize
        exit 1
    }
}
```

### 端口冲突诊断脚本模板（UTF-8 BOM + CRLF）

用于诊断端口冲突，从 config.json 读取端口配置和冲突处理策略：

```powershell
#Requires -Version 5.1
# 端口冲突诊断脚本
# 用法: powershell -File diagnose-port-conflict.ps1 -ConfigPath config.json

param(
    [string]$ConfigPath = "$PSScriptRoot\config.json"
)

# 加载配置
if (-not (Test-Path $ConfigPath)) { throw "配置文件不存在: $ConfigPath" }
$Config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

$port = $Config.service.port
$projectRoot = $Config.project.root
$conflictConfig = $Config.port_conflict
$waitSeconds = if ($conflictConfig.port_release_wait_seconds) { $conflictConfig.port_release_wait_seconds } else { 5 }

Write-Host "诊断端口 $port 冲突..." -ForegroundColor Cyan

# 查找所有监听目标端口的进程
$netstatOutput = netstat -aon | findstr ":$port.*LISTENING"
if (-not $netstatOutput) {
    Write-Host "[OK] 端口 $port 未被占用" -ForegroundColor Green
    exit 0
}

# 提取所有 PID（去重）
$pids = @()
foreach ($line in $netstatOutput) {
    $parts = $line -split '\s+'
    $pid = $parts[$parts.Length - 1]
    if ($pid -match '^\d+$' -and $pids -notcontains $pid) {
        $pids += $pid
    }
}

Write-Host "发现 $($pids.Count) 个进程监听端口 $port :" -ForegroundColor Yellow

# 对每个 PID 查询进程信息
foreach ($pid in $pids) {
    # 优先用 Get-CimInstance（wmic 在某些 Windows 版本输出为空）
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$pid" -ErrorAction SilentlyContinue
    if ($process) {
        $cmdLine = $process.CommandLine
        $name = $process.Name
    } else {
        # fallback: 用 tasklist 获取进程名
        $taskOutput = tasklist /FI "PID eq $pid" /FO CSV /NH 2>$null
        $name = ($taskOutput -split ',')[0] -trim('"')
        $cmdLine = "<无法获取命令行>"
    }

    # 判断归属
    $isSameProject = $false
    if ($cmdLine -and $projectRoot) {
        $normalizedRoot = $projectRoot -replace '\\', '\\'
        if ($cmdLine -match $normalizedRoot) { $isSameProject = $true }
    }

    $category = if ($isSameProject) { "同项目" } else { "其他项目" }
    Write-Host "  PID $pid ($name) [$category]" -ForegroundColor $(if ($isSameProject) {'Yellow'} else {'Red'})
    Write-Host "    命令行: $cmdLine" -ForegroundColor Gray

    # 按策略处理
    if ($isSameProject -and $conflictConfig.kill_same_project) {
        Write-Host "    → 杀掉同项目旧进程..." -ForegroundColor Yellow
        taskkill /F /T /PID $pid 2>$null
    } elseif (-not $isSameProject -and $conflictConfig.kill_other_project) {
        Write-Host "    → 杀掉其他项目进程..." -ForegroundColor Yellow
        taskkill /F /T /PID $pid 2>$null
    } else {
        Write-Host "    → 需用户确认处理方式" -ForegroundColor Yellow
    }
}

# 等待端口释放
Write-Host "`n等待端口释放（最多 $waitSeconds 秒）..." -ForegroundColor Cyan
for ($i = 0; $i -lt $waitSeconds; $i++) {
    Start-Sleep -Seconds 1
    $stillUsed = netstat -aon | findstr ":$port.*LISTENING"
    if (-not $stillUsed) {
        Write-Host "[OK] 端口 $port 已释放" -ForegroundColor Green
        exit 0
    }
}

# 端口仍被占用
Write-Host "[WARN] 端口 $port 仍被占用:" -ForegroundColor Red
$remaining = netstat -aon | findstr ":$port.*LISTENING"
$remaining | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host "`n建议:" -ForegroundColor Yellow
Write-Host "  1. 手动杀掉剩余进程"
Write-Host "  2. 或修改 config.json 的 service.port 为其他端口"
exit 1
```

---

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

### 示例 1：创建打包脚本

用户说："帮我创建一个打包脚本，用 PyInstaller 打包 Python 项目并制作安装包"

执行流程：
1. 询问项目名、入口模块、版本号来源
2. 生成 `config.json`（所有参数用占位符，用户填值）
3. 生成 `scripts/build.bat`（纯 ASCII + CRLF + 无 BOM，仅 echo + 调用 ps1）
4. 生成 `scripts/build.ps1`（UTF-8 BOM + CRLF，从 config 读取参数，含 iscc fallback 链，中文输出用 Write-Host）
5. 生成 `scripts/verify.ps1`（验证脚本）
6. 生成 `installer.iss`（如需安装包）
7. 运行 verify.ps1 确认编码/行尾/BOM/非 ASCII 字节正确
8. 运行 PS Parser 校验 .ps1 语法
9. 提示用户运行测试

### 示例 2：诊断脚本报错

用户说："执行 .bat 脚本报错 `'脚本' is not recognized`"

执行流程：
1. 识别症状 → 诊断流程 A（编码问题）
2. 读取报错文件前 3 字节，检查 BOM
3. 检查非 ASCII 字节数（.bat 应为 0）
4. 按"修复优先级：1.改纯 ASCII（首选）2.转 GBK + chcp 936（备选）"修复
5. 运行 PS Parser 校验语法
6. 提示用户重新执行

### 示例 3：诊断依赖冲突

用户说："pip 报 `torch requires setuptools<82, but you have setuptools 83.0.0`"

执行流程：
1. 识别症状 → 诊断流程 B（依赖冲突）
2. 读约束方向：torch requires setuptools<82
3. 查 setuptools 当前版本：83.0.0
4. 查来源：pip install --upgrade setuptools 升级到最新
5. 修复：pip install --upgrade "setuptools<82"
6. 同步更新 requirements.txt
7. 验证：pip check

### 示例 4：诊断服务启动失败

用户说："启动脚本报 `[ERROR] Web 服务在 30 秒内未启动成功`"

执行流程：
1. 识别症状 → 诊断流程 E（服务启动失败）
2. 检查日志文件 `logs/web.log` 是否存在
   - 不存在 → 启动命令未重定向 → 修复重定向
   - 存在 → 读日志尾部识别错误类型
3. 若日志显示 `Errno 10048` → 端口被占用
   - `netstat -aon | findstr ":<PORT>.*LISTENING"` 查占用 PID
   - `taskkill /F /T /PID <PID>` 杀旧进程
   - 修复启动脚本：增加端口等待释放循环
4. 若日志不存在或无明确错误 → 直接运行启动命令观察输出
   - sandbox 限制无法用 cmd /c → 用 PowerShell 后台运行 + 轮询输出
5. 修复后验证：
   - 编码验证（verify.ps1）
   - 语法校验（PS Parser）
   - 实际启动验证（后台运行 + 端口监听检测）
6. 参照"启动脚本健壮性检查清单"逐项确认

### 示例 5：批量修复脚本中文乱码

用户说："scripts 目录下所有脚本中文乱码，请修复"

执行流程：
1. 列出所有 .bat / .ps1 / .vbs 文件
2. 逐个分析编码现状（读前 3 字节判 BOM + 检测非 ASCII 字节数 + 检测行尾）
3. 按文件类型修复编码：
   - .bat → 纯 ASCII + 无 BOM + CRLF（移除所有中文 echo/注释，中文输出移至 .ps1）
   - .ps1 → UTF-8 with BOM + CRLF（用 `UTF8Encoding($true)` + `WriteAllText`）
   - .vbs → 纯 ASCII + 无 BOM + CRLF（同 .bat 策略）
4. 将 .bat 中的中文 echo 替换为英文，中文提示移至 .ps1 的 Write-Host
5. 生成 verify.ps1 验证脚本
6. 运行编码验证（.bat 非 ASCII 字节数 = 0 + .ps1 BOM 存在 + 所有文件 PASS）
7. 运行 PS Parser 语法校验（所有 .ps1 PASS）
8. 中文显示验证（.ps1 用 UTF-8 BOM 解码显示，因 sandbox 可能阻止 cmd /c）

### 示例 6：全局参数变更（端口替换）

用户说："服务端口从 8000 改为 8001，检查工作空间所有引用并替换"

执行流程：
1. 识别任务 → 全局参数变更流程
2. 在 config.json 的 `global_params` 中配置参数：
   ```json
   "global_params": {
     "port": {
       "old_value": "8000",
       "new_value": "8001",
       "exclude_patterns": ["max_context_chars.*8000", "amount.*8000", "0x80000000", "\\d{6}180000"],
       "scan_dirs": ["src", "scripts", "frontend/src", "config", "docs", "tests"],
       "exclude_dirs": ["node_modules", ".git", "__pycache__"]
     }
   }
   ```
3. 执行扫描（步骤 1）：
   - Grep `8000` 扫描整个工作空间
   - 记录所有匹配结果的文件路径和行号
4. 分类（步骤 2）：
   - A 类（必改）：代码默认值（yaml_config.py）、fallback 值（templates.py）、typer.Option 默认值（__main__.py）、测试断言、脚本中的端口引用
   - B 类（必改）：docker-compose.yml、Dockerfile
   - C 类（建议改）：README.md、部署指南、操作手册中的示例 URL
   - D 类（不改）：`"amount": 8000`、`max_context_chars: 8000`、`0x80000000`、`180000`（毫秒）
5. 询问用户修改范围（步骤 3）→ 用户选择"全部修改"
6. 修改（步骤 4）：
   - 同一文件的多个 Edit 顺序执行
   - 不同文件的 Edit 并行执行
   - 文档修改量大时用 subagent，明确告知「同一文件顺序 Edit」
   - 注意 `:8000`、`port 8000`、`8000 端口`、`port=8000`、`port: 8000` 等不同格式
7. 验证（步骤 5）：
   - 重新 Grep 扫描 `8000`
   - 确认剩余出现均为 D 类无关数值
   - 若发现遗漏 → 返回步骤 4 修复
8. 参照「全局参数变更扫描检查清单」逐项确认

### 示例 7：端口冲突诊断（多项目共存）

用户说："启动脚本报 `[ERROR] Web server failed to start within 30 seconds`，日志文件不存在"

执行流程：
1. 识别症状 → 诊断流程 E（服务启动失败）
2. 检查日志文件 → 不存在 → 启动命令未重定向
3. 直接运行启动命令观察输出 → 发现 `Errno 10048` 端口绑定失败
4. 端口冲突诊断：
   - `netstat -aon | findstr ":8000.*LISTENING"` → 发现 2 个进程
   - 对每个 PID 用 `Get-CimInstance Win32_Process` 查询命令行
   - PID 36120 命令行含本项目路径 → 同项目旧进程 → 直接 taskkill
   - PID 29116 命令行含其他项目路径 → 其他项目进程 → 询问用户
5. 用户选择"换端口"→ 修改 config.json 的 `service.port` 为 8001
6. 触发全局参数变更流程（示例 6）
7. 修复后验证：
   - 用新端口后台启动 → 验证 `Uvicorn running on http://127.0.0.1:8001`
   - 编码验证（verify.ps1）
   - 语法校验（PS Parser）
