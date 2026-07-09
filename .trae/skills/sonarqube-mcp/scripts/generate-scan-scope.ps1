# Xianyu SonarQube 扫描范围生成脚本
# 用途：根据功能模块关键词或路径，生成需要扫描的文件清单
# 使用：
#   .\generate-scan-scope.ps1 -Keyword "evaluation"
#   .\generate-scan-scope.ps1 -Keyword "auth" -Module "backend"
#   .\generate-scan-scope.ps1 -Keyword "useAutoLiveSearch" -Module "frontend"

param(
    [Parameter(Mandatory=$true)]
    [string]$Keyword,

    [Parameter(Mandatory=$false)]
    [ValidateSet("backend", "frontend", "all", "")]
    [string]$Module = "all",

    [Parameter(Mandatory=$false)]
    [string]$BasePath = "",

    [Parameter(Mandatory=$false)]
    [string]$ConfigPath = "$PSScriptRoot\..\config\scan_config.json"
)

# ========== 加载配置 ==========
if (-not (Test-Path $ConfigPath)) {
    Write-Error "配置文件不存在: $ConfigPath"
    exit 1
}

$Config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$ProjectKey = $Config.project.key

# 解析项目根路径（技能目录的上三级）
if ([string]::IsNullOrEmpty($BasePath)) {
    $SkillRoot = Split-Path -Parent $PSScriptRoot
    $ProjectRoot = (Resolve-Path (Join-Path $SkillRoot "..\..\..")).Path
    $BasePath = $ProjectRoot
}

Write-Host "=== Xianyu SonarQube 扫描范围生成 ===" -ForegroundColor Cyan
Write-Host "关键词: $Keyword" -ForegroundColor Yellow
Write-Host "模块  : $Module" -ForegroundColor Yellow
Write-Host "根目录: $BasePath" -ForegroundColor Yellow
Write-Host ""

# ========== 层级判定函数（必须在使用前定义）==========
function Get-Layer {
    param([string]$FilePath, [string]$ModuleName, [object]$ConfigObj)

    if ($ModuleName -eq "backend") {
        $layers = $ConfigObj.modules.backend.layers
    } else {
        $layers = $ConfigObj.modules.frontend.layers
    }

    foreach ($prop in $layers.PSObject.Properties) {
        $layerName = $prop.Name
        $layerPath = $prop.Value
        # 使用正则匹配路径中的层级目录
        $pattern = "\\$layerPath\\"
        if ($FilePath -match $pattern) {
            return $layerName
        }
    }
    return "其他"
}

# ========== 收集搜索路径 ==========
$SearchPaths = @()
if ($Module -eq "all" -or $Module -eq "backend") {
    $backendPath = Join-Path $BasePath $Config.modules.backend.path
    if (Test-Path $backendPath) {
        $SearchPaths += @{ Path = $backendPath; Module = "backend"; Languages = $Config.modules.backend.languages; Exclude = $Config.modules.backend.exclude }
    }
}
if ($Module -eq "all" -or $Module -eq "frontend") {
    $frontendPath = Join-Path $BasePath $Config.modules.frontend.path
    if (Test-Path $frontendPath) {
        $SearchPaths += @{ Path = $frontendPath; Module = "frontend"; Languages = $Config.modules.frontend.languages; Exclude = $Config.modules.frontend.exclude }
    }
}

if ($SearchPaths.Count -eq 0) {
    Write-Error "未找到任何有效搜索路径"
    exit 1
}

# ========== 搜索文件 ==========
$AllFiles = @()

foreach ($searchEntry in $SearchPaths) {
    $searchPath = $searchEntry.Path
    $moduleName = $searchEntry.Module
    $excludeDirs = $searchEntry.Exclude

    # 根据语言收集候选文件
    $candidateFiles = @()
    if ($searchEntry.Languages -contains "python") {
        $candidateFiles += Get-ChildItem -Path $searchPath -Filter "*.py" -Recurse -ErrorAction SilentlyContinue
    }
    if ($searchEntry.Languages -contains "typescript" -or $searchEntry.Languages -contains "javascript") {
        $candidateFiles += Get-ChildItem -Path $searchPath -Include "*.ts","*.tsx","*.js","*.jsx" -Recurse -ErrorAction SilentlyContinue
    }

    # 过滤排除目录并匹配关键词
    foreach ($f in $candidateFiles) {
        $relativePath = $f.FullName.Replace($BasePath + "\", "")
        $excluded = $false
        foreach ($ex in $excludeDirs) {
            $exPattern = $ex -replace '/', '\\'
            if ($relativePath -match $exPattern) { $excluded = $true; break }
        }
        if ($excluded) { continue }

        # 关键词匹配：文件名或文件内容
        $content = $null
        try { $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue } catch {}
        if ($f.Name -match $Keyword -or ($content -and $content -match $Keyword)) {
            $layer = Get-Layer -FilePath $f.FullName -ModuleName $moduleName -ConfigObj $Config
            $AllFiles += @{ File = $f; Module = $moduleName; Layer = $layer; RelativePath = $relativePath }
        }
    }
}

# ========== 按层级分组输出 ==========
$grouped = $AllFiles | Group-Object { $_.Layer }

Write-Host "扫描文件清单：" -ForegroundColor Green
Write-Host ""

$totalLines = 0
$totalFiles = 0

foreach ($group in $grouped) {
    Write-Host "【$($group.Name)】（$($group.Count) 个文件）" -ForegroundColor Cyan
    foreach ($entry in $group.Group) {
        $lineCount = (Get-Content $entry.File.FullName | Measure-Object -Line).Lines
        $totalLines += $lineCount
        $totalFiles++
        Write-Host "  [$($entry.Module)] $($entry.RelativePath) ($lineCount 行)" -ForegroundColor White
    }
    Write-Host ""
}

# ========== 汇总 ==========
Write-Host "=== 汇总 ===" -ForegroundColor Cyan
Write-Host "  文件总数: $totalFiles" -ForegroundColor Green
Write-Host "  代码行数: $totalLines" -ForegroundColor Green
Write-Host "  项目 Key : $ProjectKey" -ForegroundColor Green
Write-Host ""

# ========== 输出 SonarQube MCP 文件路径格式 ==========
Write-Host "SonarQube MCP 文件路径格式（用于 files 参数）：" -ForegroundColor Yellow

foreach ($entry in $AllFiles) {
    $sonarPath = "${ProjectKey}:$($entry.RelativePath.Replace('\', '/'))"
    Write-Host "  $sonarPath" -ForegroundColor White
}
