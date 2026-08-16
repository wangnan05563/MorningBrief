$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$iconsDir = Join-Path $scriptRoot '..\icons'
$svgSrcDir = $scriptRoot

if (-not (Test-Path $iconsDir)) {
    New-Item -ItemType Directory -Path $iconsDir -Force | Out-Null
}
$iconsDir = (Resolve-Path $iconsDir).Path

$iconConfigs = @(
    @{ Svg = 'tab-today-active.svg';       Out = 'tab-today-active.png';       Size = 81 }
    @{ Svg = 'tab-today-inactive.svg';     Out = 'tab-today-inactive.png';     Size = 81 }
    @{ Svg = 'tab-history-active.svg';     Out = 'tab-history-active.png';     Size = 81 }
    @{ Svg = 'tab-history-inactive.svg';    Out = 'tab-history-inactive.png';   Size = 81 }
    @{ Svg = 'tab-profile-active.svg';     Out = 'tab-profile-active.png';     Size = 81 }
    @{ Svg = 'tab-profile-inactive.svg';   Out = 'tab-profile-inactive.png';   Size = 81 }
    @{ Svg = 'play.svg';                   Out = 'play.png';                   Size = 48 }
    @{ Svg = 'pause.svg';                  Out = 'pause.png';                  Size = 48 }
    @{ Svg = 'skip-back.svg';              Out = 'skip-back.png';              Size = 48 }
    @{ Svg = 'skip-forward.svg';           Out = 'skip-forward.png';           Size = 48 }
    @{ Svg = 'play-mini.svg';              Out = 'play-mini.png';              Size = 32 }
    @{ Svg = 'favorite.svg';               Out = 'favorite.png';               Size = 48 }
    @{ Svg = 'favorite-filled.svg';        Out = 'favorite-filled.png';         Size = 48 }
    @{ Svg = 'moon.svg';                  Out = 'moon.png';                   Size = 48 }
    @{ Svg = 'alarm.svg';                 Out = 'alarm.png';                  Size = 48 }
    @{ Svg = 'search.svg';                Out = 'search.png';                 Size = 48 }
    @{ Svg = 'chevron-right.svg';         Out = 'chevron-right.png';          Size = 32 }
    @{ Svg = 'alert.svg';                 Out = 'alert.png';                  Size = 48 }
    @{ Svg = 'duration.svg';              Out = 'duration.png';              Size = 32 }
    @{ Svg = 'headphones.svg';            Out = 'headphones.png';             Size = 96 }
    @{ Svg = 'music.svg';                 Out = 'music.png';                  Size = 96 }
    @{ Svg = 'newspaper.svg';             Out = 'newspaper.png';              Size = 96 }
    @{ Svg = 'radio.svg';                 Out = 'radio.png';                  Size = 96 }
    # 应用 logo：96x96，关于页/开屏页品牌标识
    @{ Svg = 'app-logo.svg';             Out = 'app-logo.png';               Size = 96 }
    # 小程序主图标：512x512，上传至微信后台解决"最近使用"空白图标
    @{ Svg = 'app-icon.svg';             Out = 'app-icon.png';               Size = 512 }
)

Write-Host "SVG Source: $svgSrcDir"
Write-Host "PNG Output:  $iconsDir"
Write-Host "Total icons: $($iconConfigs.Count)"
Write-Host ""

$success = 0
$failed = 0

foreach ($cfg in $iconConfigs) {
    $svgPath = Join-Path $svgSrcDir $cfg.Svg
    $outPath = Join-Path $iconsDir $cfg.Out
    $size = $cfg.Size
    if (-not (Test-Path $svgPath)) {
        Write-Warning "  [MISS] $($cfg.Svg)"
        $failed++
        continue
    }
    & magick convert -background none -density 144 -resize "$($size)x$($size)" $svgPath $outPath
    if ($LASTEXITCODE -eq 0 -and (Test-Path $outPath)) {
        $sz = (Get-Item $outPath).Length
        Write-Host "  [OK]   $($cfg.Out) ($($size)x$($size), $sz bytes)"
        $success++
    } else {
        Write-Warning "  [FAIL] $($cfg.Out)"
        $failed++
    }
}

Write-Host ""
Write-Host "Success: $success, Failed: $failed"
