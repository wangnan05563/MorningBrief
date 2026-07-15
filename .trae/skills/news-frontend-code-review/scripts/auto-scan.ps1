# ========== MorningBrief 前端代码阻塞级问题自动扫描 v1.0.0 ==========
# 扫描 admin-web/src/ 下的 .vue/.js 文件 + miniprogram/ 下的 .js/.wxml/.wxss 文件
# 检查 12 项阻塞级问题（来源于 config.yaml#hard_constraints）
# 用法：pwsh .trae/skills/news-frontend-code-review/scripts/auto-scan.ps1

# 设置 UTF-8 输出，避免中文在 GBK 控制台显示为乱码
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$AdminWebSrc = Join-Path $ProjectRoot "admin-web\src"
$Miniprogram = Join-Path $ProjectRoot "miniprogram"
$ISSUE_COUNT = 0
$WARN_COUNT = 0

function Get-RelPath($fullPath) {
    if ($fullPath -like "$ProjectRoot*") {
        return $fullPath.Substring($ProjectRoot.Length + 1)
    }
    return $fullPath
}

if (-not (Test-Path $AdminWebSrc)) {
    Write-Host "[ERROR] admin-web/src 目录不存在: $AdminWebSrc" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Miniprogram)) {
    Write-Host "[ERROR] miniprogram 目录不存在: $Miniprogram" -ForegroundColor Red
    exit 1
}

Write-Host "========== MorningBrief 前端代码预检 ==========" -ForegroundColor Cyan
Write-Host "运营后台目录: $AdminWebSrc" -ForegroundColor Gray
Write-Host "小程序目录  : $Miniprogram" -ForegroundColor Gray
Write-Host "" -ForegroundColor Gray

# 收集待扫描文件
$AdminFiles = Get-ChildItem -Path $AdminWebSrc -Recurse -Include "*.vue", "*.js" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\\node_modules\\" -and $_.FullName -notmatch "\\dist\\" }

$MiniprogramFiles = Get-ChildItem -Path $Miniprogram -Recurse -Include "*.js", "*.wxml", "*.wxss" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\\node_modules\\" }

$AllFiles = @($AdminFiles) + @($MiniprogramFiles)

# 检查1：小程序循环依赖（api.js 顶部 require('./auth')）
Write-Host "[1/12] 检查小程序循环依赖（api.js 顶部 require auth）..." -ForegroundColor Yellow
$apiJs = Join-Path $Miniprogram "services\api.js"
if (Test-Path $apiJs) {
    $lines = Get-Content $apiJs -Encoding UTF8
    # 顶部 require 一定在第一个 function 定义之前；函数内的 require 是正确的延迟加载模式
    $firstFuncLine = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "\bfunction\b") {
            $firstFuncLine = $i
            break
        }
    }
    if ($firstFuncLine -ge 0) { $endLine = $firstFuncLine } else { $endLine = $lines.Count }
    for ($i = 0; $i -lt $endLine; $i++) {
        $line = $lines[$i]
        # 顶部 const { ... } = require('./auth')，非函数内部
        if ($line -match "const\s+\{[^}]*\}\s*=\s*require\(" -and $line -match "auth") {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] api.js 顶部 require auth 导致循环依赖 L${lineNum}: $(Get-RelPath $apiJs)" -ForegroundColor Red
            Write-Host "         修复：延迟到 request 函数内部 require" -ForegroundColor DarkGray
            $ISSUE_COUNT++
        }
    }
}

# 检查2：小程序 BASE_URL 硬编码 localhost
Write-Host "[2/12] 检查小程序 BASE_URL 硬编码..." -ForegroundColor Yellow
foreach ($file in $MiniprogramFiles) {
    if ($file.Name -notmatch '\.js$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "BASE_URL\s*=\s*['""]http://localhost") {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] BASE_URL 硬编码 localhost L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "         修复：按 __wxConfig.envVersion 环境切换" -ForegroundColor DarkGray
            $ISSUE_COUNT++
        }
    }
}

# 检查3：小程序 player 监听器未 off
Write-Host "[3/12] 检查小程序 player 监听器未 off..." -ForegroundColor Yellow
foreach ($file in $MiniprogramFiles) {
    if ($file.Name -notmatch '\.js$') { continue }
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    $onMethods = @('onPlay', 'onPause', 'onTimeUpdate', 'onEnded')
    foreach ($onMethod in $onMethods) {
        $offMethod = 'off' + $onMethod.Substring(2)
        if ($content -match "player\.$onMethod\(" -and $content -notmatch "player\.$offMethod\(") {
            Write-Host "  [BLOCK] player.$onMethod 未配对 $offMethod : $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "         修复：onUnload 中调用 player.$offMethod" -ForegroundColor DarkGray
            $ISSUE_COUNT++
        }
    }
}

# 检查4：isCurrentEpisode 用 title 判断
Write-Host "[4/12] 检查 isCurrentEpisode 用 title 判断..." -ForegroundColor Yellow
foreach ($file in $MiniprogramFiles) {
    if ($file.Name -notmatch '\.js$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "player\.title\s*===\s*(ep|episode)\.title") {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] isCurrentEpisode 用 title 判断 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "         修复：用 player.episodeId === ep.id 判断" -ForegroundColor DarkGray
            $ISSUE_COUNT++
        }
    }
}

# 检查5：globalData 未声明字段
Write-Host "[5/12] 检查 globalData 未声明字段..." -ForegroundColor Yellow
$appJs = Join-Path $Miniprogram "app.js"
if (Test-Path $appJs) {
    $content = Get-Content $appJs -Raw -Encoding UTF8
    $requiredFields = @('userInfo', 'token', 'player', 'todayEpisode', 'networkType', 'listenStats')
    foreach ($field in $requiredFields) {
        if ($content -notmatch "$field\s*:") {
            Write-Host "  [WARN] globalData 未显式声明字段: $field" -ForegroundColor DarkYellow
            Write-Host "         修复：app.js globalData 中添加 ${field}: null" -ForegroundColor DarkGray
            $WARN_COUNT++
        }
    }
} else {
    Write-Host "  [INFO] app.js 不存在，跳过" -ForegroundColor Gray
}

# 检查6：路由缺 404 兜底（反向校验）
Write-Host "[6/12] 检查路由缺 404 兜底..." -ForegroundColor Yellow
$routerJs = Join-Path $AdminWebSrc "router\index.js"
if (Test-Path $routerJs) {
    $content = Get-Content $routerJs -Raw -Encoding UTF8
    if ($content -notmatch 'pathMatch') {
        Write-Host "  [BLOCK] 路由表缺少 404 兜底路由: $(Get-RelPath $routerJs)" -ForegroundColor Red
        Write-Host "         修复：添加 path: '/:pathMatch(.*)*' redirect" -ForegroundColor DarkGray
        $ISSUE_COUNT++
    }
} else {
    Write-Host "  [INFO] router/index.js 不存在，跳过" -ForegroundColor Gray
}

# 检查7：console.log 检查
Write-Host "[7/12] 检查 console.log..." -ForegroundColor Yellow
foreach ($file in $AllFiles) {
    if ($file.Name -notmatch '\.(vue|js)$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        if ($line -match "console\.log\(" -and $line -notmatch "^\s*//" -and $line -notmatch "^\s*\*") {
            $lineNum = $i + 1
            Write-Host "  [WARN] console.log 调试输出 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    }
}

# 检查8：debugger 检查
Write-Host "[8/12] 检查 debugger..." -ForegroundColor Yellow
foreach ($file in $AllFiles) {
    if ($file.Name -notmatch '\.(vue|js)$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*debugger\s*;?\s*$") {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] debugger 调试器语句 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查9：API 路径判断过宽（includes '/login'）
Write-Host "[9/12] 检查 API 路径判断过宽（includes /login）..." -ForegroundColor Yellow
foreach ($file in $AdminFiles) {
    if ($file.Name -notmatch '\.(vue|js)$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "pathname\.includes\(.*/login" -or $lines[$i] -match "location\.pathname\.includes\(.*/login") {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 路径判断用 includes('/login') 会误匹配 /login-callback L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            Write-Host "         修复：改用 pathname === '/login' 严格相等" -ForegroundColor DarkGray
            $ISSUE_COUNT++
        }
    }
}

# 检查10：前后端字段名不一致（category vs categories）
Write-Host "[10/12] 检查字段名不一致（category vs categories）..." -ForegroundColor Yellow
foreach ($file in $AllFiles) {
    if ($file.Name -notmatch '\.(vue|js)$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        # 匹配 .category 但排除 .category_ 和 .categoryId
        if ($line -match "\.category\b" -and $line -notmatch "category_" -and $line -notmatch "categoryId" -and $line -notmatch "^\s*//") {
            $lineNum = $i + 1
            Write-Host "  [WARN] 后端返回 categories（复数），前端用 .category（单数） L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            Write-Host "         修复：统一用 .categories" -ForegroundColor DarkGray
            $WARN_COUNT++
        }
    }
}

# 检查11：Vue 组件缺 script setup
Write-Host "[11/12] 检查 Vue 组件缺 script setup..." -ForegroundColor Yellow
foreach ($file in $AdminFiles) {
    if ($file.Name -notmatch '\.vue$') { continue }
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    # 有 <script> 但没有 <script setup>
    $hasScript = $content -match "<script"
    $hasScriptSetup = $content -match "<script\s+setup"
    if ($hasScript -and -not $hasScriptSetup) {
        Write-Host "  [WARN] Vue 组件未用 <script setup> 语法 : $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
        Write-Host "         修复：改为 <script setup>（项目规范）" -ForegroundColor DarkGray
        $WARN_COUNT++
    }
}

# 检查12：完播率单位检查
Write-Host "[12/12] 检查完播率单位（*100 需注释）..." -ForegroundColor Yellow
foreach ($file in $AllFiles) {
    if ($file.Name -notmatch '\.(vue|js)$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "completion_rate\s*\*\s*100" -or $lines[$i] -match "completed_rate\s*\*\s*100") {
            # 检查前后2行是否有注释说明单位
            $hasComment = $false
            $start = [Math]::Max(0, $i - 2)
            $end = [Math]::Min($lines.Count - 1, $i + 2)
            for ($j = $start; $j -le $end; $j++) {
                if ($lines[$j] -match "//" -and ($lines[$j] -match "0-1" -or $lines[$j] -match "0-100" -or $lines[$j] -match "单位" -or $lines[$j] -match "unit")) {
                    $hasComment = $true
                    break
                }
            }
            if (-not $hasComment) {
                $lineNum = $i + 1
                Write-Host "  [WARN] 完播率 *100 未注释说明单位 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
                Write-Host "         修复：添加注释说明后端返回 0-1，前端 *100 转 0-100" -ForegroundColor DarkGray
                $WARN_COUNT++
            }
        }
    }
}

# 汇总
Write-Host "" -ForegroundColor Cyan
Write-Host "========== 扫描完成 ==========" -ForegroundColor Cyan
if ($ISSUE_COUNT -eq 0 -and $WARN_COUNT -eq 0) {
    Write-Host "未发现阻塞级问题，可以继续人工审查。" -ForegroundColor Green
} elseif ($ISSUE_COUNT -eq 0) {
    Write-Host "未发现阻塞级问题，但有 $WARN_COUNT 个警告，建议修复后继续。" -ForegroundColor Yellow
} else {
    Write-Host "发现 $ISSUE_COUNT 个阻塞级问题（必须修复），$WARN_COUNT 个警告。" -ForegroundColor Red
    Write-Host "请修复阻塞级问题后再提交。" -ForegroundColor Red
}
