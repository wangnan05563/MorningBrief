@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 目录，切回项目根目录
cd /d "%~dp0.."

echo ========================================
echo   20_News 启动服务
echo ========================================
echo.
echo 启动方式（自动选择，默认开发模式）：
echo   - 优先启动开发模式（.venv + backend\launcher.py）
echo   - 回退到 exe 模式（dist\20-news\20-news.exe）
echo.
echo 参数（可选）：
echo   -Dev  强制开发模式
echo   -Exe  强制 exe 模式
echo.

REM -NoProfile：跳过用户自定义 profile（避免别名干扰）
REM -ExecutionPolicy Bypass：允许执行未签名脚本
REM -File：指定入口 ps1，%* 透传所有参数
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] 启动失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo 按任意键关闭窗口...
pause >nul
exit
