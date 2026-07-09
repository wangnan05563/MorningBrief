@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 目录，切回项目根目录
cd /d "%~dp0.."

echo ========================================
echo   20_News EXE 一键构建打包
echo ========================================
echo.
echo 构建流程：
echo   1. 创建/更新构建虚拟环境（.venv-build）
echo   2. 安装项目依赖 + PyInstaller
echo   3. 构建 admin-web 前端（SPA 产物）
echo   4. PyInstaller 打包后端为 exe
echo   5. 复制配置文件与前端产物
echo   6. 生成安装包（Inno Setup，未安装时自动安装）
echo.
echo 产物：dist\20-news\20-news.exe
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] 打包失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包完成！
echo ========================================
echo   产物目录：dist\20-news\
echo   启动程序：dist\20-news\20-news.exe
echo   安装包：  dist\20News-Setup-v*.exe（需 Inno Setup）
echo.
echo   注意：
echo   - V1.2 单机 exe：SQLite 嵌入式 + TTLCache，无需 MySQL/Redis/Docker
echo   - 首次运行前编辑 exe 同目录的 .env，填入 JWT_SECRET / LLM_API_KEY / COS_* 等密钥
echo ========================================
pause
exit
