@echo off
chcp 65001 >nul 2>&1
setlocal

REM Keep this entry script ASCII-only for reliable cmd.exe parsing.
cd /d "%~dp0.."

echo ========================================
echo   MorningBrief Environment Setup
echo ========================================
echo.
echo Setup steps:
echo   1. Check Node.js (frontend) / Python (backend)
echo   2. Create .env config file
echo   3. Create runtime directories
echo   4. Install frontend deps (npm install)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-env.ps1" %*
set "SETUP_EXIT_CODE=%ERRORLEVEL%"

if not "%SETUP_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Environment setup failed. Review the messages above.
    pause
    exit /b %SETUP_EXIT_CODE%
)

echo.
echo ========================================
echo   Environment Setup Complete!
echo ========================================
echo   Next steps:
echo   1. Edit backend\.env with actual keys (V1.2: no MYSQL/REDIS needed)
echo   2. Start service: double-click scripts\启动服务.bat or build exe
echo ========================================
pause >nul
exit /b 0
