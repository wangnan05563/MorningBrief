# 全量 API 压测装置（JMeter 原生 CLI）

覆盖 243 个端点：基线 → 阶梯压测 → ≥4h 稳定性，全程只打沙箱 `127.0.0.1:8021`，
生产实例在 `:8000`。所有可调参数集中在 `perf_config.json`，脚本内不写死阈值。

## 目录

| 路径 | 作用 |
|---|---|
| `perf_config.json` | 端口、限速覆盖、`.env` 需清空的凭据键、阶梯线程数、soak 时长、采样间隔 |
| `sandbox.py` | `prepare`（在线备份生产库 + 拷贝 app + 洗凭据）/ `start` / `stop` / `status` |
| `seed_auth.py` | 建压测夹具账号（`user`、`admin_user`）并签发 token 到 `runtime/tokens.json` |
| `gen_jmx.py` | 由 `runtime/cases.json` 生成 14 个 JMX 到 `jmx/` |
| `probe_all.py` | 单发探针（probed / static-only / sse 分类）→ `results/probes.json` |
| `run_suite.py` | `--baseline` / `--stress` / `--soak`，每阶段自动挂 `monitor.py` sidecar |
| `monitor.py` | ctypes psapi/kernel32 采样 RSS/CPU/句柄/DB/WAL/磁盘 → `results/monitor_<tag>.csv` |
| `analyze.py` | JTL → `results/report_data.json` + `tables.md` + `per_endpoint.csv` + `appendix_endpoints.md` |
| `make_report.py <快照>` | `report_data.json` → 逐接口附件 `per_endpoint.csv` + `appendix_endpoints.md`（快照传本次 `results/report_data.json` 即可） |
| `rerun_all.bat` | 无人值守整批（prepare → … → soak → analyze → report → stop），落 `runtime/all.done` |

## 全批复现

```bash
# 在仓库根目录执行，路径相对仓库根推导
cd scripts/jmeter_test/full_api
PY=../../../backend/.venv/Scripts/python.exe
"$PY" sandbox.py prepare --force && "$PY" sandbox.py start
"$PY" seed_auth.py && "$PY" gen_jmx.py
"$PY" probe_all.py && "$PY" run_suite.py --baseline && "$PY" run_suite.py --stress && "$PY" run_suite.py --soak
"$PY" analyze.py && "$PY" make_report.py results/report_data.json
"$PY" sandbox.py stop
```

长跑（soak 4h+）必须脱离终端会话，用隐藏窗口起批处理，不要直接前台跑：

```bash
powershell -NoProfile -Command "Start-Process cmd.exe -ArgumentList '/c rerun_all.bat' -WindowStyle Hidden"
```

`.bat` 只写 ASCII，注释也不能用中文——否则在 GBK 控制台回显成乱码并可能截断命令。

## 复跑单个阶段

阶梯或 soak 若被后台任务污染（例：11-03 首轮阶梯期间书源索引正在外呼爬取），
不要整批重跑，按下面做单阶段复跑，同时把被污染的原始产物**移走备查而不是删除**：

```bash
mkdir -p results/contaminated_<原因>
mv results/stress_*.jtl results/stress_*.log results/monitor_stress.csv results/contaminated_<原因>/
"$PY" sandbox.py start          # 复跑前确认沙箱活着：sandbox.py status
"$PY" run_suite.py --stress     # 同理 --soak / --baseline
"$PY" analyze.py && "$PY" make_report.py results/report_data.json
```

两条必须遵守的口径：

1. `run_suite.py` 里 JMeter 的 `-l` 是**追加**写，每个阶段跑前会 `unlink` 同名 JTL；
   手工补跑时也要先删旧 JTL，否则两轮样本混进一个文件，百分位数全错。
2. 复跑后必须重跑 `analyze.py`（它会重写 `report_data.json`），再复制快照。
   `rerun_all.bat` 把 `stage_a_snapshot.json` 的生成挪到了 `analyze.py` 之后，就是这个原因。

## 已知坑

- `python3` 在本机是坏桩（exit 49），一律用绝对路径 `backend/.venv/Scripts/python.exe`。
- 终端回显是 GBK，读日志要 `| iconv -f gbk -t utf-8`；但 `results/*.md`、`*.json` 本身是
  UTF-8，**再 iconv 会变成乱码**。
- 长命令不要用 `| head` / `| grep` 收尾：退出码会被管道吞掉，失败看起来像成功。
- `monitor.py` 在 SUT 关停后仍会写 `rss=0` 的行，算斜率前先按 PID 过滤。
- 沙箱被 `sandbox.py stop` 之外的方式杀掉的残留 `STOP` / 锁文件，会让下一次 sidecar
  变成孤儿进程；按命令行（不是映像名）定位后再停。
- `make_report.py` 的**默认**快照参数指向已不存在的 `results/archive_round1_0929/`，
  不传参直接跑会报错——始终显式传 `results/report_data.json`。
