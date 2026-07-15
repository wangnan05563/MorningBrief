<#
.SYNOPSIS
    MorningBrief 图标生成脚本（PNG + ICO）
.DESCRIPTION
    使用 .NET System.Drawing 绘制与 favicon.svg 相同的设计：
    圆角方形青色渐变背景 + 白色声波线条（播客新闻产品定位）
    生成产物：
    - admin-web/public/favicon-16x16.png
    - admin-web/public/favicon-32x32.png
    - admin-web/public/apple-touch-icon.png (180x180)
    - admin-web/public/android-chrome-192x192.png
    - admin-web/public/android-chrome-512x512.png
    - assets/MorningBrief.ico（多尺寸：16/32/48/64/128/256）
.NOTES
    无需安装任何依赖，使用 Windows 自带 .NET GDI+。
    ICO 采用 PNG 编码（Vista+ 支持），文件更小且支持 256 色深。
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $repoRoot

Add-Type -AssemblyName System.Drawing

# ============================================================
# 绘制函数：返回指定尺寸的 Bitmap
# ============================================================

function New-IconBitmap {
    param([int]$Size)

    $bmp = New-Object System.Drawing.Bitmap($Size, $Size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

    # 缩放比例：设计基于 64x64 viewBox
    $scale = $Size / 64.0

    # --- 圆角方形渐变背景 ---
    # 设计中 rx=16，背景 x=2 y=2 w=60 h=60
    $bgRect = New-Object System.Drawing.Rectangle(
        [int]([Math]::Round(2 * $scale)),
        [int]([Math]::Round(2 * $scale)),
        [int]([Math]::Round(60 * $scale)),
        [int]([Math]::Round(60 * $scale))
    )
    $radius = [int]([Math]::Round(16 * $scale))

    # 渐变：#7DD3DD → #5BC0BE（左上 → 右下）
    # 用 Point 重载避免 PowerShell 对 Rectangle+Enum 四参数绑定的类型歧义
    $colorStart = [System.Drawing.ColorTranslator]::FromHtml("#7DD3DD")
    $colorEnd = [System.Drawing.ColorTranslator]::FromHtml("#5BC0BE")
    $startPoint = New-Object System.Drawing.Point($bgRect.X, $bgRect.Y)
    $endPoint = New-Object System.Drawing.Point($bgRect.Right, $bgRect.Bottom)
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        $startPoint, $endPoint, $colorStart, $colorEnd
    )

    # 构建圆角矩形路径
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc($bgRect.X, $bgRect.Y, $radius * 2, $radius * 2, 180, 90)
    $path.AddArc($bgRect.Right - $radius * 2, $bgRect.Y, $radius * 2, $radius * 2, 270, 90)
    $path.AddArc($bgRect.Right - $radius * 2, $bgRect.Bottom - $radius * 2, $radius * 2, $radius * 2, 0, 90)
    $path.AddArc($bgRect.X, $bgRect.Bottom - $radius * 2, $radius * 2, $radius * 2, 90, 90)
    $path.CloseFigure()

    $g.FillPath($brush, $path)
    $brush.Dispose()
    $path.Dispose()

    # --- 白色声波线条 ---
    # 5 条竖线，linecap=round，stroke-width=4.5
    # 设计坐标（64x64）：
    #   x=20 y1=34 y2=30  (最外左)
    #   x=28 y1=40 y2=24
    #   x=36 y1=44 y2=20  (中间最高)
    #   x=44 y1=40 y2=24
    #   x=52 y1=34 y2=30  (最外右)
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::White, [float]([Math]::Max(1, 4.5 * $scale)))
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round

    $waves = @(
        @(20, 34, 30),
        @(28, 40, 24),
        @(36, 44, 20),
        @(44, 40, 24),
        @(52, 34, 30)
    )

    foreach ($w in $waves) {
        $x = $w[0] * $scale
        $y1 = $w[1] * $scale
        $y2 = $w[2] * $scale
        $g.DrawLine($pen, [float]$x, [float]$y1, [float]$x, [float]$y2)
    }

    $pen.Dispose()
    $g.Dispose()
    return $bmp
}

# ============================================================
# 生成 PNG 图标
# ============================================================

$publicDir = "admin-web\public"
$assetsDir = "assets"

# 确保目录存在
New-Item -ItemType Directory -Force $publicDir | Out-Null
New-Item -ItemType Directory -Force $assetsDir | Out-Null

$pngTargets = @(
    @{ Size = 16;  Name = "favicon-16x16.png" },
    @{ Size = 32;  Name = "favicon-32x32.png" },
    @{ Size = 180; Name = "apple-touch-icon.png" },
    @{ Size = 192; Name = "android-chrome-192x192.png" },
    @{ Size = 512; Name = "android-chrome-512x512.png" }
)

Write-Host "[generate-icons] 生成 PNG 图标..." -ForegroundColor Cyan
foreach ($t in $pngTargets) {
    $bmp = New-IconBitmap -Size $t.Size
    $outPath = Join-Path $publicDir $t.Name
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "  [OK] $outPath ($($t.Size)x$($t.Size))" -ForegroundColor Green
}

# ============================================================
# 生成多尺寸 ICO 文件（PNG 编码，Vista+ 支持）
# ============================================================

Write-Host "[generate-icons] 生成 ICO 文件..." -ForegroundColor Cyan

$icoSizes = @(16, 32, 48, 64, 128, 256)
$icoPath = Join-Path $assetsDir "MorningBrief.ico"

# 收集各尺寸 PNG 字节数据
$pngDataList = @()
foreach ($s in $icoSizes) {
    $bmp = New-IconBitmap -Size $s
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    $pngDataList += @{ Size = $s; Data = $ms.ToArray() }
    $ms.Dispose()
}

# ICO 文件格式：
#   Header (6 bytes): reserved(2)=0, type(2)=1, count(2)
#   Directory entries (16 bytes each):
#     width(1), height(1), colors(1)=0, reserved(1)=0,
#     planes(2)=1, bitcount(2)=32, size(4), offset(4)
#   Image data (PNG encoded)

$count = $pngDataList.Count
$headerSize = 6
$dirSize = 16 * $count
$dataOffset = $headerSize + $dirSize

# 计算总大小
$totalSize = $dataOffset
foreach ($entry in $pngDataList) {
    $totalSize += $entry.Data.Length
}

# 构造 ICO 字节数组
$ms = New-Object System.IO.MemoryStream
$bw = New-Object System.IO.BinaryWriter($ms)

# Header
$bw.Write([UInt16]0)          # reserved
$bw.Write([UInt16]1)          # type = ICO
$bw.Write([UInt16]$count)     # image count

# Directory entries
$currentOffset = $dataOffset
foreach ($entry in $pngDataList) {
    $s = $entry.Size
    # ICO 中 size 字段：0 表示 256
    $sizeByte = if ($s -eq 256) { [byte]0 } else { [byte]$s }
    $bw.Write([byte]$sizeByte)       # width
    $bw.Write([byte]$sizeByte)       # height
    $bw.Write([byte]0)               # color count (0 = 256+)
    $bw.Write([byte]0)               # reserved
    $bw.Write([UInt16]1)             # color planes
    $bw.Write([UInt16]32)            # bits per pixel
    $bw.Write([UInt32]$entry.Data.Length)  # image size
    $bw.Write([UInt32]$currentOffset)      # offset to image data
    $currentOffset += $entry.Data.Length
}

# Image data
foreach ($entry in $pngDataList) {
    $bw.Write($entry.Data)
}

$bw.Flush()
$icoBytes = $ms.ToArray()
$bw.Dispose()
$ms.Dispose()

[System.IO.File]::WriteAllBytes((Resolve-Path $assetsDir).Path + "\MorningBrief.ico", $icoBytes)
Write-Host "  [OK] $icoPath ($($icoSizes.Count) sizes: $($icoSizes -join '/'))" -ForegroundColor Green

Write-Host "[generate-icons] 完成" -ForegroundColor Cyan
