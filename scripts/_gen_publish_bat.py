# -*- coding: utf-8 -*-
"""Emit scripts/一键发布.bat as pure-ASCII, CRLF, no-BOM so it satisfies the
project's batch encoding contract (see scripts/tests/bat-encoding.Tests.ps1 and
scripts/_verify_bat.py). Mirrors scripts/_gen_bat.py: the .bat entry layer is
ASCII-only and uses `chcp 936` (GBK) per the test contract, while all
non-ASCII business logic (build, version parse, git log) lives in .ps1 / .py.

The publish flow is adapted from the reference at
D:/code/otherProjects/18_comparePakage/tooling/scripts/一键发布.bat:
  1) build EXE + Inno Setup installer (skip with MB_SKIP_BUILD=1)
  2) locate release\MorningBrief-Setup-v*.exe
  3) generate release notes from git log if missing
  4) publish-release.py creates the GitHub Release + uploads the asset

To stay ASCII-only the .bat calls the ASCII-named prebuild-version.ps1 /
build-exe.ps1 directly (the same scripts 构建打包.bat wraps) rather than the
Chinese-named 构建打包.bat.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

PUBLISH = [
    "@echo off",
    "chcp 936 >nul 2>&1",
    "setlocal",
    "",
    "cd /d \"%~dp0..\"",
    "",
    "echo ========================================",
    "echo   MorningBrief One-Click Publish",
    "echo ========================================",
    "echo.",
    "echo Steps:",
    "echo   1. Build EXE + Inno Setup installer (skip with MB_SKIP_BUILD=1)",
    "echo   2. Locate release\\MorningBrief-Setup-v*.exe",
    "echo   3. Generate release notes (git log, if missing)",
    "echo   4. Create GitHub Release + upload asset",
    "echo.",
    "echo Output: GitHub Release tag = installer version",
    "echo.",
    "",
    "REM ---------- paths ----------",
    "set \"RELEASE_DIR=%CD%\\release\"",
    "set \"PUBLISH_PY=%~dp0publish-release.py\"",
    "set \"SETUP_EXE=\"",
    "",
    "REM ---------- 1) build (optional, skipped when MB_SKIP_BUILD is set) ----------",
    "if not defined MB_SKIP_BUILD (",
    "    echo [1/4] Building EXE + installer...",
    "    powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0prebuild-version.ps1\"",
    "    if errorlevel 1 ( echo [ERROR] version bump failed & pause & exit /b 1 )",
    "    powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0build-exe.ps1\" %*",
    "    if errorlevel 1 ( echo [ERROR] build failed & pause & exit /b 1 )",
    ") else (",
    "    echo [1/4] MB_SKIP_BUILD set - reusing existing installer",
    ")",
    "",
    "REM ---------- 2) locate newest installer ----------",
    "echo [2/4] Locating installer...",
    "for /f \"delims=\" %%f in ('dir /b /o:-d \"%RELEASE_DIR%\\MorningBrief-Setup-v*.exe\" 2^>nul') do (",
    "    if not defined SETUP_EXE set \"SETUP_EXE=%RELEASE_DIR%\\%%f\"",
    ")",
    "if not defined SETUP_EXE ( echo [ERROR] no MorningBrief-Setup-v*.exe found in release\\ & pause & exit /b 1 )",
    "echo   Installer: %SETUP_EXE%",
    "",
    "REM ---------- extract version from installer filename ----------",
    "for %%f in (\"%SETUP_EXE%\") do set \"SETUP_BASE=%%~nf\"",
    "for /f \"delims=\" %%v in ('powershell -NoProfile -Command \"$b='%SETUP_BASE%' -replace '^MorningBrief-Setup-v','' -replace '\\.exe$',''; $b\"') do set \"VER=%%v\"",
    "if not defined VER ( echo [ERROR] cannot parse version from %SETUP_BASE% & pause & exit /b 1 )",
    "echo   Version : %VER%",
    "",
    "REM ---------- 3) release notes ----------",
    "echo [3/4] Preparing release notes...",
    "set \"NOTES=%CD%\\release-notes-%VER%.md\"",
    "if not exist \"%NOTES%\" (",
    "    set \"NOTES=%CD%\\release-notes-%VER%.auto.md\"",
    "    echo   notes missing, generating from git log...",
    "    (",
    "        echo # MorningBrief %VER%",
    "        echo.",
    "        echo Auto-generated release notes from git history. Replace with release-notes-%VER%.md for curated notes.",
    "        echo.",
    "        git -C \"%CD%\" log --no-merges --oneline -20 2^>nul",
    "    ) > \"%NOTES%\"",
    ")",
    "echo   Notes   : %NOTES%",
    "",
    "REM ---------- DRY RUN notice ----------",
    "if defined GH_DRY_RUN ( echo   [DRY-RUN] will NOT create Release or upload asset )",
    "",
    "REM ---------- 4) publish ----------",
    "echo [4/4] Publishing to GitHub Releases...",
    "set \"GH_TAG=%VER%\"",
    "set \"PYEXE=python\"",
    "where python >nul 2>nul || set \"PYEXE=python3\"",
    "\"%PYEXE%\" \"%PUBLISH_PY%\" \"%SETUP_EXE%\" \"%NOTES%\" \"MorningBrief-Setup-v%VER%.exe\"",
    "if errorlevel 1 ( echo [ERROR] publish failed - check GH_TOKEN / git credential for github.com & pause & exit /b 1 )",
    "",
    "echo.",
    "echo ========================================",
    "echo   Publish Complete!",
    "echo ========================================",
    "echo   Release: https://github.com/wangnan05563/MorningBrief/releases/tag/%VER%",
    "echo.",
    "pause >nul",
    "exit /b 0",
]


def emit(name, lines):
    # join with CRLF, ensure a trailing CRLF, write as ASCII bytes with NO BOM.
    text = "\r\n".join(lines) + "\r\n"
    data = text.encode("ascii")  # raises if any char > 0x7F
    path = os.path.join(ROOT, name)
    with open(path, "wb") as f:
        f.write(data)
    print("wrote", path, len(data), "bytes (ascii/crlf/nobom)")


if __name__ == "__main__":
    emit("一键发布.bat", PUBLISH)
    print("done")
