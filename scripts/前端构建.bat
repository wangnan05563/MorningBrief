@echo off
chcp 65001 >nul 2>&1
setlocal

REM Keep this entry script ASCII-only for reliable cmd.exe parsing.
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
pause
exit /b 0
