# 压测批次对生产数据库的影响取证（2026-11-03 批次 / 2026-10-31 批次）

> 结论先说：**两个批次都没有向生产库写入任何一行数据**；生产库文件的时间戳确实落在批次窗口内，
> 但与本地并发开发（T04111）相关，不是压测流量。以下逐项给证据。

## 1. 数据层：生产库零写入（决定性证据）

取证方式：只读连接 `sqlite3.connect("file:backend/data/news.db?mode=ro", uri=True)`，未取写锁。

| 检查项 | 生产库 `backend/data/news.db` | 沙箱库 `sandbox/backend/data/news.db` |
|---|---|---|
| `user` 行数 | 20（**无 950020**，压测 C 端夹具账号不存在） | 21（含 950020） |
| `admin_user` | 1 行：`id=1, admin, 2026-07-12`（**无 `perf_admin`**） | 2 行（含 `perf_admin`） |
| `comment` | 3 | 51 031（压测写入全在这里） |
| `feedback` | 0 | 1 972 |
| `favorite` / `play_log` / `audit_log` | 106 / 8 / 68 | 106 / 8 / 68（写入靠 upsert 与唯一索引，量级未变） |
| 任一表 `*_at` 落在 **2026-10-31** 或 **2026-11-03** | **0 行** | 数万行 |
| 全库最新业务时间戳 | `jwt_blacklist.created_at = 2026-11-02 13:47:19`（本人退出登录） | — |
| 文件大小 | 35 045 376 B = 33.42 MiB，与批次日志 09:36 记录的「DB 33.4 MB」**逐字节同尺寸** | 46 329 856 B = 44.18 MiB（+10.8 MiB，测试数据增长） |
| `pragma integrity_check` / `freelist_count` | ok / 0 | ok |

只要压测流量打到生产实例，`favorite`、`play_log`、`comment`、`feedback`、`audit_log` 必然出现
2026-11-03 的行；实测为 0 行，因此**生产数据未受任何影响**。

## 2. 流量层：测试流量不可能到达生产实例

- 14 个 JMX 中出现的唯一目标地址是 `http://127.0.0.1:8021`（`grep` 全量 JMX 结果只有这一条），
  生产实例监听 `APP_PORT=8000`（`backend/.env:10`）。
- 单发探针与 `seed_auth.py` 同样只打 8021 / 只连沙箱库（`seed_auth.py:22,302` 指向 `sandbox/backend/data/news.db`）。
- 批次当天（11-03）全仓没有任何生产应用日志产出：`backend/logs/` 最新文件仍是
  `MorningBrief_2026-11-02.log`（21:44），仓库根也没有 `logs/` 目录 → 生产实例在压测期间并未在服务，
  自然没有请求可被它处理。

## 3. 生产库文件时间戳的解释（不做回避）

生产库确实被"打开过"，时间戳如下，需要说清是谁、做了什么：

| 文件 | mtime | 解释 |
|---|---|---|
| `backend/data/news.db` | 11-03 **11:19:06** | 主文件被重写 = SQLite 对既有 WAL 帧做恢复/检查点。**与压测无关**：同一时刻的开发指纹是 `backend/app/main.py` 11:09 被编辑、`app/__pycache__/main.cpython-312.pyc`、`models/channel`、`services/channel_service`、`services/channel_prompt_service` 在 11:14–11:15 重新生成 —— 这是 T04111「频道创建自动生成全网搜索提示词模板」的并发开发（该提交 7a401df 为当前 HEAD）。 |
| `backend/data/news.db-wal` | 11-03 **13:00:47**（0 B） | 最后一次连接关闭时把 WAL 检查点清零；`backend/data/` 目录 mtime 同为 13:00:47。 |
| `backend/data/news.db-shm` | 11-03 18:28:36、11-04 22:16 | `-shm` 侧车文件。**注意：只读取证 WAL 库也会写 `-shm`** —— 上面 11-04 的一次就是我今天用 `mode=ro` 做本取证时留下的。 |

要点：检查点只是把**早已提交**的 11-02 事务从 WAL 落进主文件，不新增/修改任何行；
证据是 §1 中「文件尺寸与 09:36 快照逐字节相同、freelist=0、全库无 11-03 行」。
压测装置对生产库的唯一一次访问是 `sandbox.py:107` 的 `mode=ro` 在线备份（只读，不检查点）。

## 4. 生产 COS：本批零写入，10-31 批留下 1 个测试对象

见同目录 [`cos_isolation_audit.md`](cos_isolation_audit.md)（可复算）：

- 2026-11-03 批次：`.env` 副本按 `scrub_env_keys` 清空 10 项外部凭据，COS 桶内
  **LastModified 晚于 09:36 沙箱启动的对象为 0 个**。
- 2026-10-31 批次（当时未清空凭据）：仅 `play_progress/950020/100.json`（130 B，2026-10-31T08:30:44Z）
  一个对象，属于压测夹具账号自己的前缀；`jwt_blacklist/`、`episodes/`、`tts/` 前缀零新增。

## 5. 出站流量（不影响生产数据，但要记录）

沙箱在 09:39–09:54 触发过一次书源索引后台构建：向 `raw.githubusercontent.com` 抓取 943 个分类
（935.3 s，成功 886 / 失败 57，产出 3.6 MB 索引写入**沙箱**数据目录）。这是只读 GET、无费用、
不写生产数据，但它同时污染了 9 个阶梯档位 —— 已在 `sandbox.py` 用 `_seed_ebook_index()` 预置索引消除，
并配置 `perf_config.json: sandbox.seed_ebook_index = true`。

## 6. 顺带发现的生产侧风险（非压测造成，建议处理）

1. **生产库没有任何备份**：`backend/data/backup/` 是空目录，而库为 33.4 MB 单文件 WAL。压测批次本身没碰数据，
   但这意味着任何一次误操作都没有回退点。
2. **`JWT_SECRET` 仍是占位符**（`backend/.env:32`）。沙箱刻意保留同一 secret 以签发测试 token，
   因此隔离完全依赖"端口只打 8021"这一条；若哪天有人把流量指向 8000，沙箱签发的 token 会被生产实例接受。
   建议在压测装置里改为沙箱自签 secret（`env_overrides` 加一条即可）。
3. 只做取证时也建议用 `?immutable=1` 打开生产库，避免写 `-shm`（本次已产生该副作用，无害但会扰动 mtime）。
4. 11-03 的 soak 第 5–6 窗口吞吐掉到 71–75 RPS（其余窗口 120–168），同期服务端 CPU 从 ~115% 跌到 12–80%、
   RSS 平稳 —— 是**客户端侧被并发开发进程挤占**，不是服务劣化；长跑建议独占机器，或把开发进程暂停。

## 7. 复算命令

```bash
cd /d/code/otherProjects/20_News && PY=backend/.venv/Scripts/python.exe
# §1 生产库零写入
"$PY" - <<'EOF'
import sqlite3
c=sqlite3.connect("file:backend/data/news.db?mode=ro",uri=True).execute
for t in ("user","admin_user","favorite","play_log","comment","audit_log","feedback"):
    print(t, c(f'select count(*) from "{t}"').fetchone()[0])
print("user 950020:", c("select count(*) from user where id=950020").fetchone()[0])
print("perf_admin :", c("select count(*) from admin_user where username='perf_admin'").fetchone()[0])
print("size:", c("pragma page_count").fetchone()[0]*c("pragma page_size").fetchone()[0], "freelist:", c("pragma freelist_count").fetchone()[0])
EOF
# §2 流量目标端口
grep -ohE "https?://[0-9a-zA-Z.:-]+" scripts/jmeter_test/full_api/jmx/*.jmx | sort -u
# §4 COS 足迹（只读 list_objects）
"$PY" scripts/jmeter_test/full_api/runtime/cos_write_scope.py
# §5 污染窗口的抓取日志
grep -n "ebook_index" scripts/jmeter_test/full_api/sandbox/server.stdout.log | tail
```
