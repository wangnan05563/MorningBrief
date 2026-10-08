# MorningBrief

> AI 起草 · 双人播报 · 每天早上听见世界

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white)
![TTS](https://img.shields.io/badge/TTS-5%20%E5%BC%95%E6%93%8E-3F6C8F)

![MorningBrief](docs/github-social-preview.png)

一个把「新闻资讯 / 专业资料」自动转成**可订阅语音节目**的完整内容生产系统：
抓取 → AI 改写 → 语音合成 → 拼接混音 → 人工审核 → 定时发布，全链路内置，
并以单 exe 形式交付，单机零运维运行。

## 特性

- **全流程内容工作流**：爬虫抓取 → LLM 改写 → TTS 合成 → ffmpeg 拼接/BGM → 人工审核 → 发布，各阶段状态可追踪、可重跑。
- **5 个 TTS 引擎可插拔**：阿里云 NLS / 腾讯云 / Edge-TTS（免费）/ Kokoro / Piper（本地离线），统一 Provider 抽象，随时切换。
- **交叉音色**：稿件分段轮流换声（轮流/随机/间隔策略），避免单一音色同质化；音色列表支持一键从官方接口同步。
- **跨端交付**：Vue 3 管理后台（Element Plus）+ 微信小程序（收听/订阅/下载/课程学习）+ 云函数。
- **单机零运维**：SQLite（WAL）+ TTLCache 进程内缓存替代 MySQL/Redis，全局写序列化，单 worker 即可稳定运行。
- **合规与安全**：内容分级提示（disclaimer）、敏感词内容安全、管理员审计日志、小程序隐私授权（`__usePrivacyCheck__`）。
- **工程化**：pytest 全量回归（620+ 用例）、小程序 `node:test` 单测、JMeter 压测脚本、SonarQube 接入。

## 架构

```
┌────────────────────────────┐
│  内容工作流（backend/app/workflow）   │
│  crawler → rewrite → tts → stitch │
│           → review → publish      │
└─────────────┬──────────────┘
              │
┌─────────────▼──────────────┐        ┌─────────────────────┐
│  FastAPI (app.main:app)    │        │  apps/admin-web     │
│  ├ /api/v1        C 端 API  │◄──────►│  Vue 3 管理后台      │
│  ├ /admin/api/v1  B 端 API  │        │  (Element Plus)     │
│  ├ /api/internal 工作流触发  │        └─────────────────────┘
│  └ /api/health    健康检查   │        ┌─────────────────────┐
│                            │◄──────►│  apps/miniprogram   │
│  SQLite(WAL) + TTLCache    │        │  微信小程序           │
└────────────────────────────┘        └─────────────────────┘
```

## 安装

### 后端（Python 3.12）

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt
# 可选：额外 TTS 引擎依赖（Kokoro / Piper 本地引擎）
pip install -r requirements-tts-extra.txt
```

### 管理后台（Node.js）

```bash
cd apps/admin-web
npm install
npm run dev        # 开发模式，Vite 本地服务
npm run build      # 生产构建，base=/news/
```

### 微信小程序

用微信开发者工具导入 `apps/miniprogram/` 目录即可（基础库 3.3.4）。
图标源稿在 `apps/miniprogram/images/svg-src/`，改 SVG 后运行：

```bash
cd apps/miniprogram/images/svg-src && npm install && node convert-icons.js
```

## 快速开始

```bash
# 1. 配置环境变量（数据库、TTS、LLM 等均有注释说明）
cp backend/.env.example backend/.env

# 2. 创建管理员账号
cd backend && .venv\Scripts\python seed_admin.py

# 3. 启动后端（默认单 worker；写锁/缓存为进程内状态，多 worker 需按角色拆分，见 backend/launcher.py）
.venv\Scripts\python -m uvicorn app.main:app --workers 1
# 需要多进程扛读量时改用 launcher（自动编排 1 个 sched + N 个 api，.env 设 UVICORN_WORKERS=2）
.venv\Scripts\python launcher.py

# 4. 打开管理后台
cd apps/admin-web && npm run dev
```

或直接使用仓库脚本：`scripts/start.ps1`（启动）/ `scripts/stop.ps1`（停止）。

## 配置

所有配置集中在 `backend/.env`（见 `.env.example` 内注释），启动时由
`ai_config` 表覆盖 `Settings` 单例，管理后台修改后**热更新**、无需重启：

| 分组 | 关键项 |
| --- | --- |
| 数据库 | `SQLITE_DB_PATH`、`SQLITE_JOURNAL_MODE=WAL`、`SQLITE_BUSY_TIMEOUT_MS` |
| LLM | `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`（OpenAI 兼容协议） |
| TTS | `TTS_PROVIDER`（aliyun/edge/tencent/kokoro/piper）+ 各引擎凭证 |
| 交叉音色 | `BGM_GAP_MODE`（continuous/silence/bridge）、`SEGMENT_CROSSFADE_SEC` |
| 云存储 | `COS_SECRET_ID/KEY/BUCKET`（可选，启用后小程序头像直传 COS） |

> 注意：`.env` 中「仅作说明的空值项」注释必须独立成行，不要写 `KEY= # 注释`
> （pydantic-settings 未开启行内注释剥离，会把注释文本当成值）。

## API

统一前缀与响应格式 `{ code, message, data }`：

| 前缀 | 用途 |
| --- | --- |
| `/api/v1/*` | C 端（小程序）：频道/节目/播放/收藏/队列/评论/下载 |
| `/admin/api/v1/*` | B 端（管理后台）：内容工作流、频道、AI 服务配置、审核、统计、云端存储 |
| `/api/internal/workflow` | 工作流内部触发 |
| `/api/health` | 健康检查 |

## 部署

支持打包为**单 exe**（内嵌 SQLite + 管理后台静态资源），单机零运维：

```powershell
scripts/build-frontend.ps1   # 构建管理后台 SPA
scripts/build-exe.ps1        # PyInstaller 打包 + Inno Setup 安装包
```

产物位于 `release/dist/`；安装器由 `installer.iss` 生成。

## 测试

```bash
# 后端全量回归（620+ 用例）
cd backend && .venv\Scripts\python -m pytest tests/ -q

# 小程序工具层单测
cd apps/miniprogram && node --test "tests/*.test.js"

# 性能压测（JMeter 5.6.3）
scripts/jmeter_test/

# 压测回归门禁：一条命令串起 清理→建用户/token→seed→固定档位压测→analyze→cleanup
# 退出码 0=达标 / 1=有档位破线（回归）/ 2=前置条件或工具链失败
cd scripts/jmeter_test && python perf_gate.py --tier quick      # ~4 分钟 3 档
python perf_gate.py --tier standard                             # 默认档（含管理端，需 GATE_ADMIN_TOKEN）
python perf_gate.py --tier full --update-baseline               # 全档位并重写延迟基线 gate_baseline.json
```

## 目录结构

```
├── apps/                 # 前端：admin-web / miniprogram / scf 云函数
├── backend/              # FastAPI 服务（app/ + tests/ + data/ + ffmpeg/）
│   └── app/workflow/     #   内容生产流水线（含 tts/ 五引擎、stitch/ 拼接）
├── docs/                 # 文档与设计源稿（assets-src/ 为社交预览图源文件）
├── release/              # 构建产物（dist / assets）
├── runtime/              # 运行时：内网穿透二进制、日志
├── scripts/              # 构建 / 启停 / 压测脚本
└── installer.iss         # Inno Setup 安装包脚本
```

## 致谢

- [edge-tts](https://github.com/rany2/edge-tts) —— 免费 Edge/Azure 神经网络语音
- [Tabler Icons](https://tabler.io/icons)（MIT）—— 全站图标
- [Element Plus](https://element-plus.org/)、[resvg-js](https://github.com/thx/resvg-js)
