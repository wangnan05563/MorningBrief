# -*- coding: utf-8 -*-
"""Generate the four MorningBrief .bat entry scripts as pure-ASCII, CRLF, no-BOM
files so they pass scripts/tests/bat-encoding.Tests.ps1.

Each .bat keeps the thin-wrapper design from the original scripts (reusing the
path/config/command conventions that live in the corresponding .ps1), but the
entry layer itself is ASCII-only and uses `chcp 936` (GBK) per the test contract.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def emit(name, lines):
    # Join with CRLF, ensure a trailing CRLF, write as ASCII bytes with NO BOM.
    text = "\r\n".join(lines) + "\r\n"
    data = text.encode("ascii")  # raises if any char > 0x7F
    path = os.path.join(ROOT, name)
    with open(path, "wb") as f:
        f.write(data)
    print("wrote", path, len(data), "bytes (ascii/crlf/nobom)")


BUILD = [
    "@echo off",
    "chcp 936 >nul 2>&1",
    "setlocal",
    "",
    "cd /d \"%~dp0..\"",
    "",
    "echo ========================================",
    "echo   MorningBrief EXE Builder",
    "echo ========================================",
    "echo.",
    "echo Build steps:",
    "echo   1. Prepare build venv (.venv-build)",
    "echo   2. Install deps + PyInstaller",
    "echo   3. Build admin-web SPA (if exists)",
    "echo   4. PyInstaller packaging",
    "echo   5. Copy external resources",
    "echo   6. Generate installer (Inno Setup, auto-install if missing)",
    "echo.",
    "echo Output: release\\dist\\MorningBrief\\MorningBrief.exe",
    "echo.",
    "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0build-exe.ps1\" %*",
    "set \"BUILD_EXIT_CODE=%ERRORLEVEL%\"",
    "",
    "if not \"%BUILD_EXIT_CODE%\"==\"0\" (",
    "    echo.",
    "    echo [ERROR] Build failed. Review the messages above.",
    "    pause",
    "    exit /b %BUILD_EXIT_CODE%",
    ")",
    "",
    "echo.",
    "echo ========================================",
    "echo   Build Complete!",
    "echo ========================================",
    "echo   Output dir: release\\dist\\MorningBrief\\",
    "echo   EXE:        release\\dist\\MorningBrief\\MorningBrief.exe",
    "echo   Installer:  release\\dist\\MorningBrief-Setup-v*.exe (if Inno Setup enabled)",
    "echo.",
    "echo   Notes:",
    "echo   - V1.2: SQLite embedded + TTLCache, no MySQL/Redis/Docker needed",
    "echo   - Edit .env in exe dir before first run (JWT_SECRET / LLM_API_KEY / COS_*)",
    "echo ========================================",
    "pause >nul",
    "exit /b 0",
]

START = [
    "@echo off",
    "chcp 936 >nul 2>&1",
    "setlocal",
    "",
    "cd /d \"%~dp0..\"",
    "",
    "echo ========================================",
    "echo   MorningBrief Service Launcher",
    "echo ========================================",
    "echo.",
    "echo Launch mode is selected automatically.",
    "echo Optional arguments: -Dev or -Exe",
    "echo.",
    "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0start.ps1\" %*",
    "set \"START_EXIT_CODE=%ERRORLEVEL%\"",
    "",
    "if not \"%START_EXIT_CODE%\"==\"0\" (",
    "    echo.",
    "    echo [ERROR] Service startup failed. Review the messages above.",
    "    pause",
    "    exit /b %START_EXIT_CODE%",
    ")",
    "",
    "echo.",
    "echo Press any key to close this launcher window...",
    "pause >nul",
    "exit /b 0",
]

FE = [
    "@echo off",
    "chcp 936 >nul 2>&1",
    "setlocal",
    "",
    "cd /d \"%~dp0..\"",
    "",
    "echo ========================================",
    "echo   MorningBrief Frontend Builder (admin-web)",
    "echo ========================================",
    "echo.",
    "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0build-frontend.ps1\" %*",
    "set \"FE_EXIT_CODE=%ERRORLEVEL%\"",
    "",
    "if not \"%FE_EXIT_CODE%\"==\"0\" (",
    "    echo.",
    "    echo [ERROR] Frontend build failed. Review the messages above.",
    "    pause",
    "    exit /b %FE_EXIT_CODE%",
    ")",
    "",
    "echo.",
    "echo ========================================",
    "echo   Frontend Build Complete!",
    "echo ========================================",
    "echo   Output dir: apps/admin-web\\dist\\",
    "echo   Served by FastAPI StaticFiles (in exe mode)",
    "echo ========================================",
    "pause >nul",
    "exit /b 0",
]

STOP = [
    "@echo off",
    "chcp 936 >nul 2>&1",
    "setlocal",
    "",
    "cd /d \"%~dp0..\"",
    "",
    "echo ========================================",
    "echo   MorningBrief Service Stopper",
    "echo ========================================",
    "echo.",
    "echo Stop mode is selected automatically.",
    "echo Optional arguments: -Force (force kill)",
    "echo.",
    "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0stop.ps1\" %*",
    "set \"STOP_EXIT_CODE=%ERRORLEVEL%\"",
    "",
    "if not \"%STOP_EXIT_CODE%\"==\"0\" (",
    "    echo.",
    "    echo [ERROR] Service stop failed. Review the messages above.",
    "    pause",
    "    exit /b %STOP_EXIT_CODE%",
    ")",
    "",
    "echo.",
    "echo Press any key to close this stopper window...",
    "pause >nul",
    "exit /b 0",
]

emit("构建打包.bat", BUILD)
emit("启动服务.bat", START)
emit("前端构建.bat", FE)
emit("停止服务.bat", STOP)
print("done")
