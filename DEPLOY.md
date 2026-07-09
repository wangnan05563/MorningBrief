# 20_News 生产部署文档

> 目标：单机 Linux 服务器，4 容器一键部署上线。

## 1. 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Linux（Ubuntu 22.04+ 推荐） |
| 容器运行时 | Docker 24.0+ + Docker Compose V2 |
| 网络 | 已备案域名 + HTTPS 证书（443 端口开放） |
| 外部服务账号 | 微信小程序（appid/secret）、通义千问 LLM、阿里云 TTS、腾讯云 COS |
| 服务器配置建议 | 4 核 / 8G / 100G 盘，可外网访问 |

## 2. 部署步骤

### 2.1 准备配置文件

```bash
cp backend/.env.example backend/.env
vi backend/.env
```

按下表分组填写真实值（**所有 `<请替换...>` 占位符必须替换**）：

**应用配置**

| 变量 | 说明 |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `APP_TIMEZONE` | `Asia/Shanghai` |

**MySQL**

| 变量 | 说明 |
| --- | --- |
| `MYSQL_HOST` | `mysql`（容器内网络名，勿改） |
| `MYSQL_PORT` | `3306` |
| `MYSQL_DATABASE` | `news_db` |
| `MYSQL_USER` | 业务账号，如 `news_app` |
| `MYSQL_PASSWORD` | 强密码 |
| `MYSQL_ROOT_PASSWORD` | 强密码 |

**Redis**

| 变量 | 说明 |
| --- | --- |
| `REDIS_HOST` | `redis`（容器内网络名，勿改） |
| `REDIS_PORT` | `6379` |
| `REDIS_PASSWORD` | 可选，建议生产设置 |

**JWT**

| 变量 | 说明 |
| --- | --- |
| `JWT_SECRET` | 32+ 位随机串，`openssl rand -hex 32` 生成 |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRE_DAYS` | C 端 token 有效期（天），默认 7 |
| `JWT_ADMIN_EXPIRE_HOURS` | B 端 token 有效期（小时），默认 2 |

**微信小程序**

| 变量 | 说明 |
| --- | --- |
| `WX_APPID` | 小程序 appid |
| `WX_SECRET` | 小程序 secret |

**LLM（通义千问）**

| 变量 | 说明 |
| --- | --- |
| `LLM_API_KEY` | DashScope API Key |
| `LLM_MODEL` | `qwen-max` |
| `LLM_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

**TTS（阿里云）**

| 变量 | 说明 |
| --- | --- |
| `ALIYUN_TTS_API_KEY` | 阿里云 TTS API Key |
| `ALIYUN_TTS_VOICE` | 默认音色，如 `xiaoyun` |
| `ALIYUN_TTS_SAMPLE_RATE` | `44100` |
| `ALIYUN_TTS_FORMAT` | `mp3` |

**COS（腾讯云对象存储）**

| 变量 | 说明 |
| --- | --- |
| `COS_SECRET_ID` | 腾讯云 SecretId |
| `COS_SECRET_KEY` | 腾讯云 SecretKey |
| `COS_BUCKET` | Bucket 名 |
| `COS_REGION` | 地域，如 `ap-guangzhou` |
| `COS_CDN_DOMAIN` | CDN 加速域名，如 `https://cdn.example.com` |

**告警（可选）**

| 变量 | 说明 |
| --- | --- |
| `ALERT_WECOM_WEBHOOK` | 企业微信机器人 webhook，用于审核通知 + 工作流告警 |

**工作流调度**

| 变量 | 说明 |
| --- | --- |
| `CRAWLER_DEDUP_TTL_DAYS` | 去重保留天数，默认 7 |
| `CRAWLER_USER_AGENT` | 爬虫 UA，默认 `20NewsBot/1.0` |
| `CRAWLER_QPS_DEFAULT` | 爬虫默认 QPS，默认 1 |

### 2.2 构建前端

```bash
cd admin-web
npm install --registry=https://registry.npmmirror.com
npm run build
# 产物在 dist/，由 nginx 容器挂载
cd ..
```

确认 `docker-compose.yml` 中 nginx 服务下 `./admin-web/dist:/usr/share/nginx/html/admin:ro` 挂载行已启用（默认已启用，无需改动）。

### 2.3 启动服务

```bash
docker compose up -d
```

容器启动顺序（由 `depends_on.healthcheck` 保障）：

```
mysql  →  redis  →  app  →  nginx
```

MySQL/Redis 健康检查通过后，`app` 才会启动；`app` 健康检查通过后，nginx 才会接收流量。

### 2.4 验证部署

```bash
# 健康检查
curl http://localhost/api/health

# 后台前端
# 浏览器访问 http://<域名>/admin/

# API 文档（仅 APP_ENV=development 时暴露）
curl http://localhost/docs
```

## 3. Nginx SSL 配置

1. 证书放置：将 `fullchain.pem` 和 `privkey.pem` 放入 `nginx/ssl/` 目录。
2. 取消 `docker-compose.yml` 中 nginx 服务下 ssl 挂载注释：

   ```yaml
   volumes:
     - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
     - ./nginx/ssl:/etc/nginx/ssl:ro   # 取消该行注释
     - ./admin-web/dist:/usr/share/nginx/html/admin:ro
   ```

3. 修改 `nginx/nginx.conf` 中 `server_name` 为真实域名（默认 `api.example.com`）。
4. HTTPS 配置（443）与 80→443 跳转已在 `nginx.conf` 中预置，重载即可：

   ```bash
   docker compose restart nginx
   ```

## 4. 微信小程序发布

1. 用「微信开发者工具」打开 `miniprogram/` 目录。
2. 修改 `miniprogram/project.config.json` 中 `appid` 为真实小程序 appid（默认占位 `wx0000000000000000`）。
3. 修改 `miniprogram/services/api.js` 中生产环境 `BASE_URL` 为真实域名：

   ```js
   const BASE_URL = (typeof __wxConfig !== 'undefined' && __wxConfig.envVersion === 'release')
     ? 'https://<你的域名>/api/v1'   // 替换为生产域名
     : 'http://localhost:8000/api/v1';
   ```

4. 在小程序后台「开发管理 → 服务器域名」配置 `request` 合法域名为 `https://<你的域名>`。
5. 上传代码 → 提交审核 → 发布。

## 5. 运维操作

```bash
# 查看 app 日志（实时）
docker compose logs -f app

# 重启应用容器
docker compose restart app

# 更新代码（拉新 + 重建 app）
git pull
docker compose up -d --build app

# 备份 MySQL（导出到宿主机）
docker exec news_mysql mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" news_db > backup_$(date +%F).sql

# 查看今日工作流状态
curl http://localhost/admin/api/v1/workflows/today
```

## 6. 监控告警

- **工作流告警**：工作流步骤失败时自动通过 `ALERT_WECOM_WEBHOOK` 推送企业微信。
- **健康检查**：`/api/health` 接口，可接入外部探活。
- **慢查询**：MySQL 慢查询日志位于容器内 `/var/lib/mysql/` 目录，由 `mysql/my.cnf` 控制开启。

## 7. 故障排查

| 现象 | 排查方向 |
| --- | --- |
| `app` 容器启动失败 | 检查 `backend/.env` 是否有未替换占位符；检查 MySQL/Redis 连通性：`docker exec news_app python -c "import redis, pymysql; ..."` |
| 工作流卡住 | 查 `workflow_step` 表当前状态；检查 LLM/TTS API 配额是否耗尽；查 `logs/` 下工作流日志 |
| 小程序登录失败 | 确认 `WX_APPID/WX_SECRET` 正确；检查服务器到微信 `api.weixin.qq.com` 网络；确认小程序后台已配置 request 合法域名 |
| 前端 404 | 确认 `admin-web/dist/` 存在且已构建；确认 nginx 挂载未注释 |
| 502 Bad Gateway | `app` 容器未就绪或崩溃，`docker compose ps` 查状态，`docker compose logs app` 查错误 |
