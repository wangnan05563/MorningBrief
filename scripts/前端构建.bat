@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 目录，切回项目根目录
cd /d "%~dp0.."

echo ========================================
echo   20_News 前端构建（admin-web）
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-frontend.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] 前端构建失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo   前端构建完成！
echo ========================================
echo   产物目录：admin-web\dist\
echo   部署方式：由 FastAPI StaticFiles 服务（单机 exe 模式）
echo ========================================
pause
exit
