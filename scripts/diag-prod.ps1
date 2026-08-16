<#
.SYNOPSIS
    生产机后端诊断脚本（在 win-20260220ins 上以【管理员】PowerShell 运行）
.DESCRIPTION
    排查小程序真机登录报 "appid missing" 的部署侧根因：
    1. 谁在监听 8000 端口（进程路径 / 启动时间）—— 确认是不是新打包的 exe
    2. 各候选部署目录的 .env 中 WX_APPID / WX_SECRET 是否非空
    用法：
        把本脚本拷到生产机，右键“用 PowerShell 运行”（或管理员 PowerShell 执行）
#>
$ErrorActionPreference = "SilentlyContinue"
$sep = "=" * 50

Write-Host $sep -ForegroundColor Cyan
Write-Host "  生产机后端诊断 (win-20260220ins)" -ForegroundColor Cyan
Write-Host $sep -ForegroundColor Cyan

# ---------- 1. 8000 端口监听进程 ----------
Write-Host "`n[1] 8000 端口监听进程" -ForegroundColor Yellow
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen
if ($conn) {
    $p = Get-Process -Id $conn.OwningProcess
    Write-Host "  PID       = $($p.Id)"
    Write-Host "  Name      = $($p.ProcessName)"
    Write-Host "  Path      = $($p.Path)"
    if ($p.Path -and (Test-Path $p.Path)) {
        $exeItem = Get-Item $p.Path
        Write-Host "  ExeMTime  = $($exeItem.LastWriteTime)"
        Write-Host "  >>> 对比：本机新打包 exe 时间为 2026-08-04 21:04 左右。" -ForegroundColor Magenta
        Write-Host "  >>> 若此处时间早于该值，说明跑的是【旧 exe（修复前打包）】。" -ForegroundColor Magenta
    }
} else {
    Write-Host "  [!] 没有任何进程监听 8000 端口！说明当前后端根本没起来，" -ForegroundColor Red
    Write-Host "      真机请求可能被转发到了别的服务或已超时。" -ForegroundColor Red
}

# ---------- 2. 所有疑似后端进程 ----------
Write-Host "`n[2] 全部 MorningBrief / python 进程" -ForegroundColor Yellow
Get-Process | Where-Object { $_.ProcessName -match 'MorningBrief|python' } | ForEach-Object {
    Write-Host "  PID=$($_.Id) Name=$($_.ProcessName) Path=$($_.Path) StartTime=$($_.StartTime)"
}

# ---------- 3. 各候选目录 .env 的微信凭证 ----------
Write-Host "`n[3] 候选目录 .env 中的 WX_APPID / WX_SECRET" -ForegroundColor Yellow
$scanDirs = @(
    "C:\Program Files\MorningBrief",
    "C:\Program Files (x86)\MorningBrief",
    "C:\MorningBrief",
    "D:\MorningBrief",
    "D:\code\otherProjects\20_News\release\dist\MorningBrief",
    $PSScriptRoot,
    (Get-Location).Path
)
$seen = @{}
foreach ($d in $scanDirs) {
    if (-not $d) { continue }
    $f = Join-Path $d ".env"
    if (Test-Path $f) {
        if ($seen.ContainsKey($f)) { continue }
        $seen[$f] = $true
        $lines = Get-Content $f
        $appidLine  = $lines | Where-Object { $_ -match '^WX_APPID=' }
        $secretLine = $lines | Where-Object { $_ -match '^WX_SECRET=' }
        $appidVal  = if ($appidLine)  { ($appidLine  -split '=', 2)[1].Trim() } else { $null }
        $secretVal = if ($secretLine) { ($secretLine -split '=', 2)[1].Trim() } else { $null }
        $ok = ($appidVal -and $appidVal.Length -gt 0 -and $secretVal -and $secretVal.Length -gt 0)
        $mark = if ($ok) { "OK 已配置" } else { "!!! 缺失/为空" }
        Write-Host "  [$mark] $f"
        Write-Host "        WX_APPID=$(if($appidVal){'***已配置***'}else{'(空)'})  WX_SECRET=$(if($secretVal){'***已配置***'}else{'(空)'})"
    }
}
if ($seen.Count -eq 0) {
    Write-Host "  [!] 未在任何候选目录找到 .env 文件！" -ForegroundColor Red
}

Write-Host "`n" $sep -ForegroundColor Cyan
Write-Host "  诊断结束。请把以上输出贴回给排查方。" -ForegroundColor Cyan
Write-Host $sep -ForegroundColor Cyan
