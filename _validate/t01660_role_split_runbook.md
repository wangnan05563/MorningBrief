# T01660 进程角色拆分 runbook（路线 A 前置）

## 1. 角色语义

| `APP_ROLE` | 建表/迁移/seed | 模板 seed | APScheduler | 启动补跑清理 | 隧道 auto_start + 通知 | 写缓冲 flush | EventBus | HTTP |
|---|---|---|---|---|---|---|---|---|
| `all`（默认，未设置时） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `sched` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 仅内部端口 |
| `api` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |

写缓冲与 EventBus 在三种角色下**都必须启动**：`PlayWriteBuffer._buf` 是进程内 list、
`EventBus._queue` 是进程内 `asyncio.Queue`，队列内容由本进程自己产生。门掉消费者的后果是
本进程缓冲的进度写永不落库、发布的事件永不分发（实测证据见 §4）。

## 2. 启动方式

- 默认（行为与改造前完全一致）：`python launcher.py` 或 `uvicorn app.main:app --workers 1`。
- 多进程：`.env` 里 `UVICORN_WORKERS=2`（或环境变量注入）后 `python launcher.py`
  → launcher 自动编排「1 个 sched + N 个 api」：
  - sched 进程端口 = `SCHED_PORT`（默认业务端口 +1），只绑 `127.0.0.1`，不对外服务；
  - launcher 轮询 `http://127.0.0.1:<SCHED_PORT>/api/health` 作为「建表/迁移已完成」的就绪探针，
    就绪后才起 api（避免 api 跳过 DDL 时打到不存在的表）；
  - 就绪超时（`SCHED_READY_TIMEOUT_SEC`，默认 120s）则回退为单进程 `all` 启动，保证服务可用优先；
  - 退出时按进程树回收（Windows 用 `taskkill /F /T`，`terminate()` 只杀父进程会残留 worker）。
- 手工分进程（不走 launcher）必须自己保证 sched 先起并完成迁移。
- 递归保护：角色由编排注入（env 里已有 `APP_ROLE=api|sched`）时，子进程不再二次拆分；
  `sched` 角色强制 `workers=1`（否则又变回重复调度）。

## 3. 观测口径（验收「重复副作用是否收敛」）

对合并日志计数（sched+2 api 实测见 §4）：

```bash
grep -c "进程角色=sched" run.log        # 期望 1
grep -c "进程角色=api"   run.log        # 期望 = workers 数
grep -c "Added job"      run.log        # 期望 10（全部来自 sched 同一时刻）
grep -c "WorkflowScheduler 已启动" run.log   # 期望 1
grep -c "内网穿透隧道已自动启动" run.log       # 期望 ≤1（auto_start=false 时为 0）
grep -c "周期 flush 已启动" run.log     # 期望 = 进程数（含 sched）
grep -c "EventBus 已启动" run.log       # 期望 = 进程数（含 sched）
```

## 4. 隔离实例复现步骤（不触碰真实 data/.env/隧道）

`paths.get_app_root()` 在开发态取 `app/` 的上两级，所以整份 backend 复制到临时目录即可完全隔离
（隧道配置、数据库、日志都落在副本里）。

```bash
ISO=$TEMP/t01660_iso/backend               # 复制 app/ + launcher.py + data/news.db + .env
# 副本内 data/tunnel_config.json 把 auto_start 置 false —— 否则会真的建 Funnel 并发通知
# 副本库中和频道排程，避免 05:00/06:00/每2小时等 cron 在验证窗口触发真实 LLM/TTS：
#   update channel set is_active=0, schedule_time=null;
cd "$ISO"
APP_PORT=8300 SCHED_PORT=8301 UVICORN_WORKERS=2 \
RATE_LIMIT_PER_MINUTE=100000 WORKFLOW_CRON_HOUR=23 WORKFLOW_BACKUP_CHECK_HOUR=22 \
python launcher.py > run_split_w2.log 2>&1 &
python <repo>/_validate/t01660_role_probe.py --label split_w2 --port 8300 \
       --reads 300 --writes 100 --workers 16 --log run_split_w2.log --out <repo>/_validate/t01660_ab.json
```

`RATE_LIMIT_PER_MINUTE` 调高是为了把「每进程独立限流」从 A/B 对照里剔除（见 §5 残留限制）；
探针自己会往副本库插一个 `t01660_probe_*` 用户并写进度，真实用户不受触碰。

## 5. 残留限制（角色拆分解决不了的，只能靠共享态）

- 进程内 TTLCache 每进程一份：A 进程的写失效不会清 B 进程的缓存，读可能读到陈旧副本；
- 全局写锁每进程一份：跨进程写并发由 SQLite 的 WAL + `busy_timeout` 兜底，
  不再是被单进程串行化的「同一把锁」；
- 限流计数每进程一份：`workers=N` 时实际放行 ≈ `N × RATE_LIMIT_PER_MINUTE`
  （实测 workers=2 单分钟放行 240=2×120）。

上述三条已在 `backend/app/config.py` 与 `docs/详细设计说明书.md` 9.2 写明。
