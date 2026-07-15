<#
.SYNOPSIS
    MorningBrief EXE 构建脚本（PyInstaller + Inno Setup）
.DESCRIPTION
    将后端 FastAPI 应用打包为 Windows exe，数据库由 Docker 提供。
    构建流程：
    1. 创建/更新构建虚拟环境（.venv-build）
    2. 安装项目依赖 + PyInstaller
    3. 构建 admin-web 前端（SPA 产物）
    4. PyInstaller 打包后端
    5. 复制外置资源（.env 模板 + 前端产物）
    6. 生成安装包（Inno Setup，未安装时自动安装）
.PARAMETER SkipSPA
    跳过 SPA 构建（仅前端无变更时用）。
.PARAMETER SkipDeps
    跳过 pip 依赖安装（仅依赖无变更时用）。
.PARAMETER SkipInstaller
    跳过 Inno Setup 安装包制作。
.PARAMETER Clean
    清理所有缓存重新构建（怀疑缓存损坏时用）。
.EXAMPLE
    .\build-exe.ps1
    标准构建：全流程执行。
.EXAMPLE
    .\build-exe.ps1 -SkipSPA -SkipDeps
    快速重建：跳过前端和依赖（仅 Python 代码变更时用）。
.NOTES
    产物：dist/MorningBrief/MorningBrief.exe
    V1.2 起单机 exe 部署：SQLite 嵌入式数据库 + TTLCache 进程内缓存，无需 MySQL/Redis/Docker。
#>
[CmdletBinding()]
param(
    [switch]$SkipSPA,
    [switch]$SkipDeps,
    [switch]$SkipInstaller,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $repoRoot

# ============================================================
# 路径常量
# ============================================================

$buildVenv      = ".venv-build"
$buildPython    = "$buildVenv\Scripts\python.exe"
$buildPyInstaller = "$buildVenv\Scripts\pyinstaller.exe"
$buildReadyMark = "$buildVenv\.MorningBrief-build-ready"
$distDir        = "dist\MorningBrief"
$frontendDir    = "admin-web"
$specFile       = "MorningBrief.spec"
$backendDir     = "backend"

# ============================================================
# 工具函数
# ============================================================

function Write-Step { param([string]$Msg) Write-Host "[MorningBrief-Build] $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "[MorningBrief-Build]   [OK] $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "[MorningBrief-Build]   [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg) Write-Host "[MorningBrief-Build]   [FAIL] $Msg" -ForegroundColor Red }

function Find-BuildPython {
    # 构建用 Python 优先 3.12（稳定，依赖兼容性好）
    # Python 3.14 太新，SQLAlchemy 2.0.x 的 TypingOnly / selectolax 0.3.x 存在兼容性问题
    # 查找顺序：uv 管理 → py launcher → 系统 python（回退，可能不兼容）
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCmd) {
        $pyExe = & uv python find 3.12 2>$null
        if ($pyExe) {
            $pyExe = $pyExe.Trim()
            if (Test-Path $pyExe) { return $pyExe }
        }
    }
    $py312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($py312) {
        $py312 = $py312.Trim()
        if (Test-Path $py312) { return $py312 }
    }
    Write-Warn "未找到 Python 3.12，回退到系统 python（可能与部分依赖不兼容）"
    return "python"
}

function New-BuildVenv {
    # 重建 venv：仅在 venv 不存在、损坏或 -Clean 时调用
    if (Test-Path $buildVenv) {
        Write-Host "  删除旧的 $buildVenv..." -ForegroundColor DarkGray
        Remove-Item -Recurse -Force $buildVenv -ErrorAction SilentlyContinue
    }
    $pyExe = Find-BuildPython
    Write-Host "  创建新 venv ($pyExe)...（约 10 秒）" -ForegroundColor DarkGray
    & $pyExe -m venv $buildVenv
    if ($LASTEXITCODE -ne 0) { throw "venv 创建失败，请确认 Python 可用: $pyExe" }
}

function Test-BuildPip {
    # 检查 build venv 的 pip 是否可用
    if (-not (Test-Path $buildPython)) { return $false }
    & $buildPython -m pip --version *> $null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-BuildPip {
    # 封装 pip 调用：失败时重建 venv 重试一次
    param(
        [Parameter(Mandatory)][string[]]$PipArgs,
        [Parameter(Mandatory)][string]$FailureMessage,
        [switch]$RetryAfterRebuild
    )
    & $buildPython -m pip @PipArgs
    if ($LASTEXITCODE -eq 0) { return }
    if ($RetryAfterRebuild) {
        Write-Warn "pip 命令失败，重建 build venv 后重试..."
        New-BuildVenv
        & $buildPython -m pip @PipArgs
        if ($LASTEXITCODE -eq 0) { return }
    }
    throw $FailureMessage
}

# ============================================================
# -Clean：清理所有缓存
# ============================================================

if ($Clean) {
    Write-Step "[Clean] 清理所有缓存..."
    foreach ($p in @(".venv-build", "admin-web\node_modules", "dist", "build")) {
        if (Test-Path $p) {
            Write-Host "  删除 $p" -ForegroundColor DarkGray
            Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue
        }
    }
}

# ============================================================
# 主流程
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MorningBrief EXE Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Repo: $repoRoot"
if ($SkipDeps)      { Write-Host "Mode: SkipDeps（跳过依赖安装）" }
if ($SkipSPA)       { Write-Host "Mode: SkipSPA（跳过 SPA 构建）" }
if ($SkipInstaller) { Write-Host "Mode: SkipInstaller（跳过安装包制作）" }
if ($Clean)         { Write-Host "Mode: Clean（清理缓存重建）" }

# ============== 1. 构建虚拟环境 ==============

Write-Step "[1/6] 准备构建虚拟环境 (.venv-build)"
# 不每次删除重建：pip install 对已安装包自动跳过，删除重建会让所有包重新解压
if (-not (Test-Path $buildPython)) {
    Write-Host "  venv 不存在" -ForegroundColor DarkGray
    New-BuildVenv
} else {
    Write-Host "  venv 已存在，增量更新" -ForegroundColor DarkGray
}

# 健康检查：缺少标记文件说明上次构建中断
if ((-not $SkipDeps) -and (Test-Path $buildPython) -and (-not (Test-Path $buildReadyMark))) {
    Write-Warn "build venv 缺少健康标记，可能是上次构建中断，重建..."
    New-BuildVenv
}

# pip 可用性检查与修复
if (-not (Test-BuildPip)) {
    Write-Warn "pip 不可用，尝试 ensurepip 修复..."
    & $buildPython -m ensurepip --upgrade *> $null
    if (-not (Test-BuildPip)) {
        Write-Warn "ensurepip 修复失败，重建 build venv..."
        New-BuildVenv
    }
}

# ============== 2. 安装依赖 ==============

if (-not $SkipDeps) {
    Write-Step "[2/6] 安装项目依赖 + PyInstaller"

    # 升级 pip + setuptools
    Invoke-BuildPip -PipArgs @("install", "--upgrade", "pip", "setuptools", "wheel") `
        -FailureMessage "pip 升级失败" -RetryAfterRebuild

    # 安装项目依赖
    $reqFile = "$backendDir\requirements.txt"
    if (Test-Path $reqFile) {
        Invoke-BuildPip -PipArgs @("install", "-r", $reqFile) `
            -FailureMessage "项目依赖安装失败" -RetryAfterRebuild
    } else {
        throw "requirements.txt 不存在: $reqFile"
    }

    # 安装 PyInstaller
    Invoke-BuildPip -PipArgs @("install", "pyinstaller") `
        -FailureMessage "PyInstaller 安装失败"

    # 写入健康标记
    Set-Content -Path $buildReadyMark -Value (Get-Date -Format o) -Encoding UTF8
    Write-OK "依赖安装完成"
} else {
    Write-Step "[2/6] 跳过依赖安装（-SkipDeps）"
}

# 验证 PyInstaller 可用（即使 -SkipDeps 也要确保）
if (-not (Test-Path $buildPyInstaller)) {
    Write-Warn "PyInstaller 未安装，强制安装..."
    Invoke-BuildPip -PipArgs @("install", "pyinstaller") -FailureMessage "PyInstaller 安装失败"
}

# ============== 3. 构建前端 SPA ==============

Write-Step "[3/6] 构建前端 SPA（admin-web）"

$spaIndex = "$frontendDir\dist\index.html"
if ($SkipSPA -and (Test-Path $spaIndex)) {
    Write-Host "  SPA 已存在且 -SkipSPA 已指定，跳过构建" -ForegroundColor DarkGray
} else {
    # 调用独立的前端构建脚本
    $buildFrontendScript = "$PSScriptRoot\build-frontend.ps1"
    if (Test-Path $buildFrontendScript) {
        $frontendArgs = @()
        if ($SkipDeps) { $frontendArgs += "-SkipInstall" }
        & $buildFrontendScript @frontendArgs
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
    } else {
        Write-Warn "build-frontend.ps1 不存在，跳过前端构建"
    }
}

# ============== 4. PyInstaller 打包 ==============

Write-Step "[4/6] 执行 PyInstaller 打包"
Write-Host "  预计耗时：约 2-5 分钟" -ForegroundColor DarkGray

# 清理旧产物（dist 每次重建）
if (Test-Path $distDir) {
    Remove-Item -Recurse -Force $distDir -ErrorAction SilentlyContinue
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
}

# 执行 PyInstaller，使用 spec 文件
& $buildPyInstaller $specFile --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }
Write-OK "PyInstaller 打包完成"

# ============== 5. 复制外置资源 ==============

Write-Step "[5/6] 复制外置资源"

# 5.1 .env 配置文件模板
# 外置到 exe 同目录，用户运行前编辑填入实际密钥
Write-Host "  [5.1] 复制 .env 模板..."
$envTemplate = "$backendDir\.env.example"
if (Test-Path $envTemplate) {
    Copy-Item -Force $envTemplate "$distDir\.env"
    Write-OK ".env 模板已复制"

    # V1.2 起 .env 已无 MYSQL_*/REDIS_* 配置（改为 SQLITE_*/CACHE_*），无需替换
    $envContent = Get-Content "$distDir\.env" -Raw
    # 日志目录改为相对路径（exe 同目录下的 logs）
    $envContent = $envContent -replace 'LOG_DIR=/app/logs', 'LOG_DIR=./logs'
    Set-Content -Path "$distDir\.env" -Value $envContent -Encoding UTF8
    Write-OK ".env 已适配 exe 模式"
} else {
    Write-Warn ".env.example 不存在，跳过 .env 复制"
}

# 5.2 前端 SPA 产物
# 外置到 exe 同目录的 admin-web/dist/，由 FastAPI StaticFiles 服务
Write-Host "  [5.2] 复制前端 SPA 产物..."
$spaSource = "$frontendDir\dist"
$spaTarget = "$distDir\admin-web\dist"
if (Test-Path "$spaSource\index.html") {
    New-Item -ItemType Directory -Force (Split-Path $spaTarget) | Out-Null
    Copy-Item -Recurse -Force $spaSource $spaTarget
    Write-OK "前端 SPA 产物已复制"
} else {
    Write-Warn "前端 SPA 产物不存在（$spaSource），跳过。exe 将无法服务运营后台"
}

# 5.3 数据目录
# 创建空的 logs 和 data 目录，避免首次运行时路径不存在
Write-Host "  [5.3] 创建运行时目录..."
foreach ($d in @("$distDir\logs", "$distDir\data\audio_cache")) {
    New-Item -ItemType Directory -Force $d | Out-Null
}
Write-OK "运行时目录已创建"
# 5.3.1 Seed 默认管理员（首次启动即可登录）
Write-Host "  [5.3.1] 初始化默认管理员..."
$dbPath = "$distDir\data\news.db"
$seedScript = "$backendDir\seed_admin.py"
if (Test-Path $seedScript) {
    python "$seedScript" "$dbPath"
    Write-OK "默认管理员已初始化（admin/admin123)"
} else {
    Write-Warn "seed_admin.py 不存在，跳过管理员初始化"
}



# 5.4 数据库启动脚本（V1.2 起已移除：SQLite 嵌入式无需独立启动）

# ============== 6. 生成安装包（Inno Setup） ==============

if ($SkipInstaller) {
    Write-Step "[6/6] 跳过安装包制作（-SkipInstaller）"
} else {
    Write-Step "[6/6] 生成安装包（Inno Setup）"

    # 6.1 查找 ISCC.exe
    function Find-ISCC {
        $cmd = Get-Command iscc -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        $paths = @(
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            "C:\Program Files\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        )
        foreach ($p in $paths) { if (Test-Path $p) { return $p } }
        return $null
    }

    function Refresh-Path {
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    }

    $iscc = Find-ISCC

    # 6.2 自动安装 Inno Setup（如未安装）
    if (-not $iscc) {
        Write-Host "  Inno Setup 未安装，尝试自动安装..." -ForegroundColor DarkGray

        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "  使用 winget 安装..." -ForegroundColor DarkGray
            winget install --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
            Refresh-Path
            $iscc = Find-ISCC
        }

        if (-not $iscc) {
            Write-Host "  直接下载 Inno Setup 安装包..." -ForegroundColor DarkGray
            $installerUrl = "https://jrsoftware.org/download.php/is.exe"
            $installerFile = "$env:TEMP\innosetup-install.exe"
            try {
                Invoke-WebRequest -Uri $installerUrl -OutFile $installerFile -UseBasicParsing
                Start-Process -FilePath $installerFile -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/SP-" -Wait -NoNewWindow
                Refresh-Path
                $iscc = Find-ISCC
            } catch {
                Write-Warn "下载安装失败：$_"
            } finally {
                if (Test-Path $installerFile) { Remove-Item $installerFile -Force -ErrorAction SilentlyContinue }
            }
        }
    }

    # 6.3 自动创建 installer.iss（如不存在）
    if ($iscc -and -not (Test-Path "installer.iss")) {
        Write-Host "  自动创建 installer.iss..." -ForegroundColor DarkGray
        $issTemplate = @"
; Auto-generated by build-exe.ps1
; MorningBrief Inno Setup 安装包配置
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0.0"
#endif
[Setup]
AppName=MorningBrief
AppVersion={#MyAppVersion}
AppPublisher=MorningBrief
DefaultDirName={autopf}\MorningBrief
DefaultGroupName=MorningBrief
UninstallDisplayIcon={app}\MorningBrief.exe
OutputDir=dist
OutputBaseFilename=MorningBrief-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
DisableProgramGroupPage=yes
[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加:"
[Files]
; 打包 dist/MorningBrief/ 下所有文件（排除日志和数据）
Source: "dist\MorningBrief\*"; DestDir: "{app}"; Excludes: "*.log,logs\*,data\*"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\MorningBrief"; Filename: "{app}\MorningBrief.exe"
Name: "{commondesktop}\MorningBrief"; Filename: "{app}\MorningBrief.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\MorningBrief.exe"; Description: "启动 MorningBrief"; Flags: nowait postinstall skipifsilent
"@
        # ISCC 需要 UTF-8 BOM 才能正确解析中文
        [System.IO.File]::WriteAllText("installer.iss", $issTemplate, (New-Object System.Text.UTF8Encoding($true)))
    }

    # 6.4 编译安装包
    if (-not $iscc) {
        Write-Warn "Inno Setup 不可用，跳过安装包制作"
        Write-Host "  手动安装: https://jrsoftware.org/isdl.php" -ForegroundColor DarkGray
    } else {
        # 版本号：从 requirements.txt 或固定 1.0.0
        $version = "1.0.0"
        Write-Host "  版本号: $version"
        Write-Host "  编译安装包..."
        & $iscc /DMyAppVersion=$version installer.iss
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "安装包编译失败"
        } else {
            $setupExe = "dist\MorningBrief-Setup-v$version.exe"
            Write-OK "安装包已生成: $setupExe"
        }
    }
}

# ============== 完成 ==============

$size = (Get-ChildItem -Recurse $distDir | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  产物目录: $distDir"
Write-Host ("  目录大小: {0:N1} MB" -f $size)
Write-Host "  EXE:      $distDir\MorningBrief.exe"
Write-Host ""
Write-Host "  使用方式:" -ForegroundColor Cyan
Write-Host "    1. 编辑 dist\MorningBrief\.env 填入实际密钥（JWT_SECRET / LLM_API_KEY / COS_* 等）"
Write-Host "    2. 双击 dist\MorningBrief\MorningBrief.exe 启动服务（SQLite 嵌入式，无需外部数据库）"
Write-Host "    3. 访问 http://127.0.0.1:8000/docs"
Write-Host "========================================" -ForegroundColor Green

