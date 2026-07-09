# ========== 20_News 后端代码阻塞级问题自动扫描 v1.0.0 ==========
# 扫描 backend/app/ 下的 .py 文件，检查 12 项阻塞级问题
# 用法：pwsh .trae/skills/news-backend-code-review/scripts/auto-scan.ps1
#
# 检查项（对应 config.yaml#hard_constraints.rules）：
#  1. datetime.utcnow() 弃用检查
#  2. 硬编码凭据检查
#  3. asyncio.create_task 未保留引用检查
#  4. async def 中同步 IO 检查（time.sleep / requests）
#  5. Redis LRANGE+LTRIM 非原子检查
#  6. 内部接口缺鉴权检查（verify_localhost）
#  7. Enum 字段未 .value 检查
#  8. 敏感词过滤器未初始化检查
#  9. PermissionError 覆盖内置异常检查
# 10. 裸 SQL 注入检查
# 11. print() 语句检查
# 12. finally 块无条件删除锁检查

# 参数：-ShowVerbose 显示详细扫描过程
# 注：避免用 $Verbose（与 PowerShell 内置 -Verbose 通用参数冲突）
param(
    [switch]$ShowVerbose
)

# 计算项目根目录（技能 scripts/ 上溯 4 层到项目根）
$SkillRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProjectRoot = (Resolve-Path (Join-Path $SkillRoot "..\..\..")).Path
$SourceDir = Join-Path $ProjectRoot "backend\app"

# 计数器
$ISSUE_COUNT = 0
$WARN_COUNT = 0
$CHECK_PASSED = 0

# 豁免 print 的文件列表（与 config.yaml#hard_constraints.rules.print_statement.exclude_files 一致）
$PrintExemptFiles = @("launcher.py", "_verify_init.py")

function Get-RelPath($fullPath) {
    # 返回相对项目根的路径，便于报告展示
    if ($fullPath -like "$ProjectRoot*") {
        return $fullPath.Substring($ProjectRoot.Length + 1)
    }
    return $fullPath
}

function Get-PyFiles {
    # 递归获取所有 .py 文件，排除 __pycache__
    if (-not (Test-Path $SourceDir)) {
        Write-Host "[ERROR] 源码目录不存在: $SourceDir" -ForegroundColor Red
        exit 1
    }
    Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "__pycache__" }
}

# 预先收集所有文件，避免重复 IO
$AllFiles = Get-PyFiles
$TotalFiles = $AllFiles.Count

Write-Host "========== 20_News 后端代码预检 ==========" -ForegroundColor Cyan
Write-Host "源码目录: $SourceDir" -ForegroundColor Gray
Write-Host "扫描文件数: $TotalFiles`n" -ForegroundColor Gray

# ============================================================
# 检查 1/12：datetime.utcnow() 弃用检查
# 对应 config.yaml: hard_constraints.rules.deprecated_utcnow
# ============================================================
Write-Host "[1/12] 检查 datetime.utcnow() 弃用..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    # 用 @() 强制转为数组，避免单行文件返回字符串导致 $lines[$i] 是 char
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    # 跟踪三引号 docstring 状态，跳过 docstring 内的引用
    $inDocstring = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = [string]$lines[$i]
        # 跟踪 """ 开关状态
        $tripleQuoteCount = ([regex]::Matches($line, '"""')).Count
        if ($tripleQuoteCount -eq 1) {
            $inDocstring = -not $inDocstring
            continue
        } elseif ($tripleQuoteCount -ge 2) {
            continue
        }
        if ($inDocstring) {
            continue
        }
        # 跳过注释行（# 开头），避免误报注释中的引用
        $trimmedLine = $line.TrimStart()
        if ($trimmedLine.StartsWith("#")) {
            continue
        }
        if ($line -match 'datetime\.utcnow\(\)') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] datetime.utcnow() 已弃用 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：改用 utcnow_naive()（core/timeutil.py）" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 未发现 datetime.utcnow() 调用" -ForegroundColor Green }

# ============================================================
# 检查 2/12：硬编码凭据检查
# 对应 config.yaml: hard_constraints.rules.hardcoded_credentials
# ============================================================
Write-Host "[2/12] 检查硬编码凭据..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配 password/secret/token 等凭据赋值（8+ 字符）
        if ($lines[$i] -match '(?i)(password|secret|token|api_key|access_key|webhook_secret)\s*[:=]\s*["''][^"'']{8,}["'']') {
            $value = [regex]::Match($lines[$i], '["'']([^"'']{8,})["'']').Groups[1].Value
            # 占位符白名单：含 < / change-me / your_ / xxx 的不报警
            if ($value -match '(<|change-me|your_|xxx)') {
                continue
            }
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 硬编码凭据 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：通过 settings 环境变量注入" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 未发现硬编码凭据" -ForegroundColor Green }

# ============================================================
# 检查 3/12：asyncio.create_task 未保留引用检查
# 对应 config.yaml: hard_constraints.rules.create_task_no_reference
# ============================================================
Write-Host "[3/12] 检查 asyncio.create_task 未保留引用..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配 asyncio.create_task(...) 但前面无 = 赋值
        if ($lines[$i] -match 'asyncio\.create_task\(') {
            # 检查是否赋值给变量（self._xxx = / _xxx = / xxx =）
            if ($lines[$i] -match '=\s*asyncio\.create_task\(') {
                continue
            }
            $lineNum = $i + 1
            Write-Host "  [BLOCK] create_task 未保留引用 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：赋值给 self._running_tasks 等实例属性" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 所有 create_task 均保留引用" -ForegroundColor Green }

# ============================================================
# 检查 4/12：async def 中同步 IO 检查（time.sleep / requests）
# 对应 config.yaml: hard_constraints.rules.sync_io_in_async / sync_requests_in_async
# ============================================================
Write-Host "[4/12] 检查 async def 中同步 IO 阻塞..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    # 跳过空文件（避免 [regex]::Matches 抛 ArgumentNullException）
    if ($null -eq $content -or $content -eq "") {
        continue
    }
    # 用正则匹配 async def 块内的同步 IO（简化版：检查 time.sleep / requests. 在 async 函数附近）
    $asyncMatches = [regex]::Matches($content, '(?s)async\s+def\s+(\w+)\([^)]*\)[^:]*:(.*?)(?=\n(?:async\s+def|def\s|\Z))')
    foreach ($m in $asyncMatches) {
        $funcName = $m.Groups[1].Value
        $funcBody = $m.Groups[2].Value
        # 检查 time.sleep
        if ($funcBody -match 'time\.sleep\(') {
            # 定位行号
            $beforeFunc = $content.Substring(0, $m.Index)
            $funcLine = ($beforeFunc -split "`n").Count
            Write-Host "  [BLOCK] async def $funcName 内 time.sleep() L${funcLine}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：改用 asyncio.sleep() 或 asyncio.to_thread()" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
        # 检查 requests.get/post/put/delete
        if ($funcBody -match 'requests\.(get|post|put|delete)\(') {
            $beforeFunc = $content.Substring(0, $m.Index)
            $funcLine = ($beforeFunc -split "`n").Count
            Write-Host "  [BLOCK] async def $funcName 内 requests 同步库 L${funcLine}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：改用 httpx.AsyncClient" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 未发现 async def 中同步 IO" -ForegroundColor Green }

# ============================================================
# 检查 5/12：Redis LRANGE+LTRIM 非原子检查
# 对应 config.yaml: hard_constraints.rules.redis_non_atomic_lrange_ltrim
# ============================================================
Write-Host "[5/12] 检查 Redis LRANGE+LTRIM 非原子..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    # 匹配 lrange 后跟 ltrim（中间无 eval/pipeline/multi）
    if ($content -match '(?s)lrange\([^)]+\)\s*\n.*?ltrim\(') {
        # 检查是否在同一 Lua/pipeline 块内
        $contextMatch = [regex]::Match($content, '(?s)(eval|pipeline|multi).*?lrange.*?ltrim|lrange.*?ltrim.*?(eval|pipeline|multi)')
        if (-not $contextMatch.Success) {
            $lines = @(Get-Content $file.FullName -Encoding UTF8)
            for ($i = 0; $i -lt $lines.Count; $i++) {
                if ($lines[$i] -match 'lrange\(') {
                    $lineNum = $i + 1
                    Write-Host "  [BLOCK] LRANGE+LTRIM 非原子 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
                    Write-Host "          修复：用 Lua 脚本或 pipeline 事务封装" -ForegroundColor DarkGray
                    $ISSUE_COUNT++
                    $found = $true
                    break
                }
            }
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 未发现非原子 Redis 操作" -ForegroundColor Green }

# ============================================================
# 检查 6/12：内部接口缺鉴权检查（verify_localhost）
# 对应 config.yaml: hard_constraints.rules.internal_route_no_auth
# ============================================================
Write-Host "[6/12] 检查内部接口缺鉴权..." -ForegroundColor Yellow
$found = $false
$internalDir = Join-Path $SourceDir "routers\internal"
if (Test-Path $internalDir) {
    $internalFiles = Get-ChildItem -Path $internalDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue
    foreach ($file in $internalFiles) {
        $content = Get-Content $file.FullName -Raw -Encoding UTF8
        $lines = @(Get-Content $file.FullName -Encoding UTF8)
        # 查找所有 @router 装饰器位置
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '@router\.(get|post|put|delete)\(') {
                # 检查后续 30 行内是否含 verify_localhost 或 Depends(verify_localhost)
                $endLine = [Math]::Min($i + 30, $lines.Count - 1)
                $funcBlock = $lines[$i..$endLine] -join "`n"
                if ($funcBlock -notmatch 'verify_localhost') {
                    $lineNum = $i + 1
                    Write-Host "  [BLOCK] 内部接口缺 verify_localhost L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
                    Write-Host "          修复：加 _: None = Depends(verify_localhost)" -ForegroundColor DarkGray
                    $ISSUE_COUNT++
                    $found = $true
                }
            }
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 所有内部接口均已鉴权" -ForegroundColor Green }

# ============================================================
# 检查 7/12：Enum 字段未 .value 检查
# 对应 config.yaml: hard_constraints.rules.enum_field_without_value
# ============================================================
Write-Host "[7/12] 检查 Enum 字段未 .value..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配 Workflow(Source|Status|StepName|StepStatus).XXX 但后面无 .value
        # 排除模型定义本身（mapped_column default=...）和枚举定义
        if ($lines[$i] -match 'Workflow(Source|Status|StepName|StepStatus)\.\w+') {
            # 跳过枚举定义文件（models/workflow.py）
            if ($file.Name -eq "workflow.py" -and $file.FullName -match "models") {
                continue
            }
            # 跳过已带 .value 的
            if ($lines[$i] -match 'Workflow(Source|Status|StepName|StepStatus)\.\w+\.value') {
                continue
            }
            # 跳过比较语句（== WorkflowStatus.RUNNING 是合法的）
            if ($lines[$i] -match '==\s*Workflow(Status|Source|StepName|StepStatus)\.') {
                continue
            }
            # 仅检查序列化场景（dict 构造、return 语句）
            if ($lines[$i] -match '("status"|"source"|"step")\s*:\s*\w*Workflow') {
                $lineNum = $i + 1
                Write-Host "  [WARN] Enum 字段可能未 .value L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
                Write-Host "         修复：序列化时用 .value，如 source.value" -ForegroundColor DarkGray
                $WARN_COUNT++
                $found = $true
            }
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] Enum 字段均正确处理 .value" -ForegroundColor Green }

# ============================================================
# 检查 8/12：敏感词过滤器未初始化检查
# 对应 config.yaml: hard_constraints.rules.sensitive_filter_not_initialized
# ============================================================
Write-Host "[8/12] 检查敏感词过滤器未初始化..." -ForegroundColor Yellow
$found = $false
# 检查启动入口文件是否调用 load_words
$startupFiles = @(
    (Join-Path $ProjectRoot "backend\app\main.py"),
    (Join-Path $ProjectRoot "backend\app\services\workflow_scheduler.py")
)
$loadWordsCalled = $false
foreach ($startupFile in $startupFiles) {
    if (Test-Path $startupFile) {
        $content = Get-Content $startupFile -Raw -Encoding UTF8
        if ($content -match 'load_words\(') {
            $loadWordsCalled = $true
            if ($ShowVerbose) { Write-Host "  [INFO] load_words 在 $(Get-RelPath $startupFile) 中调用" -ForegroundColor Gray }
        }
    }
}
# 检查是否有任何文件 import sensitive_filter 但启动文件未初始化
$sensitiveUsed = $false
foreach ($file in $AllFiles) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    if ($content -match 'sensitive_filter') {
        $sensitiveUsed = $true
        break
    }
}
if ($sensitiveUsed -and -not $loadWordsCalled) {
    Write-Host "  [BLOCK] 敏感词过滤器被使用但 load_words() 从未在启动文件中调用" -ForegroundColor Red
    Write-Host "          修复：在 main.py lifespan 或 WorkflowScheduler.__init__ 调用 load_words()" -ForegroundColor DarkGray
    $ISSUE_COUNT++
    $found = $true
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 敏感词过滤器已正确初始化" -ForegroundColor Green }

# ============================================================
# 检查 9/12：PermissionError 覆盖内置异常检查
# 对应 config.yaml: hard_constraints.rules.builtin_exception_shadowing
# ============================================================
Write-Host "[9/12] 检查内置异常覆盖..." -ForegroundColor Yellow
$found = $false
$builtinExceptions = @("PermissionError", "KeyError", "ValueError", "TypeError", "FileNotFoundError")
foreach ($file in $AllFiles) {
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        foreach ($exc in $builtinExceptions) {
            if ($lines[$i] -match "class\s+$exc\s*\(") {
                $lineNum = $i + 1
                Write-Host "  [BLOCK] 覆盖内置异常 $exc L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
                Write-Host "          修复：加业务前缀，如 Biz$exc" -ForegroundColor DarkGray
                $ISSUE_COUNT++
                $found = $true
            }
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 未发现内置异常覆盖" -ForegroundColor Green }

# ============================================================
# 检查 10/12：裸 SQL 注入检查
# 对应 config.yaml: hard_constraints.rules.bare_sql_injection
# ============================================================
Write-Host "[10/12] 检查裸 SQL 注入..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配 text(f"...") 或 text(f'...')  f-string 拼接 SQL
        if ($lines[$i] -match 'text\(\s*f["'']') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] SQL 注入风险（f-string 拼接）L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：参数化 text(\"...WHERE id=:id\"), {\"id\": x}" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
        # 匹配 f"SELECT / f"INSERT / f"UPDATE / f"DELETE
        if ($lines[$i] -match 'f["'']\s*(SELECT|INSERT|UPDATE|DELETE) ') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] SQL 注入风险（f-string SQL）L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：参数化查询" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 未发现 SQL 注入风险" -ForegroundColor Green }

# ============================================================
# 检查 11/12：print() 语句检查
# 对应 config.yaml: hard_constraints.rules.print_statement
# ============================================================
Write-Host "[11/12] 检查 print() 语句..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    # 豁免文件
    if ($PrintExemptFiles -contains $file.Name) {
        continue
    }
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配行首 print（排除 logger.print 之类）
        if ($lines[$i] -match '^\s*print\(') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] print() 语句 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "          修复：用 logging.getLogger(__name__)" -ForegroundColor DarkGray
            $ISSUE_COUNT++
            $found = $true
        }
        # 匹配 print(traceback.format_exc())
        if ($lines[$i] -match 'print\(traceback\.format_exc\(\)\)') {
            $lineNum = $i + 1
            Write-Host "  [WARN] print(traceback) 应改用 logger.exception L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
            $found = $true
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] 未发现 print() 语句" -ForegroundColor Green }

# ============================================================
# 检查 12/12：finally 块无条件删除锁检查
# 对应 config.yaml: hard_constraints.rules.finally_unconditional_release
# ============================================================
Write-Host "[12/12] 检查 finally 块无条件 release 锁..." -ForegroundColor Yellow
$found = $false
foreach ($file in $AllFiles) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    $lines = @(Get-Content $file.FullName -Encoding UTF8)
    # 匹配 finally: 后跟 await xxx.release( 但前面无 lock_acquired 判断
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*finally:') {
            # 检查 finally 块内（后续 5 行）是否有 release(
            $endLine = [Math]::Min($i + 5, $lines.Count - 1)
            $finallyBlock = $lines[$i..$endLine] -join "`n"
            if ($finallyBlock -match 'release\(') {
                # 检查是否在 finally 块内有 lock_acquired / if 判断
                if ($finallyBlock -notmatch 'if\s+\w*[Ll]ock') {
                    # 再检查 try 块内是否有 lock_acquired 标志
                    $tryStart = $i
                    while ($tryStart -gt 0 -and $lines[$tryStart] -notmatch '^\s*try:') {
                        $tryStart--
                    }
                    $tryBlock = $lines[$tryStart..$i] -join "`n"
                    if ($tryBlock -notmatch 'lock_acquired') {
                        $lineNum = $i + 1
                        Write-Host "  [BLOCK] finally 无条件 release 锁 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
                        Write-Host "          修复：加 lock_acquired 标志，仅在自己获取时 release" -ForegroundColor DarkGray
                        $ISSUE_COUNT++
                        $found = $true
                    }
                }
            }
        }
    }
}
if (-not $found) { $CHECK_PASSED++; Write-Host "  [PASS] finally 块均正确保护锁释放" -ForegroundColor Green }

# ============================================================
# 汇总
# ============================================================
Write-Host "`n========== 扫描完成 ==========" -ForegroundColor Cyan
Write-Host "检查项通过: $CHECK_PASSED / 12" -ForegroundColor Gray
if ($ISSUE_COUNT -eq 0 -and $WARN_COUNT -eq 0) {
    Write-Host "未发现阻塞级问题，可以继续人工审查。" -ForegroundColor Green
} elseif ($ISSUE_COUNT -eq 0) {
    Write-Host "未发现阻塞级问题，但有 $WARN_COUNT 个警告，建议修复后继续。" -ForegroundColor Yellow
} else {
    Write-Host "发现 $ISSUE_COUNT 个阻塞级问题（必须修复），$WARN_COUNT 个警告。" -ForegroundColor Red
    Write-Host "请修复阻塞级问题后再提交。" -ForegroundColor Red
}

# 退出码：0 通过，1 有阻塞问题
if ($ISSUE_COUNT -gt 0) {
    exit 1
}
exit 0
