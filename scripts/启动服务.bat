@echo off
chcp 65001 >nul 2>&1
setlocal

REM Keep this entry script ASCII-only for reliable cmd.exe parsing.
cd /d "%~dp0.."

echo ========================================
echo   MorningBrief Service Launcher
echo ========================================
echo.
echo Launch mode is selected automatically.
echo Optional arguments: -Dev or -Exe
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "START_EXIT_CODE=%ERRORLEVEL%"

if not "%START_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Service startup failed. Review the messages above.
    pause
    exit /b %START_EXIT_CODE%
)

echo.
echo Press any key to close this launcher window...
pause >nul
exit /b 0
