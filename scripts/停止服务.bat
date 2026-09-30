@echo off
chcp 936 >nul 2>&1
setlocal

cd /d "%~dp0.."

echo ========================================
echo   MorningBrief Service Stopper
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
