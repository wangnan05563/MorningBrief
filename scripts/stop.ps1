# 20_News 停止脚本
# 用法：.\scripts\stop.ps1         停止容器（可恢复）
#       .\scripts\stop.ps1 -Clean  停止并删除容器（保留数据）

param(
    [switch]$Clean  # 同时删除容器（保留数据）
)

Write-Host "停止 20_News 容器..." -ForegroundColor Yellow
if ($Clean) {
    docker-compose --env-file .\backend\.env down
    Write-Host "容器已停止并删除（数据保留在 ./data 目录）" -ForegroundColor Green
} else {
    docker-compose --env-file .\backend\.env stop
    Write-Host "容器已停止（docker-compose start 可恢复）" -ForegroundColor Green
}
