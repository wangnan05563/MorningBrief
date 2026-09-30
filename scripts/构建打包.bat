@echo off
chcp 936 >nul 2>&1
setlocal

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
echo Output: release\MorningBrief\MorningBrief.exe
echo.

REM [Step 0/6] Generate unique build version before packaging.
REM   - Writes MAJOR.MINOR.YYYYMMDD.NNN to project root package.json (user request)
REM   - Syncs same version to backend\VERSION for build-exe.ps1 / ISCC / About page
REM   - Every run increments NNN (or resets to 001 on new day) to guarantee uniqueness
echo [Pre-build 0/6] Assigning unique build version...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prebuild-version.ps1"
set "VER_EXIT_CODE=%ERRORLEVEL%"
if not "%VER_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Version bump failed. Build aborted.
    pause
    exit /b %VER_EXIT_CODE%
)
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
echo   Output dir: release\MorningBrief\
echo   EXE:        release\MorningBrief\MorningBrief.exe
echo   Installer:  release\MorningBrief-Setup-v*.exe (if Inno Setup enabled)
echo.
echo   Notes:
echo   - V1.2: SQLite embedded + TTLCache, no MySQL/Redis/Docker needed
echo   - Edit .env in exe dir before first run (JWT_SECRET / LLM_API_KEY / COS_*)
echo ========================================
pause >nul
exit /b 0
