@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 目录，切回项目根目录
cd /d "%~dp0.."

echo ========================================
echo   20_News 一键环境配置
echo ========================================
echo.
echo 配置流程：
echo   1. 检查 Node.js（前端构建用）/ Python（开发调试用）
echo   2. 创建 .env 配置文件
echo   3. 创建运行时数据目录
echo   4. 安装前端依赖（npm install）
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-env.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] 环境配置失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo   环境配置完成！
echo ========================================
echo   下一步：
echo   1. 编辑 backend\.env 填入实际密钥（V1.2 无 MYSQL/REDIS 配置）
echo   2. 构建打包：双击 scripts\构建打包.bat 生成 exe
echo ========================================
pause >nul
exit
