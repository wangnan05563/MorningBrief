@echo off
chcp 65001 >nul 2>&1
setlocal

REM Keep this entry script ASCII-only for reliable cmd.exe parsing.
cd /d "%~dp0.."

echo ========================================
echo   20_News Service Stopper
echo ========================================
echo.
echo Stop mode is selected automatically.
echo Optional arguments: -Force (force kill)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
set "STOP_EXIT_CODE=%ERRORLEVEL%"

if not "%STOP_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Service stop failed. Review the messages above.
    pause
    exit /b %STOP_EXIT_CODE%
)

echo.
echo Press any key to close this stopper window...
pause >nul
exit /b 0
