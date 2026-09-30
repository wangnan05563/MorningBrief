@echo off
chcp 936 >nul 2>&1
setlocal

cd /d "%~dp0.."

echo ========================================
echo   MorningBrief Frontend Builder (admin-web)
echo ========================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-frontend.ps1" %*
set "FE_EXIT_CODE=%ERRORLEVEL%"

if not "%FE_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Frontend build failed. Review the messages above.
    pause
    exit /b %FE_EXIT_CODE%
)

echo.
echo ========================================
echo   Frontend Build Complete!
echo ========================================
echo   Output dir: apps/admin-web\dist\
echo   Served by FastAPI StaticFiles (in exe mode)
echo ========================================
pause >nul
exit /b 0
