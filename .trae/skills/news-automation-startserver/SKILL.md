---
name: "news-automation-startserver"
description: "MorningBrief 项目服务生命周期自动化管理：启动/停止/前端构建/环境检查/状态查询，含环境预检查、日志记录、失败回滚。当用户要求'启动/开始/运行/起一下/打开/跑起来'MorningBrief服务，'停止/关闭/退出/停一下/关掉'服务，'构建/重新构建/编译/rebuild'前端，或提到'news-automation-startserver / MorningBrief 启动 停止 构建'时调用。仅管理 MorningBrief 项目自身服务生命周期；其他项目或系统级服务请用 RunCommand 直接操作。"
---

# MorningBrief 服务生命周期自动化管理

## 项目信息

- **项目名称**：MorningBrief 语音新闻播报系统
- **项目根目录**：`d:\code\otherProjects\MorningBrief`
- **架构**：Docker Compose 单机部署（4 容器：nginx / app / mysql / redis）
- **脚本目录**：`scripts\`
- **日志目录**：`logs\`

## 支持的操作

### 1. 启动服务
**触发词**：启动、开始、运行、起一下、打开、跑起来、start

**执行流程**：
1. 环境预检查（见下方"环境预检查"章节）
2. 执行启动脚本
3. 健康检查验证
4. 记录操作日志

**命令**：
```powershell
# 方式一：通过 bat 脚本（双击友好）
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"

# 方式二：带参数启动
# -Build  强制重新构建 Docker 镜像
# -Reset  重置数据（删除 data 目录）
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1" -Build
```

**工作目录**：`d:\code\otherProjects\MorningBrief`

**成功标志**：
- 4 个容器全部 `Up`（news_nginx / news_app / news_mysql / news_redis）
- 健康检查 `http://localhost/api/health` 返回 `code: 0`
- MySQL 和 Redis 状态为 `healthy`

**失败处理**：
- Docker Desktop 未运行 → 提示用户启动 Docker Desktop 后重试
- .env 文件缺失 → 提示用户先运行 `环境配置.bat`
- 端口冲突 → 提示检查 80/443/8000/3306/6379 端口占用
- MySQL 健康检查失败 → 检查 `data/mysql` 目录权限和磁盘空间

---

### 2. 停止服务
**触发词**：停止、关闭、退出、停一下、关掉、stop

**执行流程**：
1. 检查容器运行状态
2. 执行停止脚本
3. 验证端口已释放
4. 记录操作日志

**命令**：
```powershell
# 方式一：停止容器（可恢复，docker-compose start 可再启动）
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"

# 方式二：停止并删除容器（保留数据）
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1" -Clean
```

**工作目录**：`d:\code\otherProjects\MorningBrief`

**成功标志**：
- 4 个容器状态为 `Exited` 或不存在
- 端口 80/443/8000/3306/6379 已释放

**失败处理**：
- 容器无法停止 → 使用 `docker kill` 强制终止
- 端口未释放 → 提示检查残留进程

---

### 3. 前端构建
**触发词**：构建、重新构建、编译、rebuild、前端构建、build

**执行流程**：
1. 检查 Node.js 环境
2. 安装/更新前端依赖（增量）
3. 执行 vite build
4. 验证构建产物
5. 记录操作日志

**命令**：
```powershell
# 标准构建
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build-frontend.ps1"

# 跳过依赖安装（仅前端无变更时用）
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build-frontend.ps1" -SkipInstall
```

**工作目录**：`d:\code\otherProjects\MorningBrief`

**成功标志**：
- `admin-web\dist\index.html` 存在
- 无 ERROR 级别日志

**失败处理**：
- Node.js 未安装 → 提示安装 Node.js 18+
- Node 版本过低 → 提示升级到 18+（vite 5 要求）
- npm install 失败 → 删除 `node_modules` 后重试
- vite build 失败 → 检查 Vue 组件语法错误

**注意事项**：
- 构建产物 `admin-web\dist\` 由 nginx 容器挂载提供服务
- 构建后需重启 nginx 容器才能加载新产物：`docker-compose restart nginx`

---

### 4. 状态查询
**触发词**：状态、查看状态、运行状态、status

**命令**：
```powershell
# 查看容器状态
docker-compose --env-file .\backend\.env ps

# 查看健康检查
Invoke-RestMethod -Uri "http://localhost/api/health" -Method Get -TimeoutSec 5

# 查看端口占用
netstat -aon | findstr ":80 :443 :8000 :3306 :6379"
```

**工作目录**：`d:\code\otherProjects\MorningBrief`

**输出内容**：
- 4 个容器的运行状态（Up/Exited/重启次数）
- 健康检查结果（MySQL/Redis 连接状态）
- 端口监听情况
- 最近 10 行 app 容器日志（如容器在运行）

---

### 5. 环境检查
**触发词**：环境检查、检查环境、环境就绪、check

**检查项目**：
1. Docker Desktop 是否运行
2. .env 配置文件是否存在
3. 数据目录（data/mysql, data/redis, data/audio_cache）是否存在
4. admin-web/node_modules 是否存在（前端构建前置条件）
5. admin-web/dist 是否存在（前端产物）
6. 端口 80/8000 是否被占用

**命令**：
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup-env.ps1" -SkipSystem -SkipFrontend
```

---

## 环境预检查

**每次启动服务前必须执行以下检查**：

### 检查 1：Docker Desktop 运行状态
```powershell
docker info 2>&1
# 退出码 0 = 运行中
# 退出码非 0 = 未运行，需提示用户启动 Docker Desktop
```

### 检查 2：.env 配置文件
```powershell
Test-Path "backend\.env"
# 不存在时提示用户先运行 环境配置.bat
```

### 检查 3：端口占用
```powershell
# 检查 80 端口（nginx）
netstat -aon | findstr ":80 .*LISTENING"
# 检查 8000 端口（app）
netstat -aon | findstr ":8000 .*LISTENING"
# 如有占用，提示用户先停止现有服务或检查冲突进程
```

### 检查 4：数据目录
```powershell
# MySQL 数据目录（首次启动需存在）
Test-Path "data\mysql"
# Redis 数据目录
Test-Path "data\redis"
```

**预检查失败处理**：
- Docker 未运行 → 输出 `[SKIP] Docker Desktop 未运行，请先启动`，终止流程
- .env 缺失 → 输出 `[SKIP] backend\.env 不存在，请先运行 环境配置.bat`，终止流程
- 端口占用 → 输出 `[WARN] 端口 80/8000 已被占用`，询问用户是否先停止现有服务

---

## 日志记录

**每次操作记录到 `logs\automation.log`**，格式：
```
[2026-07-09 10:30:00] [START] 用户请求: 启动服务
[2026-07-09 10:30:00] [CHECK] Docker Desktop: OK
[2026-07-09 10:30:00] [CHECK] .env: OK
[2026-07-09 10:30:01] [EXEC] 执行: scripts\start.ps1
[2026-07-09 10:30:35] [DONE] 容器启动成功 (4/4)
[2026-07-09 10:30:36] [HEALTH] 健康检查通过
```

**日志写入方式**：
```powershell
# 在执行命令前后追加日志
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logLine = "[$timestamp] [START] 用户请求: 启动服务"
Add-Content -Path "logs\automation.log" -Value $logLine -Encoding UTF8
```

---

## 错误处理与回滚

### 启动失败回滚
1. 如果 MySQL/Redis 启动失败 → 停止 app 容器，输出 MySQL/Redis 日志
2. 如果 app 启动失败 → 停止 app 容器，输出 `docker-compose logs app` 最后 30 行
3. 如果 nginx 启动失败 → 检查 nginx.conf 语法，输出 nginx 容器日志

### 回滚命令
```powershell
# 停止所有容器（回滚）
docker-compose --env-file .\backend\.env down
```

### 错误提示规范
- `[ERROR]` 前缀：致命错误，流程终止
- `[WARN]` 前缀：警告，流程继续但需用户关注
- `[OK]` 前缀：步骤成功
- `[SKIP]` 前缀：跳过某步骤（条件不满足）

---

## 完整执行示例

### 示例 1：用户说"启动 MorningBrief 服务"

**AI 执行步骤**：
1. 切换到项目目录 `d:\code\otherProjects\MorningBrief`
2. 环境预检查：Docker Desktop → .env → 端口占用
3. 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"`
4. 等待执行完成（超时 120 秒）
5. 验证：`docker-compose ps` 查看容器状态
6. 健康检查：`Invoke-RestMethod http://localhost/api/health`
7. 向用户报告结果

### 示例 2：用户说"重新构建前端"

**AI 执行步骤**：
1. 切换到项目目录 `d:\code\otherProjects\MorningBrief`
2. 检查 Node.js 是否可用：`node --version`
3. 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build-frontend.ps1"`
4. 等待执行完成（超时 300 秒，npm install 可能较慢）
5. 验证：`Test-Path "admin-web\dist\index.html"`
6. 如服务正在运行，提示用户重启 nginx：`docker-compose restart nginx`
7. 向用户报告结果

### 示例 3：用户说"停止服务"

**AI 执行步骤**：
1. 切换到项目目录 `d:\code\otherProjects\MorningBrief`
2. 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"`
3. 等待执行完成（超时 30 秒）
4. 验证：`docker-compose ps` 确认容器已停止
5. 向用户报告结果

---

## 注意事项

1. **工作目录**：所有命令必须在 `d:\code\otherProjects\MorningBrief` 下执行，使用 RunCommand 的 `cwd` 参数指定
2. **PowerShell 语法**：PowerShell 不支持 `&&`，多命令用 `;` 分隔或分行
3. **编码**：bat 脚本使用 `chcp 65001` 确保 UTF-8 输出
4. **超时**：启动服务超时 120 秒，前端构建超时 300 秒，停止服务超时 30 秒
5. **仅管理 MorningBrief 项目**：本技能仅管理 MorningBrief 项目的服务生命周期，不适用于其他项目
6. **Docker Compose 命令**：必须带 `--env-file .\backend\.env` 参数，否则环境变量无法加载
