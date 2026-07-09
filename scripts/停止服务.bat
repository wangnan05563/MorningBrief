@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 目录，切回项目根目录
cd /d "%~dp0.."

echo ========================================
echo   20_News 停止服务
echo ========================================
echo.
echo 停止方式：
echo   1. 读取 .run\20-news.pid 停止指定进程
echo   2. 兜底按进程名查找（20-news.exe / launcher.py）
echo.
echo 用法：停止服务.bat         优雅停止
echo       停止服务.bat -Force  强制终止
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*

echo.
echo 按任意键关闭窗口...
pause >nul
exit