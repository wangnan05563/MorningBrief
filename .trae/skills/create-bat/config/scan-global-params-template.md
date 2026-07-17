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
