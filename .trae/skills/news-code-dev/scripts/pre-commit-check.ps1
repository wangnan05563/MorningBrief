# MorningBrief 提交前检查脚本
# 用法: .\scripts\pre-commit-check.ps1

$ErrorActionPreference = "Stop"
$startTime = Get-Date

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  MorningBrief 提交前检查" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$hasError = $false

# ==================== 1. 后端 Python 语法检查 ====================
Write-Host "[1/4] 检查后端 Python 语法..." -ForegroundColor Yellow
$backendFiles = Get-ChildItem -Path "backend/app" -Recurse -Filter "*.py" -File | Select-Object -ExpandProperty FullName

if ($backendFiles.Count -gt 0) {
    $compileErrors = @()
    foreach ($file in $backendFiles) {
        try {
            python -m py_compile $file 2>&1 | Out-Null
        } catch {
            $compileErrors += $file
        }
    }
    
    if ($compileErrors.Count -gt 0) {
        Write-Host "  [FAIL] 以下文件存在语法错误：" -ForegroundColor Red
        $compileErrors | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        $hasError = $true
    } else {
        Write-Host "  [PASS] 后端 Python 语法检查通过 ($($backendFiles.Count) 个文件)" -ForegroundColor Green
    }
} else {
    Write-Host "  [SKIP] 未发现 Python 文件" -ForegroundColor Gray
}

# ==================== 2. 前端构建检查 ====================
Write-Host "`n[2/4] 检查前端构建..." -ForegroundColor Yellow

if (Test-Path "admin-web/package.json") {
    Set-Location "admin-web"
    try {
        npm run build 2>&1 | Out-Null
        Write-Host "  [PASS] 前端构建检查通过" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] 前端构建失败" -ForegroundColor Red
        $hasError = $true
    }
    Set-Location ..
} else {
    Write-Host "  [SKIP] 未发现 admin-web 目录" -ForegroundColor Gray
}

# ==================== 3. 硬约束检查 ====================
Write-Host "`n[3/4] 检查硬约束..." -ForegroundColor Yellow

$forbiddenPatterns = @(
    @{ Pattern = "datetime\.utcnow\(\)"; Message = "使用 datetime.utcnow()，应改用 utcnow_naive()" },
    @{ Pattern = "datetime\.now\(\)"; Message = "使用 datetime.now()，应改用 utcnow_naive()" },
    @{ Pattern = "(?<!logger\.)print\("; Message = "使用 print()，应改用 logger" }
)

$forbiddenFound = @()
foreach ($patternInfo in $forbiddenPatterns) {
    $pattern = $patternInfo.Pattern
    $message = $patternInfo.Message
    
    $matchingFiles = Get-ChildItem -Path "backend/app" -Recurse -Filter "*.py" -File |
        Select-String -Pattern $pattern -List |
        ForEach-Object { $_.Path }
    
    if ($matchingFiles.Count -gt 0) {
        foreach ($file in $matchingFiles) {
            $forbiddenFound += "  $message`n    -> $file"
        }
    }
}

if ($forbiddenFound.Count -gt 0) {
    Write-Host "  [FAIL] 发现禁止的代码模式：" -ForegroundColor Red
    $forbiddenFound | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    $hasError = $true
} else {
    Write-Host "  [PASS] 硬约束检查通过" -ForegroundColor Green
}

# ==================== 4. 环境变量检查 ====================
Write-Host "`n[4/4] 检查环境变量配置..." -ForegroundColor Yellow

if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    $placeholders = @("your_", "changeme", "xxx", "placeholder", "<")
    $envIssues = @()
    
    foreach ($placeholder in $placeholders) {
        if ($envContent -imatch $placeholder) {
            $envIssues += "    发现占位符模式: '$placeholder'"
        }
    }
    
    if ($envIssues.Count -gt 0) {
        Write-Host "  [WARN] .env 文件中可能包含未替换的占位符：" -ForegroundColor Yellow
        $envIssues | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
        Write-Host "  请确认这些是有意为之的" -ForegroundColor Yellow
    } else {
        Write-Host "  [PASS] .env 文件检查通过" -ForegroundColor Green
    }
} else {
    Write-Host "  [SKIP] 未发现 .env 文件" -ForegroundColor Gray
}

# ==================== 总结 ====================
$elapsed = (Get-Date) - $startTime

Write-Host "`n========================================" -ForegroundColor Cyan
if ($hasError) {
    Write-Host "  检查失败，请修复上述问题后再提交" -ForegroundColor Red
    Write-Host "========================================`n" -ForegroundColor Cyan
    exit 1
} else {
    Write-Host "  所有检查通过！" -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Cyan
    Write-Host "耗时: $($elapsed.TotalSeconds.ToString('F2')) 秒`n" -ForegroundColor Gray
    exit 0
}
