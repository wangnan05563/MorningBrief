@echo off
chcp 936 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0.."

echo ========================================
echo   MorningBrief One-Click Publish
echo ========================================
echo.
echo Steps:
echo   0. Preflight: token / git / PowerShell / Python / remote / worktree
echo   1. Build EXE + Inno Setup installer (skip with MB_SKIP_BUILD=1)
echo   2. Locate release\MorningBrief-Setup-v*.exe
echo   3. Generate release notes (git log, if missing)
echo   4. Create GitHub Release + upload asset
echo.
echo Output: GitHub Release tag = installer version
echo Env   : MB_SKIP_BUILD=1 MB_ALLOW_DIRTY=1 MB_NO_PAUSE=1 GH_DRY_RUN=1
echo.

REM ---------- paths ----------
set "ROOT=%CD%"
set "ENV_FILE=%ROOT%\.env"
set "RELEASE_DIR=%ROOT%\release"
set "PUBLISH_PY=%~dp0publish-release.py"
set "SETUP_EXE="

REM ---------- 0) preflight checks (fail fast before any write) ----------
echo [0/4] Preflight checks...

REM 0.1 git
where git >nul 2>nul
if errorlevel 1 ( echo [FAIL] git not found in PATH & goto :fail )
for /f "tokens=*" %%v in ('git --version 2^>nul') do echo   [OK]   %%v

REM 0.2 PowerShell: version bump and build steps are PowerShell scripts
where powershell >nul 2>nul
if errorlevel 1 ( echo [FAIL] PowerShell not found in PATH & goto :fail )
echo   [OK]   PowerShell available

REM 0.3 Python: publish-release.py is the REST fallback when gh is absent
set "PYEXE="
where python >nul 2>nul
if not errorlevel 1 set "PYEXE=python"
if defined PYEXE goto :python_ready
where python3 >nul 2>nul
if not errorlevel 1 set "PYEXE=python3"
:python_ready
if defined PYEXE ( echo   [OK]   Python: !PYEXE! ) else ( echo [FAIL] Python not found in PATH & goto :fail )

REM 0.4 token: environment first, then repo-root .env; never echo the value
if not defined GH_TOKEN (
    for /f "tokens=1,* delims==" %%a in ('findstr /i "^GH_TOKEN=" "%ENV_FILE%" 2^>nul') do set "GH_TOKEN=%%b"
)
if not defined GITHUB_TOKEN (
    for /f "tokens=1,* delims==" %%a in ('findstr /i "^GITHUB_TOKEN=" "%ENV_FILE%" 2^>nul') do set "GITHUB_TOKEN=%%b"
)
if defined GH_TOKEN set "GH_TOKEN=!GH_TOKEN:"=!"
if defined GITHUB_TOKEN set "GITHUB_TOKEN=!GITHUB_TOKEN:"=!"
if not defined GH_TOKEN if defined GITHUB_TOKEN set "GH_TOKEN=!GITHUB_TOKEN!"
if defined GH_TOKEN (
    echo   [OK]   GitHub token loaded from environment or .env
) else (
    echo   [WARN] no GH_TOKEN found - git credential store will be tried
)

REM 0.5 gh CLI is optional: publish-release.py falls back to GitHub REST
where gh >nul 2>nul
if not errorlevel 1 (
    echo   [OK]   gh CLI available
) else (
    echo   [OK]   gh CLI absent - will use GitHub REST with token
)

REM 0.6 remote must be a GitHub repository
set "ORIGIN="
for /f "tokens=*" %%u in ('git -C "%ROOT%" remote get-url origin 2^>nul') do set "ORIGIN=%%u"
if not defined ORIGIN ( echo [FAIL] git remote origin is missing & goto :fail )
echo "!ORIGIN!" | findstr /i "github.com" >nul
if errorlevel 1 ( echo [FAIL] origin is not github.com: !ORIGIN! & goto :fail )
echo   [OK]   GitHub remote: !ORIGIN!

REM 0.7 worktree: build-hook version files are generated on every build,
REM     so they are allow-listed; any other uncommitted change blocks publish.
set "DIRTY_COUNT=0"
for /f "delims=" %%l in ('git -C "%ROOT%" status --porcelain ^| findstr /v /c:"backend/VERSION" /c:"backend/app/_build_info.py" /c:"package.json" 2^>nul') do set /a DIRTY_COUNT+=1
if !DIRTY_COUNT! EQU 0 (
    echo   [OK]   worktree clean
) else (
    echo   [WARN] worktree has !DIRTY_COUNT! unexpected uncommitted files
    if not defined GH_DRY_RUN if not defined MB_ALLOW_DIRTY (
        echo [FAIL] commit or stash changes first, or set MB_ALLOW_DIRTY=1
        goto :fail
    )
)

REM 0.8 branch warning
set "BRANCH="
for /f "tokens=*" %%b in ('git -C "%ROOT%" rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%b"
if defined BRANCH if /i not "!BRANCH!"=="main" echo   [WARN] current branch is !BRANCH!, not main

REM 0.9 build scripts must exist when a build is requested
if defined MB_SKIP_BUILD goto :preflight_done
if not exist "%~dp0prebuild-version.ps1" ( echo [FAIL] missing prebuild-version.ps1 & goto :fail )
if not exist "%~dp0build-exe.ps1" ( echo [FAIL] missing build-exe.ps1 & goto :fail )
echo   [OK]   build scripts present
:preflight_done
echo.

REM ---------- 1) build (optional, skipped when MB_SKIP_BUILD is set) ----------
if not defined MB_SKIP_BUILD (
    echo [1/4] Building EXE + installer...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prebuild-version.ps1"
    if errorlevel 1 ( echo [ERROR] version bump failed & goto :fail )
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*
    if errorlevel 1 ( echo [ERROR] build failed & goto :fail )
) else (
    echo [1/4] MB_SKIP_BUILD set - reusing existing installer
)

REM ---------- 2) locate newest installer ----------
echo [2/4] Locating installer...
for /f "delims=" %%f in ('dir /b /o:-d "%RELEASE_DIR%\MorningBrief-Setup-v*.exe" 2^>nul') do (
    if not defined SETUP_EXE set "SETUP_EXE=%RELEASE_DIR%\%%f"
)
if not defined SETUP_EXE ( echo [ERROR] no MorningBrief-Setup-v*.exe found in release\ & goto :fail )
echo   Installer: %SETUP_EXE%

REM ---------- extract version from installer filename ----------
for %%f in ("%SETUP_EXE%") do set "SETUP_BASE=%%~nf"
for /f "delims=" %%v in ('powershell -NoProfile -Command "$b='%SETUP_BASE%' -replace '^MorningBrief-Setup-v','' -replace '\.exe$',''; $b"') do set "VER=%%v"
if not defined VER ( echo [ERROR] cannot parse version from %SETUP_BASE% & goto :fail )
echo   Version : %VER%

REM ---------- 3) release notes ----------
echo [3/4] Preparing release notes...
set "NOTES=%CD%\release-notes-%VER%.md"
set "AUTO_NOTES=%CD%\release-notes-%VER%.auto.md"
if not exist "%NOTES%" (
    set "NOTES=%AUTO_NOTES%"
    echo   notes missing, generating from git log...
    (
        echo # MorningBrief %VER%
        echo.
        echo Auto-generated release notes from git history. Replace with release-notes-%VER%.md for curated notes.
        echo.
        git -C "%CD%" log --no-merges --oneline -20 2>nul
    ) > "%AUTO_NOTES%"
)
echo   Notes   : %NOTES%

REM ---------- DRY RUN notice ----------
if defined GH_DRY_RUN ( echo   [DRY-RUN] will NOT create Release or upload asset )

REM ---------- 4) publish ----------
echo [4/4] Publishing to GitHub Releases...
set "GH_TAG=%VER%"
"!PYEXE!" "%PUBLISH_PY%" "%SETUP_EXE%" "%NOTES%" "MorningBrief-Setup-v%VER%.exe"
if errorlevel 1 ( echo [ERROR] publish failed - check GH_TOKEN / git credential for github.com & goto :fail )

echo.
echo ========================================
echo   Publish Complete!
echo ========================================
echo   Release: https://github.com/wangnan05563/MorningBrief/releases/tag/%VER%
echo.
if not defined MB_NO_PAUSE pause >nul
exit /b 0

:fail
if not defined MB_NO_PAUSE pause
exit /b 1
