# T01659 验证数据汇总（无密钥版）

原始日志（含 JWT 前缀 / Tailscale Funnel 公网地址）为临时取证产物，不入库，测完即删。

## 1. perf_gate --tier quick（workers=1，三次运行）

| 运行 | 树状态 | S0 P95/TPS | S1_read_50 P95/TPS | S2_write_50 P95/TPS | 结论 |
|--|--|--|--|--|--|
| R1 02:18 | pool ON(T01662 已提交) + 本单改动 | 752.0ms / 75.82 | 7066.7ms / 37.32 | 6393.4ms / 14.24 | FAIL |
| R2 02:27 | 同 R1（同代码同配置复跑） | 1115.0ms / 47.18 | 5414.2ms / 44.04 | 10021.8ms / 10.23 | FAIL |
| R3 02:33 | 同 R1 + `SQLITE_POOL_ENABLED=false` | 1253.0ms / 39.27 | 5960.5ms / 37.19 | 22683.0ms / 6.36 | FAIL |
| 门禁基线 | gate_config.json（T01623 标定） | 549→限714 / 56.4 | 2223→限2890 / 71.1 | 4337→限5638 / 18.5 | — |

归因（可信度声明）：
- **同一代码、同一配置的 R1↔R2 抖动**：S0 P95 752→1115（+48%）、TPS 75.8→47.2（−38%）。
  抖动幅度大于「本单改动」的量级（每请求 ≤1ms），故门禁 FAIL 无法归因于本单，
  本机 CPU 长期 44–93% 与并发会话（T01662 提交 02:12、其 A/B 复跑）共同压制，
  绝对值判定需等 **T01661 空闲机复跑**。
- **方向一致性**：R3（关连接池）在三个档位上都比 R1/R2（开池）更差，
  S2_write TPS 6.36 vs 10.2–14.2 —— 与 T01662「池化降低每请求建连」的结论同向，
  未见本单接线引入回归的证据。
- S0_baseline R1 无一条 >3s 样本（max 1572ms、P50 8ms），仅 P95 触线 714ms，属边缘破线。

## 2. openid 缓存单变量 A/B（同进程交替，不依赖压测机负载）

`_validate/t01659_openid_ab.py` → `_validate/t01659_openid_ab.json`
600 对样本，A=每次 SELECT openid，B=命中进程内 TTLCache，业务 SQL 相同：

| 指标 | A（改造前） | B（改造后） |
|--|--|--|
| P50 | 2.726ms | 1.805ms |
| P95 | 3.524ms | 2.249ms |
| 均值 | 2.777ms | 1.836ms |

每请求削减 **0.941ms（33.9%）**。
注意：这是 T01662 池化后的**净值**——T01617 记的「该段 64.24ms 中约 41ms 是建连」，
建连已被池化吃掉，缓存真正省下的是「一次 SELECT 往返」，约 1ms/请求（9 个调用点各一处）。

## 3. 正确性（跨用户隔离，52 用户矩阵）

`_validate/t01659_openid_cache_check.py`（dev 库只读副本 + 副本内补造 50 用户）：10/10 断言通过
——52/52 用户缓存后仍各自返回自身 openid；键按 user_id 维度无串号；
单用户失效不波及其它用户；不存在用户抛 NotFoundError 且不写负缓存；
cold 59.87ms → warm 0.249ms。

## 4. workers=2 实验（launcher.py 接线，端口 8101，观测后即刻停）

`_validate/t01659_w2_launcher.log`（含敏感行，不入库）计数结果：

| 启动副作用 | 次数 | 说明 |
|--|--|--|
| Application startup complete | 2 | 两进程各自完整启动 |
| WorkflowScheduler 已启动 | 2 | 各注册 8 个定时任务 + 1 个频道级 cron（**05:00 工作流会跑两遍 = 双倍 LLM/TTS 预算**） |
| EventBus 启动 | 2 | 同一事件被两个消费者各取一次 |
| 内网穿透隧道已自动启动 | 2 | Tailscale Funnel 重复建立 |
| 通知发送完成 | 2 | 隧道启动通知**重复外发**（用户可见） |
| 迁移失败 / Traceback / database is locked | 0 | DDL 迁移在双进程竞态下幂等安全 |

功能面：健康检查通过；24 次 `/api/v1/favorites` 读全部 200；写路径 8 次 POST（7×200 + 1×404 空档）
与 7 次 DELETE 全部 200，无 500。停服用 `taskkill /F /T` 进程树回收，端口即刻释放（workers>1 时
terminate() 只杀父进程，残留 worker 会继续占端口污染下一轮门禁，故 perf_gate stop_backend 已加树杀 + 按端口清扫）。

## 5. perf_gate --workers 2 集成路径（02:45 起，未拿到 gate_report）

`--tier quick --only S0_baseline --workers 2`：
- start_backend 以 `--workers 2` 拉起并通过健康检查（日志确认 2 个 worker 进程号）；
- JMeter 侧 60s 档跑完：3870 样本全 200/OK、`elapsed>5s` 为 0、jmeter.log 显示 02:47:14 全部线程 finished；
- **但 gate 主进程在 jmeter 步骤后停摆 >10 分钟未进入 analyze**（stdout 未捕获、无残留 cmd/java 子进程可查，
  result.jtl 末行未 flush 完整），故 workers=2 的门禁指标结论缺失；手动回收进程树后 8100 端口干净、
  `cleanup_seed.py` 复核 perf 夹具 0 条、`[INTEGRITY] ok`。
- 定性：停摆发生在压测工具链侧（被测系统全程正常响应），但它是「路线 A 用 gate 直接压多 worker」这条路
  的现实阻断项之一，与第 4 节的重复调度/重复通知同批交给 **T01660**。

## 6. 附带发现（未在本单修）

`loguru` 用 `%s`/`%d` 风格占位符不会格式化，直接把占位符写进日志（实测：
`[startup] 内网穿透隧道已自动启动: %s`、`通知渠道已加载: %s`、`通知发送完成: total=%d success=%d failed=%d`），
运维日志丢失关键值。属独立缺陷，另建单处理（见回传「本次回写」）。
