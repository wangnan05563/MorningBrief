---
name: "create-bat"
description: "Windows bat/ps1 脚本生成与诊断技能：覆盖编码三元组、依赖冲突排查、工具链 fallback、冒烟测试验证。Invoke when user asks to create/fix .bat or .ps1 scripts on Windows, especially with Chinese content, PowerShell calls, dependency management, or packaging workflows."
---

# Create Bat

Windows 中文环境下 .bat + .ps1 脚本的**生成、诊断、修复**技能。基于实战复盘抽象出固定流程，无硬编码，所有参数配置驱动。

## 核心规则（必须遵守）

### 规则 1：编码三元组一致性（.bat 与 .ps1 规则不同）

**.bat 文件**——cmd.exe 始终按系统 ANSI（中文 Win 为 GBK）解析 .bat 文件本身，`chcp` 只改控制台输出代码页，不影响 .bat 解析：

| 文件编码 | chcp | BOM | 状态 |
|----------|------|-----|------|
| GBK（CP936） | `chcp 936` | 无 BOM | ✅ 推荐 |
| UTF-8 | `chcp 65001` | 无 BOM | ⚠️ 不可靠（cmd 仍按 ANSI 解析文件） |
| UTF-8 + BOM | 任意 | 有 BOM | ❌ 禁止（BOM 让 `@` 不在行首，`@echo off` 失效） |

**.ps1 文件**——PowerShell 5.1（Win10 默认）按 BOM 判断编码，无 BOM 时按系统 ANSI（GBK）解析：

| 文件编码 | BOM | 状态 |
|----------|-----|------|
| UTF-8 with BOM | 有（`EF BB BF`） | ✅ 推荐（PS 5.1 + 7+ 均兼容） |
| UTF-8 无 BOM | 无 | ❌ PS 5.1 按 GBK 解析导致中文乱码 + 语法错误 |
| GBK | 无 | ⚠️ 仅纯英文可用 |

**绝对禁止**：
- .bat 含 BOM（任何编码）
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
  "installer": {
    "enabled": false,
    "iss_file": "<ISS_FILE>",
    "output_dir": "<OUTPUT_DIR>"
  }
}
```

### 步骤 3：生成 .bat 入口脚本

模板（GBK + chcp 936 + CRLF + 无 BOM）：

```bat
@echo off
chcp 936 >nul 2>&1
REM <SCRIPT_DESCRIPTION>
cd /d "%~dp0.."

echo ============================================
echo   <PROJECT_NAME> <SCRIPT_PURPOSE>
echo ============================================
echo.
echo <FLOW_DESCRIPTION>
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0<main>.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] <ERROR_MESSAGE>
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   <SUCCESS_MESSAGE>
echo ============================================
pause
exit
```

### 步骤 4：生成 .ps1 主逻辑脚本

模板（UTF-8 with BOM + CRLF）：

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
# 验证 .bat / .ps1 文件编码、行尾、BOM 是否符合规范
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
    if ($expectBom -and -not $hasBom) { $issues += "缺少 BOM" }
    if (-not $expectBom -and $hasBom) { $issues += "不应有 BOM" }
    
    # 行尾检查（孤立 LF）
    $lf = 0
    for ($i=0; $i -lt $b.Length; $i++) {
        if ($b[$i] -eq 0x0A -and ($i -eq 0 -or $b[$i-1] -ne 0x0D)) { $lf++ }
    }
    if ($lf -gt 0) { $issues += "$lf 个孤立 LF 行尾" }
    
    # 编码可解码性
    try {
        if ($expectedEncoding -eq 'GBK') { $null = $gbk.GetString($b) }
        elseif ($expectedEncoding -eq 'UTF8') { $null = [System.Text.Encoding]::UTF8.GetString($b) }
    } catch { $issues += "无法按 $expectedEncoding 解码" }
    
    return @{ issues = $issues; hasBom = $hasBom; lf = $lf }
}

# 验证所有 .bat（GBK + 无 BOM）
Get-ChildItem $TargetDir -Filter '*.bat' -Recurse | ForEach-Object {
    $r = Test-FileEncoding $_.FullName 'GBK' $false
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
Write-Host "总计: $pass PASS, $fail FAIL" -ForegroundColor $(if ($fail -eq 0) {'Green'} else {'Red'})
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

---

## 诊断流程（从报错识别问题）

### 诊断流程 A：编码问题（"'XX' is not recognized" 或中文乱码）

```
症状："'脚本' is not recognized" / 中文显示乱码
  │
  ├─ 出错文件类型？
  │   ├─ .bat
  │   │   ├─ 读前 3 字节
  │   │   │   ├─ EF BB BF → 含 BOM，需移除
  │   │   │   └─ 非 EF BB BF → 检查文件编码
  │   │   ├─ 检查 chcp 行
  │   │   │   ├─ chcp 65001 + 文件 UTF-8 → cmd 仍按 GBK 解析，改 chcp 936 + 文件转 GBK
  │   │   │   └─ chcp 936 + 文件 GBK → ✅
  │   │   └─ 修复：文件转 GBK + chcp 936 + 无 BOM + CRLF
  │   │
  │   └─ .ps1
  │       ├─ 读前 3 字节
  │       │   ├─ EF BB BF → ✅ 有 BOM
  │       │   └─ 非 EF BB BF → 缺 BOM，PS 5.1 按 GBK 解析
  │       └─ 修复：加 UTF-8 BOM（不影响内容，只加 3 字节头）
  │
  └─ 验证：Parser::ParseFile 无错误 + 中文字符正常显示
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
- **规避**：.bat 文件转 GBK + chcp 936

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

---

## 模板套件

本技能生成以下文件套件：

| 文件 | 作用 | 编码 | 行尾 | BOM |
|------|------|------|------|-----|
| `config.json` | 参数配置（无硬编码） | UTF-8 | 任意 | 任意 |
| `scripts/<entry>.bat` | 入口脚本 | GBK | CRLF | 无 |
| `scripts/<main>.ps1` | 主逻辑 | UTF-8 | CRLF | 有 |
| `scripts/verify.ps1` | 验证脚本 | UTF-8 | CRLF | 有 |
| `<installer>.iss` | 安装包配置（如需） | UTF-8 | 任意 | 任意 |

---

## 适用场景

- Windows 中文环境下的 .bat + .ps1 自动化脚本生成
- 含中文 echo / 中文注释的脚本
- 需兼容 PowerShell 5.1（Win10 默认）的脚本
- PyInstaller 打包项目
- 需要自动安装依赖工具链的场景（Python/Node/Inno Setup）
- 有传递依赖冲突的 Python 项目环境配置
- 需要制作 Inno Setup 安装包的项目
- 需要从报错诊断编码/依赖/工具问题的场景

## 不适用场景

- 跨平台脚本（应改用 Python/Node 跨平台方案）
- Linux/macOS 环境（无 cmd、无 chcp、PS 7+ 默认 UTF-8）
- 纯 ASCII 内容（无编码问题，无需三元组检查）
- 纯 .ps1 脚本无 .bat 入口（无需 .bat 编码规则，但仍需 .ps1 BOM）
- 仅 PowerShell 7+ 专用项目（默认 UTF-8 无需 BOM）

---

## 调用示例

### 示例 1：创建打包脚本

用户说："帮我创建一个打包脚本，用 PyInstaller 打包 Python 项目并制作安装包"

执行流程：
1. 询问项目名、入口模块、版本号来源、是否含中文
2. 生成 `config.json`（所有参数用占位符，用户填值）
3. 生成 `scripts/构建.bat`（GBK + chcp 936 + CRLF + 无 BOM）
4. 生成 `scripts/build.ps1`（UTF-8 BOM + CRLF，从 config 读取参数，含 iscc fallback 链）
5. 生成 `scripts/verify.ps1`（验证脚本）
6. 生成 `installer.iss`（如需安装包）
7. 运行 verify.ps1 确认编码/行尾/BOM 正确
8. 运行 PS Parser 校验 .ps1 语法
9. 提示用户运行测试

### 示例 2：诊断脚本报错

用户说："执行 .bat 脚本报错 `'脚本' is not recognized`"

执行流程：
1. 识别症状 → 诊断流程 A（编码问题）
2. 读取报错文件前 3 字节，检查 BOM
3. 检查文件编码 vs chcp 是否匹配
4. 按"修复：文件转 GBK + chcp 936 + 无 BOM + CRLF"修复
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
