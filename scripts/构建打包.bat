@echo off
chcp 65001 >nul 2>&1
setlocal

REM Keep this entry script ASCII-only for reliable cmd.exe parsing.
cd /d "%~dp0.."

echo ========================================
echo   MorningBrief EXE Builder
echo ========================================
echo.
echo Build steps:
echo   1. Prepare build venv (.venv-build)
echo   2. Install deps + PyInstaller
echo   3. Build admin-web SPA (if exists)
echo   4. PyInstaller packaging
echo   5. Copy external resources
echo   6. Generate installer (Inno Setup, auto-install if missing)
echo.
echo Output: dist\MorningBrief\MorningBrief.exe
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*
set "BUILD_EXIT_CODE=%ERRORLEVEL%"

if not "%BUILD_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Build failed. Review the messages above.
    pause
    exit /b %BUILD_EXIT_CODE%
)

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo   Output dir: dist\MorningBrief\
echo   EXE:        dist\MorningBrief\MorningBrief.exe
echo   Installer:  dist\MorningBrief-Setup-v*.exe (if Inno Setup enabled)
echo.
echo   Notes:
echo   - V1.2: SQLite embedded + TTLCache, no MySQL/Redis/Docker needed
echo   - Edit .env in exe dir before first run (JWT_SECRET / LLM_API_KEY / COS_*)
echo ========================================
pause
exit /b 0
