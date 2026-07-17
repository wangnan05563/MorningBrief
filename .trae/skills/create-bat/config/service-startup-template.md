### 服务启动脚本模板（纯 ASCII + CRLF + 无 BOM）

生成服务启动脚本时必须包含以下健壮性要素（参考诊断流程 E 的检查清单）。所有 echo 内容为英文，中文提示由 .ps1 输出：

```bat
@echo off
REM <SCRIPT_DESCRIPTION>
cd /d "%~dp0.."
setlocal enabledelayedexpansion

echo ========================================
echo   <PROJECT_NAME> Starting...
echo ========================================

REM [1/N] Clean old process (PID file + port scan)
echo [1/N] Cleaning old process...

if exist "logs\<service>.pid" (
    for /f "tokens=*" %%a in (logs\<service>.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    del "logs\<service>.pid" >nul 2>&1
)

REM Kill process occupying port (fallback when PID file missing)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":<PORT>.*LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

REM Wait for port release (max N seconds), avoid bind failure after kill
set /a portWait=0
:wait_port_release
netstat -aon | findstr ":<PORT>.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    set /a portWait+=1
    if !portWait! lss <MAX_WAIT_SECONDS> (
        timeout /t 1 >nul 2>&1
        goto wait_port_release
    )
    echo [WARN] Port <PORT> still in use, startup may fail
)

timeout /t 1 >nul 2>&1

REM [2/N] Check dependencies
echo [2/N] Checking dependencies...

if not exist "<VENV_DIR>\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv <VENV_DIR>
    pause
    exit /b 1
)

if not exist "logs" mkdir logs

REM [3/N] Start service (redirect to log file for troubleshooting)
echo [3/N] Starting <SERVICE_NAME>...

REM Clear old log to avoid confusion
if exist "logs\<service>.log" del "logs\<service>.log" >nul 2>&1

REM Start service and redirect output to log file
start "<WINDOW_TITLE>" cmd /c "<VENV_DIR>\Scripts\python.exe -m <MODULE> <ARGS> > logs\<service>.log 2>&1"

REM Wait for port ready (max N seconds)
echo Waiting for service ready...
set /a tries=0
:wait_service
set /a tries+=1
ping -n 2 127.0.0.1 >nul 2>&1
netstat -aon | findstr ":<PORT>.*LISTENING" >nul 2>&1
if errorlevel 1 (
    if !tries! lss <MAX_RETRIES> goto wait_service
    echo [ERROR] Service failed to start within <TIMEOUT> seconds!
    echo.
    echo ====== Last 30 lines of log ======
    if exist "logs\<service>.log" (
        powershell -NoProfile -Command "Get-Content 'logs\<service>.log' -Tail 30 -Encoding UTF8"
    ) else (
        echo Log file not generated, process may have crashed on startup
    )
    echo ==============================
    echo Full log: logs\<service>.log
    pause
    exit /b 1
)

REM Record PID
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":<PORT>.*LISTENING"') do (
    echo %%a> "logs\<service>.pid"
)

REM [N/N] Verify process alive
echo [N/N] Verifying service...

set SERVICE_ALIVE=0
if exist "logs\<service>.pid" (
    for /f "tokens=*" %%a in (logs\<service>.pid) do (
        tasklist /FI "PID eq %%a" 2>nul | findstr "%%a" >nul 2>&1
        if not errorlevel 1 (
            set SERVICE_ALIVE=1
            echo   [OK] Service PID %%a
        )
    )
)

if "!SERVICE_ALIVE!"=="0" (
    echo   [FAIL] Service process not running!
    echo   Check logs\<service>.log for details
    pause
    exit /b 1
)

echo.
echo ========================================
echo   <PROJECT_NAME> Service Started
echo ========================================
echo   URL:  http://127.0.0.1:<PORT>
echo   Log:  logs\<service>.log
echo.
echo To stop: run scripts\<stop_script>.bat
echo.

start "" http://127.0.0.1:<PORT>/
timeout /t 3 >nul 2>&1
exit
```

**模板占位符说明**（所有参数从 config.json 读取，无硬编码）：
**模板占位符说明**：所有模板占位符及其 config.json 映射关系见 config/template-meta.json。