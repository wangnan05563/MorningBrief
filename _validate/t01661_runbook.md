# T01661 写路径每请求归因 · 空闲机复跑手册（runbook）

> 交付物清单
> - 临时探针补丁：`_validate/t01661_probe.patch`（`git apply --check` 已验证可干净应用；**禁止合入 main**）
> - 驱动与解析：`_validate/t01661_comment_probe.py`（复用 `_validate/t01660_role_probe.py` 的
>   副本 token 签发 / 探针用户 / HTTP 计时）
> - 本手册 + 结果口径模板（见 §5）
> - 忙机结构性预跑数据：`_validate/t01661_probe_data.json`（绝对值不可引用，只用于校准口径）

## 0. 前置条件（不满足就停手，别出数）

| 条件 | 判据 | 采样命令 |
|---|---|---|
| 专用空闲执行机（T01623 同机） | **system CPU < 15%** | `typeperf '\Processor(_Total)\% Processor Time' -sc 8` |
| 无实时防护全盘扫描 | MsMpEng CPU 累计 < 1% | `Get-Process MsMpEng | Select CPU` |
| 无 IDE/遥测干扰 | 关闭 Qoder IDE、CompatTelRunner 暂停 | 任务管理器 |
| 复跑前记录采样值 | 把上面三个数值写进结果表头 | — |

本机（开发机）2026-10-09 07:33 实测 **CPU 60–70%**（`_validate/t01661_cpu_before.txt` /
`_validate/t01661_cpu_after.txt`），**不满足前置** → 正式复跑必须在空闲机执行；
本手册的 §4 数据只是「口径是否跑得通」的自检，不得当作结论绝对值。

## 1. 建隔离副本（不动真实 data/，不触发隧道与通知）

```bash
ISO="$TEMP/t01661_iso/backend"; rm -rf "$TEMP/t01661_iso"; mkdir -p "$ISO/data"
cd backend
cp -r app "$ISO/" && cp launcher.py pytest.ini .env "$ISO/"
cp data/news.db "$ISO/data/"          # 只带库，不带 audio_cache/backup/tunnel_config.json
find "$ISO/app" -name __pycache__ -type d -prune -exec rm -rf {} +
```

关键点：
- **不复制 `data/tunnel_config.json`** → 代码默认 `auto_start=False`，绝不会再建一条 Funnel
  并发用户可见通知（T01659 踩过，perf_gate 的同类缺陷已建 T01692）。
- 中和副本库里的定时频道，避免验证窗口触发真实 LLM/TTS 花费：
  ```sql
  update channel set is_active=0, schedule_time=NULL;
  ```
- 环境变量注入，**不改 `.env`**：
  `RATE_LIMIT_PER_MINUTE=100000`（剔除限流变量）、`WORKFLOW_CRON_HOUR=23`、
  `WORKFLOW_BACKUP_CHECK_HOUR=22`、`APP_ROLE=all`。

## 2. 应用临时探针补丁

```bash
cd <repo> && git apply _validate/t01661_probe.patch && cd <repo>/backend
cp -r app "$ISO/"          # 补丁随 app 目录一起进副本；副本被改，main 不受影响
```

补丁做 5 处改动（全部只加计时，不改业务行为）：

| 文件 | 改动 |
|---|---|
| `app/core/_t01661_probe.py`（新增） | ContextVar 分段计时 + 建连 PRAGMA 全局累加 + loguru sink 自耗时 |
| `app/core/auth.py:get_current_user` | `begin()` + `token_extract`/`jwt_decode`/`blacklist` 三段 |
| `app/database.py:_set_sqlite_pragma` | 每条新建连接的 4 条 PRAGMA 耗时累加（`conn_new`/`conn_pragma`） |
| `app/core/write_gate.py` | 新增 `write_lock_probed()`：拆 `lock_wait`（等锁）与 `lock_hold`（持锁提交） |
| `app/routers/api/comments.py:create_comment` | `profile_query`/`episode_check`/`commit` 标记 + 结尾 `flush()` |

换其它写接口做归因时，照 `comments.py` 的四行模式接入即可（`begin` 已在 `get_current_user`）。

## 3. 起实例并跑探针

```bash
cd "$ISO"
APP_ROLE=all RATE_LIMIT_PER_MINUTE=100000 WORKFLOW_CRON_HOUR=23 \
WORKFLOW_BACKUP_CHECK_HOUR=22 LOG_LEVEL=INFO \
<repo>/backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8411 \
  > t01661_server.log 2>&1 &
# 冷启动 ≈70s（含建表/迁移），就绪判据：curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8411/api/v1/channels

cd <repo>
backend/.venv/Scripts/python.exe _validate/t01661_comment_probe.py \
    --port 8411 --iso-root "<ISO 的 Windows 路径>" --seq 30 --burst 50 \
    --out _validate/t01661_probe_data.json
```

⚠ 探针行落在 **loguru 文件 sink**：`<ISO>/logs/MorningBrief_<date>.log`（脚本默认已按此解析）；
`t01661_server.log`（stdout 重定向）里没有 `[T01661PROBE]`，别按它解析（我踩过一次，白跑一轮）。

跑完回滚（硬约束：临时探针不得进 main）：

```bash
git checkout -- backend/app/core/auth.py backend/app/core/write_gate.py \
                backend/app/database.py backend/app/routers/api/comments.py
rm -f backend/app/core/_t01661_probe.py
git status --short          # 确认工作区只剩本单 _validate 交付物
```

## 4. 本机忙机预跑数据（口径自检，CPU 60–70%，绝对值不可引用）

`POST /api/v1/comments`，n=14 顺序（间隔 300ms）+ n=24 并发（8 线程）：

| 段 | 顺序写中位 ms（占比） | 并发写中位 ms（占比） |
|---|---|---|
| 服务端 total | 201.4（100%） | 692.9（100%） |
| token_extract / jwt_decode / blacklist | 0.0 / 0.1 / 0.0 | 0.0 / 0.1 / 0.0 |
| profile_query | 62.2（31%） | 23.7（3%） |
| episode_check | 32.4（16%） | 20.2（3%） |
| lock_wait（等锁） | **0.1（0%）** | **252.9（36%）** |
| lock_hold（持锁提交+refresh） | 63.6（32%） | 22.6（3%） |
| └ commit | 38.0 | 20.2 |
| conn_new / conn_pragma | 0 条 / 0.0ms | 0 条 / 0.0ms |
| sink_prev（单条日志写盘） | 3.0（2%） | 0.9（0%） |
| 客户端往返 | 229.5 | 748.3 |

另一轮并发样本：`lock_wait=619ms（48%）`、客户端往返 1322ms → 并发段随机器负载强波动，
空闲机复跑需给出多轮中位数与离散度，不能只报一轮。

### 对 T01661 三条待验证假设的判定

1. **`Depends(get_db)` 每请求新建连接触发 PRAGMA** → **已被 T01662 消除**：
   连接池开启后 `conn_new=0`、`conn_pragma=0.0ms`（NullPool 时代该项 ≈41ms/请求）。
   空闲机复跑只需确认 `SQLITE_POOL_ENABLED=true` 下仍为 0，
   并用 `SQLITE_POOL_ENABLED=false` 做一轮对照（T01659 的 R3 口径）。
2. **loguru 同步文件 sink 在 Defender 实时防护下写盘放大** → **不是主因，但不可忽略**：
   单条 INFO ≈0.9–3.2ms，一个写请求路径约 6–10 条 → 折算 5–30ms/请求（忙机 total 的 3–15%）。
   空闲机请按「每请求日志条数 × 单条 sink 成本」复核（单条成本另有
   `_validate/t01659_log_sink_cost.py` 可跑）。
3. **全局写锁在无并发场景的 await 开销** → **假设不成立**：无并发时 `lock_wait=0.1ms`。
   真正的代价在**争用排队**：并发下 `lock_wait` 升为第一大段（36–48%）。
   归因方向应从「锁本身开销」改为「持锁段长度 × 并发数」。

### 与 T01617「约 75% 每请求耗时无法解释」的收敛

本次分段把可解释比例提到 ≈79%（profile_query + episode_check + lock_hold 三项就覆盖
201ms 中的 ~158ms），剩余 ~40ms 落在 FastAPI 依赖注入 / 响应序列化 / 中间件。
空闲机进一步夹逼：`--seq 30` 之外补一组「只读同路径 + 空 POST（校验失败即返回）」基线，
用差值分离框架开销与 SQL 开销。

## 5. 结果口径模板（复跑后按此回填，用于回填 T01659 取舍阈值）

```
机器：____（T01623 同机？）   采样时刻：____
前置 CPU：<__% （必须 <15%，否则本轮作废）  MsMpEng CPU：__%  IDE 是否关闭：__
代码版本：commit ____   SQLITE_POOL_ENABLED=true|false   APP_ROLE=all   worker=1
样本：顺序 n=__（间隔 __ms） / 并发 n=__（线程 __）   接口：POST /api/v1/comments

| 段 | 顺序中位ms | 顺序占比 | 并发中位ms | 并发占比 | 离散度(p95/p50) |
| --- | --- | --- | --- | --- | --- |
| total | | | | | |
| profile_query | | | | | |
| episode_check | | | | | |
| lock_wait | | | | | |
| lock_hold / commit | | | | | |
| conn_new(条)/conn_pragma | | | | | |
| sink_prev × 日志条数 | | | | | |
| 未归因残差 | | | | | |

结论阈值判定（回填 T01659）：
- lock_hold 占 total > 25%  → 把 db.refresh 移出写锁，锁内只留 commit（建议建单）
- lock_wait 占 total > 30%  → 全局串行写锁是并发写第一瓶颈，需评估「按表/按行分锁」或队列化提交
- profile_query+episode_check > 30% → 合并为一条 SQL 或走只读缓存
- sink 折算 > 10% → 降日志级别 / 异步 sink
```

## 6. 基线必须重标定（携带 T01659 的对照结论）

- T01659 同机不同日复跑 R1(02:18)/R2(02:27)：S0 P95 **752→1115ms**、TPS **75.8→47.2**，
  离散 ±48%/38% —— **大于门禁阈值本身**，说明「机器状态」是首要变量，任何跨日绝对值比较都无意义。
- R3（`SQLITE_POOL_ENABLED=false` 对照）证明连接池收益方向明确，但该轮跑在忙机上，
  绝对值同样不可引用。
- **T01662 连接池 + T01660 角色编排已改变每请求路径构成**（建连成本归零、多进程限流 N×），
  T01623 标定的门禁基线**已失效**，空闲机复跑时必须同时重录 S0/S1/S2 基线，
  并把「pool on/off」「role 编排」「worker 数」写进基线元数据（perf_gate 侧改造见 **T01692**）。

## 7. 残留限制

- 本探针只覆盖 `POST /api/v1/comments` 一条写路径；`playlogs/progress`（走写缓冲）与
  `favorites`（走 `serialized_write`）需要按 §2 的四行模式各接一次。
- `sink_prev` 滞后一条（无法自测本次 log 调用），只看量级。
- 未归因残差仍含 ASGI/中间件与 httpx 之外的客户端开销；框架级拆细需要更深的插桩，
  本轮不做（避免探针复杂度过高反而放大被测成本）。
