# 20_News 单机部署一键启动脚本
# 适用：Windows 10 + PowerShell + Docker Desktop
# 用法：.\scripts\start.ps1
# 注意：PowerShell 不支持 && 串联，使用 ; 或分行

param(
    [switch]$Build,        # 强制重新构建镜像
    [switch]$Reset         # 重置数据（删除 data 目录）
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  20_News 单机部署启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 检查 Docker Desktop 是否运行
Write-Host "`n[1/6] 检查 Docker Desktop..." -ForegroundColor Yellow
$dockerStatus = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop 未运行，正在启动..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "等待 Docker Desktop 启动完成（60秒）..." -ForegroundColor Yellow
    Start-Sleep -Seconds 60
    docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker Desktop 启动失败，请手动启动后重试" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Docker Desktop 运行正常" -ForegroundColor Green

# 2. 检查 .env 文件
Write-Host "`n[2/6] 检查 .env 配置..." -ForegroundColor Yellow
if (-not (Test-Path .\backend\.env)) {
    if (Test-Path .\backend\.env.example) {
        Write-Host ".env 不存在，从 .env.example 复制..." -ForegroundColor Yellow
        Copy-Item .\backend\.env.example .\backend\.env
        Write-Host "WARNING: 请编辑 .env 填入实际配置后重新运行此脚本" -ForegroundColor Red
        Write-Host "  notepad backend\.env" -ForegroundColor Gray
        exit 1
    } else {
        Write-Host "ERROR: .env 与 .env.example 均不存在" -ForegroundColor Red
        exit 1
    }
}
Write-Host ".env 配置存在" -ForegroundColor Green

# 3. 可选：重置数据
if ($Reset) {
    Write-Host "`n[3/6] 重置数据（删除 data 目录）..." -ForegroundColor Yellow
    docker-compose --env-file .\backend\.env down -v
    Remove-Item -Recurse -Force data -ErrorAction SilentlyContinue
    Write-Host "数据已重置" -ForegroundColor Green
} else {
    Write-Host "`n[3/6] 保留现有数据" -ForegroundColor Green
}

# 4. 构建镜像（可选）
if ($Build) {
    Write-Host "`n[4/6] 重新构建镜像..." -ForegroundColor Yellow
    docker-compose --env-file .\backend\.env build --no-cache app
    Write-Host "镜像构建完成" -ForegroundColor Green
} else {
    Write-Host "`n[4/6] 跳过镜像构建" -ForegroundColor Green
}

# 5. 启动容器（按依赖顺序）
Write-Host "`n[5/6] 启动容器..." -ForegroundColor Yellow

# 先启动数据库，等待健康检查
docker-compose --env-file .\backend\.env up -d mysql redis
Write-Host "等待 MySQL/Redis 健康检查（30秒）..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# 启动应用
docker-compose --env-file .\backend\.env up -d app
Write-Host "等待 FastAPI 应用启动（20秒）..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# 启动 Nginx
docker-compose --env-file .\backend\.env up -d nginx

Write-Host "所有容器已启动" -ForegroundColor Green

# 6. 健康检查
Write-Host "`n[6/6] 健康检查..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost/api/health" -Method Get -TimeoutSec 10
    if ($response.code -eq 0) {
        Write-Host "健康检查通过" -ForegroundColor Green
        Write-Host "  MySQL: $($response.data.mysql)" -ForegroundColor Gray
        Write-Host "  Redis: $($response.data.redis)" -ForegroundColor Gray
    } else {
        Write-Host "WARNING: 健康检查返回非 0 状态" -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARNING: 健康检查失败，应用可能仍在启动中" -ForegroundColor Yellow
    Write-Host "  手动检查：curl http://localhost:8000/api/health" -ForegroundColor Gray
}

# 容器状态
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  部署完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n容器状态：" -ForegroundColor Yellow
docker-compose --env-file .\backend\.env ps

Write-Host "`n访问地址：" -ForegroundColor Yellow
Write-Host "  API:        http://localhost/api/v1/" -ForegroundColor Gray
Write-Host "  运营后台:   http://localhost/admin/" -ForegroundColor Gray
Write-Host "  健康检查:   http://localhost/api/health" -ForegroundColor Gray

Write-Host "`n日志查看：" -ForegroundColor Yellow
Write-Host "  docker-compose logs -f app" -ForegroundColor Gray
Write-Host "  docker-compose logs -f nginx" -ForegroundColor Gray
